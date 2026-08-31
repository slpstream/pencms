"""Agent-assisted key bootstrap (approve-code)."""

from __future__ import annotations

import time

import pytest

from services.bootstrap_store import clear_bootstrap_store


@pytest.fixture(autouse=True)
def _clean_bootstrap():
    clear_bootstrap_store()
    yield
    clear_bootstrap_store()


def test_bootstrap_request_approve_verify(authed_client, client):
    # Agent (no auth) requests a code
    resp = client.post(
        "/api/auth/agent/request-code",
        json={"name": "cursor", "scopes": ["read", "write"], "site_id": "default"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    user_code = data["user_code"]
    assert len(user_code) == 8
    assert data["expires_in"] == 600
    assert data["site_id"] == "default"

    # Verify before approve → 202
    resp = client.post(
        "/api/auth/agent/verify-code", json={"user_code": user_code}
    )
    assert resp.status_code == 202
    assert resp.json()["status"] == "pending"

    # Admin lists pending
    resp = authed_client.get("/api/auth/agent/pending")
    assert resp.status_code == 200
    pending = resp.json()["pending"]
    assert any(p["user_code"] == user_code and p["name"] == "cursor" for p in pending)

    # Admin approves
    resp = authed_client.post(
        "/api/auth/agent/approve", json={"user_code": user_code}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "approved"

    # Agent verifies → receives pen-sk-…
    resp = client.post(
        "/api/auth/agent/verify-code", json={"user_code": user_code}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["key"].startswith("pen-sk-")
    assert body["name"] == "cursor"
    assert body["site_id"] == "default"
    raw_key = body["key"]

    # Second verify fails (consumed)
    resp = client.post(
        "/api/auth/agent/verify-code", json={"user_code": user_code}
    )
    assert resp.status_code == 400

    # Key works for automation token exchange
    resp = client.post("/api/auth/token", json={"agent_key": raw_key})
    assert resp.status_code == 200
    assert "access_token" in resp.json()

    # Named key appears in list
    listed = authed_client.get("/api/auth/keys")
    names = [k["name"] for k in listed.json()["keys"]]
    assert "cursor" in names


def test_bootstrap_deny(authed_client, client):
    resp = client.post(
        "/api/auth/agent/request-code",
        json={"name": "claude", "scopes": ["read"]},
    )
    user_code = resp.json()["user_code"]

    resp = authed_client.post(
        "/api/auth/agent/approve",
        json={"user_code": user_code, "deny": True},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "denied"

    resp = client.post(
        "/api/auth/agent/verify-code", json={"user_code": user_code}
    )
    assert resp.status_code == 400


def test_bootstrap_duplicate_name_on_verify(authed_client, client):
    # Pre-create named key
    resp = authed_client.post(
        "/api/auth/keys", json={"name": "writing-partner", "scopes": ["read"]}
    )
    assert resp.status_code == 200

    resp = client.post(
        "/api/auth/agent/request-code",
        json={"name": "writing-partner", "scopes": ["read"]},
    )
    assert resp.status_code == 200, resp.text
    user_code = resp.json()["user_code"]

    authed_client.post(
        "/api/auth/agent/approve", json={"user_code": user_code}
    )
    resp = client.post(
        "/api/auth/agent/verify-code", json={"user_code": user_code}
    )
    assert resp.status_code == 400
    assert "already exists" in resp.json()["detail"]


def test_bootstrap_expired(client, authed_client, monkeypatch):
    from services import bootstrap_store as bs

    monkeypatch.setattr(bs, "BOOTSTRAP_TTL_SECONDS", 1)
    # Bypass rate limit between tests
    bs._last_request_at = 0.0

    resp = client.post(
        "/api/auth/agent/request-code",
        json={"name": "expired-bot", "scopes": ["read"]},
    )
    assert resp.status_code == 200
    user_code = resp.json()["user_code"]

    time.sleep(1.2)
    resp = authed_client.post(
        "/api/auth/agent/approve", json={"user_code": user_code}
    )
    assert resp.status_code == 400

    resp = client.post(
        "/api/auth/agent/verify-code", json={"user_code": user_code}
    )
    assert resp.status_code == 400
