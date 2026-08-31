"""Phase 4: SSH content/assets storage type + vault headers (Pro overlay)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.pro
pytest.importorskip("pencms_pro", reason="SSH storage type is Pro overlay")


def test_storage_types_include_ssh(client):
    from services.storage_registry import list_storage_types

    assert list_storage_types() == ["local", "git", "ssh"]


def test_pro_vault_headers_include_content_assets_ssh(client):
    from services.vault_headers import list_vault_headers

    aliases = {alias.lower() for alias, _fn in list_vault_headers()}
    assert "x-vault-content-pass" in aliases
    assert "x-vault-assets-pass" in aliases


def test_available_providers_include_ssh(authed_client):
    resp = authed_client.get("/api/storage/config")
    assert resp.status_code == 200, resp.text
    assert resp.json()["available_providers"] == ["local", "git", "ssh"]


def test_put_ssh_storage_validates_uri(authed_client, temp_data_root):
    resp = authed_client.put(
        "/api/storage/config",
        json={
            "content_storage_type": "ssh",
            "assets_storage_type": "local",
            "content_ssh": {
                "host": "example.com",
                "port": 22,
                "username": "deploy",
                "path": "/var/www/content",
            },
            "assets_dir": str(temp_data_root / "assets"),
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json().get("restart_required") is True


def test_test_ssh_probes_via_helper(authed_client, monkeypatch):
    seen = {}

    async def fake_exec(*, user, host, port, command, password=None, input_data=None):
        seen["user"] = user
        seen["host"] = host
        seen["password"] = password
        seen["command"] = command
        return 0, b"PENCMS_OK\n", b""

    monkeypatch.setattr("routers.storage.ssh_exec", fake_exec)

    resp = authed_client.post(
        "/api/storage/test-ssh",
        json={
            "host": "example.com",
            "port": 22,
            "username": "deploy",
            "path": "/var/www/html",
            "auth_method": "password",
            "password": "s3cret",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert seen["user"] == "deploy"
    assert seen["host"] == "example.com"
    assert seen["password"] == "s3cret"
    assert "PENCMS_OK" in seen["command"] or "mkdir" in seen["command"]
