"""Publish target GET/PUT — per-site non-secret host config."""

from __future__ import annotations

import shutil

import pytest
import yaml


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


def _target_body(**overrides):
    body = {
        "site": "default",
        "provider": "sftp",
        "host": "example.com",
        "port": 22,
        "username": "deploy",
        "remote_path": "/var/www/html",
        "auth_method": "password",
        "public_url": "https://example.com",
    }
    body.update(overrides)
    return body


def test_get_target_unauthenticated(client, isolated_content):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    resp = client.get("/api/publish/target", params={"site": "default"})
    assert resp.status_code == 401


def test_get_target_unknown_site(authed_client, isolated_content):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    resp = authed_client.get("/api/publish/target", params={"site": "nosuchsite"})
    assert resp.status_code == 404


def test_get_target_invalid_site_id(authed_client, isolated_content):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    resp = authed_client.get("/api/publish/target", params={"site": "Bad!"})
    assert resp.status_code == 400


def test_get_target_unconnected(authed_client, isolated_content):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    resp = authed_client.get("/api/publish/target", params={"site": "default"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["site_id"] == "default"
    assert data["configured"] is False
    assert data["host"] is None
    assert "password" not in data


def test_put_get_round_trip(authed_client, isolated_content, temp_data_root):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    put = authed_client.put("/api/publish/target", json=_target_body())
    assert put.status_code == 200, put.text
    body = put.json()
    assert body["configured"] is True
    assert body["host"] == "example.com"
    assert body["username"] == "deploy"
    assert body["remote_path"] == "/var/www/html"
    assert body["port"] == 22
    assert body["auth_method"] == "password"
    assert body["public_url"] == "https://example.com"
    assert body["agent_publish"] == "off"
    assert body["last_published_at"] is None
    assert body["last_status"] is None
    assert body["provider"] == "sftp"
    assert "password" not in body

    get = authed_client.get("/api/publish/target", params={"site": "default"})
    assert get.status_code == 200
    assert get.json() == body

    registry = temp_data_root / "data" / "sites.yaml"
    data = yaml.safe_load(registry.read_text())
    site = next(s for s in data["sites"] if s["id"] == "default")
    assert "publish" in site
    pub = site["publish"]
    assert pub["host"] == "example.com"
    assert pub["username"] == "deploy"
    assert pub.get("provider") == "sftp"
    assert "password" not in pub
    assert "pass" not in pub
    assert "secret" not in pub
    assert "token" not in pub


def test_put_provider_defaults_to_sftp(authed_client, isolated_content):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    body = _target_body()
    del body["provider"]
    put = authed_client.put("/api/publish/target", json=body)
    assert put.status_code == 200, put.text
    assert put.json()["provider"] == "sftp"


def test_put_unknown_provider_rejected(authed_client, isolated_content):
    """Unregistered provider ids are rejected on PUT."""
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    put = authed_client.put(
        "/api/publish/target",
        json=_target_body(provider="azure_static_web"),
    )
    assert put.status_code == 400, put.text
    assert "unknown" in put.json()["detail"].lower()


@pytest.mark.pro
def test_put_here_now_without_host(authed_client, isolated_content):
    """here.now targets need no SFTP host/user/path; slug optional."""
    pytest.importorskip("pencms_pro", reason="cloud publish is Pro overlay")
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    put = authed_client.put(
        "/api/publish/target",
        json={
            "site": "default",
            "provider": "here_now",
            "auth_method": "token",
            "here_now_slug": "my-demo",
            "public_url": "https://my-demo.here.now",
        },
    )
    assert put.status_code == 200, put.text
    body = put.json()
    assert body["configured"] is True
    assert body["provider"] == "here_now"
    assert body["auth_method"] == "token"
    assert body["here_now_slug"] == "my-demo"
    assert body["host"] is None
    assert body["username"] is None
    assert body["remote_path"] is None
    assert "api_key" not in body
    assert "token" not in body
    assert "password" not in body

    get = authed_client.get("/api/publish/target", params={"site": "default"})
    assert get.json() == body


def test_put_webhook_url_round_trip(authed_client, isolated_content, temp_data_root):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    put = authed_client.put(
        "/api/publish/target",
        json=_target_body(webhook_url="https://hooks.example.com/publish"),
    )
    assert put.status_code == 200, put.text
    body = put.json()
    assert body["webhook_url"] == "https://hooks.example.com/publish"

    get = authed_client.get("/api/publish/target", params={"site": "default"})
    assert get.json()["webhook_url"] == "https://hooks.example.com/publish"

    registry = temp_data_root / "data" / "sites.yaml"
    data = yaml.safe_load(registry.read_text())
    site = next(s for s in data["sites"] if s["id"] == "default")
    assert site["publish"]["webhook_url"] == "https://hooks.example.com/publish"

    # Clear via empty string
    cleared = authed_client.put(
        "/api/publish/target",
        json=_target_body(webhook_url=""),
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["webhook_url"] is None


def test_put_webhook_url_rejects_bad_scheme(authed_client, isolated_content):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    resp = authed_client.put(
        "/api/publish/target",
        json=_target_body(webhook_url="ftp://hooks.example.com/publish"),
    )
    assert resp.status_code == 400
    assert "webhook_url" in resp.json()["detail"].lower()


def test_put_webhook_secret_write_only(authed_client, isolated_content, temp_data_root):
    from services.site_service import ensure_sites_initialized, get_publish_webhook_secret

    ensure_sites_initialized()
    put = authed_client.put(
        "/api/publish/target",
        json=_target_body(
            webhook_url="https://hooks.example.com/publish",
            webhook_secret="hook-secret-1",
        ),
    )
    assert put.status_code == 200, put.text
    body = put.json()
    assert body["has_webhook_secret"] is True
    assert "webhook_secret" not in body

    get = authed_client.get("/api/publish/target", params={"site": "default"})
    assert get.json()["has_webhook_secret"] is True
    assert "webhook_secret" not in get.json()
    assert get_publish_webhook_secret("default") == "hook-secret-1"

    # Omit on next PUT → secret retained
    kept = authed_client.put(
        "/api/publish/target",
        json=_target_body(webhook_url="https://hooks.example.com/publish"),
    )
    assert kept.status_code == 200, kept.text
    assert kept.json()["has_webhook_secret"] is True
    assert get_publish_webhook_secret("default") == "hook-secret-1"

    # Empty string clears
    cleared = authed_client.put(
        "/api/publish/target",
        json=_target_body(
            webhook_url="https://hooks.example.com/publish",
            webhook_secret="",
        ),
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["has_webhook_secret"] is False
    assert get_publish_webhook_secret("default") is None

    registry = temp_data_root / "data" / "sites.yaml"
    data = yaml.safe_load(registry.read_text())
    site = next(s for s in data["sites"] if s["id"] == "default")
    assert "webhook_secret" not in site.get("publish", {})


@pytest.mark.pro
def test_put_here_now_rejects_api_key(authed_client, isolated_content):
    pytest.importorskip("pencms_pro", reason="cloud publish is Pro overlay")
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    resp = authed_client.put(
        "/api/publish/target",
        json={
            "site": "default",
            "provider": "here_now",
            "api_key": "hnk_secret",
        },
    )
    assert resp.status_code == 400, resp.text


def test_get_providers_catalog(authed_client, isolated_content):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    resp = authed_client.get("/api/publish/providers")
    assert resp.status_code == 200, resp.text
    providers = resp.json()["providers"]
    by_id = {p["id"]: p for p in providers}
    assert set(by_id) == {"sftp", "github_pages"}
    assert by_id["sftp"]["enabled"] is True
    assert by_id["github_pages"]["enabled"] is True
    assert "ui_schema" in by_id["sftp"]
    assert "ui_schema" in by_id["github_pages"]


def test_put_rejects_password(authed_client, isolated_content, temp_data_root):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    resp = authed_client.put(
        "/api/publish/target",
        json=_target_body(password="s3cret"),
    )
    assert resp.status_code == 400, resp.text
    assert "password" in resp.json()["detail"].lower()

    registry = temp_data_root / "data" / "sites.yaml"
    if registry.is_file():
        raw = registry.read_text()
        assert "s3cret" not in raw
        data = yaml.safe_load(raw) or {}
        for site in data.get("sites") or []:
            pub = site.get("publish") or {}
            assert "password" not in pub


def test_put_unknown_site(authed_client, isolated_content):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    resp = authed_client.put(
        "/api/publish/target",
        json=_target_body(site="nosuchsite"),
    )
    assert resp.status_code == 404


def test_set_publish_target_service_rejects_secrets(isolated_content):
    from services.site_service import (
        ensure_sites_initialized,
        set_publish_target,
    )

    ensure_sites_initialized()
    with pytest.raises(ValueError, match="password"):
        set_publish_target(
            "default",
            {
                "host": "example.com",
                "username": "deploy",
                "remote_path": "/var/www",
                "password": "nope",
            },
        )
