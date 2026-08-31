"""MCP site presentation / SEO bootstrap tools."""

from __future__ import annotations

import secrets
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent
REAL_THEMES = BACKEND_ROOT.parent / "frontend-php" / "src" / "blog" / "themes"


@pytest.fixture(autouse=True)
def patch_themes_root(monkeypatch):
    """Point theme discovery at the real install themes (temp BASE_DIR has none)."""
    import services.social_preview as social_preview

    monkeypatch.setattr(social_preview, "themes_root", lambda: REAL_THEMES)
    monkeypatch.setattr(social_preview, "install_active_theme", lambda: "default")


@pytest.fixture
def agent_token_factory(authed_client):
    def _create(scopes, site_id: str = "default"):
        resp = authed_client.post(
            "/api/auth/keys",
            json={
                "name": f"pres-{secrets.token_hex(4)}",
                "scopes": scopes,
                "site_id": site_id,
            },
        )
        assert resp.status_code == 200, resp.text
        raw_key = resp.json()["key"]
        resp = authed_client.post("/api/auth/token", json={"agent_key": raw_key})
        assert resp.status_code == 200, resp.text
        return resp.json()["access_token"]

    return _create


def test_unauthenticated_presentation_endpoints_rejected(client):
    assert client.get("/api/v1/mcp/themes").status_code == 401
    assert client.get("/api/v1/mcp/site-presentation").status_code == 401
    assert (
        client.patch(
            "/api/v1/mcp/site-presentation", json={"sitename": "X"}
        ).status_code
        == 401
    )


def test_read_scoped_key_allowed_on_read_presentation(
    authed_client, agent_token_factory
):
    token = agent_token_factory(["read"])
    headers = {"Authorization": f"Bearer {token}"}

    resp = authed_client.get("/api/v1/mcp/themes", headers=headers)
    assert resp.status_code == 200, resp.text
    themes = resp.json()
    assert isinstance(themes, list)
    ids = {t["id"] for t in themes}
    assert "default" in ids or "starter" in ids
    assert all("id" in t and "label" in t for t in themes)

    resp = authed_client.get("/api/v1/mcp/site-presentation", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["site_id"] == "default"
    assert "effective_theme" in body
    assert "social_effective" in body
    assert "social_preview_defaults" in body
    assert "social_overrides" in body
    assert body["branding"]["logo"] is None
    assert body["branding"]["favicon"] is None


def test_read_scoped_key_rejected_on_write_presentation(
    authed_client, agent_token_factory
):
    token = agent_token_factory(["read"])
    headers = {"Authorization": f"Bearer {token}"}

    resp = authed_client.patch(
        "/api/v1/mcp/site-presentation",
        json={"sitename": "No Write"},
        headers=headers,
    )
    assert resp.status_code == 403
    assert "lacks required scope: write:seo" in resp.json()["detail"]


def test_get_presentation_empty_site_safe(authed_client, agent_token_factory):
    """Presentation read works with empty menus/authors/content siblings."""
    import config

    site_root = config.CONTENT_DIR_PATH / "sites" / "default"
    for name in ("menus.yaml", "authors.yaml"):
        path = site_root / name
        if path.exists():
            path.unlink()

    token = agent_token_factory(["read"])
    headers = {"Authorization": f"Bearer {token}"}
    resp = authed_client.get("/api/v1/mcp/site-presentation", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["site_id"] == "default"
    # Theme Social defaults present even with zero Social overrides
    assert body["social_overrides"] == {}
    assert body["social_effective"]["twitter_card"]
    assert body["social_preview_defaults"]["og_accent_color"]


def test_update_presentation_sparse_and_clear(authed_client, agent_token_factory):
    from services.site_service import get_site

    write_token = agent_token_factory(["write", "read"])
    headers = {"Authorization": f"Bearer {write_token}"}

    resp = authed_client.patch(
        "/api/v1/mcp/site-presentation",
        json={
            "theme": "starter",
            "sitename": "Acme",
            "tagline": "Notes",
            "title_template": "%page% · %site%",
            "meta_description": "About Acme",
            "robots_index": True,
            "sitemap_enabled": True,
            "og_accent_color": "#112233",
            "og_headline_style": "plain",
            "og_accent_bar": False,
            "twitter_card": "summary",
            "comments_enabled": True,
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["theme"] == "starter"
    assert body["effective_theme"] == "starter"
    assert body["sitename"] == "Acme"
    assert body["comments_enabled"] is True
    assert body["tagline"] == "Notes"
    assert body["title_template"] == "%page% · %site%"
    assert body["meta_description"] == "About Acme"
    assert body["social_overrides"]["og_accent_color"] == "#112233"
    assert body["social_overrides"]["og_headline_style"] == "plain"
    assert body["social_overrides"]["og_accent_bar"] is False
    assert body["social_effective"]["og_accent_color"] == "#112233"
    # Theme defaults still exposed separately
    assert "og_accent_color" in body["social_preview_defaults"]

    site = get_site("default")
    raw = site.to_dict()
    assert raw.get("og_accent_color") == "#112233"
    assert "og_vignette_color" not in raw  # sparse — no full theme dump

    # Clear Social string + accent bar → inherit theme again
    resp = authed_client.patch(
        "/api/v1/mcp/site-presentation",
        json={
            "og_accent_color": "",
            "og_headline_style": "",
            "og_accent_bar": None,
            "twitter_card": "",
            "sitename": "",
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    cleared = resp.json()
    assert cleared["sitename"] is None
    assert "og_accent_color" not in cleared["social_overrides"]
    assert "og_accent_bar" not in cleared["social_overrides"]
    assert cleared["theme"] == "starter"  # unchanged (absent key)


def test_update_presentation_indexnow(authed_client, agent_token_factory):
    token = agent_token_factory(["write", "read"])
    headers = {"Authorization": f"Bearer {token}"}
    resp = authed_client.patch(
        "/api/v1/mcp/site-presentation",
        json={
            "indexnow_enabled": True,
            "content_signal_ai_train": False,
            "seo_redirects": [{"from": "/a/", "to": "/b/"}],
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["indexnow_enabled"] is True
    assert body["indexnow_key"]
    assert len(body["indexnow_key"]) == 32
    assert body["seo_redirects"] == [{"from": "/a/", "to": "/b/"}]


def test_update_empty_body_rejected(authed_client, agent_token_factory):
    token = agent_token_factory(["write", "read"])
    headers = {"Authorization": f"Bearer {token}"}
    resp = authed_client.patch(
        "/api/v1/mcp/site-presentation",
        json={},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "at least one field" in resp.json()["detail"]


def test_presentation_site_binding(authed_client, agent_token_factory):
    """Agent JWT site_id is authoritative; writes only touch the bound site."""
    from services.site_service import create_site, ensure_sites_initialized, get_site

    ensure_sites_initialized()
    create_site("preswiki", "Pres Wiki", theme="starter")

    wiki_token = agent_token_factory(["write", "read"], site_id="preswiki")
    wiki_headers = {"Authorization": f"Bearer {wiki_token}"}

    resp = authed_client.patch(
        "/api/v1/mcp/site-presentation",
        json={"sitename": "Wiki Only"},
        headers=wiki_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["site_id"] == "preswiki"
    assert resp.json()["sitename"] == "Wiki Only"

    assert get_site("preswiki").sitename == "Wiki Only"
    # Default site untouched
    default = get_site("default")
    assert default is not None
    assert default.sitename != "Wiki Only"

    # Read also bound
    resp = authed_client.get(
        "/api/v1/mcp/site-presentation", headers=wiki_headers
    )
    assert resp.status_code == 200
    assert resp.json()["site_id"] == "preswiki"
    assert resp.json()["sitename"] == "Wiki Only"


def test_branding_presence_hint(authed_client, agent_token_factory, temp_data_root):
    logo = (
        temp_data_root
        / "content"
        / "sites"
        / "default"
        / "assets"
        / "images"
        / "logo.png"
    )
    logo.parent.mkdir(parents=True, exist_ok=True)
    logo.write_bytes(b"\x89PNG\r\n\x1a\n")

    token = agent_token_factory(["read"])
    headers = {"Authorization": f"Bearer {token}"}
    resp = authed_client.get("/api/v1/mcp/site-presentation", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["branding"]["logo"] == "images/logo.png"


def test_mcp_presentation_tools_registered_in_openapi(client):
    resp = client.get("/api/openapi.json")
    assert resp.status_code == 200
    paths = resp.json().get("paths", {})

    assert "/api/v1/mcp/themes" in paths
    assert "/api/v1/mcp/site-presentation" in paths

    themes_get = paths["/api/v1/mcp/themes"]["get"]
    assert "mcp" in themes_get["tags"]
    assert themes_get.get("operationId") == "list_themes"

    pres = paths["/api/v1/mcp/site-presentation"]
    assert pres["get"].get("operationId") == "get_site_presentation"
    assert "mcp" in pres["get"]["tags"]
    assert pres["patch"].get("operationId") == "update_site_presentation"
    assert "mcp" in pres["patch"]["tags"]
