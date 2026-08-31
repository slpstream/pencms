"""Admin REST for installing themes from uploaded .zip packages.

Wraps ``theme_install_service``. Auth: session JWT + admin role.
"""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from models.user import UserPublic
from routers.auth import get_current_user
from services.authz import require_capability
from services.site_service import ensure_sites_initialized
from services.social_preview import scan_installed_themes_detail
from services.theme_install_service import (
    ThemeExistsError,
    ThemeInstallError,
    ThemeInvalidArchiveError,
    ThemeInvalidManifestError,
    ThemeTooLargeError,
    install_from_url,
    install_from_zip,
)
from services.theme_url_fetch import (
    ThemeUrlFetchError,
    ThemeUrlTimeoutError,
    ThemeUrlUpstreamError,
)

router = APIRouter(prefix="/themes", tags=["theme-install"])


class InstallResponse(BaseModel):
    slug: str
    name: str
    version: str
    overwrote: bool
    warnings: list[str] = Field(default_factory=list)


class InstallFromUrlRequest(BaseModel):
    url: str = Field(..., min_length=1)
    overwrite: bool = False


class InstalledThemeDetail(BaseModel):
    slug: str
    name: str
    version: str
    author: str
    description: str
    color_mode: str
    supports: list[str] = Field(default_factory=list)
    has_screenshot: bool


class InstalledThemesResponse(BaseModel):
    themes: list[InstalledThemeDetail]


@router.get("", response_model=InstalledThemesResponse)
async def list_installed_themes(
    current_user: UserPublic = Depends(get_current_user),
):
    """List install themes with manifest metadata for the admin UI."""
    ensure_sites_initialized()
    return {"themes": scan_installed_themes_detail()}


@router.post("/install", response_model=InstallResponse)
async def install_theme(
    file: UploadFile = File(...),
    overwrite: bool = Form(False),
    current_user: UserPublic = Depends(require_capability("write:theme")),
):
    """Install a theme from a .zip archive into the global themes directory.

    Returns 409 if the theme slug already exists and ``overwrite`` is false.
    """
    ensure_sites_initialized()

    if file is None or not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")

    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext != "zip":
        raise HTTPException(status_code=400, detail="File must be a .zip archive")

    try:
        contents = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read upload: {e}") from e

    try:
        result = install_from_zip(contents, overwrite=overwrite)
    except ThemeTooLargeError as e:
        raise HTTPException(status_code=413, detail=str(e)) from e
    except ThemeExistsError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except (ThemeInvalidArchiveError, ThemeInvalidManifestError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ThemeInstallError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Install failed: {e}") from e

    return InstallResponse(**result)


@router.post("/install-from-url", response_model=InstallResponse)
async def install_theme_from_url(
    body: InstallFromUrlRequest,
    current_user: UserPublic = Depends(require_capability("write:theme")),
):
    """Install a theme from a remote HTTPS .zip or GitHub/GitLab repository URL."""
    ensure_sites_initialized()

    try:
        result = install_from_url(body.url, overwrite=body.overwrite)
    except ThemeTooLargeError as e:
        raise HTTPException(status_code=413, detail=str(e)) from e
    except ThemeExistsError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ThemeUrlTimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e)) from e
    except ThemeUrlUpstreamError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except (ThemeUrlFetchError, ThemeInvalidArchiveError, ThemeInvalidManifestError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ThemeInstallError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Install failed: {e}") from e

    return InstallResponse(**result)
