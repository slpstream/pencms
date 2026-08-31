"""Phase 2: users CRUD routes are unmounted on a Core boot."""

from __future__ import annotations


def test_config_edition_is_core(client):
    resp = client.get("/api/config")
    assert resp.status_code == 200, resp.text
    assert resp.json()["edition"] == "core"


def test_users_list_unmounted(client):
    resp = client.get("/api/users")
    assert resp.status_code == 404, resp.text


def test_users_create_unmounted(authed_client):
    resp = authed_client.post(
        "/api/users",
        json={
            "username": "core-orphan",
            "password": "tempPass123",
            "role": "author",
        },
    )
    assert resp.status_code == 404, resp.text


def test_users_absent_from_live_openapi(client):
    resp = client.get("/api/openapi.json")
    assert resp.status_code == 200, resp.text
    paths = resp.json().get("paths", {})
    assert "/api/users" not in paths
    assert "/api/users/{user_uuid}" not in paths


def test_auth_setup_and_agent_keys_still_mounted(client):
    resp = client.get("/api/openapi.json")
    assert resp.status_code == 200, resp.text
    paths = resp.json().get("paths", {})
    assert "/api/auth/setup" in paths
    assert "/api/auth/keys" in paths
