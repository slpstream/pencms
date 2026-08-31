"""Site registry admin API (Option C multisite + lifecycle)."""

from typing import Dict, FrozenSet, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from models.user import UserPublic
from routers.auth import get_current_user
from services.authz import (
    accessible_site_ids,
    assert_capability,
    resolve_request_user,
)
from services.site_service import (
    _UNSET,
    ensure_sites_initialized,
    get_site,
    get_site_content_prefix,
    list_sites,
    update_site,
)
from services.i18n_service import (
    is_i18n_active,
    normalize_language_config,
)
from services.social_preview import (
    SOCIAL_BOOL_KEYS,
    SOCIAL_STRING_KEYS,
    apply_social_draft,
    effective_theme_name,
    resolve_social_preview,
    theme_social_preview_defaults,
)

router = APIRouter(prefix="/sites", tags=["sites"])

_REGISTRY_KEYS: FrozenSet[str] = frozenset(
    {
        "name",
        "domain",
        "language",
        "languages",
        "language_labels",
        "translation_automation_paused",
        "feedback_relay_url",
        "feedback_submission_key",
        "feedback_fetch_token",
    }
)
_SEO_KEYS: FrozenSet[str] = frozenset(
    {
        "theme",
        "sitename",
        "display_logo",
        "comments_enabled",
        "tagline",
        "hero_title",
        "hero_image",
        "contact_email",
        "title_template",
        "meta_description",
        "keywords",
        "robots_index",
        "robots_follow",
        "robots_txt",
        "sitemap_enabled",
        "google_site_verification",
        "bing_site_verification",
        "indexnow_enabled",
        "indexnow_key",
        "content_signal_ai_train",
        "seo_redirects",
        "social_links",
        *SOCIAL_STRING_KEYS,
        *SOCIAL_BOOL_KEYS,
    }
)


async def _preflight_language_slug_collisions(
    site_id: str,
    *,
    language,
    languages,
) -> None:
    config = normalize_language_config(language=language, languages=languages)
    if not config.active:
        return
    from config import content_storage

    root = get_site_content_prefix(site_id)
    try:
        items = await content_storage.list_dir(root)
    except Exception:
        return
    for item in items:
        name = item.split("/")[-1]
        full = f"{root}/{name}" if not item.startswith(root) else item
        slug = None
        offending_path = full
        if await content_storage.is_dir(full):
            index_path = f"{full}/index.md"
            if await content_storage.exists(index_path):
                slug = name
                offending_path = index_path
        elif name.endswith(".md") and not name.startswith("_"):
            slug = name[:-3]
        if slug in config.languages:
            raise ValueError(
                f"{offending_path}: slug '{slug}' shadows a configured language code. "
                "Fix: rename the content slug or remove that language before enabling i18n."
            )


def _assert_patch_caps(request: Request, site_id: str, fields: dict) -> None:
    """SEO-only PATCH needs write:seo; registry-only needs manage:sites; mixed needs both."""
    keys = set(fields)
    needs_seo = bool(keys & _SEO_KEYS)
    needs_registry = bool(keys & _REGISTRY_KEYS)
    if needs_seo:
        assert_capability(request, "write:seo", site_id=site_id)
    if needs_registry:
        assert_capability(request, "manage:sites", site_id=site_id)
    if not needs_seo and not needs_registry:
        # Unknown keys only — treat as registry mutation.
        assert_capability(request, "manage:sites", site_id=site_id)


class SeoRedirectItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    from_path: str = Field(..., alias="from", description="Source path starting with /")
    to: str = Field(..., description="Destination path starting with /")

    def as_pair(self) -> dict:
        return {"from": self.from_path, "to": self.to}


class SocialLinkItem(BaseModel):
    platform: str = Field("custom", description="Platform key e.g. twitter, bluesky, custom")
    url: str = Field(..., description="Link URL")
    label: Optional[str] = Field(None, description="Display label for custom platform")


def _og_font_catalog(theme_name: str, site_id: str):
    from services.og_image import build_og_font_catalog

    return build_og_font_catalog(
        theme_social_preview_defaults(theme_name, site_id=site_id)
    )


def _site_payload(record) -> dict:
    theme_name = record.theme or "starter"
    return {
        "id": record.id,
        "name": record.name,
        "domain": record.domain,
        "content_relpath": record.content_relpath,
        "language": record.language,
        "languages": record.languages,
        "language_labels": record.language_labels,
        "translation_automation_paused": record.translation_automation_paused,
        "i18n_active": is_i18n_active(record.language, record.languages),
        "theme": record.theme,
        "sitename": record.sitename,
        "display_logo": record.display_logo,
        "comments_enabled": bool(record.comments_enabled),
        "tagline": record.tagline,
        "hero_title": record.hero_title,
        "hero_image": record.hero_image,
        "contact_email": record.contact_email,
        "title_template": record.title_template,
        "meta_description": record.meta_description,
        "keywords": record.keywords,
        "robots_index": record.robots_index,
        "robots_follow": record.robots_follow,
        "robots_txt": record.robots_txt,
        "sitemap_enabled": record.sitemap_enabled,
        "google_site_verification": record.google_site_verification,
        "bing_site_verification": record.bing_site_verification,
        "indexnow_enabled": record.indexnow_enabled,
        "indexnow_key": record.indexnow_key,
        "content_signal_ai_train": record.content_signal_ai_train,
        "seo_redirects": record.seo_redirects or [],
        "social_links": record.social_links,
        "og_accent_color": record.og_accent_color,
        "og_vignette_color": record.og_vignette_color,
        "og_text_color": record.og_text_color,
        "og_bar_color": record.og_bar_color,
        "og_font": record.og_font,
        "og_headline_style": record.og_headline_style,
        "og_text_case": record.og_text_case,
        "og_grade_preset": record.og_grade_preset,
        "og_accent_bar": record.og_accent_bar,
        "og_watermark_enabled": record.og_watermark_enabled,
        "og_watermark": record.og_watermark,
        "og_watermark_source": record.og_watermark_source,
        "og_watermark_layout": record.og_watermark_layout,
        "og_watermark_corner": record.og_watermark_corner,
        "og_watermark_scale": record.og_watermark_scale,
        "og_default_hero": record.og_default_hero,
        "og_default_image": record.og_default_image,
        "og_fallback_title": record.og_fallback_title,
        "og_title_fallback": record.og_title_fallback,
        "og_description_fallback": record.og_description_fallback,
        "twitter_card": record.twitter_card,
        "social_preview_defaults": theme_social_preview_defaults(
            theme_name, site_id=record.id
        ),
        "og_font_catalog": _og_font_catalog(theme_name, record.id),
        "feedback_relay_url": record.feedback_relay_url,
        "feedback_submission_key": record.feedback_submission_key,
        "feedback_relay_cursor": record.feedback_relay_cursor,
        "has_feedback_fetch_token": bool(record.feedback_fetch_token),
    }


def _social_str_field():
    return Field(
        None, description="Social override; empty string clears (inherit theme)"
    )


class UpdateSiteBody(BaseModel):
    name: Optional[str] = Field(None, description="Display name")
    domain: Optional[str] = Field(
        None, description="Public hostname; empty string clears"
    )
    language: Optional[str] = Field(
        None,
        description="Default normalized BCP-47 language tag",
    )
    languages: Optional[List[str]] = Field(
        None,
        description="Ordered unique BCP-47 tags; include language when non-empty",
    )
    language_labels: Optional[Dict[str, str]] = Field(
        None,
        description="Display-label overrides keyed by BCP-47 tag",
    )
    translation_automation_paused: Optional[bool] = Field(
        None,
        description="Whether translation automation is paused for this site",
    )
    theme: Optional[str] = Field(
        None, description="Active theme override; empty string clears"
    )
    sitename: Optional[str] = Field(
        None, description="Public sitename; empty string clears"
    )
    display_logo: Optional[bool] = Field(
        None, description="Logo display override"
    )
    comments_enabled: Optional[bool] = Field(
        None, description="Reader comments on posts; false when omitted"
    )
    tagline: Optional[str] = Field(
        None, description="Tagline; empty string clears"
    )
    hero_title: Optional[str] = Field(
        None, description="Hero title; empty string clears"
    )
    hero_image: Optional[str] = Field(
        None, description="Hero image; empty string clears"
    )
    contact_email: Optional[str] = Field(
        None, description="Contact email; empty string clears"
    )
    title_template: Optional[str] = Field(
        None, description="Page title template; empty string clears"
    )
    meta_description: Optional[str] = Field(
        None, description="Default meta description; empty string clears"
    )
    keywords: Optional[str] = Field(
        None, description="Comma-separated keywords; empty string clears"
    )
    robots_index: Optional[bool] = Field(
        None, description="Default allow indexing"
    )
    robots_follow: Optional[bool] = Field(
        None, description="Default allow following links"
    )
    robots_txt: Optional[str] = Field(
        None, description="Custom robots.txt body; empty string clears"
    )
    sitemap_enabled: Optional[bool] = Field(
        None, description="Sitemap discovery flag"
    )
    google_site_verification: Optional[str] = Field(
        None,
        description="Google Search Console verification token; empty string clears",
    )
    bing_site_verification: Optional[str] = Field(
        None,
        description="Bing Webmaster verification token; empty string clears",
    )
    indexnow_enabled: Optional[bool] = Field(
        None, description="IndexNow ping after public HTTPS publish"
    )
    indexnow_key: Optional[str] = Field(
        None,
        description="Per-site IndexNow key; empty string regenerates when enabled",
    )
    content_signal_ai_train: Optional[bool] = Field(
        None, description="Content-Signal ai-train (training) bit"
    )
    seo_redirects: Optional[List[SeoRedirectItem]] = Field(
        None, description="Static 301 list; empty list clears"
    )
    social_links: Optional[List[SocialLinkItem]] = Field(
        None,
        description="Per-site social links list",
    )
    og_accent_color: Optional[str] = _social_str_field()
    og_vignette_color: Optional[str] = _social_str_field()
    og_text_color: Optional[str] = _social_str_field()
    og_bar_color: Optional[str] = _social_str_field()
    og_font: Optional[str] = _social_str_field()
    og_headline_style: Optional[str] = _social_str_field()
    og_text_case: Optional[str] = _social_str_field()
    og_grade_preset: Optional[str] = _social_str_field()
    og_accent_bar: Optional[bool] = Field(
        None,
        description="Slanted accent bar; null clears (inherit theme)",
    )
    og_watermark_enabled: Optional[bool] = Field(
        None,
        description="Watermark overlay; null clears (inherit theme)",
    )
    og_watermark: Optional[str] = _social_str_field()
    og_watermark_source: Optional[str] = _social_str_field()
    og_watermark_layout: Optional[str] = _social_str_field()
    og_watermark_corner: Optional[str] = _social_str_field()
    og_watermark_scale: Optional[str] = _social_str_field()
    og_default_hero: Optional[str] = _social_str_field()
    og_default_image: Optional[str] = _social_str_field()
    og_fallback_title: Optional[str] = _social_str_field()
    og_title_fallback: Optional[str] = _social_str_field()
    og_description_fallback: Optional[str] = _social_str_field()
    twitter_card: Optional[str] = _social_str_field()
    feedback_relay_url: Optional[str] = Field(
        None,
        description=(
            "Public relay origin; empty clears (sync/bake use "
            "https://feedback.pencms.org). Optional override for a self-hosted queue."
        ),
    )
    feedback_submission_key: Optional[str] = Field(
        None,
        description="Public 32-char hex queue key; empty string clears",
    )
    feedback_fetch_token: Optional[str] = Field(
        None,
        description=(
            "Private 64-char hex drain token. Write-only: never returned on GET. "
            "Empty string rotates (new token + re-register). "
            "Omitted leaves the existing token."
        ),
    )


class OgPreviewBody(BaseModel):
    """Draft Social overrides for one synthetic OG JPEG. Does not persist."""

    title: Optional[str] = Field(
        None, description="Sample headline; default is resolved og_fallback_title"
    )
    use_site_hero: bool = Field(
        False,
        description="When true, use the site hero_image as the sample background",
    )
    og_accent_color: Optional[str] = _social_str_field()
    og_vignette_color: Optional[str] = _social_str_field()
    og_text_color: Optional[str] = _social_str_field()
    og_bar_color: Optional[str] = _social_str_field()
    og_font: Optional[str] = _social_str_field()
    og_headline_style: Optional[str] = _social_str_field()
    og_text_case: Optional[str] = _social_str_field()
    og_grade_preset: Optional[str] = _social_str_field()
    og_accent_bar: Optional[bool] = Field(
        None,
        description="Slanted accent bar; null clears (inherit theme)",
    )
    og_watermark_enabled: Optional[bool] = Field(
        None,
        description="Watermark overlay; null clears (inherit theme)",
    )
    og_watermark: Optional[str] = _social_str_field()
    og_watermark_source: Optional[str] = _social_str_field()
    og_watermark_layout: Optional[str] = _social_str_field()
    og_watermark_corner: Optional[str] = _social_str_field()
    og_watermark_scale: Optional[str] = _social_str_field()
    og_default_hero: Optional[str] = _social_str_field()
    og_default_image: Optional[str] = _social_str_field()
    og_fallback_title: Optional[str] = _social_str_field()
    og_title_fallback: Optional[str] = _social_str_field()
    og_description_fallback: Optional[str] = _social_str_field()
    twitter_card: Optional[str] = _social_str_field()
    hero_data_url: Optional[str] = Field(
        None,
        description="Optional in-memory hero as data:image/...;base64,... (preview only)",
    )
    watermark_data_url: Optional[str] = Field(
        None,
        description="Optional in-memory watermark as data:image/...;base64,... (preview only)",
    )


@router.get("")
async def get_sites(
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
):
    """List sites this actor may access (admin: all; author: memberships; agent: JWT site)."""
    user, payload = resolve_request_user(request)
    ensure_sites_initialized()
    records = list_sites()
    allowed = set(
        accessible_site_ids(
            user,
            token_payload=payload,
            all_site_ids=[s.id for s in records],
        )
    )
    from services.feedback_service import ensure_feedback_relay

    payloads = []
    for site in records:
        if site.id not in allowed:
            continue
        site = await ensure_feedback_relay(site.id)
        payloads.append(_site_payload(site))
    return {"sites": payloads}


@router.patch("/{site_id}")
async def patch_site(
    site_id: str,
    body: UpdateSiteBody,
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
):
    """Soft-update site name, domain, and/or presentation fields."""
    ensure_sites_initialized()
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one field to update",
        )
    _assert_patch_caps(request, site_id, fields)
    if "theme" in fields:
        theme_val = fields.get("theme")
        if isinstance(theme_val, str) and theme_val.strip() == "custom":
            from services.theme_customize_service import has_site_custom_theme

            if not has_site_custom_theme(site_id):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Cannot set theme to 'custom': no site theme tree exists. "
                        "Fork a base theme first via POST /api/sites/{id}/theme/fork."
                    ),
                )
    social_present = {k for k in SOCIAL_STRING_KEYS if k in fields}
    try:
        if "language" in fields or "languages" in fields:
            current = get_site(site_id)
            if current is None:
                raise ValueError(f"Unknown site_id: {site_id}")
            await _preflight_language_slug_collisions(
                site_id,
                language=fields.get("language", current.language),
                languages=fields.get("languages", current.languages),
            )
        record = update_site(
            site_id,
            name=fields.get("name") if "name" in fields else None,
            domain=fields.get("domain") if "domain" in fields else None,
            language=fields["language"] if "language" in fields else _UNSET,
            languages=fields["languages"] if "languages" in fields else _UNSET,
            language_labels=(
                fields["language_labels"]
                if "language_labels" in fields
                else _UNSET
            ),
            translation_automation_paused=(
                fields["translation_automation_paused"]
                if "translation_automation_paused" in fields
                else _UNSET
            ),
            theme=fields.get("theme") if "theme" in fields else None,
            sitename=fields.get("sitename") if "sitename" in fields else None,
            display_logo=(
                fields.get("display_logo") if "display_logo" in fields else None
            ),
            comments_enabled=(
                fields.get("comments_enabled")
                if "comments_enabled" in fields
                else None
            ),
            tagline=fields.get("tagline") if "tagline" in fields else None,
            hero_title=fields.get("hero_title") if "hero_title" in fields else None,
            hero_image=fields.get("hero_image") if "hero_image" in fields else None,
            contact_email=(
                fields.get("contact_email") if "contact_email" in fields else None
            ),
            title_template=(
                fields.get("title_template") if "title_template" in fields else None
            ),
            meta_description=(
                fields.get("meta_description")
                if "meta_description" in fields
                else None
            ),
            keywords=fields.get("keywords") if "keywords" in fields else None,
            robots_index=(
                fields.get("robots_index") if "robots_index" in fields else None
            ),
            robots_follow=(
                fields.get("robots_follow") if "robots_follow" in fields else None
            ),
            robots_txt=(
                fields.get("robots_txt") if "robots_txt" in fields else None
            ),
            sitemap_enabled=(
                fields.get("sitemap_enabled")
                if "sitemap_enabled" in fields
                else None
            ),
            google_site_verification=(
                fields.get("google_site_verification")
                if "google_site_verification" in fields
                else None
            ),
            bing_site_verification=(
                fields.get("bing_site_verification")
                if "bing_site_verification" in fields
                else None
            ),
            indexnow_enabled=(
                fields.get("indexnow_enabled")
                if "indexnow_enabled" in fields
                else None
            ),
            indexnow_key=(
                fields.get("indexnow_key")
                if "indexnow_key" in fields
                else _UNSET
            ),
            content_signal_ai_train=(
                fields.get("content_signal_ai_train")
                if "content_signal_ai_train" in fields
                else None
            ),
            seo_redirects=(
                [item.as_pair() for item in body.seo_redirects]
                if "seo_redirects" in fields
                else _UNSET
            ),
            social_links=fields.get("social_links") if "social_links" in fields else _UNSET,
            og_accent_color=fields.get("og_accent_color"),
            og_vignette_color=fields.get("og_vignette_color"),
            og_text_color=fields.get("og_text_color"),
            og_bar_color=fields.get("og_bar_color"),
            og_font=fields.get("og_font"),
            og_headline_style=fields.get("og_headline_style"),
            og_text_case=fields.get("og_text_case"),
            og_grade_preset=fields.get("og_grade_preset"),
            og_accent_bar=(
                fields["og_accent_bar"] if "og_accent_bar" in fields else _UNSET
            ),
            og_watermark_enabled=(
                fields["og_watermark_enabled"]
                if "og_watermark_enabled" in fields
                else _UNSET
            ),
            og_watermark=fields.get("og_watermark"),
            og_watermark_source=fields.get("og_watermark_source"),
            og_watermark_layout=fields.get("og_watermark_layout"),
            og_watermark_corner=fields.get("og_watermark_corner"),
            og_watermark_scale=fields.get("og_watermark_scale"),
            og_default_hero=fields.get("og_default_hero"),
            og_default_image=fields.get("og_default_image"),
            og_fallback_title=fields.get("og_fallback_title"),
            og_title_fallback=fields.get("og_title_fallback"),
            og_description_fallback=fields.get("og_description_fallback"),
            twitter_card=fields.get("twitter_card"),
            _social_string_keys_present=social_present,
            feedback_relay_url=(
                fields["feedback_relay_url"]
                if "feedback_relay_url" in fields
                else _UNSET
            ),
            feedback_submission_key=(
                fields["feedback_submission_key"]
                if "feedback_submission_key" in fields
                else _UNSET
            ),
            feedback_fetch_token=(
                fields["feedback_fetch_token"]
                if (
                    "feedback_fetch_token" in fields
                    and str(fields.get("feedback_fetch_token") or "").strip()
                )
                else _UNSET
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    rotate_fetch = (
        "feedback_fetch_token" in fields
        and not str(fields.get("feedback_fetch_token") or "").strip()
    )
    patched_relay_url = (
        "feedback_relay_url" in fields
        and bool(str(fields.get("feedback_relay_url") or "").strip())
    )
    if rotate_fetch or patched_relay_url:
        from services.feedback_service import ensure_feedback_relay

        relay_arg = (
            (str(fields.get("feedback_relay_url") or "").strip() or None)
            if "feedback_relay_url" in fields
            else None
        )
        record = await ensure_feedback_relay(
            site_id,
            relay_url=relay_arg,
            rotate_fetch_token=rotate_fetch,
        )

    return {**_site_payload(record), "message": "Site updated"}


@router.post("/{site_id}/og-preview")
async def post_og_preview(
    site_id: str,
    body: OgPreviewBody,
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
):
    """Render one synthetic OG JPEG from draft Social fields. Does not save."""
    assert_capability(request, "write:seo", site_id=site_id)
    ensure_sites_initialized()
    record = get_site(site_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Unknown site '{site_id}'")

    fields = body.model_dump(exclude_unset=True)
    title = fields.pop("title", None)
    use_site_hero = bool(fields.pop("use_site_hero", False))
    hero_data_url = fields.pop("hero_data_url", None)
    watermark_data_url = fields.pop("watermark_data_url", None)

    from services.og_image import (
        decode_preview_data_url,
        render_og_preview,
        theme_path_for_site,
    )

    hero_image = None
    watermark_image = None
    try:
        if hero_data_url:
            hero_image = decode_preview_data_url(hero_data_url)
        if watermark_data_url:
            watermark_image = decode_preview_data_url(watermark_data_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    draft = apply_social_draft(record, fields)
    cfg = resolve_social_preview(draft, theme_name=effective_theme_name(record))
    sample = (title or "").strip() or (cfg.get("og_fallback_title") or "ARCHIVAL RECORD")
    hero_source = None
    if hero_image is not None:
        hero_source = hero_image
    elif use_site_hero and record.hero_image:
        hero_source = record.hero_image
    try:
        jpeg = render_og_preview(
            sample,
            cfg,
            site_id=site_id,
            theme_path=theme_path_for_site(record),
            hero_source=hero_source,
            watermark_image=watermark_image,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OG preview failed: {e}") from e
    return Response(content=jpeg, media_type="image/jpeg")
