"""Storage configuration and SSH management API.

Provides endpoints for reading/writing storage config, testing SSH
connectivity, generating SSH keys, and triggering service restarts.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from typing import Optional
import asyncio
import configparser
import io
import logging
import os
import shlex
import signal

from PIL import Image, ImageOps

import config as app_config

logger = logging.getLogger("pencms.storage")
from models.user import UserPublic
from services.authz import require_admin
from services.ssh_client import compose_uri, decompose_uri, parse_sftp_uri, ssh_exec
from services.storage_registry import (
    SSH_STORAGE_PRO_POINTER,
    get_storage_type,
    list_storage_types,
)

router = APIRouter(prefix="/storage", tags=["storage"])


def _optimize_raster_image(contents: bytes, ext: str) -> bytes:
    """Resize and compress a raster image (same pipeline as content uploads).

    Applies EXIF transpose, downsizes to IMAGE_MAX_DIMENSION on the longest
    side, and re-saves with IMAGE_QUALITY compression.  Non-raster formats
    (.svg, .ico) are returned unchanged.
    """
    raster_exts = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
    if ext not in raster_exts:
        return contents

    img = Image.open(io.BytesIO(contents))
    img = ImageOps.exif_transpose(img)
    w, h = img.size
    if w > app_config.IMAGE_MAX_DIMENSION or h > app_config.IMAGE_MAX_DIMENSION:
        img.thumbnail(
            (app_config.IMAGE_MAX_DIMENSION, app_config.IMAGE_MAX_DIMENSION),
            Image.Resampling.LANCZOS,
        )
    save_format = img.format or "JPEG"
    buf = io.BytesIO()
    save_kwargs: dict = {"optimize": True}
    if save_format in ("JPEG", "WEBP"):
        save_kwargs["quality"] = app_config.IMAGE_QUALITY
    img.save(buf, format=save_format, **save_kwargs)
    return buf.getvalue()


async def _upload_site_branding_file(
    request: Request,
    file: UploadFile,
    basename: str,
    allowed_exts: list[str],
    success_message: str,
) -> dict:
    """Write logo/hero/favicon into the active site's assets/images/.

    Favicon is per-site only (no install shared fallback).
    Admin PenCMS chrome is unaffected.
    """
    from config import content_storage, MAX_UPLOAD_SIZE
    from routers.assets import public_asset_url
    from services.authz import assert_capability
    from services.site_service import join_site_assets_path, resolve_human_site_id

    site_id = resolve_human_site_id(request)
    assert_capability(request, "write:seo", site_id=site_id)

    if file.size and file.size > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({file.size} bytes). Maximum allowed is 10MB.",
        )

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed_exts:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported type: {ext}. Allowed: {', '.join(allowed_exts)}",
        )
    ext_val = ".jpg" if ext == ".jpeg" else ext

    images_dir = join_site_assets_path(site_id, "images")
    try:
        await content_storage.mkdir(images_dir)

        formats = ["png", "svg", "webp", "jpg", "jpeg", "gif", "ico"]
        for fmt in formats:
            old_path = f"{images_dir}/{basename}.{fmt}"
            if await content_storage.exists(old_path):
                try:
                    await content_storage.delete(old_path)
                except Exception as e:
                    logger.warning("Failed to remove old %s file %s: %s", basename, old_path, e)

        target_path = f"{images_dir}/{basename}{ext_val}"
        contents = await file.read()
        if len(contents) > MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large ({len(contents)} bytes). Maximum allowed is 10MB.",
            )
        contents = _optimize_raster_image(contents, ext)
        await content_storage.write_bytes(target_path, contents)

        logical = f"images/{basename}{ext_val}"
        return {
            "message": success_message,
            "path": logical,
            "url": public_asset_url(site_id, logical),
            "site_id": site_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to save %s: %s", basename, e)
        raise HTTPException(status_code=500, detail=f"Failed to save {basename}: {e}")
    finally:
        file.file.close()


# --- Helpers ---

def _get_config_path():
    """Return the absolute path to config.ini."""
    return app_config.BASE_DIR / "config.ini"


def _read_ini():
    """Read and parse config.ini."""
    cp = configparser.ConfigParser()
    cp.read(_get_config_path())
    return cp


def _detect_provider_type(path_raw: str, storage_type: str) -> str:
    """Determine the effective provider type for display."""
    # 1. Prioritize explicit storage type from config
    if storage_type == "ssh":
        return "ssh"
    if storage_type == "git":
        return "git"
    if storage_type == "local":
        return "local"

    # 2. Fallback for old/untyped configs where storage_type might not be set
    if app_config._is_uri(path_raw):
        if path_raw.startswith("sftp://"):
            return "ssh"
        return "unknown"

    # 3. Auto-detect .git (only for local paths with no explicit storage_type)
    try:
        resolved = (app_config.BASE_DIR / path_raw).resolve()
        if resolved.is_dir() and (resolved / ".git").exists():
            return "git"
    except Exception:
        pass
    return "local"


def _default_key_path() -> str:
    """Return the default SSH key path for the process user."""
    return os.path.join(os.path.expanduser("~"), ".ssh", "id_ed25519")


# --- Endpoints ---

@router.get("/config")
async def get_storage_config(
    current_user: UserPublic = Depends(require_admin),
):
    """Read current storage configuration from config.ini.

    Returns decomposed SSH fields for the UI instead of raw URIs.
    """
    cp = _read_ini()

    content_dir = cp.get("Paths", "content_dir", fallback="../pencms-data/content")
    content_type = cp.get("Paths", "content_storage_type", fallback="local")
    content_auth = cp.get("Paths", "content_auth_method", fallback="key")
    assets_dir = cp.get("Paths", "assets_dir", fallback="../pencms-data/assets")
    assets_type = cp.get("Paths", "assets_storage_type", fallback="local")
    assets_auth = cp.get("Paths", "assets_auth_method", fallback="key")

    key_path = _default_key_path()

    return {
        "content": {
            "path": content_dir,
            "storage_type": content_type,
            "auth_method": content_auth,
            "effective_provider": _detect_provider_type(content_dir, content_type),
            "is_remote": app_config._is_uri(content_dir),
            "ssh": decompose_uri(content_dir) if app_config._is_uri(content_dir) else None,
        },
        "assets": {
            "path": assets_dir,
            "storage_type": assets_type,
            "auth_method": assets_auth,
            "effective_provider": _detect_provider_type(assets_dir, assets_type),
            "is_remote": app_config._is_uri(assets_dir),
            "ssh": decompose_uri(assets_dir) if app_config._is_uri(assets_dir) else None,
        },
        "available_providers": list_storage_types(),
        "ssh_key_exists": os.path.isfile(key_path),
        "ssh_key_path": key_path,
    }


@router.put("/config")
async def update_storage_config(
    data: dict,
    current_user: UserPublic = Depends(require_admin),
):
    """Validate and write storage configuration to config.ini.

    URI validation is a hard gate. Passwords are now handled client-side in the vault.
    Accepts decomposed SSH fields (host, port, username, path) or a raw URI.
    """
    content_type = data.get("content_storage_type", "local")
    assets_type = data.get("assets_storage_type", "local")
    content_auth = data.get("content_auth_method", "key")
    assets_auth = data.get("assets_auth_method", "key")

    # Build URIs from decomposed fields or raw path
    if content_type == "ssh":
        if get_storage_type("ssh") is None:
            raise HTTPException(status_code=400, detail=SSH_STORAGE_PRO_POINTER)
        ssh = data.get("content_ssh", {})
        if not ssh.get("host") or not ssh.get("username"):
            raise HTTPException(status_code=400, detail="Host and username are required for Content Storage (SSH)")
        content_dir = compose_uri(
            ssh.get("host", ""), int(ssh.get("port", 22)),
            ssh.get("username", ""), ssh.get("path", "/")
        )
    else:
        content_dir = data.get("content_dir", "")

    if assets_type == "ssh":
        if get_storage_type("ssh") is None:
            raise HTTPException(status_code=400, detail=SSH_STORAGE_PRO_POINTER)
        ssh = data.get("assets_ssh", {})
        if not ssh.get("host") or not ssh.get("username"):
            raise HTTPException(status_code=400, detail="Host and username are required for Asset Storage (SSH)")
        assets_dir = compose_uri(
            ssh.get("host", ""), int(ssh.get("port", 22)),
            ssh.get("username", ""), ssh.get("path", "/")
        )
    else:
        assets_dir = data.get("assets_dir", "")

    if not content_dir or not assets_dir:
        raise HTTPException(status_code=400, detail="Both content and assets paths are required")

    # Hard validation:
    # 1. URIs must be parseable and are only allowed for SSH storage
    # 2. Local/Git storage must not use URIs
    for label, uri, storage_type in [("content", content_dir, content_type), ("assets", assets_dir, assets_type)]:
        is_uri = app_config._is_uri(uri)
        if storage_type == "ssh":
            if get_storage_type("ssh") is None:
                raise HTTPException(status_code=400, detail=SSH_STORAGE_PRO_POINTER)
            if not is_uri:
                raise HTTPException(status_code=400, detail=f"{label.capitalize()} Storage is set to SSH but path is not a URI: {uri}")
            if not uri.startswith("sftp://"):
                raise HTTPException(status_code=400, detail=f"Unsupported URI scheme for {label}: {uri}")
            try:
                factory = get_storage_type("ssh")
                factory(uri)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid {label} URI: {e}")
        else:
            if is_uri:
                raise HTTPException(status_code=400, detail=f"{label.capitalize()} Storage is set to {storage_type} but path is a URI: {uri}")

    # Write to config.ini (backup first)
    ini_path = _get_config_path()
    backup_path = ini_path.with_suffix(".ini.bak")

    try:
        if ini_path.exists():
            import shutil
            shutil.copy2(ini_path, backup_path)

        cp = _read_ini()
        if not cp.has_section("Paths"):
            cp.add_section("Paths")

        cp.set("Paths", "content_dir", content_dir)
        cp.set("Paths", "content_storage_type", content_type)
        cp.set("Paths", "content_auth_method", content_auth)
        cp.set("Paths", "assets_dir", assets_dir)
        cp.set("Paths", "assets_storage_type", assets_type)
        cp.set("Paths", "assets_auth_method", assets_auth)

        with open(ini_path, "w", encoding="utf-8") as f:
            cp.write(f)

        return {
            "message": "Storage configuration saved. Service restart required to apply changes.",
            "restart_required": True,
        }
    except Exception as e:
        if backup_path.exists():
            import shutil
            shutil.copy2(backup_path, ini_path)
        raise HTTPException(status_code=500, detail=f"Failed to save config: {e}")


@router.post("/test-ssh")
async def test_ssh_connection(
    data: dict,
    current_user: UserPublic = Depends(require_admin),
):
    """Test SSH connectivity and write permissions to a remote path.

    Accepts decomposed fields (host, port, username, path) or a raw URI.
    Supports both key and password authentication.
    """
    # Accept decomposed fields or raw URI
    uri = data.get("uri")
    if not uri:
        host = data.get("host", "")
        port = int(data.get("port", 22))
        username = data.get("username", "")
        path = data.get("path", "/")
        if not host or not username:
            raise HTTPException(status_code=400, detail="Host and username are required")
        uri = compose_uri(host, port, username, path)

    if get_storage_type("ssh") is None:
        raise HTTPException(status_code=400, detail=SSH_STORAGE_PRO_POINTER)

    password = data.get("password")  # None for key auth
    auth_method = data.get("auth_method", "key")

    try:
        parsed = parse_sftp_uri(uri)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid URI: {e}")

    if auth_method == "password" and password:
        active_password = password
    else:
        active_password = parsed.get("password")

    import time
    start = time.monotonic()

    base = parsed["path"]
    probe = f"{base}/.pencms-probe"
    cmd = (
        f"echo PENCMS_OK && "
        f"mkdir -p {shlex.quote(base)} && "
        f"touch {shlex.quote(probe)} && "
        f"rm -f {shlex.quote(probe)}"
    )

    print(f"[test-ssh] uri={uri} auth={auth_method} has_password={bool(active_password)}", flush=True)
    print(f"[test-ssh] cmd={cmd}", flush=True)
    try:
        rc, stdout, stderr = await asyncio.wait_for(
            ssh_exec(
                user=parsed["user"],
                host=parsed["host"],
                port=parsed["port"],
                command=cmd,
                password=active_password,
            ),
            timeout=30,
        )
    except asyncio.TimeoutError:
        elapsed_ms = round((time.monotonic() - start) * 1000)
        print(f"[test-ssh] TIMEOUT after {elapsed_ms}ms", flush=True)
        return {"success": False, "error": f"Connection timed out after {elapsed_ms}ms"}
    except Exception as e:
        elapsed_ms = round((time.monotonic() - start) * 1000)
        print(f"[test-ssh] EXCEPTION after {elapsed_ms}ms: {type(e).__name__}: {e}", flush=True)
        return {"success": False, "error": f"SSH execution failed: {e}"}

    elapsed_ms = round((time.monotonic() - start) * 1000)
    print(f"[test-ssh] rc={rc} elapsed={elapsed_ms}ms stdout={stdout[:200]!r} stderr={stderr[:200]!r}", flush=True)

    if rc != 0:
        error_msg = stderr.decode(errors="replace").strip()
        if not error_msg:
            error_msg = f"SSH exited with code {rc} (no error message)"
        return {"success": False, "error": error_msg, "latency_ms": elapsed_ms}

    output = stdout.decode(errors="replace").strip()
    err_output = stderr.decode(errors="replace").strip()
    if "PENCMS_OK" not in output:
        detail = f"Unexpected output: {output}"
        if err_output:
            detail += f" | stderr: {err_output}"
        return {"success": False, "error": detail, "latency_ms": elapsed_ms}

    return {"success": True, "latency_ms": elapsed_ms}



@router.get("/ssh-key")
async def get_ssh_key(
    current_user: UserPublic = Depends(require_admin),
):
    """Read the existing SSH public key without any generation side-effects.

    Returns the key path, existence status, and public key content.
    Safe to call on page load (GET, idempotent, no state changes).
    """
    key_path = _default_key_path()
    pub_path = key_path + ".pub"
    exists = os.path.isfile(key_path)
    public_key = ""

    if exists and os.path.isfile(pub_path):
        try:
            with open(pub_path, "r") as f:
                public_key = f.read().strip()
        except Exception:
            public_key = "(unable to read public key file)"

    return {
        "exists": exists,
        "key_path": key_path,
        "public_key": public_key,
    }

@router.post("/generate-key")
async def generate_ssh_key(
    current_user: UserPublic = Depends(require_admin),
):
    """Generate an Ed25519 SSH key pair if one doesn't exist.

    The key is created at the default path for the process user
    (e.g. /home/www-data/.ssh/id_ed25519 if running as www-data).
    Never overwrites an existing key.
    """
    key_path = _default_key_path()
    ssh_dir = os.path.dirname(key_path)
    pub_path = key_path + ".pub"

    # Never overwrite an existing key
    if os.path.isfile(key_path):
        try:
            with open(pub_path, "r") as f:
                public_key = f.read().strip()
        except FileNotFoundError:
            public_key = "(public key file missing — key exists but .pub not found)"

        return {
            "created": False,
            "key_path": key_path,
            "public_key": public_key,
            "message": "SSH key already exists. Not overwriting.",
        }

    # Ensure ~/.ssh/ directory exists with correct permissions
    try:
        os.makedirs(ssh_dir, mode=0o700, exist_ok=True)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Cannot create {ssh_dir}: {e}")

    # Generate key
    try:
        proc = await asyncio.create_subprocess_exec(
            "ssh-keygen", "-t", "ed25519",
            "-f", key_path,
            "-N", "",  # No passphrase
            "-C", "pencms-cms",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"ssh-keygen failed: {stderr.decode(errors='replace').strip()}"
            )

        with open(pub_path, "r") as f:
            public_key = f.read().strip()

        return {
            "created": True,
            "key_path": key_path,
            "public_key": public_key,
            "message": "SSH key pair generated successfully.",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Key generation failed: {e}")


@router.get("/list")
async def list_storage_files(
    path: str = "",
    recursive: bool = False,
    current_user: UserPublic = Depends(require_admin),
):
    """List all files in the storage provider at the given path."""
    from config import assets_storage
    
    if not await assets_storage.exists(path):
        return []
        
    # Use the provider's native list_dir which already handles recursion efficiently
    return await assets_storage.list_dir(path, recursive=recursive)


@router.post("/restart")
async def restart_service(
    current_user: UserPublic = Depends(require_admin),
):
    """Gracefully shut down the service for config reload.

    Relies on systemd (Restart=always) or equivalent process manager
    to respawn the service with the updated config.ini.
    """
    # Schedule shutdown slightly in the future so the response can be sent
    async def delayed_shutdown():
        await asyncio.sleep(0.5)
        os.kill(os.getpid(), signal.SIGTERM)

    asyncio.create_task(delayed_shutdown())

    return {"message": "Service shutting down for config reload. It will restart automatically."}


@router.post("/rebuild-cache")
async def rebuild_cache(
    current_user: UserPublic = Depends(require_admin),
):
    """Clear and rebuild the in-memory cache for storage providers."""
    cleared = False
    
    if hasattr(app_config.content_storage, "clear_cache"):
        app_config.content_storage.clear_cache()
        cleared = True
        
    if hasattr(app_config.assets_storage, "clear_cache"):
        app_config.assets_storage.clear_cache()
        cleared = True
        
    if cleared:
        from services.cache_service import sync_cache_with_storage
        from services.file_service import list_pages
        
        async def warm_cache():
            try:
                await sync_cache_with_storage(app_config.content_storage)
                await list_pages()
            except Exception as e:
                logger.error(f"Failed to warm cache: {e}")
                
        asyncio.create_task(warm_cache())
        return {"message": "Cache successfully cleared and warming initiated."}
    else:
        return {"message": "Caching is not enabled or active."}


@router.put("/theme")
async def update_active_theme(
    data: dict,
    current_user: UserPublic = Depends(require_admin),
):
    """Update the active theme in config.ini securely."""
    theme = data.get("theme")
    if not theme:
        raise HTTPException(status_code=400, detail="Theme name is required")
        
    ini_path = _get_config_path()
    backup_path = ini_path.with_suffix(".ini.bak")
    
    try:
        if ini_path.exists():
            import shutil
            shutil.copy2(ini_path, backup_path)
            
        cp = _read_ini()
        if not cp.has_section("theme"):
            cp.add_section("theme")
            
        cp.set("theme", "active", theme)
        
        with open(ini_path, "w", encoding="utf-8") as f:
            cp.write(f)
            
        return {"message": "Theme successfully updated", "theme": theme}
    except Exception as e:
        if backup_path.exists():
            import shutil
            shutil.copy2(backup_path, ini_path)
        raise HTTPException(status_code=500, detail=f"Failed to update theme: {e}")


@router.get("/general")
async def get_general_config(
    current_user: UserPublic = Depends(require_admin),
):
    """Read install-wide General settings from config.ini (use_ai only)."""
    cp = _read_ini()
    use_ai = cp.getboolean("General", "use_ai", fallback=False)
    return {"use_ai": use_ai}


@router.put("/general")
async def update_general_config(
    data: dict,
    current_user: UserPublic = Depends(require_admin),
):
    """Write install General fields to config.ini.

    Only ``use_ai`` is accepted. Legacy presentation keys (tagline, hero_*,
    display_logo, contact_email) are ignored so old clients cannot reintroduce
    install-wide branding — those live on PATCH /api/sites/{id}.
    """
    ini_path = _get_config_path()
    backup_path = ini_path.with_suffix(".ini.bak")

    try:
        if ini_path.exists():
            import shutil
            shutil.copy2(ini_path, backup_path)

        cp = _read_ini()
        if not cp.has_section("General"):
            cp.add_section("General")

        if "use_ai" in data:
            use_ai = data.get("use_ai", False)
            cp.set("General", "use_ai", "true" if use_ai else "false")

        with open(ini_path, "w", encoding="utf-8") as f:
            cp.write(f)

        result = await get_general_config()
        result["message"] = "General settings successfully updated"
        return result
    except Exception as e:
        if backup_path.exists():
            import shutil
            shutil.copy2(backup_path, ini_path)
        raise HTTPException(status_code=500, detail=f"Failed to update general settings: {e}")



@router.get("/branding")
async def get_site_branding(request: Request):
    """Resolve logo/favicon URLs for the active Content site in one round-trip.

    Admin Site Settings used to HEAD-probe every extension through the PHP
    proxy; a single list_dir keeps the preview in sync with the form paint.
    """
    from config import content_storage
    from routers.assets import public_asset_url
    from services.site_service import join_site_assets_path, resolve_human_site_id

    site_id = resolve_human_site_id(request)
    images_dir = join_site_assets_path(site_id, "images")

    names: set[str] = set()
    try:
        if await content_storage.exists(images_dir):
            for entry in await content_storage.list_dir(images_dir):
                # Non-recursive list_dir returns bare names (files + subdirs)
                base = entry.replace("\\", "/").split("/")[-1].lower()
                if base and "." in base:
                    names.add(base)
    except Exception as e:
        logger.warning("Failed to list branding images for site %s: %s", site_id, e)

    def pick(basename: str, formats: list[str]) -> Optional[str]:
        for fmt in formats:
            if f"{basename}.{fmt}" in names:
                return public_asset_url(site_id, f"images/{basename}.{fmt}")
        return None

    return {
        "site_id": site_id,
        "logo": pick("logo", ["png", "svg", "webp", "jpg", "gif"]),
        "favicon": pick("favicon", ["svg", "ico", "png"]),
    }


@router.post("/logo")
async def upload_site_logo(request: Request, file: UploadFile = File(...)):
    """Upload a site logo into the active site's assets (X-Pen-Site-Id / cookie)."""
    return await _upload_site_branding_file(
        request,
        file,
        basename="logo",
        allowed_exts=[".png", ".svg", ".webp", ".jpg", ".jpeg", ".gif"],
        success_message="Logo uploaded successfully",
    )


@router.post("/avatar")
async def upload_user_avatar(file: UploadFile = File(...)):
    """Upload a new shared user avatar, clearing out any existing user avatar files first."""
    if file.size and file.size > app_config.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({file.size} bytes). Maximum allowed is 10MB."
        )

    # 1. Validate file extension
    ext = os.path.splitext(file.filename or "")[1].lower()
    allowed_exts = ['.png', '.svg', '.webp', '.jpg', '.jpeg', '.gif']
    if ext not in allowed_exts:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image type: {ext}. Allowed: {', '.join(allowed_exts)}"
        )

    # Standardize jpeg to jpg
    ext_val = ".jpg" if ext == ".jpeg" else ext

    avatar_dir = app_config.BASE_DIR / "apps/blog/shared/images"

    try:
        # Ensure the shared/images directory exists
        os.makedirs(avatar_dir, exist_ok=True)

        # 2. Prevent extension competing: Scan and remove any existing avatar.* files
        formats = ['png', 'svg', 'webp', 'jpg', 'jpeg', 'gif']
        for fmt in formats:
            old_file = avatar_dir / f"avatar.{fmt}"
            if old_file.exists():
                try:
                    os.remove(old_file)
                except OSError as e:
                    logger.warning(f"Failed to remove old avatar file {old_file}: {e}")

        # 3. Save new avatar
        target_path = avatar_dir / f"avatar{ext_val}"
        contents = await file.read()
        if len(contents) > app_config.MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large ({len(contents)} bytes). Maximum allowed is 10MB."
            )
        contents = _optimize_raster_image(contents, ext)

        with open(target_path, "wb") as f:
            f.write(contents)

        return {
            "message": "Avatar uploaded successfully",
            "url": f"/blog/shared/images/avatar{ext_val}"
        }
    except Exception as e:
        logger.error(f"Failed to save avatar: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save avatar: {e}")
    finally:
        file.file.close()


@router.post("/hero")
async def upload_site_hero(request: Request, file: UploadFile = File(...)):
    """Upload a site hero banner into the active site's assets (X-Pen-Site-Id / cookie)."""
    return await _upload_site_branding_file(
        request,
        file,
        basename="hero",
        allowed_exts=[".png", ".svg", ".webp", ".jpg", ".jpeg", ".gif"],
        success_message="Hero image uploaded successfully",
    )


@router.post("/favicon")
async def upload_site_favicon(request: Request, file: UploadFile = File(...)):
    """Upload a site favicon into the active site's assets (X-Pen-Site-Id / cookie)."""
    return await _upload_site_branding_file(
        request,
        file,
        basename="favicon",
        allowed_exts=[".ico", ".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp"],
        success_message="Favicon uploaded successfully",
    )


@router.post("/og-default")
async def upload_site_og_default(request: Request, file: UploadFile = File(...)):
    """Upload static default share / OG image (site-wide og:image fallback)."""
    return await _upload_site_branding_file(
        request,
        file,
        basename="og-default",
        allowed_exts=[".png", ".jpg", ".jpeg", ".webp", ".gif"],
        success_message="Default share image uploaded successfully",
    )


@router.post("/og-defaulthero")
async def upload_site_og_default_hero(request: Request, file: UploadFile = File(...)):
    """Upload generator fallback hero used when a post has no featured image."""
    return await _upload_site_branding_file(
        request,
        file,
        basename="og-defaulthero",
        allowed_exts=[".png", ".jpg", ".jpeg", ".webp", ".gif"],
        success_message="OG default hero uploaded successfully",
    )


@router.post("/og-watermark")
async def upload_site_og_watermark(request: Request, file: UploadFile = File(...)):
    """Upload full-canvas OG watermark overlay (transparent PNG preferred)."""
    return await _upload_site_branding_file(
        request,
        file,
        basename="og-watermark",
        allowed_exts=[".png", ".webp"],
        success_message="OG watermark uploaded successfully",
    )


