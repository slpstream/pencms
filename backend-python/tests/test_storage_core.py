"""Phase 4: SSH as a content/assets storage type is unmounted on a Core boot."""

from __future__ import annotations


def test_storage_types_are_local_and_git():
    from services.storage_registry import list_storage_types

    assert list_storage_types() == ["local", "git"]


def test_core_vault_headers_omit_content_assets_ssh():
    from services.vault_headers import list_vault_headers

    aliases = {alias.lower() for alias, _fn in list_vault_headers()}
    assert "x-vault-publish-pass" in aliases
    assert "x-vault-publish-github-token" in aliases
    assert "x-vault-content-pass" not in aliases
    assert "x-vault-assets-pass" not in aliases


def test_available_providers_omit_ssh(authed_client):
    resp = authed_client.get("/api/storage/config")
    assert resp.status_code == 200, resp.text
    assert resp.json()["available_providers"] == ["local", "git"]


def test_put_ssh_storage_refused(authed_client):
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
            "assets_dir": "../pencms-data/assets",
        },
    )
    assert resp.status_code == 400, resp.text
    detail = resp.json()["detail"]
    assert "ssh" in detail.lower()
    assert "pro" in detail.lower()


def test_test_ssh_refused(authed_client):
    resp = authed_client.post(
        "/api/storage/test-ssh",
        json={
            "host": "example.com",
            "port": 22,
            "username": "deploy",
            "path": "/var/www/html",
            "auth_method": "key",
        },
    )
    assert resp.status_code == 400, resp.text
    detail = resp.json()["detail"]
    assert "ssh" in detail.lower()
    assert "pro" in detail.lower()


def test_ssh_key_endpoint_still_mounted(authed_client):
    resp = authed_client.get("/api/storage/ssh-key")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "exists" in body
    assert "key_path" in body
    assert "public_key" in body
