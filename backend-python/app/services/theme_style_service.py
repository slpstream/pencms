"""Per-site theme style overrides backed by theme.json schemas."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config import BASE_DIR
from services.site_service import get_site, update_site
from services.theme_customize_service import resolve_theme_dir
import services.social_preview as social_preview

_COLOR_RE = re.compile(
    r"^(?:#[0-9a-fA-F]{3,8}|"
    r"rgb\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)|"
    r"rgba\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*(?:0?\.\d+|1(\.0)?)\s*\)|"
    r"hsl\(\s*\d+\s*,\s*\d+%?\s*,\s*\d+%?\s*\)|"
    r"hsla\(\s*\d+\s*,\s*\d+%?\s*,\s*\d+%?\s*,\s*(?:0?\.\d+|1(\.0)?)\s*\))$"
)

# Cached registry select options: list[{"value": stack, "label": label}]
_REGISTRY_FONT_OPTIONS: Optional[List[Dict[str, str]]] = None


class StyleOverrideError(ValueError):
    """Raised for invalid style override payloads."""


def font_registry_path() -> Path:
    """Resolve ``frontend-php/public/assets/fonts/fonts.json``.

    Prefer a path derived from ``[theme] directory``; fall back to the
    conventional sibling of ``backend-python/``.
    """
    try:
        root = social_preview.themes_root()
        candidate = root.parents[2] / "public" / "assets" / "fonts" / "fonts.json"
        if candidate.is_file():
            return candidate
    except Exception:
        pass
    return (BASE_DIR / "../frontend-php/public/assets/fonts/fonts.json").resolve()


def _load_registry_font_options() -> List[Dict[str, str]]:
    """Return sorted ``{value, label}`` options from the central font registry."""
    global _REGISTRY_FONT_OPTIONS
    if _REGISTRY_FONT_OPTIONS is not None:
        return _REGISTRY_FONT_OPTIONS

    options: List[Dict[str, str]] = []
    path = font_registry_path()
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
        if isinstance(data, dict):
            for entry in data.values():
                if not isinstance(entry, dict):
                    continue
                stack = entry.get("stack")
                label = entry.get("label") or entry.get("family")
                if isinstance(stack, str) and stack.strip() and isinstance(label, str) and label.strip():
                    options.append({"value": stack, "label": label})
            options.sort(key=lambda o: o["label"].lower())

    _REGISTRY_FONT_OPTIONS = options
    return options


def reset_font_registry_cache() -> None:
    """Test helper: clear the cached registry options."""
    global _REGISTRY_FONT_OPTIONS
    _REGISTRY_FONT_OPTIONS = None


def _is_font_select_field(field: Dict[str, Any]) -> bool:
    if field.get("type") != "select":
        return False
    fid = str(field.get("id") or "").lower()
    var = str(field.get("var") or "").lower()
    return fid.startswith("font") or "font" in var


def _merge_registry_into_font_select(field: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of ``field`` with registry stacks appended (deduped by value)."""
    out = copy.deepcopy(field)
    existing = out.get("options")
    if not isinstance(existing, list):
        existing = []
    seen: set[str] = set()
    merged: List[Dict[str, str]] = []
    for opt in existing:
        if not isinstance(opt, dict):
            continue
        value = opt.get("value")
        label = opt.get("label")
        if not isinstance(value, str) or not isinstance(label, str):
            continue
        if value in seen:
            continue
        seen.add(value)
        merged.append({"value": value, "label": label})
    for opt in _load_registry_font_options():
        if opt["value"] in seen:
            continue
        seen.add(opt["value"])
        merged.append({"value": opt["value"], "label": opt["label"]})
    out["options"] = merged
    return out


def _enrich_style_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Deep-copy schema and merge the central font registry into font selects."""
    enriched = copy.deepcopy(schema)
    groups = enriched.get("groups")
    if not isinstance(groups, list):
        return enriched
    for group in groups:
        if not isinstance(group, dict):
            continue
        fields = group.get("fields")
        if not isinstance(fields, list):
            continue
        group["fields"] = [
            _merge_registry_into_font_select(f)
            if isinstance(f, dict) and _is_font_select_field(f)
            else f
            for f in fields
        ]
    return enriched


def _load_style_schema(theme_dir: Path) -> Optional[Dict[str, Any]]:
    """Read the ``style`` schema from a theme's theme.json, if present.

    Font ``select`` fields are enriched with the full central font registry so
    operators see every registry family without hand-curating each theme.json.
    """
    manifest_path = theme_dir / "theme.json"
    if not manifest_path.is_file():
        return None
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    schema = data.get("style")
    if not isinstance(schema, dict):
        return None
    if not isinstance(schema.get("groups"), list) or not schema["groups"]:
        return None
    return _enrich_style_schema(schema)


def _build_field_index(
    schema: Dict[str, Any], *, dark: bool = False
) -> Dict[str, Dict[str, Any]]:
    """Map field id -> field definition. When ``dark`` is True, only include
    fields that declare a ``dark_default``."""
    index: Dict[str, Dict[str, Any]] = {}
    for group in schema.get("groups", []):
        if not isinstance(group, dict):
            continue
        for field in group.get("fields", []):
            if not isinstance(field, dict):
                continue
            fid = field.get("id")
            if not isinstance(fid, str) or not fid.strip():
                continue
            if dark and "dark_default" not in field:
                continue
            index[fid] = field
    return index


def _validate_value(field: Dict[str, Any], value: str) -> Optional[str]:
    """Return an error message if ``value`` is invalid for ``field``."""
    if value == "":
        return None
    ftype = field.get("type")
    if ftype == "color":
        if not _COLOR_RE.match(value.strip()):
            return f"Invalid color value for {field.get('id')}"
    elif ftype == "select":
        allowed = {
            opt.get("value")
            for opt in field.get("options", [])
            if isinstance(opt, dict)
        }
        if value not in allowed:
            return f"Invalid option for {field.get('id')}"
    return None


def _filter_overrides(
    overrides: Dict[str, Any], index: Dict[str, Dict[str, Any]]
) -> Tuple[Dict[str, str], List[str]]:
    """Validate a map of override values against a field index.

    Returns the filtered non-empty values and a list of validation errors.
    """
    filtered: Dict[str, str] = {}
    errors: List[str] = []
    for key, value in overrides.items():
        if not isinstance(key, str) or not key.strip():
            errors.append("Override key must be a non-empty string")
            continue
        field = index.get(key)
        if field is None:
            errors.append(f"Unknown style override: {key}")
            continue
        if not isinstance(value, str):
            errors.append(f"Value for {key} must be a string")
            continue
        err = _validate_value(field, value)
        if err:
            errors.append(err)
            continue
        if value != "":
            filtered[key] = value
    return filtered, errors


def _sanitize_string_map(raw: Any) -> Dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    return {
        str(k): str(v)
        for k, v in raw.items()
        if isinstance(k, (str, int)) and isinstance(v, str)
    }


def get_style_settings(site_id: str) -> Dict[str, Any]:
    """Return the style schema + stored overrides for a site's effective theme."""
    site = get_site(site_id)
    if site is None:
        raise ValueError(f"Unknown site_id: {site_id}")

    theme = social_preview.effective_theme_name(site)
    saved_for_theme: Optional[str] = None
    stored_values: Dict[str, str] = {}
    stored_dark: Dict[str, str] = {}

    stored = site.style_overrides
    if isinstance(stored, dict) and stored.get("theme") == theme:
        saved_for_theme = theme
        stored_values = _sanitize_string_map(stored.get("values"))
        stored_dark = _sanitize_string_map(stored.get("dark"))

    try:
        theme_dir = resolve_theme_dir(site_id, theme_name=theme)
        schema = _load_style_schema(theme_dir)
    except Exception:
        schema = None

    values: Dict[str, str] = {}
    dark_values: Dict[str, str] = {}
    if schema:
        index = _build_field_index(schema)
        dark_index = _build_field_index(schema, dark=True)
        for k, v in stored_values.items():
            if k in index:
                values[k] = v
        for k, v in stored_dark.items():
            if k in dark_index:
                dark_values[k] = v

    return {
        "theme": theme,
        "schema": schema,
        "values": values,
        "dark_values": dark_values,
        "saved_for_theme": saved_for_theme,
    }


def set_style_overrides(site_id: str, values: Any, dark: Any) -> Dict[str, Any]:
    """Validate and persist style overrides for a site's effective theme."""
    site = get_site(site_id)
    if site is None:
        raise ValueError(f"Unknown site_id: {site_id}")

    theme = social_preview.effective_theme_name(site)

    try:
        theme_dir = resolve_theme_dir(site_id, theme_name=theme)
        schema = _load_style_schema(theme_dir)
    except Exception as exc:
        raise StyleOverrideError(
            f"Cannot load style schema for theme '{theme}': {exc}"
        )

    if schema is None:
        raise StyleOverrideError(f"Theme '{theme}' does not expose style settings")

    index = _build_field_index(schema)
    dark_index = _build_field_index(schema, dark=True)

    if not isinstance(values, dict):
        values = {}
    if not isinstance(dark, dict):
        dark = {}

    light_filtered, light_errors = _filter_overrides(values, index)
    dark_filtered, dark_errors = _filter_overrides(dark, dark_index)

    errors = light_errors + dark_errors
    if errors:
        raise StyleOverrideError("; ".join(errors))

    # Light overrides are emitted under :root !important. If a paired dark
    # value is missing, that light color leaks into dark mode. Pin the schema
    # dark_default whenever light is customized and dark was left untouched.
    for key, field in dark_index.items():
        if key not in light_filtered or key in dark_filtered:
            continue
        dark_default = field.get("dark_default")
        if not isinstance(dark_default, str) or dark_default == "":
            continue
        err = _validate_value(field, dark_default)
        if err:
            continue
        dark_filtered[key] = dark_default

    payload = {
        "theme": theme,
        "values": light_filtered,
        "dark": dark_filtered,
    }
    update_site(site_id, style_overrides=payload)
    return get_style_settings(site_id)


def _clean_override_map(block: Any) -> Dict[str, str]:
    if not isinstance(block, dict):
        return {}
    cleaned: Dict[str, str] = {}
    for key, value in block.items():
        if not isinstance(key, (str, int)) or not isinstance(value, str):
            continue
        key_text = str(key).strip()
        if not key_text or value == "":
            continue
        cleaned[key_text] = value
    return cleaned


def rekey_style_overrides_for_fork(
    stored: Any,
    parent_slug: str,
    *,
    target_theme: str = "custom",
) -> Optional[Dict[str, Any]]:
    """Re-key parent-theme style overrides to ``custom`` after a theme fork.

    Only migrates when ``stored.theme`` matches the fork parent slug so
    cross-theme override pollution cannot occur.
    """
    if not isinstance(stored, dict):
        return None
    parent = (parent_slug or "").strip()
    if not parent or stored.get("theme") != parent:
        return None

    values = _clean_override_map(stored.get("values"))
    dark = _clean_override_map(stored.get("dark"))
    if not values and not dark:
        return None

    target = (target_theme or "").strip() or "custom"
    return {"theme": target, "values": values, "dark": dark}
