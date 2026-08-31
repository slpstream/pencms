"""MCP tools for site presentation / SEO bootstrap (theme, identity, Meta, Social, Indexing).

Empty-safe and order-independent relative to menus, authors, and content.
Agents are bound to JWT ``site_id`` — no cross-site edits.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from models.user import UserPublic
from routers.auth import get_current_user
from routers.mcp_tools import require_scope, resolve_mcp_site_id
from services.site_service import (
    _UNSET,
    ensure_sites_initialized,
    get_site,
    join_site_assets_path,
    update_site,
)
from services.social_preview import (
    SOCIAL_STRING_KEYS,
    effective_theme_name,
    list_installed_themes,
    resolve_social_preview,
    site_social_overrides,
    theme_social_preview_defaults,
)

router = APIRouter(prefix="/api/v1", tags=["mcp"])

_LOGO_EXTS = ("png", "jpg", "jpeg", "svg", "webp", "gif")
_FAVICON_EXTS = ("ico", "png", "svg", "gif", "webp")

UPDATE_PRESENTATION_DOC = """Sparse update of presentation / SEO fields for the bound site.

Absent keys are unchanged. Empty string clears a string field (inherit theme /
install defaults). ``og_accent_bar`` / ``og_watermark_enabled``: omit to leave,
``null`` to clear, bool to set.

Allowlisted: theme, identity (sitename, tagline, hero_title, hero_image,
contact_email, display_logo, comments_enabled), Site Meta (title_template, meta_description,
keywords), Indexing (robots_*, robots_txt, sitemap_enabled, verification
tokens, IndexNow, Content-Signal training, seo_redirects), and Tier-1 Social overrides.

Does not accept name, domain, publish secrets, or Tier-3 engine knobs.
Works on a blank site — no menus, authors, or posts required.

Example:
{"sitename":"Acme Blog","tagline":"Notes","theme":"starter","twitter_card":"summary_large_image"}
"""


class SeoRedirectItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    from_path: str = Field(..., alias="from", description="Source path starting with /")
    to: str = Field(..., description="Destination path starting with /")

    def as_pair(self) -> dict:
        return {"from": self.from_path, "to": self.to}


def _social_str_field():
    return Field(
        None, description="Social override; empty string clears (inherit theme)"
    )


class UpdateSitePresentationBody(BaseModel):
    theme: Optional[str] = Field(
        None, description="Active theme override; empty string clears"
    )
    sitename: Optional[str] = Field(
        None, description="Public sitename; empty string clears"
    )
    display_logo: Optional[bool] = Field(None, description="Logo display override")
    comments_enabled: Optional[bool] = Field(
        None, description="Reader comments on posts; false when omitted"
    )
    tagline: Optional[str] = Field(None, description="Tagline; empty string clears")
    hero_title: Optional[str] = Field(
        None, description="Hero title; empty string clears"
    )
    hero_image: Optional[str] = Field(
        None, description="Hero image path; empty string clears"
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
    robots_index: Optional[bool] = Field(None, description="Default allow indexing")
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


def _mcp_og_font_catalog(theme_name: str, site_id: str):
    from services.og_image import build_og_font_catalog

    return build_og_font_catalog(
        theme_social_preview_defaults(theme_name, site_id=site_id)
    )


async def _branding_presence(site_id: str) -> Dict[str, Optional[str]]:
    """Return conventional logo/favicon logical paths if files exist."""
    from config import content_storage

    logo_path: Optional[str] = None
    favicon_path: Optional[str] = None
    for ext in _LOGO_EXTS:
        logical = f"images/logo.{ext}"
        storage = join_site_assets_path(site_id, logical)
        if await content_storage.exists(storage):
            logo_path = logical
            break
    for ext in _FAVICON_EXTS:
        logical = f"images/favicon.{ext}"
        storage = join_site_assets_path(site_id, logical)
        if await content_storage.exists(storage):
            favicon_path = logical
            break
    return {"logo": logo_path, "favicon": favicon_path}


async def _presentation_payload(site_id: str) -> Dict[str, Any]:
    ensure_sites_initialized()
    record = get_site(site_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Unknown site_id: {site_id}")

    theme_eff = effective_theme_name(record)
    branding = await _branding_presence(site_id)
    return {
        "site_id": record.id,
        "theme": record.theme,
        "effective_theme": theme_eff,
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
        "social_overrides": site_social_overrides(record),
        "social_preview_defaults": theme_social_preview_defaults(
            theme_eff, site_id=site_id
        ),
        "og_font_catalog": _mcp_og_font_catalog(theme_eff, site_id),
        "social_effective": resolve_social_preview(record, theme_name=theme_eff),
        "branding": branding,
    }


@router.get(
    "/mcp/themes",
    operation_id="list_themes",
    dependencies=[Depends(require_scope("read"))],
)
async def list_themes(
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> List[Dict[str, str]]:
    """List install themes plus this site's custom entry when a theme tree exists."""
    site_id = resolve_mcp_site_id(request)
    return list_installed_themes(site_id=site_id)


@router.get(
    "/mcp/site-presentation",
    operation_id="get_site_presentation",
    dependencies=[Depends(require_scope("read"))],
)
async def get_site_presentation(
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    """Read resolved presentation / SEO for the bound site (empty-safe)."""
    site_id = resolve_mcp_site_id(request)
    return await _presentation_payload(site_id)


@router.patch(
    "/mcp/site-presentation",
    operation_id="update_site_presentation",
    dependencies=[Depends(require_scope("write:seo"))],
    summary="Update site presentation / SEO",
    description=UPDATE_PRESENTATION_DOC,
)
async def update_site_presentation(
    body: UpdateSitePresentationBody,
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    site_id = resolve_mcp_site_id(request)
    ensure_sites_initialized()
    if get_site(site_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown site_id: {site_id}")

    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one field to update",
        )
    social_present = {k for k in SOCIAL_STRING_KEYS if k in fields}
    try:
        update_site(
            site_id,
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
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await _presentation_payload(site_id)


update_site_presentation.__doc__ = UPDATE_PRESENTATION_DOC
