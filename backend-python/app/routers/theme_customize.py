"""Site-private theme customize REST.

Wraps ``theme_customize_service`` — no filesystem logic here.
Auth: ``write:theme`` on path ``{site_id}``; path is authoritative.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from models.user import UserPublic
from services.authz import assert_capability
from services.site_service import ensure_sites_initialized, get_site
from services.theme_customize_service import (
    ThemeCustomizeError,
    delete,
    fork,
    get_theme_context,
    list_files,
    read_file,
    reset,
    reset_file,
    validate,
    write_file,
)

router = APIRouter(prefix="/sites", tags=["theme-customize"])


def _require_theme_write(request: Request, site_id: str) -> UserPublic:
    return assert_capability(request, "write:theme", site_id=site_id)


def _require_site(site_id: str) -> None:
    ensure_sites_initialized()
    if get_site(site_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown site_id: {site_id}")


def _map_service_error(exc: Exception) -> HTTPException:
    msg = str(exc)
    if isinstance(exc, ThemeCustomizeError) and msg.startswith("Unknown site_id:"):
        return HTTPException(status_code=404, detail=msg)
    return HTTPException(status_code=400, detail=msg)


class ForkBody(BaseModel):
    parent: Optional[str] = Field(
        default=None,
        description="Install base slug to fork; omit to infer from effective theme",
    )


class WriteFileBody(BaseModel):
    path: str = Field(..., min_length=1)
    content: str = ""


class ResetFileBody(BaseModel):
    path: str = Field(..., min_length=1, description="Allowlisted path to restore from parent")


@router.post("/{site_id}/theme/fork")
async def post_theme_fork(
    site_id: str,
    request: Request,
    body: ForkBody = ForkBody(),
):
    """Copy install base → site theme tree; set registry theme to ``custom``."""
    _require_theme_write(request, site_id)
    _require_site(site_id)
    try:
        return fork(site_id, parent_slug=body.parent)
    except (ThemeCustomizeError, ValueError) as e:
        raise _map_service_error(e) from e


@router.get("/{site_id}/theme/context")
async def get_theme_context_endpoint(
    site_id: str,
    request: Request,
):
    """Parent, name, active?, preview pointer, paths summary for Themes picker / Customize."""
    _require_theme_write(request, site_id)
    _require_site(site_id)
    try:
        return get_theme_context(site_id)
    except (ThemeCustomizeError, ValueError) as e:
        raise _map_service_error(e) from e


@router.get("/{site_id}/theme/tree")
async def get_theme_tree(
    site_id: str,
    request: Request,
):
    """List allowlisted theme files (Twig + assets/css/*.css) under the site theme tree."""
    _require_theme_write(request, site_id)
    _require_site(site_id)
    try:
        return {"files": list_files(site_id)}
    except (ThemeCustomizeError, ValueError) as e:
        raise _map_service_error(e) from e


@router.get("/{site_id}/theme/file")
async def get_theme_file(
    site_id: str,
    request: Request,
    path: str = Query(..., min_length=1),
):
    """Read an allowlisted theme file."""
    _require_theme_write(request, site_id)
    _require_site(site_id)
    try:
        content = read_file(site_id, path)
        return {"path": path, "content": content}
    except (ThemeCustomizeError, ValueError) as e:
        raise _map_service_error(e) from e


@router.put("/{site_id}/theme/file")
async def put_theme_file(
    site_id: str,
    body: WriteFileBody,
    request: Request,
):
    """Write an allowlisted theme file (Twig or assets/css/*.css). Never writes install themes."""
    _require_theme_write(request, site_id)
    _require_site(site_id)
    try:
        result = write_file(site_id, body.path, body.content, enforce_guardrail=False)
        return result
    except (ThemeCustomizeError, ValueError) as e:
        raise _map_service_error(e) from e


@router.post("/{site_id}/theme/reset")
async def post_theme_reset(
    site_id: str,
    request: Request,
):
    """Re-copy site theme tree from ``theme.json.parent``."""
    _require_theme_write(request, site_id)
    _require_site(site_id)
    try:
        return reset(site_id)
    except (ThemeCustomizeError, ValueError) as e:
        raise _map_service_error(e) from e


@router.post("/{site_id}/theme/reset-file")
async def post_theme_reset_file(
    site_id: str,
    body: ResetFileBody,
    request: Request,
):
    """Restore one allowlisted file from ``theme.json.parent`` (no history)."""
    _require_theme_write(request, site_id)
    _require_site(site_id)
    try:
        return reset_file(site_id, body.path)
    except (ThemeCustomizeError, ValueError) as e:
        raise _map_service_error(e) from e


@router.post("/{site_id}/theme/validate")
async def post_theme_validate(
    site_id: str,
    request: Request,
):
    """Structural validate of the site custom theme (advisory; never blocks Save)."""
    _require_theme_write(request, site_id)
    _require_site(site_id)
    try:
        return validate(site_id)
    except (ThemeCustomizeError, ValueError) as e:
        raise _map_service_error(e) from e


@router.delete("/{site_id}/theme")
async def delete_theme(
    site_id: str,
    request: Request,
):
    """Delete site theme tree; revert registry if theme was ``custom``."""
    _require_theme_write(request, site_id)
    _require_site(site_id)
    try:
        return delete(site_id)
    except (ThemeCustomizeError, ValueError) as e:
        raise _map_service_error(e) from e
