"""Live /blog/ preview paths for Glowbot. Empty unless the page is actually live."""

from __future__ import annotations

import re
from typing import Any, Mapping, Optional
from urllib.parse import quote, urlencode

from routers.pages import is_page_doc
from services.file_service import read_page, sanitize_slug
from services.i18n_service import is_live_translation

_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_SECTION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_./-]{0,127}$")


def live_content_path(
    site_id: str,
    slug: str,
    section: str,
    comment_slug: Optional[str] = None,
) -> Optional[str]:
    """Instant PHP preview: post.php?slug=&section=&site= (posts only)."""
    site = (site_id or "").strip()
    leaf = (slug or "").strip()
    sect = (section or "").strip().lower()
    if not _SLUG_RE.fullmatch(site) or not _SLUG_RE.fullmatch(leaf):
        return None
    if not _SECTION_RE.fullmatch(sect):
        return None
    query = urlencode({"slug": leaf, "section": sect, "site": site})
    path = f"/blog/post.php?{query}"
    frag = (comment_slug or "").strip()
    if frag:
        if not _SLUG_RE.fullmatch(frag):
            return None
        path = f"{path}#{quote(frag, safe='')}"
    return path


def public_path_if_live(
    site_id: str,
    slug: str,
    metadata: Mapping[str, Any],
    *,
    comment_slug: Optional[str] = None,
    comment_visible: bool = True,
) -> Optional[str]:
    """Return a live post.php path only when the post is published (and the comment is visible)."""
    if comment_slug and not comment_visible:
        return None
    if is_page_doc(metadata):
        return None
    if not is_live_translation(metadata):
        return None
    section = str(metadata.get("category") or metadata.get("type") or "").strip()
    return live_content_path(site_id, slug, section, comment_slug)


async def public_content_path(
    site_id: str,
    slug: str,
    *,
    comment_slug: Optional[str] = None,
    comment_visible: bool = True,
) -> Optional[str]:
    """Read the post and return a live /blog/post.php path, or None."""
    if comment_slug and not comment_visible:
        return None
    page_id = sanitize_slug(slug)
    if not page_id:
        return None
    page = await read_page(page_id, site_id=site_id)
    if page is None:
        return None
    meta = page.frontmatter if isinstance(page.frontmatter, Mapping) else {}
    return public_path_if_live(
        site_id,
        page_id,
        meta,
        comment_slug=comment_slug,
        comment_visible=comment_visible,
    )
