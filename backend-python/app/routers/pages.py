from fastapi import APIRouter, HTTPException, Query, Depends, Request
from pydantic import ValidationError
from typing import Any, Optional
from routers.auth import get_current_user, get_optional_user, UserPublic

from models.page import Page, PageFrontmatter, PageResponse, format_validation_error
from services.authz import assert_capability, require_capability
from services.concurrency import check_expected_version, page_version_token
from services.file_service import (
    write_page,
    read_page,
    delete_page,
    list_pages,
    name_to_id,
    sanitize_slug,
    resolve_path,
)
from services.site_service import apply_human_site_taxonomy, resolve_human_site_id
from services.i18n_service import ContentI18nError
from services.file_service import get_site_language_config
from services.i18n_service import normalize_requested_language
from services.translation_service import (
    ActorContext,
    SERVER_PROVENANCE_FIELDS,
    TranslationConflictError,
    TranslationNotFoundError,
    create_translation_sibling,
    delete_translation_sibling,
    reject_spoofed_provenance,
    review_translation_sibling,
    stamp_actor_provenance,
    update_translation_sibling,
)

router = APIRouter(prefix="/pages", tags=["pages"])


def is_page_doc(frontmatter_or_page: Any) -> bool:
    """True when frontmatter `page` is True or the string \"true\".

    Matches PageFrontmatter and file_service enrichment. Accepts a Page,
    PageResponse, PageFrontmatter, or a frontmatter dict.
    """
    if frontmatter_or_page is None:
        return False
    fm = frontmatter_or_page
    nested = getattr(frontmatter_or_page, "frontmatter", None)
    if nested is not None and not isinstance(frontmatter_or_page, dict):
        fm = nested
    if isinstance(fm, dict):
        return fm.get("page") in (True, "true")
    return getattr(fm, "page", False) in (True, "true")


def _write_cap(frontmatter_or_page: Any) -> str:
    return "write:pages" if is_page_doc(frontmatter_or_page) else "write:posts"


def _delete_cap(frontmatter_or_page: Any) -> str:
    return "delete:pages" if is_page_doc(frontmatter_or_page) else "delete:posts"


def _require_human_request(request: Request) -> None:
    from services.auth_service import decode_access_token

    token = None
    authorization = request.headers.get("Authorization")
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
    if not token:
        token = request.cookies.get("pen_jwt")
    if token:
        try:
            if decode_access_token(token).get("type") == "agent":
                raise HTTPException(
                    status_code=403,
                    detail="Human admin session required for /api/pages mutations",
                )
        except HTTPException:
            raise
        except Exception:
            pass


def resolve_page_site_id(request: Request) -> str:
    """Honor JWT site binding for agents; humans/public use site preference."""
    from services.auth_service import decode_access_token, decode_agent_token
    from services.site_service import get_site

    token = None
    authorization = request.headers.get("Authorization")
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
    if not token:
        token = request.cookies.get("pen_jwt")
    if token:
        try:
            peek = decode_access_token(token)
            if peek.get("type") == "agent":
                payload = decode_agent_token(token)
                site_id = payload.get("site_id")
                if not site_id or get_site(site_id) is None:
                    raise HTTPException(
                        status_code=403,
                        detail="Agent token has no valid site binding",
                    )
                return site_id
        except HTTPException:
            raise
        except Exception:
            pass
    return resolve_human_site_id(request)


# --- Create or update a page ---

@router.post("/", response_model=PageResponse, response_model_exclude_none=True, status_code=201)
async def create_page(
    page: Page,
    request: Request,
    language: Optional[str] = Query(
        None, description="Exact configured language. Omitted means the site default."
    ),
    current_user: UserPublic = Depends(get_current_user),
    site_id: str = Depends(apply_human_site_taxonomy),
):
    """Create a new page. Fails if the page already exists."""
    _require_human_request(request)
    assert_capability(request, _write_cap(page), site_id=site_id)
    # Prefer explicit slug from client; fall back to auto-generated from name
    if page.slug:
        page_id = sanitize_slug(page.slug)
    else:
        page_id = name_to_id(page.frontmatter.name)

    if page_id.lower().strip() in ("undefined", "null", ""):
        raise HTTPException(
            status_code=400,
            detail="Invalid page ID: cannot be 'undefined', 'null', or empty."
        )
    page.frontmatter.slug = page_id

    config = get_site_language_config(site_id)
    try:
        requested_language = normalize_requested_language(language, config)
        if config.active:
            reject_spoofed_provenance(
                page.frontmatter.model_dump(exclude_unset=True)
            )
    except (ContentI18nError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if config.active and requested_language != config.language:
        try:
            return await create_translation_sibling(
                collection=page.frontmatter.category or "general",
                slug=page_id,
                language=requested_language,
                actor=ActorContext("human", current_user.username, site_id),
                frontmatter=page.frontmatter.model_dump(
                    exclude=SERVER_PROVENANCE_FIELDS, exclude_none=True
                ),
                body=page.content or "",
                composite=page.composite,
                partials=page.partials,
            )
        except TranslationConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (TranslationNotFoundError, ContentI18nError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    existing_path = await resolve_path(
        page_id, site_id=site_id, language=requested_language
    )

    if existing_path:
        raise HTTPException(
            status_code=409,
            detail=f"Page '{page_id}' already exists. Use PUT to update."
        )

    stamped_page = page
    if config.active:
        metadata = stamp_actor_provenance(
            page.frontmatter.model_dump(exclude_none=True),
            actor=ActorContext("human", current_user.username, site_id),
        )
        stamped_page = Page(
            frontmatter=PageFrontmatter(**metadata),
            content=page.content,
            composite=page.composite,
            partials=page.partials,
        )
    return await write_page(
        stamped_page,
        page_id=page_id,
        composite=bool(page.composite),
        partials=page.partials or {},
        site_id=site_id,
        language=requested_language,
    )


@router.put("/{page_id}", response_model=PageResponse, response_model_exclude_none=True)
async def update_page(
    page_id: str,
    page: Page,
    request: Request,
    language: Optional[str] = Query(
        None, description="Exact configured language. Omitted means the site default."
    ),
    current_user: UserPublic = Depends(get_current_user),
    site_id: str = Depends(apply_human_site_taxonomy),
):
    """Update an existing page. Fails if the page does not exist."""
    _require_human_request(request)
    if page_id.lower().strip() in ("undefined", "null", ""):
        raise HTTPException(
            status_code=400,
            detail="Invalid page ID: cannot be 'undefined', 'null', or empty."
        )
    page.frontmatter.slug = page_id

    config = get_site_language_config(site_id)
    try:
        requested_language = normalize_requested_language(language, config)
        if config.active:
            reject_spoofed_provenance(
                page.frontmatter.model_dump(exclude_unset=True)
            )
    except (ContentI18nError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    existing_path = await resolve_path(
        page_id, site_id=site_id, language=requested_language
    )

    if not existing_path:
        raise HTTPException(
            status_code=404,
            detail=f"Page '{page_id}' not found. Use POST to create."
        )

    existing_page = await read_page(
        page_id,
        include_partials=True,
        site_id=site_id,
        language=requested_language,
    )
    if existing_page is None:
        raise HTTPException(status_code=404, detail=f"Page '{page_id}' not found.")
    if is_page_doc(page) != is_page_doc(existing_page):
        raise HTTPException(status_code=403, detail="cannot_change_page_kind")
    assert_capability(request, _write_cap(existing_page), site_id=site_id)

    version_warning = check_expected_version(
        page.expected_version,
        await page_version_token(existing_page.file_path),
        force=bool(page.force),
    )

    if config.active and requested_language != config.language:
        try:
            result = await update_translation_sibling(
                collection=page.frontmatter.category or "general",
                slug=page_id,
                language=requested_language,
                actor=ActorContext("human", current_user.username, site_id),
                frontmatter=page.frontmatter.model_dump(
                    exclude=SERVER_PROVENANCE_FIELDS, exclude_none=True
                ),
                body=page.content or "",
                composite=page.composite,
                partials=page.partials,
            )
        except (TranslationNotFoundError, ContentI18nError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if version_warning:
            result.version_warning = version_warning
        return result
    stamped_page = page
    if config.active:
        metadata = stamp_actor_provenance(
            page.frontmatter.model_dump(exclude_none=True),
            actor=ActorContext("human", current_user.username, site_id),
            existing=existing_page.frontmatter,
        )
        stamped_page = Page(
            frontmatter=PageFrontmatter(**metadata),
            content=page.content,
            composite=page.composite,
            partials=page.partials,
        )
    result = await write_page(
        stamped_page,
        page_id=page_id,
        composite=(
            existing_page.composite
            if page.composite is None
            else bool(page.composite)
        ),
        partials=(
            existing_page.partials
            if page.partials is None
            else page.partials
        ),
        site_id=site_id,
        language=requested_language,
    )
    if version_warning:
        result.version_warning = version_warning
    return result


# --- Read a single page ---

@router.get("/{page_id}", response_model=PageResponse, response_model_exclude_none=True)
async def get_page(
    page_id: str,
    include_partials: bool = Query(False, description="Include narrative partials for composite pages"),
    language: Optional[str] = Query(
        None,
        description="Exact configured language. Omitted means the site default.",
    ),
    live_only: bool = Query(
        False,
        description=(
            "When true, require the exact page to be public now. "
            "Translated details also require a live default-language peer."
        ),
    ),
    current_user: Optional[UserPublic] = Depends(get_optional_user),
    site_id: str = Depends(resolve_page_site_id),
):
    """Read a single page by ID."""
    try:
        page = await read_page(
            page_id,
            include_partials=include_partials,
            site_id=site_id,
            language=language,
            translations_live_only=current_user is None,
            public_only=live_only,
        )
    except ContentI18nError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not page:
        raise HTTPException(
            status_code=404,
            detail=f"Page '{page_id}' not found."
        )

    return page


# --- Delete a page ---

@router.delete("/{page_id}", status_code=204)
async def remove_page(
    page_id: str,
    request: Request,
    language: Optional[str] = Query(
        None, description="Exact configured language. Omitted means the site default."
    ),
    delete_group: bool = Query(
        False,
        description="Delete the default document and every translation sibling.",
    ),
    current_user: UserPublic = Depends(get_current_user),
    site_id: str = Depends(resolve_page_site_id),
):
    """Delete a page. Returns 204 on success, 404 if not found."""
    _require_human_request(request)
    config = get_site_language_config(site_id)
    try:
        requested_language = normalize_requested_language(language, config)
        existing = await read_page(
            page_id,
            site_id=site_id,
            language=requested_language,
        )
        if not existing:
            raise HTTPException(
                status_code=404,
                detail=f"Page '{page_id}' not found."
            )
        assert_capability(request, _delete_cap(existing), site_id=site_id)
        if config.active and requested_language != config.language:
            deleted = await delete_translation_sibling(
                collection="general",
                slug=page_id,
                language=requested_language,
                actor=ActorContext("human", current_user.username, site_id),
            )
        else:
            deleted = await delete_page(
                page_id,
                site_id=site_id,
                language=requested_language,
                delete_group=delete_group,
            )
    except TranslationConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ContentI18nError as exc:
        code = 409 if "siblings" in str(exc).lower() else 400
        raise HTTPException(status_code=code, detail=str(exc)) from exc

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Page '{page_id}' not found."
        )


# --- List pages with filters ---

@router.get("/", response_model=list[PageResponse], response_model_exclude_none=True)
async def get_pages(
    category: Optional[str] = Query(None, description="Filter by category"),
    status: Optional[str] = Query(None, description="Filter by status"),
    domain: Optional[str] = Query(None, description="Filter by domain"),
    needs_review: Optional[bool] = Query(None, description="Filter by review flag"),
    published: Optional[bool] = Query(None, description="Filter by published flag"),
    live_only: Optional[bool] = Query(
        None,
        description=(
            "When true, return only publicly listable pages "
            "(status=published and publish_at null or past). "
            "Defaults to true for unauthenticated callers."
        ),
    ),
    due_within_hours: Optional[int] = Query(
        None,
        description=(
            "When set, return published pages whose publish_at fell within "
            "the last N hours (for static rebuild-due)."
        ),
        ge=1,
    ),
    language: Optional[str] = Query(
        None,
        description="Configured language. Omitted means the site default.",
    ),
    fallback: str = Query(
        "none",
        pattern="^(none|default)$",
        description="Use default-language rows for missing live siblings when set to default.",
    ),
    current_user: Optional[UserPublic] = Depends(get_optional_user),
    site_id: str = Depends(resolve_page_site_id),
):
    """List all pages. Supports filtering by category, status, domain,
    needs_review, published, live_only, and due_within_hours.

    Examples:
      GET /pages?status=draft
      GET /pages?category=person&published=false
      GET /pages?needs_review=true
      GET /pages?status=published&live_only=true
    """
    # Unauthenticated public/preview callers get live-only by default so
    # scheduled (future publish_at) posts stay out of listings. Authenticated
    # admin callers see the full set unless they opt into live_only.
    effective_live_only = live_only if live_only is not None else (current_user is None)
    try:
        return await list_pages(
            category=category,
            status=status,
            domain=domain,
            needs_review=needs_review,
            published=published,
            site_id=site_id,
            live_only=effective_live_only,
            due_within_hours=due_within_hours,
            language=language,
            fallback=fallback,
            translations_live_only=current_user is None,
        )
    except ContentI18nError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# --- Approve a draft page ---

@router.patch("/{page_id}/approve", response_model=PageResponse, response_model_exclude_none=True)
async def approve_page(
    page_id: str,
    request: Request,
    language: Optional[str] = Query(
        None, description="Exact configured language. Omitted means the site default."
    ),
    current_user: UserPublic = Depends(require_capability("publish:content")),
    site_id: str = Depends(apply_human_site_taxonomy),
):
    """Promote a draft or stub page to published.

    One decision: Approve means live. Removes needs_review. Schema validation
    is enforced on approval — a stub cannot be approved until required fields
    are present.
    """
    _require_human_request(request)
    config = get_site_language_config(site_id)
    requested_language = normalize_requested_language(language, config)
    if config.active and requested_language != config.language:
        try:
            return await review_translation_sibling(
                slug=page_id,
                language=requested_language,
                actor=ActorContext("human", current_user.username, site_id),
                decision="approve",
            )
        except TranslationNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except TranslationConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    existing = await read_page(
        page_id,
        include_partials=True,
        site_id=site_id,
        language=requested_language,
    )

    if not existing:
        raise HTTPException(
            status_code=404,
            detail=f"Page '{page_id}' not found."
        )

    fm = existing.frontmatter

    if fm.get("status") not in ("stub", "draft"):
        raise HTTPException(
            status_code=400,
            detail=f"Page '{page_id}' has status '{fm.get('status')}' "
                   f"and does not need approval."
        )

    # Promote status
    fm["status"] = "published"
    fm["published"] = True
    fm["needs_review"] = False

    # Rebuild and validate the page — this enforces required fields
    try:
        updated_page = Page(
            frontmatter=PageFrontmatter(**fm),
            content=existing.content,
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot approve — schema validation failed: {format_validation_error(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot approve — schema validation failed: {str(e)}"
        )

    return await write_page(
        updated_page,
        page_id=page_id,
        composite=existing.composite,
        partials=existing.partials,
        site_id=site_id,
        language=requested_language,
    )


# --- Publish a page ---

@router.patch("/{page_id}/publish", response_model=PageResponse, response_model_exclude_none=True)
async def publish_page(
    page_id: str,
    request: Request,
    language: Optional[str] = Query(
        None, description="Exact configured language. Omitted means the site default."
    ),
    current_user: UserPublic = Depends(require_capability("publish:content")),
    site_id: str = Depends(apply_human_site_taxonomy),
):
    """Set published: true on an unpublished page.
    Only unpublished pages can be published directly.
    """
    _require_human_request(request)
    config = get_site_language_config(site_id)
    requested_language = normalize_requested_language(language, config)
    existing = await read_page(
        page_id,
        include_partials=True,
        site_id=site_id,
        language=requested_language,
    )

    if not existing:
        raise HTTPException(
            status_code=404,
            detail=f"Page '{page_id}' not found."
        )

    fm = existing.frontmatter

    if fm.get("status") != "unpublished":
        raise HTTPException(
            status_code=400,
            detail=f"Page '{page_id}' must be 'unpublished' before publishing. "
                   f"Current status: '{fm.get('status')}'."
        )

    fm["published"] = True
    fm["status"] = "published"

    updated_page = Page(
        frontmatter=PageFrontmatter(**fm),
        content=existing.content,
    )

    return await write_page(
        updated_page,
        page_id=page_id,
        composite=existing.composite,
        partials=existing.partials,
        site_id=site_id,
        language=requested_language,
    )
