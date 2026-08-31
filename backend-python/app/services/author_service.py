"""Per-site author bios stored as ``sites/{id}/authors.yaml``."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import List, Optional

import yaml
from models.author import Author, AuthorCreate, AuthorUpdate
from services.site_service import (
    DEFAULT_SITE_ID,
    join_site_assets_path,
    site_authors_relpath,
)

logger = logging.getLogger("pencms.authors")

_file_lock = asyncio.Lock()

_AVATAR_EXTS = ("png", "svg", "webp", "jpg", "jpeg", "gif")


def _empty_authors() -> List[Author]:
    return []


def sanitize_author_slug(slug: str) -> str:
    """Normalize a slug to kebab-case (filesystem-safe within a site)."""
    slug = (slug or "").lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


def slug_from_name(name: str) -> str:
    return sanitize_author_slug(name)


def _parse_authors_data(data: object) -> List[Author]:
    if not isinstance(data, dict):
        return _empty_authors()
    raw_list = data.get("authors", [])
    if not isinstance(raw_list, list):
        return _empty_authors()
    authors: List[Author] = []
    for item in raw_list:
        try:
            authors.append(Author.model_validate(item))
        except Exception:
            continue
    authors.sort(key=lambda a: (a.sort_order, a.name.lower()))
    return authors


async def read_authors(site_id: str = DEFAULT_SITE_ID) -> List[Author]:
    """Read all authors for a site from ``authors.yaml``."""
    from config import content_storage

    rel = site_authors_relpath(site_id)
    async with _file_lock:
        try:
            if not await content_storage.exists(rel):
                return _empty_authors()
            raw = await content_storage.read(rel)
            data = yaml.safe_load(raw) or {}
        except Exception:
            return _empty_authors()
        return _parse_authors_data(data)


async def write_authors(
    authors: List[Author], site_id: str = DEFAULT_SITE_ID
) -> None:
    """Write all authors for a site to ``authors.yaml``."""
    from config import content_storage

    rel = site_authors_relpath(site_id)
    async with _file_lock:
        sorted_authors = sorted(
            authors, key=lambda a: (a.sort_order, a.name.lower())
        )
        data_to_write = {
            "authors": [a.model_dump(mode="json") for a in sorted_authors]
        }
        text = yaml.safe_dump(
            data_to_write,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )
        parent = "/".join(rel.split("/")[:-1])
        if parent:
            await content_storage.mkdir(parent)
        await content_storage.write(rel, text)


async def list_authors(site_id: str = DEFAULT_SITE_ID) -> List[Author]:
    return await read_authors(site_id)


async def get_author(slug: str, site_id: str = DEFAULT_SITE_ID) -> Author:
    authors = await read_authors(site_id)
    key = sanitize_author_slug(slug)
    for author in authors:
        if author.slug == key:
            return author
    raise KeyError(f"Author '{key}' not found")


async def create_author(
    item: AuthorCreate, site_id: str = DEFAULT_SITE_ID
) -> Author:
    authors = await read_authors(site_id)

    name = (item.name or "").strip()
    if not name:
        raise ValueError("Author name is required")

    raw_slug = item.slug if item.slug is not None else name
    slug = sanitize_author_slug(raw_slug)
    if not slug:
        raise ValueError("Author slug is empty after sanitization")

    if any(a.slug == slug for a in authors):
        raise ValueError(f"Author slug '{slug}' already exists on this site")

    sort_order = item.sort_order
    if sort_order is None:
        sort_order = max((a.sort_order for a in authors), default=-1) + 1

    avatar = (item.avatar or "").strip() or None

    new_author = Author(
        slug=slug,
        name=name,
        bio=item.bio or "",
        website=item.website or "",
        avatar=avatar,
        email=item.email or "",
        role=item.role or "",
        sort_order=sort_order,
    )
    authors.append(new_author)
    await write_authors(authors, site_id)
    return new_author


async def update_author(
    slug: str, item: AuthorUpdate, site_id: str = DEFAULT_SITE_ID
) -> Author:
    authors = await read_authors(site_id)
    key = sanitize_author_slug(slug)
    idx = next((i for i, a in enumerate(authors) if a.slug == key), None)
    if idx is None:
        raise KeyError(f"Author '{key}' not found")

    current = authors[idx]
    data = current.model_dump()
    updates = item.model_dump(exclude_unset=True)
    if "name" in updates and updates["name"] is not None:
        name = str(updates["name"]).strip()
        if not name:
            raise ValueError("Author name cannot be empty")
        updates["name"] = name
    if "avatar" in updates:
        av = updates["avatar"]
        updates["avatar"] = (str(av).strip() if av else None) or None
    data.update(updates)
    updated = Author.model_validate(data)
    authors[idx] = updated
    await write_authors(authors, site_id)
    return updated


async def set_author_avatar(
    slug: str, logical_path: str, site_id: str = DEFAULT_SITE_ID
) -> Author:
    """Set the avatar relative path on an existing author."""
    return await update_author(
        slug, AuthorUpdate(avatar=logical_path), site_id=site_id
    )


async def _delete_avatar_files(
    site_id: str, slug: str, avatar: Optional[str] = None
) -> None:
    """Best-effort remove avatar binaries under site assets."""
    from config import content_storage

    paths: set[str] = set()
    if avatar:
        # avatar is logical under assets (e.g. images/authors/jane.webp)
        paths.add(join_site_assets_path(site_id, avatar))

    authors_dir = join_site_assets_path(site_id, "images", "authors")
    for ext in _AVATAR_EXTS:
        paths.add(f"{authors_dir}/{slug}.{ext}")

    for path in paths:
        try:
            if await content_storage.exists(path):
                await content_storage.delete(path)
        except Exception as e:
            logger.warning("Failed to remove author avatar %s: %s", path, e)


async def delete_author(slug: str, site_id: str = DEFAULT_SITE_ID) -> None:
    authors = await read_authors(site_id)
    key = sanitize_author_slug(slug)
    target = next((a for a in authors if a.slug == key), None)
    if target is None:
        raise KeyError(f"Author '{key}' not found")

    remaining = [a for a in authors if a.slug != key]
    await write_authors(remaining, site_id)
    await _delete_avatar_files(site_id, key, target.avatar)
