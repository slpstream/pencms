"""Site registry — init, migrate, create, validate."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def isolated_content(temp_data_root, monkeypatch):
    """Point content storage at the temp root and reset site registry."""
    import config
    from services.storage_provider import LocalStorageProvider
    import services.file_service as file_service
    import services.site_service as site_service

    content = temp_data_root / "content"
    content.mkdir(exist_ok=True)
    # Wipe prior registry / sites between tests
    sites_yaml = temp_data_root / "data" / "sites.yaml"
    if sites_yaml.exists():
        sites_yaml.unlink()
    sites_dir = content / "sites"
    if sites_dir.exists():
        shutil.rmtree(sites_dir)
    for child in list(content.iterdir()):
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()

    provider = LocalStorageProvider(str(content))
    monkeypatch.setattr(config, "CONTENT_DIR_PATH", content)
    monkeypatch.setattr(config, "content_storage", provider)
    monkeypatch.setattr(file_service, "content_storage", provider)
    yield content


def _listed_site(authed_client, site_id: str) -> dict:
    resp = authed_client.get("/api/sites")
    assert resp.status_code == 200, resp.text
    for row in resp.json()["sites"]:
        if row["id"] == site_id:
            return row
    raise AssertionError(f"site {site_id!r} missing from GET /api/sites")


def test_ensure_creates_default_registry(isolated_content, temp_data_root):
    from services.site_service import ensure_sites_initialized, list_sites

    records = ensure_sites_initialized()
    assert any(r.id == "default" for r in records)
    assert (isolated_content / "sites" / "default").is_dir()
    registry = temp_data_root / "data" / "sites.yaml"
    assert registry.is_file()
    data = yaml.safe_load(registry.read_text())
    assert data["sites"][0]["id"] == "default"
    assert data["sites"][0]["language"] == "en"
    assert data["sites"][0]["languages"] == []
    assert data["sites"][0]["language_labels"] == {}
    assert data["sites"][0]["translation_automation_paused"] is False


def test_migrate_flat_content_once(isolated_content, temp_data_root):
    from services.site_service import ensure_sites_initialized

    page = isolated_content / "hello"
    page.mkdir()
    (page / "index.md").write_text("---\nname: Hello\ncategory: posts\n---\nHi\n")
    (isolated_content / "notes.md").write_text("---\nname: Notes\ncategory: posts\n---\n")

    ensure_sites_initialized()
    assert not (isolated_content / "hello").exists()
    assert (isolated_content / "sites" / "default" / "hello" / "index.md").is_file()
    assert (isolated_content / "sites" / "default" / "notes.md").is_file()

    # Idempotent — second call does not duplicate / fail
    ensure_sites_initialized()
    assert (isolated_content / "sites" / "default" / "hello" / "index.md").is_file()


def test_create_second_site(isolated_content, temp_data_root):
    from services.site_service import create_site, ensure_sites_initialized, list_sites

    ensure_sites_initialized()
    create_site("blog", "Blog Site", domain="blog.example")
    ids = {s.id for s in list_sites()}
    assert ids == {"default", "blog"}
    assert (isolated_content / "sites" / "blog").is_dir()


def test_create_site_defaults_theme_to_starter(isolated_content):
    from services.site_service import create_site, ensure_sites_initialized, get_site

    ensure_sites_initialized()
    record = create_site("wiki", "Wiki")
    assert record.theme == "starter"
    assert get_site("wiki").theme == "starter"


def test_create_site_honors_explicit_theme(isolated_content):
    from services.site_service import create_site, ensure_sites_initialized, get_site

    ensure_sites_initialized()
    record = create_site("wiki", "Wiki", theme="editorial")
    assert record.theme == "editorial"
    assert get_site("wiki").theme == "editorial"


def test_reject_bad_site_id(isolated_content):
    from services.site_service import ensure_sites_initialized, validate_site_id

    ensure_sites_initialized()
    for bad in ("", "A", "has space", "x", "Bad!"):
        with pytest.raises(ValueError):
            validate_site_id(bad)


@pytest.mark.pro
def test_sites_api(authed_client, isolated_content, temp_data_root):
    pytest.importorskip("pencms_pro", reason="sites CRUD is Pro overlay")
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    resp = authed_client.get("/api/sites")
    assert resp.status_code == 200, resp.text
    ids = [s["id"] for s in resp.json()["sites"]]
    assert "default" in ids

    resp = authed_client.post(
        "/api/sites",
        json={"id": "wiki", "name": "Wiki"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == "wiki"
    assert resp.json()["theme"] == "starter"

    resp = authed_client.post(
        "/api/sites",
        json={"id": "wiki", "name": "Dup"},
    )
    assert resp.status_code == 400


def test_normalize_domain():
    from services.site_service import normalize_domain

    assert normalize_domain(None) is None
    assert normalize_domain("") is None
    assert normalize_domain("  ") is None
    assert normalize_domain("Wiki.Example") == "wiki.example"
    assert normalize_domain("https://Wiki.Example:443/path") == "wiki.example"
    assert normalize_domain("wiki.localhost:8080") == "wiki.localhost"
    assert normalize_domain("wiki.example.") == "wiki.example"


@pytest.mark.pro
def test_domain_uniqueness_create_and_patch(authed_client, isolated_content):
    pytest.importorskip("pencms_pro", reason="sites CRUD is Pro overlay")
    from services.site_service import create_site, ensure_sites_initialized

    ensure_sites_initialized()
    create_site("wiki", "Wiki", domain="wiki.example")

    resp = authed_client.post(
        "/api/sites",
        json={"id": "docs", "name": "Docs", "domain": "https://Wiki.Example:443/"},
    )
    assert resp.status_code == 400
    assert "already assigned" in resp.json()["detail"].lower()

    create_site("blog", "Blog")
    resp = authed_client.patch(
        "/api/sites/blog",
        json={"domain": "wiki.example"},
    )
    assert resp.status_code == 400

    # Same site may keep its own domain
    resp = authed_client.patch(
        "/api/sites/wiki",
        json={"domain": "wiki.example", "name": "Wiki 2"},
    )
    assert resp.status_code == 200, resp.text


def test_clear_domain_frees_and_host_resolve(isolated_content):
    from services.site_service import (
        create_site,
        ensure_sites_initialized,
        resolve_site_id_by_host,
        update_site,
    )

    ensure_sites_initialized()
    create_site("wiki", "Wiki", domain="wiki.localhost")
    assert resolve_site_id_by_host("wiki.localhost:8080") == "wiki"
    assert resolve_site_id_by_host("unknown.localhost") == "default"
    assert resolve_site_id_by_host(None) == "default"
    assert resolve_site_id_by_host("") == "default"

    update_site("wiki", domain="")
    assert resolve_site_id_by_host("wiki.localhost") == "default"
    create_site("docs", "Docs", domain="wiki.localhost")
    assert resolve_site_id_by_host("Wiki.Localhost") == "docs"


def test_branding_and_theme_soft_patch(authed_client, isolated_content):
    from services.site_service import create_site, ensure_sites_initialized, get_site

    ensure_sites_initialized()
    create_site(
        "wiki",
        "Wiki",
        domain="wiki.example",
        theme="editorial",
        sitename="Wiki Site",
        display_logo=False,
        tagline="Notes",
        hero_title="Welcome",
        hero_image="/hero.webp",
        contact_email="wiki@example.com",
    )
    data = _listed_site(authed_client, "wiki")
    assert data["theme"] == "editorial"
    assert data["sitename"] == "Wiki Site"
    assert data["display_logo"] is False
    assert data["comments_enabled"] is False
    assert data["tagline"] == "Notes"
    assert data["hero_title"] == "Welcome"
    assert data["hero_image"] == "/hero.webp"
    assert data["contact_email"] == "wiki@example.com"

    resp = authed_client.patch(
        "/api/sites/wiki",
        json={
            "sitename": "Knowledge",
            "theme": "",
            "contact_email": "editors@wiki.example",
            "title_template": "%page% | %site%",
            "meta_description": "Wiki notes and docs",
            "keywords": "wiki, notes, docs",
            "robots_index": False,
            "robots_follow": True,
            "robots_txt": "User-agent: *\nDisallow: /",
            "sitemap_enabled": False,
            "google_site_verification": "google-token",
            "bing_site_verification": "bing-token",
            "comments_enabled": True,
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["sitename"] == "Knowledge"
    assert resp.json()["comments_enabled"] is True
    assert resp.json()["theme"] is None
    assert resp.json()["contact_email"] == "editors@wiki.example"
    assert resp.json()["title_template"] == "%page% | %site%"
    assert resp.json()["meta_description"] == "Wiki notes and docs"
    assert resp.json()["keywords"] == "wiki, notes, docs"
    assert resp.json()["robots_index"] is False
    assert resp.json()["robots_follow"] is True
    assert resp.json()["robots_txt"] == "User-agent: *\nDisallow: /"
    assert resp.json()["sitemap_enabled"] is False
    assert resp.json()["google_site_verification"] == "google-token"
    assert resp.json()["bing_site_verification"] == "bing-token"
    site = get_site("wiki")
    assert site.sitename == "Knowledge"
    assert site.theme is None
    assert site.contact_email == "editors@wiki.example"
    assert site.title_template == "%page% | %site%"
    assert site.meta_description == "Wiki notes and docs"
    assert site.keywords == "wiki, notes, docs"
    assert site.robots_index is False
    assert site.robots_follow is True
    assert site.robots_txt == "User-agent: *\nDisallow: /"
    assert site.sitemap_enabled is False
    assert site.google_site_verification == "google-token"
    assert site.bing_site_verification == "bing-token"
    assert site.comments_enabled is True

    resp = authed_client.patch(
        "/api/sites/wiki",
        json={
            "contact_email": "",
            "meta_description": "",
            "keywords": "",
            "robots_txt": "",
            "google_site_verification": "",
            "bing_site_verification": "",
            "robots_index": True,
            "sitemap_enabled": True,
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["contact_email"] is None
    assert resp.json()["meta_description"] is None
    assert resp.json()["keywords"] is None
    assert resp.json()["robots_txt"] is None
    assert resp.json()["google_site_verification"] is None
    assert resp.json()["bing_site_verification"] is None
    assert resp.json()["robots_index"] is True
    assert resp.json()["sitemap_enabled"] is True
    assert get_site("wiki").contact_email is None
    assert get_site("wiki").meta_description is None
    assert get_site("wiki").keywords is None
    assert get_site("wiki").robots_txt is None
    assert get_site("wiki").google_site_verification is None
    assert get_site("wiki").bing_site_verification is None
    assert get_site("wiki").robots_index is True
    assert get_site("wiki").sitemap_enabled is True
    assert get_site("wiki").title_template == "%page% | %site%"
    assert get_site("wiki").robots_follow is True


def test_indexnow_and_redirects_round_trip(authed_client, isolated_content):
    from services.site_service import create_site, ensure_sites_initialized, get_site

    ensure_sites_initialized()
    create_site("wiki", "Wiki")

    resp = authed_client.patch(
        "/api/sites/wiki",
        json={"indexnow_enabled": True},
    )
    assert resp.status_code == 200, resp.text
    key = resp.json()["indexnow_key"]
    assert key and len(key) == 32
    assert get_site("wiki").indexnow_enabled is True
    assert get_site("wiki").indexnow_key == key

    resp = authed_client.patch(
        "/api/sites/wiki",
        json={
            "indexnow_key": "",
            "content_signal_ai_train": True,
            "seo_redirects": [{"from": "/old/", "to": "/new/"}],
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["indexnow_key"] != key
    assert len(resp.json()["indexnow_key"]) == 32
    assert resp.json()["content_signal_ai_train"] is True
    assert resp.json()["seo_redirects"] == [{"from": "/old/", "to": "/new/"}]

    bad = authed_client.patch(
        "/api/sites/wiki",
        json={"seo_redirects": [{"from": "/old/", "to": "https://evil.example/"}]},
    )
    assert bad.status_code == 400


def test_social_preview_sparse_overrides(authed_client, isolated_content):
    from services.site_service import create_site, ensure_sites_initialized, get_site
    from services.social_preview import resolve_social_preview

    ensure_sites_initialized()
    create_site("social", "Social", theme="starter")
    data = _listed_site(authed_client, "social")
    assert data["og_accent_color"] is None
    assert data["social_preview_defaults"]["og_accent_color"] == "#2563EB"
    assert data["social_preview_defaults"]["og_headline_style"] == "plain"
    assert "Roboto-Bold" in data["social_preview_defaults"]["og_fonts"]

    resolved = resolve_social_preview(get_site("social"))
    assert resolved["og_accent_color"] == "#2563EB"
    assert resolved["og_headline_style"] == "plain"

    resp = authed_client.patch(
        "/api/sites/social",
        json={
            "og_accent_color": "#112233",
            "og_headline_style": "plain",
            "og_accent_bar": False,
            "og_fallback_title": "CUSTOM",
            "twitter_card": "summary",
            "og_default_image": "images/og-default.jpg",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["og_accent_color"] == "#112233"
    assert body["og_headline_style"] == "plain"
    assert body["og_accent_bar"] is False
    assert body["og_fallback_title"] == "CUSTOM"
    assert body["twitter_card"] == "summary"
    assert body["og_default_image"] == "images/og-default.jpg"
    # Theme defaults still present for admin placeholders
    assert body["social_preview_defaults"]["og_accent_color"] == "#2563EB"

    site = get_site("social")
    assert site.og_accent_color == "#112233"
    assert site.og_headline_style == "plain"
    assert site.og_accent_bar is False
    # Sparse: YAML should not dump full theme block
    raw = site.to_dict()
    assert "og_vignette_color" not in raw
    assert raw["og_accent_color"] == "#112233"

    resolved = resolve_social_preview(site)
    assert resolved["og_accent_color"] == "#112233"
    assert resolved["og_headline_style"] == "plain"
    assert resolved["og_accent_bar"] is False
    assert resolved["og_vignette_color"] == "#64748B"  # still theme

    # Clear overrides → inherit theme again
    resp = authed_client.patch(
        "/api/sites/social",
        json={
            "og_accent_color": "",
            "og_headline_style": "",
            "og_accent_bar": None,
            "og_fallback_title": "",
            "twitter_card": "",
            "og_default_image": "",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["og_accent_color"] is None
    assert resp.json()["og_headline_style"] is None
    assert resp.json()["og_accent_bar"] is None
    assert resp.json()["og_fallback_title"] is None
    assert resp.json()["twitter_card"] is None
    assert resp.json()["og_default_image"] is None
    site = get_site("social")
    assert site.og_accent_color is None
    assert site.og_accent_bar is None
    resolved = resolve_social_preview(site)
    assert resolved["og_accent_color"] == "#2563EB"
    assert resolved["og_headline_style"] == "plain"
    assert resolved["og_accent_bar"] is True


def test_og_watermark_enabled_sparse_override(authed_client, isolated_content):
    from services.site_service import create_site, ensure_sites_initialized, get_site
    from services.social_preview import resolve_social_preview

    ensure_sites_initialized()
    create_site("wmbool", "WM Bool", theme="starter")
    data = _listed_site(authed_client, "wmbool")
    assert data["og_watermark_enabled"] is None
    assert data["social_preview_defaults"]["og_watermark_enabled"] is True
    catalog = data.get("og_font_catalog") or []
    assert any(e.get("source") == "registry" for e in catalog)

    resp = authed_client.patch(
        "/api/sites/wmbool",
        json={"og_watermark_enabled": False},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["og_watermark_enabled"] is False
    site = get_site("wmbool")
    assert site.og_watermark_enabled is False
    assert "og_watermark_enabled" in site.to_dict()
    resolved = resolve_social_preview(site)
    assert resolved["og_watermark_enabled"] is False

    resp = authed_client.patch(
        "/api/sites/wmbool",
        json={"og_watermark_enabled": None},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["og_watermark_enabled"] is None
    site = get_site("wmbool")
    assert site.og_watermark_enabled is None
    resolved = resolve_social_preview(site)
    assert resolved["og_watermark_enabled"] is True


def test_og_preview_returns_jpeg_without_persisting(
    authed_client, isolated_content
):
    from services.site_service import create_site, ensure_sites_initialized, get_site

    ensure_sites_initialized()
    create_site("ogprev", "OG Prev", theme="starter")
    assert get_site("ogprev").og_headline_style is None

    resp = authed_client.post(
        "/api/sites/ogprev/og-preview",
        json={
            "title": "Draft Headline",
            "og_headline_style": "plain",
            "og_grade_preset": "none",
            "og_accent_bar": False,
            "og_watermark_enabled": False,
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("image/jpeg")
    assert resp.content[:2] == b"\xff\xd8"
    from PIL import Image
    import io

    img = Image.open(io.BytesIO(resp.content))
    assert img.size == (1200, 630)

    site = get_site("ogprev")
    assert site.og_headline_style is None
    assert site.og_grade_preset is None
    assert site.og_accent_bar is None
    assert site.og_watermark_enabled is None


def _png_data_url(color, size=(8, 8)):
    import base64
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGBA", size, color).save(buf, "PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def test_og_preview_draft_data_urls_jpeg_without_persisting(
    authed_client, isolated_content, temp_data_root
):
    from services.site_service import create_site, ensure_sites_initialized, get_site

    ensure_sites_initialized()
    create_site("ogdraft", "OG Draft", theme="starter")
    registry = temp_data_root / "data" / "sites.yaml"
    before = registry.read_text()
    site_before = get_site("ogdraft").to_dict()

    hero = _png_data_url((12, 34, 56, 255), (32, 32))
    watermark = _png_data_url((255, 0, 0, 160), (1200, 630))
    resp = authed_client.post(
        "/api/sites/ogdraft/og-preview",
        json={
            "title": "Draft Assets",
            "og_headline_style": "plain",
            "og_grade_preset": "none",
            "og_accent_bar": False,
            "og_watermark_enabled": True,
            "hero_data_url": hero,
            "watermark_data_url": watermark,
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("image/jpeg")
    assert resp.content[:2] == b"\xff\xd8"
    from PIL import Image
    import io

    img = Image.open(io.BytesIO(resp.content))
    assert img.size == (1200, 630)

    site = get_site("ogdraft")
    assert site.to_dict() == site_before
    assert site.og_headline_style is None
    assert site.og_default_hero is None
    assert site.og_watermark is None
    assert registry.read_text() == before


def test_og_preview_invalid_and_oversize_data_url_400(
    authed_client, isolated_content
):
    import base64

    from services.og_image import PREVIEW_DATA_URL_MAX_DECODED
    from services.site_service import create_site, ensure_sites_initialized, get_site

    ensure_sites_initialized()
    create_site("ogbad", "OG Bad", theme="starter")

    garbage = authed_client.post(
        "/api/sites/ogbad/og-preview",
        json={
            "title": "Nope",
            "hero_data_url": "data:image/png;base64,not-valid!!!",
        },
    )
    assert garbage.status_code == 400, garbage.text

    huge = "data:image/png;base64," + base64.b64encode(
        b"\x00" * (PREVIEW_DATA_URL_MAX_DECODED + 1)
    ).decode("ascii")
    oversize = authed_client.post(
        "/api/sites/ogbad/og-preview",
        json={"title": "Nope", "hero_data_url": huge},
    )
    assert oversize.status_code == 400, oversize.text
    assert get_site("ogbad").og_default_hero is None


def test_og_preview_draft_watermark_respects_enabled_false(
    authed_client, isolated_content
):
    from services.site_service import create_site, ensure_sites_initialized, get_site

    ensure_sites_initialized()
    create_site("ogwmoff", "OG WM Off", theme="starter")

    hero = _png_data_url((10, 20, 30, 255), (32, 32))
    watermark = _png_data_url((255, 0, 0, 200), (1200, 630))
    common = {
        "title": "WM Gate",
        "og_headline_style": "plain",
        "og_grade_preset": "none",
        "og_accent_bar": False,
        "hero_data_url": hero,
    }
    enabled = authed_client.post(
        "/api/sites/ogwmoff/og-preview",
        json={
            **common,
            "og_watermark_enabled": True,
            "watermark_data_url": watermark,
        },
    )
    disabled = authed_client.post(
        "/api/sites/ogwmoff/og-preview",
        json={
            **common,
            "og_watermark_enabled": False,
            "watermark_data_url": watermark,
        },
    )
    disabled_plain = authed_client.post(
        "/api/sites/ogwmoff/og-preview",
        json={**common, "og_watermark_enabled": False},
    )
    assert enabled.status_code == 200, enabled.text
    assert disabled.status_code == 200, disabled.text
    assert disabled_plain.status_code == 200, disabled_plain.text
    assert enabled.content != disabled.content
    assert disabled.content == disabled_plain.content
    assert get_site("ogwmoff").og_watermark_enabled is None


def test_og_watermark_layout_sparse_override(
    authed_client, isolated_content, temp_data_root
):
    from services.site_service import create_site, ensure_sites_initialized, get_site

    ensure_sites_initialized()
    create_site("ogcorner", "OG Corner", theme="starter")
    created = _listed_site(authed_client, "ogcorner")
    assert created["og_watermark_source"] is None
    assert created["og_watermark_layout"] is None

    resp = authed_client.patch(
        "/api/sites/ogcorner",
        json={
            "og_watermark_source": "logo",
            "og_watermark_layout": "corner",
            "og_watermark_corner": "tl",
            "og_watermark_scale": "sm",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["og_watermark_source"] == "logo"
    assert data["og_watermark_layout"] == "corner"
    assert data["og_watermark_corner"] == "tl"
    assert data["og_watermark_scale"] == "sm"
    site = get_site("ogcorner")
    assert site.og_watermark_source == "logo"
    assert site.og_watermark_layout == "corner"

    registry = temp_data_root / "data" / "sites.yaml"
    before = registry.read_text()
    preview = authed_client.post(
        "/api/sites/ogcorner/og-preview",
        json={
            "title": "Corner Draft",
            "og_headline_style": "plain",
            "og_grade_preset": "none",
            "og_accent_bar": False,
            "og_watermark_enabled": True,
            "og_watermark_source": "custom",
            "og_watermark_layout": "corner",
            "og_watermark_corner": "br",
            "og_watermark_scale": "lg",
        },
    )
    assert preview.status_code == 200, preview.text
    assert preview.headers["content-type"].startswith("image/jpeg")
    assert preview.content[:2] == b"\xff\xd8"
    site = get_site("ogcorner")
    assert site.og_watermark_source == "logo"
    assert site.og_watermark_layout == "corner"
    assert site.og_watermark_corner == "tl"
    assert registry.read_text() == before

    cleared = authed_client.patch(
        "/api/sites/ogcorner",
        json={
            "og_watermark_source": "",
            "og_watermark_layout": "",
            "og_watermark_corner": "",
            "og_watermark_scale": "",
        },
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["og_watermark_source"] is None
    assert get_site("ogcorner").og_watermark_source is None
    assert get_site("ogcorner").og_watermark_layout is None


def test_og_preview_logo_source_raster_and_svg(
    authed_client, isolated_content, temp_data_root
):
    from pathlib import Path

    from PIL import Image

    import config
    from services.site_service import (
        create_site,
        ensure_sites_initialized,
        get_site,
        join_site_assets_path,
    )

    ensure_sites_initialized()
    create_site("oglogo", "OG Logo", theme="starter")
    logo_dir = Path(config.CONTENT_DIR_PATH) / join_site_assets_path(
        "oglogo", "images"
    )
    logo_dir.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (40, 40), (0, 255, 0, 255)).save(logo_dir / "logo.png")
    registry = temp_data_root / "data" / "sites.yaml"
    before = registry.read_text()

    common = {
        "title": "Logo WM",
        "og_headline_style": "plain",
        "og_grade_preset": "none",
        "og_accent_bar": False,
        "og_watermark_source": "logo",
        "og_watermark_layout": "full_canvas",
    }
    with_logo = authed_client.post(
        "/api/sites/oglogo/og-preview",
        json={**common, "og_watermark_enabled": True},
    )
    without = authed_client.post(
        "/api/sites/oglogo/og-preview",
        json={**common, "og_watermark_enabled": False},
    )
    assert with_logo.status_code == 200, with_logo.text
    assert without.status_code == 200, without.text
    assert with_logo.content[:2] == b"\xff\xd8"
    assert with_logo.content != without.content
    assert registry.read_text() == before
    assert get_site("oglogo").og_watermark_source is None

    (logo_dir / "logo.png").unlink()
    (logo_dir / "logo.svg").write_text(
        "<svg xmlns='http://www.w3.org/2000/svg'></svg>", encoding="utf-8"
    )
    svg_only = authed_client.post(
        "/api/sites/oglogo/og-preview",
        json={**common, "og_watermark_enabled": True},
    )
    assert svg_only.status_code == 200, svg_only.text
    assert svg_only.content == without.content


def test_og_preview_forbidden_for_non_admin(authed_client, isolated_content, login_author):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    login_author(capabilities=["write:posts"], username="og-denied")
    resp = authed_client.post(
        "/api/sites/default/og-preview",
        json={"title": "Nope", "og_grade_preset": "none"},
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["detail"] == "missing_capability: write:seo"


def test_og_preview_unknown_site_404(authed_client, isolated_content):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    resp = authed_client.post(
        "/api/sites/nosuch/og-preview",
        json={"title": "Missing"},
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.parametrize(
    ("language", "languages", "expected"),
    [
        ("en", [], False),
        ("en", ["en"], False),
        ("en", ["en", "fr"], True),
        ("fr", ["en", "fr"], True),
    ],
)
def test_i18n_activation_permutations(language, languages, expected):
    from services.i18n_service import is_i18n_active

    assert is_i18n_active(language, languages) is expected


def test_i18n_normalizes_codes_and_labels():
    from services.i18n_service import normalize_language_config

    config = normalize_language_config(
        language="EN_us",
        languages=["EN-us", "FR", "i-klingon"],
        language_labels={"FR": " Français ", "iw-IL": "עברית"},
        translation_automation_paused=True,
    )

    assert config.language == "en-us"
    assert config.languages == ["en-us", "fr", "tlh"]
    assert config.language_labels == {"fr": "Français", "he-il": "עברית"}
    assert config.translation_automation_paused is True
    assert config.active is True


@pytest.mark.parametrize("invalid", ["zz", "en--US", "", 42])
def test_i18n_rejects_invalid_or_unknown_codes(invalid):
    from services.i18n_service import normalize_language_config

    with pytest.raises(ValueError, match="BCP-47"):
        normalize_language_config(language=invalid)


def test_i18n_rejects_duplicates_and_missing_default():
    from services.i18n_service import normalize_language_config

    with pytest.raises(ValueError, match="Duplicate language tag"):
        normalize_language_config(language="en", languages=["EN", "en"])

    with pytest.raises(ValueError, match="include the default language 'en'"):
        normalize_language_config(language="en", languages=["fr"])

    with pytest.raises(ValueError, match="Duplicate language label key"):
        normalize_language_config(
            language_labels={"iw-IL": "Hebrew", "he-il": "עברית"}
        )


def test_i18n_legacy_registry_defaults_without_rewrite(
    authed_client, isolated_content, temp_data_root
):
    registry = temp_data_root / "data" / "sites.yaml"
    legacy = {
        "sites": [
            {
                "id": "default",
                "name": "Legacy",
                "content_relpath": "sites/default",
            }
        ]
    }
    registry.write_text(yaml.safe_dump(legacy, sort_keys=False))

    response = authed_client.get("/api/sites")
    assert response.status_code == 200, response.text
    site = response.json()["sites"][0]
    assert site["language"] == "en"
    assert site["languages"] == []
    assert site["language_labels"] == {}
    assert site["translation_automation_paused"] is False
    assert site["i18n_active"] is False
    on_disk = yaml.safe_load(registry.read_text())
    row = on_disk["sites"][0]
    assert row["id"] == "default"
    assert row["name"] == "Legacy"
    assert "language" not in row
    assert "languages" not in row
    assert "language_labels" not in row
    assert row.get("feedback_submission_key")
    assert row.get("feedback_fetch_token")


@pytest.mark.pro
def test_i18n_site_api_round_trip_and_isolation(authed_client, isolated_content):
    pytest.importorskip("pencms_pro", reason="sites CRUD is Pro overlay")
    from services.site_service import ensure_sites_initialized, get_site

    ensure_sites_initialized()
    response = authed_client.post(
        "/api/sites",
        json={
            "id": "global",
            "name": "Global",
            "language": "EN_us",
            "languages": ["EN-us", "FR"],
            "language_labels": {"FR": "Français"},
            "translation_automation_paused": True,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["language"] == "en-us"
    assert body["languages"] == ["en-us", "fr"]
    assert body["language_labels"] == {"fr": "Français"}
    assert body["translation_automation_paused"] is True
    assert body["i18n_active"] is True

    default = get_site("default")
    assert default.language == "en"
    assert default.languages == []
    assert default.language_labels == {}
    assert default.translation_automation_paused is False

    response = authed_client.patch(
        "/api/sites/global",
        json={"language": "fr", "languages": ["fr"]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["language"] == "fr"
    assert response.json()["languages"] == ["fr"]
    assert response.json()["i18n_active"] is False


@pytest.mark.parametrize(
    "payload",
    [
        {"language": "zz"},
        {"language": "en", "languages": ["en", "EN"]},
        {"language": "en", "languages": ["fr"]},
        {"language": None},
        {"translation_automation_paused": None},
    ],
)
def test_i18n_site_api_rejects_invalid_config(
    authed_client, isolated_content, payload
):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    response = authed_client.patch("/api/sites/default", json=payload)
    assert response.status_code in {400, 422}, response.text


def test_i18n_inactive_gate_leaves_content_api_unchanged(
    authed_client, isolated_content
):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    before = authed_client.get("/api/v1/content/collections")
    assert before.status_code == 200, before.text

    update = authed_client.patch(
        "/api/sites/default",
        json={
            "language": "en",
            "languages": ["en"],
            "language_labels": {"en": "English"},
            "translation_automation_paused": True,
        },
    )
    assert update.status_code == 200, update.text
    assert update.json()["i18n_active"] is False

    after = authed_client.get("/api/v1/content/collections")
    assert after.status_code == 200, after.text
    assert after.json() == before.json()


def test_i18n_openapi_contracts(authed_client):
    runtime = authed_client.get("/api/openapi.json")
    assert runtime.status_code == 200, runtime.text
    runtime_spec = runtime.json()
    update_properties = runtime_spec["components"]["schemas"]["UpdateSiteBody"][
        "properties"
    ]
    for field in (
        "language",
        "languages",
        "language_labels",
        "translation_automation_paused",
    ):
        assert field in update_properties

    contract_path = Path(__file__).resolve().parents[2] / "core" / "openapi.yaml"
    contract = yaml.safe_load(contract_path.read_text())
    assert contract["paths"]["/sites"]["servers"] == [{"url": "/api"}]
    assert contract["paths"]["/sites/{site_id}"]["servers"] == [{"url": "/api"}]
    i18n = contract["components"]["schemas"]["SiteI18nConfig"]["properties"]
    assert i18n["language"]["default"] == "en"
    assert i18n["languages"]["default"] == []
    assert i18n["translation_automation_paused"]["default"] is False


@pytest.mark.pro
def test_i18n_create_site_body_openapi(authed_client):
    pytest.importorskip("pencms_pro", reason="sites CRUD is Pro overlay")
    runtime = authed_client.get("/api/openapi.json")
    assert runtime.status_code == 200, runtime.text
    create_properties = runtime.json()["components"]["schemas"]["CreateSiteBody"][
        "properties"
    ]
    for field in (
        "language",
        "languages",
        "language_labels",
        "translation_automation_paused",
    ):
        assert field in create_properties


@pytest.mark.pro
def test_delete_frees_domain(authed_client, isolated_content):
    pytest.importorskip("pencms_pro", reason="sites CRUD is Pro overlay")
    from services.site_service import (
        create_site,
        ensure_sites_initialized,
        resolve_site_id_by_host,
    )

    ensure_sites_initialized()
    create_site("wiki", "Wiki", domain="wiki.example")
    assert resolve_site_id_by_host("wiki.example") == "wiki"

    resp = authed_client.request(
        "DELETE",
        "/api/sites/wiki",
        json={"confirm": True, "revoke_keys": True},
    )
    assert resp.status_code == 200, resp.text
    assert resolve_site_id_by_host("wiki.example") == "default"

    resp = authed_client.post(
        "/api/sites",
        json={"id": "docs", "name": "Docs", "domain": "wiki.example"},
    )
    assert resp.status_code == 200, resp.text
    assert resolve_site_id_by_host("wiki.example") == "docs"
