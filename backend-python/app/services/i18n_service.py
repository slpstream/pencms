"""Per-site language configuration and activation gate.

This module is the sole semantic BCP-47 normalization and validation path.
Other runtimes consume the normalized registry values.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any
from uuid import uuid4

import langcodes
from langcodes.tag_parser import LanguageTagError


DEFAULT_LANGUAGE = "en"
TRANSLATION_GROUP_RE = re.compile(r"^tg_[0-9a-f]{32}$")


class ContentI18nError(ValueError):
    """A file-backed i18n invariant failed."""


@dataclass(frozen=True)
class ContentIdentity:
    site_id: str
    slug: str
    language: str
    is_default: bool
    filepath: str


@dataclass(frozen=True)
class LanguageConfig:
    language: str
    languages: list[str]
    language_labels: dict[str, str]
    translation_automation_paused: bool

    @property
    def active(self) -> bool:
        return len(self.languages) >= 2 and self.language in self.languages


def normalize_language_tag(value: Any, *, field: str = "language") -> str:
    """Return a known, canonical lowercase BCP-47 tag."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty BCP-47 language tag")

    raw = value.strip()
    try:
        if not langcodes.tag_is_valid(raw):
            raise ValueError(
                f"Invalid or unknown BCP-47 language tag '{raw}' in {field}"
            )
        return langcodes.standardize_tag(raw).lower()
    except (LanguageTagError, ValueError) as exc:
        if isinstance(exc, ValueError) and str(exc).startswith("Invalid or unknown"):
            raise
        raise ValueError(
            f"Invalid or unknown BCP-47 language tag '{raw}' in {field}"
        ) from exc


def _normalize_languages(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ValueError("languages must be an ordered list of BCP-47 language tags")

    normalized: list[str] = []
    seen: set[str] = set()
    for index, value in enumerate(values):
        tag = normalize_language_tag(value, field=f"languages[{index}]")
        if tag in seen:
            raise ValueError(
                f"Duplicate language tag '{tag}' in languages after normalization"
            )
        seen.add(tag)
        normalized.append(tag)
    return normalized


def _normalize_language_labels(values: Any) -> dict[str, str]:
    if values is None:
        return {}
    if not isinstance(values, Mapping):
        raise ValueError("language_labels must be an object keyed by BCP-47 tag")

    normalized: dict[str, str] = {}
    for raw_tag, raw_label in values.items():
        tag = normalize_language_tag(raw_tag, field="language_labels key")
        if tag in normalized:
            raise ValueError(
                f"Duplicate language label key '{tag}' after normalization"
            )
        if not isinstance(raw_label, str) or not raw_label.strip():
            raise ValueError(f"language_labels['{tag}'] must be a non-empty string")
        normalized[tag] = raw_label.strip()
    return normalized


def normalize_language_config(
    *,
    language: Any = DEFAULT_LANGUAGE,
    languages: Any = None,
    language_labels: Any = None,
    translation_automation_paused: Any = False,
) -> LanguageConfig:
    """Validate and normalize one site's complete language configuration."""
    normalized_default = normalize_language_tag(language)
    normalized_languages = _normalize_languages(languages)
    normalized_labels = _normalize_language_labels(language_labels)

    if normalized_languages and normalized_default not in normalized_languages:
        raise ValueError(
            "languages must include the default language "
            f"'{normalized_default}' when the list is not empty"
        )
    if not isinstance(translation_automation_paused, bool):
        raise ValueError("translation_automation_paused must be a boolean")

    return LanguageConfig(
        language=normalized_default,
        languages=normalized_languages,
        language_labels=normalized_labels,
        translation_automation_paused=translation_automation_paused,
    )


def is_i18n_active(
    language: Any = DEFAULT_LANGUAGE,
    languages: Any = None,
) -> bool:
    """Return the locked activation rule for a validated site config."""
    return normalize_language_config(
        language=language,
        languages=languages,
    ).active


def normalize_requested_language(
    value: Any,
    config: LanguageConfig,
    *,
    field: str = "language",
) -> str:
    """Resolve an optional request language against one site's config."""
    if value is None or value == "":
        return config.language
    language = normalize_language_tag(value, field=field)
    if language == config.language:
        return language
    if not config.active:
        raise ContentI18nError(
            f"{field} '{language}' cannot be used because i18n is inactive. "
            "Fix: configure at least two languages including the default language first."
        )
    if language not in config.languages:
        raise ContentI18nError(
            f"{field} '{language}' is not configured for this site. "
            f"Fix: use one of: {', '.join(config.languages)}."
        )
    return language


def new_translation_group() -> str:
    """Return a stable opaque identifier suitable for Markdown frontmatter."""
    return f"tg_{uuid4().hex}"


def validate_translation_group(value: Any, *, filepath: str) -> str:
    if not isinstance(value, str) or not TRANSLATION_GROUP_RE.fullmatch(value):
        raise ContentI18nError(
            f"{filepath}: translation_group must use the generated 'tg_<32 hex>' "
            "format. Create the sibling through the sibling service or copy the "
            "exact translation_group from its default-language peer."
        )
    return value


def content_identity_from_path(
    rel_path: str,
    *,
    site_id: str,
    site_prefix: str,
    config: LanguageConfig,
) -> ContentIdentity:
    """Parse a canonical content path using Pattern B.

    Default files remain ``{slug}/index.md`` (or legacy ``{slug}.md``).
    Active non-default siblings are ``{slug}/{lang}/index.md``.
    """
    normalized = rel_path.replace("\\", "/").strip("/")
    prefix = site_prefix.replace("\\", "/").strip("/")
    if normalized == prefix:
        relative = ""
    elif normalized.startswith(f"{prefix}/"):
        relative = normalized[len(prefix) + 1 :]
    else:
        raise ContentI18nError(
            f"{rel_path}: file is outside the configured site root '{site_prefix}'."
        )

    parts = [part for part in relative.split("/") if part]
    if len(parts) == 1 and parts[0].endswith(".md"):
        slug = parts[0][:-3]
        identity = ContentIdentity(
            site_id=site_id,
            slug=slug,
            language=config.language,
            is_default=True,
            filepath=normalized,
        )
    elif len(parts) == 2 and parts[1] == "index.md":
        identity = ContentIdentity(
            site_id=site_id,
            slug=parts[0],
            language=config.language,
            is_default=True,
            filepath=normalized,
        )
    elif len(parts) == 3 and parts[2] == "index.md":
        slug, raw_language, _ = parts
        try:
            language = normalize_language_tag(
                raw_language, field=f"locale folder in {rel_path}"
            )
        except ValueError as exc:
            raise ContentI18nError(
                f"{rel_path}: '{raw_language}' is not a valid locale folder. "
                "Fix: use a configured normalized BCP-47 language code."
            ) from exc
        if not config.active:
            raise ContentI18nError(
                f"{rel_path}: locale folders are ignored while i18n is inactive. "
                "Fix: enable at least two configured languages before adding siblings."
            )
        if language != raw_language:
            raise ContentI18nError(
                f"{rel_path}: locale folder must be normalized as '{language}'. "
                f"Fix: rename '{raw_language}' to '{language}'."
            )
        if language == config.language:
            raise ContentI18nError(
                f"{rel_path}: the default language '{language}' must stay at "
                f"'{slug}/index.md'. Fix: remove the default-language subfolder."
            )
        if language not in config.languages:
            raise ContentI18nError(
                f"{rel_path}: language '{language}' is not configured for this site. "
                f"Fix: use one of: {', '.join(config.languages)}."
            )
        identity = ContentIdentity(
            site_id=site_id,
            slug=slug,
            language=language,
            is_default=False,
            filepath=normalized,
        )
    else:
        raise ContentI18nError(
            f"{rel_path}: unsupported content path. Use '{site_prefix}/<slug>/index.md' "
            "for the default language or "
            f"'{site_prefix}/<slug>/<lang>/index.md' for a translation. "
            "Fix: move the index to one of those canonical locations."
        )

    if config.active and identity.slug in config.languages:
        raise ContentI18nError(
            f"{rel_path}: slug '{identity.slug}' shadows a configured language code. "
            "Fix: rename the content slug or remove that language from the site config."
        )
    return identity


def manifest_partial_ids(metadata: Mapping[str, Any]) -> list[str]:
    """Return ordered composite partial IDs, excluding the controller body."""
    raw_items = metadata.get("posts")
    if raw_items is None:
        raw_items = metadata.get("articles")
    if not isinstance(raw_items, list):
        return []
    ids: list[str] = []
    for item in raw_items:
        if not isinstance(item, Mapping):
            continue
        value = item.get("id")
        if value and value != "index":
            ids.append(str(value))
    return ids


def is_live_translation(metadata: Mapping[str, Any]) -> bool:
    """Return whether a row is currently eligible for merged public reads.

    Public liveness is ``status == published`` with a non-future ``publish_at``.
    The boolean ``published`` flag is not part of this contract. Translation
    rows pending review are withheld even when status is published.
    """
    if bool(metadata.get("needs_review", False)):
        return False
    if metadata.get("status", "published") != "published":
        return False
    publish_at = metadata.get("publish_at")
    if not publish_at:
        return True
    if not isinstance(publish_at, str):
        return False
    candidate = publish_at.replace("Z", "+00:00") if publish_at.endswith("Z") else publish_at
    try:
        scheduled = datetime.fromisoformat(candidate)
    except ValueError:
        return False
    if scheduled.tzinfo is None:
        scheduled = scheduled.replace(tzinfo=timezone.utc)
    return scheduled.astimezone(timezone.utc) <= datetime.now(timezone.utc)
