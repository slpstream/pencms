"""MCP tools for site-private theme file customize (Twig + CSS).

Agents are bound to JWT ``site_id`` — no path ``{site_id}``, no install-theme writes.
All FS via ``theme_customize_service`` (editable allowlist + realpath confinement).
Allowlist: ``templates/**``, ``partials/**`` (``.html.twig`` / ``.twig``) and
``assets/css/**`` (``.css`` only). ``theme.json``, fonts, images, and JS are not
writable. ``validate_theme`` is read-scope advisory only.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from models.user import UserPublic
from routers.auth import get_current_user
from routers.mcp_tools import require_scope, resolve_mcp_site_id
from services.theme_customize_service import (
    ThemeCustomizeError,
    fork,
    get_theme_context,
    list_files,
    patch_file,
    read_file_payload,
    reset,
    reset_file,
    revert_file,
    validate,
    write_file,
)

router = APIRouter(prefix="/api/v1", tags=["mcp"])

WRITE_THEME_FILE_DOC = """FULL REPLACEMENT of an allowlisted file under the bound site's theme tree.

WARNING: This tool REPLACES the entire file content. For a single-section change, prefer ``patch_theme_file``.
Only use this tool for new files or full intentional rewrites — do NOT send partial fragments here.

Editable: ``templates/**`` and ``partials/**`` with ``.html.twig`` / ``.twig``, plus ``assets/css/**`` with ``.css`` only.
Never writes install ``themes/``, ``theme.json``, fonts, images, or JS. Write-through to disk.

Guardrail: If the existing file is >100 bytes and the new content shrinks by >80% (DESTRUCTIVE_WRITE), the request is blocked.
To force a full overwrite, you must pass force=true AND expected_size=<current_on_disk_bytes>.
Errors return structured detail with ``error``, ``reason``, ``hint``, ``expected_size``, and ``revert_available``.
``suggested_action: revert_theme_file`` is included only when a prior write left a snapshot; newly created files have no revision history.

Success responses include lineage fields: ``created`` / ``overwritten`` (mutually exclusive),
``previous_size`` when overwritten, ``guarded`` (true only when a destructive-write override was used),
and a short ``hint`` describing what happened on disk.

Examples:
{"path":"partials/nav.twig","content":"{% extends '_base.html.twig' %}\\n<nav>Full nav template content...</nav>\\n"}
"""

PATCH_THEME_FILE_DOC = """Context-anchored section replace on an allowlisted theme file.

Replaces a unique target string with replacement text. Target must match exactly once in the file.
When exact match fails, a limited fuzzy fallback runs:
1. ``crlf`` — normalize CRLF→LF on both sides, then exact substring match
2. ``line_trim`` — match a unique contiguous block of **whole lines** after stripping
   leading/trailing whitespace on each line

``match_mode`` only affects *finding* the target. The ``replacement`` is always written
literally (matched lines are swapped for the replacement lines as given) — line-trim does
not strip or re-indent the replacement. Internal or mid-line whitespace differences are
**not** normalized — re-read and copy exact bytes.
Use this primitive for section or block edits instead of full file replacement.

Pass ``dry_run=true`` to preview the change: returns ``matched_at_line``, ``match_mode``, and ``unified_diff`` without writing.
Committed (and dry-run) responses include ``match_mode`` (``exact`` / ``crlf`` / ``line_trim``) and ``matched_at_line``.
Also returns ``created: false``, ``overwritten: true``, ``guarded: false``, and a ``hint`` (lineage / dry-run notice).

Examples:
{"path":"partials/nav.twig","target":"<a href=\\"/old\\">","replacement":"<a href=\\"/new\\">"}
{"path":"partials/nav.twig","target":"<a href=\\"/old\\">","replacement":"<a href=\\"/new\\">","dry_run":true}
"""

REVERT_THEME_FILE_DOC = """Revert an allowlisted theme file to its most recent pre-write snapshot.

Restores the previous file state saved before the latest write_theme_file or patch_theme_file operation.
Suggested when a write was blocked (DESTRUCTIVE_WRITE) after a bad prior edit, or after an unwanted patch.
This is NOT the same as reset_theme_file (which re-copies stock content from the parent install theme).

Examples:
{"path":"partials/nav.twig"}
"""

RESET_THEME_FILE_DOC = """Restore one allowlisted theme file from the parent install theme.

Re-copies ``path`` from ``theme.json.parent`` into the site custom tree. No snapshot/history —
this is stock restore from the install base, not undo-last-write (use ``revert_theme_file`` for that).
Use when a file is mangled, the snapshot is already consumed/absent, and you do not want whole-tree
``reset_site_theme``. Same allowlist as write/patch: templates/**, partials/**, assets/css/**.
Fails if the path has no original on the parent (custom-only files).

Examples:
{"path":"partials/nav.twig"}
"""

FORK_SITE_THEME_DOC = """Copy an install base theme into the bound site's private theme tree.

Sets registry theme to ``custom``. Optional ``parent`` slug; omit to infer from
the site's effective theme. Replaces any existing site theme tree.

Example:
{"parent":"starter"}
"""


def _map_service_error(exc: Exception) -> HTTPException:
    msg = str(exc)
    if isinstance(exc, ThemeCustomizeError) and msg.startswith("Unknown site_id:"):
        return HTTPException(status_code=404, detail=msg)
    if isinstance(exc, ThemeCustomizeError) and getattr(exc, "payload", None):
        return HTTPException(status_code=400, detail=exc.payload)
    return HTTPException(status_code=400, detail=msg)


class ForkBody(BaseModel):
    parent: Optional[str] = Field(
        default=None,
        description="Install base slug to fork; omit to infer from effective theme",
    )


class WriteFileBody(BaseModel):
    path: str = Field(..., min_length=1, description="Relative path under site theme/")
    content: str = Field(default="", description="Full file contents")
    force: bool = Field(default=False, description="Set true to force overwrite when shrinking file")
    expected_size: Optional[int] = Field(default=None, description="Must match current on-disk byte size when force is true")


class PatchFileBody(BaseModel):
    path: str = Field(..., min_length=1, description="Relative path under site theme/")
    target: str = Field(..., min_length=1, description="Exact or normalized target string to replace")
    replacement: str = Field(..., description="Replacement text")
    dry_run: bool = Field(
        default=False,
        description="If true, return match metadata and unified_diff without writing",
    )


class RevertFileBody(BaseModel):
    path: str = Field(..., min_length=1, description="Relative path under site theme/")


class ResetFileBody(BaseModel):
    path: str = Field(
        ...,
        min_length=1,
        description="Allowlisted path to restore from parent install theme",
    )


@router.get(
    "/mcp/theme/files",
    operation_id="list_theme_files",
    dependencies=[Depends(require_scope("read"))],
)
async def list_theme_files(
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    """List allowlisted theme files (Twig + assets/css/*.css) under the bound site's theme tree."""
    site_id = resolve_mcp_site_id(request)
    try:
        return {"files": list_files(site_id)}
    except (ThemeCustomizeError, ValueError) as e:
        raise _map_service_error(e) from e


@router.get(
    "/mcp/theme/file",
    operation_id="read_theme_file",
    dependencies=[Depends(require_scope("read"))],
)
async def read_theme_file(
    request: Request,
    path: str = Query(..., min_length=1, description="Relative path under site theme/"),
    if_version: Optional[str] = Query(
        None,
        description="If this mtime token matches on-disk, omit content and set unchanged=true.",
    ),
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    """Read an allowlisted theme file (Twig or CSS) from the bound site's theme tree."""
    site_id = resolve_mcp_site_id(request)
    try:
        return read_file_payload(site_id, path, if_version=if_version)
    except (ThemeCustomizeError, ValueError) as e:
        raise _map_service_error(e) from e


@router.put(
    "/mcp/theme/file",
    operation_id="write_theme_file",
    dependencies=[Depends(require_scope("write:theme"))],
    summary="Write a theme file (Twig or CSS)",
    description=WRITE_THEME_FILE_DOC,
)
async def write_theme_file(
    body: WriteFileBody,
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    site_id = resolve_mcp_site_id(request)
    try:
        return write_file(
            site_id,
            body.path,
            body.content,
            enforce_guardrail=True,
            force=body.force,
            expected_size=body.expected_size,
        )
    except (ThemeCustomizeError, ValueError) as e:
        raise _map_service_error(e) from e


write_theme_file.__doc__ = WRITE_THEME_FILE_DOC


@router.patch(
    "/mcp/theme/file",
    operation_id="patch_theme_file",
    dependencies=[Depends(require_scope("write:theme"))],
    summary="Patch a section in a theme file",
    description=PATCH_THEME_FILE_DOC,
)
async def patch_theme_file(
    body: PatchFileBody,
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    site_id = resolve_mcp_site_id(request)
    try:
        return patch_file(
            site_id,
            body.path,
            body.target,
            body.replacement,
            dry_run=body.dry_run,
        )
    except (ThemeCustomizeError, ValueError) as e:
        raise _map_service_error(e) from e


patch_theme_file.__doc__ = PATCH_THEME_FILE_DOC


@router.post(
    "/mcp/theme/file/revert",
    operation_id="revert_theme_file",
    dependencies=[Depends(require_scope("write:theme"))],
    summary="Revert a theme file to last snapshot",
    description=REVERT_THEME_FILE_DOC,
)
async def revert_theme_file(
    body: RevertFileBody,
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    site_id = resolve_mcp_site_id(request)
    try:
        return revert_file(site_id, body.path)
    except (ThemeCustomizeError, ValueError) as e:
        raise _map_service_error(e) from e


revert_theme_file.__doc__ = REVERT_THEME_FILE_DOC


@router.post(
    "/mcp/theme/file/reset",
    operation_id="reset_theme_file",
    dependencies=[Depends(require_scope("write:theme"))],
    summary="Restore a theme file from parent install theme",
    description=RESET_THEME_FILE_DOC,
)
async def reset_theme_file(
    body: ResetFileBody,
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    site_id = resolve_mcp_site_id(request)
    try:
        return reset_file(site_id, body.path)
    except (ThemeCustomizeError, ValueError) as e:
        raise _map_service_error(e) from e


reset_theme_file.__doc__ = RESET_THEME_FILE_DOC


@router.get(
    "/mcp/theme/context",
    operation_id="get_theme_context",
    dependencies=[Depends(require_scope("read"))],
)
async def mcp_get_theme_context(
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    """Manifest summary, parent, allowlist, active flag, and preview pointer for the bound site theme."""
    site_id = resolve_mcp_site_id(request)
    try:
        return get_theme_context(site_id)
    except (ThemeCustomizeError, ValueError) as e:
        raise _map_service_error(e) from e


@router.post(
    "/mcp/theme/fork",
    operation_id="fork_site_theme",
    dependencies=[Depends(require_scope("write:theme"))],
    summary="Fork install base into site theme tree",
    description=FORK_SITE_THEME_DOC,
)
async def fork_site_theme(
    request: Request,
    body: ForkBody = ForkBody(),
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    site_id = resolve_mcp_site_id(request)
    try:
        return fork(site_id, parent_slug=body.parent)
    except (ThemeCustomizeError, ValueError) as e:
        raise _map_service_error(e) from e


fork_site_theme.__doc__ = FORK_SITE_THEME_DOC


@router.post(
    "/mcp/theme/reset",
    operation_id="reset_site_theme",
    dependencies=[Depends(require_scope("write:theme"))],
)
async def reset_site_theme(
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    """Re-copy the bound site's theme tree from ``theme.json.parent``."""
    site_id = resolve_mcp_site_id(request)
    try:
        return reset(site_id)
    except (ThemeCustomizeError, ValueError) as e:
        raise _map_service_error(e) from e


@router.get(
    "/mcp/theme/validate",
    operation_id="validate_theme",
    dependencies=[Depends(require_scope("read"))],
)
async def validate_theme(
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    """Structural validate of the bound site's custom theme (advisory; never blocks writes).

    Each issue in ``errors`` / ``warnings`` includes ``severity`` (``error`` or ``warning``).
    Agents may self-gate on ``ok === false`` / ``error_count > 0``; warnings alone should not
    stop writes. The server never blocks Save/AI writes based on validate results.
    """
    site_id = resolve_mcp_site_id(request)
    try:
        return validate(site_id)
    except (ThemeCustomizeError, ValueError) as e:
        raise _map_service_error(e) from e
