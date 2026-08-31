"""Publish POST /api/publish/test — vault password + connection probe."""

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


def _configure_target(authed_client, **overrides):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    put = authed_client.put("/api/publish/target", json=_target_body(**overrides))
    assert put.status_code == 200, put.text
    return put.json()


def test_publish_test_unauthenticated(client, isolated_content):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    resp = client.post("/api/publish/test", json={"site": "default", "password": "x"})
    assert resp.status_code == 401


def test_publish_test_unknown_site(authed_client, isolated_content):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    resp = authed_client.post(
        "/api/publish/test",
        json={"site": "nosuchsite", "password": "x"},
    )
    assert resp.status_code == 404


def test_publish_test_unconfigured(authed_client, isolated_content):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    resp = authed_client.post(
        "/api/publish/test",
        json={"site": "default", "password": "x"},
    )
    assert resp.status_code == 400
    assert "not configured" in resp.json()["detail"].lower()


def test_publish_test_missing_password(authed_client, isolated_content):
    _configure_target(authed_client)
    resp = authed_client.post("/api/publish/test", json={"site": "default"})
    assert resp.status_code == 400
    detail = resp.json()["detail"].lower()
    assert "password" in detail


def test_publish_test_key_auth_no_password(authed_client, isolated_content, monkeypatch):
    """Key auth probes without vault publish password; provider has no secret_key."""
    _configure_target(authed_client, auth_method="key")
    seen = {}

    async def fake_exec(*, user, host, port, command, password=None, input_data=None):
        seen["password"] = password
        return 0, b"PENCMS_OK\n", b""

    monkeypatch.setattr("services.publish_providers.sftp.ssh_exec", fake_exec)

    resp = authed_client.post("/api/publish/test", json={"site": "default"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True
    assert seen["password"] is None


def test_publish_test_success_body_password(authed_client, isolated_content, monkeypatch, temp_data_root):
    _configure_target(authed_client)

    async def fake_exec(*, user, host, port, command, password=None, input_data=None):
        return 0, b"PENCMS_OK\n", b""

    monkeypatch.setattr("services.publish_providers.sftp.ssh_exec", fake_exec)

    resp = authed_client.post(
        "/api/publish/test",
        json={"site": "default", "password": "s3cret-smoke"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    assert "latency_ms" in data
    assert "password" not in data
    assert "s3cret" not in resp.text

    # Password must not leak into GET target or sites.yaml
    get = authed_client.get("/api/publish/target", params={"site": "default"})
    assert get.status_code == 200
    assert "password" not in get.json()
    assert "s3cret" not in get.text

    registry = temp_data_root / "data" / "sites.yaml"
    raw = registry.read_text()
    assert "s3cret" not in raw
    site = next(s for s in yaml.safe_load(raw)["sites"] if s["id"] == "default")
    assert "password" not in (site.get("publish") or {})


def test_publish_test_success_vault_header(authed_client, isolated_content, monkeypatch):
    _configure_target(authed_client)

    async def fake_exec(*, user, host, port, command, password=None, input_data=None):
        return 0, b"PENCMS_OK\n", b""

    monkeypatch.setattr("services.publish_providers.sftp.ssh_exec", fake_exec)

    resp = authed_client.post(
        "/api/publish/test",
        json={"site": "default"},
        headers={
            "X-Pen-Site-Id": "default",
            "X-Vault-Publish-Pass": "vault-pass-xyz",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True
    assert "vault-pass" not in resp.text


def test_publish_test_ssh_failure(authed_client, isolated_content, monkeypatch):
    _configure_target(authed_client)

    async def fake_exec(*, user, host, port, command, password=None, input_data=None):
        return 1, b"", b"Permission denied (publickey,password)."

    monkeypatch.setattr("services.publish_providers.sftp.ssh_exec", fake_exec)

    resp = authed_client.post(
        "/api/publish/test",
        json={"site": "default", "password": "wrong"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is False
    assert "Permission denied" in data["error"]
