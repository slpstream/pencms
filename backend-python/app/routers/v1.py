import os
import yaml
import base64
import time
import json
import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Header, Query, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from models.user import User
from models.page import Page, PageFrontmatter, format_validation_error
from services.user_service import USERS_DIR, get_user_by_uuid
from services.auth_service import verify_password, decode_access_token
from services.authz import assert_capability, expand_capabilities
from services.concurrency import check_expected_version, page_version_token
from services.file_service import (
    get_site_language_config,
    read_page,
    translation_peer_summaries,
    write_page,
    delete_page,
)
from services.i18n_service import (
    ContentI18nError,
    normalize_requested_language,
)
from services.publish_autonomy import (
    PublishAutonomyError,
    autonomy_for_site,
    clear_review_if_published,
    enforce_publish_autonomy,
)
from services.translation_service import (
    TranslationAuthorizationError,
    TranslationConflictError,
    TranslationNotFoundError,
    actor_context_from_state,
    content_provenance,
    create_translation_sibling,
    delete_translation_sibling,
    page_payload,
    reject_spoofed_provenance,
    stamp_actor_provenance,
    update_translation_sibling,
)
from services.cache_service import query_entries, get_entry, get_collections_list
from services.site_service import resolve_human_site_id as resolve_human_site_preference
from config import content_storage, assets_storage

logger = logging.getLogger("pencms.v1")

router = APIRouter(prefix="/v1", tags=["v1"])

# --- Security Dependency ---

async def verify_api_key(
    request: Request,
    x_pen_api_key: Optional[str] = Header(None, alias="X-Pen-API-Key")
) -> str:
    """Validate request via X-Pen-API-Key header or JWT cookie/Bearer token fallback.
    
    API key auth is the primary method (for agents/scripts).
    JWT cookie/Bearer token auth is accepted as a fallback so that the admin UI
    can call v1 endpoints using its existing browser session.
    """
    # 1. Try API key auth first
    if x_pen_api_key:
        valid_user = None
        matching_key = None
        if os.path.exists(USERS_DIR):
            for filename in os.listdir(USERS_DIR):
                if not filename.endswith(".yaml"):
                    continue
                try:
                    filepath = USERS_DIR / filename
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                        u = User(**data)
                        for key_meta in u.auth.agent_keys:
                            if verify_password(x_pen_api_key, key_meta.hash):
                                valid_user = u
                                matching_key = key_meta
                                break
                    if valid_user:
                        break
                except Exception:
                    continue

        if not valid_user or matching_key is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid X-Pen-API-Key"
            )
        request.state.site_id = getattr(matching_key, "site_id", None) or "default"
        request.state.actor_kind = "agent"
        request.state.actor_id = matching_key.name
        request.state.actor_scopes = tuple(matching_key.scopes)
        request.state.actor_key_id = matching_key.key_id
        return valid_user.public.username

    # 2. Fallback: JWT cookie or Bearer token (admin UI session)
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    if not token:
        token = request.cookies.get("pen_jwt")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Pen-API-Key header or session token"
        )

    try:
        payload = decode_access_token(token)
        uuid = payload.get("sub")
        if uuid is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token"
        )

    user = get_user_by_uuid(uuid)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    if payload.get("type") == "agent":
        from services.auth_service import decode_agent_token

        try:
            payload = decode_agent_token(token)
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid or expired agent token")
        request.state.site_id = payload.get("site_id")
        request.state.actor_kind = "agent"
        request.state.actor_id = (
            payload.get("agent_key_name")
            or f"key-{payload.get('agent_key_index')}"
        )
        request.state.actor_scopes = tuple(payload.get("scopes") or ())
        request.state.actor_key_id = payload.get("agent_key_id")
    else:
        request.state.actor_kind = "human"
        request.state.actor_id = user.public.username
        request.state.actor_scopes = ()
        request.state.actor_key_id = None
    return user.public.username


def resolve_v1_site_id(request: Request) -> str:
    """Use a key/token-bound site for agents and the selected site for humans."""
    if getattr(request.state, "actor_kind", None) == "agent":
        site_id = getattr(request.state, "site_id", None)
        if not site_id:
            raise HTTPException(status_code=403, detail="Agent credential is not site-bound")
        return site_id
    return resolve_human_site_preference(request)


def require_v1_agent_scope(request: Request, scope: str) -> None:
    """Enforce ``scope`` for agents (expanded JWT/key scopes) and humans (memberships)."""
    if getattr(request.state, "actor_kind", None) == "agent":
        scopes = tuple(getattr(request.state, "actor_scopes", ()))
        if scope not in expand_capabilities(scopes):
            raise HTTPException(
                status_code=403, detail=f"Agent key lacks required scope: {scope}"
            )
        return
    site_id = resolve_v1_site_id(request)
    assert_capability(request, scope, site_id=site_id)


def _v1_write_cap(frontmatter_or_page) -> str:
    from routers.pages import is_page_doc

    return "write:pages" if is_page_doc(frontmatter_or_page) else "write:posts"


def _v1_delete_cap(frontmatter_or_page) -> str:
    from routers.pages import is_page_doc

    return "delete:pages" if is_page_doc(frontmatter_or_page) else "delete:posts"

# --- Models ---

class EntryDetail(BaseModel):
    model_config = ConfigDict(extra='allow')
    frontmatter: Dict[str, Any]
    body: str
    composite: Optional[bool] = None
    partials: Optional[Dict[str, str]] = None
    run_id: Optional[str] = None
    expected_version: Optional[str] = None
    force: bool = False


class TranslationSiblingCreateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    language: str
    frontmatter: Dict[str, Any] = Field(default_factory=dict)
    body: str = ""
    composite: Optional[bool] = None
    partials: Optional[Dict[str, str]] = None
    run_id: Optional[str] = None

class MediaUploadRequest(BaseModel):
    filename: str
    content_base64: str


def _translation_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, TranslationNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, TranslationConflictError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, TranslationAuthorizationError):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, ContentI18nError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, PublishAutonomyError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))

# --- Endpoints ---

@router.get("/auth/verify")
async def verify_token(username: str = Depends(verify_api_key)):
    """Check if the provided credential token is valid."""
    return {
        "authenticated": True,
        "user": username
    }

@router.get("/content/collections")
async def list_collections(
    request: Request,
    username: str = Depends(verify_api_key),
    site_id: str = Depends(resolve_v1_site_id),
):
    """Retrieve list of content collections (e.g., pages, blog, portfolio)."""
    require_v1_agent_scope(request, "read")
    return get_collections_list(site_id=site_id)

@router.get("/content/collections/{collection}/entries")
async def list_entries(
    collection: str,
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1),
    language: Optional[str] = Query(
        None,
        description="Configured language. Omitted means the site default.",
    ),
    fallback: str = Query(
        "none",
        pattern="^(none|default)$",
        description="Use default rows where a live target sibling is missing.",
    ),
    username: str = Depends(verify_api_key),
    site_id: str = Depends(resolve_v1_site_id),
):
    """Retrieve indexed entries inside a specific collection (SQLite cached)."""
    require_v1_agent_scope(request, "read")
    try:
        config = get_site_language_config(site_id)
        requested_language = normalize_requested_language(language, config)
        items, total = query_entries(
            collection,
            page,
            limit,
            site_id=site_id,
            language=requested_language,
            fallback=fallback,
        )
    except ContentI18nError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "items": items,
        "total": total
    }

@router.get("/content/collections/{collection}/entries/{slug}")
async def read_entry(
    collection: str,
    slug: str,
    request: Request,
    language: Optional[str] = Query(
        None,
        description="Exact configured language. This endpoint never falls back.",
    ),
    username: str = Depends(verify_api_key),
    site_id: str = Depends(resolve_v1_site_id),
):
    """Retrieve the raw body and frontmatter content of a single flat file. Auto-syncs cache if disk is newer."""
    require_v1_agent_scope(request, "read")
    try:
        config = get_site_language_config(site_id)
        requested_language = normalize_requested_language(language, config)
    except ContentI18nError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    entry = get_entry(
        collection,
        slug,
        site_id=site_id,
        language=requested_language,
    )
    
    # Check if disk version is newer
    from services.file_service import resolve_path, read_page
    rel_path = await resolve_path(
        slug,
        collection,
        site_id=site_id,
        language=requested_language,
    )
    if rel_path:
        assert content_storage is not None
        try:
            file_stat = await content_storage.stat(rel_path)
            mtime = file_stat.get("mtime", 0.0)
        except Exception:
            mtime = 0.0
            
        if not entry or abs(entry.get("modified_at", 0.0) - mtime) > 1.0:
            # Stale or missing cache entry! Auto-sync it
            page_res = await read_page(
                slug,
                category=collection,
                include_partials=True,
                site_id=site_id,
                language=requested_language,
            )
            if page_res:
                from services.cache_service import save_entry_to_cache
                save_entry_to_cache(
                    collection=collection,
                    slug=slug,
                    filepath=rel_path,
                    title=page_res.frontmatter.get("title") or page_res.frontmatter.get("name") or slug.replace("-", " ").capitalize(),
                    published=page_res.frontmatter.get("published", True),
                    status=page_res.frontmatter.get("status", "published"),
                    domain=page_res.frontmatter.get("domain", "blog"),
                    needs_review=page_res.frontmatter.get("needs_review", False),
                    mtime=mtime,
                    frontmatter_dict=page_res.frontmatter,
                    body=page_res.content or "",
                    site_id=site_id,
                    language=requested_language,
                    translation_group=page_res.frontmatter.get("translation_group"),
                )
                entry = get_entry(
                    collection,
                    slug,
                    site_id=site_id,
                    language=requested_language,
                )

    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
        
    fm = json.loads(entry["frontmatter"])
    if "articles" in fm and "posts" not in fm:
        fm["posts"] = fm["articles"]
        fm["is_legacy"] = True
    composite_flag = fm.get("composite", False)
    partials_dict = {}
    if composite_flag:
        from services.file_service import read_partials
        if rel_path:
            manifest = fm.get("posts")
            partials_dict = await read_partials(rel_path, manifest)

    response = {
        "frontmatter": fm,
        "body": entry["body"],
        "composite": composite_flag,
        "partials": partials_dict,
        "provenance": content_provenance(fm),
    }
    if config.active:
        response.update({
            "language": entry["language"],
            "translation_group": entry["translation_group"],
            "translations": await translation_peer_summaries(
                slug,
                current_language=entry["language"],
                site_id=site_id,
            ),
        })
    if rel_path:
        response["version"] = await page_version_token(rel_path)
    return response

@router.put("/content/collections/{collection}/entries/{slug}")
async def save_entry(
    collection: str,
    slug: str,
    entry: EntryDetail,
    request: Request,
    language: Optional[str] = Query(
        None,
        description="Exact configured language. Omitted means the site default.",
    ),
    username: str = Depends(verify_api_key),
    site_id: str = Depends(resolve_v1_site_id),
):
    """Create or update a flat file with metadata frontmatter and body. Updates SQLite cache."""
    if slug.lower().strip() in ("undefined", "null", ""):
        raise HTTPException(
            status_code=400,
            detail="Invalid slug value: cannot be 'undefined', 'null', or empty."
        )

    config = get_site_language_config(site_id)
    try:
        requested_language = normalize_requested_language(language, config)
    except ContentI18nError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    existing_default = await read_page(
        slug,
        category=collection,
        include_partials=True,
        site_id=site_id,
        language=requested_language,
    )
    from routers.pages import is_page_doc

    if existing_default is not None:
        if is_page_doc(entry.frontmatter) != is_page_doc(existing_default):
            raise HTTPException(status_code=403, detail="cannot_change_page_kind")
        require_v1_agent_scope(request, _v1_write_cap(existing_default))
    else:
        require_v1_agent_scope(request, _v1_write_cap(entry.frontmatter))

    version_warning = check_expected_version(
        entry.expected_version,
        await page_version_token(existing_default.file_path)
        if existing_default is not None
        else None,
        force=bool(entry.force),
    )

    if config.active and requested_language != config.language:
        try:
            result = await update_translation_sibling(
                collection=collection,
                slug=slug,
                language=requested_language,
                actor=actor_context_from_state(request, site_id),
                frontmatter=dict(entry.frontmatter),
                body=entry.body,
                composite=entry.composite,
                partials=entry.partials,
                run_id=entry.run_id,
            )
            response = {
                "message": "Translation sibling saved successfully",
                "entry": page_payload(result),
                "version": result.version
                or await page_version_token(result.file_path),
            }
            if version_warning:
                response["version_warning"] = version_warning
            return response
        except Exception as exc:
            raise _translation_http_error(exc) from exc

    # Build PageFrontmatter and Page for the backward-compatible default language.
    import config as app_config

    if config.active:
        try:
            reject_spoofed_provenance(entry.frontmatter)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    actor = actor_context_from_state(request, site_id)
    fm_dict = dict(entry.frontmatter)
    if actor.is_agent:
        existing_status = (
            existing_default.frontmatter.get("status") if existing_default else "stub"
        )
        try:
            enforce_publish_autonomy(
                existing_status=existing_status,
                new_status=fm_dict.get("status"),
                autonomy=autonomy_for_site(site_id),
            )
        except PublishAutonomyError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    if config.active:
        fm_dict = stamp_actor_provenance(
            fm_dict,
            actor=actor,
            existing=(existing_default.frontmatter if existing_default else None),
            require_agent_review=False,
        )
    clear_review_if_published(fm_dict)
    if fm_dict.get("page") in (True, "true"):
        fm_dict["category"] = ""
    else:
        fm_dict["category"] = collection
    if "slug" not in fm_dict:
        fm_dict["slug"] = slug

    tax_token = app_config.set_active_taxonomy(app_config.load_taxonomy_for_site(site_id))
    try:
        try:
            page_obj = Page(
                frontmatter=PageFrontmatter(**fm_dict),
                content=entry.body,
                composite=(
                    existing_default.composite
                    if entry.composite is None and existing_default
                    else bool(entry.composite)
                ),
                partials=(
                    existing_default.partials
                    if entry.partials is None and existing_default
                    else (entry.partials or {})
                ),
            )
            result = await write_page(
                page_obj,
                page_id=slug,
                composite=bool(page_obj.composite),
                partials=page_obj.partials,
                site_id=site_id,
                language=requested_language,
            )
        except ValidationError as e:
            raise HTTPException(status_code=400, detail=format_validation_error(e))
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid document data / schema validation failure: {str(e)}")
    finally:
        app_config.reset_active_taxonomy(tax_token)

    response = {"message": "Entry saved successfully"}
    if config.active:
        response["entry"] = page_payload(result)
    response["version"] = result.version or await page_version_token(result.file_path)
    if version_warning:
        response["version_warning"] = version_warning
    return response


@router.post(
    "/content/collections/{collection}/entries/{slug}/translations",
    status_code=status.HTTP_201_CREATED,
)
async def create_entry_translation(
    collection: str,
    slug: str,
    body: TranslationSiblingCreateBody,
    request: Request,
    username: str = Depends(verify_api_key),
    site_id: str = Depends(resolve_v1_site_id),
):
    existing = await read_page(slug, category=collection, site_id=site_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    require_v1_agent_scope(request, _v1_write_cap(existing))
    try:
        result = await create_translation_sibling(
            collection=collection,
            slug=slug,
            language=body.language,
            actor=actor_context_from_state(request, site_id),
            frontmatter=body.frontmatter,
            body=body.body,
            composite=body.composite,
            partials=body.partials,
            run_id=body.run_id,
        )
        return {
            "message": "Translation sibling created",
            "entry": page_payload(result),
        }
    except Exception as exc:
        raise _translation_http_error(exc) from exc

@router.delete("/content/collections/{collection}/entries/{slug}")
async def delete_entry(
    collection: str,
    slug: str,
    request: Request,
    language: Optional[str] = Query(
        None,
        description="Exact configured language. Omitted means the site default.",
    ),
    delete_group: bool = Query(
        False,
        description="Delete the default document and every translation sibling.",
    ),
    username: str = Depends(verify_api_key),
    site_id: str = Depends(resolve_v1_site_id),
):
    """Delete the flat Markdown file and remove it from the SQLite index cache."""
    existing = await read_page(slug, category=collection, site_id=site_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    require_v1_agent_scope(request, _v1_delete_cap(existing))
    actor = actor_context_from_state(request, site_id)
    if delete_group and actor.is_agent:
        raise HTTPException(
            status_code=403,
            detail="Whole-group deletion requires a human admin session",
        )
    config = get_site_language_config(site_id)
    try:
        requested_language = normalize_requested_language(language, config)
        if config.active and requested_language != config.language:
            deleted = await delete_translation_sibling(
                collection=collection,
                slug=slug,
                language=requested_language,
                actor=actor,
            )
        else:
            deleted = await delete_page(
                slug,
                category=collection,
                site_id=site_id,
                language=requested_language,
                delete_group=delete_group,
            )
    except ContentI18nError as exc:
        code = 409 if "siblings" in str(exc).lower() else 400
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    except Exception as exc:
        raise _translation_http_error(exc) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"message": "File deleted"}

@router.get("/media/files")
async def list_media_files(
    request: Request,
    username: str = Depends(verify_api_key),
    site_id: str = Depends(resolve_v1_site_id),
):
    """List all assets stored in the active site's media directory."""
    require_v1_agent_scope(request, "read")
    try:
        from config import content_storage
        from routers.assets import public_asset_url, _logical_from_site_path
        from services.site_service import site_assets_prefix

        assert content_storage is not None
        prefix = site_assets_prefix(site_id)
        if not await content_storage.exists(prefix):
            return []
        files = await content_storage.list_dir(prefix, recursive=True)

        from services.cache_service import get_db_connection
        page_categories = {}
        try:
            with get_db_connection() as conn:
                rows = conn.execute(
                    "SELECT slug, collection FROM entries WHERE site_id = ? "
                    "GROUP BY slug, collection",
                    (site_id,),
                ).fetchall()
                page_categories = {r["slug"]: r["collection"] for r in rows}
        except Exception:
            pass

        media_files = []
        for filepath in files:
            # list_dir may return paths relative to prefix or absolute storage paths
            storage_path = filepath
            if not filepath.startswith(prefix):
                storage_path = f"{prefix}/{filepath}".replace("//", "/")
            try:
                stat = await content_storage.stat(storage_path)
                size_bytes = stat.get("size", 0)
                mtime = stat.get("mtime", 0.0)
                iso_time = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(mtime))
            except Exception:
                size_bytes = 0
                iso_time = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

            logical = _logical_from_site_path(site_id, storage_path)
            entity_id = "media"
            entity_type = "general"
            parts = logical.split("/")
            if len(parts) >= 3 and parts[0] == "images" and parts[1] == "content":
                entity_id = parts[2]
                entity_type = page_categories.get(entity_id, "general")

            media_files.append({
                "filename": logical,
                "public_url": public_asset_url(site_id, logical),
                "size_bytes": size_bytes,
                "modified_at": iso_time,
                "entity_id": entity_id,
                "entity_type": entity_type,
                "site_id": site_id,
            })
        return media_files
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list media files: {str(e)}")

@router.post("/media/files", status_code=201)
async def upload_media_file(
    payload: MediaUploadRequest,
    request: Request,
    username: str = Depends(verify_api_key),
    site_id: str = Depends(resolve_v1_site_id),
):
    """Upload a new media binary asset. Supports Base64 payload."""
    require_v1_agent_scope(request, "write:media")
    try:
        from config import content_storage
        from routers.assets import public_asset_url
        from services.site_service import join_site_assets_path

        assert content_storage is not None
        content_bytes = base64.b64decode(payload.content_base64)

        # Flatten target path: images/content/{category}/{page_id}/{filename} -> images/content/{page_id}/{filename}
        parts = payload.filename.split("/")
        if len(parts) >= 5 and parts[0] == "images" and parts[1] == "content":
            target_logical = f"images/content/{parts[3]}/{parts[4]}"
        else:
            target_logical = payload.filename.lstrip("/")

        if ".." in target_logical.split("/"):
            raise HTTPException(status_code=400, detail="Directory traversal is not allowed")

        storage_path = join_site_assets_path(site_id, target_logical)
        parent = "/".join(storage_path.split("/")[:-1])
        if parent:
            await content_storage.mkdir(parent)
        await content_storage.write_bytes(storage_path, content_bytes)

        stat = await content_storage.stat(storage_path)
        size_bytes = stat.get("size", len(content_bytes))
        mtime = stat.get("mtime", time.time())
        iso_time = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(mtime))

        entity_id = "media"
        entity_type = "general"
        t_parts = target_logical.split("/")
        if len(t_parts) >= 3 and t_parts[0] == "images" and t_parts[1] == "content":
            entity_id = t_parts[2]
            from services.cache_service import get_db_connection
            try:
                with get_db_connection() as conn:
                    row = conn.execute(
                        "SELECT collection FROM entries WHERE site_id = ? AND slug = ? "
                        "ORDER BY language LIMIT 1",
                        (site_id, entity_id),
                    ).fetchone()
                    if row:
                        entity_type = row["collection"]
            except Exception:
                pass

        return {
            "filename": target_logical,
            "public_url": public_asset_url(site_id, target_logical),
            "size_bytes": size_bytes,
            "modified_at": iso_time,
            "entity_id": entity_id,
            "entity_type": entity_type,
            "site_id": site_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload media file: {str(e)}")

@router.post("/sync")
async def git_sync(username: str = Depends(verify_api_key)):
    """Synchronize content files to the remote origin repository."""
    # Check if storage has sync capability
    if hasattr(content_storage, "sync"):
        success = await content_storage.sync()
        if not success:
            raise HTTPException(status_code=500, detail="Git sync pull/push failed")
    elif hasattr(content_storage, "_run_git"):
        # We can trigger git pull and push directly for the GitStorageProvider
        pull_ok = await content_storage._run_git("pull", "--rebase")
        if not pull_ok:
            raise HTTPException(status_code=500, detail="Git sync pull failed")
        push_ok = await content_storage._run_git("push")
        if not push_ok:
            raise HTTPException(status_code=500, detail="Git sync push failed")
    else:
        # If not a git provider, we can log a warning and return success as a stub
        logger.info("Storage provider is not Git-based; skipping sync operation.")
        
    return {"message": "Sync completed"}

@router.post("/cache/sync")
async def manual_cache_sync(username: str = Depends(verify_api_key)):
    """Manually trigger SQLite cache synchronization with storage provider."""
    from services.cache_service import sync_cache_with_storage
    try:
        await sync_cache_with_storage(content_storage)
    except ContentI18nError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok", "message": "Cache synchronized successfully"}

@router.get("/cache/status")
async def get_cache_status(username: str = Depends(verify_api_key)):
    """Retrieve database cache statistics (size, entry count, last sync time)."""
    from services.cache_service import get_db_connection, _db_path

    db_path = str(_db_path())

    entry_count = 0
    try:
        with get_db_connection() as conn:
            row = conn.execute("SELECT count(*) as count FROM entries").fetchone()
            if row:
                entry_count = row["count"]
    except Exception as e:
        logger.error(f"Failed to count entries: {e}")

    last_sync = 0.0
    db_size = 0
    if os.path.exists(db_path):
        try:
            last_sync = os.path.getmtime(db_path)
            db_size = os.path.getsize(db_path)
        except Exception as e:
            logger.error(f"Failed to stat DB file: {e}")

    return {
        "entry_count": entry_count,
        "last_sync": last_sync,
        "db_size_bytes": db_size,
        "server_now": time.time()
    }
