"""Site-scoped author bios CRUD + avatar upload."""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from models.author import Author, AuthorCreate, AuthorUpdate, AuthorsListResponse
from routers.auth import UserPublic, get_current_user
from services import author_service
from services.authz import require_capability
from services.site_service import join_site_assets_path, resolve_human_site_id

logger = logging.getLogger("pencms.authors")

router = APIRouter(prefix="/authors", tags=["authors"])

_ALLOWED_AVATAR_EXTS = [".png", ".svg", ".webp", ".jpg", ".jpeg", ".gif"]


@router.get("/", response_model=AuthorsListResponse)
async def list_authors(
    current_user: UserPublic = Depends(get_current_user),
    site_id: str = Depends(resolve_human_site_id),
):
    """List all authors for the active Content site."""
    try:
        authors = await author_service.list_authors(site_id)
        return AuthorsListResponse(site_id=site_id, authors=authors)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list authors: {e}")


@router.post("/", response_model=Author, status_code=201)
async def create_author(
    body: AuthorCreate,
    current_user: UserPublic = Depends(require_capability("write:authors")),
    site_id: str = Depends(resolve_human_site_id),
):
    """Create one author bio on the active site (avatar not required)."""
    try:
        return await author_service.create_author(body, site_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create author: {e}")


@router.get("/{slug}", response_model=Author)
async def get_author(
    slug: str,
    current_user: UserPublic = Depends(get_current_user),
    site_id: str = Depends(resolve_human_site_id),
):
    """Get one author by slug for the active site."""
    try:
        return await author_service.get_author(slug, site_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get author: {e}")


@router.put("/{slug}", response_model=Author)
async def update_author(
    slug: str,
    body: AuthorUpdate,
    current_user: UserPublic = Depends(require_capability("write:authors")),
    site_id: str = Depends(resolve_human_site_id),
):
    """Update one author (slug immutable; avatar not required)."""
    try:
        return await author_service.update_author(slug, body, site_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update author: {e}")


@router.delete("/{slug}", status_code=204)
async def delete_author(
    slug: str,
    current_user: UserPublic = Depends(require_capability("write:authors")),
    site_id: str = Depends(resolve_human_site_id),
):
    """Delete one author and best-effort remove their avatar file."""
    try:
        await author_service.delete_author(slug, site_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete author: {e}")


@router.post("/{slug}/avatar")
async def upload_author_avatar(
    slug: str,
    file: UploadFile = File(...),
    current_user: UserPublic = Depends(require_capability("write:authors")),
    site_id: str = Depends(resolve_human_site_id),
):
    """Upload an avatar image for one author under site assets/images/authors/."""
    from config import content_storage
    from routers.assets import public_asset_url

    # Ensure author exists on this site before writing files
    try:
        await author_service.get_author(slug, site_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

    key = author_service.sanitize_author_slug(slug)
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _ALLOWED_AVATAR_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported type: {ext}. Allowed: {', '.join(_ALLOWED_AVATAR_EXTS)}",
        )
    ext_val = ".jpg" if ext == ".jpeg" else ext

    authors_dir = join_site_assets_path(site_id, "images", "authors")
    try:
        await content_storage.mkdir(authors_dir)

        for fmt in ("png", "svg", "webp", "jpg", "jpeg", "gif"):
            old_path = f"{authors_dir}/{key}.{fmt}"
            if await content_storage.exists(old_path):
                try:
                    await content_storage.delete(old_path)
                except Exception as e:
                    logger.warning(
                        "Failed to remove old author avatar %s: %s", old_path, e
                    )

        target_path = f"{authors_dir}/{key}{ext_val}"
        contents = await file.read()
        await content_storage.write_bytes(target_path, contents)

        logical = f"images/authors/{key}{ext_val}"
        author = await author_service.set_author_avatar(key, logical, site_id)
        return {
            "message": "Author avatar uploaded",
            "path": logical,
            "url": public_asset_url(site_id, logical),
            "site_id": site_id,
            "author": author.model_dump(mode="json"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to save author avatar: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to save avatar: {e}")
    finally:
        file.file.close()
