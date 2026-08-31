"""Per-site AI prompts and guardrails (data/ai-settings/{site_id}.json)."""

from __future__ import annotations

import json
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional

import config
from services.localization_policy_service import (
    POLICY_KEY,
    default_localization_policy,
    normalize_localization_policy,
)

DEFAULT_AI_SETTINGS: Dict[str, Any] = {
    "ai_publish_autonomy": "require_approval",
    "ai_metadata_scope": "allow_metadata",
    "text_generation_prompt": "",
    "image_generation_prompt": "",
    "post_quality_checklist": "",
    POLICY_KEY: default_localization_policy(),
}

VALID_AUTONOMY = frozenset({"autonomous", "require_approval", "restricted"})
VALID_SCOPE = frozenset({"allow_metadata", "body_only"})


def _data_dir() -> Path:
    return config.BASE_DIR / "data"


def legacy_settings_path() -> Path:
    return _data_dir() / "ai-settings.json"


def settings_path_for_site(site_id: str) -> Path:
    return _data_dir() / "ai-settings" / f"{site_id}.json"


def _read_json_file(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            return raw
    except Exception:
        pass
    return None


def migrate_legacy_ai_settings_if_needed() -> None:
    """Move install-global ``data/ai-settings.json`` → ``data/ai-settings/default.json``.

    Only runs when the legacy file exists and the default site file does not.
    Other sites are unaffected (they keep DEFAULT_AI_SETTINGS until first save).
    """
    legacy = legacy_settings_path()
    default_path = settings_path_for_site("default")
    if not legacy.exists() or default_path.exists():
        return
    default_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(legacy), str(default_path))
    except Exception:
        # Fall back to copy+unlink so a partial move cannot leave both missing.
        data = _read_json_file(legacy)
        if data is None:
            return
        with open(default_path, "w", encoding="utf-8") as f:
            json.dump({**DEFAULT_AI_SETTINGS, **data}, f, indent=2)
        try:
            legacy.unlink()
        except OSError:
            pass


def load_ai_settings(site_id: str) -> Dict[str, Any]:
    """Return merged AI settings for ``site_id`` (defaults for missing keys/files)."""
    migrate_legacy_ai_settings_if_needed()
    data = deepcopy(DEFAULT_AI_SETTINGS)
    stored = _read_json_file(settings_path_for_site(site_id))
    if stored:
        data.update(
            {
                k: deepcopy(stored[k])
                for k in DEFAULT_AI_SETTINGS
                if k in stored
            }
        )
    return data


def save_ai_settings(
    site_id: str,
    settings: Dict[str, Any],
    *,
    validate_localization_bindings: bool = True,
) -> Dict[str, Any]:
    """Validate and persist AI settings for ``site_id``. Returns the saved document."""
    migrate_legacy_ai_settings_if_needed()
    existing = load_ai_settings(site_id)

    autonomy = settings.get("ai_publish_autonomy", existing.get("ai_publish_autonomy"))
    scope = settings.get("ai_metadata_scope", existing.get("ai_metadata_scope"))
    text_prompt = settings.get(
        "text_generation_prompt", existing.get("text_generation_prompt", "")
    )
    image_prompt = settings.get(
        "image_generation_prompt", existing.get("image_generation_prompt", "")
    )
    checklist = settings.get(
        "post_quality_checklist", existing.get("post_quality_checklist", "")
    )
    localization_policy = settings.get(POLICY_KEY, existing.get(POLICY_KEY))

    if autonomy not in VALID_AUTONOMY:
        raise ValueError(f"Invalid ai_publish_autonomy value. Allowed: {set(VALID_AUTONOMY)}")
    if scope not in VALID_SCOPE:
        raise ValueError(f"Invalid ai_metadata_scope value. Allowed: {set(VALID_SCOPE)}")
    from services.file_service import get_site_language_config

    language_config = get_site_language_config(site_id)
    localization_policy = normalize_localization_policy(
        site_id,
        localization_policy,
        default_language=language_config.language,
        configured_languages=language_config.languages,
        validate_bindings=validate_localization_bindings,
    )

    to_save = {
        "ai_publish_autonomy": autonomy,
        "ai_metadata_scope": scope,
        "text_generation_prompt": text_prompt if text_prompt is not None else "",
        "image_generation_prompt": image_prompt if image_prompt is not None else "",
        "post_quality_checklist": checklist if checklist is not None else "",
        POLICY_KEY: localization_policy,
    }

    path = settings_path_for_site(site_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(to_save, f, indent=2)

    # Drop legacy install file if it somehow still exists after migrate.
    legacy = legacy_settings_path()
    if legacy.exists() and site_id == "default":
        try:
            legacy.unlink()
        except OSError:
            pass

    return to_save


def agent_house_facts(site_id: str) -> Dict[str, Any]:
    """Sitename + agent guardrails for Glowbot / MCP site-config (no secrets)."""
    from services.site_service import get_site

    record = get_site(site_id)
    sitename = None
    if record is not None:
        raw = (record.sitename or "").strip()
        sitename = raw or None

    settings = load_ai_settings(site_id)
    autonomy = settings.get("ai_publish_autonomy") or "require_approval"
    if autonomy not in VALID_AUTONOMY:
        autonomy = "require_approval"
    metadata = settings.get("ai_metadata_scope") or "allow_metadata"
    if metadata not in VALID_SCOPE:
        metadata = "allow_metadata"
    return {
        "sitename": sitename,
        "ai_publish_autonomy": autonomy,
        "ai_metadata_scope": metadata,
    }
