"""Package site themes for distribution (zip download / local install).

Site export copies the effective theme tree (custom fork or install theme),
bakes Style Settings into ``theme.json`` + skin CSS, vendors registry fonts,
and produces a standalone installable base. Raw install-theme export skips baking.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from zipfile import ZIP_DEFLATED, ZipFile

import services.social_preview as social_preview
from services.site_service import get_site
from services.theme_customize_service import resolve_theme_dir
from services.theme_install_service import (
    RESERVED_THEME_ID,
    ThemeExistsError,
    ThemeInstallError,
    ThemeInvalidManifestError,
    ThemeTooLargeError,
    _advisory_warnings,
    _validate_slug,
    MAX_FILES,
    MAX_UNCOMPRESSED_BYTES,
    MAX_UPLOAD_BYTES,
)
from services.theme_style_service import (
    _build_field_index,
    _enrich_style_schema,
    _filter_overrides,
    _sanitize_string_map,
    font_registry_path,
)

logger = logging.getLogger("pencms.theme_package")

PACKAGED_CSS_MARKER_START = "/* === PenCMS packaged style defaults (do not edit) === */"
PACKAGED_CSS_MARKER_END = "/* === end PenCMS packaged style defaults === */"
PACKAGED_FONTS_MARKER_START = "/* === PenCMS packaged registry fonts === */"
PACKAGED_FONTS_MARKER_END = "/* === end PenCMS packaged registry fonts === */"

CARD_SCREENSHOT_SETTLE_S = 0.4
CARD_SCREENSHOT_WEBP_QUALITY = 80
SCREENSHOT_WARNING_PREFIX = "Screenshot capture skipped:"

# System stacks that do not need vendored files.
_SYSTEM_FONT_HINTS = (
    "georgia",
    "times new roman",
    "serif",
    "sans-serif",
    "monospace",
    "ui-monospace",
    "system-ui",
    "-apple-system",
    "blinkmacsystemfont",
    "segoe ui",
    "courier new",
    "liberation mono",
)


class ThemePackageError(ValueError):
    """Raised for invalid package operations."""


@dataclass
class PreparedPackageTree:
    """Temp directory containing ``{slug}/``; caller must rmtree ``root``."""

    root: Path
    slug: str
    warnings: List[str] = field(default_factory=list)


def _png_to_webp(png: bytes, dest: Path, *, quality: int = CARD_SCREENSHOT_WEBP_QUALITY) -> None:
    """Write PNG bytes as WebP (admin theme cards use screenshot.webp)."""
    try:
        from PIL import Image
    except ImportError as e:
        raise ThemePackageError("Pillow is required for screenshot.webp export") from e
    dest.parent.mkdir(parents=True, exist_ok=True)
    img = Image.open(BytesIO(png))
    img.save(dest, "WEBP", quality=quality, method=6)


def _capture_homepage_png(site_id: str) -> bytes:
    """Navigate the live site homepage and return viewport PNG bytes."""
    from services.theme_render_inspect_service import (
        capture_png_on_page,
        invoke_inspect,
        open_inspect_page,
    )

    def _run() -> bytes:
        with open_inspect_page(
            site_id=site_id,
            path="/blog/",
            viewport="desktop",
            block_media=False,
        ) as page:
            if CARD_SCREENSHOT_SETTLE_S > 0:
                time.sleep(CARD_SCREENSHOT_SETTLE_S)
            return capture_png_on_page(page, full_page=False)

    return invoke_inspect(_run)


def capture_theme_card_webp(site_id: str, dest: Path) -> Optional[str]:
    """Capture the live site homepage and write ``screenshot.webp``.

    Returns a warning string on failure; never raises. On failure the dest file
    is not created (any stale copy should be removed by the caller first).
    """
    from services.theme_render_inspect_service import ThemeRenderInspectError

    try:
        png = _capture_homepage_png(site_id)
        _png_to_webp(png, dest)
        logger.info("Captured theme card screenshot for site %s → %s", site_id, dest)
        return None
    except ThemeRenderInspectError as exc:
        msg = f"{SCREENSHOT_WARNING_PREFIX} {exc.reason}"
        if exc.hint:
            msg = f"{msg} ({exc.hint})"
        logger.warning("Theme package screenshot failed for %s: %s", site_id, exc.reason)
        return msg
    except Exception as exc:
        logger.warning(
            "Theme package screenshot failed for %s: %s",
            site_id,
            exc,
            exc_info=True,
        )
        return f"{SCREENSHOT_WARNING_PREFIX} {exc}"


def _recapture_staging_screenshot(site_id: str, staging: Path) -> List[str]:
    """Remove any copied screenshot and recapture from the live site."""
    shot_path = staging / "screenshot.webp"
    if shot_path.is_file():
        shot_path.unlink()
    warning = capture_theme_card_webp(site_id, shot_path)
    return [warning] if warning else []


def _is_macosx_or_junk(rel: str) -> bool:
    return rel.startswith("__MACOSX/") or os.path.basename(rel) == ".DS_Store"


def _load_manifest(theme_dir: Path) -> Dict[str, Any]:
    path = theme_dir / "theme.json"
    if not path.is_file():
        raise ThemePackageError("theme.json is missing")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        raise ThemePackageError(f"Invalid theme.json: {e}") from e
    if not isinstance(data, dict):
        raise ThemePackageError("theme.json must be a JSON object")
    return data


def _write_manifest(theme_dir: Path, data: Dict[str, Any]) -> None:
    (theme_dir / "theme.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _find_skin_css(theme_dir: Path) -> Optional[Path]:
    css_dir = theme_dir / "assets" / "css"
    if not css_dir.is_dir():
        return None
    skins = sorted(css_dir.glob("skin-*.css"))
    return skins[0] if skins else None


def _strip_packaged_block(content: str, start: str, end: str) -> str:
    """Remove a previously packaged marker block if present."""
    while True:
        i = content.find(start)
        if i < 0:
            break
        j = content.find(end, i)
        if j < 0:
            content = content[:i].rstrip() + "\n"
            break
        j += len(end)
        content = (content[:i] + content[j:]).strip() + "\n"
    return content


def _load_font_registry() -> Dict[str, Dict[str, Any]]:
    path = font_registry_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _registry_fonts_root() -> Path:
    return font_registry_path().parent


def _is_system_font_stack(stack: str) -> bool:
    lowered = stack.lower()
    # Empty or theme-default sentinel
    if not lowered.strip():
        return True
    # Pure system stacks without quoted family names
    if "'" not in lowered and '"' not in lowered:
        return True
    for hint in _SYSTEM_FONT_HINTS:
        if hint in lowered and "'" not in lowered.split(hint)[0][-3:]:
            # Heuristic: if stack is only system fonts
            pass
    # If every quoted family is absent from registry, may still be system
    registry = _load_font_registry()
    for entry in registry.values():
        if not isinstance(entry, dict):
            continue
        reg_stack = entry.get("stack")
        if isinstance(reg_stack, str) and reg_stack.strip() == stack.strip():
            return False
    # No registry match → treat as system / theme-local already
    return True


def _match_registry_entry(stack: str, registry: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    target = stack.strip()
    if not target:
        return None
    for entry in registry.values():
        if not isinstance(entry, dict):
            continue
        reg_stack = entry.get("stack")
        if isinstance(reg_stack, str) and reg_stack.strip() == target:
            return entry
    return None


def _collect_style_overrides(site_id: str, effective_theme: str) -> Tuple[Dict[str, str], Dict[str, str]]:
    site = get_site(site_id)
    if site is None:
        return {}, {}
    stored = site.style_overrides
    if not isinstance(stored, dict):
        return {}, {}
    stored_theme = stored.get("theme")
    if stored_theme != effective_theme:
        return {}, {}
    return (
        _sanitize_string_map(stored.get("values")),
        _sanitize_string_map(stored.get("dark")),
    )


def _build_packaged_style_css(
    schema: Dict[str, Any],
    values: Dict[str, str],
    dark: Dict[str, str],
) -> str:
    """Mirror ThemeEngine::buildStyleOverridesCss for baked defaults."""
    index = _build_field_index(schema)
    if not index:
        return ""

    # Pin dark_default when light customized but dark omitted (same as style service)
    dark_work = dict(dark)
    for fid, value in values.items():
        field = index.get(fid)
        if not field or fid in dark_work:
            continue
        if "dark_default" not in field:
            continue
        dark_default = field.get("dark_default")
        if isinstance(dark_default, str) and dark_default != "":
            dark_work[fid] = dark_default

    light_rules: List[str] = []
    for fid, value in values.items():
        if not value:
            continue
        field = index.get(fid)
        if not field:
            continue
        var = field.get("var")
        if not isinstance(var, str) or not var:
            continue
        light_rules.append(f"  {var}: {value} !important;")

    dark_index = _build_field_index(schema, dark=True)
    dark_rules: List[str] = []
    for fid, value in dark_work.items():
        if not value:
            continue
        field = dark_index.get(fid)
        if not field:
            continue
        var = field.get("var")
        if not isinstance(var, str) or not var:
            continue
        dark_rules.append(f"  {var}: {value} !important;")

    if not light_rules and not dark_rules:
        return ""

    css_parts: List[str] = []
    if light_rules:
        css_parts.append(":root {\n" + "\n".join(light_rules) + "\n}")
    if dark_rules:
        dark_scope = schema.get("dark_scope") if isinstance(schema.get("dark_scope"), dict) else {}
        selector = dark_scope.get("selector") if isinstance(dark_scope, dict) else None
        media = dark_scope.get("media") if isinstance(dark_scope, dict) else None
        if isinstance(selector, str) and selector.strip():
            css_parts.append(f"{selector.strip()} {{\n" + "\n".join(dark_rules) + "\n}}")
        elif isinstance(media, str) and media.strip():
            css_parts.append(
                f"@media {media.strip()} {{\n  :root {{\n"
                + "\n".join(dark_rules)
                + "\n  }\n}"
            )
        else:
            css_parts.append(":root {\n" + "\n".join(dark_rules) + "\n}")

    return "\n".join(css_parts)


def _bake_style_into_manifest(
    manifest: Dict[str, Any],
    values: Dict[str, str],
    dark: Dict[str, str],
) -> Dict[str, Any]:
    schema = manifest.get("style")
    if not isinstance(schema, dict):
        return manifest
    enriched = _enrich_style_schema(schema)
    light_index = _build_field_index(enriched)
    dark_index = _build_field_index(enriched, dark=True)

    light_filtered, _ = _filter_overrides(values, light_index)
    dark_filtered, _ = _filter_overrides(dark, dark_index)

    # Pin dark defaults for light-only customizations
    for fid, value in light_filtered.items():
        field = dark_index.get(fid)
        if not field or fid in dark_filtered:
            continue
        dark_default = field.get("dark_default")
        if isinstance(dark_default, str) and dark_default != "":
            dark_filtered[fid] = dark_default

    for group in enriched.get("groups", []):
        if not isinstance(group, dict):
            continue
        for field in group.get("fields", []):
            if not isinstance(field, dict):
                continue
            fid = field.get("id")
            if not isinstance(fid, str):
                continue
            if fid in light_filtered:
                field["default"] = light_filtered[fid]
            if fid in dark_filtered and "dark_default" in field:
                field["dark_default"] = dark_filtered[fid]

    manifest["style"] = enriched
    return manifest


def _vendor_registry_fonts(
    theme_dir: Path,
    manifest: Dict[str, Any],
    values: Dict[str, str],
    dark: Dict[str, str],
) -> Tuple[Dict[str, Any], str]:
    """Copy registry font files and return @font-face CSS block."""
    schema = manifest.get("style")
    if not isinstance(schema, dict):
        return manifest, ""

    enriched = _enrich_style_schema(schema)
    index = _build_field_index(enriched)
    registry = _load_font_registry()
    if not registry:
        return manifest, ""

    stacks: Set[str] = set()
    for fid, field in index.items():
        if field.get("type") != "select":
            continue
        fid_lower = str(field.get("id") or "").lower()
        var_lower = str(field.get("var") or "").lower()
        if not (fid_lower.startswith("font") or "font" in var_lower):
            continue
        for store in (values, dark):
            val = store.get(fid)
            if isinstance(val, str) and val.strip() and not _is_system_font_stack(val):
                entry = _match_registry_entry(val, registry)
                if entry:
                    stacks.add(val.strip())

    if not stacks:
        return manifest, ""

    fonts_dir = theme_dir / "assets" / "fonts"
    fonts_dir.mkdir(parents=True, exist_ok=True)
    registry_root = _registry_fonts_root()
    face_rules: List[str] = []
    copied_any = False

    for stack in sorted(stacks):
        entry = _match_registry_entry(stack, registry)
        if not entry:
            continue
        family = entry.get("family") or entry.get("label") or "Font"
        if not isinstance(family, str):
            family = "Font"
        files = entry.get("files")
        if not isinstance(files, dict):
            continue
        for weight_key, filename in files.items():
            if not isinstance(filename, str) or not filename.strip():
                continue
            src = registry_root / filename
            if not src.is_file():
                continue
            dest_name = filename
            dest = fonts_dir / dest_name
            if not dest.exists():
                shutil.copy2(src, dest)
                copied_any = True
            weight = 400
            style = "normal"
            wk = str(weight_key)
            if wk.endswith("i"):
                style = "italic"
                wk = wk[:-1]
            try:
                weight = int(wk)
            except ValueError:
                weight = 400
            face_rules.append(
                "@font-face {\n"
                f"  font-family: {family!r};\n"
                f"  font-style: {style};\n"
                f"  font-weight: {weight};\n"
                "  font-display: swap;\n"
                f"  src: url('../fonts/{dest_name}') format('woff2');\n"
                "}"
            )

    if not copied_any and not face_rules:
        return manifest, ""

    supports = manifest.get("supports")
    if not isinstance(supports, dict):
        supports = {}
        manifest["supports"] = supports
    supports["custom_fonts"] = True

    css_block = ""
    if face_rules:
        css_block = (
            PACKAGED_FONTS_MARKER_START
            + "\n"
            + "\n\n".join(face_rules)
            + "\n"
            + PACKAGED_FONTS_MARKER_END
            + "\n"
        )
    return manifest, css_block


def _apply_packaged_css(skin_path: Path, style_css: str, font_css: str) -> None:
    content = skin_path.read_text(encoding="utf-8")
    content = _strip_packaged_block(content, PACKAGED_FONTS_MARKER_START, PACKAGED_FONTS_MARKER_END)
    content = _strip_packaged_block(content, PACKAGED_CSS_MARKER_START, PACKAGED_CSS_MARKER_END)

    append_parts: List[str] = []
    if font_css.strip():
        append_parts.append(font_css.rstrip())
    if style_css.strip():
        append_parts.append(
            PACKAGED_CSS_MARKER_START
            + "\n"
            + style_css.rstrip()
            + "\n"
            + PACKAGED_CSS_MARKER_END
        )
    if append_parts:
        content = content.rstrip() + "\n\n" + "\n\n".join(append_parts) + "\n"
    skin_path.write_text(content, encoding="utf-8")


def _finalize_standalone_manifest(
    manifest: Dict[str, Any],
    slug: str,
    name: Optional[str],
    author: Optional[str],
) -> Dict[str, Any]:
    for key in ("parent", "origin", "customized_at"):
        manifest.pop(key, None)
    manifest["slug"] = slug
    if name and name.strip():
        manifest["name"] = name.strip()
    elif not manifest.get("name"):
        manifest["name"] = slug
    if author and author.strip():
        manifest["author"] = author.strip()
    if not manifest.get("license"):
        manifest["license"] = "MIT"
    if not manifest.get("version"):
        manifest["version"] = "1.0.0"
    return manifest


def _copy_theme_tree(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(
        src,
        dest,
        ignore=shutil.ignore_patterns("__MACOSX", ".DS_Store"),
        dirs_exist_ok=False,
    )


def _iter_theme_files(theme_dir: Path) -> List[Tuple[Path, str]]:
    """Return (absolute_path, relative_posix_path) for all files under theme_dir."""
    files: List[Tuple[Path, str]] = []
    root = theme_dir.resolve()
    for dirpath, dirnames, filenames in os.walk(root):
        # Skip junk dirs
        dirnames[:] = [d for d in dirnames if d != "__MACOSX" and d != ".DS_Store"]
        for fname in filenames:
            if fname == ".DS_Store":
                continue
            abs_path = Path(dirpath) / fname
            rel = abs_path.relative_to(root).as_posix()
            if _is_macosx_or_junk(rel):
                continue
            if abs_path.is_symlink():
                raise ThemePackageError(f"Symlinks are not allowed: {rel}")
            files.append((abs_path, rel))
    return files


def _check_package_size(files: List[Tuple[Path, str]]) -> None:
    total = 0
    count = 0
    for abs_path, _rel in files:
        total += abs_path.stat().st_size
        if total > MAX_UNCOMPRESSED_BYTES:
            raise ThemeTooLargeError(
                f"Package contents exceed {MAX_UNCOMPRESSED_BYTES} bytes uncompressed"
            )
        count += 1
        if count > MAX_FILES:
            raise ThemeTooLargeError(f"Package contains more than {MAX_FILES} files")


def _zip_theme_dir(theme_dir: Path, slug: str) -> bytes:
    files = _iter_theme_files(theme_dir)
    if not files:
        raise ThemePackageError("Theme directory is empty")
    _check_package_size(files)

    buf = BytesIO()
    with ZipFile(buf, "w", ZIP_DEFLATED) as zf:
        for abs_path, rel in files:
            arcname = f"{slug}/{rel}"
            zf.write(abs_path, arcname)
    data = buf.getvalue()
    if len(data) > MAX_UPLOAD_BYTES:
        raise ThemeTooLargeError(
            f"Zip is {len(data)} bytes; maximum allowed is {MAX_UPLOAD_BYTES} bytes"
        )
    if not data:
        raise ThemePackageError("Generated zip is empty")
    return data


def _prepare_packaged_tree(
    site_id: str,
    slug: str,
    *,
    name: Optional[str] = None,
    author: Optional[str] = None,
    bake: bool = True,
) -> PreparedPackageTree:
    """Build a packaged theme tree in a temp directory; caller must rmtree."""
    validated_slug = _validate_slug(slug)

    site = get_site(site_id)
    if site is None:
        raise ThemePackageError(f"Unknown site_id: {site_id}")

    effective_theme = social_preview.effective_theme_name(site)
    try:
        source = resolve_theme_dir(site_id, theme_name=effective_theme)
    except Exception as e:
        raise ThemePackageError(str(e)) from e

    staging_parent = Path(tempfile.mkdtemp(prefix="pencms-theme-package-"))
    staging = staging_parent / validated_slug
    try:
        _copy_theme_tree(source, staging)

        manifest = _load_manifest(staging)
        values: Dict[str, str] = {}
        dark: Dict[str, str] = {}
        if bake:
            values, dark = _collect_style_overrides(site_id, effective_theme)
            if values or dark:
                manifest = _bake_style_into_manifest(manifest, values, dark)

        manifest, font_css = _vendor_registry_fonts(staging, manifest, values, dark)
        schema = manifest.get("style")
        style_css = ""
        if bake and isinstance(schema, dict) and (values or dark):
            style_css = _build_packaged_style_css(schema, values, dark)
        skin = _find_skin_css(staging)
        if skin and (style_css or font_css):
            _apply_packaged_css(skin, style_css, font_css)

        manifest = _finalize_standalone_manifest(manifest, validated_slug, name, author)
        _write_manifest(staging, manifest)

        package_warnings = _recapture_staging_screenshot(site_id, staging)
        return PreparedPackageTree(
            root=staging_parent,
            slug=validated_slug,
            warnings=package_warnings,
        )
    except Exception:
        if staging_parent.exists():
            shutil.rmtree(staging_parent, ignore_errors=True)
        raise


def build_site_package_zip(
    site_id: str,
    slug: str,
    *,
    name: Optional[str] = None,
    author: Optional[str] = None,
) -> Tuple[bytes, str, List[str]]:
    """Package the site's effective theme and return (zip_bytes, filename, warnings)."""
    validated_slug = _validate_slug(slug)
    prepared = _prepare_packaged_tree(
        site_id, validated_slug, name=name, author=author, bake=True
    )
    try:
        staging = prepared.root / prepared.slug
        data = _zip_theme_dir(staging, validated_slug)
        filename = f"{validated_slug}.zip"
        logger.info(
            "Packaged site theme for %s as %s (%s bytes)",
            site_id,
            validated_slug,
            len(data),
        )
        return data, filename, prepared.warnings
    finally:
        shutil.rmtree(prepared.root, ignore_errors=True)


def install_site_package(
    site_id: str,
    slug: str,
    *,
    name: Optional[str] = None,
    author: Optional[str] = None,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """Write a packaged site theme into the global install themes directory."""
    validated_slug = _validate_slug(slug)
    prepared = _prepare_packaged_tree(
        site_id, validated_slug, name=name, author=author, bake=True
    )
    try:
        staging = prepared.root / prepared.slug
        dest = social_preview.themes_root() / validated_slug
        did_exist = dest.exists()
        if did_exist and not overwrite:
            raise ThemeExistsError(f"Theme '{validated_slug}' already exists")

        social_preview.themes_root().mkdir(parents=True, exist_ok=True)
        backup_dir: Optional[Path] = None
        install_staging = Path(
            tempfile.mkdtemp(prefix=f"theme-{validated_slug}-", dir=social_preview.themes_root())
        )
        try:
            _copy_theme_tree(staging, install_staging)
            if did_exist and overwrite:
                ts = int(time.time())
                backup_dir = social_preview.themes_root() / f"{validated_slug}.bak-{ts}"
                dest.rename(backup_dir)
            install_staging.rename(dest)
            if backup_dir and backup_dir.exists():
                shutil.rmtree(backup_dir)
        except Exception:
            if backup_dir and backup_dir.exists() and not dest.exists():
                try:
                    backup_dir.rename(dest)
                except Exception:
                    pass
            if install_staging.exists():
                shutil.rmtree(install_staging, ignore_errors=True)
            raise

        manifest = _load_manifest(dest)
        warnings = _advisory_warnings(dest) + list(prepared.warnings)
        logger.info(
            "Installed packaged theme '%s' for site %s (overwrite=%s)",
            validated_slug,
            site_id,
            overwrite,
        )
        return {
            "slug": validated_slug,
            "name": manifest.get("name") or validated_slug,
            "version": str(manifest.get("version") or "1.0.0"),
            "overwrote": bool(did_exist and overwrite),
            "warnings": warnings,
        }
    finally:
        shutil.rmtree(prepared.root, ignore_errors=True)


def export_installed_theme_zip(theme_slug: str) -> Tuple[bytes, str]:
    """Zip an installed theme directory without baking (raw export)."""
    slug = _validate_slug(theme_slug)
    if slug == RESERVED_THEME_ID:
        raise ThemeInvalidManifestError(
            f"Cannot export reserved theme identifier '{RESERVED_THEME_ID}'"
        )
    theme_dir = social_preview.themes_root() / slug
    if not theme_dir.is_dir() or not (theme_dir / "theme.json").is_file():
        raise ThemePackageError(f"Theme '{slug}' is not installed")

    data = _zip_theme_dir(theme_dir, slug)
    filename = f"{slug}.zip"
    logger.info("Exported installed theme '%s' (%s bytes)", slug, len(data))
    return data, filename
