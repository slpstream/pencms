"""Site registry for Option C multisite (one install, many sites).

Registry: ``{BASE_DIR}/data/sites.yaml``. Content roots live under
``{content_dir}/sites/{site_id}/``. On first boot, existing flat content is
migrated into ``sites/default/``.
"""

from __future__ import annotations

import logging
import re
import secrets
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import frontmatter
import yaml
from fastapi import Depends, HTTPException, Request

from services.i18n_service import (
    DEFAULT_LANGUAGE,
    normalize_language_config,
)

logger = logging.getLogger("pencms.sites")

SITE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")
INDEXNOW_KEY_RE = re.compile(r"^[A-Za-z0-9-]{8,128}$")
DEFAULT_SITE_ID = "default"
DEFAULT_NEW_SITE_THEME = "starter"
DEFAULT_FEEDBACK_RELAY_URL = "https://feedback.pencms.org"
HUMAN_SITE_HEADER = "X-Pen-Site-Id"
HUMAN_SITE_COOKIE = "pen_site_id"

# Non-secret publish target fields persisted under site.publish in sites.yaml.
_PUBLISH_SHARED_KEYS: Set[str] = {
    "provider",
    "host",
    "port",
    "username",
    "remote_path",
    "auth_method",
    "public_url",
    "last_published_at",
    "last_status",
    "agent_publish",
    "webhook_url",
    # Write-only HMAC signing secret (never returned by GET payloads).
    "webhook_secret",
}


def publish_allowed_keys() -> Set[str]:
    """Shared keys plus yaml_fields of every registered publish adapter."""
    keys = set(_PUBLISH_SHARED_KEYS)
    from services.publish_providers.registry import registered_provider_classes

    for cls in registered_provider_classes():
        keys.update(cls().yaml_fields())
    return keys


# Rejected on write — host secrets never land in YAML (vault / Deploy Grant later).
PUBLISH_SECRET_KEYS: Set[str] = {
    "password",
    "pass",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "private_key",
    "ssh_pass",
    "sftp_pass",
}
PUBLISH_AUTH_METHODS = frozenset({"password", "key", "token"})
PUBLISH_LAST_STATUSES = frozenset({"ok", "failed", "never"})
PUBLISH_AGENT_PUBLISH = frozenset({"off", "enrolled"})


@dataclass
class SiteRecord:
    id: str
    name: str
    domain: Optional[str] = None
    content_relpath: str = ""
    language: str = DEFAULT_LANGUAGE
    languages: List[str] = field(default_factory=list)
    language_labels: Dict[str, str] = field(default_factory=dict)
    translation_automation_paused: bool = False
    theme: Optional[str] = None
    sitename: Optional[str] = None
    display_logo: Optional[bool] = None
    comments_enabled: Optional[bool] = None
    tagline: Optional[str] = None
    hero_title: Optional[str] = None
    hero_image: Optional[str] = None
    contact_email: Optional[str] = None
    title_template: Optional[str] = None
    meta_description: Optional[str] = None
    keywords: Optional[str] = None
    robots_index: Optional[bool] = None
    robots_follow: Optional[bool] = None
    robots_txt: Optional[str] = None
    sitemap_enabled: Optional[bool] = None
    google_site_verification: Optional[str] = None
    bing_site_verification: Optional[str] = None
    indexnow_enabled: Optional[bool] = None
    indexnow_key: Optional[str] = None
    content_signal_ai_train: Optional[bool] = None
    seo_redirects: Optional[List[Dict[str, str]]] = None
    # Social Previews — sparse site overrides (empty/null = inherit theme)
    og_accent_color: Optional[str] = None
    og_vignette_color: Optional[str] = None
    og_text_color: Optional[str] = None
    og_bar_color: Optional[str] = None
    og_font: Optional[str] = None
    og_headline_style: Optional[str] = None
    og_text_case: Optional[str] = None
    og_grade_preset: Optional[str] = None
    og_accent_bar: Optional[bool] = None
    og_watermark_enabled: Optional[bool] = None
    og_watermark: Optional[str] = None
    og_watermark_source: Optional[str] = None
    og_watermark_layout: Optional[str] = None
    og_watermark_corner: Optional[str] = None
    og_watermark_scale: Optional[str] = None
    og_default_hero: Optional[str] = None
    og_default_image: Optional[str] = None
    og_fallback_title: Optional[str] = None
    og_title_fallback: Optional[str] = None
    og_description_fallback: Optional[str] = None
    twitter_card: Optional[str] = None
    social_links: Optional[List[Dict[str, Any]]] = None
    style_overrides: Optional[Dict[str, Any]] = None
    publish: Optional[Dict[str, Any]] = None
    feedback_relay_url: Optional[str] = None
    feedback_submission_key: Optional[str] = None
    feedback_fetch_token: Optional[str] = None
    feedback_relay_cursor: Optional[str] = None

    def to_dict(self) -> dict:
        d: Dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "content_relpath": self.content_relpath or f"sites/{self.id}",
            "language": self.language,
            "languages": list(self.languages),
            "language_labels": dict(self.language_labels),
            "translation_automation_paused": self.translation_automation_paused,
        }
        if self.domain:
            d["domain"] = self.domain
        if self.theme:
            d["theme"] = self.theme
        if self.sitename:
            d["sitename"] = self.sitename
        if self.display_logo is not None:
            d["display_logo"] = self.display_logo
        if self.comments_enabled is not None:
            d["comments_enabled"] = self.comments_enabled
        if self.tagline:
            d["tagline"] = self.tagline
        if self.hero_title:
            d["hero_title"] = self.hero_title
        if self.hero_image:
            d["hero_image"] = self.hero_image
        if self.contact_email:
            d["contact_email"] = self.contact_email
        if self.title_template:
            d["title_template"] = self.title_template
        if self.meta_description:
            d["meta_description"] = self.meta_description
        if self.keywords:
            d["keywords"] = self.keywords
        if self.robots_index is not None:
            d["robots_index"] = self.robots_index
        if self.robots_follow is not None:
            d["robots_follow"] = self.robots_follow
        if self.robots_txt:
            d["robots_txt"] = self.robots_txt
        if self.sitemap_enabled is not None:
            d["sitemap_enabled"] = self.sitemap_enabled
        if self.google_site_verification:
            d["google_site_verification"] = self.google_site_verification
        if self.bing_site_verification:
            d["bing_site_verification"] = self.bing_site_verification
        if self.indexnow_enabled is not None:
            d["indexnow_enabled"] = self.indexnow_enabled
        if self.indexnow_key:
            d["indexnow_key"] = self.indexnow_key
        if self.content_signal_ai_train is not None:
            d["content_signal_ai_train"] = self.content_signal_ai_train
        if self.seo_redirects:
            d["seo_redirects"] = [dict(item) for item in self.seo_redirects]
        if self.og_accent_color:
            d["og_accent_color"] = self.og_accent_color
        if self.og_vignette_color:
            d["og_vignette_color"] = self.og_vignette_color
        if self.og_text_color:
            d["og_text_color"] = self.og_text_color
        if self.og_bar_color:
            d["og_bar_color"] = self.og_bar_color
        if self.og_font:
            d["og_font"] = self.og_font
        if self.og_headline_style:
            d["og_headline_style"] = self.og_headline_style
        if self.og_text_case:
            d["og_text_case"] = self.og_text_case
        if self.og_grade_preset:
            d["og_grade_preset"] = self.og_grade_preset
        if self.og_accent_bar is not None:
            d["og_accent_bar"] = self.og_accent_bar
        if self.og_watermark_enabled is not None:
            d["og_watermark_enabled"] = self.og_watermark_enabled
        if self.og_watermark:
            d["og_watermark"] = self.og_watermark
        if self.og_watermark_source:
            d["og_watermark_source"] = self.og_watermark_source
        if self.og_watermark_layout:
            d["og_watermark_layout"] = self.og_watermark_layout
        if self.og_watermark_corner:
            d["og_watermark_corner"] = self.og_watermark_corner
        if self.og_watermark_scale:
            d["og_watermark_scale"] = self.og_watermark_scale
        if self.og_default_hero:
            d["og_default_hero"] = self.og_default_hero
        if self.og_default_image:
            d["og_default_image"] = self.og_default_image
        if self.og_fallback_title:
            d["og_fallback_title"] = self.og_fallback_title
        if self.og_title_fallback:
            d["og_title_fallback"] = self.og_title_fallback
        if self.og_description_fallback:
            d["og_description_fallback"] = self.og_description_fallback
        if self.twitter_card:
            d["twitter_card"] = self.twitter_card
        if self.social_links:
            d["social_links"] = self.social_links
        if self.style_overrides:
            d["style_overrides"] = self.style_overrides
        if self.publish:
            d["publish"] = dict(self.publish)
        if self.feedback_relay_url:
            d["feedback_relay_url"] = self.feedback_relay_url
        if self.feedback_submission_key:
            d["feedback_submission_key"] = self.feedback_submission_key
        if self.feedback_fetch_token:
            d["feedback_fetch_token"] = self.feedback_fetch_token
        if self.feedback_relay_cursor:
            d["feedback_relay_cursor"] = self.feedback_relay_cursor
        return d


def normalize_domain(raw: Optional[str]) -> Optional[str]:
    """Normalize a public hostname for registry storage / Host matching.

    Lowercase; strip scheme, path, port, trailing dot; reject empty.
    Returns None for empty/whitespace input.
    """
    if raw is None:
        return None
    value = raw.strip().lower()
    if not value:
        return None
    # Strip scheme
    if "://" in value:
        value = value.split("://", 1)[1]
    # Strip path / query / fragment
    value = value.split("/")[0].split("?")[0].split("#")[0]
    # Strip port
    if value.startswith("["):
        # IPv6 literal [::1]:port — keep bracket form without port
        end = value.find("]")
        if end != -1:
            value = value[: end + 1]
        else:
            value = value.rstrip(".")
    elif ":" in value:
        value = value.rsplit(":", 1)[0]
    value = value.rstrip(".")
    if not value:
        return None
    return value


def mint_indexnow_key() -> str:
    """32-char hex IndexNow key (spec allows 8–128 alphanumeric / hyphen)."""
    return secrets.token_hex(16)


def mint_feedback_submission_key() -> str:
    """Public 32-char hex queue routing key (16 bytes)."""
    return secrets.token_hex(16)


def mint_feedback_fetch_token() -> str:
    """Private 64-char hex drain token (32 bytes)."""
    return secrets.token_hex(32)


def normalize_feedback_relay_url(raw: Optional[str]) -> Optional[str]:
    """http(s) origin with no trailing slash, or None if empty."""
    text = _optional_str(raw)
    if text is None:
        return None
    text = text.rstrip("/")
    lower = text.lower()
    if not (lower.startswith("http://") or lower.startswith("https://")):
        raise ValueError("feedback_relay_url must be an http:// or https:// URL")
    return text


def resolve_feedback_relay_url(
    site: Optional["SiteRecord"] = None,
    *,
    url: Optional[str] = None,
) -> str:
    """Relay origin for sync/register/bake. Empty site field → default origin."""
    raw = url
    if raw is None and site is not None:
        raw = site.feedback_relay_url
    cleaned = normalize_feedback_relay_url(raw)
    return cleaned or DEFAULT_FEEDBACK_RELAY_URL


def _resolve_indexnow_key(
    *,
    enabled: bool,
    incoming: Any,
    existing: Optional[str],
) -> Optional[str]:
    """Mint, keep, set, or clear the per-site IndexNow key.

    Empty incoming while enabled regenerates. Missing incoming keeps existing
    unless enabling with no key yet.
    """
    if incoming is _UNSET:
        cleaned = existing
        if enabled and not cleaned:
            return mint_indexnow_key()
        return cleaned if cleaned else None
    sanitized = sanitize_indexnow_key(
        None if incoming is None else str(incoming)
    )
    if sanitized == "" or sanitized is None:
        if enabled:
            return mint_indexnow_key()
        return None
    return sanitized


def sanitize_indexnow_key(raw: Optional[str]) -> Optional[str]:
    """Return a valid key, empty string for regenerate/clear, or None if omitted."""
    if raw is None:
        return None
    cleaned = str(raw).strip()
    if not cleaned:
        return ""
    if not INDEXNOW_KEY_RE.fullmatch(cleaned):
        raise ValueError(
            "indexnow_key must be 8–128 letters, digits, or hyphens"
        )
    return cleaned


def sanitize_redirect_path(raw: str, *, field: str) -> str:
    """Same-site path starting with a single slash; no scheme or protocol-relative."""
    path = str(raw or "").strip()
    if not path.startswith("/") or path.startswith("//"):
        raise ValueError(f"{field} must be a same-site path starting with /")
    lowered = path.lower()
    if "://" in path or lowered.startswith("http:") or lowered.startswith("https:"):
        raise ValueError(f"{field} must be a same-site path, not an absolute URL")
    if "\\" in path or "\n" in path or "\r" in path:
        raise ValueError(f"{field} contains invalid characters")
    return path


def sanitize_seo_redirects(raw: Any) -> List[Dict[str, str]]:
    """Normalize [{from, to}, ...] or clear with an empty list."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("seo_redirects must be a list of {from, to} objects")
    out: List[Dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("each seo_redirects entry must be an object")
        frm = item.get("from")
        to = item.get("to")
        if frm is None or to is None:
            raise ValueError("each redirect needs from and to")
        out.append(
            {
                "from": sanitize_redirect_path(str(frm), field="from"),
                "to": sanitize_redirect_path(str(to), field="to"),
            }
        )
    return out


def assert_domain_available(
    domain: Optional[str], *, exclude_site_id: Optional[str] = None
) -> None:
    """Raise ValueError if another live site already owns this domain."""
    if not domain:
        return
    exclude = None
    if exclude_site_id:
        try:
            exclude = validate_site_id(exclude_site_id)
        except ValueError:
            exclude = None
    for site in list_sites():
        if exclude and site.id == exclude:
            continue
        if site.domain and site.domain == domain:
            raise ValueError(
                f"Domain '{domain}' is already assigned to site '{site.id}'"
            )


def match_site_id_from_host(host: Optional[str]) -> Optional[str]:
    """Return site_id when Host matches a registry domain; else None."""
    ensure_sites_initialized()
    normalized = normalize_domain(host)
    if not normalized:
        return None
    for site in list_sites():
        if site.domain and site.domain == normalized:
            return site.id
    return None


def resolve_site_id_by_host(host: Optional[str]) -> str:
    """Map HTTP Host to a site_id via registry domain; miss → default."""
    return match_site_id_from_host(host) or DEFAULT_SITE_ID


def _registry_path() -> Path:
    from config import BASE_DIR

    return Path(BASE_DIR) / "data" / "sites.yaml"


def validate_site_id(site_id: str) -> str:
    """Normalize and validate a site id slug."""
    normalized = (site_id or "").strip().lower()
    if not SITE_ID_RE.match(normalized):
        raise ValueError(
            "site_id must match ^[a-z0-9][a-z0-9_-]{1,63}$ "
            "(lowercase letters, digits, underscore, hyphen)"
        )
    return normalized


def get_site_content_prefix(site_id: str) -> str:
    """Return the storage-relative prefix for a site (e.g. ``sites/default``)."""
    site = get_site(site_id)
    if site is None:
        raise ValueError(f"Unknown site_id: {site_id}")
    return site.content_relpath.rstrip("/")


def site_menus_relpath(site_id: str) -> str:
    return f"{get_site_content_prefix(site_id)}/menus.yaml"


def site_taxonomy_relpath(site_id: str) -> str:
    return f"{get_site_content_prefix(site_id)}/taxonomy.yaml"


def site_collections_relpath(site_id: str) -> str:
    return f"{get_site_content_prefix(site_id)}/collections.yaml"


def site_authors_relpath(site_id: str) -> str:
    return f"{get_site_content_prefix(site_id)}/authors.yaml"


def site_assets_prefix(site_id: str) -> str:
    """Storage-relative assets root for a site (e.g. ``sites/default/assets``)."""
    return f"{get_site_content_prefix(site_id)}/assets"


def join_site_assets_path(site_id: str, *parts: str) -> str:
    """Join logical asset parts under the site assets prefix.

    Example: ``join_site_assets_path("wiki", "images", "content", "x", "a.webp")``
    → ``sites/wiki/assets/images/content/x/a.webp``.
    """
    cleaned = [p.strip("/").replace("\\", "/") for p in parts if p]
    prefix = site_assets_prefix(site_id)
    if not cleaned:
        return prefix
    return f"{prefix}/{'/'.join(cleaned)}"


def _legacy_menus_json_path() -> Path:
    """Install-wide menus.json location (pre-per-site migration)."""
    from config import BASE_DIR

    if (BASE_DIR / "config.ini").exists():
        return BASE_DIR.parent / "pencms-data" / "menus.json"
    return BASE_DIR / "menus.json"


def _empty_menus_dict() -> dict:
    return {"primary": [], "secondary": [], "footer": []}


def _empty_taxonomy_dict() -> dict:
    """Blank taxonomy slate for every site (no thematic demo vocabularies)."""
    return {
        "primary_vocabulary": "",
        "required_fields": ["name", "status"],
        "vocabularies": {},
    }


def _empty_authors_dict() -> dict:
    """Blank authors slate for every site (no demo contributors)."""
    return {"authors": []}


def _seed_site_structure_files(site_id: str, site_dir: Path) -> None:
    """Ensure menus/taxonomy/collections/authors/assets exist under a local site dir."""
    from config import COLLECTIONS_SCHEMA_PATH

    assets_dir = site_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    menus_path = site_dir / "menus.yaml"
    if not menus_path.is_file():
        with open(menus_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(_empty_menus_dict(), f, default_flow_style=False, sort_keys=False)

    tax_path = site_dir / "taxonomy.yaml"
    if not tax_path.is_file():
        with open(tax_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                _empty_taxonomy_dict(), f, default_flow_style=False, sort_keys=False
            )

    authors_path = site_dir / "authors.yaml"
    if not authors_path.is_file():
        with open(authors_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                _empty_authors_dict(), f, default_flow_style=False, sort_keys=False
            )

    coll_path = site_dir / "collections.yaml"
    if not coll_path.is_file() and COLLECTIONS_SCHEMA_PATH.is_file():
        shutil.copy2(COLLECTIONS_SCHEMA_PATH, coll_path)


def _migrate_menus_json_to_default(content_root: Path) -> None:
    """Convert install-wide menus.json → sites/default/menus.yaml (idempotent)."""
    import json

    dest = content_root / "sites" / DEFAULT_SITE_ID / "menus.yaml"
    if dest.is_file():
        return

    legacy = _legacy_menus_json_path()
    if not legacy.is_file():
        return

    try:
        with open(legacy, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.warning("Could not read legacy menus.json at %s: %s", legacy, e)
        return

    if not isinstance(data, dict):
        data = _empty_menus_dict()

    menus = {}
    for slot in ("primary", "secondary", "footer"):
        menus[slot] = data.get(slot, []) if isinstance(data.get(slot, []), list) else []

    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        yaml.safe_dump(menus, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    logger.info(
        "Migrated menus.json → %s (original left at %s)", dest, legacy
    )


def _migrate_assets_to_default(content_root: Path) -> None:
    """Move install-wide assets/ into sites/default/assets/ (idempotent)."""
    from config import ASSETS_DIR_PATH

    if ASSETS_DIR_PATH is None:
        return

    dest = content_root / "sites" / DEFAULT_SITE_ID / "assets"
    dest.mkdir(parents=True, exist_ok=True)

    if not ASSETS_DIR_PATH.is_dir():
        return

    # Already migrated / has content under default assets — skip moves that collide
    has_legacy = any(ASSETS_DIR_PATH.iterdir())
    if not has_legacy:
        return

    dest_populated = dest.is_dir() and any(dest.iterdir())
    if dest_populated:
        # Only migrate items that don't already exist at dest
        pass

    moved = 0
    for item in list(ASSETS_DIR_PATH.iterdir()):
        target = dest / item.name
        if target.exists():
            logger.warning(
                "Skip asset migrate %s — destination already exists: %s", item, target
            )
            continue
        shutil.move(str(item), str(target))
        moved += 1
    if moved:
        logger.info(
            "Migrated %d entries from %s into sites/default/assets/",
            moved,
            ASSETS_DIR_PATH,
        )


def _load_raw() -> List[dict]:
    path = _registry_path()
    if not path.is_file():
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    sites = data.get("sites") if isinstance(data, dict) else None
    if not isinstance(sites, list):
        return []
    return [s for s in sites if isinstance(s, dict) and s.get("id")]


def _save_raw(sites: List[dict]) -> None:
    path = _registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"sites": sites}, f, default_flow_style=False, sort_keys=False)


def _optional_str(value) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_webhook_url(value) -> Optional[str]:
    """Normalize optional post-publish webhook URL (http/https only)."""
    text = _optional_str(value)
    if text is None:
        return None
    lower = text.lower()
    if not (lower.startswith("http://") or lower.startswith("https://")):
        raise ValueError("webhook_url must be an http:// or https:// URL")
    return text


def _optional_bool(value) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in ("true", "1", "yes", "on"):
        return True
    if text in ("false", "0", "no", "off"):
        return False
    return None


def _dict_to_record(d: dict) -> SiteRecord:
    sid = str(d["id"]).strip().lower()
    domain = normalize_domain(d.get("domain")) if d.get("domain") else None
    language_config = normalize_language_config(
        language=d.get("language", DEFAULT_LANGUAGE),
        languages=d.get("languages", []),
        language_labels=d.get("language_labels", {}),
        translation_automation_paused=d.get(
            "translation_automation_paused", False
        ),
    )
    raw_publish = d.get("publish")
    publish = None
    if isinstance(raw_publish, dict) and raw_publish:
        # Strip any secret keys that may have been written historically.
        publish = {
            k: v
            for k, v in raw_publish.items()
            if k in publish_allowed_keys() and k.lower() not in PUBLISH_SECRET_KEYS
        }
        if not publish:
            publish = None
    try:
        redirects = sanitize_seo_redirects(d.get("seo_redirects") or [])
    except ValueError:
        redirects = []
    return SiteRecord(
        id=sid,
        name=str(d.get("name") or sid),
        domain=domain,
        content_relpath=str(d.get("content_relpath") or f"sites/{sid}"),
        language=language_config.language,
        languages=language_config.languages,
        language_labels=language_config.language_labels,
        translation_automation_paused=(
            language_config.translation_automation_paused
        ),
        theme=_optional_str(d.get("theme")),
        sitename=_optional_str(d.get("sitename")),
        display_logo=_optional_bool(d.get("display_logo")),
        comments_enabled=_optional_bool(d.get("comments_enabled")),
        tagline=_optional_str(d.get("tagline")),
        hero_title=_optional_str(d.get("hero_title")),
        hero_image=_optional_str(d.get("hero_image")),
        contact_email=_optional_str(d.get("contact_email")),
        title_template=_optional_str(d.get("title_template")),
        meta_description=_optional_str(d.get("meta_description")),
        keywords=_optional_str(d.get("keywords")),
        robots_index=_optional_bool(d.get("robots_index")),
        robots_follow=_optional_bool(d.get("robots_follow")),
        robots_txt=_optional_str(d.get("robots_txt")),
        sitemap_enabled=_optional_bool(d.get("sitemap_enabled")),
        google_site_verification=_optional_str(d.get("google_site_verification")),
        bing_site_verification=_optional_str(d.get("bing_site_verification")),
        indexnow_enabled=_optional_bool(d.get("indexnow_enabled")),
        indexnow_key=_optional_str(d.get("indexnow_key")),
        content_signal_ai_train=_optional_bool(d.get("content_signal_ai_train")),
        seo_redirects=redirects,
        og_accent_color=_optional_str(d.get("og_accent_color")),
        og_vignette_color=_optional_str(d.get("og_vignette_color")),
        og_text_color=_optional_str(d.get("og_text_color")),
        og_bar_color=_optional_str(d.get("og_bar_color")),
        og_font=_optional_str(d.get("og_font")),
        og_headline_style=_optional_str(d.get("og_headline_style")),
        og_text_case=_optional_str(d.get("og_text_case")),
        og_grade_preset=_optional_str(d.get("og_grade_preset")),
        og_accent_bar=_optional_bool(d.get("og_accent_bar")),
        og_watermark_enabled=_optional_bool(d.get("og_watermark_enabled")),
        og_watermark=_optional_str(d.get("og_watermark")),
        og_watermark_source=_optional_str(d.get("og_watermark_source")),
        og_watermark_layout=_optional_str(d.get("og_watermark_layout")),
        og_watermark_corner=_optional_str(d.get("og_watermark_corner")),
        og_watermark_scale=_optional_str(d.get("og_watermark_scale")),
        og_default_hero=_optional_str(d.get("og_default_hero")),
        og_default_image=_optional_str(d.get("og_default_image")),
        og_fallback_title=_optional_str(d.get("og_fallback_title")),
        og_title_fallback=_optional_str(d.get("og_title_fallback")),
        og_description_fallback=_optional_str(d.get("og_description_fallback")),
        twitter_card=_optional_str(d.get("twitter_card")),
        social_links=d.get("social_links") if isinstance(d.get("social_links"), list) else None,
        style_overrides=_sanitize_style_overrides(d.get("style_overrides")),
        publish=publish,
        feedback_relay_url=_optional_str(d.get("feedback_relay_url")),
        feedback_submission_key=_optional_str(d.get("feedback_submission_key")),
        feedback_fetch_token=_optional_str(d.get("feedback_fetch_token")),
        feedback_relay_cursor=_optional_str(d.get("feedback_relay_cursor")),
    )


def list_sites() -> List[SiteRecord]:
    return [_dict_to_record(s) for s in _load_raw()]


def get_site(site_id: str) -> Optional[SiteRecord]:
    try:
        sid = validate_site_id(site_id)
    except ValueError:
        return None
    for s in list_sites():
        if s.id == sid:
            return s
    return None


def site_comments_enabled(site_id: str) -> bool:
    """Public comments chrome/ingest. Missing or None is off."""
    record = get_site(site_id)
    return bool(record and record.comments_enabled)


def resolve_human_site_id(request: Request) -> str:
    """Resolve the human operator's active site for content/MCP routes.

    Order: ``X-Pen-Site-Id`` header → ``pen_site_id`` cookie → ``default``.
    Missing/empty preference falls back to ``default`` if the actor may
    access it, else the first membership site. A present but unknown or
    invalid id raises HTTP 400. A present known site the human is not a
    member of raises HTTP 403 ``site_access_denied``.

    Agents that reach this helper are bound to JWT ``site_id`` — the
    header/cookie is ignored. Anonymous callers (no JWT) skip membership.
    """
    raw = request.headers.get(HUMAN_SITE_HEADER)
    if raw is None or not str(raw).strip():
        raw = request.cookies.get(HUMAN_SITE_COOKIE)
    present = raw is not None and bool(str(raw).strip())

    if present:
        try:
            sid = validate_site_id(raw)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        ensure_sites_initialized()
        if get_site(sid) is None:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown site_id: {sid}",
            )
    else:
        sid = DEFAULT_SITE_ID

    from services.authz import (
        accessible_site_ids,
        may_access_site,
        resolve_request_user,
        token_from_request,
    )

    if not token_from_request(request):
        return sid

    user, payload = resolve_request_user(request)

    if payload.get("type") == "agent":
        jwt_sid = payload.get("site_id")
        if not jwt_sid:
            raise HTTPException(
                status_code=403,
                detail="Agent token missing site_id claim",
            )
        ensure_sites_initialized()
        if get_site(str(jwt_sid)) is None:
            raise HTTPException(
                status_code=403,
                detail=f"Agent token site_id unknown: {jwt_sid}",
            )
        return str(jwt_sid)

    if may_access_site(user, sid, token_payload=payload):
        return sid

    if not present:
        ensure_sites_initialized()
        allowed = accessible_site_ids(
            user,
            token_payload=payload,
            all_site_ids=[s.id for s in list_sites()],
        )
        if allowed:
            return allowed[0]

    raise HTTPException(
        status_code=403,
        detail="site_access_denied",
    )


async def apply_human_site_taxonomy(site_id: str = Depends(resolve_human_site_id)):
    """Yield dependency: set request-scoped taxonomy before body validation."""
    import config

    snap = config.load_taxonomy_for_site(site_id)
    token = config.set_active_taxonomy(snap)
    try:
        yield site_id
    finally:
        config.reset_active_taxonomy(token)


def site_content_relpath(site_id: str) -> str:
    return get_site_content_prefix(site_id)


def _set_or_clear_str(entry: dict, key: str, value: Optional[str]) -> None:
    """Set a string field, or remove it when value is empty/None."""
    cleaned = _optional_str(value)
    if cleaned:
        entry[key] = cleaned
    else:
        entry.pop(key, None)


def _set_or_clear_bool(entry: dict, key: str, value: Optional[bool]) -> None:
    """Set a bool field, or remove it when value is None (inherit theme)."""
    if value is None:
        entry.pop(key, None)
    else:
        entry[key] = value


# Sentinel: field omitted from update_site kwargs (distinct from None = clear).
_UNSET = object()


def create_site(
    site_id: str,
    name: str,
    domain: Optional[str] = None,
    *,
    theme: Optional[str] = None,
    sitename: Optional[str] = None,
    display_logo: Optional[bool] = None,
    comments_enabled: Optional[bool] = None,
    tagline: Optional[str] = None,
    hero_title: Optional[str] = None,
    hero_image: Optional[str] = None,
    contact_email: Optional[str] = None,
    title_template: Optional[str] = None,
    meta_description: Optional[str] = None,
    keywords: Optional[str] = None,
    robots_index: Optional[bool] = None,
    robots_follow: Optional[bool] = None,
    robots_txt: Optional[str] = None,
    sitemap_enabled: Optional[bool] = None,
    google_site_verification: Optional[str] = None,
    bing_site_verification: Optional[str] = None,
    indexnow_enabled: Optional[bool] = None,
    indexnow_key: Optional[str] = None,
    content_signal_ai_train: Optional[bool] = None,
    seo_redirects: Optional[List[Dict[str, str]]] = None,
    og_accent_color: Optional[str] = None,
    og_vignette_color: Optional[str] = None,
    og_text_color: Optional[str] = None,
    og_bar_color: Optional[str] = None,
    og_font: Optional[str] = None,
    og_headline_style: Optional[str] = None,
    og_text_case: Optional[str] = None,
    og_grade_preset: Optional[str] = None,
    og_accent_bar: Optional[bool] = None,
    og_watermark_enabled: Optional[bool] = None,
    og_watermark: Optional[str] = None,
    og_watermark_source: Optional[str] = None,
    og_watermark_layout: Optional[str] = None,
    og_watermark_corner: Optional[str] = None,
    og_watermark_scale: Optional[str] = None,
    og_default_hero: Optional[str] = None,
    og_default_image: Optional[str] = None,
    og_fallback_title: Optional[str] = None,
    og_title_fallback: Optional[str] = None,
    og_description_fallback: Optional[str] = None,
    twitter_card: Optional[str] = None,
    social_links: Optional[List[Dict[str, Any]]] = None,
    style_overrides: Optional[Dict[str, Any]] = None,
    language: str = DEFAULT_LANGUAGE,
    languages: Optional[List[str]] = None,
    language_labels: Optional[Dict[str, str]] = None,
    translation_automation_paused: bool = False,
    feedback_relay_url: Optional[str] = None,
    feedback_submission_key: Optional[str] = None,
    feedback_fetch_token: Optional[str] = None,
    feedback_relay_cursor: Optional[str] = None,
) -> SiteRecord:
    """Create a new site registry entry and on-disk content root."""
    sid = validate_site_id(site_id)
    if get_site(sid) is not None:
        raise ValueError(f"Site '{sid}' already exists")

    normalized_domain = normalize_domain(domain)
    assert_domain_available(normalized_domain)
    language_config = normalize_language_config(
        language=language,
        languages=languages,
        language_labels=language_labels,
        translation_automation_paused=translation_automation_paused,
    )

    resolved_theme = _optional_str(theme) or DEFAULT_NEW_SITE_THEME
    record = SiteRecord(
        id=sid,
        name=(name or sid).strip() or sid,
        domain=normalized_domain,
        content_relpath=f"sites/{sid}",
        language=language_config.language,
        languages=language_config.languages,
        language_labels=language_config.language_labels,
        translation_automation_paused=(
            language_config.translation_automation_paused
        ),
        theme=resolved_theme,
        sitename=_optional_str(sitename),
        display_logo=display_logo,
        comments_enabled=(
            False if comments_enabled is None else bool(comments_enabled)
        ),
        tagline=_optional_str(tagline),
        hero_title=_optional_str(hero_title),
        hero_image=_optional_str(hero_image),
        contact_email=_optional_str(contact_email),
        title_template=_optional_str(title_template),
        meta_description=_optional_str(meta_description),
        keywords=_optional_str(keywords),
        robots_index=robots_index,
        robots_follow=robots_follow,
        robots_txt=_optional_str(robots_txt),
        sitemap_enabled=sitemap_enabled,
        google_site_verification=_optional_str(google_site_verification),
        bing_site_verification=_optional_str(bing_site_verification),
        indexnow_enabled=indexnow_enabled,
        indexnow_key=_resolve_indexnow_key(
            enabled=bool(indexnow_enabled),
            incoming=indexnow_key,
            existing=None,
        ),
        content_signal_ai_train=content_signal_ai_train,
        seo_redirects=sanitize_seo_redirects(seo_redirects or []),
        og_accent_color=_optional_str(og_accent_color),
        og_vignette_color=_optional_str(og_vignette_color),
        og_text_color=_optional_str(og_text_color),
        og_bar_color=_optional_str(og_bar_color),
        og_font=_optional_str(og_font),
        og_headline_style=_optional_str(og_headline_style),
        og_text_case=_optional_str(og_text_case),
        og_grade_preset=_optional_str(og_grade_preset),
        og_accent_bar=og_accent_bar,
        og_watermark_enabled=og_watermark_enabled,
        og_watermark=_optional_str(og_watermark),
        og_watermark_source=_optional_str(og_watermark_source),
        og_watermark_layout=_optional_str(og_watermark_layout),
        og_watermark_corner=_optional_str(og_watermark_corner),
        og_watermark_scale=_optional_str(og_watermark_scale),
        og_default_hero=_optional_str(og_default_hero),
        og_default_image=_optional_str(og_default_image),
        og_fallback_title=_optional_str(og_fallback_title),
        og_title_fallback=_optional_str(og_title_fallback),
        og_description_fallback=_optional_str(og_description_fallback),
        twitter_card=_optional_str(twitter_card),
        social_links=_sanitize_social_links(social_links),
        style_overrides=_sanitize_style_overrides(style_overrides),
        feedback_relay_url=normalize_feedback_relay_url(feedback_relay_url),
        feedback_submission_key=(
            _optional_str(feedback_submission_key) or mint_feedback_submission_key()
        ),
        feedback_fetch_token=(
            _optional_str(feedback_fetch_token) or mint_feedback_fetch_token()
        ),
        feedback_relay_cursor=_optional_str(feedback_relay_cursor),
    )
    sites = _load_raw()
    sites.append(record.to_dict())
    _save_raw(sites)
    _ensure_site_dir(record)
    return record


# ---------------------------------------------------------------------------
# Social-link URL canonicalization
# ---------------------------------------------------------------------------
# Each known platform maps to its canonical base URL, a set of domain aliases
# the user might type, and an optional default path prefix for bare usernames.
# Platforms with ``None`` (e.g. Mastodon) are federated — no single canonical
# domain exists, so only generic URL hygiene (https://, strip trailing /) is
# applied.
# ---------------------------------------------------------------------------

_SOCIAL_CANONICAL: Dict[str, Optional[Dict[str, Any]]] = {
    "twitter": {
        "domain": "https://x.com",
        "aliases": {"twitter.com", "x.com", "www.twitter.com", "www.x.com"},
        "path_prefix": "",
        "known_path_prefixes": [],
    },
    "bluesky": {
        "domain": "https://bsky.app",
        "aliases": {"bsky.app", "www.bsky.app", "staging.bsky.app"},
        "path_prefix": "/profile",
        "known_path_prefixes": ["/profile"],
    },
    "instagram": {
        "domain": "https://www.instagram.com",
        "aliases": {"instagram.com", "www.instagram.com", "instagr.am"},
        "path_prefix": "",
        "known_path_prefixes": [],
    },
    "facebook": {
        "domain": "https://www.facebook.com",
        "aliases": {"facebook.com", "www.facebook.com", "fb.com", "www.fb.com", "m.facebook.com"},
        "path_prefix": "",
        "known_path_prefixes": ["/groups", "/pages"],
    },
    "vk": {
        "domain": "https://vk.com",
        "aliases": {"vk.com", "www.vk.com", "m.vk.com"},
        "path_prefix": "",
        "known_path_prefixes": [],
    },
    "linkedin": {
        "domain": "https://www.linkedin.com",
        "aliases": {"linkedin.com", "www.linkedin.com"},
        "path_prefix": "/in",
        "known_path_prefixes": ["/in", "/company", "/school"],
    },
    "github": {
        "domain": "https://github.com",
        "aliases": {"github.com", "www.github.com"},
        "path_prefix": "",
        "known_path_prefixes": [],
    },
    "telegram": {
        "domain": "https://t.me",
        "aliases": {"t.me", "telegram.me", "www.telegram.me"},
        "path_prefix": "",
        "known_path_prefixes": [],
    },
    "youtube": {
        "domain": "https://www.youtube.com",
        "aliases": {"youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com"},
        "path_prefix": "",
        "known_path_prefixes": ["/channel", "/@", "/c", "/user"],
    },
    "tiktok": {
        "domain": "https://www.tiktok.com",
        "aliases": {"tiktok.com", "www.tiktok.com", "vm.tiktok.com"},
        "path_prefix": "/@",
        "known_path_prefixes": ["/@"],
    },
    "reddit": {
        "domain": "https://www.reddit.com",
        "aliases": {"reddit.com", "www.reddit.com", "old.reddit.com"},
        "path_prefix": "/user",
        "known_path_prefixes": ["/r", "/u", "/user"],
    },
    "discord": {
        "domain": "https://discord.gg",
        "aliases": {"discord.gg", "discord.com", "www.discord.com", "discordapp.com", "www.discordapp.com"},
        "path_prefix": "",
        "known_path_prefixes": ["/invite", "/servers"],
    },
    "slack": {
        "domain": "https://slack.com",
        "aliases": {"slack.com", "www.slack.com"},
        "path_prefix": "",
        "known_path_prefixes": [],
    },
    "whatsapp": {
        "domain": "https://wa.me",
        "aliases": {"wa.me", "whatsapp.com", "www.whatsapp.com", "api.whatsapp.com"},
        "path_prefix": "",
        "known_path_prefixes": [],
    },
    "mastodon": None,  # federated — no single canonical domain
}


def _normalize_social_url(platform: str, raw_url: str) -> str:
    """Normalise a social-media URL to its canonical form.

    Handles bare usernames, ``@`` prefixes, missing ``https://``, alias
    domains, and trailing slashes.  For unknown / federated platforms only
    generic URL hygiene is applied.
    """
    url = raw_url.strip()
    if not url:
        return ""

    rules = _SOCIAL_CANONICAL.get(platform)
    if rules is None:
        # Custom / federated (e.g. Mastodon): generic hygiene only.
        if not url.startswith(("http://", "https://")):
            first_seg = url.split("/")[0].split("?")[0]
            if "." in first_seg:
                url = "https://" + url
        url = url.replace("http://", "https://", 1)
        return url.rstrip("/")

    canonical_domain: str = rules["domain"]            # e.g. "https://x.com"
    aliases: Set[str] = rules["aliases"]
    default_path_prefix: str = rules["path_prefix"]     # e.g. "/in" for LinkedIn
    known_prefixes: list = rules["known_path_prefixes"]

    # Strip leading @ and / — common user mistakes.
    stripped = url.lstrip("@").lstrip("/").rstrip("/")
    if not stripped:
        return ""

    # Decide: does this look like a URL (contains a dot before the first /)
    # or a bare username/handle?
    first_seg = stripped.split("/")[0].split("?")[0]
    is_url_like = "." in first_seg or "://" in stripped

    if is_url_like:
        # Ensure scheme.
        if not stripped.startswith(("http://", "https://")):
            stripped = "https://" + stripped
        stripped = stripped.replace("http://", "https://", 1)

        # Split into scheme+host vs path.
        after_scheme = stripped.split("://", 1)[1] if "://" in stripped else stripped
        parts = after_scheme.split("/", 1)
        hostname = parts[0].lower()
        path = "/" + parts[1] if len(parts) > 1 else ""
        path = path.rstrip("/")

        if hostname in aliases:
            # Rewrite to canonical domain, keep path.
            # Check if path already starts with a known prefix.
            has_known = any(path.startswith(kp) for kp in known_prefixes) if known_prefixes else False
            if has_known or not default_path_prefix:
                return canonical_domain + path
            # Path is bare (e.g. /username) — prepend default prefix.
            if path:
                return canonical_domain + default_path_prefix + path
            return canonical_domain
        else:
            # Domain not in aliases — return the cleaned-up URL as-is.
            return stripped
    else:
        # Bare username / handle.
        username = stripped

        # TikTok: ensure @ prefix on username.
        if platform == "tiktok":
            username = username.lstrip("@")
            return canonical_domain + "/@" + username

        # Reddit: detect r/ or u/ prefix.
        if platform == "reddit":
            for pfx in ("r/", "u/", "user/"):
                if username.lower().startswith(pfx):
                    return canonical_domain + "/" + username
            return canonical_domain + "/user/" + username

        # YouTube: detect channel/handle prefixes.
        if platform == "youtube":
            if username.startswith("@"):
                return canonical_domain + "/" + username
            for pfx in ("channel/", "@", "c/", "user/"):
                if username.startswith(pfx):
                    return canonical_domain + "/" + username
            return canonical_domain + "/@" + username

        # LinkedIn: detect /company/ or /school/ prefix.
        if platform == "linkedin":
            for pfx in ("in/", "company/", "school/"):
                if username.lower().startswith(pfx):
                    return canonical_domain + "/" + username
            return canonical_domain + "/in/" + username

        # Bluesky: bare handle → profile URL.
        if platform == "bluesky":
            return canonical_domain + "/profile/" + username

        # WhatsApp: bare phone number or handle normalization
        if platform == "whatsapp":
            digits = re.sub(r"\D", "", username)
            if digits and (username.startswith("+") or username.isdigit() or not re.search(r"[a-zA-Z]", username)):
                return canonical_domain + "/" + digits
            return canonical_domain + "/" + username.lstrip("/")

        # Generic known platform: canonical domain + username.
        if default_path_prefix:
            return canonical_domain + default_path_prefix + "/" + username
        return canonical_domain + "/" + username


def _sanitize_style_overrides(raw: Any) -> Optional[Dict[str, Any]]:
    """Normalize per-site style overrides.

    Expected shape: {"theme": "<slug>", "values": {...}, "dark": {...}}.
    Values/dark values must be strings (CSS custom property values).
    """
    if not isinstance(raw, dict):
        return None
    theme = _optional_str(raw.get("theme"))
    if not theme:
        return None

    def _clean_map(block: Any) -> Dict[str, str]:
        if not isinstance(block, dict):
            return {}
        cleaned: Dict[str, str] = {}
        for key, value in block.items():
            if not isinstance(key, str) or not key.strip():
                continue
            if not isinstance(value, str):
                continue
            cleaned[key.strip()] = value
        return cleaned

    values = _clean_map(raw.get("values"))
    dark = _clean_map(raw.get("dark"))
    if not values and not dark:
        return None
    return {"theme": theme, "values": values, "dark": dark}


def _sanitize_social_links(raw: Any) -> Optional[List[Dict[str, str]]]:
    if not isinstance(raw, list):
        return None
    cleaned = []
    for item in raw[:50]:
        if not isinstance(item, dict):
            continue
        platform = str(item.get("platform") or "custom").strip().lower()
        url = _normalize_social_url(platform, str(item.get("url") or ""))
        if not url:
            continue
        entry: Dict[str, str] = {"platform": platform, "url": url}
        lbl = str(item.get("label") or "").strip()
        if lbl:
            entry["label"] = lbl
        cleaned.append(entry)
    return cleaned if cleaned else None


def update_site(
    site_id: str,
    name: Optional[str] = None,
    domain: Optional[str] = None,
    *,
    theme: Optional[str] = None,
    sitename: Optional[str] = None,
    display_logo: Optional[bool] = None,
    comments_enabled: Optional[bool] = None,
    tagline: Optional[str] = None,
    hero_title: Optional[str] = None,
    hero_image: Optional[str] = None,
    contact_email: Optional[str] = None,
    title_template: Optional[str] = None,
    meta_description: Optional[str] = None,
    keywords: Optional[str] = None,
    robots_index: Optional[bool] = None,
    robots_follow: Optional[bool] = None,
    robots_txt: Optional[str] = None,
    sitemap_enabled: Optional[bool] = None,
    google_site_verification: Optional[str] = None,
    bing_site_verification: Optional[str] = None,
    indexnow_enabled: Optional[bool] = None,
    indexnow_key: Any = _UNSET,
    content_signal_ai_train: Optional[bool] = None,
    seo_redirects: Any = _UNSET,
    og_accent_color: Optional[str] = None,
    og_vignette_color: Optional[str] = None,
    og_text_color: Optional[str] = None,
    og_bar_color: Optional[str] = None,
    og_font: Optional[str] = None,
    og_headline_style: Optional[str] = None,
    og_text_case: Optional[str] = None,
    og_grade_preset: Optional[str] = None,
    og_accent_bar: Any = _UNSET,
    og_watermark_enabled: Any = _UNSET,
    og_watermark: Optional[str] = None,
    og_watermark_source: Optional[str] = None,
    og_watermark_layout: Optional[str] = None,
    og_watermark_corner: Optional[str] = None,
    og_watermark_scale: Optional[str] = None,
    og_default_hero: Optional[str] = None,
    og_default_image: Optional[str] = None,
    og_fallback_title: Optional[str] = None,
    og_title_fallback: Optional[str] = None,
    og_description_fallback: Optional[str] = None,
    twitter_card: Optional[str] = None,
    social_links: Any = _UNSET,
    style_overrides: Any = _UNSET,
    language: Any = _UNSET,
    languages: Any = _UNSET,
    language_labels: Any = _UNSET,
    translation_automation_paused: Any = _UNSET,
    feedback_relay_url: Any = _UNSET,
    feedback_submission_key: Any = _UNSET,
    feedback_fetch_token: Any = _UNSET,
    feedback_relay_cursor: Any = _UNSET,
    _social_string_keys_present: Optional[set] = None,
) -> SiteRecord:
    """Soft-update name, domain, and/or presentation fields. Path unchanged.

    Social string fields: pass the value when the key is present in the PATCH
    body (including empty string to clear). Keys not in the request are left
    alone — callers should only pass social kwargs that were explicitly set.

    ``og_accent_bar`` and ``og_watermark_enabled`` use ``_UNSET`` (omit) vs
    ``None`` (clear) vs bool (set).
    """
    sid = validate_site_id(site_id)
    sites = _load_raw()
    found = None
    for i, s in enumerate(sites):
        if str(s.get("id", "")).strip().lower() == sid:
            found = i
            break
    if found is None:
        raise ValueError(f"Unknown site_id: {sid}")

    if any(
        value is not _UNSET
        for value in (
            language,
            languages,
            language_labels,
            translation_automation_paused,
        )
    ):
        current = sites[found]
        language_config = normalize_language_config(
            language=(
                current.get("language", DEFAULT_LANGUAGE)
                if language is _UNSET
                else language
            ),
            languages=(
                current.get("languages", [])
                if languages is _UNSET
                else languages
            ),
            language_labels=(
                current.get("language_labels", {})
                if language_labels is _UNSET
                else language_labels
            ),
            translation_automation_paused=(
                current.get("translation_automation_paused", False)
                if translation_automation_paused is _UNSET
                else translation_automation_paused
            ),
        )
        current["language"] = language_config.language
        current["languages"] = language_config.languages
        current["language_labels"] = language_config.language_labels
        current["translation_automation_paused"] = (
            language_config.translation_automation_paused
        )

    if name is not None:
        sites[found]["name"] = (name or sid).strip() or sid
    if domain is not None:
        # Empty string clears domain
        cleaned = normalize_domain(domain) if domain.strip() else None
        if cleaned:
            assert_domain_available(cleaned, exclude_site_id=sid)
            sites[found]["domain"] = cleaned
        else:
            sites[found].pop("domain", None)
    if theme is not None:
        _set_or_clear_str(sites[found], "theme", theme)
    if sitename is not None:
        _set_or_clear_str(sites[found], "sitename", sitename)
    if display_logo is not None:
        sites[found]["display_logo"] = display_logo
    if comments_enabled is not None:
        sites[found]["comments_enabled"] = bool(comments_enabled)
    if tagline is not None:
        _set_or_clear_str(sites[found], "tagline", tagline)
    if hero_title is not None:
        _set_or_clear_str(sites[found], "hero_title", hero_title)
    if hero_image is not None:
        _set_or_clear_str(sites[found], "hero_image", hero_image)
    if contact_email is not None:
        _set_or_clear_str(sites[found], "contact_email", contact_email)
    if title_template is not None:
        _set_or_clear_str(sites[found], "title_template", title_template)
    if meta_description is not None:
        _set_or_clear_str(sites[found], "meta_description", meta_description)
    if keywords is not None:
        _set_or_clear_str(sites[found], "keywords", keywords)
    if robots_index is not None:
        sites[found]["robots_index"] = robots_index
    if robots_follow is not None:
        sites[found]["robots_follow"] = robots_follow
    if robots_txt is not None:
        _set_or_clear_str(sites[found], "robots_txt", robots_txt)
    if sitemap_enabled is not None:
        sites[found]["sitemap_enabled"] = sitemap_enabled
    if google_site_verification is not None:
        _set_or_clear_str(
            sites[found], "google_site_verification", google_site_verification
        )
    if bing_site_verification is not None:
        _set_or_clear_str(
            sites[found], "bing_site_verification", bing_site_verification
        )
    if indexnow_enabled is not None:
        sites[found]["indexnow_enabled"] = indexnow_enabled
    if content_signal_ai_train is not None:
        sites[found]["content_signal_ai_train"] = content_signal_ai_train
    if seo_redirects is not _UNSET:
        cleaned_redirects = sanitize_seo_redirects(seo_redirects)
        if cleaned_redirects:
            sites[found]["seo_redirects"] = cleaned_redirects
        else:
            sites[found].pop("seo_redirects", None)

    enabled_now = bool(
        sites[found]["indexnow_enabled"]
        if "indexnow_enabled" in sites[found]
        else False
    )
    resolved_key = _resolve_indexnow_key(
        enabled=enabled_now,
        incoming=indexnow_key,
        existing=_optional_str(sites[found].get("indexnow_key")),
    )
    if resolved_key:
        sites[found]["indexnow_key"] = resolved_key
    else:
        sites[found].pop("indexnow_key", None)

    if social_links is not _UNSET:
        sanitized = _sanitize_social_links(social_links)
        if sanitized:
            sites[found]["social_links"] = sanitized
        else:
            sites[found].pop("social_links", None)

    if style_overrides is not _UNSET:
        sanitized = _sanitize_style_overrides(style_overrides)
        if sanitized:
            sites[found]["style_overrides"] = sanitized
        else:
            sites[found].pop("style_overrides", None)

    # Social string overrides: only touch keys the caller marked present.
    # When _social_string_keys_present is None, treat non-None kwargs as present
    # (legacy / direct service calls that pass values intentionally).
    social_strings = {
        "og_accent_color": og_accent_color,
        "og_vignette_color": og_vignette_color,
        "og_text_color": og_text_color,
        "og_bar_color": og_bar_color,
        "og_font": og_font,
        "og_headline_style": og_headline_style,
        "og_text_case": og_text_case,
        "og_grade_preset": og_grade_preset,
        "og_watermark": og_watermark,
        "og_watermark_source": og_watermark_source,
        "og_watermark_layout": og_watermark_layout,
        "og_watermark_corner": og_watermark_corner,
        "og_watermark_scale": og_watermark_scale,
        "og_default_hero": og_default_hero,
        "og_default_image": og_default_image,
        "og_fallback_title": og_fallback_title,
        "og_title_fallback": og_title_fallback,
        "og_description_fallback": og_description_fallback,
        "twitter_card": twitter_card,
    }
    if _social_string_keys_present is None:
        for key, val in social_strings.items():
            if val is not None:
                _set_or_clear_str(sites[found], key, val)
    else:
        for key in _social_string_keys_present:
            if key in social_strings:
                _set_or_clear_str(sites[found], key, social_strings[key])

    if og_accent_bar is not _UNSET:
        _set_or_clear_bool(sites[found], "og_accent_bar", og_accent_bar)
    if og_watermark_enabled is not _UNSET:
        _set_or_clear_bool(sites[found], "og_watermark_enabled", og_watermark_enabled)

    if feedback_relay_url is not _UNSET:
        _set_or_clear_str(
            sites[found],
            "feedback_relay_url",
            normalize_feedback_relay_url(feedback_relay_url),
        )
    if feedback_submission_key is not _UNSET:
        _set_or_clear_str(
            sites[found], "feedback_submission_key", feedback_submission_key
        )
    if feedback_fetch_token is not _UNSET:
        _set_or_clear_str(
            sites[found], "feedback_fetch_token", feedback_fetch_token
        )
    if feedback_relay_cursor is not _UNSET:
        _set_or_clear_str(
            sites[found], "feedback_relay_cursor", feedback_relay_cursor
        )

    _save_raw(sites)
    return _dict_to_record(sites[found])


def _try_get_provider(provider_id: Optional[str]):
    from services.publish_providers.registry import (
        ProviderNotEnabledError,
        UnknownPublishProviderError,
        get_provider,
    )

    try:
        return get_provider(provider_id)
    except (UnknownPublishProviderError, ProviderNotEnabledError):
        return None


def _is_token_host(provider_obj) -> bool:
    if provider_obj is None:
        return False
    methods = (provider_obj.capabilities() or {}).get("auth_methods") or []
    return "token" in methods and "password" not in methods


def _publish_yaml_field_names() -> List[str]:
    from services.publish_providers.registry import registered_provider_classes

    names: List[str] = []
    seen: Set[str] = set()
    for cls in registered_provider_classes():
        for field in cls().yaml_fields():
            if field not in seen:
                names.append(field)
                seen.add(field)
    return names


def _publish_configured(block: Optional[Dict[str, Any]]) -> bool:
    """True when a publish block has enough fields to count as connected."""
    if not block or not isinstance(block, dict):
        return False
    provider = (_optional_str(block.get("provider")) or "sftp").strip().lower()
    adapter = _try_get_provider(provider)
    if adapter is None:
        return False
    return bool(adapter.is_configured(block))


def unconnected_publish_payload(site_id: str) -> Dict[str, Any]:
    """API shape when a site has no publish target configured."""
    out: Dict[str, Any] = {
        "site_id": site_id,
        "configured": False,
        "provider": None,
        "host": None,
        "port": None,
        "username": None,
        "remote_path": None,
        "auth_method": None,
        "public_url": None,
        "last_published_at": None,
        "last_status": None,
        "agent_publish": None,
        "webhook_url": None,
        "has_webhook_secret": False,
    }
    for field in _publish_yaml_field_names():
        if field not in out:
            out[field] = None
    return out


def _has_webhook_secret(block: Optional[Dict[str, Any]]) -> bool:
    if not block or not isinstance(block, dict):
        return False
    return bool(_optional_str(block.get("webhook_secret")))


def publish_target_payload(site_id: str, block: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Build the GET/PUT response for a site's publish target (never includes secrets)."""
    if not _publish_configured(block):
        return unconnected_publish_payload(site_id)
    assert block is not None
    provider = _optional_str(block.get("provider")) or "sftp"
    adapter = _try_get_provider(provider)
    token_host = _is_token_host(adapter)
    port = block.get("port")
    try:
        port_out = int(port) if port is not None and str(port).strip() != "" else 22
    except (TypeError, ValueError):
        port_out = 22
    default_auth = "token" if token_host else "password"
    port_for_sftp = port_out if not token_host else (
        block.get("port") if block.get("port") is not None else None
    )
    out: Dict[str, Any] = {
        "site_id": site_id,
        "configured": True,
        "provider": provider,
        "host": _optional_str(block.get("host")),
        "port": port_for_sftp,
        "username": _optional_str(block.get("username")),
        "remote_path": _optional_str(block.get("remote_path")),
        "auth_method": _optional_str(block.get("auth_method")) or default_auth,
        "public_url": _optional_str(block.get("public_url")),
        "last_published_at": block.get("last_published_at"),
        "last_status": block.get("last_status"),
        "agent_publish": _optional_str(block.get("agent_publish")) or "off",
        "webhook_url": _optional_str(block.get("webhook_url")),
        "has_webhook_secret": _has_webhook_secret(block),
    }
    for field in _publish_yaml_field_names():
        if field not in out:
            out[field] = _optional_str(block.get(field))
    return out


def get_publish_target(site_id: str) -> Dict[str, Any]:
    """Return the API payload for a site's publish target.

    Raises ValueError for invalid or unknown site_id.
    """
    sid = validate_site_id(site_id)
    ensure_sites_initialized()
    site = get_site(sid)
    if site is None:
        raise ValueError(f"Unknown site_id: {sid}")
    return publish_target_payload(sid, site.publish)


def get_publish_webhook_secret(site_id: str) -> Optional[str]:
    """Return the stored webhook HMAC secret for deploy use (never for API GET).

    Raises ValueError for invalid or unknown site_id.
    """
    sid = validate_site_id(site_id)
    ensure_sites_initialized()
    site = get_site(sid)
    if site is None:
        raise ValueError(f"Unknown site_id: {sid}")
    if not site.publish:
        return None
    return _optional_str(site.publish.get("webhook_secret"))


def _normalize_publish_block(
    payload: Dict[str, Any],
    *,
    existing: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Validate and normalize a publish write payload into a YAML-safe block.

    Raises ValueError if secret keys are present or required connection fields
    are missing / invalid.
    """
    from services.publish_providers.registry import (
        ProviderNotEnabledError,
        UnknownPublishProviderError,
        get_provider,
    )

    if not isinstance(payload, dict):
        raise ValueError("publish payload must be an object")

    secret_hits = [
        k
        for k in payload
        if k.lower() in PUBLISH_SECRET_KEYS or k.lower() == "password"
    ]
    if secret_hits:
        raise ValueError(
            "Publish passwords must not be sent to this endpoint; "
            f"remove: {', '.join(sorted(secret_hits))}"
        )

    allowed = publish_allowed_keys()
    # Merge over existing so status fields survive a host-settings PUT.
    base: Dict[str, Any] = dict(existing) if existing else {}
    for key, value in payload.items():
        if key == "site" or key == "site_id":
            continue
        if key not in allowed:
            # Ignore unknown non-secret keys rather than failing loudly.
            continue
        base[key] = value

    provider = (_optional_str(base.get("provider")) or "sftp").strip().lower() or "sftp"
    try:
        adapter = get_provider(provider)
    except (UnknownPublishProviderError, ProviderNotEnabledError) as e:
        raise ValueError(str(e)) from e

    agent_publish = _optional_str(base.get("agent_publish")) or "off"
    if agent_publish not in PUBLISH_AGENT_PUBLISH:
        raise ValueError("agent_publish must be 'off' or 'enrolled'")

    last_status = base.get("last_status", None)
    if last_status is not None and last_status != "":
        last_status = _optional_str(last_status)
        if last_status not in PUBLISH_LAST_STATUSES:
            raise ValueError("last_status must be 'ok', 'failed', or 'never'")
    else:
        last_status = None

    last_published_at = base.get("last_published_at", None)
    if last_published_at is not None and str(last_published_at).strip() == "":
        last_published_at = None

    webhook_url = _optional_webhook_url(base.get("webhook_url"))

    # Write-only: omit → keep existing; empty/null → clear; else set.
    if "webhook_secret" in payload:
        raw_secret = payload.get("webhook_secret")
        if raw_secret is None or str(raw_secret).strip() == "":
            webhook_secret: Optional[str] = None
        else:
            webhook_secret = str(raw_secret).strip()
    else:
        webhook_secret = _optional_str(base.get("webhook_secret"))

    provider_fields = adapter.normalize(base)
    caps = adapter.capabilities() or {}
    auth_methods = caps.get("auth_methods") or ["password"]
    if "token" in auth_methods and "password" not in auth_methods:
        auth_method = "token"
    else:
        auth_method = _optional_str(base.get("auth_method")) or "password"
        if auth_method not in ("password", "key"):
            raise ValueError("auth_method must be 'password' or 'key'")

    token_host = _is_token_host(adapter)
    out: Dict[str, Any] = {
        "provider": provider,
        "host": None,
        "port": None,
        "username": None,
        "remote_path": None,
        "auth_method": auth_method,
        "public_url": _optional_str(base.get("public_url")),
        "last_published_at": last_published_at,
        "last_status": last_status,
        "agent_publish": agent_publish,
        "webhook_url": webhook_url,
        "webhook_secret": webhook_secret,
    }
    for field in adapter.yaml_fields():
        out[field] = provider_fields.get(field)
    if not token_host:
        out["host"] = provider_fields.get("host")
        out["port"] = provider_fields.get("port")
        out["username"] = provider_fields.get("username")
        out["remote_path"] = provider_fields.get("remote_path")
    return out


def set_publish_target(site_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Persist a non-secret publish target for a site; return API payload.

    Raises ValueError for invalid/unknown site or bad payload (including secrets).
    """
    sid = validate_site_id(site_id)
    ensure_sites_initialized()
    sites = _load_raw()
    found = None
    for i, s in enumerate(sites):
        if str(s.get("id", "")).strip().lower() == sid:
            found = i
            break
    if found is None:
        raise ValueError(f"Unknown site_id: {sid}")

    existing = sites[found].get("publish")
    if not isinstance(existing, dict):
        existing = None
    elif existing:
        existing = {
            k: v
            for k, v in existing.items()
            if k in publish_allowed_keys() and k.lower() not in PUBLISH_SECRET_KEYS
        }

    block = _normalize_publish_block(payload, existing=existing)
    # Drop None public_url from YAML noise; keep null status fields explicit.
    to_store = {k: v for k, v in block.items() if v is not None or k in ("last_published_at", "last_status")}
    sites[found]["publish"] = to_store
    _save_raw(sites)
    return publish_target_payload(sid, to_store)


def _require_local_content_root() -> Path:
    from config import CONTENT_DIR_PATH

    if CONTENT_DIR_PATH is None:
        raise ValueError(
            "Site lifecycle disk operations require local CONTENT_DIR_PATH"
        )
    return Path(CONTENT_DIR_PATH)


def rename_site(old_id: str, new_id: str) -> SiteRecord:
    """Hard-rename a site id: disk tree, registry, agent keys, and FTS."""
    from services.cache_service import reassign_entries_site_id
    from services.user_service import reassign_agent_keys_site

    old = validate_site_id(old_id)
    new = validate_site_id(new_id)
    if old == DEFAULT_SITE_ID:
        raise ValueError("Cannot rename the default site")
    if old == new:
        site = get_site(old)
        if site is None:
            raise ValueError(f"Unknown site_id: {old}")
        return site
    if get_site(old) is None:
        raise ValueError(f"Unknown site_id: {old}")
    if get_site(new) is not None:
        raise ValueError(f"Site '{new}' already exists")

    content_root = _require_local_content_root()
    old_dir = content_root / "sites" / old
    new_dir = content_root / "sites" / new
    if new_dir.exists():
        raise ValueError(f"Destination directory already exists: sites/{new}")
    if old_dir.exists():
        new_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old_dir), str(new_dir))
    else:
        new_dir.mkdir(parents=True, exist_ok=True)
        _seed_site_structure_files(new, new_dir)

    sites = _load_raw()
    for s in sites:
        if str(s.get("id", "")).strip().lower() == old:
            s["id"] = new
            s["content_relpath"] = f"sites/{new}"
            if not s.get("name") or s.get("name") == old:
                s["name"] = new
            break
    _save_raw(sites)

    reassign_agent_keys_site(old, new)
    reassign_entries_site_id(old, new)

    record = get_site(new)
    if record is None:
        raise ValueError(f"Rename failed: site '{new}' not found after update")
    return record


def delete_site(
    site_id: str,
    *,
    confirm: bool = False,
    reassign_keys_to: Optional[str] = None,
    revoke_keys: bool = False,
) -> dict:
    """Delete a site: tombstone content, drop registry, purge FTS, handle keys."""
    from datetime import datetime

    from services.cache_service import delete_entries_for_site
    from services.user_service import (
        count_agent_keys_for_site,
        reassign_agent_keys_site,
        revoke_agent_keys_for_site,
    )

    sid = validate_site_id(site_id)
    if not confirm:
        raise ValueError("Delete requires confirm=true")
    if sid == DEFAULT_SITE_ID:
        raise ValueError("Cannot delete the default site")

    sites = list_sites()
    if len(sites) <= 1:
        raise ValueError("Cannot delete the last remaining site")
    if get_site(sid) is None:
        raise ValueError(f"Unknown site_id: {sid}")

    key_count = count_agent_keys_for_site(sid)
    keys_action = None
    if key_count > 0:
        if reassign_keys_to:
            target = validate_site_id(reassign_keys_to)
            if get_site(target) is None:
                raise ValueError(f"Unknown reassign_keys_to site: {target}")
            if target == sid:
                raise ValueError("reassign_keys_to must differ from the deleted site")
            reassign_agent_keys_site(sid, target)
            keys_action = f"reassigned:{target}"
        elif revoke_keys:
            revoke_agent_keys_for_site(sid)
            keys_action = "revoked"
        else:
            raise ValueError(
                f"{key_count} agent key(s) still bound to '{sid}'. "
                "Pass reassign_keys_to or revoke_keys=true"
            )

    content_root = _require_local_content_root()
    src = content_root / "sites" / sid
    tombstone_rel: Optional[str] = None
    if src.exists():
        tombstone_name = f"{sid}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        tombstone_rel = f"_deleted/{tombstone_name}"
        tombstone_path = content_root / "_deleted" / tombstone_name
        tombstone_path.parent.mkdir(parents=True, exist_ok=True)
        if tombstone_path.exists():
            raise ValueError(f"Tombstone path already exists: {tombstone_rel}")
        shutil.move(str(src), str(tombstone_path))

    remaining = [
        s
        for s in _load_raw()
        if str(s.get("id", "")).strip().lower() != sid
    ]
    _save_raw(remaining)
    delete_entries_for_site(sid)

    return {
        "id": sid,
        "tombstone": tombstone_rel,
        "keys_action": keys_action,
        "message": "Site deleted",
    }


def _normalize_content_relpath(path: str) -> str:
    """Validate a path relative to a site content root (no traversal)."""
    raw = (path or "").strip().replace("\\", "/").lstrip("/")
    if not raw:
        raise ValueError("Empty content path")
    parts = []
    for seg in raw.split("/"):
        if not seg or seg == ".":
            continue
        if seg == ".." or seg.startswith(".."):
            raise ValueError("Path traversal not allowed")
        parts.append(seg)
    if not parts:
        raise ValueError("Empty content path")
    return "/".join(parts)


def _slug_from_site_relpath(rel: str) -> str:
    """Derive a content slug from a path under a site root."""
    parts = rel.split("/")
    filename = parts[-1]
    if filename == "index.md":
        # Pattern B locale paths are <slug>/<lang>/index.md; the first path
        # segment remains the document identity.
        return parts[0] if parts else "index"
    if filename.endswith(".md"):
        return filename[:-3]
    return parts[0] if parts else rel


async def move_content_between_sites(
    from_site: str,
    to_site: str,
    paths: List[str],
    *,
    overwrite: bool = False,
    include_assets: bool = True,
) -> dict:
    """Move content paths (and matching slug assets) between sites; update FTS."""
    from config import content_storage
    from services.cache_service import (
        delete_entries_by_site_and_slugs,
        sync_cache_with_storage,
    )

    src_id = validate_site_id(from_site)
    dst_id = validate_site_id(to_site)
    if src_id == dst_id:
        raise ValueError("from_site and to_site must differ")
    if get_site(src_id) is None:
        raise ValueError(f"Unknown site_id: {src_id}")
    if get_site(dst_id) is None:
        raise ValueError(f"Unknown site_id: {dst_id}")
    if not paths:
        raise ValueError("paths must be a non-empty list")

    content_root = _require_local_content_root()
    src_root = content_root / "sites" / src_id
    dst_root = content_root / "sites" / dst_id
    dst_root.mkdir(parents=True, exist_ok=True)

    moved: List[str] = []
    moved_assets: List[str] = []
    slugs_to_purge: List[str] = []

    for raw_path in paths:
        rel = _normalize_content_relpath(raw_path)
        src_path = src_root / rel
        dst_path = dst_root / rel
        if not src_path.exists():
            raise ValueError(f"Source path not found: {rel}")
        if dst_path.exists():
            if not overwrite:
                raise ValueError(
                    f"Destination already exists: {rel} (pass overwrite=true)"
                )
            if dst_path.is_dir():
                shutil.rmtree(dst_path)
            else:
                dst_path.unlink()
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_path), str(dst_path))
        moved.append(rel)
        slug = _slug_from_site_relpath(rel)
        slugs_to_purge.append(slug)

        if include_assets:
            asset_rel = f"assets/images/content/{slug}"
            asset_src = src_root / asset_rel
            if asset_src.exists():
                asset_dst = dst_root / asset_rel
                if asset_dst.exists():
                    if not overwrite:
                        raise ValueError(
                            f"Destination asset already exists: {asset_rel} "
                            "(pass overwrite=true)"
                        )
                    if asset_dst.is_dir():
                        shutil.rmtree(asset_dst)
                    else:
                        asset_dst.unlink()
                asset_dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(asset_src), str(asset_dst))
                moved_assets.append(asset_rel)

    delete_entries_by_site_and_slugs(src_id, slugs_to_purge)
    try:
        await sync_cache_with_storage(content_storage)
    except Exception as e:
        logger.warning("Cache sync after move-content failed: %s", e)

    return {
        "from_site": src_id,
        "to_site": dst_id,
        "moved": moved,
        "moved_assets": moved_assets,
        "message": "Content moved",
    }


def _ensure_site_dir(record: SiteRecord) -> None:
    from config import CONTENT_DIR_PATH, content_storage

    if CONTENT_DIR_PATH is not None:
        target = CONTENT_DIR_PATH / record.content_relpath
        target.mkdir(parents=True, exist_ok=True)
        _seed_site_structure_files(record.id, target)
        return

    # Remote / non-local: best-effort mkdir + seed via storage provider
    try:
        import asyncio

        async def _mkdir_and_seed():
            assert content_storage is not None
            await content_storage.mkdir(record.content_relpath)
            await content_storage.mkdir(f"{record.content_relpath}/assets")
            menus_rel = f"{record.content_relpath}/menus.yaml"
            if not await content_storage.exists(menus_rel):
                await content_storage.write(
                    menus_rel, yaml.safe_dump(_empty_menus_dict(), sort_keys=False)
                )
            from config import COLLECTIONS_SCHEMA_PATH

            tax_rel = f"{record.content_relpath}/taxonomy.yaml"
            if not await content_storage.exists(tax_rel):
                await content_storage.write(
                    tax_rel,
                    yaml.safe_dump(_empty_taxonomy_dict(), sort_keys=False),
                )
            authors_rel = f"{record.content_relpath}/authors.yaml"
            if not await content_storage.exists(authors_rel):
                await content_storage.write(
                    authors_rel,
                    yaml.safe_dump(_empty_authors_dict(), sort_keys=False),
                )
            coll_rel = f"{record.content_relpath}/collections.yaml"
            if (
                not await content_storage.exists(coll_rel)
                and COLLECTIONS_SCHEMA_PATH.is_file()
            ):
                await content_storage.write(
                    coll_rel, COLLECTIONS_SCHEMA_PATH.read_text(encoding="utf-8")
                )

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(_mkdir_and_seed())
        else:
            loop.create_task(_mkdir_and_seed())
    except Exception as e:
        logger.warning("Could not create site dir %s: %s", record.content_relpath, e)


def _migrate_flat_content_to_default(content_root: Path) -> None:
    """Move top-level content (except ``sites/`` and ``_deleted/``) into ``sites/default/``."""
    default_dir = content_root / "sites" / "default"
    default_dir.mkdir(parents=True, exist_ok=True)

    moved = 0
    for item in list(content_root.iterdir()):
        if item.name in ("sites", "_deleted"):
            continue
        dest = default_dir / item.name
        if dest.exists():
            logger.warning(
                "Skip migrate %s — destination already exists: %s", item, dest
            )
            continue
        shutil.move(str(item), str(dest))
        moved += 1
    if moved:
        logger.info(
            "Migrated %d top-level content entries into sites/default/", moved
        )


def _comment_file_is_visible(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    try:
        parsed = frontmatter.loads(text)
    except Exception:
        return False
    vis = str(dict(parsed.metadata).get("visibility") or "").strip().lower()
    return vis == "visible"


def _site_has_visible_comments(content_root: Path, content_relpath: str) -> bool:
    site_dir = content_root / content_relpath
    if not site_dir.is_dir():
        return False
    for path in site_dir.rglob("c-*.md"):
        if path.parent.name != "comments":
            continue
        if _comment_file_is_visible(path):
            return True
    return False


def _migrate_comments_enabled(sites: List[dict], content_root: Optional[Path]) -> bool:
    """Fill missing comments_enabled once. Visible c-*.md → on; else off.

    Does not rewrite sites that already have the key. Never deletes comment files.
    """
    changed = False
    for entry in sites:
        if not isinstance(entry, dict) or "comments_enabled" in entry:
            continue
        rel = str(entry.get("content_relpath") or f"sites/{entry.get('id', '')}")
        enabled = False
        if content_root is not None:
            enabled = _site_has_visible_comments(content_root, rel)
        entry["comments_enabled"] = enabled
        changed = True
    return changed


def ensure_sites_initialized() -> List[SiteRecord]:
    """Ensure registry + default site exist; migrate flat content once.

    Idempotent. Safe to call on every startup.
    """
    path = _registry_path()
    sites = _load_raw()

    if not sites:
        default = SiteRecord(
            id=DEFAULT_SITE_ID,
            name="Default",
            content_relpath=f"sites/{DEFAULT_SITE_ID}",
            comments_enabled=False,
        )
        _save_raw([default.to_dict()])
        sites = [default.to_dict()]
        logger.info("Created site registry with default site at %s", path)

    from config import CONTENT_DIR_PATH

    records = [_dict_to_record(s) for s in sites]

    if CONTENT_DIR_PATH is not None:
        CONTENT_DIR_PATH.mkdir(parents=True, exist_ok=True)
        default_dir = CONTENT_DIR_PATH / "sites" / DEFAULT_SITE_ID
        # Migrate only when default dir is empty/missing and flat content exists
        has_flat = any(
            p.name not in ("sites", "_deleted") for p in CONTENT_DIR_PATH.iterdir()
        ) if CONTENT_DIR_PATH.is_dir() else False
        default_populated = (
            default_dir.is_dir() and any(default_dir.iterdir())
        )
        if has_flat and not default_populated:
            _migrate_flat_content_to_default(CONTENT_DIR_PATH)
        default_dir.mkdir(parents=True, exist_ok=True)

        _migrate_menus_json_to_default(CONTENT_DIR_PATH)
        _migrate_assets_to_default(CONTENT_DIR_PATH)

        for rec in records:
            site_dir = CONTENT_DIR_PATH / rec.content_relpath
            site_dir.mkdir(parents=True, exist_ok=True)
            _seed_site_structure_files(rec.id, site_dir)

    if _migrate_comments_enabled(sites, CONTENT_DIR_PATH):
        _save_raw(sites)
        logger.info("Migrated comments_enabled on site registry at %s", path)
        records = [_dict_to_record(s) for s in sites]

    return records
