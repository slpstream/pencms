"""Admin REST for packaging and exporting themes.

Site-scoped package endpoints bake Style Settings and vendor registry fonts.
Raw install-theme export returns an unmodified zip of ``blog/themes/{slug}/``.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from models.user import UserPublic
from services.authz import assert_capability, require_capability
from services.site_service import ensure_sites_initialized, get_site
from services.theme_install_service import (
    ThemeExistsError,
    ThemeInvalidManifestError,
    ThemeTooLargeError,
)
from services.theme_package_service import (
    ThemePackageError,
    build_site_package_zip,
    export_installed_theme_zip,
    install_site_package,
)

router = APIRouter(tags=["theme-package"])


class PackageBody(BaseModel):
    slug: str = Field(..., min_length=1, max_length=64)
    name: Optional[str] = Field(default=None, max_length=200)
    author: Optional[str] = Field(default=None, max_length=200)


class PackageInstallBody(PackageBody):
    overwrite: bool = False


class PackageInstallResponse(BaseModel):
    slug: str
    name: str
    version: str
    overwrote: bool
    warnings: list[str] = Field(default_factory=list)


def _peek_token_payload(request: Request) -> Dict[str, Any]:
    from services.auth_service import decode_access_token
    import jwt as pyjwt

    token = None
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1]
    if not token:
        token = request.cookies.get("pen_jwt")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        return decode_access_token(token)
    except pyjwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail="Invalid token") from e


def _is_agent(payload: Dict[str, Any]) -> bool:
    return payload.get("type") == "agent"


def _require_human(request: Request) -> Dict[str, Any]:
    """Operator-only theme distribution actions reject agent JWTs."""
    payload = _peek_token_payload(request)
    if _is_agent(payload):
        raise HTTPException(
            status_code=403,
            detail="This action requires a human admin session",
        )
    return payload


def _latin1_header_value(text: str, *, max_len: int = 800) -> str:
    """Starlette encodes response headers as latin-1; collapse inspect logs."""
    collapsed = " ".join((text or "").split())
    collapsed = collapsed.replace("\u2014", "-").replace("\u2013", "-")
    collapsed = collapsed.replace("\u2018", "'").replace("\u2019", "'")
    collapsed = collapsed.replace("\u201c", '"').replace("\u201d", '"')
    encoded = collapsed.encode("latin-1", errors="replace").decode("latin-1")
    if len(encoded) > max_len:
        encoded = encoded[: max_len - 3].rstrip() + "..."
    return encoded


def _zip_response(data: bytes, filename: str, warnings: Optional[List[str]] = None) -> Response:
    disposition = (
        f'attachment; filename="{filename}"; '
        f"filename*=UTF-8''{quote(filename)}"
    )
    headers: Dict[str, str] = {
        "Content-Disposition": disposition,
        "Content-Length": str(len(data)),
        "Cache-Control": "no-store",
    }
    if warnings:
        headers["X-Pen-Package-Warnings"] = _latin1_header_value(" | ".join(warnings))
    return Response(
        content=data,
        media_type="application/zip",
        headers=headers,
    )


def _map_package_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ThemeTooLargeError):
        return HTTPException(status_code=413, detail=str(exc))
    if isinstance(exc, ThemeExistsError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, ThemeInvalidManifestError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, ThemePackageError):
        msg = str(exc)
        if msg.startswith("Unknown site_id"):
            return HTTPException(status_code=404, detail=msg)
        return HTTPException(status_code=400, detail=msg)
    return HTTPException(status_code=400, detail=str(exc))


@router.post("/sites/{site_id}/theme/package-zip")
async def package_site_theme_zip(
    site_id: str,
    body: PackageBody,
    request: Request,
    current_user: UserPublic = Depends(require_capability("write:theme")),
) -> Response:
    """Package the site's effective theme and return a zip download."""
    _require_human(request)
    assert_capability(request, "write:theme", site_id=site_id)
    ensure_sites_initialized()
    if get_site(site_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown site_id: {site_id}")

    try:
        # Off the event loop: Playwright loads /blog/ which curls FastAPI
        # (InternalAPIClient). Blocking here deadlocks preview even with
        # PHP_CLI_SERVER_WORKERS>=4. Same pattern as mcp_theme_inspect.
        data, filename, warnings = await asyncio.to_thread(
            build_site_package_zip,
            site_id,
            body.slug,
            name=body.name,
            author=body.author,
        )
    except Exception as e:
        raise _map_package_error(e) from e

    if not data:
        raise HTTPException(status_code=500, detail="Package returned an empty archive")
    return _zip_response(data, filename, warnings)


@router.post("/sites/{site_id}/theme/package-install", response_model=PackageInstallResponse)
async def package_site_theme_install(
    site_id: str,
    body: PackageInstallBody,
    request: Request,
    current_user: UserPublic = Depends(require_capability("write:theme")),
) -> PackageInstallResponse:
    """Write a packaged site theme into the global install themes directory."""
    _require_human(request)
    assert_capability(request, "write:theme", site_id=site_id)
    ensure_sites_initialized()
    if get_site(site_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown site_id: {site_id}")

    try:
        result = await asyncio.to_thread(
            install_site_package,
            site_id,
            body.slug,
            name=body.name,
            author=body.author,
            overwrite=body.overwrite,
        )
    except Exception as e:
        raise _map_package_error(e) from e

    return PackageInstallResponse(**result)


@router.get("/themes/{slug}/export-zip")
async def export_theme_zip(
    slug: str,
    request: Request,
    current_user: UserPublic = Depends(require_capability("write:theme")),
) -> Response:
    """Export an installed theme directory as a zip (no Style Settings bake)."""
    _require_human(request)

    try:
        data, filename = await asyncio.to_thread(export_installed_theme_zip, slug)
    except Exception as e:
        raise _map_package_error(e) from e

    if not data:
        raise HTTPException(status_code=500, detail="Export returned an empty archive")
    return _zip_response(data, filename)
