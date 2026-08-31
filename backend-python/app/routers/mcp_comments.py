"""MCP tools for comment files beside a post (not fb-* stubs)."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from models.user import UserPublic
from routers.auth import get_current_user
from routers.mcp_tools import require_scope, resolve_mcp_site_id
from services.comment_service import (
    AUTHOR_KIND_AGENT,
    VISIBILITY_VISIBLE,
    CommentIngestError,
    CommentNotFoundError,
    CommentVisibilityError,
    delete_comment,
    list_comments_mcp,
    set_comment_visibility,
    write_comment,
)
from services.house_url_service import public_content_path

router = APIRouter(prefix="/api/v1", tags=["mcp"])

SOURCE_TYPE_MCP = "mcp"


class CreateCommentBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    post_slug: str
    body: str = Field(..., min_length=1, max_length=8000)
    in_reply_to: Optional[str] = None

    @field_validator("post_slug", "body", "in_reply_to", mode="before")
    @classmethod
    def strip_strings(cls, v: Any) -> Any:
        if isinstance(v, str):
            stripped = v.strip()
            return stripped or None
        return v


class SetCommentVisibilityBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visibility: str
    post_slug: str


def _raise_comment_error(exc: Exception) -> None:
    if isinstance(exc, CommentIngestError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, CommentVisibilityError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, CommentNotFoundError):
        raise HTTPException(status_code=404, detail="Comment not found") from exc
    raise exc


def _agent_key_name(request: Request) -> str:
    return str(getattr(request.state, "actor_id", "") or "")


@router.get(
    "/mcp/comments",
    operation_id="list_comments",
    dependencies=[Depends(require_scope("read"))],
)
async def mcp_list_comments(
    request: Request,
    post_slug: Optional[str] = Query(None),
    visibility: Optional[str] = Query(None),
    current_user: UserPublic = Depends(get_current_user),
) -> dict[str, Any]:
    """List comment files beside a post for the bound MCP site.

    Omit ``visibility`` for all states (admin payload, including pending).
    Oldest-first. Unknown post → empty list. JWT ``site_id`` is authoritative.
    """
    del current_user
    site_id = resolve_mcp_site_id(request)
    cleaned = (post_slug or "").strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="post_slug is required")
    try:
        comments = await list_comments_mcp(
            site_id, cleaned, visibility=visibility
        )
    except CommentVisibilityError as exc:
        _raise_comment_error(exc)
    return {"post_slug": cleaned, "comments": comments}


@router.post(
    "/mcp/comments",
    operation_id="create_comment",
    dependencies=[Depends(require_scope("write:posts"))],
)
async def mcp_create_comment(
    payload: CreateCommentBody,
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> dict[str, Any]:
    """Write a visible agent comment beside a post. Not create_post.

    ``author_kind=agent``, ``source_type=mcp``, display name is the key name.
    Unknown post_slug → 400.
    """
    del current_user
    site_id = resolve_mcp_site_id(request)
    cleaned_post = (payload.post_slug or "").strip()
    if not cleaned_post:
        raise HTTPException(status_code=400, detail="post_slug is required")
    key_name = _agent_key_name(request)
    try:
        slug = await write_comment(
            site_id,
            submitter=key_name,
            message=payload.body,
            parent_slug=cleaned_post,
            source_type=SOURCE_TYPE_MCP,
            in_reply_to=payload.in_reply_to,
            visibility=VISIBILITY_VISIBLE,
            author_kind=AUTHOR_KIND_AGENT,
            agent_key_name=key_name,
        )
    except CommentIngestError as exc:
        _raise_comment_error(exc)
    comments = await list_comments_mcp(site_id, cleaned_post)
    comment = next((row for row in comments if row.get("slug") == slug), None)
    if comment is None:
        raise HTTPException(status_code=500, detail="Comment write did not persist")
    visible = str(comment.get("visibility") or "") == VISIBILITY_VISIBLE
    public_path = await public_content_path(
        site_id,
        cleaned_post,
        comment_slug=slug,
        comment_visible=visible,
    )
    return {"comment": comment, "public_path": public_path}


@router.patch(
    "/mcp/comments/{comment_slug}",
    operation_id="set_comment_visibility",
    dependencies=[Depends(require_scope("write:posts"))],
)
async def mcp_set_comment_visibility(
    comment_slug: str,
    payload: SetCommentVisibilityBody,
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> dict[str, Any]:
    """Set visibility on a comment file. Moderation, not post status."""
    del current_user
    site_id = resolve_mcp_site_id(request)
    cleaned_post = (payload.post_slug or "").strip()
    if not cleaned_post:
        raise HTTPException(status_code=400, detail="post_slug is required")
    try:
        comment = await set_comment_visibility(
            site_id, cleaned_post, comment_slug, payload.visibility
        )
    except (CommentNotFoundError, CommentVisibilityError) as exc:
        _raise_comment_error(exc)
    return {"comment": comment}


@router.delete(
    "/mcp/comments/{comment_slug}",
    operation_id="delete_comment",
    dependencies=[Depends(require_scope("delete:posts"))],
    status_code=204,
)
async def mcp_delete_comment(
    comment_slug: str,
    request: Request,
    post_slug: Optional[str] = Query(None),
    current_user: UserPublic = Depends(get_current_user),
) -> None:
    """Delete a comment file via storage. Git history remains."""
    del current_user
    site_id = resolve_mcp_site_id(request)
    cleaned_post = (post_slug or "").strip()
    if not cleaned_post:
        raise HTTPException(status_code=400, detail="post_slug is required")
    try:
        await delete_comment(site_id, cleaned_post, comment_slug)
    except CommentNotFoundError as exc:
        _raise_comment_error(exc)
