"""Site-private theme fork under ``content/sites/{id}/theme/``.

Install themes under ``frontend-php/src/blog/themes/`` are immutable from
this module. Editable allowlist (Slice 1+2): ``templates/**`` and
``partials/**`` with ``.html.twig`` / ``.twig``, plus ``assets/css/**`` with
``.css`` only. ``theme.json`` is service-managed only. Fonts, images, and JS
are never listed or writable.
"""

from __future__ import annotations

import difflib
import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

from services.site_service import (
    get_site,
    get_site_content_prefix,
    update_site,
)
import services.social_preview as social_preview

logger = logging.getLogger("pencms.theme_customize")

RESERVED_THEME_ID = "custom"
ORIGIN_SITE_CUSTOM = "site-custom"

# Prefix → allowed extensions (prefix AND matching extension).
TWIG_PREFIXES = ("templates/", "partials/")
TWIG_EXTENSIONS = (".html.twig", ".twig")
CSS_PREFIX = "assets/css/"
CSS_EXTENSIONS = (".css",)

EDITABLE_PREFIXES = TWIG_PREFIXES + (CSS_PREFIX,)
EDITABLE_EXTENSIONS = TWIG_EXTENSIONS + CSS_EXTENSIONS

# Walk roots under the site theme tree (posix relative dir names).
EDITABLE_WALK_DIRS = ("templates", "partials", "assets/css")


class ThemeCustomizeError(ValueError):
    """Raised for invalid theme customize operations (confinement, allowlist, missing tree)."""

    def __init__(self, message: str, *, payload: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.payload = payload


def site_theme_prefix(site_id: str) -> str:
    """Storage-relative prefix for the site theme tree (e.g. ``sites/wiki/theme``)."""
    return f"{get_site_content_prefix(site_id)}/theme"


def site_theme_root(site_id: str) -> Path:
    """Absolute filesystem path to ``content/sites/{id}/theme``."""
    from config import CONTENT_DIR_PATH

    if CONTENT_DIR_PATH is None:
        raise ThemeCustomizeError(
            "Theme customize requires local CONTENT_DIR_PATH"
        )
    return Path(CONTENT_DIR_PATH) / site_theme_prefix(site_id)


def has_site_custom_theme(site_id: str) -> bool:
    """True when the site has a valid custom theme tree (dir + theme.json)."""
    try:
        root = site_theme_root(site_id)
    except (ThemeCustomizeError, ValueError):
        return False
    return root.is_dir() and (root / "theme.json").is_file()


def resolve_theme_dir(site_id: str, theme_name: Optional[str] = None) -> Path:
    """Resolve absolute theme directory for a site + theme slug.

    When ``theme_name`` is ``custom`` (or omitted and registry says custom),
    returns the site theme tree. Otherwise returns the install theme dir.
    """
    site = get_site(site_id)
    if site is None:
        raise ThemeCustomizeError(f"Unknown site_id: {site_id}")

    name = (theme_name or social_preview.effective_theme_name(site) or "").strip() or "starter"
    if name == RESERVED_THEME_ID:
        root = site_theme_root(site_id)
        if not root.is_dir() or not (root / "theme.json").is_file():
            raise ThemeCustomizeError(
                f"Site '{site_id}' theme is 'custom' but no valid theme tree "
                f"exists at {site_theme_prefix(site_id)}/"
            )
        return root.resolve()

    base = social_preview.themes_root() / name
    if not base.is_dir() or not (base / "theme.json").is_file():
        raise ThemeCustomizeError(
            f"Theme '{name}' is not installed under themes/"
        )
    return base.resolve()


def _normalize_rel(rel: str) -> str:
    raw = rel or ""
    if raw.startswith("/") or raw.startswith("\\"):
        raise ThemeCustomizeError("Absolute paths are not allowed")
    # Windows-style drive path
    if len(raw) >= 2 and raw[1] == ":" and raw[0].isalpha():
        raise ThemeCustomizeError("Absolute paths are not allowed")
    clean = raw.replace("\\", "/").strip("/")
    if not clean:
        raise ThemeCustomizeError("Path is required")
    parts: List[str] = []
    for seg in clean.split("/"):
        if not seg or seg == ".":
            continue
        if seg == ".." or seg.startswith(".."):
            raise ThemeCustomizeError("Path traversal not allowed")
        parts.append(seg)
    if not parts:
        raise ThemeCustomizeError("Path is required")
    return "/".join(parts)


def confine_theme_path(site_id: str, rel: str) -> Path:
    """Resolve ``rel`` under the site theme root; realpath must stay inside."""
    normalized = _normalize_rel(rel)
    root = site_theme_root(site_id).resolve()
    if not root.is_dir():
        raise ThemeCustomizeError(
            f"No site theme tree at {site_theme_prefix(site_id)}/"
        )
    candidate = (root / normalized).resolve()
    root_s = str(root)
    cand_s = str(candidate)
    if cand_s != root_s and not cand_s.startswith(root_s + "/"):
        raise ThemeCustomizeError("Path escapes site theme root")
    return candidate


def _extensions_for_prefix(rel: str) -> Optional[Tuple[str, ...]]:
    """Return allowed extensions for ``rel``, or None if prefix is not editable."""
    if any(rel.startswith(p) for p in TWIG_PREFIXES):
        return TWIG_EXTENSIONS
    if rel.startswith(CSS_PREFIX):
        return CSS_EXTENSIONS
    return None


def _is_allowlisted(rel: str) -> bool:
    if rel.endswith("/") or rel in ("templates", "partials", "assets/css", "assets"):
        return False
    exts = _extensions_for_prefix(rel)
    if exts is None:
        return False
    lower = rel.lower()
    return any(lower.endswith(ext) for ext in exts)


def assert_writable(rel: str) -> str:
    """Normalize and assert editable allowlist. Denies theme.json."""
    normalized = _normalize_rel(rel)
    if normalized == "theme.json" or normalized.endswith("/theme.json"):
        raise ThemeCustomizeError("theme.json is not writable via file API")
    if not _is_allowlisted(normalized):
        raise ThemeCustomizeError(
            f"Path not in editable allowlist (templates/**, partials/** "
            f"with {', '.join(TWIG_EXTENSIONS)}; {CSS_PREFIX}** with "
            f"{', '.join(CSS_EXTENSIONS)}): {normalized}"
        )
    return normalized


def _read_theme_json(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ThemeCustomizeError(f"Invalid theme.json: {e}") from e
    if not isinstance(data, dict):
        raise ThemeCustomizeError("theme.json must be a JSON object")
    return data


def _parent_label(parent_slug: str) -> str:
    meta_path = social_preview.themes_root() / parent_slug / "theme.json"
    if meta_path.is_file():
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                name = data.get("name")
                if isinstance(name, str) and name.strip():
                    return name.strip()
        except (OSError, json.JSONDecodeError):
            pass
    return parent_slug


def _apply_fork_metadata(theme_json_path: Path, parent_slug: str) -> Dict[str, Any]:
    data = _read_theme_json(theme_json_path)
    label = _parent_label(parent_slug)
    data["parent"] = parent_slug
    data["origin"] = ORIGIN_SITE_CUSTOM
    data["name"] = f"{label} (custom)"
    data["customized_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    theme_json_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return data


def _install_base_dir(parent_slug: str) -> Path:
    slug = (parent_slug or "").strip()
    if not slug:
        raise ThemeCustomizeError("parent_slug is required")
    if slug == RESERVED_THEME_ID:
        raise ThemeCustomizeError(
            f"Cannot fork from reserved theme id '{RESERVED_THEME_ID}'"
        )
    base = social_preview.themes_root() / slug
    if not base.is_dir() or not (base / "theme.json").is_file():
        raise ThemeCustomizeError(
            f"Parent theme '{slug}' is not installed under themes/"
        )
    # Never treat a rogue install folder named custom as a base (already blocked).
    return base.resolve()


def _copy_base_to_site(site_id: str, parent_slug: str) -> Path:
    base = _install_base_dir(parent_slug)
    dest = site_theme_root(site_id)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(base, dest)
    _apply_fork_metadata(dest / "theme.json", parent_slug)
    return dest


def fork(site_id: str, parent_slug: Optional[str] = None) -> Dict[str, Any]:
    """Full-copy install base → site theme tree; set registry theme to ``custom``."""
    site = get_site(site_id)
    if site is None:
        raise ThemeCustomizeError(f"Unknown site_id: {site_id}")

    parent = (parent_slug or "").strip() or None
    if parent is None:
        current = social_preview.effective_theme_name(site)
        if current == RESERVED_THEME_ID:
            # Prefer existing tree parent when re-forking without explicit parent
            if has_site_custom_theme(site_id):
                meta = _read_theme_json(site_theme_root(site_id) / "theme.json")
                existing_parent = meta.get("parent")
                if isinstance(existing_parent, str) and existing_parent.strip():
                    parent = existing_parent.strip()
            if parent is None:
                raise ThemeCustomizeError(
                    "Cannot infer parent while theme is 'custom'; "
                    "pass parent_slug explicitly"
                )
        else:
            parent = current

    assert parent is not None
    dest = _copy_base_to_site(site_id, parent)
    _clear_revisions(site_id)
    from services.theme_style_service import rekey_style_overrides_for_fork

    migrated = rekey_style_overrides_for_fork(site.style_overrides, parent)
    if migrated is not None:
        update_site(site_id, theme=RESERVED_THEME_ID, style_overrides=migrated)
    else:
        update_site(site_id, theme=RESERVED_THEME_ID)
    meta = _read_theme_json(dest / "theme.json")
    logger.info("Forked theme for site %s from %s → custom", site_id, parent)
    return {
        "site_id": site_id,
        "theme": RESERVED_THEME_ID,
        "parent": parent,
        "path": site_theme_prefix(site_id),
        "name": meta.get("name"),
        "origin": meta.get("origin"),
        "customized_at": meta.get("customized_at"),
    }


def reset(site_id: str) -> Dict[str, Any]:
    """Re-copy from ``theme.json.parent``; keep registry theme ``custom``."""
    if not has_site_custom_theme(site_id):
        raise ThemeCustomizeError(
            f"No site theme tree to reset for '{site_id}'"
        )
    meta = _read_theme_json(site_theme_root(site_id) / "theme.json")
    parent = meta.get("parent")
    if not isinstance(parent, str) or not parent.strip():
        raise ThemeCustomizeError(
            "Site theme.json is missing parent; cannot reset"
        )
    parent = parent.strip()
    dest = _copy_base_to_site(site_id, parent)
    _clear_revisions(site_id)
    site = get_site(site_id)
    if site is not None and social_preview.effective_theme_name(site) != RESERVED_THEME_ID:
        update_site(site_id, theme=RESERVED_THEME_ID)
    meta = _read_theme_json(dest / "theme.json")
    logger.info("Reset custom theme for site %s from parent %s", site_id, parent)
    return {
        "site_id": site_id,
        "theme": RESERVED_THEME_ID,
        "parent": parent,
        "path": site_theme_prefix(site_id),
        "name": meta.get("name"),
        "customized_at": meta.get("customized_at"),
    }


def reset_file(site_id: str, rel: str) -> Dict[str, Any]:
    """Re-copy one allowlisted path from ``theme.json.parent`` into the site tree.

    No snapshot / revision history — this is stock restore from the install
    parent, not undo-last-write (see ``revert_file``).
    """
    normalized = assert_writable(rel)
    if not has_site_custom_theme(site_id):
        raise ThemeCustomizeError(
            f"No site theme tree to reset for '{site_id}'"
        )
    meta = _read_theme_json(site_theme_root(site_id) / "theme.json")
    parent = meta.get("parent")
    if not isinstance(parent, str) or not parent.strip():
        raise ThemeCustomizeError(
            "Site theme.json is missing parent; cannot reset"
        )
    parent = parent.strip()

    base = _install_base_dir(parent).resolve()
    src = (base / normalized).resolve()
    base_s = str(base)
    src_s = str(src)
    if src_s != base_s and not src_s.startswith(base_s + "/"):
        raise ThemeCustomizeError("Path escapes parent theme root")
    if not src.is_file():
        raise ThemeCustomizeError(
            f"No parent original for '{normalized}' in theme '{parent}'"
        )

    dest = confine_theme_path(site_id, normalized)
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Re-check after mkdir that we did not escape
    dest = confine_theme_path(site_id, normalized)
    shutil.copy2(src, dest)

    written_bytes = dest.stat().st_size
    logger.info(
        "Reset file %s for site %s from parent %s",
        normalized,
        site_id,
        parent,
    )
    return _with_file_version(
        {
            "path": normalized,
            "parent": parent,
            "ok": True,
            "restored": True,
            "bytes": written_bytes,
            "hint": f"Restored from parent theme '{parent}'",
        },
        dest,
    )


def delete(site_id: str) -> Dict[str, Any]:
    """Remove site theme tree; if registry was ``custom``, revert to parent."""
    site = get_site(site_id)
    if site is None:
        raise ThemeCustomizeError(f"Unknown site_id: {site_id}")

    parent: Optional[str] = None
    root = site_theme_root(site_id)
    if (root / "theme.json").is_file():
        try:
            meta = _read_theme_json(root / "theme.json")
            p = meta.get("parent")
            if isinstance(p, str) and p.strip():
                parent = p.strip()
        except ThemeCustomizeError:
            pass

    was_custom = social_preview.effective_theme_name(site) == RESERVED_THEME_ID
    reverted_theme: Optional[str] = None
    if was_custom:
        reverted_theme = parent or "starter"
        update_site(site_id, theme=reverted_theme)

    _clear_revisions(site_id)
    if root.exists():
        shutil.rmtree(root)

    logger.info(
        "Deleted custom theme for site %s (reverted=%s parent=%s)",
        site_id,
        was_custom,
        parent,
    )
    return {
        "site_id": site_id,
        "deleted": True,
        "reverted_theme": reverted_theme,
        "parent": parent,
    }


# ── Revisions (Disk-only, N=10 max, outside theme/ tree) ───────────────────

REVISION_MAX = 10


def _site_revisions_root(site_id: str) -> Path:
    from config import CONTENT_DIR_PATH

    if CONTENT_DIR_PATH is None:
        raise ThemeCustomizeError(
            "Theme customize requires local CONTENT_DIR_PATH"
        )
    return Path(CONTENT_DIR_PATH) / get_site_content_prefix(site_id) / ".theme-revisions"


def _clear_revisions(site_id: str) -> None:
    try:
        rev_root = _site_revisions_root(site_id)
        if rev_root.exists():
            shutil.rmtree(rev_root)
    except Exception as e:
        logger.warning("Failed to clear revisions for site %s: %s", site_id, e)


def _rev_key(rel: str) -> str:
    return rel.replace("/", "__").replace("\\", "__")


def _has_revision(site_id: str, rel: str) -> bool:
    """True when at least one pre-write snapshot exists for ``rel``."""
    try:
        key_dir = _site_revisions_root(site_id) / _rev_key(rel)
        if not key_dir.is_dir():
            return False
        return any(key_dir.glob("*.txt"))
    except ThemeCustomizeError:
        return False


def _destructive_write_error(
    *,
    normalized: str,
    current_bytes: int,
    new_bytes: int,
    ratio: float,
    expected_size: Optional[int],
    force: bool,
    revert_available: bool,
) -> ThemeCustomizeError:
    """Build a DESTRUCTIVE_WRITE error with structured payload for MCP clients."""
    message = (
        f"DESTRUCTIVE_WRITE: Proposed write to '{normalized}' reduces size from "
        f"{current_bytes} to {new_bytes} bytes (ratio {ratio:.1%}). "
        f"revert_available={'true' if revert_available else 'false'}. "
    )
    if force and expected_size is not None and expected_size != current_bytes:
        message += (
            f"force=true was set but expected_size={expected_size} does not match "
            f"on-disk size {current_bytes}. Re-read the file and retry with "
            f"force=true and expected_size={current_bytes}. "
            f"Prefer patch_theme_file for section edits. "
        )
    else:
        message += (
            "Prefer patch_theme_file for section edits. "
            f"To force full overwrite, pass force=true and expected_size={current_bytes}. "
        )
    if revert_available:
        message += "If a prior write was bad, call revert_theme_file."
        hint = (
            "Prefer patch_theme_file for section edits. If a prior write corrupted the file, "
            f"call revert_theme_file first. To force full overwrite, re-read and resubmit with "
            f"force=true and expected_size={current_bytes}."
        )
    else:
        message += (
            "No revision history for this path — do not call revert_theme_file; "
            "re-read and rewrite with force=true and matching expected_size, or use patch_theme_file."
        )
        hint = (
            "Prefer patch_theme_file for section edits. No revision history for this path — "
            "do not call revert_theme_file. To force full overwrite, re-read and resubmit with "
            f"force=true and expected_size={current_bytes}."
        )

    payload: Dict[str, Any] = {
        "error": "DESTRUCTIVE_WRITE",
        "reason": message,
        "hint": hint,
        "path": normalized,
        "current_bytes": current_bytes,
        "proposed_bytes": new_bytes,
        "expected_size": current_bytes,
        "revert_available": revert_available,
    }
    if revert_available:
        payload["suggested_action"] = "revert_theme_file"
    return ThemeCustomizeError(message, payload=payload)


def _snapshot_revision(site_id: str, rel: str) -> None:
    try:
        path = confine_theme_path(site_id, rel)
        if not path.is_file():
            return
        content = path.read_text(encoding="utf-8")
        key_dir = _site_revisions_root(site_id) / _rev_key(rel)
        key_dir.mkdir(parents=True, exist_ok=True)
        import time

        timestamp = int(time.time() * 1000000)
        rev_file = key_dir / f"{timestamp}.txt"
        rev_file.write_text(content, encoding="utf-8")

        # Prune older revisions if count > REVISION_MAX
        rev_files = sorted(key_dir.glob("*.txt"))
        if len(rev_files) > REVISION_MAX:
            for old_file in rev_files[:-REVISION_MAX]:
                try:
                    old_file.unlink()
                except OSError:
                    pass
    except Exception as e:
        logger.warning(
            "Failed to snapshot revision for site %s, rel %s: %s", site_id, rel, e
        )


def _file_version_token(path: Path) -> Optional[str]:
    """Opaque mtime token, same shape as content ``page_version_token``."""
    try:
        return f"{path.stat().st_mtime:.6f}"
    except OSError:
        return None


def _with_file_version(result: Dict[str, Any], path: Path) -> Dict[str, Any]:
    token = _file_version_token(path)
    if token is not None:
        result["version"] = token
    return result


def revert_file(site_id: str, rel: str) -> Dict[str, Any]:
    """Revert an allowlisted theme file to its last pre-write snapshot."""
    normalized = assert_writable(rel)
    path = confine_theme_path(site_id, normalized)
    key_dir = _site_revisions_root(site_id) / _rev_key(normalized)
    if not key_dir.is_dir():
        raise ThemeCustomizeError(
            f"NO_REVISION: No revision history available to revert '{normalized}'."
        )
    rev_files = sorted(key_dir.glob("*.txt"))
    if not rev_files:
        raise ThemeCustomizeError(
            f"NO_REVISION: No revision history available to revert '{normalized}'."
        )
    latest = rev_files.pop()
    reverted_content = latest.read_text(encoding="utf-8")
    latest.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(reverted_content, encoding="utf-8")
    content_bytes = len(reverted_content.encode("utf-8"))
    content_lines = len(reverted_content.splitlines())
    return _with_file_version(
        {
            "path": normalized,
            "reverted": True,
            "bytes": content_bytes,
            "lines": content_lines,
            "ok": True,
        },
        path,
    )


def list_files(site_id: str) -> List[Dict[str, Any]]:
    """List allowlisted files under the site theme tree (Twig + CSS) with metadata."""
    root = site_theme_root(site_id).resolve()
    if not root.is_dir():
        raise ThemeCustomizeError(
            f"No site theme tree at {site_theme_prefix(site_id)}/"
        )
    out: List[Dict[str, Any]] = []
    for prefix in EDITABLE_WALK_DIRS:
        base = root / prefix
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            if _is_allowlisted(rel):
                # Confinement check
                confine_theme_path(site_id, rel)
                try:
                    text = path.read_text(encoding="utf-8")
                    file_bytes = path.stat().st_size
                    file_lines = len(text.splitlines())
                except OSError:
                    file_bytes = 0
                    file_lines = 0
                out.append({"path": rel, "bytes": file_bytes, "lines": file_lines})
    return out


def read_file(site_id: str, rel: str) -> str:
    """Read an allowlisted theme file (Twig or CSS)."""
    normalized = assert_writable(rel)
    path = confine_theme_path(site_id, normalized)
    if not path.is_file():
        raise ThemeCustomizeError(f"File not found: {normalized}")
    return path.read_text(encoding="utf-8")


def read_file_payload(
    site_id: str,
    rel: str,
    if_version: Optional[str] = None,
) -> Dict[str, Any]:
    """MCP read: content + version, or ``unchanged`` when ``if_version`` matches."""
    normalized = assert_writable(rel)
    path = confine_theme_path(site_id, normalized)
    if not path.is_file():
        raise ThemeCustomizeError(f"File not found: {normalized}")
    content = path.read_text(encoding="utf-8")
    content_bytes = len(content.encode("utf-8"))
    content_lines = len(content.splitlines())
    version = _file_version_token(path)
    payload: Dict[str, Any] = {
        "path": normalized,
        "size": content_bytes,
        "bytes": content_bytes,
        "lines": content_lines,
        "version": version,
    }
    want = (if_version or "").strip()
    if want and version and want == version:
        payload["unchanged"] = True
        return payload
    payload["content"] = content
    payload["unchanged"] = False
    return payload


def write_file(
    site_id: str,
    rel: str,
    content: str,
    *,
    enforce_guardrail: bool = False,
    force: bool = False,
    expected_size: Optional[int] = None,
) -> Dict[str, Any]:
    """Write an allowlisted theme file. Never writes install themes."""
    normalized = assert_writable(rel)
    path = confine_theme_path(site_id, normalized)

    new_str = content if content is not None else ""
    new_bytes = len(new_str.encode("utf-8"))
    previous_size: Optional[int] = None
    created = not path.is_file()
    guarded = False

    if path.is_file():
        existing_text = path.read_text(encoding="utf-8")
        current_bytes = len(existing_text.encode("utf-8"))
        previous_size = current_bytes

        if enforce_guardrail and current_bytes > 100 and new_bytes < 0.20 * current_bytes:
            if not (force and expected_size == current_bytes):
                ratio = new_bytes / current_bytes if current_bytes > 0 else 0.0
                revert_available = _has_revision(site_id, normalized)
                raise _destructive_write_error(
                    normalized=normalized,
                    current_bytes=current_bytes,
                    new_bytes=new_bytes,
                    ratio=ratio,
                    expected_size=expected_size,
                    force=force,
                    revert_available=revert_available,
                )
            # Shrink threshold crossed but force+expected_size overrode the block.
            guarded = True

        _snapshot_revision(site_id, normalized)

    path.parent.mkdir(parents=True, exist_ok=True)
    # Re-check after mkdir that we did not escape
    path = confine_theme_path(site_id, normalized)
    path.write_text(new_str, encoding="utf-8")

    written_bytes = path.stat().st_size
    written_lines = len(new_str.splitlines())
    if created:
        hint = "Created new file"
    elif guarded:
        hint = (
            f"Overwrote existing file with destructive-write override "
            f"(previous_size={previous_size})"
        )
    else:
        hint = f"Overwrote existing file (previous_size={previous_size})"

    res: Dict[str, Any] = {
        "path": normalized,
        "bytes": written_bytes,
        "lines": written_lines,
        "ok": True,
        "created": created,
        "overwritten": not created,
        "guarded": guarded,
        "hint": hint,
    }
    if previous_size is not None:
        res["previous_size"] = previous_size
    return _with_file_version(res, path)


def _line_of_index(text: str, index: int) -> int:
    """1-based line number for a character index in ``text``."""
    return text.count("\n", 0, index) + 1


def _unified_diff(before: str, after: str, rel: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{rel}",
            tofile=f"b/{rel}",
        )
    )


def _resolve_patch(
    content: str, target: str, replacement: str, rel: str
) -> Tuple[str, str, int]:
    """Resolve a unique patch. Returns ``(new_content, match_mode, matched_at_line)``."""
    exact_count = content.count(target)
    if exact_count == 1:
        idx = content.find(target)
        new_content = content[:idx] + replacement + content[idx + len(target) :]
        return new_content, "exact", _line_of_index(content, idx)
    if exact_count > 1:
        raise ThemeCustomizeError(
            f"TARGET_AMBIGUOUS: Found {exact_count} exact matches for target in '{rel}'. Target must be unique."
        )
    return _apply_fuzzy_patch(content, target, replacement, rel)


def patch_file(
    site_id: str,
    rel: str,
    target: str,
    replacement: str,
    *,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Context-anchored section replace on an allowlisted theme file."""
    normalized = assert_writable(rel)
    if not target:
        raise ThemeCustomizeError(
            "TARGET_NOT_FOUND: Empty target parameter is not allowed."
        )
    path = confine_theme_path(site_id, normalized)
    if not path.is_file():
        raise ThemeCustomizeError(f"File not found: {normalized}")

    existing_content = path.read_text(encoding="utf-8")
    previous_size = len(existing_content.encode("utf-8"))

    new_content, match_mode, matched_at_line = _resolve_patch(
        existing_content, target, replacement, normalized
    )
    new_bytes = len(new_content.encode("utf-8"))
    new_lines = len(new_content.splitlines())
    unified = _unified_diff(existing_content, new_content, normalized)

    if dry_run:
        return {
            "path": normalized,
            "ok": True,
            "dry_run": True,
            "matched_at_line": matched_at_line,
            "match_mode": match_mode,
            "replacements": 1,
            "unified_diff": unified,
            "bytes_after": new_bytes,
            "lines_after": new_lines,
            "previous_size": previous_size,
            "created": False,
            "overwritten": True,
            "guarded": False,
            "hint": "Dry-run preview only — nothing written",
        }

    _snapshot_revision(site_id, normalized)
    path.write_text(new_content, encoding="utf-8")

    return _with_file_version(
        {
            "path": normalized,
            "bytes": new_bytes,
            "previous_size": previous_size,
            "lines": new_lines,
            "replacements": 1,
            "ok": True,
            "dry_run": False,
            "matched_at_line": matched_at_line,
            "match_mode": match_mode,
            "unified_diff": unified,
            "created": False,
            "overwritten": True,
            "guarded": False,
            "hint": "Modified existing file (section patch)",
        },
        path,
    )


def _apply_fuzzy_patch(
    content: str, target: str, replacement: str, rel: str
) -> Tuple[str, str, int]:
    """Fuzzy patch after exact miss. Returns ``(new_content, match_mode, matched_at_line)``.

    Fallback order:
    1. ``crlf`` — normalize ``\\r\\n`` → ``\\n`` on both sides, then exact substring match
    2. ``line_trim`` — match a unique contiguous block of **whole lines** after
       ``.strip()`` on each line (leading/trailing whitespace only)

    Does **not** collapse internal or mid-line whitespace runs.
    """
    norm_content = content.replace("\r\n", "\n")
    norm_target = target.replace("\r\n", "\n")
    norm_replacement = replacement.replace("\r\n", "\n")

    cnt = norm_content.count(norm_target)
    if cnt == 1:
        idx = norm_content.find(norm_target)
        new_content = (
            norm_content[:idx]
            + norm_replacement
            + norm_content[idx + len(norm_target) :]
        )
        return new_content, "crlf", _line_of_index(norm_content, idx)
    if cnt > 1:
        raise ThemeCustomizeError(
            f"TARGET_AMBIGUOUS: Found {cnt} matches for target in '{rel}'. Target must be unique."
        )

    # Line-by-line trimmed matching
    c_lines = norm_content.split("\n")
    t_lines = norm_target.split("\n")
    t_stripped = [l.strip() for l in t_lines]

    matches: List[int] = []
    len_t = len(t_lines)
    for i in range(len(c_lines) - len_t + 1):
        candidate_stripped = [c_lines[i + j].strip() for j in range(len_t)]
        if candidate_stripped == t_stripped:
            matches.append(i)

    if len(matches) == 1:
        idx = matches[0]
        r_lines = norm_replacement.split("\n")
        new_lines = c_lines[:idx] + r_lines + c_lines[idx + len_t :]
        return "\n".join(new_lines), "line_trim", idx + 1
    if len(matches) > 1:
        raise ThemeCustomizeError(
            f"TARGET_AMBIGUOUS: Found {len(matches)} fuzzy matches for target in '{rel}'. Target must be unique."
        )
    raise ThemeCustomizeError(
        f"TARGET_NOT_FOUND: Target text not found in '{rel}'. "
        f"Fuzzy fallback only covers CRLF→LF and whole-line trim (leading/trailing "
        f"whitespace on full lines) — not internal or mid-line space differences. "
        f"Re-read the file and copy the exact target bytes."
    )


def custom_theme_list_entry(site_id: str) -> Optional[Dict[str, str]]:
    """Build the ``custom`` list entry for a site, or None if no valid tree."""
    if not has_site_custom_theme(site_id):
        return None
    meta = _read_theme_json(site_theme_root(site_id) / "theme.json")
    label = meta.get("name")
    if not isinstance(label, str) or not label.strip():
        label = "Custom"
    parent = meta.get("parent")
    entry: Dict[str, str] = {
        "id": RESERVED_THEME_ID,
        "label": label.strip(),
        "source": "site",
    }
    if isinstance(parent, str) and parent.strip():
        entry["parent"] = parent.strip()
    return entry


def get_theme_context(site_id: str) -> Dict[str, Any]:
    """Manifest summary for admin/MCP: exists, active, parent, allowlist, preview."""
    site = get_site(site_id)
    if site is None:
        raise ThemeCustomizeError(f"Unknown site_id: {site_id}")

    registry = (site.theme or "").strip() or None
    exists = has_site_custom_theme(site_id)
    active = social_preview.effective_theme_name(site) == RESERVED_THEME_ID
    ctx: Dict[str, Any] = {
        "site_id": site_id,
        "exists": exists,
        "active": active,
        "registry_theme": registry,
        "path": site_theme_prefix(site_id),
        "allowlist": {
            "prefixes": list(EDITABLE_PREFIXES),
            "extensions": list(EDITABLE_EXTENSIONS),
        },
        "preview": {
            "path": f"/blog/?site={quote(site_id, safe='')}",
            "header_control": "Preview Site",
            "live_serves_custom": active,
        },
    }
    if exists:
        meta = _read_theme_json(site_theme_root(site_id) / "theme.json")
        for key in ("parent", "name", "origin", "customized_at"):
            val = meta.get(key)
            if isinstance(val, str) and val.strip():
                ctx[key] = val.strip()
    return ctx


# ── Structural validate (soft; never blocks writes) ─────────────────────────

_REQUIRED_SOCIAL_KEYS = (
    "og_accent_color",
    "og_vignette_color",
    "og_text_color",
    "og_bar_color",
    "og_font",
    "og_fonts",
    "og_headline_style",
    "og_text_case",
    "og_grade_preset",
    "og_accent_bar",
    "og_watermark",
    "og_default_hero",
    "og_default_image",
    "og_fallback_title",
    "og_title_fallback",
    "og_description_fallback",
    "twitter_card",
)
_HEADLINE_STYLES = social_preview.HEADLINE_STYLES
_GRADE_PRESETS = social_preview.GRADE_PRESETS
_WATERMARK_SOURCES = social_preview.WATERMARK_SOURCES
_WATERMARK_LAYOUTS = social_preview.WATERMARK_LAYOUTS
_WATERMARK_CORNERS = social_preview.WATERMARK_CORNERS
_WATERMARK_SCALES = social_preview.WATERMARK_SCALES
_TEXT_CASES = frozenset({"upper", "title", "as_is"})
_HEADER_PARTIALS = (
    "partials/_header.php",
    "partials/_header.html.twig",
    "partials/_header.twig",
    "partials/header.php",
    "partials/header.html.twig",
    "partials/header.twig",
)
_FOOTER_PARTIALS = (
    "partials/_footer.php",
    "partials/_footer.html.twig",
    "partials/_footer.twig",
    "partials/footer.php",
    "partials/footer.html.twig",
    "partials/footer.twig",
)
_OVERRIDE_SUFFIXES = (".html.twig", ".twig")


def _issue(code: str, message: str, path: Optional[str] = None) -> Dict[str, str]:
    item: Dict[str, str] = {"code": code, "message": message}
    if path:
        item["path"] = path
    return item


def _find_template(root: Path, basename: str) -> Optional[Path]:
    for ext in (".html.twig", ".twig", ".php"):
        candidate = root / "templates" / f"{basename}{ext}"
        if candidate.is_file():
            return candidate
    return None


def _rel_under(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def _glob_overrides(root: Path, prefix: str) -> List[Tuple[str, Path]]:
    """Return (category, path) for templates/{prefix}-*.{html.twig,twig}."""
    templates = root / "templates"
    if not templates.is_dir():
        return []
    found: Dict[str, Path] = {}
    for suffix in _OVERRIDE_SUFFIXES:
        for path in sorted(templates.glob(f"{prefix}-*{suffix}")):
            if not path.is_file():
                continue
            name = path.name
            if not name.startswith(f"{prefix}-") or not name.endswith(suffix):
                continue
            cat = name[len(prefix) + 1 : -len(suffix)]
            if not cat or cat in found:
                continue
            found[cat] = path
    return sorted(found.items(), key=lambda x: x[0])


def _has_override(root: Path, prefix: str, cat: str) -> bool:
    for suffix in _OVERRIDE_SUFFIXES:
        if (root / "templates" / f"{prefix}-{cat}{suffix}").is_file():
            return True
    return False


def _check_traven_preview(
    root: Path, path: Path, errors: List[Dict[str, str]]
) -> None:
    rel = _rel_under(root, path)
    try:
        contents = path.read_text(encoding="utf-8")
    except OSError:
        errors.append(
            _issue(
                "missing_traven_preview",
                f"Missing 'traven-preview' in {rel} "
                '(body wrappers need class="article-content traven-preview")',
                rel,
            )
        )
        return
    if "traven-preview" not in contents:
        errors.append(
            _issue(
                "missing_traven_preview",
                f"Missing 'traven-preview' in {rel} "
                '(body wrappers need class="article-content traven-preview")',
                rel,
            )
        )


def validate(site_id: str) -> Dict[str, Any]:
    """Structural validate of the site custom theme tree (advisory only).

    Ports key rules from ``frontend-php/cli-tools/theme-validate.php`` against
    ``content/sites/{id}/theme/``. Never writes; never touches install themes.
    """
    site = get_site(site_id)
    if site is None:
        raise ThemeCustomizeError(f"Unknown site_id: {site_id}")
    if not has_site_custom_theme(site_id):
        raise ThemeCustomizeError(
            f"No site theme tree to validate for '{site_id}'"
        )

    root = site_theme_root(site_id).resolve()
    errors: List[Dict[str, str]] = []
    warnings: List[Dict[str, str]] = []

    # ── Manifest ──
    theme_json_path = root / "theme.json"
    data: Optional[Dict[str, Any]] = None
    if not theme_json_path.is_file():
        errors.append(
            _issue("missing_theme_json", "Missing mandatory file: theme.json", "theme.json")
        )
    else:
        try:
            raw = json.loads(theme_json_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                errors.append(
                    _issue(
                        "invalid_theme_json",
                        "theme.json must be a JSON object",
                        "theme.json",
                    )
                )
            else:
                data = raw
                if "name" not in data:
                    warnings.append(
                        _issue(
                            "missing_name",
                            "'name' missing in theme.json",
                            "theme.json",
                        )
                    )
        except (OSError, json.JSONDecodeError) as e:
            errors.append(
                _issue(
                    "invalid_theme_json",
                    f"Invalid JSON in theme.json: {e}",
                    "theme.json",
                )
            )

    # ── Mandatory templates ──
    for basename, code in (
        ("post", "missing_template_post"),
        ("index", "missing_template_index"),
        ("page", "missing_template_page"),
        ("search", "missing_template_search"),
    ):
        if _find_template(root, basename) is None:
            msg = (
                f"Missing mandatory template: templates/{basename}.php or "
                f"templates/{basename}.html.twig"
            )
            if basename == "search":
                msg += " (static publish renders search/index.html)"
            errors.append(_issue(code, msg, f"templates/{basename}.html.twig"))

    # ── Category overrides (pairing warnings) ──
    post_overrides = _glob_overrides(root, "post")
    archive_overrides = _glob_overrides(root, "archive")
    page_overrides = _glob_overrides(root, "page")

    for cat, path in post_overrides:
        if not _has_override(root, "archive", cat):
            rel = _rel_under(root, path)
            warnings.append(
                _issue(
                    "unpaired_post_override",
                    f"{rel} exists but templates/archive-{cat}.html.twig does not. "
                    f"The '{cat}' category will have themed posts but a generic "
                    "listing page. This may be intentional.",
                    rel,
                )
            )
    for cat, path in archive_overrides:
        if not _has_override(root, "post", cat):
            rel = _rel_under(root, path)
            warnings.append(
                _issue(
                    "unpaired_archive_override",
                    f"{rel} exists but templates/post-{cat}.html.twig does not.",
                    rel,
                )
            )

    if _find_template(root, "archive") is None:
        warnings.append(
            _issue(
                "missing_archive",
                "'archive' template missing (optional, falls back to index)",
            )
        )

    # ── Header / footer partials ──
    if not any((root / p).is_file() for p in _HEADER_PARTIALS):
        errors.append(
            _issue(
                "missing_header",
                "Missing mandatory partial: _header.php or _header.html.twig",
                "partials/_header.html.twig",
            )
        )
    if not any((root / p).is_file() for p in _FOOTER_PARTIALS):
        errors.append(
            _issue(
                "missing_footer",
                "Missing mandatory partial: _footer.php or _footer.html.twig",
                "partials/_footer.html.twig",
            )
        )

    if data is not None and "variables" not in data:
        warnings.append(
            _issue(
                "missing_variables",
                "'variables' block missing in theme.json",
                "theme.json",
            )
        )

    # ── Content skin ──
    css_dir = root / "assets" / "css"
    skin_files = (
        sorted(css_dir.glob("skin-*.css")) if css_dir.is_dir() else []
    )
    skin_files = [p for p in skin_files if p.is_file()]
    if not skin_files:
        errors.append(
            _issue(
                "missing_skin",
                "Missing content skin: assets/css/skin-*.css "
                "(at least one required; overlay themes may ship base + overlay)",
                "assets/css/",
            )
        )

    # ── traven-preview markup contract ──
    post_path = _find_template(root, "post")
    if post_path is not None:
        _check_traven_preview(root, post_path, errors)
    page_path = _find_template(root, "page")
    if page_path is not None:
        _check_traven_preview(root, page_path, errors)
    for _, path in post_overrides:
        _check_traven_preview(root, path, errors)
    for _, path in page_overrides:
        _check_traven_preview(root, path, errors)

    # ── editor_skin ──
    if data is not None:
        editor_skin = data.get("editor_skin")
        if editor_skin is None or editor_skin == "":
            warnings.append(
                _issue(
                    "missing_editor_skin",
                    "'editor_skin' missing in theme.json "
                    "(required for dual-duty / active-theme editor parity)",
                    "theme.json",
                )
            )

    # ── social_preview ──
    social: Optional[Dict[str, Any]] = None
    if data is not None:
        raw_social = data.get("social_preview")
        if not isinstance(raw_social, dict):
            errors.append(
                _issue(
                    "missing_social_preview",
                    "Missing or invalid 'social_preview' object in theme.json",
                    "theme.json",
                )
            )
        else:
            social = raw_social
            missing_keys = [k for k in _REQUIRED_SOCIAL_KEYS if k not in social]
            if missing_keys:
                errors.append(
                    _issue(
                        "incomplete_social_preview",
                        "Incomplete social_preview; missing keys: "
                        + ", ".join(missing_keys),
                        "theme.json",
                    )
                )
            else:
                og_fonts = social.get("og_fonts")
                if not isinstance(og_fonts, dict):
                    errors.append(
                        _issue(
                            "invalid_og_fonts",
                            "social_preview.og_fonts must be an object/map",
                            "theme.json",
                        )
                    )
                if social.get("og_headline_style") not in _HEADLINE_STYLES:
                    errors.append(
                        _issue(
                            "invalid_og_headline_style",
                            "social_preview.og_headline_style must be one of: "
                            + "|".join(sorted(_HEADLINE_STYLES)),
                            "theme.json",
                        )
                    )
                if social.get("og_text_case") not in _TEXT_CASES:
                    errors.append(
                        _issue(
                            "invalid_og_text_case",
                            "social_preview.og_text_case must be one of: "
                            + "|".join(sorted(_TEXT_CASES)),
                            "theme.json",
                        )
                    )
                if social.get("og_grade_preset") not in _GRADE_PRESETS:
                    errors.append(
                        _issue(
                            "invalid_og_grade_preset",
                            "social_preview.og_grade_preset must be one of: "
                            + "|".join(sorted(_GRADE_PRESETS)),
                            "theme.json",
                        )
                    )
                if not isinstance(social.get("og_accent_bar"), bool):
                    errors.append(
                        _issue(
                            "invalid_og_accent_bar",
                            "social_preview.og_accent_bar must be a boolean",
                            "theme.json",
                        )
                    )
                if "og_watermark_enabled" in social and not isinstance(
                    social.get("og_watermark_enabled"), bool
                ):
                    errors.append(
                        _issue(
                            "invalid_og_watermark_enabled",
                            "social_preview.og_watermark_enabled must be a boolean",
                            "theme.json",
                        )
                    )
                for key, allowed, label in (
                    ("og_watermark_source", _WATERMARK_SOURCES, "theme|logo|custom"),
                    ("og_watermark_layout", _WATERMARK_LAYOUTS, "full_canvas|corner"),
                    ("og_watermark_corner", _WATERMARK_CORNERS, "tl|tr|bl|br"),
                    ("og_watermark_scale", _WATERMARK_SCALES, "sm|md|lg"),
                ):
                    if key not in social:
                        continue
                    val = social.get(key)
                    if val is None or (isinstance(val, str) and not str(val).strip()):
                        continue
                    if val not in allowed:
                        errors.append(
                            _issue(
                                f"invalid_{key}",
                                f"social_preview.{key} must be one of: {label}",
                                "theme.json",
                            )
                        )

    # ── OG fonts warnings ──
    if social is not None and isinstance(social.get("og_fonts"), dict):
        og_fonts = social["og_fonts"]
        if len(og_fonts) == 0:
            warnings.append(
                _issue(
                    "empty_og_fonts",
                    "social_preview.og_fonts is empty — engine falls back to "
                    "frontend-php/fonts/CourierPrime-Bold.ttf",
                    "theme.json",
                )
            )
        else:
            for font_id, font_path in og_fonts.items():
                if not isinstance(font_path, str) or not font_path:
                    warnings.append(
                        _issue(
                            "bad_og_font_path",
                            f"og_fonts['{font_id}'] path is empty or not a string",
                            "theme.json",
                        )
                    )
                    continue
                ext = Path(font_path).suffix.lower().lstrip(".")
                if ext not in ("ttf", "otf"):
                    warnings.append(
                        _issue(
                            "bad_og_font_ext",
                            f"og_fonts['{font_id}'] is not TTF/OTF ({font_path}) "
                            "— Pillow needs local TTF/OTF",
                            font_path.lstrip("/"),
                        )
                    )
                abs_font = root / font_path.lstrip("/")
                if not abs_font.is_file():
                    warnings.append(
                        _issue(
                            "missing_og_font_file",
                            f"og_fonts['{font_id}'] file missing: {font_path}",
                            font_path.lstrip("/"),
                        )
                    )

    # ── Hero / defaulthero ──
    supports = data.get("supports") if isinstance(data, dict) else None
    supports_hero = (
        isinstance(supports, dict) and bool(supports.get("hero_image"))
    )
    if supports_hero:
        hero_file = root / "assets" / "images" / "defaulthero.jpg"
        og_default_hero = social.get("og_default_hero") if social else None
        missing_hero_file = not hero_file.is_file()
        missing_hero_key = og_default_hero is None or og_default_hero == ""
        if missing_hero_file or missing_hero_key:
            bits: List[str] = []
            if missing_hero_file:
                bits.append("assets/images/defaulthero.jpg missing")
            if missing_hero_key:
                bits.append("social_preview.og_default_hero is null/empty")
            warnings.append(
                _issue(
                    "hero_support_incomplete",
                    "supports.hero_image is true but " + "; ".join(bits),
                )
            )
        elif isinstance(og_default_hero, str):
            hero_abs = root / og_default_hero.lstrip("/")
            if not hero_abs.is_file():
                warnings.append(
                    _issue(
                        "missing_og_default_hero",
                        f"social_preview.og_default_hero path missing: "
                        f"{og_default_hero}",
                        og_default_hero.lstrip("/"),
                    )
                )

    for e in errors:
        e["severity"] = "error"
    for w in warnings:
        w["severity"] = "warning"

    return {
        "site_id": site_id,
        "ok": len(errors) == 0,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }
