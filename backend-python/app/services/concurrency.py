"""Optimistic concurrency tokens for content reads and writes.

Reads return an opaque mtime token; writes may echo it as ``expected_version``.
When ``PENCMS_STRICT_CONTENT_VERSION`` is enabled (default), a mismatch raises
409 ``version_conflict`` before persist. When disabled, the write still applies
and callers receive ``version_warning``.

Omitted ``expected_version`` is an unconditional write (legacy clients).
``force=True`` is the explicit overwrite after a conflict. Create (no on-disk
file) skips the check.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from fastapi import HTTPException, status

STRICT_ENV = "PENCMS_STRICT_CONTENT_VERSION"
# Default on: Stage C. Set the env to 0/false/no/off to restore soft-warn.
_STRICT_DEFAULT = True

SOFT_VERSION_WARNING = (
    "expected_version did not match the on-disk version at write time; "
    "write was applied anyway (strict concurrency not yet enforced)."
)


def strict_content_version_enabled() -> bool:
    raw = os.environ.get(STRICT_ENV)
    if raw is None or not str(raw).strip():
        return _STRICT_DEFAULT
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


async def page_version_token(file_path: Optional[str]) -> Optional[str]:
    """Opaque version token from the content file's mtime."""
    if not file_path:
        return None
    try:
        from config import content_storage

        file_stat = await content_storage.stat(file_path)
        mtime = file_stat.get("mtime")
        if mtime is None:
            return None
        return f"{float(mtime):.6f}"
    except Exception:
        return None


def check_expected_version(
    expected_version: Optional[str],
    current_version: Optional[str],
    *,
    force: bool = False,
) -> Optional[str]:
    """Return a soft-warn string, raise 409 if strict, or None if no conflict.

    Call after reading the existing file and before persist.
    """
    if force or expected_version is None or current_version is None:
        return None
    if expected_version == current_version:
        return None
    if strict_content_version_enabled():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "version_conflict",
                "message": "The document has been modified since it was read.",
                "current_version": current_version,
                "expected_version": expected_version,
            },
        )
    return SOFT_VERSION_WARNING


async def attach_page_version(page: Any) -> Any:
    """Set ``page.version`` from ``page.file_path``. No-op when page is None."""
    if page is None:
        return None
    token = await page_version_token(getattr(page, "file_path", None))
    if hasattr(page, "version"):
        page.version = token
    return page
