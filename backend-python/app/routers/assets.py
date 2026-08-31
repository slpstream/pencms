"""Per-site media assets under ``content/sites/{id}/assets/`` via content_storage."""

from __future__ import annotations

import io
import mimetypes
import os
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from PIL import Image, ImageOps

from config import (
    IMAGE_CONVERT_TO_WEBP,
    IMAGE_EXTENSIONS,
    IMAGE_MAX_DIMENSION,
    IMAGE_QUALITY,
    MAX_UPLOAD_SIZE,
    content_storage,
)
from routers.auth import get_current_user, UserPublic
from services.authz import require_capability
from services.site_service import (
    join_site_assets_path,
    resolve_human_site_id,
    site_assets_prefix,
    validate_site_id,
    get_site,
)

router = APIRouter(prefix="/assets", tags=["assets"])


def public_asset_url(site_id: str, logical_path: str) -> str:
    """Public URL embedding site id (API proxy path — works for local + SSH)."""
    full = join_site_assets_path(site_id, logical_path)
    return f"/api/assets/raw/{full}"


def _logical_from_site_path(site_id: str, storage_path: str) -> str:
    prefix = site_assets_prefix(site_id) + "/"
    if storage_path.startswith(prefix):
        return storage_path[len(prefix) :]
    return storage_path


def resolve_asset_site_id(request: Request) -> str:
    """Human header/cookie; if agent JWT site is on request.state, prefer that."""
    agent_site = getattr(request.state, "site_id", None)
    if agent_site:
        return str(agent_site)
    return resolve_human_site_id(request)


def _safe_raw_storage_path(path: str) -> tuple[str, str]:
    """Validate a raw asset path and return (site_id, storage_path).

    Accepts:
    - ``sites/{site_id}/assets/...`` (canonical site assets)
    - ``sites/{site_id}/theme/assets/...`` (site custom theme assets only)
    - legacy ``images/...`` → mapped to default site

    Does **not** expose ``theme/templates`` or ``theme/partials``.
    """
    clean = path.replace("\\", "/").strip("/")
    if ".." in clean.split("/"):
        raise HTTPException(status_code=400, detail="Directory traversal is not allowed")

    parts = clean.split("/")
    if len(parts) >= 3 and parts[0] == "sites" and parts[2] == "assets":
        try:
            site_id = validate_site_id(parts[1])
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        if get_site(site_id) is None:
            raise HTTPException(status_code=400, detail=f"Unknown site_id: {site_id}")
        return site_id, clean

    # Site custom theme assets: sites/{id}/theme/assets/...
    if (
        len(parts) >= 4
        and parts[0] == "sites"
        and parts[2] == "theme"
        and parts[3] == "assets"
    ):
        try:
            site_id = validate_site_id(parts[1])
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        if get_site(site_id) is None:
            raise HTTPException(status_code=400, detail=f"Unknown site_id: {site_id}")
        return site_id, clean

    # Legacy flat path → default site
    site_id = "default"
    storage = join_site_assets_path(site_id, clean)
    return site_id, storage


@router.head("/raw/{path:path}", include_in_schema=False)
async def head_asset(path: str):
    """Existence-only HEAD for raw assets.

    FastAPI does not auto-answer HEAD on GET routes. PHP ``assetExists``
    probes heroes during homepage render; it must not download bytes.
    """
    _site_id, storage_path = _safe_raw_storage_path(path)
    if not await content_storage.exists(storage_path):
        raise HTTPException(status_code=404, detail="Asset not found")
    mime_type, _ = mimetypes.guess_type(storage_path)
    return Response(status_code=200, media_type=mime_type or "application/octet-stream")


@router.get("/raw/{path:path}")
async def serve_asset(path: str):
    """Serve an asset from content_storage (site-scoped path).

    Public read — path must embed ``sites/{id}/assets/…``,
    ``sites/{id}/theme/assets/…`` (or legacy ``images/…`` mapped to default).
    Cross-site reads via crafted paths are limited to known site ids;
    no auth required for public pages. Templates/partials under theme/ are not served.
    """
    _site_id, storage_path = _safe_raw_storage_path(path)

    if not await content_storage.exists(storage_path):
        raise HTTPException(status_code=404, detail="Asset not found")

    mime_type, _ = mimetypes.guess_type(storage_path)
    if not mime_type:
        mime_type = "application/octet-stream"

    try:
        content = await content_storage.read_bytes(storage_path)
        return Response(content=content, media_type=mime_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read asset: {str(e)}")


@router.get("/")
async def list_all_assets(
    current_user: UserPublic = Depends(get_current_user),
    site_id: str = Depends(resolve_human_site_id),
):
    """List all image assets for the active site."""
    base_images_dir = join_site_assets_path(site_id, "images/content")
    if not await content_storage.exists(base_images_dir):
        return []

    assets = []
    entities = await content_storage.list_dir(base_images_dir)

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

    for entity_id in entities:
        entity_path = f"{base_images_dir}/{entity_id}"
        if not await content_storage.is_dir(entity_path):
            continue

        files = await content_storage.list_dir(entity_path)
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext in IMAGE_EXTENSIONS:
                file_path = f"{entity_path}/{filename}"
                stats = await content_storage.stat(file_path)
                logical = _logical_from_site_path(site_id, file_path)
                category = page_categories.get(entity_id, "general")

                assets.append(
                    {
                        "filename": filename,
                        "path": logical,
                        "url": public_asset_url(site_id, logical),
                        "entity_type": category,
                        "entity_id": entity_id,
                        "size_bytes": stats["size"],
                        "modified_at": stats["mtime"],
                        "site_id": site_id,
                    }
                )

    return assets


@router.get("/{category}/{page_id}")
async def list_entity_assets(
    category: str,
    page_id: str,
    current_user: UserPublic = Depends(get_current_user),
    site_id: str = Depends(resolve_human_site_id),
):
    """List all image assets for a specific page."""
    asset_dir = join_site_assets_path(site_id, f"images/content/{page_id}")

    if not await content_storage.exists(asset_dir):
        return []

    assets = []
    files = await content_storage.list_dir(asset_dir)
    for filename in files:
        ext = os.path.splitext(filename)[1].lower()
        if ext in IMAGE_EXTENSIONS:
            file_path = f"{asset_dir}/{filename}"
            logical = _logical_from_site_path(site_id, file_path)
            assets.append(
                {
                    "filename": filename,
                    "path": logical,
                    "url": public_asset_url(site_id, logical),
                    "site_id": site_id,
                }
            )

    return assets


@router.post("/{category}/{page_id}")
async def upload_entity_asset(
    category: str,
    page_id: str,
    file: UploadFile = File(...),
    current_user: UserPublic = Depends(require_capability("write:media")),
    site_id: str = Depends(resolve_human_site_id),
):
    """Upload and optimize a new image asset for a specific page."""
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    asset_dir = join_site_assets_path(site_id, f"images/content/{page_id}")
    await content_storage.mkdir(asset_dir)

    if file.size and file.size > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({file.size} bytes). Maximum allowed is {MAX_UPLOAD_SIZE} bytes.",
        )

    try:
        contents = await file.read()
        img = Image.open(io.BytesIO(contents))

        img = ImageOps.exif_transpose(img)

        width, height = img.size
        if width > IMAGE_MAX_DIMENSION or height > IMAGE_MAX_DIMENSION:
            img.thumbnail(
                (IMAGE_MAX_DIMENSION, IMAGE_MAX_DIMENSION), Image.Resampling.LANCZOS
            )
            width, height = img.size

        original_base = os.path.splitext(file.filename)[0]
        if IMAGE_CONVERT_TO_WEBP:
            final_filename = f"{original_base}.webp"
            save_format = "WEBP"
        else:
            final_filename = file.filename
            save_format = img.format if img.format else "JPEG"

        file_path = f"{asset_dir}/{final_filename}"
        logical = _logical_from_site_path(site_id, file_path)

        buf = io.BytesIO()
        img.save(buf, format=save_format, quality=IMAGE_QUALITY, optimize=True)
        await content_storage.write_bytes(file_path, buf.getvalue())

        return {
            "filename": final_filename,
            "path": logical,
            "url": public_asset_url(site_id, logical),
            "dimensions": {"width": width, "height": height},
            "site_id": site_id,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process image: {str(e)}")
    finally:
        file.file.close()


@router.delete("/{category}/{page_id}/{filename}")
async def delete_entity_asset(
    category: str,
    page_id: str,
    filename: str,
    current_user: UserPublic = Depends(require_capability("delete:media")),
    site_id: str = Depends(resolve_human_site_id),
):
    """Delete a specific image asset."""
    file_path = join_site_assets_path(site_id, f"images/content/{page_id}/{filename}")

    if not await content_storage.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        await content_storage.delete(file_path)
        return {"status": "deleted", "filename": filename, "site_id": site_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")
