"""Authenticated human admin routes for comment files (not fb-* stubs)."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from models.page import format_validation_error
from models.user import UserPublic
from routers.auth import get_current_user
from services.authz import assert_capability
from services.comment_service import (
    AUTHOR_KIND_HUMAN,
    SOURCE_TYPE_ADMIN,
    VISIBILITY_VISIBLE,
    CommentIngestError,
    CommentNotFoundError,
    CommentVisibilityError,
    delete_comment,
    list_comments_admin,
    load_admin_comment,
    set_comment_visibility,
    update_comment,
    write_comment,
)
from services.site_service import apply_human_site_taxonomy

router = APIRouter(prefix="/v1/admin", tags=["admin"])


class PatchCommentBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    post_slug: str
    visibility: Optional[str] = None
    body: Optional[str] = Field(default=None, min_length=1, max_length=8000)
    author_name: Optional[str] = None

    @field_validator("post_slug", "visibility", "body", "author_name", mode="before")
    @classmethod
    def strip_strings(cls, v: Any) -> Any:
        if isinstance(v, str):
            stripped = v.strip()
            return stripped or None
        return v


class CreateAdminCommentBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    post_slug: str
    body: str = Field(..., min_length=1, max_length=8000)
    in_reply_to: Optional[str] = None
    approve_parent: Optional[bool] = None

    @field_validator("post_slug", "body", "in_reply_to", mode="before")
    @classmethod
    def strip_strings(cls, v: Any) -> Any:
        if isinstance(v, str):
            stripped = v.strip()
            return stripped or None
        return v


def _raise_comment_error(exc: Exception) -> None:
    if isinstance(exc, CommentIngestError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, CommentVisibilityError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, CommentNotFoundError):
        raise HTTPException(status_code=404, detail="Comment not found") from exc
    raise exc


def _operator_display_name(user: UserPublic) -> str:
    return (user.display_name or user.username or "Editor").strip() or "Editor"


@router.get("/comments")
async def admin_list_comments(
    request: Request,
    post_slug: Optional[str] = Query(None),
    visibility: Optional[str] = Query(None),
    current_user: UserPublic = Depends(get_current_user),
    site_id: str = Depends(apply_human_site_taxonomy),
) -> dict[str, Any]:
    """List comment files for a post or the whole site (human admin)."""
    del current_user
    assert_capability(request, "write:posts", site_id=site_id)
    cleaned = (post_slug or "").strip()
    try:
        comments, pending_counts = await list_comments_admin(
            site_id, cleaned or None, visibility=visibility
        )
    except CommentVisibilityError as exc:
        _raise_comment_error(exc)
    return {
        "post_slug": cleaned,
        "comments": comments,
        "pending_counts": pending_counts,
    }


@router.post("/comments")
async def admin_create_comment(
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
    site_id: str = Depends(apply_human_site_taxonomy),
) -> dict[str, Any]:
    """Write a visible human reply beside a post. Optionally approve the parent."""
    assert_capability(request, "write:posts", site_id=site_id)
    try:
        raw = await request.json()
        payload = CreateAdminCommentBody.model_validate(raw)
    except ValidationError as exc:
        raise HTTPException(
            status_code=400, detail=format_validation_error(exc)
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc
    cleaned_post = (payload.post_slug or "").strip()
    if not cleaned_post or not (payload.body or "").strip():
        raise HTTPException(status_code=400, detail="post_slug and body are required")
    should_approve = bool(payload.in_reply_to) and payload.approve_parent is not False
    try:
        if should_approve and payload.in_reply_to:
            await set_comment_visibility(
                site_id,
                cleaned_post,
                payload.in_reply_to,
                VISIBILITY_VISIBLE,
            )
        slug = await write_comment(
            site_id,
            submitter=_operator_display_name(current_user),
            message=payload.body,
            parent_slug=cleaned_post,
            source_type=SOURCE_TYPE_ADMIN,
            in_reply_to=payload.in_reply_to,
            visibility=VISIBILITY_VISIBLE,
            author_kind=AUTHOR_KIND_HUMAN,
        )
        comment = await load_admin_comment(site_id, cleaned_post, slug)
    except (
        CommentIngestError,
        CommentNotFoundError,
        CommentVisibilityError,
    ) as exc:
        _raise_comment_error(exc)
    return {"comment": comment}


@router.patch("/comments/{comment_slug}")
async def admin_patch_comment(
    comment_slug: str,
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
    site_id: str = Depends(apply_human_site_taxonomy),
) -> dict[str, Any]:
    """Set visibility and/or rewrite body on a comment file. Not a Page."""
    del current_user
    assert_capability(request, "write:posts", site_id=site_id)
    try:
        raw = await request.json()
        payload = PatchCommentBody.model_validate(raw)
    except ValidationError as exc:
        raise HTTPException(
            status_code=400, detail=format_validation_error(exc)
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc
    cleaned_post = (payload.post_slug or "").strip()
    if not cleaned_post:
        raise HTTPException(status_code=400, detail="post_slug is required")
    if (
        payload.visibility is None
        and payload.body is None
        and payload.author_name is None
    ):
        raise HTTPException(status_code=400, detail="Nothing to update")
    try:
        comment = await update_comment(
            site_id,
            cleaned_post,
            comment_slug,
            visibility=payload.visibility,
            body=payload.body,
            author_name=payload.author_name,
        )
    except (CommentNotFoundError, CommentVisibilityError) as exc:
        _raise_comment_error(exc)
    return {"comment": comment}


@router.delete("/comments/{comment_slug}", status_code=204)
async def admin_delete_comment(
    comment_slug: str,
    request: Request,
    post_slug: Optional[str] = Query(None),
    current_user: UserPublic = Depends(get_current_user),
    site_id: str = Depends(apply_human_site_taxonomy),
) -> None:
    """Delete a comment file via storage. Git history remains."""
    del current_user
    assert_capability(request, "delete:posts", site_id=site_id)
    cleaned_post = (post_slug or "").strip()
    if not cleaned_post:
        raise HTTPException(status_code=400, detail="post_slug is required")
    try:
        await delete_comment(site_id, cleaned_post, comment_slug)
    except CommentNotFoundError as exc:
        _raise_comment_error(exc)
