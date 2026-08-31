"""Public and agent comments as Markdown files beside a post.

Not pages: writes ``content/sites/{site}/{post_slug}/comments/c-*.md`` via
storage, never ``write_page``. Contact ingest stays in feedback_service (fb-*).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

import frontmatter

import config as app_config
from services.file_service import join_site_path, name_to_id, resolve_path, sanitize_slug
from services.site_service import get_site_content_prefix

logger = logging.getLogger("pencms.comments")

COMMENTS_DIR = "comments"
KIND_COMMENT = "comment"
VISIBILITY_PENDING = "pending"
VISIBILITY_VISIBLE = "visible"
VISIBILITY_HIDDEN = "hidden"
AUTHOR_KIND_PUBLIC = "public"
AUTHOR_KIND_AGENT = "agent"
AUTHOR_KIND_HUMAN = "human"
HEADLINE_WORD_COUNT = 6
UNKNOWN_POST_SLUG = "Unknown post_slug"
SOURCE_TYPE_ADMIN = "admin"


class CommentIngestError(ValueError):
    """Comment cannot be written (unknown parent, invalid reply, …)."""


class CommentsDisabledError(CommentIngestError):
    """Public/relay comment ingest refused because the site knob is off."""


class CommentNotFoundError(LookupError):
    """Comment file does not exist beside this post."""


class CommentVisibilityError(ValueError):
    """visibility is not pending, visible, or hidden."""


ALLOWED_VISIBILITIES = frozenset(
    {VISIBILITY_PENDING, VISIBILITY_VISIBLE, VISIBILITY_HIDDEN}
)


def _headline_from_message(message: str) -> tuple[str, str]:
    words = message.split()[:HEADLINE_WORD_COUNT]
    raw = " ".join(words).strip()
    slug_part = name_to_id(raw) if raw else ""
    if not slug_part:
        return "Comment", "comment"
    return raw, slug_part


def _received_at_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dt%H%M%Sz")


def comment_relpath(site_id: str, post_slug: str, comment_slug: str) -> str:
    return join_site_path(site_id, post_slug, COMMENTS_DIR, f"{comment_slug}.md")


def comments_dir(site_id: str, post_slug: str) -> str:
    return join_site_path(site_id, post_slug, COMMENTS_DIR)


async def _unique_comment_slug(site_id: str, post_slug: str, base: str) -> str:
    candidate = base
    n = 2
    while await app_config.content_storage.exists(
        comment_relpath(site_id, post_slug, candidate)
    ):
        candidate = f"{base}-{n}"
        n += 1
    return candidate


async def resolve_comment_parent(site_id: str, parent_slug: Optional[str]) -> str:
    """Return sanitized post slug or raise CommentIngestError."""
    cleaned = sanitize_slug(parent_slug or "")
    if not cleaned or cleaned.startswith("fb-"):
        raise CommentIngestError(UNKNOWN_POST_SLUG)
    if await resolve_path(cleaned, site_id=site_id) is None:
        raise CommentIngestError(UNKNOWN_POST_SLUG)
    return cleaned


async def _assert_in_reply_to(
    site_id: str, post_slug: str, in_reply_to: Optional[str]
) -> Optional[str]:
    if not in_reply_to:
        return None
    reply_slug = sanitize_slug(in_reply_to)
    if not reply_slug:
        raise CommentIngestError("Invalid in_reply_to")
    path = comment_relpath(site_id, post_slug, reply_slug)
    if not await app_config.content_storage.exists(path):
        raise CommentIngestError("Unknown in_reply_to")
    text = await app_config.content_storage.read(path)
    meta = dict(frontmatter.loads(text).metadata)
    parent_reply = meta.get("in_reply_to")
    if parent_reply not in (None, "", False):
        raise CommentIngestError("in_reply_to may be only one level deep")
    return reply_slug


async def write_comment(
    site_id: str,
    *,
    submitter: str,
    message: str,
    parent_slug: Optional[str],
    source_type: str,
    received_at: Optional[str] = None,
    in_reply_to: Optional[str] = None,
    visibility: str = VISIBILITY_PENDING,
    author_kind: str = AUTHOR_KIND_PUBLIC,
    agent_key_name: Optional[str] = None,
) -> str:
    """Write a comment file beside the post and return its slug (``c-…``)."""
    post_slug = await resolve_comment_parent(site_id, parent_slug)
    reply_to = await _assert_in_reply_to(site_id, post_slug, in_reply_to)

    headline, slug_suffix = _headline_from_message(message)
    stamp = _utc_stamp()
    slug = await _unique_comment_slug(
        site_id, post_slug, f"c-{stamp}-{slug_suffix}"
    )

    handle = (submitter or "").strip() or "Anonymous"
    stamped = (received_at or "").strip() or _received_at_now()

    fm_dict = {
        "name": headline,
        "slug": slug,
        "kind": KIND_COMMENT,
        "post_slug": post_slug,
        "in_reply_to": reply_to,
        "visibility": visibility,
        "author_name": handle,
        "author_kind": author_kind,
        "agent_key_name": agent_key_name,
        "source_type": source_type,
        "received_at": stamped,
    }

    rel_dir = comments_dir(site_id, post_slug)
    await app_config.content_storage.mkdir(rel_dir)
    rel_path = comment_relpath(site_id, post_slug, slug)
    post = frontmatter.Post(message, **fm_dict)
    await app_config.content_storage.write(rel_path, frontmatter.dumps(post))

    logger.info(
        "Wrote comment %s on site %s post %s", slug, site_id, post_slug
    )
    return slug


def _comment_sort_key(item: dict[str, Any]) -> tuple[str, str]:
    return (_received_at_str(item.get("received_at")), str(item.get("slug") or ""))


def _thread_comments(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group replies immediately after their visible parent.

    ``items`` must already be oldest-first. Top-level comments (no
    ``in_reply_to``, or parent not in this set) keep that order. Visible
    children follow their parent, oldest-first among siblings. Orphan
    replies stay in the top-level stream at their chronological position.
    """
    by_slug = {
        str(item.get("slug") or ""): item for item in items if item.get("slug")
    }
    children: dict[str, list[dict[str, Any]]] = {}
    roots: list[dict[str, Any]] = []
    for item in items:
        parent = item.get("in_reply_to")
        slug = str(item.get("slug") or "")
        if parent and parent in by_slug and parent != slug:
            children.setdefault(str(parent), []).append(item)
        else:
            roots.append(item)
    out: list[dict[str, Any]] = []
    for root in roots:
        out.append(root)
        root_slug = str(root.get("slug") or "")
        out.extend(children.get(root_slug, []))
    return out


def _received_at_str(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        iso = value.strftime("%Y-%m-%dT%H:%M:%SZ")
        if getattr(value, "tzinfo", None) is None:
            return iso
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    text = str(value).strip()
    if text.endswith("+00:00"):
        return text[:-6] + "Z"
    return text.replace(" ", "T")


def _reply_slug(meta: dict[str, Any]) -> Optional[str]:
    reply = meta.get("in_reply_to")
    if reply in (None, "", False):
        return None
    return str(reply)


def _public_comment(meta: dict[str, Any], body: str) -> dict[str, Any]:
    return {
        "slug": str(meta.get("slug") or ""),
        "author_name": str(meta.get("author_name") or "Anonymous"),
        "author_kind": str(meta.get("author_kind") or AUTHOR_KIND_PUBLIC),
        "body": body,
        "in_reply_to": _reply_slug(meta),
        "received_at": _received_at_str(meta.get("received_at")),
    }


def _admin_comment(meta: dict[str, Any], body: str) -> dict[str, Any]:
    agent = meta.get("agent_key_name")
    if agent in (None, "", False):
        agent = None
    else:
        agent = str(agent)
    row = _public_comment(meta, body)
    row["visibility"] = str(meta.get("visibility") or "")
    row["source_type"] = str(meta.get("source_type") or "")
    row["agent_key_name"] = agent
    row["post_slug"] = str(meta.get("post_slug") or "")
    return row


async def _iter_comment_records(
    site_id: str, post_slug: str
) -> list[tuple[dict[str, Any], str]]:
    """Read kind=comment files beside a post. Unknown post → [].

    Does not use ``write_page`` / page cache.
    """
    cleaned = sanitize_slug(post_slug or "")
    if not cleaned or cleaned.startswith("fb-"):
        return []
    if await resolve_path(cleaned, site_id=site_id) is None:
        return []

    rel_dir = comments_dir(site_id, cleaned)
    try:
        names = await app_config.content_storage.list_dir(rel_dir)
    except Exception:
        return []

    records: list[tuple[dict[str, Any], str]] = []
    for name in names:
        filename = str(name).replace("\\", "/").split("/")[-1]
        if not filename.endswith(".md") or filename.startswith("_"):
            continue
        rel_path = comment_relpath(site_id, cleaned, filename[:-3])
        try:
            text = await app_config.content_storage.read(rel_path)
            parsed = frontmatter.loads(text)
        except Exception:
            logger.warning("Skipping unreadable comment %s", rel_path)
            continue
        meta = dict(parsed.metadata)
        if str(meta.get("kind") or "") != KIND_COMMENT:
            continue
        if not meta.get("slug"):
            meta["slug"] = filename[:-3]
        records.append((meta, (parsed.content or "").strip()))
    return records


async def _iter_site_comment_records(
    site_id: str,
) -> list[tuple[dict[str, Any], str]]:
    """Read kind=comment files beside every post on the site."""
    try:
        prefix = get_site_content_prefix(site_id)
        names = await app_config.content_storage.list_dir(prefix)
    except Exception:
        return []

    records: list[tuple[dict[str, Any], str]] = []
    for item in names:
        name = str(item).replace("\\", "/").split("/")[-1]
        if not name or name.startswith(".") or name.startswith("fb-"):
            continue
        full = join_site_path(site_id, name)
        try:
            if not await app_config.content_storage.is_dir(full):
                continue
        except Exception:
            continue
        records.extend(await _iter_comment_records(site_id, name))
    return records


def _pending_counts(
    records: list[tuple[dict[str, Any], str]],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for meta, _body in records:
        if str(meta.get("visibility") or "") != VISIBILITY_PENDING:
            continue
        post = str(meta.get("post_slug") or "")
        if not post:
            continue
        counts[post] = counts.get(post, 0) + 1
    return counts


async def list_comments(
    site_id: str,
    post_slug: str,
    *,
    visibility: str = VISIBILITY_VISIBLE,
) -> list[dict[str, Any]]:
    """Read comment files beside a post. Unknown post → empty list.

    Public callers pass ``visibility=visible`` so pending and hidden stay
    off the live thread. Payload has no ``visibility`` field.

    Top-level comments are oldest-first by ``received_at`` then slug.
    Each comment's replies follow immediately after it, oldest-first
    among siblings, even when a reply was written days later.
    """
    items: list[dict[str, Any]] = []
    for meta, body in await _iter_comment_records(site_id, post_slug):
        if str(meta.get("visibility") or "") != visibility:
            continue
        items.append(_public_comment(meta, body))
    items.sort(key=_comment_sort_key)
    return _thread_comments(items)


async def list_comments_admin(
    site_id: str,
    post_slug: Optional[str] = None,
    *,
    visibility: Optional[str] = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Human moderation list. Newest ``received_at`` first.

    Omit ``post_slug`` for every post on the site. Unknown post → empty
    comments. ``pending_counts`` is always site-wide.
    """
    cleaned_vis: Optional[str] = None
    if visibility is not None and str(visibility).strip():
        cleaned_vis = str(visibility).strip()
        if cleaned_vis not in ALLOWED_VISIBILITIES:
            raise CommentVisibilityError(
                "visibility must be pending, visible, or hidden"
            )

    site_records = await _iter_site_comment_records(site_id)
    pending_counts = _pending_counts(site_records)

    cleaned_post = sanitize_slug(post_slug or "")
    if cleaned_post:
        records = await _iter_comment_records(site_id, cleaned_post)
    else:
        records = site_records

    items = [_admin_comment(meta, body) for meta, body in records]
    if cleaned_vis is not None:
        items = [row for row in items if row.get("visibility") == cleaned_vis]
    items.sort(key=_comment_sort_key, reverse=True)
    return items, pending_counts


async def list_comments_mcp(
    site_id: str,
    post_slug: str,
    *,
    visibility: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Agent list: admin payload, oldest-first. Unknown post → empty list.

    Omit ``visibility`` for all states. A set value filters to that state.
    Newest-first ordering stays on ``list_comments_admin`` only.
    """
    cleaned_vis: Optional[str] = None
    if visibility is not None and str(visibility).strip():
        cleaned_vis = str(visibility).strip()
        if cleaned_vis not in ALLOWED_VISIBILITIES:
            raise CommentVisibilityError(
                "visibility must be pending, visible, or hidden"
            )
    items = [
        _admin_comment(meta, body)
        for meta, body in await _iter_comment_records(site_id, post_slug)
    ]
    if cleaned_vis is not None:
        items = [row for row in items if row.get("visibility") == cleaned_vis]
    items.sort(key=_comment_sort_key)
    return items


async def _load_comment_post(
    site_id: str, post_slug: str, comment_slug: str
) -> tuple[str, Any]:
    cleaned_post = sanitize_slug(post_slug or "")
    cleaned_comment = sanitize_slug(comment_slug or "")
    if (
        not cleaned_post
        or cleaned_post.startswith("fb-")
        or not cleaned_comment
    ):
        raise CommentNotFoundError("Comment not found")
    rel_path = comment_relpath(site_id, cleaned_post, cleaned_comment)
    if not await app_config.content_storage.exists(rel_path):
        raise CommentNotFoundError("Comment not found")
    try:
        text = await app_config.content_storage.read(rel_path)
        parsed = frontmatter.loads(text)
    except Exception as exc:
        raise CommentNotFoundError("Comment not found") from exc
    meta = dict(parsed.metadata)
    if str(meta.get("kind") or "") != KIND_COMMENT:
        raise CommentNotFoundError("Comment not found")
    if not meta.get("slug"):
        meta["slug"] = cleaned_comment
        parsed.metadata["slug"] = cleaned_comment
    return rel_path, parsed


async def set_comment_visibility(
    site_id: str,
    post_slug: str,
    comment_slug: str,
    visibility: str,
) -> dict[str, Any]:
    """Rewrite YAML visibility on an existing comment file. Not a Page."""
    cleaned_vis = (visibility or "").strip()
    if cleaned_vis not in ALLOWED_VISIBILITIES:
        raise CommentVisibilityError(
            "visibility must be pending, visible, or hidden"
        )
    rel_path, parsed = await _load_comment_post(site_id, post_slug, comment_slug)
    meta = dict(parsed.metadata)
    meta["visibility"] = cleaned_vis
    body = parsed.content or ""
    post = frontmatter.Post(body, **meta)
    await app_config.content_storage.write(rel_path, frontmatter.dumps(post))
    logger.info(
        "Set comment %s visibility=%s on site %s post %s",
        meta.get("slug"),
        cleaned_vis,
        site_id,
        sanitize_slug(post_slug or ""),
    )
    return _admin_comment(meta, body.strip())


async def update_comment(
    site_id: str,
    post_slug: str,
    comment_slug: str,
    *,
    visibility: Optional[str] = None,
    body: Optional[str] = None,
    author_name: Optional[str] = None,
) -> dict[str, Any]:
    """Rewrite visibility and/or body in place. Same slug and filename."""
    cleaned_vis: Optional[str] = None
    if visibility is not None:
        cleaned_vis = str(visibility).strip()
        if cleaned_vis not in ALLOWED_VISIBILITIES:
            raise CommentVisibilityError(
                "visibility must be pending, visible, or hidden"
            )
    rel_path, parsed = await _load_comment_post(site_id, post_slug, comment_slug)
    meta = dict(parsed.metadata)
    current_body = parsed.content or ""
    if cleaned_vis is not None:
        meta["visibility"] = cleaned_vis
    if body is not None:
        current_body = body
        headline, _slug_part = _headline_from_message(body)
        meta["name"] = headline
    if author_name is not None:
        handle = str(author_name).strip() or "Anonymous"
        meta["author_name"] = handle
    post = frontmatter.Post(current_body, **meta)
    await app_config.content_storage.write(rel_path, frontmatter.dumps(post))
    logger.info(
        "Updated comment %s on site %s post %s",
        meta.get("slug"),
        site_id,
        sanitize_slug(post_slug or ""),
    )
    return _admin_comment(meta, current_body.strip())


async def load_admin_comment(
    site_id: str, post_slug: str, comment_slug: str
) -> dict[str, Any]:
    _rel_path, parsed = await _load_comment_post(site_id, post_slug, comment_slug)
    meta = dict(parsed.metadata)
    return _admin_comment(meta, (parsed.content or "").strip())


async def delete_comment(
    site_id: str, post_slug: str, comment_slug: str
) -> None:
    """Delete the comment file via storage. Not ``delete_page``."""
    rel_path, parsed = await _load_comment_post(site_id, post_slug, comment_slug)
    slug = parsed.metadata.get("slug") or sanitize_slug(comment_slug or "")
    await app_config.content_storage.delete(rel_path)
    logger.info(
        "Deleted comment %s on site %s post %s",
        slug,
        site_id,
        sanitize_slug(post_slug or ""),
    )
