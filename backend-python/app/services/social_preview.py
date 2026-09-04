"""Theme defaults + sparse site overrides for Social / OG image settings.

Resolution order for maker and public meta consumers:
  site override → theme social_preview → ENGINE_DEFAULTS
"""

from __future__ import annotations

import configparser
import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Union

from config import BASE_DIR

# Flat string override keys stored sparsely on SiteRecord / sites.yaml.
SOCIAL_STRING_KEYS = (
    "og_accent_color",
    "og_vignette_color",
    "og_text_color",
    "og_bar_color",
    "og_font",
    "og_headline_style",
    "og_text_case",
    "og_grade_preset",
    "og_watermark",
    "og_watermark_source",
    "og_watermark_layout",
    "og_watermark_corner",
    "og_watermark_scale",
    "og_default_hero",
    "og_default_image",
    "og_fallback_title",
    "og_title_fallback",
    "og_description_fallback",
    "twitter_card",
)

SOCIAL_BOOL_KEYS = ("og_accent_bar", "og_watermark_enabled")

SOCIAL_OVERRIDE_KEYS = SOCIAL_STRING_KEYS + SOCIAL_BOOL_KEYS

HEADLINE_STYLES = frozenset(
    {
        "redacted",
        "shadow",
        "plain",
        "left",
        "left_redacted",
        "center",
        "center_redacted",
        "outline",
        "banner",
        "boxed",
        "underline",
        "caption",
        "poster",
    }
)

GRADE_PRESETS = frozenset(
    {
        "noir",
        "clean",
        "none",
        "vibrant",
        "warm",
        "cool",
        "fade",
        "high_contrast",
        "sepia",
        "mono",
        "dusk",
        "night",
        "paper",
    }
)

WATERMARK_SOURCES = frozenset({"theme", "logo", "custom"})
WATERMARK_LAYOUTS = frozenset({"full_canvas", "corner"})
WATERMARK_CORNERS = frozenset({"tl", "tr", "bl", "br"})
WATERMARK_SCALES = frozenset({"sm", "md", "lg"})

ENGINE_DEFAULTS: Dict[str, Any] = {
    "og_accent_color": "#C12929",
    "og_vignette_color": "#FF8000",
    "og_text_color": "#FFFFFF",
    "og_bar_color": "#000000",
    "og_font": "CourierPrime-Bold",
    "og_fonts": {"CourierPrime-Bold": "fonts/CourierPrime-Bold.ttf"},
    "og_headline_style": "redacted",
    "og_text_case": "upper",
    "og_grade_preset": "noir",
    "og_accent_bar": True,
    "og_watermark_enabled": True,
    "og_watermark": None,
    "og_watermark_source": None,
    "og_watermark_layout": "full_canvas",
    "og_watermark_corner": "br",
    "og_watermark_scale": "md",
    "og_default_hero": None,
    "og_default_image": None,
    "og_fallback_title": "ARCHIVAL RECORD",
    "og_title_fallback": None,
    "og_description_fallback": None,
    "twitter_card": "summary_large_image",
}


def themes_root() -> Path:
    """Resolve the themes directory from config.ini [theme] directory."""
    cp = configparser.ConfigParser()
    ini_path = BASE_DIR / "config.ini"
    if not ini_path.is_file():
        app_root_ini = Path(__file__).resolve().parents[2] / "config.ini"
        if app_root_ini.is_file():
            ini_path = app_root_ini
    cp.read(ini_path)
    raw = cp.get("theme", "directory", fallback="../frontend-php/src/blog/themes")
    path = Path(raw)
    if not path.is_absolute():
        resolved = (ini_path.parent / path).resolve()
        if resolved.is_dir():
            return resolved
        path = (BASE_DIR / path).resolve()
    return path


def install_active_theme() -> str:
    """Install-wide ``[theme] active`` fallback (default ``starter``)."""
    cp = configparser.ConfigParser()
    ini_path = BASE_DIR / "config.ini"
    if not ini_path.is_file():
        app_root_ini = Path(__file__).resolve().parents[2] / "config.ini"
        if app_root_ini.is_file():
            ini_path = app_root_ini
    cp.read(ini_path)
    raw = cp.get("theme", "active", fallback="starter").strip()
    return raw or "starter"


def theme_json_path(
    theme_name: str,
    site_id: Optional[str] = None,
) -> Path:
    """Path to theme.json for an install slug, or site custom when name is ``custom``.

    ``custom`` requires ``site_id`` and a valid site theme tree.
    """
    name = (theme_name or "starter").strip() or "starter"
    if name == "custom":
        if not site_id:
            raise ValueError("theme 'custom' requires site_id")
        from services.theme_customize_service import site_theme_root

        root = site_theme_root(site_id)
        path = root / "theme.json"
        if not root.is_dir() or not path.is_file():
            raise FileNotFoundError(
                f"Site '{site_id}' has no valid custom theme tree "
                f"(expected {root}/theme.json)"
            )
        return path
    return themes_root() / name / "theme.json"


def list_installed_themes(site_id: Optional[str] = None) -> list[Dict[str, str]]:
    """Scan themes_root for directories containing theme.json.

    Returns ``[{"id": "<slug>", "label": "<name or slug>"}]`` sorted by id.
    Missing or unreadable theme.json still yields the directory slug as label.
    Skips leading-underscore dirs (``_deprecated``, ``_asset-kits``, …)
    and the reserved install slug ``custom``.

    When ``site_id`` is set and that site has a valid ``theme/`` tree, appends
    ``{id: "custom", label, source: "site", parent}`` for that site only.
    """
    root = themes_root()
    out: list[Dict[str, str]] = []
    if root.is_dir():
        for child in sorted(root.iterdir(), key=lambda p: p.name.lower()):
            if not child.is_dir() or child.name.startswith("_"):
                continue
            if child.name == "custom":
                continue
            meta_path = child / "theme.json"
            if not meta_path.is_file():
                continue
            label = child.name
            try:
                data = json.loads(meta_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    name = data.get("name")
                    if isinstance(name, str) and name.strip():
                        label = name.strip()
            except (OSError, json.JSONDecodeError):
                pass
            out.append({"id": child.name, "label": label})

    if site_id:
        from services.theme_customize_service import custom_theme_list_entry

        entry = custom_theme_list_entry(site_id)
        if entry is not None:
            out.append(entry)
    return out


def scan_installed_themes_detail() -> list[Dict[str, Any]]:
    """Full install-theme metadata for the admin Theme Settings UI.

    Mirrors the PHP scan in ``admin-settings-theme.php``. Skips leading-underscore
    dirs and the reserved install slug ``custom``.
    """
    root = themes_root()
    out: list[Dict[str, Any]] = []
    if not root.is_dir():
        return out
    for child in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if not child.is_dir() or child.name.startswith("_") or child.name == "custom":
            continue
        meta_path = child / "theme.json"
        if not meta_path.is_file():
            continue
        slug = child.name
        theme_data: Dict[str, Any] = {}
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                theme_data = data
        except (OSError, json.JSONDecodeError):
            pass
        supports = theme_data.get("supports")
        if not isinstance(supports, list):
            supports = []
        out.append(
            {
                "slug": slug,
                "name": theme_data.get("name") or slug,
                "version": theme_data.get("version") or "1.0.0",
                "author": theme_data.get("author") or "Unknown",
                "description": theme_data.get("description") or "No description provided.",
                "color_mode": theme_data.get("color_mode") or "both",
                "supports": supports,
                "has_screenshot": (child / "screenshot.webp").is_file(),
            }
        )
    return out


def load_theme_social_preview(
    theme_name: Optional[str],
    site_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Load the theme's social_preview block (empty dict if missing)."""
    name = theme_name or "starter"
    try:
        path = theme_json_path(name, site_id=site_id)
    except (ValueError, FileNotFoundError, OSError):
        return {}
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    block = data.get("social_preview")
    if not isinstance(block, dict):
        return {}
    return dict(block)


def _site_override_value(site: Any, key: str) -> Any:
    if site is None:
        return None
    if isinstance(site, Mapping):
        return site.get(key)
    return getattr(site, key, None)


def effective_theme_name(site: Any) -> str:
    """Site theme override, else install active, else ``starter``."""
    stored = _site_override_value(site, "theme")
    if isinstance(stored, str) and stored.strip():
        return stored.strip()
    return install_active_theme()


def site_social_overrides(site: Any) -> Dict[str, Any]:
    """Return only keys that are explicitly set on the site record."""
    out: Dict[str, Any] = {}
    for key in SOCIAL_STRING_KEYS:
        val = _site_override_value(site, key)
        if val is None:
            continue
        text = str(val).strip()
        if text:
            out[key] = text
    for key in SOCIAL_BOOL_KEYS:
        val = _site_override_value(site, key)
        if val is None:
            continue
        if isinstance(val, bool):
            out[key] = val
        else:
            text = str(val).strip().lower()
            if text in ("true", "1", "yes", "on"):
                out[key] = True
            elif text in ("false", "0", "no", "off"):
                out[key] = False
    return out


def merge_social_preview(
    theme_block: Mapping[str, Any],
    overrides: Mapping[str, Any],
) -> Dict[str, Any]:
    """Merge engine ← theme ← site overrides into a complete config dict."""
    merged: Dict[str, Any] = dict(ENGINE_DEFAULTS)
    for key, val in theme_block.items():
        if key == "og_fonts":
            if isinstance(val, dict) and val:
                merged["og_fonts"] = dict(val)
            continue
        if val is None:
            continue
        if isinstance(val, str) and not val.strip():
            continue
        merged[key] = val
    for key, val in overrides.items():
        if key == "og_fonts":
            continue
        if val is None:
            continue
        if isinstance(val, str) and not val.strip():
            continue
        merged[key] = val
    if not isinstance(merged.get("og_fonts"), dict):
        merged["og_fonts"] = dict(ENGINE_DEFAULTS["og_fonts"])
    return merged


def _site_id_of(site: Any) -> Optional[str]:
    val = _site_override_value(site, "id")
    if isinstance(val, str) and val.strip():
        return val.strip()
    return None


def apply_social_draft(site: Any, draft: Mapping[str, Any]) -> Dict[str, Any]:
    """Copy a site record into a mapping and overlay sparse Social draft fields.

    Does not persist. Empty string / null on a present key means inherit theme
    (clears a saved override for this resolution only). Absent keys keep the
    saved site values.
    """
    if isinstance(site, Mapping):
        out: Dict[str, Any] = dict(site)
    elif hasattr(site, "to_dict"):
        out = dict(site.to_dict())
    else:
        out = {}
        sid = _site_id_of(site)
        if sid:
            out["id"] = sid
        theme = _site_override_value(site, "theme")
        if theme:
            out["theme"] = theme
    for key in SOCIAL_STRING_KEYS:
        if key not in draft:
            continue
        val = draft[key]
        if val is None or (isinstance(val, str) and not str(val).strip()):
            out.pop(key, None)
        else:
            out[key] = str(val).strip()
    for key in SOCIAL_BOOL_KEYS:
        if key not in draft:
            continue
        val = draft[key]
        if val is None:
            out.pop(key, None)
        else:
            out[key] = bool(val)
    return out


def resolve_social_preview(
    site: Any,
    *,
    theme_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Full resolved Social/OG config for a site record or mapping."""
    theme = theme_name
    if not theme:
        theme = _site_override_value(site, "theme")
    if not theme:
        theme = install_active_theme()
    site_id = _site_id_of(site)
    theme_block = load_theme_social_preview(str(theme), site_id=site_id)
    overrides = site_social_overrides(site)
    return merge_social_preview(theme_block, overrides)


def theme_social_preview_defaults(
    theme_name: Optional[str],
    site_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Theme block merged over engine defaults (no site overrides) for admin UI."""
    return merge_social_preview(
        load_theme_social_preview(theme_name, site_id=site_id),
        {},
    )
