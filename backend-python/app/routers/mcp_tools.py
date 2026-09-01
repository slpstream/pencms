import base64
import json
import subprocess
import uuid
from typing import Any, Dict, List, Optional

from config import COLLECTIONS_SCHEMA, CONTENT_DIR_PATH, REQUIRED_FIELDS, TAXONOMY, content_storage
from fastapi import APIRouter, BackgroundTasks, Body, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from models.user import UserPublic
from routers.ai_proxy import is_valid_url
import httpx
from routers.auth import get_current_user
from services.ai_settings_service import agent_house_facts, load_ai_settings
from services.publish_autonomy import (
    PublishAutonomyError,
    clear_review_if_published,
    enforce_publish_autonomy,
)
from services.extract_prompts import extractive_prompts_payload
from services.house_url_service import public_path_if_live
from services.authz import caps_for_actor, expand_capabilities
from services.cache_service import get_collections_list, query_entries, search_entries
from services.concurrency import check_expected_version, page_version_token
from services.file_service import (
    get_site_language_config,
    list_pages,
    read_page,
    sanitize_slug,
    write_page,
)
from services.i18n_service import ContentI18nError, normalize_requested_language
from services.i18n_run_service import list_runs, start_run, update_run
from services.translation_service import (
    TranslationAuthorizationError,
    TranslationConflictError,
    TranslationNotFoundError,
    actor_context_from_state,
    create_translation_sibling,
    delete_translation_sibling as delete_translation_sibling_service,
    page_payload,
    plan_translation_run,
    require_active_config,
    reject_spoofed_provenance,
    review_translation_sibling,
    stamp_actor_provenance,
    translation_config,
    translation_coverage,
    update_translation_sibling,
)


class ReviewRequest(BaseModel):
    checklist: Optional[str] = None   # Override stored checklist
    model: Optional[str] = None       # Override default model


class CheckExpandRefsRequest(BaseModel):
    markdown: Optional[str] = None
    slug: Optional[str] = None


def _escape_shortcode_attr(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _catalog_row_from_page(page) -> Dict[str, Any]:
    """Build an enrich shape matching the AI sidebar published catalog."""
    fm = page.frontmatter if isinstance(page.frontmatter, dict) else {}
    slug = str(getattr(page, "id", None) or fm.get("slug") or "").strip()
    hero_title = str(fm.get("hero_title") or "").strip() or None
    name = str(fm.get("name") or "").strip() or None
    title = (
        hero_title
        or name
        or str(fm.get("title") or "").strip()
        or slug
    )
    suggested_text = hero_title or name or str(fm.get("title") or "").strip() or slug
    return {
        "slug": slug,
        "title": title,
        "hero_title": hero_title,
        "name": name,
        "suggested_text": suggested_text,
        "markdown_link": f"[{suggested_text}]({slug})",
        "expand_shortcode": (
            f'[expand slug="{_escape_shortcode_attr(slug)}" '
            f'text="{_escape_shortcode_attr(suggested_text)}"]'
        ),
    }


def _parse_expand_embed_refs(text: str) -> List[Dict[str, Any]]:
    """Scan markdown for [expand]/[embed] shortcodes (slug-only health)."""
    import re

    refs: List[Dict[str, Any]] = []
    re_sc = re.compile(r"\[(expand|embed)\s*([^\]]*)\]", re.IGNORECASE)
    for m in re_sc.finditer(text or ""):
        mode = m.group(1).lower()
        attr = m.group(2) or ""
        slug = ""
        heading = None
        slug_m = re.search(
            r'(?:^|\s)slug\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s\]]+))',
            attr,
            re.IGNORECASE,
        )
        def_m = re.match(
            r'^\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s\]]+))',
            attr,
        )
        head_m = re.search(
            r'heading\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s\]]+))',
            attr,
            re.IGNORECASE,
        )
        if slug_m:
            slug = slug_m.group(1) or slug_m.group(2) or slug_m.group(3) or ""
        elif def_m:
            slug = def_m.group(1) or def_m.group(2) or def_m.group(3) or ""
        if head_m:
            heading = head_m.group(1) or head_m.group(2) or head_m.group(3) or None
        if "#" in slug:
            parts = slug.split("#", 1)
            slug = parts[0]
            if not heading:
                heading = parts[1] or None
        refs.append(
            {
                "mode": mode,
                "slug": (slug or "").strip(),
                "heading": heading,
            }
        )
    return refs


router = APIRouter(prefix="/api/v1", tags=["mcp"])


def sanitize_media_path(filename: str) -> str:
    """Sanitize a site-relative media path to prevent directory traversal."""
    clean = filename.replace("\\", "/").strip("/")

    if ".." in clean.split("/"):
        raise HTTPException(
            status_code=400, detail="Directory traversal is not allowed"
        )

    parts = clean.split("/")
    # Strip accidental sites/{id}/assets/ prefix if an agent passes a full path
    if len(parts) >= 3 and parts[0] == "sites" and parts[2] == "assets":
        clean = "/".join(parts[3:])
        parts = clean.split("/") if clean else []

    if len(parts) >= 5 and parts[0] == "images" and parts[1] == "content":
        target = f"images/content/{parts[3]}/{parts[4]}"
    else:
        target = clean

    return target


def normalize_public_media_paths(text: str) -> str:
    """Rewrite /api/assets/raw/... public URLs to site-relative paths in text.

    Editor preview and some clients embed public_url forms; content on disk
    should use relative_path (e.g. images/content/...). Safe no-op when absent.
    """
    import re

    if not text:
        return text or ""
    out = re.sub(
        r"/api/assets/raw/sites/[^/]+/assets/",
        "",
        text,
    )
    out = re.sub(
        r"/api/assets/raw/images/content/",
        "images/content/",
        out,
    )
    return out


def _normalize_media_fields_in_frontmatter(fm: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize hero_image / main_image public_url forms to relative paths."""
    out = dict(fm)
    for key in ("hero_image", "main_image"):
        val = out.get(key)
        if isinstance(val, str) and val.strip():
            out[key] = normalize_public_media_paths(val.strip())
    return out


def _extract_image_shortcode_srcs(body: str) -> List[str]:
    """Return non-empty src values from [image ...] shortcodes in body markdown."""
    import re

    return [
        m.group(2).strip()
        for m in re.finditer(
            r'\[image[^\]]*?\bsrc=(["\'])(.*?)\1',
            body or "",
            flags=re.IGNORECASE,
        )
        if m.group(2).strip()
    ]


async def collect_media_path_warnings(
    site_id: str,
    body: str,
    frontmatter: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Soft-check image paths referenced in body shortcodes and frontmatter.

    Returns warning strings; never raises. Skips empty values and http(s) URLs.
    """
    from services.site_service import join_site_assets_path

    candidates: List[str] = []
    candidates.extend(_extract_image_shortcode_srcs(body or ""))
    fm = frontmatter or {}
    for key in ("hero_image", "main_image"):
        val = fm.get(key)
        if isinstance(val, str) and val.strip():
            candidates.append(val.strip())

    warnings: List[str] = []
    seen: set = set()
    for raw in candidates:
        if raw in seen:
            continue
        seen.add(raw)
        if raw.startswith(("http://", "https://")):
            continue
        if "/api/assets/raw/" in raw or raw.startswith("/api/assets/"):
            warnings.append(
                f"Media path looks like a public_url API path ('{raw}'). "
                "Use the site-relative relative_path from generate_media / list_media "
                "in shortcodes and frontmatter (e.g. hero_image)."
            )
            continue
        try:
            logical = sanitize_media_path(raw)
        except HTTPException:
            warnings.append(
                f"Media path is invalid ('{raw}'). "
                "Use relative_path from generate_media / list_media."
            )
            continue
        storage_path = join_site_assets_path(site_id, logical)
        if content_storage is not None and not await content_storage.exists(storage_path):
            warnings.append(
                f"Media path not found in site library: '{raw}'. "
                "Use relative_path from generate_media / list_media."
            )
    return warnings


def resolve_mcp_site_id(request: Request) -> str:
    """Return the active site_id for an MCP tool call.

    Agents must carry a valid ``site_id`` claim (set on ``request.state`` by
    ``require_scope``). Human sessions use the same active-site preference as
    admin content routes (``X-Pen-Site-Id`` / ``pen_site_id`` / ``default``).
    """
    site_id = getattr(request.state, "site_id", None)
    if site_id:
        return site_id
    from services.site_service import resolve_human_site_id

    return resolve_human_site_id(request)


def _content_write_cap(frontmatter_or_page: Any) -> str:
    from routers.pages import is_page_doc

    return "write:pages" if is_page_doc(frontmatter_or_page) else "write:posts"


_BOOL_FRONTMATTER_KEYS = frozenset(
    {"page", "needs_review", "published", "pinned", "noindex"}
)


def _coerce_faqs_value(value: Any) -> list:
    """Accept a list of {q, a} or a JSON string of that list. Empty is valid."""
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=422,
                detail="faqs must be a JSON array of {q, a} objects.",
            ) from exc
    if value is None:
        return []
    if not isinstance(value, list):
        raise HTTPException(
            status_code=422,
            detail="faqs must be a JSON array of {q, a} objects.",
        )
    coerced: list = []
    for item in value:
        if not isinstance(item, dict) or "q" not in item or "a" not in item:
            raise HTTPException(
                status_code=422,
                detail="faqs items must be objects with q and a strings.",
            )
        coerced.append({"q": str(item["q"]), "a": str(item["a"])})
    return coerced


def _coerce_frontmatter_value(key: str, value: Any) -> Any:
    """Match the editor sidebar's boolean YAML keys; parse faqs JSON strings."""
    if key == "faqs":
        return _coerce_faqs_value(value)
    if key not in _BOOL_FRONTMATTER_KEYS:
        return value
    if isinstance(value, str):
        return value.strip().lower() == "true"
    return bool(value)


def _content_delete_cap(frontmatter_or_page: Any) -> str:
    from routers.pages import is_page_doc

    return "delete:pages" if is_page_doc(frontmatter_or_page) else "delete:posts"


def _raise_missing_mcp_scope(request: Request, required_scope: str) -> None:
    from services.auth_service import bearer_www_authenticate

    if getattr(request.state, "actor_kind", None) == "agent":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Agent key lacks required scope: {required_scope}",
            headers={
                "WWW-Authenticate": bearer_www_authenticate(
                    scope=required_scope,
                    error="insufficient_scope",
                ),
            },
        )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"missing_capability: {required_scope}",
    )


def assert_mcp_capability(request: Request, required_scope: str) -> None:
    """Raise 403 unless the already-bound MCP actor may do ``required_scope``."""
    if getattr(request.state, "actor_kind", None) == "agent":
        scopes = getattr(request.state, "actor_scopes", ()) or ()
        if required_scope not in expand_capabilities(scopes):
            _raise_missing_mcp_scope(request, required_scope)
        return

    from services.authz import resolve_request_user

    user, payload = resolve_request_user(request)
    site_id = getattr(request.state, "site_id", None) or resolve_mcp_site_id(request)
    if required_scope not in caps_for_actor(
        user, site_id=str(site_id), token_payload=payload
    ):
        _raise_missing_mcp_scope(request, required_scope)


async def bind_mcp_actor(request: Request) -> None:
    """Authenticate and bind ``request.state`` site/actor. Does not check a cap.

    Used by posts-vs-pages tools that pick ``write:posts`` / ``write:pages``
    (or delete:*) from the document after bind.
    """
    from services.auth_service import (
        bearer_www_authenticate,
        decode_access_token,
        decode_agent_token,
    )
    from services.site_service import (
        ensure_sites_initialized,
        get_site,
        resolve_human_site_id,
    )
    import jwt as pyjwt

    token = None
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        token = auth.split(" ")[1]
    if not token:
        token = request.cookies.get("pen_jwt")
    if not token:
        raise HTTPException(401, "Not authenticated")

    try:
        peek = decode_access_token(token)
    except Exception:
        raise HTTPException(401, "Invalid token")

    if peek.get("type") == "agent":
        try:
            payload = decode_agent_token(token)
        except pyjwt.PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={
                    "WWW-Authenticate": bearer_www_authenticate(scope="read"),
                },
            )
        site_id = payload.get("site_id")
        if not site_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Agent token missing site_id claim",
            )
        ensure_sites_initialized()
        if get_site(site_id) is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Agent token site_id unknown: {site_id}",
            )
        # JWT site_id is authoritative — do not honor X-Pen-Site-Id / cookie.
        request.state.site_id = site_id
        request.state.actor_kind = "agent"
        request.state.actor_id = (
            payload.get("agent_key_name")
            or f"key-{payload.get('agent_key_index')}"
        )
        request.state.actor_scopes = tuple(payload.get("scopes") or [])
        request.state.actor_key_id = payload.get("agent_key_id")
        return

    from services.user_service import get_user_by_uuid

    request.state.site_id = resolve_human_site_id(request)
    request.state.actor_kind = "human"
    subject = str(peek.get("sub") or "")
    user = get_user_by_uuid(subject) if subject else None
    if user is None:
        raise HTTPException(401, "User no longer exists")
    request.state.actor_id = user.public.username
    request.state.actor_scopes = ()
    request.state.actor_key_id = None


def require_scope(required_scope: Optional[str] = None):
    """FastAPI dependency factory: bind MCP actor, then enforce ``required_scope``.

    Agents: JWT scopes after ``expand_capabilities`` (iss/aud via
    ``decode_agent_token``). Humans: memberships via ``caps_for_actor``
    (admin still has all caps). Pass ``None`` to bind only — posts-vs-pages
    tools then call ``assert_mcp_capability``.
    """

    async def _check(request: Request):
        await bind_mcp_actor(request)
        if required_scope:
            assert_mcp_capability(request, required_scope)

    return _check


# --- Read tools (scope: read) ---


@router.get(
    "/mcp/pages/{slug}/metadata",
    operation_id="read_page_metadata",
    dependencies=[Depends(require_scope("read"))],
)
async def read_page_metadata(
    slug: str,
    request: Request,
    language: Optional[str] = None,
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return frontmatter + stats for a content entry, without the body."""
    site_id = resolve_mcp_site_id(request)
    page = await read_page(
        slug, include_partials=False, site_id=site_id, language=language
    )
    if not page:
        raise HTTPException(404, f"Page '{slug}' not found")
    return {
        "slug": slug,
        "frontmatter": page.frontmatter,
        "composite": page.composite,
        "version": await page_version_token(page.file_path),
        "site_id": site_id,
        "language": page.language,
        "translation_group": page.translation_group,
        "translations": [
            peer.model_dump(exclude_none=True) for peer in (page.translations or [])
        ],
    }


@router.get(
    "/mcp/pages/{slug}/content",
    operation_id="read_page_content",
    dependencies=[Depends(require_scope("read"))],
)
async def read_page_content(
    slug: str,
    request: Request,
    language: Optional[str] = None,
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return the full Markdown body (and partials, if composite) of a page."""
    site_id = resolve_mcp_site_id(request)
    page = await read_page(
        slug, include_partials=True, site_id=site_id, language=language
    )
    if not page:
        raise HTTPException(404, f"Page '{slug}' not found")
    return {
        "slug": slug,
        "body": page.content,
        "partials": page.partials,
        "composite": page.composite,
        "version": await page_version_token(page.file_path),
        "site_id": site_id,
        "language": page.language,
        "translation_group": page.translation_group,
    }


@router.get(
    "/mcp/collections/{collection_name}/entries",
    operation_id="list_collection_entries",
    dependencies=[Depends(require_scope("read"))],
)
async def list_collection_entries(
    collection_name: str,
    request: Request,
    page: int = 1,
    limit: int = 20,
    language: Optional[str] = None,
    fallback: str = "none",
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    """List entries in a collection (paginated). Returns slug, title, status, modified_at."""
    site_id = resolve_mcp_site_id(request)
    config = get_site_language_config(site_id)
    requested_language = normalize_requested_language(language, config)
    items, total = query_entries(
        collection_name,
        page,
        limit,
        site_id=site_id,
        language=requested_language,
        fallback=fallback,
    )
    return {"items": items, "total": total, "page": page, "limit": limit, "site_id": site_id}


@router.get(
    "/mcp/collections",
    operation_id="list_collections",
    dependencies=[Depends(require_scope("read"))],
)
async def list_collections(
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """List all available content collections."""
    return get_collections_list(site_id=resolve_mcp_site_id(request))


@router.get(
    "/mcp/search",
    operation_id="search_content",
    dependencies=[Depends(require_scope("read"))],
)
async def search_content(
    query: str,
    request: Request,
    limit: int = 20,
    language: Optional[str] = None,
    current_user: UserPublic = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """Full-text search across all content (title, frontmatter, body)."""
    site_id = resolve_mcp_site_id(request)
    config = get_site_language_config(site_id)
    requested_language = normalize_requested_language(language, config)
    return search_entries(
        query, limit=limit, site_id=site_id, language=requested_language
    )


@router.get(
    "/mcp/translations/config",
    operation_id="get_translation_config",
    dependencies=[Depends(require_scope("read"))],
)
async def get_translation_config_tool(
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return active-language, labels, and automation-pause configuration."""
    return translation_config(resolve_mcp_site_id(request))


@router.get(
    "/mcp/translations/gaps",
    operation_id="list_translation_gaps",
    dependencies=[Depends(require_scope("read"))],
)
async def list_translation_gaps_tool(
    request: Request,
    language: Optional[str] = None,
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return exact coverage rows that have missing/draft/review/rejected gaps."""
    coverage = await translation_coverage(
        resolve_mcp_site_id(request), language=language
    )
    return {
        "config": coverage["config"],
        "totals": coverage["totals"],
        "items": [row for row in coverage["items"] if row["gap_codes"]],
    }


@router.post(
    "/mcp/translations/{slug}",
    operation_id="create_translation_sibling",
    dependencies=[Depends(require_scope())],
)
async def create_translation_sibling_tool(
    slug: str,
    request: Request,
    language: str = Body(...),
    collection: str = Body(default="general"),
    frontmatter: Optional[Dict[str, Any]] = Body(default=None),
    body: str = Body(default=""),
    composite: Optional[bool] = Body(default=None),
    partials: Optional[Dict[str, str]] = Body(default=None),
    run_id: Optional[str] = Body(default=None),
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    """Create one exact draft sibling; never overwrites an existing locale."""
    site_id = resolve_mcp_site_id(request)
    existing = await read_page(sanitize_slug(slug), site_id=site_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Source document not found")
    assert_mcp_capability(request, _content_write_cap(existing))
    try:
        page = await create_translation_sibling(
            collection=collection,
            slug=sanitize_slug(slug),
            language=language,
            actor=actor_context_from_state(request, site_id),
            frontmatter=frontmatter,
            body=body,
            composite=composite,
            partials=partials,
            run_id=run_id,
        )
        return {
            "message": "Translation sibling created",
            "entry": page_payload(page),
            "site_id": site_id,
        }
    except TranslationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TranslationConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except TranslationAuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (ContentI18nError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete(
    "/mcp/translations/{slug}/{language}",
    operation_id="delete_translation_sibling",
    dependencies=[Depends(require_scope())],
)
async def delete_translation_sibling_tool(
    slug: str,
    language: str,
    request: Request,
    collection: str = "general",
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    """Delete one exact non-default sibling without cascading to its group."""
    site_id = resolve_mcp_site_id(request)
    existing = await read_page(sanitize_slug(slug), site_id=site_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Source document not found")
    assert_mcp_capability(request, _content_delete_cap(existing))
    try:
        deleted = await delete_translation_sibling_service(
            collection=collection,
            slug=sanitize_slug(slug),
            language=language,
            actor=actor_context_from_state(request, site_id),
        )
    except TranslationConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except TranslationAuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (ContentI18nError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Translation sibling not found")
    return {"message": "Translation sibling deleted", "site_id": site_id}


@router.post(
    "/mcp/translations/{slug}/{language}/review",
    operation_id="review_translation_sibling",
    dependencies=[Depends(require_scope("publish:content"))],
)
async def review_translation_sibling_tool(
    slug: str,
    language: str,
    request: Request,
    decision: str = Body(..., embed=True),
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    """Approve or reject an exact sibling under the current human-review policy."""
    site_id = resolve_mcp_site_id(request)
    try:
        page = await review_translation_sibling(
            slug=sanitize_slug(slug),
            language=language,
            actor=actor_context_from_state(request, site_id),
            decision=decision,
        )
        return {
            "message": f"Translation {decision} recorded",
            "entry": page_payload(page),
            "site_id": site_id,
        }
    except TranslationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TranslationConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except TranslationAuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (ContentI18nError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/mcp/i18n-runs",
    operation_id="list_translation_runs",
    dependencies=[Depends(require_scope("read"))],
)
async def list_translation_runs_tool(
    request: Request,
    limit: int = 25,
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    """List recent bounded telemetry for this credential's site."""
    return {"runs": list_runs(resolve_mcp_site_id(request), limit=limit)}


@router.post(
    "/mcp/i18n-runs",
    operation_id="report_translation_run",
    dependencies=[Depends(require_scope("write"))],
)
async def report_translation_run_tool(
    request: Request,
    run_id: Optional[str] = Body(default=None),
    mode: Optional[str] = Body(default=None),
    target_languages: Optional[List[str]] = Body(default=None),
    run_status: Optional[str] = Body(default=None),
    counts: Optional[Dict[str, int]] = Body(default=None),
    error: Optional[str] = Body(default=None),
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    """Start or update telemetry for external work; never schedules or runs a model."""
    site_id = resolve_mcp_site_id(request)
    actor = actor_context_from_state(request, site_id)
    try:
        if run_id is None:
            config = require_active_config(site_id)
            effective_config = translation_config(site_id)
            policy_targets = list(
                effective_config.get("automation_policy", {}).get("targets", {})
            )
            targets = target_languages or (
                policy_targets
                if actor.is_agent
                and effective_config.get("automation_policy", {}).get("enabled")
                else [code for code in config.languages if code != config.language]
            )
            selected_mode = mode or "translate"
            policy_snapshot = plan_translation_run(
                actor=actor,
                mode=selected_mode,
                target_languages=targets,
            )
            return start_run(
                site_id=site_id,
                actor=actor.kind,
                actor_id=actor.actor_id,
                mode=selected_mode,
                target_languages=targets,
                policy_snapshot=policy_snapshot,
            )
        return update_run(
            site_id=site_id,
            run_id=run_id,
            actor=actor.kind,
            actor_id=actor.actor_id,
            status=run_status,
            counts=counts,
            error=error,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Translation run not found: {exc.args[0]}") from exc
    except TranslationAuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (ContentI18nError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/mcp/suggest-internal-links",
    operation_id="suggest_internal_links",
    dependencies=[Depends(require_scope("read"))],
)
async def mcp_suggest_internal_links(
    query: str,
    request: Request,
    limit: int = 8,
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    """Suggest live-published pages for Markdown links or [expand]/[embed] targets.

    Filters to status=published with publish_at null or past. Returns enriched
    rows (suggested_text, markdown_link, expand_shortcode). Prefer insert via
    write_content_file with the shortcode string — there is no MCP cursor insert.
    """
    site_id = resolve_mcp_site_id(request)
    q = (query or "").strip().lower()
    if not q:
        raise HTTPException(400, "query is required")

    pages = await list_pages(site_id=site_id, live_only=True)
    results: List[Dict[str, Any]] = []
    for page in pages:
        row = _catalog_row_from_page(page)
        if not row["slug"]:
            continue
        hay = " ".join(
            filter(
                None,
                [
                    row["title"],
                    row.get("hero_title") or "",
                    row.get("name") or "",
                    row["slug"],
                ],
            )
        ).lower()
        if q not in hay:
            # Also match any significant token from a multi-word query
            tokens = [t for t in q.split() if len(t) > 2]
            if tokens and not any(t in hay for t in tokens):
                continue
            if not tokens:
                continue
        results.append(row)
        if len(results) >= max(1, min(limit, 20)):
            break

    return {
        "query_used": query.strip(),
        "results": results,
        "usage_hint": (
            "For Nutshells insert [expand slug=\"…\" text=\"…\"] via "
            "write_content_file; for normal links use markdown_link / [text](slug)."
        ),
        "site_id": site_id,
    }


@router.post(
    "/mcp/check-expand-refs",
    operation_id="check_expand_refs",
    dependencies=[Depends(require_scope("read"))],
)
async def mcp_check_expand_refs(
    request: Request,
    body: CheckExpandRefsRequest = Body(...),
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    """Validate [expand]/[embed] target slugs in markdown or a page body.

    Heading misses are not broken (resolver falls back to the whole post).
    Only missing/unpublished slugs are flagged.
    """
    site_id = resolve_mcp_site_id(request)
    markdown = body.markdown
    if (markdown is None or markdown == "") and body.slug:
        page = await read_page(body.slug, include_partials=True, site_id=site_id)
        if not page:
            raise HTTPException(404, f"Page '{body.slug}' not found")
        blobs = [page.content or ""]
        if page.partials:
            blobs.extend((v or "") for v in page.partials.values())
        markdown = "\n".join(blobs)
    if markdown is None:
        raise HTTPException(400, "Provide markdown or slug")

    refs = _parse_expand_embed_refs(markdown)
    if not refs:
        return {"ok": True, "broken": [], "checked": 0, "site_id": site_id}

    pages = await list_pages(site_id=site_id, live_only=True)
    published = {
        str(getattr(p, "id", None) or "").strip()
        for p in pages
        if str(getattr(p, "id", None) or "").strip()
    }

    broken: List[Dict[str, Any]] = []
    for ref in refs:
        if not ref["slug"]:
            broken.append(
                {
                    "slug": "",
                    "heading": ref.get("heading"),
                    "mode": ref["mode"],
                    "reason": "missing_slug",
                }
            )
        elif ref["slug"] not in published:
            broken.append(
                {
                    "slug": ref["slug"],
                    "heading": ref.get("heading"),
                    "mode": ref["mode"],
                    "reason": "not_found_or_unpublished",
                }
            )

    return {
        "ok": len(broken) == 0,
        "broken": broken,
        "checked": len(refs),
        "site_id": site_id,
    }


@router.get(
    "/mcp/media",
    operation_id="list_media",
    dependencies=[Depends(require_scope("read"))],
)
async def list_media(
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """Browse the media library for the agent's site. Returns filenames and public URLs."""
    from routers.assets import public_asset_url, _logical_from_site_path
    from services.site_service import site_assets_prefix

    site_id = resolve_mcp_site_id(request)
    prefix = site_assets_prefix(site_id)
    if content_storage is None or not await content_storage.exists(prefix):
        return []
    files = await content_storage.list_dir(prefix, recursive=True)
    result = []
    for f in files:
        storage_path = f if f.startswith(prefix) else f"{prefix}/{f}"
        logical = _logical_from_site_path(site_id, storage_path)
        result.append(
            {
                "filename": logical,
                "public_url": public_asset_url(site_id, logical),
                "site_id": site_id,
            }
        )
    return result


@router.get(
    "/mcp/site-config",
    operation_id="get_site_config",
    dependencies=[Depends(require_scope("read"))],
)
async def get_site_config(
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    """Read site settings, taxonomy, collection schemas, and extractive prompts."""
    import config

    site_id = resolve_mcp_site_id(request)
    snap = config.load_taxonomy_for_site(site_id)
    ai_settings = load_ai_settings(site_id)
    checklist = ai_settings.get("post_quality_checklist", "") or DEFAULT_QUALITY_CHECKLIST
    facts = agent_house_facts(site_id)
    return {
        "collections": config.load_collections_for_site(site_id),
        "taxonomy": snap["vocabularies"],
        "required_fields": snap["required_fields"],
        "prompts": {
            "text_generation_prompt": ai_settings.get("text_generation_prompt", "") or "",
            "image_generation_prompt": ai_settings.get("image_generation_prompt", "") or "",
            "post_quality_checklist": checklist,
        },
        "extractive_prompts": extractive_prompts_payload(),
        "sitename": facts["sitename"],
        "agent": {
            "ai_publish_autonomy": facts["ai_publish_autonomy"],
            "ai_metadata_scope": facts["ai_metadata_scope"],
        },
        "site_id": site_id,
    }


DEFAULT_QUALITY_CHECKLIST = """1. **Title & Meta**: Does the post have a clear, compelling hero_title? Is the meta description (if any) 150-160 chars?
2. **Structure**: Does the post use H2/H3 headings logically? Is there a clear introduction, body sections, and conclusion?
3. **Readability**: Are paragraphs concise (3-5 sentences)? Is the tone consistent? Are sentences in active voice?
4. **SEO**: Is the primary keyword used naturally in the title, first paragraph, and headings? Are there internal link opportunities?
5. **Content Completeness**: Does the post adequately cover the topic? Are claims supported? Are there obvious gaps?
6. **Formatting**: Is markdown used effectively (lists, bold, blockquotes)? Are images/media referenced where appropriate?
7. **Call to Action**: Does the post end with a clear next step for the reader?"""


async def _call_llm_chat(
    messages: List[Dict[str, Any]],
    base_url: str,
    model: str,
    api_key: Optional[str] = None,
    temperature: float = 0.5,
) -> str:
    """Helper to call LLM chat completion endpoint with standard error handling and validation."""
    if not is_valid_url(base_url):
        raise HTTPException(status_code=400, detail="Invalid or restricted Base URL.")

    # Determine loopback/localhost for local auth exception
    from urllib.parse import urlparse
    import ipaddress as ipaddress_mod
    parsed = urlparse(base_url)
    hostname = parsed.hostname or ""
    is_local = hostname.lower() == "localhost"
    if not is_local:
        try:
            ip = ipaddress_mod.ip_address(hostname)
            if ip.is_loopback:
                is_local = True
        except ValueError:
            pass

    if not is_local and not api_key:
        raise HTTPException(
            status_code=400,
            detail="AI Provider API Key is required for non-local endpoints.",
        )

    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "temperature": temperature,
    }

    headers = {"Content-Type": "application/json"}
    if api_key and not is_local:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(endpoint, json=payload, headers=headers)
            if resp.status_code != 200:
                detail = resp.text
                try:
                    err_json = resp.json()
                    detail = err_json.get("error", {}).get("message", detail)
                except Exception:
                    pass
                raise HTTPException(
                    status_code=502,
                    detail=f"LLM evaluation failed upstream: {detail}"
                )

            data = resp.json()
            return data["choices"][0]["message"]["content"]

    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to connect to AI provider: {str(exc)}"
        )


@router.post(
    "/mcp/pages/{slug}/review",
    operation_id="review_post",
    dependencies=[Depends(require_scope("read"))],
)
async def review_post(
    slug: str,
    http_request: Request,
    request: ReviewRequest = Body(default=ReviewRequest()),
    current_user: UserPublic = Depends(get_current_user),
    x_pen_ai_key: Optional[str] = Header(None, alias="X-Pen-AI-Key"),
    x_pen_ai_base_url: Optional[str] = Header(None, alias="X-Pen-AI-Base-URL"),
    x_pen_ai_model: Optional[str] = Header(None, alias="X-Pen-AI-Model"),
) -> Dict[str, Any]:
    """Evaluate a post against a quality checklist using the configured LLM.
    
    Checklist resolution order:
    1. `checklist` field in request body (ad-hoc override)
    2. `post_quality_checklist` from per-site AI settings
    3. Hardcoded built-in default checklist
    
    Returns a structured scorecard with per-criterion scores, notes,
    suggested edits, top improvements, and the raw LLM evaluation text.
    """
    # 1. Read post from disk
    site_id = resolve_mcp_site_id(http_request)
    page = await read_page(slug, include_partials=True, site_id=site_id)
    if not page:
        raise HTTPException(404, f"Page '{slug}' not found")

    # 2. Resolve checklist
    checklist_text = request.checklist
    if not checklist_text or not checklist_text.strip():
        checklist_text = load_ai_settings(site_id).get("post_quality_checklist", "") or ""
    
    if not checklist_text or not checklist_text.strip():
        # Hardcoded default
        checklist_text = DEFAULT_QUALITY_CHECKLIST

    # 3. Build the full post text for evaluation
    fm_str = json.dumps(page.frontmatter, indent=2) if page.frontmatter else '(empty)'
    post_text = f"## Frontmatter\n```json\n{fm_str}\n```\n\n"
    post_text += f"## Body\n{page.content or '(empty)'}\n"
    if page.composite and page.partials:
        for name, content in page.partials.items():
            post_text += f"\n## Fragment: _{name}.md\n{content or '(empty)'}\n"

    # 4. Build evaluation prompt
    eval_prompt = f"""You are a content quality evaluator. Assess the following post against the provided checklist. Be thorough, specific, and actionable.

## Quality Checklist
{checklist_text}

## Post to Evaluate (slug: {slug})
{post_text}

## Instructions
For each criterion in the checklist above:
- Assign a score from 0 to 100
- Explain the score with specific observations about the post
- Suggest a concrete edit that would improve the score

Then provide:
1. An overall score (weighted average, with content completeness and SEO weighted higher)
2. A prioritized list of the top 3-5 improvements that would have the highest impact

Return your evaluation as a JSON object with this exact structure:
{{
  "overall_score": <int 0-100>,
  "criteria": [
    {{
      "name": "<criterion name>",
      "score": <int 0-100>,
      "notes": "<specific observation>",
      "suggested_edit": "<concrete edit suggestion>"
    }}
  ],
  "top_improvements": [
    "<improvement 1>",
    "<improvement 2>"
  ]
}}

Return ONLY the JSON object, no other text."""

    # 5. Call the LLM
    base_url = x_pen_ai_base_url or "https://api.openai.com/v1"
    model = request.model or x_pen_ai_model
    if not model:
        raise HTTPException(
            status_code=400,
            detail="Model must be specified in request body or X-Pen-AI-Model header.",
        )

    raw_text = await _call_llm_chat(
        messages=[{"role": "user", "content": eval_prompt}],
        base_url=base_url,
        model=model,
        api_key=x_pen_ai_key,
        temperature=0.5,
    )

    # 6. Parse the structured response
    # Try to extract JSON from the response (handle markdown code fences)
    import re
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw_text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        # Try raw JSON
        json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        json_str = json_match.group(0) if json_match else raw_text

    try:
        parsed = json.loads(json_str)
        overall_score = parsed.get("overall_score", 0)
        criteria = parsed.get("criteria", [])
        top_improvements = parsed.get("top_improvements", [])
    except (json.JSONDecodeError, AttributeError, ValueError):
        # Fallback if parsing fails: return raw text in a single criterion
        overall_score = 0
        criteria = [{
            "name": "Fallback Review",
            "score": 0,
            "notes": "Could not parse JSON response from LLM.",
            "suggested_edit": "Please see raw_evaluation for the full text feedback."
        }]
        top_improvements = []

    return {
        "slug": slug,
        "overall_score": overall_score,
        "criteria": criteria,
        "top_improvements": top_improvements,
        "raw_evaluation": raw_text,
    }


# --- Write tools (scope: write) ---


@router.patch(
    "/mcp/pages/{slug}/frontmatter",
    operation_id="update_frontmatter_field",
    dependencies=[Depends(require_scope())],
)
async def update_frontmatter_field(
    slug: str,
    request: Request,
    key: str = Body(..., embed=True),
    value: Any = Body(default=None, embed=True),
    expected_version: Optional[str] = Body(default=None, embed=True),
    force: bool = Body(default=False, embed=True),
    language: Optional[str] = Body(default=None, embed=True),
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    """Patch one YAML frontmatter field; the Markdown body and other keys stay on disk.

    Use this for ``deck``, ``summary``, ``faqs``, ``hero_title``, ``category``, ``status``, ``author``,
    ``publish_at``, etc. ``faqs`` is a list of ``{q, a}`` strings; ``[]`` is valid
    and clears the field. Do not use ``write_content_file`` (and do not read this
    repo) when only frontmatter changes. Same merge, scopes, and AI guardrails
    as ``write_content_file``. The editor AI sidebar keeps its own local
    ``update_frontmatter_field`` (open-document form + save); this HTTP tool is
    for remote MCP agents.
    """
    field = (key or "").strip()
    if not field or field in {"slug", "is_legacy"}:
        raise HTTPException(
            status_code=400,
            detail="key must be a frontmatter field name (not slug or empty).",
        )
    site_id = resolve_mcp_site_id(request)
    language_config = get_site_language_config(site_id)
    try:
        requested_language = normalize_requested_language(language, language_config)
    except ContentI18nError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    page = await read_page(
        sanitize_slug(slug),
        include_partials=True,
        site_id=site_id,
        language=requested_language,
    )
    if not page:
        raise HTTPException(status_code=404, detail=f"Page '{slug}' not found")
    return await write_content_file(
        slug,
        request,
        frontmatter={field: _coerce_frontmatter_value(field, value)},
        body=page.content,
        composite=page.composite,
        partials=page.partials,
        expected_version=expected_version,
        force=force,
        language=language,
        run_id=None,
        current_user=current_user,
    )


@router.put(
    "/mcp/pages/{slug}",
    operation_id="write_content_file",
    dependencies=[Depends(require_scope())],
)
async def write_content_file(
    slug: str,
    request: Request,
    frontmatter: Dict[str, Any] = Body(...),
    body: Optional[str] = Body(default=None),
    composite: Optional[bool] = Body(default=None),
    partials: Optional[Dict[str, str]] = Body(default=None),
    expected_version: Optional[str] = Body(default=None),
    force: bool = Body(default=False),
    language: Optional[str] = Body(default=None),
    run_id: Optional[str] = Body(default=None),
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    """Partial frontmatter merge plus Markdown body write. Omitted YAML keys stay on disk.

    Prefer ``update_frontmatter_field`` to change one field (``deck``,
    ``faqs``, ``hero_title``, …) without resending the body. This tool is for create,
    body edits, or several frontmatter keys at once. Validates against
    PageFrontmatter. ``body`` is required when creating a new slug; on an
    existing page, omit ``body`` (or send null) to keep the on-disk Markdown.

    Frontmatter preservation: the AI's `write_content_file` tool is a
    *partial* writer — the model frequently sends only the fields it cares
    about (e.g. `{name, category, status}`) and omits optional fields that
    were already on disk (`hero_title`, `deck`, `trumpet`, `hero_image`,
    `date`, `author`, `main_image`, `tags`, etc.). Without a merge step,
    the write would silently destroy those fields, replacing the file's
    frontmatter with only what the model chose to send.

    To prevent that, we merge the incoming frontmatter over the page's
    existing on-disk frontmatter before constructing the Pydantic model.
    Incoming keys override existing ones (so the AI can still change any
    field); keys absent from the payload are preserved from disk. New
    pages (slug not found on disk) skip the merge and use the payload as-is.

    Scheduled publishing: set ``status`` to ``published`` and ``publish_at``
    to a future UTC ISO-8601 datetime (ending in ``Z``) to embargo the page
    from public listings until that instant. Omitted or past ``publish_at``
    means live immediately. Distinct from ``date`` (display/sort dateline).
    Status changes are gated by site ``ai_publish_autonomy`` settings.

    ``expected_version`` is an optional opaque token from a prior read
    (``version`` field). A mismatch raises 409 ``version_conflict`` unless
    ``force`` is true or ``PENCMS_STRICT_CONTENT_VERSION`` is disabled
    (soft ``version_warning``, write still applied). Omitted
    ``expected_version`` is an unconditional write.
    """
    from models.page import Page, PageFrontmatter, format_validation_error
    from pydantic import ValidationError
    import config as app_config

    site_id = resolve_mcp_site_id(request)
    language_config = get_site_language_config(site_id)
    try:
        requested_language = normalize_requested_language(language, language_config)
    except ContentI18nError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    tax_token = app_config.set_active_taxonomy(app_config.load_taxonomy_for_site(site_id))
    try:
        page_id = sanitize_slug(slug)
        if page_id.lower().strip() in ("undefined", "null", ""):
            raise HTTPException(
                status_code=400,
                detail="Invalid slug value: cannot be 'undefined', 'null', or empty."
            )
        if language_config.active:
            try:
                reject_spoofed_provenance(frontmatter)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        # Merge incoming frontmatter over the existing on-disk frontmatter so
        # partial writes don't destroy fields the model didn't mention. We read
        # the existing page (if any) and use its frontmatter dict as the base.
        existing_page = await read_page(
            page_id,
            include_partials=True,
            site_id=site_id,
            language=requested_language,
        )
        current_version = (
            await page_version_token(existing_page.file_path)
            if existing_page is not None
            else None
        )
        if existing_page is not None:
            merged_fm = {**existing_page.frontmatter, **frontmatter}
        else:
            merged_fm = dict(frontmatter)

        if body is None:
            if existing_page is None:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "body is required when creating a new page; omit it "
                        "only to keep an existing page's Markdown."
                    ),
                )
            body = existing_page.content

        from routers.pages import is_page_doc

        if existing_page is not None:
            if is_page_doc(merged_fm) != is_page_doc(existing_page):
                raise HTTPException(
                    status_code=403, detail="cannot_change_page_kind"
                )
            assert_mcp_capability(request, _content_write_cap(existing_page))
        else:
            assert_mcp_capability(request, _content_write_cap(merged_fm))

        version_warning = check_expected_version(
            expected_version,
            current_version,
            force=force,
        )

        # `read_page` returns enriched keys (`is_legacy`, etc.) that aren't valid
        # Pydantic inputs — strip known enrichment keys before constructing the
        # model so the merge doesn't trip the validator.
        for _enrichment_key in ("is_legacy",):
            merged_fm.pop(_enrichment_key, None)

        if "slug" not in merged_fm:
            merged_fm["slug"] = page_id

        # Normalize editor/public_url media paths to site-relative before
        # guardrails, soft warnings, and persist — so agents that round-trip
        # /api/assets/raw/... still land clean relative_path forms on disk.
        body = normalize_public_media_paths(body or "")
        if partials:
            partials = {
                k: normalize_public_media_paths(v) if isinstance(v, str) else v
                for k, v in partials.items()
            }
        merged_fm = _normalize_media_fields_in_frontmatter(merged_fm)

        # Load per-site AI settings guardrails
        import re

        ai_settings = load_ai_settings(site_id)

        publish_autonomy = ai_settings.get("ai_publish_autonomy", "require_approval")
        metadata_scope = ai_settings.get("ai_metadata_scope", "allow_metadata")
        prevent_empty_media = True

        # 1. Enforce publishing autonomy (same dial for i18n default language).
        existing_status = existing_page.frontmatter.get("status") if existing_page else "stub"
        new_status = merged_fm.get("status")
        try:
            enforce_publish_autonomy(
                existing_status=existing_status,
                new_status=new_status,
                autonomy=publish_autonomy,
            )
        except PublishAutonomyError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        clear_review_if_published(merged_fm)

        # 2. Enforce metadata scope
        if metadata_scope == "body_only":
            if existing_page:
                # Check if any values are changed in frontmatter (excluding legacy / helper fields)
                for k, v in merged_fm.items():
                    if k in ("is_legacy", "slug"):
                        continue
                    if existing_page.frontmatter.get(k) != v:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Permission Denied: AI is restricted to body-only edits and cannot modify frontmatter field '{k}'."
                        )
            else:
                # New page: only allow minimal fields like 'name' and 'slug'
                for k in merged_fm.keys():
                    if k not in ("name", "slug"):
                        raise HTTPException(
                            status_code=400,
                            detail="Permission Denied: AI is restricted to body-only edits and cannot set custom metadata for new pages."
                        )

        # 3. Enforce media path integrity
        if prevent_empty_media:
            if re.search(r'\[image[^\]]*src=(["\'])\s*\1', body) or re.search(r'\[image\s+[^\]]*src=\s*\]', body) or re.search(r'!\[.*?\]\(\s*\)', body):
                raise HTTPException(
                    status_code=400,
                    detail="Integrity Violation: Image source path cannot be empty. Ensure all [image src=\"...\"] shortcodes have a valid path. Use the relative_path returned by generate_media or list_media to verify correct paths."
                )

        media_path_warnings = await collect_media_path_warnings(
            site_id, body, merged_fm
        )

        effective_composite = (
            existing_page.composite
            if composite is None and existing_page is not None
            else bool(composite)
        )
        effective_partials = (
            existing_page.partials
            if partials is None and existing_page is not None
            else (partials or {})
        )
        if (
            language_config.active
            and requested_language == language_config.language
        ):
            actor = actor_context_from_state(request, site_id)
            merged_fm = stamp_actor_provenance(
                merged_fm,
                actor=actor,
                existing=(
                    existing_page.frontmatter if existing_page is not None else None
                ),
                run_id=run_id,
                require_agent_review=False,
            )
            clear_review_if_published(merged_fm)
        try:
            page_obj = Page(
                frontmatter=PageFrontmatter(**merged_fm),
                content=body,
                composite=effective_composite,
                partials=effective_partials,
            )
        except ValidationError as e:
            raise HTTPException(400, f"Schema validation failed: {format_validation_error(e)}")
        except Exception as e:
            raise HTTPException(400, f"Schema validation failed: {e}")
        if language_config.active and requested_language != language_config.language:
            try:
                written = await update_translation_sibling(
                    collection=merged_fm.get("category") or "general",
                    slug=page_id,
                    language=requested_language,
                    actor=actor_context_from_state(request, site_id),
                    frontmatter=frontmatter,
                    body=body,
                    composite=effective_composite,
                    partials=effective_partials,
                    run_id=run_id,
                )
            except TranslationNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except TranslationConflictError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            except TranslationAuthorizationError as exc:
                raise HTTPException(status_code=403, detail=str(exc)) from exc
            except (ContentI18nError, ValueError) as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        else:
            written = await write_page(
                page_obj,
                page_id=page_id,
                composite=effective_composite,
                partials=effective_partials,
                site_id=site_id,
                language=requested_language,
            )
        new_version = await page_version_token(written.file_path)
        response: Dict[str, Any] = {
            "slug": slug,
            "message": "Saved successfully",
            "version": new_version,
        }
        if language_config.active:
            response.update(
                {
                    "language": written.language,
                    "translation_group": written.translation_group,
                    "provenance": page_payload(written).get("provenance"),
                }
            )
        if version_warning:
            response["version_warning"] = version_warning
        if media_path_warnings:
            response["media_path_warnings"] = media_path_warnings
        response["public_path"] = public_path_if_live(site_id, page_id, merged_fm)
        return response
    finally:
        app_config.reset_active_taxonomy(tax_token)


@router.post(
    "/mcp/media",
    operation_id="write_media_file",
    dependencies=[Depends(require_scope("write:media"))],
)
async def write_media_file(
    request: Request,
    filename: str = Body(...),
    content_base64: str = Body(...),
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    """Upload a media file via base64-encoded content (scoped to agent site)."""
    from routers.assets import public_asset_url
    from services.site_service import join_site_assets_path

    site_id = resolve_mcp_site_id(request)
    content_bytes = base64.b64decode(content_base64)
    logical = sanitize_media_path(filename)
    storage_path = join_site_assets_path(site_id, logical)
    parent = "/".join(storage_path.split("/")[:-1])
    if content_storage is not None:
        if parent:
            await content_storage.mkdir(parent)
        await content_storage.write_bytes(storage_path, content_bytes)
    return {
        "filename": logical,
        "relative_path": logical,
        "use_for_embedding": logical,
        "public_url": public_asset_url(site_id, logical),
        "site_id": site_id,
    }


@router.post(
    "/mcp/posts",
    operation_id="create_post",
    dependencies=[Depends(require_scope("write:posts"))],
)
async def create_post(
    http_request: Request,
    name: str = Body(..., embed=True),
    category: Optional[str] = Body(default=None, embed=True),
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    """Create a new empty post as a stub (bootstrap, not a publish lock).

    Always writes ``status: stub`` with an empty body. Live publish is a later
    ``write_content_file`` / ``update_frontmatter_field`` on ``status``, gated by
    Settings → AI Publishing autonomy (``ai_publish_autonomy``). An empty stub
    cannot be created as ``published`` — required_fields apply once status leaves
    stub/draft.
    """
    import config
    from services.file_service import name_to_id, unique_post_slug
    from models.page import Page, PageFrontmatter, format_validation_error
    from pydantic import ValidationError

    site_id = resolve_mcp_site_id(http_request)
    tax_token = config.set_active_taxonomy(config.load_taxonomy_for_site(site_id))
    try:
        if not name or not name.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Post name cannot be empty."
            )

        slug = name_to_id(name)
        if not slug:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not derive a valid slug from post name '{name}'."
            )

        if slug.lower().strip() in ("undefined", "null", ""):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid slug derived: cannot be 'undefined', 'null', or empty."
            )

        slug = await unique_post_slug(site_id, slug)

        # Load per-site AI settings guardrails
        ai_settings = load_ai_settings(site_id)

        metadata_scope = ai_settings.get("ai_metadata_scope", "allow_metadata")
        if metadata_scope == "body_only" and category is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Permission Denied: AI is restricted to body-only edits and cannot set custom metadata (like category) for new pages."
            )

        # Resolve category default if not provided
        snap = config.get_active_taxonomy()
        primary_terms = snap.get("primary_terms") or []
        if not category or not category.strip():
            if primary_terms:
                category = primary_terms[0]
            else:
                category = "general"

        # Construct the Page
        fm_dict = {
            "name": name,
            "slug": slug,
            "category": category,
            "status": "stub",
            "published": False
        }

        try:
            page_obj = Page(
                frontmatter=PageFrontmatter(**fm_dict),
                content="",
                composite=False,
                partials={}
            )
        except ValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Schema validation failed: {format_validation_error(e)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Schema validation failed: {e}"
            )

        # Save to disk / cache
        await write_page(
            page_obj, page_id=slug, composite=False, partials={}, site_id=site_id
        )

        autonomy = ai_settings.get("ai_publish_autonomy", "require_approval") or "require_approval"
        next_step = (
            "Write the Markdown body and required frontmatter with write_content_file."
        )
        if autonomy == "autonomous":
            next_step += (
                " Then set status to published (this site allows autonomous publishing)."
            )
        elif autonomy == "restricted":
            next_step += (
                " Leave status as stub/draft; this site blocks AI from changing status."
            )
        else:
            next_step += (
                " Then set status to published only when autonomy is autonomous "
                "(this site is require_approval: publish attempts are downgraded)."
            )

        return {
            "slug": slug,
            "status": "stub",
            "published": False,
            "ai_publish_autonomy": autonomy,
            "next": next_step,
            "message": (
                f"Post '{name}' created successfully as a stub. "
                "Use write_content_file with this slug to add content."
            ),
            "category": category,
        }
    finally:
        config.reset_active_taxonomy(tax_token)




def match_heading(line: str, heading_path: str) -> bool:
    import re
    line_stripped = line.strip()
    h_stripped = heading_path.strip()
    
    # Direct match (case-insensitive)
    if line_stripped.lower() == h_stripped.lower():
        return True
        
    # Match heading title only
    match = re.match(r"^(#{1,6})\s+(.*)$", line_stripped)
    if match:
        title = match.group(2).strip()
        # Compare title case-insensitively
        if title.lower() == h_stripped.lower():
            return True
        # Also compare title if heading_path has leading hash
        h_match = re.match(r"^(#{1,6})\s+(.*)$", h_stripped)
        if h_match and title.lower() == h_match.group(2).strip().lower():
            return True
    return False


@router.post(
    "/mcp/pages/{slug}/split",
    operation_id="split_section",
    dependencies=[Depends(require_scope())],
)
async def split_section(
    slug: str,
    http_request: Request,
    source_slug: str = Body(..., embed=True),
    new_fragment_slug: str = Body(..., embed=True),
    split_marker: str = Body(None, embed=True),
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    """Split a heading section or arbitrary text into a new child fragment."""
    site_id = resolve_mcp_site_id(http_request)
    page_id = sanitize_slug(slug)
    page_data = await read_page(page_id, include_partials=True, site_id=site_id)
    if page_data is None:
        raise HTTPException(404, f"Page '{slug}' not found")
    assert_mcp_capability(http_request, _content_write_cap(page_data))

    new_frag_id = sanitize_slug(new_fragment_slug).lstrip("_")
    clean_source_slug = sanitize_slug(source_slug).lstrip("_")
    
    if page_data.composite and new_frag_id in (page_data.partials or {}):
        raise HTTPException(400, f"Fragment with ID '{new_frag_id}' already exists in this page")

    is_main = (clean_source_slug == "index" or clean_source_slug == "main")
    if is_main:
        target_content = page_data.content or ""
    else:
        partials = page_data.partials or {}
        if clean_source_slug not in partials:
            raise HTTPException(404, f"Source fragment '{clean_source_slug}' not found")
        target_content = partials[clean_source_slug] or ""

    def perform_split(text: str, marker: Optional[str]) -> tuple[str, str, str]:
        import re
        lines = text.replace("\r", "").split("\n")
        
        if not marker:
            # Automatic split by double newline
            empty_line_indices = [i for i, line in enumerate(lines) if not line.strip()]
            
            paragraphs = []
            current_p = []
            for line in lines:
                if not line.strip():
                    if current_p:
                        paragraphs.append(current_p)
                        current_p = []
                else:
                    current_p.append(line)
            if current_p:
                paragraphs.append(current_p)
                
            if len(paragraphs) == 2:
                split_idx = empty_line_indices[0] if empty_line_indices else -1
                if split_idx != -1:
                    rem_text = "\n".join(lines[:split_idx]).strip()
                    section_text = "\n".join(lines[split_idx+1:]).strip()
                    heading_title = new_frag_id.replace("-", " ").title()
                    return rem_text, heading_title, section_text
            
            raise HTTPException(400, f"Multiple paragraphs found in '{clean_source_slug}'. Please specify a `split_marker` to indicate exactly where to split, or ask the user.")

        # Check if marker matches a heading exactly
        start_idx = -1
        match_line = None
        is_heading = False
        
        for idx, line in enumerate(lines):
            if match_heading(line, marker):
                start_idx = idx
                match_line = line
                is_heading = True
                break
                
        if not is_heading:
            # Fallback to exact text match in line
            for idx, line in enumerate(lines):
                if marker.strip() in line:
                    start_idx = idx
                    is_heading = False
                    break
        
        if start_idx == -1:
            raise HTTPException(404, f"Split marker '{marker}' not found in '{clean_source_slug}'")
            
        if is_heading and match_line is not None:
            m = re.match(r"^(#{1,6})\s+(.*)$", match_line.strip())
            start_level = len(m.group(1)) if m else 1
            heading_title = m.group(2).strip() if m else marker
            
            end_idx = len(lines)
            for i in range(start_idx + 1, len(lines)):
                m_sub = re.match(r"^(#{1,6})\s+(.*)$", lines[i].strip())
                if m_sub:
                    level = len(m_sub.group(1))
                    if level <= start_level:
                        end_idx = i
                        break
                        
            section_text = "\n".join(lines[start_idx:end_idx]).strip()
            rem_lines = lines[:start_idx] + lines[end_idx:]
            rem_text = "\n".join(rem_lines).strip()
            return rem_text, heading_title, section_text
        else:
            # Split before the line containing the text marker
            heading_title = new_frag_id.replace("-", " ").title()
            rem_text = "\n".join(lines[:start_idx]).strip()
            section_text = "\n".join(lines[start_idx:]).strip()
            return rem_text, heading_title, section_text

    remaining_content, title, extracted_section = perform_split(target_content, split_marker)

    if is_main:
        page_data.content = remaining_content
    else:
        if page_data.partials is None:
            page_data.partials = {}
        page_data.partials[clean_source_slug] = remaining_content

    if not page_data.partials:
        page_data.partials = {}
    page_data.partials[new_frag_id] = extracted_section

    posts = page_data.frontmatter.get("posts", [])
    new_post = {
        "id": new_frag_id,
        "title": title,
        "content": f"_{new_frag_id}.md"
    }

    if not page_data.composite:
        posts = [
            {"id": "index", "title": page_data.frontmatter.get("title") or page_data.frontmatter.get("name") or "Index", "content": "index.md"},
            new_post
        ]
    else:
        if is_main:
            idx_pos = next((i for i, a in enumerate(posts) if a.get("id") == "index"), -1)
            if idx_pos == -1:
                posts.insert(0, new_post) # fallback
            else:
                posts.insert(idx_pos + 1, new_post)
        else:
            parent_pos = next((i for i, a in enumerate(posts) if a.get("id") == clean_source_slug), -1)
            if parent_pos != -1:
                posts.insert(parent_pos + 1, new_post)
            else:
                posts.append(new_post)

    page_data.frontmatter["posts"] = posts
    page_data.frontmatter["composite"] = True
    page_data.composite = True

    from models.page import Page, PageFrontmatter
    for _enrichment_key in ("is_legacy",):
        page_data.frontmatter.pop(_enrichment_key, None)

    await write_page(
        page=Page(
            frontmatter=PageFrontmatter(**page_data.frontmatter),
            content=page_data.content,
            composite=True,
            partials=page_data.partials,
        ),
        page_id=page_id,
        composite=True,
        partials=page_data.partials,
        site_id=site_id,
    )

    return {"slug": slug, "message": "Section split successfully", "new_fragment_slug": new_frag_id}


@router.post(
    "/mcp/pages/{slug}/merge",
    operation_id="merge_sections",
    dependencies=[Depends(require_scope())],
)
async def merge_sections(
    slug: str,
    http_request: Request,
    fragment_slugs: List[str] = Body(..., embed=True),
    into_slug: str = Body(..., embed=True),
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    """Merge one or more fragments into a target fragment or 'index'."""
    site_id = resolve_mcp_site_id(http_request)
    page_id = sanitize_slug(slug)
    page_data = await read_page(page_id, include_partials=True, site_id=site_id)
    if page_data is None:
        raise HTTPException(404, f"Page '{slug}' not found")
    assert_mcp_capability(http_request, _content_write_cap(page_data))

    if not page_data.composite:
        raise HTTPException(400, f"Page '{slug}' is not a composite page; cannot merge sections.")

    clean_frag_slugs = [sanitize_slug(s).lstrip("_") for s in fragment_slugs]
    clean_into_slug = sanitize_slug(into_slug).lstrip("_")

    for fs in clean_frag_slugs:
        if fs not in (page_data.partials or {}):
            raise HTTPException(400, f"Fragment '{fs}' not found in this page")

    if clean_into_slug != "index" and clean_into_slug not in (page_data.partials or {}):
        raise HTTPException(400, f"Target fragment '{into_slug}' not found in this page")

    merge_content_parts = []
    partials = page_data.partials if page_data.partials is not None else {}
    for fs in clean_frag_slugs:
        content = partials.get(fs, "").strip()
        if content:
            merge_content_parts.append(content)
        partials.pop(fs, None)

    merged_text = "\n\n" + "\n\n".join(merge_content_parts) if merge_content_parts else ""

    if clean_into_slug == "index":
        page_data.content = (page_data.content or "").strip() + merged_text
    else:
        partials[clean_into_slug] = (partials.get(clean_into_slug, "") or "").strip() + merged_text
    page_data.partials = partials

    posts = page_data.frontmatter.get("posts", [])
    updated_posts = [a for a in posts if a.get("id") not in clean_frag_slugs]
    page_data.frontmatter["posts"] = updated_posts

    is_still_composite = len([a for a in updated_posts if a.get("id") != "index"]) > 0
    if not is_still_composite:
        page_data.frontmatter.pop("posts", None)
        page_data.frontmatter.pop("composite", None)
        page_data.composite = False
    else:
        page_data.frontmatter["composite"] = True
        page_data.composite = True

    from models.page import Page, PageFrontmatter
    for _enrichment_key in ("is_legacy",):
        page_data.frontmatter.pop(_enrichment_key, None)

    await write_page(
        page=Page(
            frontmatter=PageFrontmatter(**page_data.frontmatter),
            content=page_data.content,
            composite=page_data.composite,
            partials=page_data.partials if page_data.composite else {},
        ),
        page_id=page_id,
        composite=page_data.composite,
        partials=page_data.partials if page_data.composite else {},
        site_id=site_id,
    )

    return {
        "slug": slug,
        "message": f"Merged fragments {fragment_slugs} into '{into_slug}' successfully",
        "composite": page_data.composite
    }


@router.post(
    "/mcp/pages/{slug}/move",
    operation_id="move_section",
    dependencies=[Depends(require_scope())],
)
async def move_section(
    slug: str,
    http_request: Request,
    heading_path: str = Body(..., embed=True),
    before_or_after: str = Body(..., embed=True),
    target_heading_path: str = Body(..., embed=True),
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    """Reorder sections within a composite document."""
    site_id = resolve_mcp_site_id(http_request)
    page_id = sanitize_slug(slug)
    page_data = await read_page(page_id, include_partials=True, site_id=site_id)
    if page_data is None:
        raise HTTPException(404, f"Page '{slug}' not found")
    assert_mcp_capability(http_request, _content_write_cap(page_data))

    if not page_data.composite:
        raise HTTPException(400, f"Page '{slug}' is not a composite page; cannot move sections.")

    posts = page_data.frontmatter.get("posts", [])
    if not posts:
        raise HTTPException(400, f"No posts found in composite page '{slug}'")

    def find_post_id(ref: str) -> Optional[str]:
        ref_clean = ref.strip().lower().lstrip("_")
        for a in posts:
            if a.get("id", "").lower() == ref_clean:
                return a["id"]
        for a in posts:
            if a.get("title", "").strip().lower() == ref_clean:
                return a["id"]
        import re
        ref_title = re.sub(r"^#{1,6}\s+", "", ref_clean).strip()
        for a in posts:
            if a.get("title", "").strip().lower() == ref_title:
                return a["id"]
            content_slug = a.get("content", "").replace(".md", "").lstrip("_").lower()
            if content_slug == ref_title:
                return a["id"]
        return None

    source_id = find_post_id(heading_path)
    target_id = find_post_id(target_heading_path)

    if not source_id:
        raise HTTPException(400, f"Section to move '{heading_path}' not found")
    if not target_id:
        raise HTTPException(400, f"Target section '{target_heading_path}' not found")

    if source_id == "index":
        raise HTTPException(400, "The main index section ('index') cannot be moved")
    if before_or_after == "before" and target_id == "index":
        raise HTTPException(400, "Cannot place a section before the main index section ('index')")

    if source_id == target_id:
        return {"slug": slug, "message": "Source and target sections are the same; no move needed"}

    source_post = next((a for a in posts if a.get("id") == source_id), None)
    new_posts = [a for a in posts if a.get("id") != source_id]
    
    target_idx = next((i for i, a in enumerate(new_posts) if a.get("id") == target_id), -1)
    if target_idx == -1:
        raise HTTPException(400, "Target section index error")

    if before_or_after == "before":
        new_posts.insert(target_idx, source_post)
    elif before_or_after == "after":
        new_posts.insert(target_idx + 1, source_post)
    else:
        raise HTTPException(400, "before_or_after must be either 'before' or 'after'")

    page_data.frontmatter["posts"] = new_posts

    from models.page import Page, PageFrontmatter
    for _enrichment_key in ("is_legacy",):
        page_data.frontmatter.pop(_enrichment_key, None)

    await write_page(
        page=Page(
            frontmatter=PageFrontmatter(**page_data.frontmatter),
            content=page_data.content,
            composite=True,
            partials=page_data.partials,
        ),
        page_id=page_id,
        composite=True,
        partials=page_data.partials,
        site_id=site_id,
    )

    return {
        "slug": slug,
        "message": f"Moved section '{source_id}' {before_or_after} '{target_id}' successfully"
    }


# --- Git integration tools ---

class PublishRequest(BaseModel):
    message: str
    paths: Optional[List[str]] = None
    push: bool = False
    dry_run: bool = False

PUSH_TASKS: Dict[str, Dict[str, Any]] = {}

def _run_git_command(args: List[str]) -> tuple[int, str, str]:
    """Run a git command in the content directory root."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=str(CONTENT_DIR_PATH),
            capture_output=True,
            text=True,
            check=False
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, "", str(e)

def _background_git_push(task_id: str):
    """Background task to push changes to remote."""
    rc, stdout, stderr = _run_git_command(["push"])
    if rc == 0:
        PUSH_TASKS[task_id] = {"status": "success"}
    else:
        PUSH_TASKS[task_id] = {"status": "error", "error": stderr.strip() or stdout.strip()}

@router.post(
    "/mcp/publish",
    operation_id="commit_and_push",
    dependencies=[Depends(require_scope("write"))],
)
async def commit_and_push(
    request: PublishRequest,
    http_request: Request,
    background_tasks: BackgroundTasks,
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    """Stage, commit, and optionally push changes to git."""
    from services.site_service import get_site_content_prefix

    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Commit message cannot be empty")

    site_id = resolve_mcp_site_id(http_request)
    site_prefix = get_site_content_prefix(site_id)

    # Stage files — default to this site's tree; reject paths outside it.
    if request.paths:
        paths_to_stage = []
        for p in request.paths:
            clean = p.replace("\\", "/").lstrip("./")
            if clean in (".", ""):
                paths_to_stage.append(site_prefix)
                continue
            if not (clean == site_prefix or clean.startswith(site_prefix + "/")):
                raise HTTPException(
                    status_code=403,
                    detail=f"Path '{p}' is outside site '{site_id}' content root",
                )
            paths_to_stage.append(clean)
    else:
        paths_to_stage = [site_prefix]
    rc, stdout, stderr = _run_git_command(["add"] + paths_to_stage)
    if rc != 0:
        raise HTTPException(status_code=500, detail=f"Failed to stage files: {stderr}")

    if request.dry_run:
        # Return the diff of staged changes
        rc, diff_out, diff_err = _run_git_command(["diff", "--staged"])
        return {
            "status": "dry_run",
            "message": request.message,
            "diff": diff_out
        }

    # Commit
    rc, out, err = _run_git_command(["commit", "-m", request.message])
    if rc != 0:
        # If nothing to commit, return gracefully or error.
        # "nothing to commit, working tree clean"
        if "nothing to commit" in out or "nothing to commit" in err:
            raise HTTPException(status_code=400, detail="Nothing to commit")
        raise HTTPException(status_code=500, detail=f"Failed to commit: {err or out}")

    # Get the commit SHA
    rc, sha_out, _ = _run_git_command(["rev-parse", "HEAD"])
    sha = sha_out.strip() if rc == 0 else "unknown"

    if request.push:
        task_id = str(uuid.uuid4())
        PUSH_TASKS[task_id] = {"status": "running"}
        background_tasks.add_task(_background_git_push, task_id)
        return {
            "status": "pushing",
            "sha": sha,
            "task_id": task_id
        }

    return {
        "status": "success",
        "sha": sha
    }

@router.get(
    "/mcp/publish/{task_id}",
    operation_id="get_publish_status",
    dependencies=[Depends(require_scope("read"))],
)
async def get_publish_status(
    task_id: str,
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    """Check the status of a background git push."""
    if task_id not in PUSH_TASKS:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = PUSH_TASKS[task_id]
    if task["status"] in ["success", "error"]:
        # Pop it to avoid memory leak if we wanted to, but let's keep it simple
        pass
    
    return task


# --- Host deploy (scope: publish) — distinct from git commit_and_push ---


@router.post(
    "/mcp/publish_site",
    operation_id="publish_site",
    dependencies=[Depends(require_scope("publish"))],
)
async def publish_site(
    http_request: Request,
    background_tasks: BackgroundTasks,
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    """Build and deploy this site's static dist/ to the configured publish host.

    Requires agent scope ``publish`` and an enrolled Deploy Grant. Never returns
    host passwords. Distinct from ``commit_and_push`` (git content push).
    """
    from routers.publish import start_publish_run
    from services.auth_service import decode_access_token
    import jwt as pyjwt

    site_id = resolve_mcp_site_id(http_request)

    token = None
    auth = http_request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1]
    if not token:
        token = http_request.cookies.get("pen_jwt")
    is_agent = False
    agent_site_id = None
    agent_scopes = None
    if token:
        try:
            peek = decode_access_token(token)
            if peek.get("type") == "agent":
                is_agent = True
                agent_site_id = peek.get("site_id") or site_id
                agent_scopes = peek.get("scopes") or []
        except pyjwt.PyJWTError:
            pass

    return start_publish_run(
        site_id,
        background_tasks,
        is_agent=is_agent,
        body_password=None,
        agent_site_id=agent_site_id,
        agent_scopes=agent_scopes,
    )


@router.get(
    "/mcp/publish_site/status",
    operation_id="get_publish_site_status",
    dependencies=[Depends(require_scope("publish"))],
)
async def get_publish_site_status(
    http_request: Request,
    task_id: Optional[str] = None,
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    """Poll a host-deploy publish run for this site (never returns secrets)."""
    from services.publish_deploy import get_run_status
    from services.site_service import get_publish_target

    site_id = resolve_mcp_site_id(http_request)
    try:
        target = get_publish_target(site_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    run = get_run_status(site_id, task_id=task_id)
    if run is None:
        if task_id:
            raise HTTPException(status_code=404, detail="Task not found")
        return {
            "site_id": site_id,
            "status": "idle",
            "phase": None,
            "task_id": None,
            "error": None,
            "log": [],
            "last_published_at": target.get("last_published_at"),
            "last_status": target.get("last_status"),
        }
    return {
        "site_id": run.get("site_id", site_id),
        "status": run.get("status"),
        "phase": run.get("phase"),
        "task_id": run.get("task_id"),
        "started_at": run.get("started_at"),
        "finished_at": run.get("finished_at"),
        "error": run.get("error"),
        "log": run.get("log") or [],
        "last_published_at": target.get("last_published_at"),
        "last_status": target.get("last_status"),
    }


class GenerateMediaRequest(BaseModel):
    prompt: str
    filename: str
    preset: Optional[str] = None
    alt_text: Optional[str] = None

@router.post(
    "/mcp/media/generate",
    operation_id="generate_media",
    dependencies=[Depends(require_scope("write:media"))],
)
async def generate_media(
    request: GenerateMediaRequest,
    http_request: Request,
    current_user: UserPublic = Depends(get_current_user),
    x_pen_ai_image_key: Optional[str] = Header(None, alias="X-Pen-AI-Image-Key"),
    x_pen_ai_image_base_url: Optional[str] = Header(None, alias="X-Pen-AI-Image-Base-URL"),
    x_pen_ai_image_model: Optional[str] = Header(None, alias="X-Pen-AI-Image-Model"),
) -> Dict[str, Any]:
    """Generate an image via provider and store it (scoped to agent site)."""
    from routers.assets import public_asset_url
    from services.site_service import join_site_assets_path

    site_id = resolve_mcp_site_id(http_request)
    base_url = x_pen_ai_image_base_url
    if not base_url:
        raise HTTPException(status_code=400, detail="Image generation base URL not configured.")
        
    if not is_valid_url(base_url):
        raise HTTPException(status_code=400, detail="Invalid or restricted image base URL.")

    # Resolve the target endpoint URL (matching ai_proxy.py logic)
    if base_url.endswith("/images") or base_url.endswith("/images/generations"):
        endpoint = base_url
    else:
        endpoint = f"{base_url.rstrip('/')}/images/generations"

    # Load per-site AI settings for add-on image prompt
    image_prompt = load_ai_settings(site_id).get("image_generation_prompt", "") or ""

    final_prompt = request.prompt
    if image_prompt and image_prompt.strip():
        if final_prompt:
            final_prompt = f"{final_prompt}, {image_prompt.strip()}"
        else:
            final_prompt = image_prompt.strip()

    payload = {
        "prompt": final_prompt,
        "model": x_pen_ai_image_model or "dall-e-3",
        "response_format": "b64_json"
    }

    # Handle Plan A vs Plan B for Nano-GPT compatibility
    if not endpoint.endswith("/images/generations"):
        payload["resolution"] = "1024x1024"
    else:
        payload["size"] = "1024x1024"

    headers = {"Content-Type": "application/json"}
    if x_pen_ai_image_key:
        if "nano-gpt.com" in base_url and "/api/v1/" in base_url:
            headers["x-api-key"] = x_pen_ai_image_key
        else:
            headers["Authorization"] = f"Bearer {x_pen_ai_image_key}"

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(endpoint, json=payload, headers=headers)
            if resp.status_code != 200:
                err_detail = resp.text
                try:
                    err_json = resp.json()
                    err_detail = err_json.get("error", {}).get("message", err_detail)
                except Exception:
                    pass
                # Always return 502 for upstream errors so the frontend doesn't confuse a 404 from upstream with a missing local endpoint
                raise HTTPException(status_code=502, detail=f"Image generation failed upstream: {err_detail} (URL: {endpoint})")
            
            data = resp.json()
            
            if "data" not in data or len(data["data"]) == 0 or "b64_json" not in data["data"][0]:
                raise HTTPException(status_code=500, detail="Invalid response format from image provider.")
            
            b64_img = data["data"][0]["b64_json"]
            image_data = base64.b64decode(b64_img)

            logical = sanitize_media_path(request.filename)
            storage_path = join_site_assets_path(site_id, logical)
            parent = "/".join(storage_path.split("/")[:-1])
            if content_storage is not None:
                if parent:
                    await content_storage.mkdir(parent)
                await content_storage.write_bytes(storage_path, image_data)

            public_url = public_asset_url(site_id, logical)

            return {
                "status": "success",
                "relative_path": logical,
                "use_for_embedding": logical,
                "public_url": public_url,
                "site_id": site_id,
                "message": (
                    f"Saved {logical}. Use relative_path "
                    f"(or use_for_embedding) in shortcodes and frontmatter — "
                    f"do not invent filenames. public_url is for chat preview only."
                ),
            }
            
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Error connecting to image provider: {str(e)}")
