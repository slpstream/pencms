"""Per-site menus, assets, and taxonomy isolation."""

from __future__ import annotations

import base64
import json
import shutil

import pytest
import yaml


@pytest.fixture
def two_sites(authed_client, temp_data_root, monkeypatch):
    """Ensure default + other sites exist."""
    from services.site_service import create_site, ensure_sites_initialized
    import config

    ensure_sites_initialized()
    try:
        create_site("other", "Other Site")
    except ValueError:
        pass
    config.invalidate_taxonomy_cache()
    config.invalidate_collections_cache()
    return temp_data_root / "content"


def _mint_token(authed_client, name: str, site_id: str) -> str:
    resp = authed_client.post(
        "/api/auth/keys",
        json={"name": name, "scopes": ["read", "write"], "site_id": site_id},
    )
    assert resp.status_code == 200, resp.text
    raw = resp.json()["key"]
    resp = authed_client.post("/api/auth/token", json={"agent_key": raw})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def test_menus_rest_site_isolation(authed_client, two_sites):
    headers_other = {"X-Pen-Site-Id": "other"}
    headers_default = {"X-Pen-Site-Id": "default"}

    body = {
        "menu": "primary",
        "label": "Wiki Home",
        "labels": {"fr": "Accueil Wiki"},
        "target": {"type": "system", "content_slug": "home", "url": "/"},
        "parent_id": None,
    }
    resp = authed_client.post(
        "/api/menus/primary/items", json=body, headers=headers_other
    )
    assert resp.status_code == 201, resp.text

    other_menus = two_sites / "sites" / "other" / "menus.yaml"
    assert other_menus.is_file()
    data = yaml.safe_load(other_menus.read_text())
    assert any(i.get("label") == "Wiki Home" for i in data.get("primary", []))
    assert any(
        i.get("labels") == {"fr": "Accueil Wiki"}
        for i in data.get("primary", [])
    )

    resp = authed_client.get("/api/menus", headers=headers_default)
    assert resp.status_code == 200
    default_primary = resp.json().get("primary", [])
    assert not any(i.get("label") == "Wiki Home" for i in default_primary)

    resp = authed_client.get("/api/menus", headers=headers_other)
    other_primary = resp.json().get("primary", [])
    assert any(i.get("label") == "Wiki Home" for i in other_primary)
    assert any(i.get("labels") == {"fr": "Accueil Wiki"} for i in other_primary)


def test_menus_unknown_site_400(authed_client, two_sites):
    resp = authed_client.get("/api/menus", headers={"X-Pen-Site-Id": "nope"})
    assert resp.status_code == 400


def test_menus_mcp_agent_cannot_clear_other(authed_client, two_sites):
    authed_client.post(
        "/api/menus/primary/items",
        json={
            "menu": "primary",
            "label": "Keep Me",
            "target": {"type": "system", "content_slug": "home", "url": "/"},
            "parent_id": None,
        },
        headers={"X-Pen-Site-Id": "other"},
    )

    token = _mint_token(authed_client, "default-menu-agent", "default")

    # Agent on default tries to clear other via header — must not affect other
    resp = authed_client.delete(
        "/api/v1/mcp/menus/primary",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Pen-Site-Id": "other",
        },
    )
    assert resp.status_code == 204, resp.text

    other_data = yaml.safe_load(
        (two_sites / "sites" / "other" / "menus.yaml").read_text()
    )
    assert any(i.get("label") == "Keep Me" for i in other_data.get("primary", []))


def test_authors_mcp_agent_cannot_mutate_other(authed_client, two_sites):
    resp = authed_client.post(
        "/api/authors/",
        json={"name": "Other Author", "bio": "Keep me"},
        headers={"X-Pen-Site-Id": "other"},
    )
    assert resp.status_code == 201, resp.text
    other_slug = resp.json()["slug"]

    token = _mint_token(authed_client, "default-author-agent", "default")

    # Agent on default tries to delete other via header — must not affect other
    resp = authed_client.delete(
        f"/api/v1/mcp/authors/{other_slug}",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Pen-Site-Id": "other",
        },
    )
    # Slug absent on default → 404; either way other site must keep the author
    assert resp.status_code in (204, 404), resp.text

    other_data = yaml.safe_load(
        (two_sites / "sites" / "other" / "authors.yaml").read_text()
    )
    assert any(a.get("slug") == other_slug for a in other_data.get("authors", []))

    # Create on MCP must land in default, not other
    resp = authed_client.post(
        "/api/v1/mcp/authors",
        json={"name": "Default Only"},
        headers={
            "Authorization": f"Bearer {token}",
            "X-Pen-Site-Id": "other",
        },
    )
    assert resp.status_code == 201, resp.text

    default_data = yaml.safe_load(
        (two_sites / "sites" / "default" / "authors.yaml").read_text()
    )
    assert any(
        a.get("name") == "Default Only" for a in default_data.get("authors", [])
    )

    other_data2 = yaml.safe_load(
        (two_sites / "sites" / "other" / "authors.yaml").read_text()
    )
    assert not any(
        a.get("name") == "Default Only" for a in other_data2.get("authors", [])
    )


def test_assets_upload_site_isolation(authed_client, two_sites):
    png_1x1 = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    files = {"file": ("dot.png", png_1x1, "image/png")}
    resp = authed_client.post(
        "/api/assets/content/test-page",
        files=files,
        headers={"X-Pen-Site-Id": "other"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["site_id"] == "other"
    assert "sites/other/assets" in data["url"]

    dest = two_sites / "sites" / "other" / "assets" / "images" / "content" / "test-page"
    assert dest.is_dir()
    assert any(dest.iterdir())

    resp = authed_client.get("/api/assets/", headers={"X-Pen-Site-Id": "default"})
    assert resp.status_code == 200
    assert not any(a.get("entity_id") == "test-page" for a in resp.json())

    resp = authed_client.get("/api/assets/", headers={"X-Pen-Site-Id": "other"})
    assert any(a.get("entity_id") == "test-page" for a in resp.json())


def test_assets_mcp_jwt_scopes_media(authed_client, two_sites):
    token = _mint_token(authed_client, "wiki-media", "other")
    payload = {
        "filename": "images/content/mcp-page/hello.txt",
        "content_base64": base64.b64encode(b"hello").decode("ascii"),
    }
    resp = authed_client.post(
        "/api/v1/mcp/media",
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "X-Pen-Site-Id": "default",  # must not override JWT
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["site_id"] == "other"
    assert (
        two_sites
        / "sites"
        / "other"
        / "assets"
        / "images"
        / "content"
        / "mcp-page"
        / "hello.txt"
    ).is_file()
    assert not (
        two_sites
        / "sites"
        / "default"
        / "assets"
        / "images"
        / "content"
        / "mcp-page"
        / "hello.txt"
    ).exists()

    default_token = _mint_token(authed_client, "def-media", "default")
    resp = authed_client.get(
        "/api/v1/mcp/media",
        headers={"Authorization": f"Bearer {default_token}"},
    )
    assert resp.status_code == 200
    files = [f["filename"] for f in resp.json()]
    assert not any("mcp-page" in f for f in files)


def test_taxonomy_put_site_isolation(authed_client, two_sites):
    resp = authed_client.get("/api/taxonomy/", headers={"X-Pen-Site-Id": "default"})
    assert resp.status_code == 200, resp.text

    other_payload = {
        "vocabularies": {
            "topics": {"label": "Topics", "terms": ["Alpha", "Beta"]},
        },
        "primary_vocabulary": "topics",
        "required_fields": ["name", "status"],
    }
    resp = authed_client.put(
        "/api/taxonomy/",
        json=other_payload,
        headers={"X-Pen-Site-Id": "other"},
    )
    assert resp.status_code == 200, resp.text

    other_file = two_sites / "sites" / "other" / "taxonomy.yaml"
    assert other_file.is_file()
    other_data = yaml.safe_load(other_file.read_text())
    assert other_data["primary_vocabulary"] == "topics"

    default_file = two_sites / "sites" / "default" / "taxonomy.yaml"
    default_data = yaml.safe_load(default_file.read_text())
    assert default_data.get("primary_vocabulary") != "topics"

    resp = authed_client.get("/api/taxonomy/", headers={"X-Pen-Site-Id": "other"})
    assert resp.json()["parsed"]["primary_vocabulary"] == "topics"


def test_migrate_menus_and_assets(temp_data_root, monkeypatch):
    import config
    from services.storage_provider import LocalStorageProvider
    import services.file_service as file_service
    from services.site_service import ensure_sites_initialized

    content = temp_data_root / "content"
    assets = temp_data_root / "assets"
    content.mkdir(exist_ok=True)
    assets.mkdir(exist_ok=True)

    sites_yaml = temp_data_root / "data" / "sites.yaml"
    if sites_yaml.exists():
        sites_yaml.unlink()
    if (content / "sites").exists():
        shutil.rmtree(content / "sites")

    menus_json = temp_data_root / "menus.json"
    menus_json.write_text(
        json.dumps(
            {
                "primary": [
                    {
                        "id": "m1",
                        "menu": "primary",
                        "label": "Migrated",
                        "target": {"type": "system", "content_slug": "home"},
                        "parent_id": None,
                        "order": 0,
                        "open_in_new_tab": False,
                    }
                ],
                "secondary": [],
                "footer": [],
            }
        )
    )

    legacy_img = assets / "images" / "content" / "old-page"
    legacy_img.mkdir(parents=True)
    (legacy_img / "pic.png").write_bytes(b"png")

    provider = LocalStorageProvider(str(content))
    monkeypatch.setattr(config, "CONTENT_DIR_PATH", content)
    monkeypatch.setattr(config, "ASSETS_DIR_PATH", assets)
    monkeypatch.setattr(config, "content_storage", provider)
    monkeypatch.setattr(file_service, "content_storage", provider)

    ensure_sites_initialized()

    menus_yaml = content / "sites" / "default" / "menus.yaml"
    assert menus_yaml.is_file()
    data = yaml.safe_load(menus_yaml.read_text())
    assert any(i.get("label") == "Migrated" for i in data.get("primary", []))
    assert menus_json.is_file()

    migrated = (
        content
        / "sites"
        / "default"
        / "assets"
        / "images"
        / "content"
        / "old-page"
        / "pic.png"
    )
    assert migrated.is_file()


def test_create_site_seeds_structure(authed_client, two_sites):
    from services.site_service import create_site

    try:
        create_site("wiki", "Wiki")
    except ValueError:
        pass
    root = two_sites / "sites" / "wiki"
    assert (root / "menus.yaml").is_file()
    assert (root / "taxonomy.yaml").is_file()
    assert (root / "collections.yaml").is_file()
    assert (root / "assets").is_dir()

    import yaml

    with open(root / "taxonomy.yaml", encoding="utf-8") as f:
        tax = yaml.safe_load(f) or {}
    assert tax.get("vocabularies") == {}
    assert not tax.get("primary_vocabulary")
    assert tax.get("required_fields") == ["name", "status"]
