"""File-backed UI string overrides for the admin translation workspace."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from config import content_storage
from services.file_service import get_site_language_config, join_site_path
from services.i18n_service import (
    ContentI18nError,
    normalize_requested_language,
)
from services.theme_customize_service import resolve_theme_dir


UI_STRING_KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")
ENGINE_DEFAULTS_PATH = (
    Path(__file__).resolve().parents[3]
    / "frontend-php"
    / "src"
    / "core"
    / "i18n"
    / "strings.json"
)


class UiStringsError(ValueError):
    """A UI string dictionary is malformed or unavailable."""


def _validate_map(raw: Any, *, location: str) -> dict[str, str]:
    if not isinstance(raw, Mapping):
        raise UiStringsError(
            f"{location}: top-level value must be a JSON object. "
            "Fix: provide a flat object of string keys and string values."
        )
    values: dict[str, str] = {}
    for key, value in raw.items():
        if (
            not isinstance(key, str)
            or UI_STRING_KEY_RE.fullmatch(key) is None
            or not isinstance(value, str)
        ):
            raise UiStringsError(
                f"{location}: key '{key}' must use a flat string value and a valid "
                "identifier. Fix: use keys matching "
                "[A-Za-z][A-Za-z0-9_.-]* and string values."
            )
        values[key] = value
    return values


def _decode_map(raw: str, *, location: str) -> dict[str, str]:
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise UiStringsError(
            f"{location}: invalid JSON: {exc.msg}. "
            "Fix: provide a flat object of string keys and string values."
        ) from exc
    return _validate_map(decoded, location=location)


def _load_local_map(path: Path, *, required: bool = False) -> dict[str, str]:
    if not path.is_file():
        if required:
            raise UiStringsError(
                f"{path}: file is missing. "
                "Fix: restore the engine UI string dictionary."
            )
        return {}
    return _decode_map(path.read_text(encoding="utf-8"), location=str(path))


def _site_strings_path(site_id: str, language: str) -> str:
    return join_site_path(site_id, "strings", f"{language}.json")


async def _load_site_map(site_id: str, language: str) -> dict[str, str]:
    path = _site_strings_path(site_id, language)
    if not await content_storage.exists(path):
        return {}
    return _decode_map(await content_storage.read(path), location=path)


async def resolve_ui_strings(
    site_id: str,
    language: str | None = None,
) -> dict[str, Any]:
    """Return effective strings, layer sources, and exact sparse overrides."""
    from services.translation_service import translation_config

    config = get_site_language_config(site_id)
    requested = normalize_requested_language(language, config)
    engine = _load_local_map(ENGINE_DEFAULTS_PATH, required=True)
    resolved = dict(engine)
    sources = {key: "engine" for key in engine}
    overrides: dict[str, str] = {}

    if config.active:
        theme_path = resolve_theme_dir(site_id) / "strings.json"
        theme = _load_local_map(theme_path)
        default_site = await _load_site_map(site_id, config.language)
        target_site = (
            {}
            if requested == config.language
            else await _load_site_map(site_id, requested)
        )
        layers = [
            ("theme", theme),
            ("site_default", default_site),
            ("site_target", target_site),
        ]
        for source, values in layers:
            for key, value in values.items():
                resolved[key] = value
                sources[key] = source
        overrides = default_site if requested == config.language else target_site

    strings = {
        key: {
            "effective": resolved[key],
            "source": sources[key],
            "override": overrides.get(key),
        }
        for key in sorted(resolved)
    }
    return {
        "config": translation_config(site_id),
        "language": requested,
        "strings": strings,
        "overrides": dict(sorted(overrides.items())),
    }


async def replace_ui_string_overrides(
    site_id: str,
    language: str,
    overrides: Mapping[str, Any],
) -> dict[str, Any]:
    """Replace one language's sparse site file; omitted keys reset fallback."""
    config = get_site_language_config(site_id)
    if not config.active:
        raise ContentI18nError(
            f"Site '{site_id}' i18n is inactive. Fix: configure at least two "
            "unique languages including the default language before editing UI strings."
        )
    requested = normalize_requested_language(language, config)
    values = _validate_map(overrides, location=f"UI string overrides ({requested})")
    path = _site_strings_path(site_id, requested)

    await content_storage.begin_transaction()
    try:
        if values:
            payload = json.dumps(
                dict(sorted(values.items())),
                ensure_ascii=False,
                indent=2,
            ) + "\n"
            await content_storage.write(path, payload)
        elif await content_storage.exists(path):
            await content_storage.delete(path)
        await content_storage.end_transaction(
            f"Update {site_id} UI strings ({requested})"
        )
    except Exception:
        await content_storage.cancel_transaction()
        raise

    return await resolve_ui_strings(site_id, requested)
