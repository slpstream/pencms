"""Per-site theme style overrides API."""

from __future__ import annotations

import json

import pytest


@pytest.fixture
def isolated_content(temp_data_root, monkeypatch):
    """Point content storage at the temp root and reset site registry."""
    import shutil
    from pathlib import Path

    import config
    from services.storage_provider import LocalStorageProvider
    import services.file_service as file_service
    import services.site_service as site_service

    content = temp_data_root / "content"
    content.mkdir(exist_ok=True)
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


@pytest.fixture
def styled_themes(tmp_path, monkeypatch):
    """Install themes root with a theme that exposes a style schema."""
    root = tmp_path / "themes"
    base = root / "styled"
    (base / "templates").mkdir(parents=True)
    (base / "partials").mkdir(parents=True)
    (base / "assets" / "css").mkdir(parents=True)
    (base / "theme.json").write_text(
        json.dumps(
            {
                "name": "Styled",
                "version": "1.0.0",
                "type": "native",
                "color_mode": "both",
                "style": {
                    "dark_scope": {"selector": ".dark"},
                    "groups": [
                        {
                            "id": "colors",
                            "label": "Color Palette",
                            "fields": [
                                {
                                    "id": "bg",
                                    "label": "Background",
                                    "type": "color",
                                    "var": "--styled-bg",
                                    "default": "#ffffff",
                                    "dark_default": "#111111",
                                },
                                {
                                    "id": "accent",
                                    "label": "Accent",
                                    "type": "color",
                                    "var": "--styled-accent",
                                    "default": "#cc0000",
                                },
                            ],
                        },
                        {
                            "id": "typography",
                            "label": "Typography",
                            "fields": [
                                {
                                    "id": "font-body",
                                    "label": "Body Font",
                                    "type": "select",
                                    "var": "--styled-font-body",
                                    "default": "'Roboto', sans-serif",
                                    "options": [
                                        {"value": "", "label": "Theme default"},
                                        {"value": "'Roboto', sans-serif", "label": "Roboto"},
                                        {"value": "'Inter', sans-serif", "label": "Inter"},
                                    ],
                                }
                            ],
                        },
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    (base / "templates" / "index.html.twig").write_text(
        "{# styled index #}\n", encoding="utf-8"
    )
    (base / "partials" / "nav.twig").write_text("{# nav #}\n", encoding="utf-8")
    (base / "assets" / "css" / "styles.css").write_text("body{}\n", encoding="utf-8")

    plain = root / "plain"
    (plain / "templates").mkdir(parents=True)
    (plain / "partials").mkdir(parents=True)
    (plain / "assets" / "css").mkdir(parents=True)
    (plain / "theme.json").write_text(
        json.dumps({"name": "Plain", "version": "1.0.0", "type": "native"}),
        encoding="utf-8",
    )
    (plain / "templates" / "index.html.twig").write_text(
        "{# plain index #}\n", encoding="utf-8"
    )
    (plain / "partials" / "nav.twig").write_text("{# nav #}\n", encoding="utf-8")
    (plain / "assets" / "css" / "styles.css").write_text("body{}\n", encoding="utf-8")

    import services.social_preview as social_preview

    monkeypatch.setattr(social_preview, "themes_root", lambda: root)
    monkeypatch.setattr(social_preview, "install_active_theme", lambda: "styled")
    return root


@pytest.fixture
def site_ready(isolated_content, styled_themes):
    from services.site_service import create_site, ensure_sites_initialized

    ensure_sites_initialized()
    create_site("wiki", "Wiki", theme="styled")
    return isolated_content


def test_style_get_unauthenticated(site_ready, client):
    resp = client.get("/api/sites/wiki/theme/style")
    assert resp.status_code in (401, 403)


def test_style_put_unauthenticated(site_ready, client):
    resp = client.put(
        "/api/sites/wiki/theme/style", json={"values": {}, "dark": {}}
    )
    assert resp.status_code in (401, 403)


def test_style_non_admin_forbidden(site_ready, authed_client, login_author):
    login_author(capabilities=["write:posts"], username="style-denied")
    resp = authed_client.get("/api/sites/wiki/theme/style")
    assert resp.status_code == 403, resp.text
    assert resp.json()["detail"] == "missing_capability: write:theme"
    resp = authed_client.put(
        "/api/sites/wiki/theme/style", json={"values": {}, "dark": {}}
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["detail"] == "missing_capability: write:theme"


def test_style_get_returns_schema(site_ready, authed_client):
    resp = authed_client.get("/api/sites/wiki/theme/style")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["theme"] == "styled"
    assert data["schema"] is not None
    assert data["saved_for_theme"] is None
    assert data["values"] == {}
    assert data["dark_values"] == {}


def test_style_put_roundtrip(site_ready, authed_client):
    put = authed_client.put(
        "/api/sites/wiki/theme/style",
        json={
            "values": {"bg": "#f5f5f5", "font-body": "'Inter', sans-serif"},
            "dark": {"bg": "#0a0a0a"},
        },
    )
    assert put.status_code == 200, put.text
    data = put.json()
    assert data["theme"] == "styled"
    assert data["saved_for_theme"] == "styled"
    assert data["values"]["bg"] == "#f5f5f5"
    assert data["values"]["font-body"] == "'Inter', sans-serif"
    assert data["dark_values"]["bg"] == "#0a0a0a"

    get = authed_client.get("/api/sites/wiki/theme/style")
    assert get.status_code == 200, get.text
    data = get.json()
    assert data["saved_for_theme"] == "styled"
    assert data["values"]["bg"] == "#f5f5f5"
    assert data["values"]["font-body"] == "'Inter', sans-serif"
    assert data["dark_values"]["bg"] == "#0a0a0a"


def test_style_put_pins_dark_default_when_light_only(site_ready, authed_client):
    """Light-only saves must pin dark_default so :root !important does not leak."""
    put = authed_client.put(
        "/api/sites/wiki/theme/style",
        json={"values": {"bg": "#abcdef"}, "dark": {}},
    )
    assert put.status_code == 200, put.text
    data = put.json()
    assert data["values"]["bg"] == "#abcdef"
    assert data["dark_values"]["bg"] == "#111111"

    get = authed_client.get("/api/sites/wiki/theme/style")
    assert get.status_code == 200, get.text
    assert get.json()["dark_values"]["bg"] == "#111111"


def test_style_put_rejects_unknown_id(site_ready, authed_client):
    resp = authed_client.put(
        "/api/sites/wiki/theme/style",
        json={"values": {"unknown-key": "#ffffff"}},
    )
    assert resp.status_code == 400, resp.text
    assert "Unknown" in resp.json()["detail"]


def test_style_put_rejects_bad_color(site_ready, authed_client):
    resp = authed_client.put(
        "/api/sites/wiki/theme/style",
        json={"values": {"bg": "not-a-color"}},
    )
    assert resp.status_code == 400, resp.text
    assert "Invalid color" in resp.json()["detail"]


def test_style_put_rejects_bad_select(site_ready, authed_client):
    resp = authed_client.put(
        "/api/sites/wiki/theme/style",
        json={"values": {"font-body": "Comic Sans"}},
    )
    assert resp.status_code == 400, resp.text
    assert "Invalid option" in resp.json()["detail"]


def test_style_put_rejects_dark_for_non_dark_field(site_ready, authed_client):
    resp = authed_client.put(
        "/api/sites/wiki/theme/style",
        json={"dark": {"accent": "#000000"}},
    )
    assert resp.status_code == 400, resp.text
    assert "Unknown" in resp.json()["detail"]


def test_style_overrides_stale_theme_ignored(site_ready, authed_client):
    from services.site_service import update_site

    authed_client.put(
        "/api/sites/wiki/theme/style",
        json={"values": {"bg": "#f5f5f5"}},
    )
    # Switch site to a different theme; stored overrides for "styled" are
    # inert and should not be returned.
    update_site("wiki", theme="starter")
    resp = authed_client.get("/api/sites/wiki/theme/style")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["saved_for_theme"] is None
    assert "bg" not in data.get("values", {})


def test_style_custom_fork_schema(site_ready, authed_client):
    fork = authed_client.post(
        "/api/sites/wiki/theme/fork", json={"parent": "styled"}
    )
    assert fork.status_code == 200, fork.text

    resp = authed_client.get("/api/sites/wiki/theme/style")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["theme"] == "custom"
    assert data["schema"] is not None
    assert data["schema"]["groups"][0]["fields"][0]["id"] == "bg"


def test_fork_migrates_style_overrides_to_custom(site_ready, authed_client):
    from services.site_service import get_site

    put = authed_client.put(
        "/api/sites/wiki/theme/style",
        json={
            "values": {"bg": "#f5f5f5", "font-body": "'Inter', sans-serif"},
            "dark": {"bg": "#0a0a0a"},
        },
    )
    assert put.status_code == 200, put.text

    fork = authed_client.post(
        "/api/sites/wiki/theme/fork", json={"parent": "styled"}
    )
    assert fork.status_code == 200, fork.text

    stored = get_site("wiki").style_overrides
    assert stored["theme"] == "custom"
    assert stored["values"]["bg"] == "#f5f5f5"
    assert stored["values"]["font-body"] == "'Inter', sans-serif"
    assert stored["dark"]["bg"] == "#0a0a0a"

    resp = authed_client.get("/api/sites/wiki/theme/style")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["saved_for_theme"] == "custom"
    assert data["values"]["bg"] == "#f5f5f5"
    assert data["values"]["font-body"] == "'Inter', sans-serif"
    assert data["dark_values"]["bg"] == "#0a0a0a"


def test_fork_does_not_migrate_mismatched_overrides(site_ready, authed_client):
    from services.site_service import get_site

    put = authed_client.put(
        "/api/sites/wiki/theme/style",
        json={"values": {"bg": "#f5f5f5"}},
    )
    assert put.status_code == 200, put.text

    fork = authed_client.post(
        "/api/sites/wiki/theme/fork", json={"parent": "plain"}
    )
    assert fork.status_code == 200, fork.text

    stored = get_site("wiki").style_overrides
    assert stored["theme"] == "styled"
    assert stored["values"]["bg"] == "#f5f5f5"

    resp = authed_client.get("/api/sites/wiki/theme/style")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["theme"] == "custom"
    assert data["saved_for_theme"] is None
    assert "bg" not in data.get("values", {})


def test_rekey_style_overrides_for_fork_unit():
    from services.theme_style_service import rekey_style_overrides_for_fork

    stored = {
        "theme": "styled",
        "values": {"bg": "#f5f5f5", "empty": ""},
        "dark": {"bg": "#0a0a0a"},
    }
    migrated = rekey_style_overrides_for_fork(stored, "styled")
    assert migrated == {
        "theme": "custom",
        "values": {"bg": "#f5f5f5"},
        "dark": {"bg": "#0a0a0a"},
    }
    assert rekey_style_overrides_for_fork(stored, "plain") is None
    assert rekey_style_overrides_for_fork({"theme": "styled", "values": {}}, "styled") is None


@pytest.fixture
def tiny_font_registry(tmp_path, monkeypatch):
    """Point the style service at a tiny fonts.json for merge tests."""
    import services.theme_style_service as style_svc

    fonts_dir = tmp_path / "public" / "assets" / "fonts"
    fonts_dir.mkdir(parents=True)
    registry = {
        "sora": {
            "label": "Sora",
            "family": "Sora",
            "stack": "'Sora', sans-serif",
        },
        "outfit": {
            "label": "Outfit",
            "family": "Outfit",
            "stack": "'Outfit', sans-serif",
        },
    }
    path = fonts_dir / "fonts.json"
    path.write_text(json.dumps(registry), encoding="utf-8")
    style_svc.reset_font_registry_cache()
    monkeypatch.setattr(style_svc, "font_registry_path", lambda: path)
    yield path
    style_svc.reset_font_registry_cache()


def test_style_schema_merges_registry_fonts(site_ready, tiny_font_registry, authed_client):
    resp = authed_client.get("/api/sites/wiki/theme/style")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    font_field = data["schema"]["groups"][1]["fields"][0]
    assert font_field["id"] == "font-body"
    values = [o["value"] for o in font_field["options"]]
    # Theme-authored options first
    assert values[0] == ""
    assert "'Roboto', sans-serif" in values
    assert "'Inter', sans-serif" in values
    # Registry append
    assert "'Sora', sans-serif" in values
    assert "'Outfit', sans-serif" in values
    # Color selects are not font fields — untouched (no options)
    color_field = data["schema"]["groups"][0]["fields"][0]
    assert color_field["type"] == "color"
    assert "options" not in color_field


def test_style_put_accepts_registry_only_stack(
    site_ready, tiny_font_registry, authed_client
):
    resp = authed_client.put(
        "/api/sites/wiki/theme/style",
        json={"values": {"font-body": "'Sora', sans-serif"}},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["values"]["font-body"] == "'Sora', sans-serif"
