"""Site lifecycle: soft PATCH, hard rename, delete tombstone, move-content, key reassign. Pro overlay."""

from __future__ import annotations

import shutil
from pathlib import Path

import jwt
import pytest

pytestmark = pytest.mark.pro
pytest.importorskip("pencms_pro", reason="sites CRUD is Pro overlay")


@pytest.fixture
def isolated_content(temp_data_root, monkeypatch):
    """Point content storage at the temp root and reset site registry."""
    import config
    from services.storage_provider import LocalStorageProvider
    import services.file_service as file_service

    content = temp_data_root / "content"
    content.mkdir(exist_ok=True)
    sites_yaml = temp_data_root / "data" / "sites.yaml"
    if sites_yaml.exists():
        sites_yaml.unlink()
    sites_dir = content / "sites"
    if sites_dir.exists():
        shutil.rmtree(sites_dir)
    deleted = content / "_deleted"
    if deleted.exists():
        shutil.rmtree(deleted)
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


def _mint_raw_key(authed_client, name: str, site_id: str) -> str:
    resp = authed_client.post(
        "/api/auth/keys",
        json={"name": name, "scopes": ["read", "write"], "site_id": site_id},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["key"]


def _token_from_raw(authed_client, raw: str) -> str:
    resp = authed_client.post("/api/auth/token", json={"agent_key": raw})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def test_soft_patch_name_domain_leaves_path(authed_client, isolated_content):
    from services.site_service import create_site, ensure_sites_initialized, get_site

    ensure_sites_initialized()
    create_site("wiki", "Wiki", domain="wiki.example")

    resp = authed_client.patch(
        "/api/sites/wiki",
        json={"name": "Knowledge Base", "domain": "kb.example"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["name"] == "Knowledge Base"
    assert data["domain"] == "kb.example"
    assert data["content_relpath"] == "sites/wiki"
    assert (isolated_content / "sites" / "wiki").is_dir()
    assert get_site("wiki").content_relpath == "sites/wiki"


def test_hard_rename_keeps_domain(authed_client, isolated_content):
    from services.site_service import (
        create_site,
        ensure_sites_initialized,
        get_site,
        resolve_site_id_by_host,
    )

    ensure_sites_initialized()
    create_site(
        "wiki",
        "Wiki",
        domain="wiki.example",
        language="en",
        languages=["en", "fr"],
        language_labels={"fr": "Français"},
        translation_automation_paused=True,
    )
    resp = authed_client.post("/api/sites/wiki/rename", json={"new_id": "docs"})
    assert resp.status_code == 200, resp.text
    renamed = get_site("docs")
    assert renamed.domain == "wiki.example"
    assert renamed.language == "en"
    assert renamed.languages == ["en", "fr"]
    assert renamed.language_labels == {"fr": "Français"}
    assert renamed.translation_automation_paused is True
    assert resolve_site_id_by_host("wiki.example") == "docs"


def test_hard_rename_moves_disk_keys_fts(authed_client, isolated_content, temp_data_root):
    from services.cache_service import get_entry, save_entry_to_cache
    from services.site_service import create_site, ensure_sites_initialized, get_site
    from services.user_service import get_user_by_uuid, list_users

    ensure_sites_initialized()
    create_site("wiki", "Wiki")

    page = isolated_content / "sites" / "wiki" / "hello" / "index.md"
    page.parent.mkdir(parents=True)
    page.write_text("---\nname: Hello\ncategory: posts\n---\nHi\n")
    save_entry_to_cache(
        "posts",
        "hello",
        "sites/wiki/hello/index.md",
        "Hello",
        True,
        "published",
        "blog",
        False,
        1.0,
        {"name": "Hello", "category": "posts"},
        "Hi",
        site_id="wiki",
    )

    raw = _mint_raw_key(authed_client, "wiki-bot", "wiki")
    old_token = _token_from_raw(authed_client, raw)
    assert jwt.decode(old_token, options={"verify_signature": False})["site_id"] == "wiki"

    resp = authed_client.post("/api/sites/wiki/rename", json={"new_id": "docs"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == "docs"
    assert get_site("wiki") is None
    assert get_site("docs") is not None
    assert not (isolated_content / "sites" / "wiki").exists()
    assert (isolated_content / "sites" / "docs" / "hello" / "index.md").is_file()

    users = list_users()
    user = get_user_by_uuid(users[0].uuid)
    assert any(getattr(k, "site_id", None) == "docs" for k in user.auth.agent_keys)

    assert get_entry("posts", "hello", site_id="wiki") is None
    assert get_entry("posts", "hello", site_id="docs") is not None

    new_token = _token_from_raw(authed_client, raw)
    assert jwt.decode(new_token, options={"verify_signature": False})["site_id"] == "docs"
    # Old JWT still carries old claim
    assert jwt.decode(old_token, options={"verify_signature": False})["site_id"] == "wiki"


def test_cannot_rename_default(authed_client, isolated_content):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    resp = authed_client.post("/api/sites/default/rename", json={"new_id": "main"})
    assert resp.status_code == 400
    assert "default" in resp.json()["detail"].lower()


def test_delete_tombstone_and_key_policy(authed_client, isolated_content, temp_data_root):
    from services.cache_service import get_entry, save_entry_to_cache
    from services.site_service import create_site, ensure_sites_initialized, get_site, list_sites

    ensure_sites_initialized()
    create_site("wiki", "Wiki")
    save_entry_to_cache(
        "posts",
        "gone",
        "sites/wiki/gone.md",
        "Gone",
        True,
        "published",
        "blog",
        False,
        1.0,
        {"name": "Gone"},
        "x",
        site_id="wiki",
    )
    _mint_raw_key(authed_client, "wiki-agent", "wiki")

    # Missing confirm
    resp = authed_client.request(
        "DELETE",
        "/api/sites/wiki",
        json={"confirm": False},
    )
    assert resp.status_code == 400

    # Keys block without policy
    resp = authed_client.request(
        "DELETE",
        "/api/sites/wiki",
        json={"confirm": True},
    )
    assert resp.status_code == 400
    assert "agent key" in resp.json()["detail"].lower()

    resp = authed_client.request(
        "DELETE",
        "/api/sites/wiki",
        json={"confirm": True, "revoke_keys": True},
    )
    assert resp.status_code == 200, resp.text
    assert get_site("wiki") is None
    tombstone = resp.json().get("tombstone")
    assert tombstone
    assert (isolated_content / tombstone).is_dir() or (
        isolated_content / Path(tombstone)
    ).exists()
    assert get_entry("posts", "gone", site_id="wiki") is None
    assert any(s.id == "default" for s in list_sites())


def test_cannot_delete_default_or_last_site(authed_client, isolated_content):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    resp = authed_client.request(
        "DELETE",
        "/api/sites/default",
        json={"confirm": True, "revoke_keys": True},
    )
    assert resp.status_code == 400
    assert "default" in resp.json()["detail"].lower()


def test_move_content_between_sites(authed_client, isolated_content):
    from services.site_service import create_site, ensure_sites_initialized

    ensure_sites_initialized()
    create_site("other", "Other")

    page = isolated_content / "sites" / "other" / "moved-post" / "index.md"
    page.parent.mkdir(parents=True)
    page.write_text("---\nname: Moved\ncategory: summer\nstatus: stub\n---\nbody\n")

    other_raw = _mint_raw_key(authed_client, "move-other", "other")
    default_raw = _mint_raw_key(authed_client, "move-default", "default")
    other_token = _token_from_raw(authed_client, other_raw)
    default_token = _token_from_raw(authed_client, default_raw)

    # Ensure other agent can see it before move
    resp = authed_client.get(
        "/api/v1/mcp/pages/moved-post/content",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 200, resp.text

    resp = authed_client.post(
        "/api/sites/move-content",
        json={
            "from_site": "other",
            "to_site": "default",
            "paths": ["moved-post"],
        },
    )
    assert resp.status_code == 200, resp.text
    assert (isolated_content / "sites" / "default" / "moved-post" / "index.md").is_file()
    assert not (isolated_content / "sites" / "other" / "moved-post").exists()

    resp = authed_client.get(
        "/api/v1/mcp/pages/moved-post/content",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 404

    resp = authed_client.get(
        "/api/v1/mcp/pages/moved-post/content",
        headers={"Authorization": f"Bearer {default_token}"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["site_id"] == "default"


def test_key_reassign_updates_new_token_keeps_old_claim(authed_client, isolated_content):
    from services.site_service import create_site, ensure_sites_initialized

    ensure_sites_initialized()
    create_site("docs", "Docs")

    raw = _mint_raw_key(authed_client, "reassign-bot", "default")
    old_token = _token_from_raw(authed_client, raw)
    assert jwt.decode(old_token, options={"verify_signature": False})["site_id"] == "default"

    # Find key index
    keys = authed_client.get("/api/auth/keys").json()["keys"]
    idx = next(k["id"] for k in keys if k["name"] == "reassign-bot")

    resp = authed_client.patch(
        f"/api/auth/keys/{idx}",
        json={"site_id": "docs"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["site_id"] == "docs"

    new_token = _token_from_raw(authed_client, raw)
    assert jwt.decode(new_token, options={"verify_signature": False})["site_id"] == "docs"
    assert jwt.decode(old_token, options={"verify_signature": False})["site_id"] == "default"


def test_unknown_site_header_still_400(authed_client, isolated_content):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    resp = authed_client.get(
        "/api/v1/content/collections",
        headers={"X-Pen-Site-Id": "does-not-exist"},
    )
    assert resp.status_code == 400
    assert "Unknown site_id" in resp.json()["detail"]
