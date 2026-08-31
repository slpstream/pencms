"""Deploy Grants + agent scope ``publish`` + host deploy path (S8)."""

from __future__ import annotations

import shutil

import pytest


@pytest.fixture(autouse=True)
def _clear_publish_runs():
    from services.publish_deploy import clear_runs

    clear_runs()
    yield
    clear_runs()


@pytest.fixture
def isolated_content(temp_data_root, monkeypatch):
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

    grants = temp_data_root / "data" / "publish-grants"
    if grants.exists():
        shutil.rmtree(grants)

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


def _mint_agent(authed_client, name: str, scopes: list, site_id: str = "default") -> str:
    resp = authed_client.post(
        "/api/auth/keys",
        json={"name": name, "scopes": scopes, "site_id": site_id},
    )
    assert resp.status_code == 200, resp.text
    raw = resp.json()["key"]
    resp = authed_client.post("/api/auth/token", json={"agent_key": raw})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def test_validate_scopes_accepts_publish():
    from routers.auth import validate_agent_scopes

    assert validate_agent_scopes(["publish"]) == ["publish"]
    assert validate_agent_scopes(["read", "write", "publish"]) == [
        "read",
        "write",
        "publish",
    ]


def test_validate_scopes_preserves_granular():
    from routers.auth import validate_agent_scopes

    assert validate_agent_scopes(["write:posts", "read"]) == ["read", "write:posts"]
    assert validate_agent_scopes(["publish:content"]) == ["publish:content"]


def test_mint_key_with_publish_scope(authed_client, isolated_content):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    resp = authed_client.post(
        "/api/auth/keys",
        json={
            "name": "publish-bot",
            "scopes": ["read", "write", "publish"],
            "site_id": "default",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["scopes"] == ["read", "write", "publish"]


def test_grant_enroll_password_and_status(authed_client, isolated_content, temp_data_root):
    _configure_target(authed_client)
    enroll = authed_client.post(
        "/api/publish/grant",
        json={"site": "default", "password": "s3cret"},
    )
    assert enroll.status_code == 200, enroll.text
    body = enroll.json()
    assert body["enrolled"] is True
    assert body["has_ciphertext"] is True
    assert "password" not in body
    assert (temp_data_root / "data" / "publish-grants" / "default.enc").is_file()

    status = authed_client.get("/api/publish/grant?site=default")
    assert status.status_code == 200
    assert status.json()["enrolled"] is True
    assert "password" not in status.json()

    target = authed_client.get("/api/publish/target?site=default")
    assert target.json()["agent_publish"] == "enrolled"


def test_grant_enroll_key_no_ciphertext(authed_client, isolated_content, temp_data_root):
    _configure_target(authed_client, auth_method="key")
    enroll = authed_client.post("/api/publish/grant", json={"site": "default"})
    assert enroll.status_code == 200, enroll.text
    body = enroll.json()
    assert body["enrolled"] is True
    assert body["has_ciphertext"] is False
    assert not (temp_data_root / "data" / "publish-grants" / "default.enc").exists()


def test_grant_enroll_password_missing(authed_client, isolated_content):
    _configure_target(authed_client)
    resp = authed_client.post("/api/publish/grant", json={"site": "default"})
    assert resp.status_code == 400
    assert "password" in resp.json()["detail"].lower()


def test_agent_cannot_manage_grant(authed_client, isolated_content):
    _configure_target(authed_client)
    token = _mint_agent(authed_client, "grant-nosy", ["read", "write", "publish"])
    headers = {"Authorization": f"Bearer {token}"}
    resp = authed_client.post(
        "/api/publish/grant",
        json={"site": "default", "password": "x"},
        headers=headers,
    )
    assert resp.status_code == 403


def test_write_only_agent_cannot_run(authed_client, isolated_content, monkeypatch):
    _configure_target(authed_client)
    authed_client.post(
        "/api/publish/grant",
        json={"site": "default", "password": "s3cret"},
    )
    token = _mint_agent(authed_client, "writer-only", ["read", "write"])
    headers = {"Authorization": f"Bearer {token}"}

    async def fake_run(site_id, vault, password=None, force_full=False):
        from services.publish_deploy import _mark_success

        _mark_success(site_id)

    monkeypatch.setattr("routers.publish.run_publish", fake_run)

    resp = authed_client.post(
        "/api/publish/run",
        json={"site": "default"},
        headers=headers,
    )
    assert resp.status_code == 403
    assert "publish" in resp.json()["detail"].lower()


def test_agent_with_publish_and_grant_can_run(
    authed_client, isolated_content, monkeypatch
):
    _configure_target(authed_client)
    authed_client.post(
        "/api/publish/grant",
        json={"site": "default", "password": "s3cret-from-grant"},
    )
    token = _mint_agent(
        authed_client, "publisher", ["read", "write", "publish"]
    )
    headers = {"Authorization": f"Bearer {token}"}
    seen = {}

    async def fake_run(site_id, vault, password=None, force_full=False):
        from services.publish_deploy import _mark_success

        seen["password"] = password
        seen["site_id"] = site_id
        _mark_success(site_id)

    monkeypatch.setattr("routers.publish.run_publish", fake_run)

    # No vault headers, no body password — grant store only.
    resp = authed_client.post(
        "/api/publish/run",
        json={"site": "default"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "running"
    assert seen["password"] == "s3cret-from-grant"


def test_revoke_grant_blocks_agent(authed_client, isolated_content, monkeypatch):
    _configure_target(authed_client)
    authed_client.post(
        "/api/publish/grant",
        json={"site": "default", "password": "s3cret"},
    )
    token = _mint_agent(authed_client, "revokee", ["publish"])
    headers = {"Authorization": f"Bearer {token}"}

    revoke = authed_client.delete("/api/publish/grant?site=default")
    assert revoke.status_code == 200
    assert revoke.json()["enrolled"] is False

    async def fake_run(site_id, vault, password=None, force_full=False):
        from services.publish_deploy import _mark_success

        _mark_success(site_id)

    monkeypatch.setattr("routers.publish.run_publish", fake_run)

    resp = authed_client.post(
        "/api/publish/run",
        json={"site": "default"},
        headers=headers,
    )
    assert resp.status_code == 403
    assert "grant" in resp.json()["detail"].lower()


def test_mcp_publish_site_requires_publish_scope(
    authed_client, isolated_content, monkeypatch
):
    _configure_target(authed_client)
    authed_client.post(
        "/api/publish/grant",
        json={"site": "default", "password": "s3cret"},
    )
    write_token = _mint_agent(authed_client, "mcp-writer", ["read", "write"])
    publish_token = _mint_agent(
        authed_client, "mcp-publisher", ["read", "write", "publish"]
    )

    async def fake_run(site_id, vault, password=None, force_full=False):
        from services.publish_deploy import _mark_success

        _mark_success(site_id)

    monkeypatch.setattr("routers.publish.run_publish", fake_run)

    denied = authed_client.post(
        "/api/v1/mcp/publish_site",
        headers={"Authorization": f"Bearer {write_token}"},
    )
    assert denied.status_code == 403

    ok = authed_client.post(
        "/api/v1/mcp/publish_site",
        headers={"Authorization": f"Bearer {publish_token}"},
    )
    assert ok.status_code == 200, ok.text
    data = ok.json()
    assert data["status"] == "running"
    assert "password" not in data
    assert "task_id" in data

    status = authed_client.get(
        "/api/v1/mcp/publish_site/status",
        params={"task_id": data["task_id"]},
        headers={"Authorization": f"Bearer {publish_token}"},
    )
    assert status.status_code == 200
    assert "password" not in status.json()


def test_agent_body_password_ignored_uses_grant(
    authed_client, isolated_content, monkeypatch
):
    """Agents must not override grant secrets via request body."""
    _configure_target(authed_client)
    authed_client.post(
        "/api/publish/grant",
        json={"site": "default", "password": "grant-pass"},
    )
    token = _mint_agent(authed_client, "body-ignore", ["publish"])
    seen = {}

    async def fake_run(site_id, vault, password=None, force_full=False):
        from services.publish_deploy import _mark_success

        seen["password"] = password
        _mark_success(site_id)

    monkeypatch.setattr("routers.publish.run_publish", fake_run)

    resp = authed_client.post(
        "/api/publish/run",
        json={"site": "default", "password": "attacker-pass"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert seen["password"] == "grant-pass"
