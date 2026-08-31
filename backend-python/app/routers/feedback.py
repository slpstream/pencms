"""Public feedback ingest: POST /api/v1/feedback (no auth).

Public visible comments: GET /api/v1/comments?post_slug=… (no auth).
Authenticated drain: POST /api/v1/feedback/sync (human session or agent write).
"""

from __future__ import annotations

import threading
import time
from typing import Any, Literal, Optional
from urllib.parse import parse_qs, urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from models.page import format_validation_error
from models.user import UserPublic
from routers.auth import get_current_user
from routers.mcp_tools import (
    assert_mcp_capability,
    bind_mcp_actor,
    resolve_mcp_site_id,
)
from services.authz import assert_capability
from services.comment_service import (
    CommentIngestError,
    CommentsDisabledError,
    list_comments,
)
from services.feedback_service import sync_from_relay, write_ingest_item
from services.site_service import (
    DEFAULT_SITE_ID,
    HUMAN_SITE_COOKIE,
    HUMAN_SITE_HEADER,
    ensure_sites_initialized,
    get_site,
    list_sites,
    normalize_domain,
    validate_site_id,
)

router = APIRouter(prefix="/v1", tags=["feedback"])

RATE_LIMIT_MAX = 5
RATE_LIMIT_WINDOW_SECONDS = 300.0

_rate_lock = threading.Lock()
_rate_hits: dict[str, list[float]] = {}


def reset_feedback_rate_limit() -> None:
    """Clear in-process IP buckets (tests)."""
    with _rate_lock:
        _rate_hits.clear()


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        first = xff.split(",")[0].strip()
        if first:
            return first
    real = (request.headers.get("x-real-ip") or "").strip()
    if real:
        return real
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _rate_limit_ok(ip: str) -> bool:
    now = time.monotonic()
    cutoff = now - RATE_LIMIT_WINDOW_SECONDS
    with _rate_lock:
        hits = _rate_hits.setdefault(ip, [])
        hits[:] = [t for t in hits if t > cutoff]
        if len(hits) >= RATE_LIMIT_MAX:
            return False
        hits.append(now)
        return True


class FeedbackIngestRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: Optional[str] = Field(default=None, max_length=120)
    message: str = Field(..., min_length=1, max_length=8000)
    email: Optional[str] = None
    source_url: Optional[str] = None
    kind: Literal["contact", "comment"] = "contact"
    parent_slug: Optional[str] = None

    @field_validator("message", mode="before")
    @classmethod
    def strip_message(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("name", "email", "source_url", "parent_slug", mode="before")
    @classmethod
    def blank_optional(cls, v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, str):
            stripped = v.strip()
            return stripped or None
        return v

    @field_validator("kind", mode="before")
    @classmethod
    def default_kind(cls, v: Any) -> Any:
        if v is None:
            return "contact"
        if isinstance(v, str):
            stripped = v.strip().lower()
            return stripped or "contact"
        return v

    @model_validator(mode="after")
    def comment_requires_parent(self) -> "FeedbackIngestRequest":
        if self.kind == "comment" and not self.parent_slug:
            raise ValueError("parent_slug is required for comments")
        return self


async def _read_body(request: Request) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON body") from None
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="JSON body must be an object")
        return body
    form = await request.form()
    out: dict[str, Any] = {}
    for key, value in form.multi_items():
        if isinstance(value, str):
            out[key] = value
    return out


def _match_public_host_site_id(host: Optional[str]) -> Optional[str]:
    """Return site_id when Host matches a registry domain; else None.

    Inlined so LAN/preview installs without ``match_site_id_from_host`` still
    treat an unmapped Host (IP / localhost) as unbound.
    """
    ensure_sites_initialized()
    normalized = normalize_domain(host)
    if not normalized:
        return None
    for site in list_sites():
        if site.domain and site.domain == normalized:
            return site.id
    return None


def _known_public_site_id(raw: Optional[str], *, strict: bool = True) -> Optional[str]:
    """Validate a client-supplied site id for public ingest/list. None if omitted."""
    if raw is None or not str(raw).strip():
        return None
    try:
        sid = validate_site_id(raw)
    except ValueError as exc:
        if strict:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return None
    if get_site(sid) is None:
        if strict:
            raise HTTPException(status_code=400, detail=f"Unknown site_id: {sid}")
        return None
    return sid


def _site_id_from_source_url(source_url: Optional[str]) -> Optional[str]:
    """Read ``?site=`` from the page URL already posted as ``source_url``."""
    if not source_url or not str(source_url).strip():
        return None
    try:
        parsed = urlparse(str(source_url).strip())
    except ValueError:
        return None
    raw = (parse_qs(parsed.query).get("site") or [None])[0]
    return _known_public_site_id(raw, strict=False)


def _resolve_public_feedback_site_id(
    request: Request, *, source_url: Optional[str] = None
) -> str:
    """Public comments/ingest site binding (no admin session).

    Host domain match wins (cannot retarget a Host-mapped public origin).
    Unmapped Host (localhost / LAN IP): ``X-Pen-Site-Id``, request ``?site=``,
    ``source_url`` ``?site=`` (live preview), then ``pen_site_id`` cookie.
    Body ``site_id`` stays ignored.
    """
    matched = _match_public_host_site_id(request.headers.get("host"))
    if matched:
        return matched
    hinted = _known_public_site_id(request.headers.get(HUMAN_SITE_HEADER))
    if hinted:
        return hinted
    hinted = _known_public_site_id(request.query_params.get("site"))
    if hinted:
        return hinted
    hinted = _site_id_from_source_url(source_url)
    if hinted:
        return hinted
    hinted = _known_public_site_id(
        request.cookies.get(HUMAN_SITE_COOKIE), strict=False
    )
    if hinted:
        return hinted
    return DEFAULT_SITE_ID


@router.get("/comments")
async def list_public_comments(
    request: Request,
    post_slug: Optional[str] = Query(None),
) -> dict[str, Any]:
    """Unauthenticated visible comments for a post (live /blog/ thread)."""
    cleaned = (post_slug or "").strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="post_slug is required")
    site_id = _resolve_public_feedback_site_id(request)
    comments = await list_comments(site_id, cleaned)
    return {"post_slug": cleaned, "comments": comments}


async def _require_feedback_sync(request: Request) -> None:
    """Human session (write:posts / admin) or agent scope ``write``."""
    await bind_mcp_actor(request)
    if getattr(request.state, "actor_kind", None) == "agent":
        assert_mcp_capability(request, "write")
        return
    site_id = resolve_mcp_site_id(request)
    assert_capability(request, "write:posts", site_id=site_id)


@router.post("/feedback")
async def ingest_feedback(request: Request) -> dict[str, str]:
    """Accept public contact/comment submissions.

    Contact writes fb-* stub pages. Comments write ``comments/c-*.md`` beside
    an existing post (pending). Unknown parent_slug is 400.
    """
    ip = _client_ip(request)
    if not _rate_limit_ok(ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    body = await _read_body(request)
    try:
        payload = FeedbackIngestRequest.model_validate(body)
    except ValidationError as exc:
        raise HTTPException(
            status_code=400, detail=format_validation_error(exc)
        ) from exc

    site_id = _resolve_public_feedback_site_id(
        request, source_url=payload.source_url
    )
    try:
        slug = await write_ingest_item(
            site_id,
            submitter=payload.name or "Anonymous",
            message=payload.message,
            email=payload.email,
            source_url=payload.source_url,
            kind=payload.kind,
            parent_slug=payload.parent_slug,
            source_type="form",
        )
    except CommentsDisabledError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except CommentIngestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "received", "slug": slug}


@router.post(
    "/feedback/sync",
    dependencies=[Depends(_require_feedback_sync)],
)
async def sync_feedback(
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> dict:
    """Pull the public relay queue into fb-* stubs for the actor's site."""
    site_id = resolve_mcp_site_id(request)
    return await sync_from_relay(site_id)
