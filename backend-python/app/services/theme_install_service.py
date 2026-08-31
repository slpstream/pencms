"""Install themes from uploaded .zip packages into the global themes directory.

Install themes under ``frontend-php/src/blog/themes/`` are immutable from the
site-private theme customization service. This module adds the ability to upload
a zipped theme package and extract it into that directory, replacing the
immutable install themes available to every site.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import tempfile
import time
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from zipfile import ZipFile, ZipInfo

import services.social_preview as social_preview

logger = logging.getLogger("pencms.theme_install")

RESERVED_THEME_ID = "custom"
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
MAX_FILES = 2000
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


class ThemeInstallError(ValueError):
    """Raised for invalid install operations."""


class ThemeExistsError(ThemeInstallError):
    """Raised when a theme slug already exists and overwrite was not requested."""


class ThemeInvalidArchiveError(ThemeInstallError):
    """Raised for zip structural or safety violations."""


class ThemeTooLargeError(ThemeInstallError):
    """Raised when upload or uncompressed contents exceed limits."""


class ThemeInvalidManifestError(ThemeInstallError):
    """Raised when theme.json is missing or invalid."""


def _slug_from_name(name: str) -> str:
    """Derive a directory-safe slug from a human-readable theme name."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not slug:
        raise ThemeInvalidManifestError(
            "theme.json 'name' cannot be sanitized to a valid slug"
        )
    return slug


def _validate_slug(slug: str) -> str:
    """Confirm slug is safe and not reserved; return it stripped/lowercased."""
    s = (slug or "").strip().lower()
    if not s:
        raise ThemeInvalidManifestError("Theme slug is required")
    if s == RESERVED_THEME_ID:
        raise ThemeInvalidManifestError(
            f"'{RESERVED_THEME_ID}' is a reserved theme identifier"
        )
    if s.startswith("_"):
        raise ThemeInvalidManifestError(
            "Theme slug cannot start with an underscore"
        )
    if not SLUG_RE.match(s):
        raise ThemeInvalidManifestError(
            f"Invalid theme slug '{s}'. Slug must be lowercase letters, numbers, "
            "and hyphens, 1-64 characters, and cannot start with a hyphen."
        )
    return s


def _is_macosx_or_junk(name: str) -> bool:
    """Return True for resource-fork / macOS metadata paths that should be ignored."""
    return name.startswith("__MACOSX/") or os.path.basename(name) == ".DS_Store"


def _is_symlink(info: ZipInfo) -> bool:
    """Detect zip entries that are symlinks via Unix mode bits."""
    try:
        mode = (info.external_attr >> 16) & 0o170000
        return mode == 0o120000
    except Exception:
        return False


def _zip_info_is_dir(info: ZipInfo) -> bool:
    """Return True if the zip entry represents a directory.

    Python 3.10's ZipInfo.is_dir() only checks the trailing slash; on newer
    Pythons it also checks external_attr. We replicate the full check so it
    works across all supported versions.
    """
    if info.filename.endswith('/'):
        return True
    try:
        mode = (info.external_attr >> 16) & 0o170000
        return mode == 0o040000
    except Exception:
        return False


def _normalize_zip_name(name: str) -> str:
    """Return a normalized posix-style path or raise on absolute/traversal."""
    raw = name or ""
    if raw.startswith("/") or raw.startswith("\\"):
        raise ThemeInvalidArchiveError(f"Absolute path in zip: {name}")
    if len(raw) >= 2 and raw[1] == ":" and raw[0].isalpha():
        raise ThemeInvalidArchiveError(f"Windows absolute path in zip: {name}")
    clean = raw.replace("\\", "/").strip("/")
    if not clean:
        raise ThemeInvalidArchiveError("Empty path in zip")
    parts: List[str] = []
    for seg in clean.split("/"):
        if not seg or seg == ".":
            continue
        if seg == ".." or seg.startswith(".."):
            raise ThemeInvalidArchiveError(
                f"Path traversal in zip: {name}"
            )
        parts.append(seg)
    if not parts:
        raise ThemeInvalidArchiveError("Empty path in zip")
    return "/".join(parts)


def _find_manifest_root(zf: ZipFile) -> Tuple[str, Dict[str, Any]]:
    """Find the implicit directory prefix that contains theme.json.

    Returns the prefix (e.g. "" or "repo-main") and the parsed manifest. The
    zip is expected to have exactly one theme.json at the root of a single
    top-level directory, or at the root of the archive itself. We ignore
    macOS metadata paths when scanning.
    """
    candidates: List[Tuple[str, str]] = []  # (prefix, filename)
    for info in zf.infolist():
        if _is_macosx_or_junk(info.filename):
            continue
        normalized = _normalize_zip_name(info.filename)
        if normalized.lower() == "theme.json":
            candidates.append(("", info.filename))
            continue
        parts = normalized.split("/")
        if len(parts) == 2 and parts[1].lower() == "theme.json":
            candidates.append((parts[0], info.filename))

    if not candidates:
        raise ThemeInvalidManifestError("Missing theme.json in zip archive")
    if len(candidates) > 1:
        raise ThemeInvalidManifestError(
            "Multiple theme.json files found. Theme archive must contain exactly one theme.json."
        )

    prefix, manifest_name = candidates[0]
    try:
        raw = zf.read(manifest_name).decode("utf-8")
        data = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ThemeInvalidManifestError(f"Invalid theme.json: {e}") from e
    if not isinstance(data, dict):
        raise ThemeInvalidManifestError("theme.json must be a JSON object")
    return prefix, data


def _derive_slug(data: Dict[str, Any]) -> str:
    """Derive and validate the theme slug from the manifest."""
    slug = (data.get("slug") or "").strip().lower()
    if not slug:
        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ThemeInvalidManifestError(
                "theme.json must contain 'name' or 'slug'"
            )
        slug = _slug_from_name(name)
    return _validate_slug(slug)


def _collect_entries(
    zf: ZipFile, prefix: str
) -> Tuple[List[Tuple[ZipInfo, str]], int, int]:
    """Return (entries, total_uncompressed_bytes, file_count) after safety checks.

    Each entry is a tuple of (ZipInfo, normalized_path_without_prefix). Junk
    macOS entries are dropped. Raises on symlink, traversal, or size limits.
    """
    entries: List[Tuple[ZipInfo, str]] = []
    total_uncompressed = 0
    file_count = 0

    prefix_len = len(prefix) + 1 if prefix else 0
    seen: Set[str] = set()

    for info in zf.infolist():
        if _is_macosx_or_junk(info.filename):
            continue

        # Some zip tools write directory entries without a trailing slash.
        # Detect and skip them before treating them as files.
        if _zip_info_is_dir(info):
            continue

        normalized = _normalize_zip_name(info.filename)

        if prefix and not normalized.startswith(prefix + "/"):
            # A single stray file outside the prefix is a sign of a malformed archive.
            if not normalized.startswith("__MACOSX/"):
                raise ThemeInvalidArchiveError(
                    f"File outside theme folder '{prefix}': {info.filename}"
                )
            continue

        rel = normalized[prefix_len:] if prefix_len else normalized
        if rel == "" or rel.endswith("/"):
            continue

        # Must not already have processed this logical path
        if rel in seen:
            raise ThemeInvalidArchiveError(f"Duplicate zip entry: {rel}")
        seen.add(rel)

        if _is_symlink(info):
            raise ThemeInvalidArchiveError(f"Symlink not allowed in zip: {rel}")

        total_uncompressed += info.file_size or 0
        if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
            raise ThemeTooLargeError(
                f"Uncompressed contents exceed {MAX_UNCOMPRESSED_BYTES} bytes"
            )

        file_count += 1
        if file_count > MAX_FILES:
            raise ThemeTooLargeError(
                f"Archive contains more than {MAX_FILES} files"
            )

        entries.append((info, rel))

    return entries, total_uncompressed, file_count


def _advisory_warnings(dest: Path) -> List[str]:
    """Return non-blocking warnings about the installed theme tree."""
    warnings: List[str] = []

    css_dir = dest / "assets" / "css"
    if not css_dir.is_dir() or not list(css_dir.glob("skin-*.css")):
        warnings.append(
            "No assets/css/skin-*.css found. Theme may not render Traven content correctly."
        )

    for basename in ("post", "index", "page", "search"):
        found = False
        for ext in (".html.twig", ".twig", ".php"):
            if (dest / "templates" / f"{basename}{ext}").is_file():
                found = True
                break
        if not found:
            warnings.append(
                f"Missing template for {basename}.html.twig / .php"
            )

    return warnings


def install_from_zip(zip_bytes: bytes, overwrite: bool = False) -> Dict[str, Any]:
    """Validate and install a theme .zip into the global themes directory.

    Args:
        zip_bytes: Raw bytes of the uploaded .zip file.
        overwrite: If True, replace an existing theme directory with the same slug.

    Returns:
        dict with slug, name, version, overwrote, warnings.

    Raises:
        ThemeTooLargeError: Upload size or uncompressed size limit exceeded.
        ThemeInvalidArchiveError: Zip is malformed or unsafe.
        ThemeInvalidManifestError: theme.json is missing or invalid.
        ThemeExistsError: Slug already exists and overwrite is False.
    """
    if len(zip_bytes) > MAX_UPLOAD_BYTES:
        raise ThemeTooLargeError(
            f"Upload is {len(zip_bytes)} bytes; maximum allowed is {MAX_UPLOAD_BYTES} bytes"
        )

    try:
        zf = ZipFile(BytesIO(zip_bytes))
    except Exception as e:
        raise ThemeInvalidArchiveError(f"Not a valid zip file: {e}") from e

    with zf:
        prefix, manifest = _find_manifest_root(zf)
        slug = _derive_slug(manifest)

        entries, uncompressed_size, file_count = _collect_entries(zf, prefix)
        if not entries:
            raise ThemeInvalidArchiveError("Archive contains no installable files")

        dest = social_preview.themes_root() / slug
        backup_dir: Optional[Path] = None
        if dest.exists() and not overwrite:
            raise ThemeExistsError(f"Theme '{slug}' already exists")

        # Extract into a staging directory next to the destination so the final
        # rename is atomic-ish across the same filesystem.
        social_preview.themes_root().mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f"theme-{slug}-", dir=social_preview.themes_root()))
        try:
            for info, rel in entries:
                target = staging / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                # Re-check confinement after mkdir
                resolved = target.resolve()
                staging_s = str(staging.resolve())
                if str(resolved) != staging_s and not str(resolved).startswith(staging_s + os.sep):
                    raise ThemeInvalidArchiveError(
                        f"Resolved path escapes staging directory: {rel}"
                    )
                with zf.open(info) as src, open(resolved, "wb") as out:
                    shutil.copyfileobj(src, out)

            # Atomically write the manifest parent pointer to the staging root.
            manifest_path = staging / "theme.json"
            if manifest_path.is_file():
                # Ensure manifest has the derived slug if absent
                if "slug" not in manifest or not str(manifest.get("slug", "")).strip():
                    manifest["slug"] = slug
                    manifest_path.write_text(
                        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8",
                    )

            # Replace existing theme directory if requested
            if dest.exists() and overwrite:
                ts = int(time.time())
                backup_dir = social_preview.themes_root() / f"{slug}.bak-{ts}"
                dest.rename(backup_dir)

            # Move staging into place
            staging.rename(dest)

            if backup_dir and backup_dir.exists():
                shutil.rmtree(backup_dir)

        except Exception:
            # Best-effort cleanup and restore
            if backup_dir and backup_dir.exists() and not dest.exists():
                try:
                    backup_dir.rename(dest)
                except Exception:
                    pass
            if staging.exists():
                try:
                    shutil.rmtree(staging)
                except Exception:
                    pass
            raise

    warnings = _advisory_warnings(dest)
    logger.info(
        "Installed theme '%s' (%s files, %s bytes uncompressed, overwrite=%s)",
        slug,
        file_count,
        uncompressed_size,
        overwrite,
    )
    return {
        "slug": slug,
        "name": (manifest.get("name") or slug),
        "version": str(manifest.get("version") or "1.0.0"),
        "overwrote": dest.exists() and overwrite,  # if we got here, it was overwritten
        "warnings": warnings,
    }


def install_from_url(url: str, overwrite: bool = False) -> Dict[str, Any]:
    """Fetch a remote theme archive and install it via ``install_from_zip``."""
    from services.theme_url_fetch import download_zip_bytes, resolve_download_url

    download_url = resolve_download_url(url)
    zip_bytes = download_zip_bytes(download_url)
    return install_from_zip(zip_bytes, overwrite=overwrite)
