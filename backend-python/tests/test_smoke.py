"""Smoke tests that validate the test harness itself.

These exist to fail fast if the conftest path-patching breaks — they do not
assert anything about AI proxy behaviour. The real Phase 1 invariants live
in `test_ai_proxy.py`.
"""

from __future__ import annotations


def test_health_endpoint(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_root_lists_endpoints(client):
    resp = client.get("/api")
    assert resp.status_code == 200
    body = resp.json()
    assert body["health"] == "/api/health"
    assert body["docs"] == "/api/docs"


def test_setup_then_login(authed_client):
    # The `authed_client` fixture already did setup + login; sanity-check it.
    resp = authed_client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json()["user"]["username"] == "testadmin"


def test_unauthenticated_ai_chat_rejected(client):
    # No cookie, no bearer → 401 from get_current_user.
    resp = client.post(
        "/api/ai/chat",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code == 401


def test_agent_key_flow_yields_bearer_token(agent_key):
    # The fixture already exchanged; just assert it looks like a JWT.
    assert isinstance(agent_key, str)
    assert agent_key.count(".") == 2
