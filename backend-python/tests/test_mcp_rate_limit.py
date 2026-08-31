"""MCP agent loop-guard: 429 on /api/mcp and /api/v1/mcp/* per agent key."""

from __future__ import annotations

import secrets

import pytest

from services.mcp_rate_limit import RATE_LIMIT_ENV, RATE_LIMIT_PER_MIN_ENV, limiter


@pytest.fixture
def mcp_limit_on(monkeypatch):
    monkeypatch.setenv(RATE_LIMIT_ENV, "1")
    monkeypatch.setenv(RATE_LIMIT_PER_MIN_ENV, "3")
    limiter.reset()
    yield
    limiter.reset()


def _mint_agent_token(authed_client, scopes=None) -> str:
    resp = authed_client.post(
        "/api/auth/keys",
        json={
            "name": f"rl-{secrets.token_hex(4)}",
            "scopes": scopes or ["read"],
            "site_id": "default",
        },
    )
    assert resp.status_code == 200, resp.text
    raw_key = resp.json()["key"]
    resp = authed_client.post("/api/auth/token", json={"agent_key": raw_key})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def test_agent_fourth_mcp_call_is_429(authed_client, mcp_limit_on):
    token = _mint_agent_token(authed_client)
    headers = {"Authorization": f"Bearer {token}"}
    statuses = []
    for _ in range(4):
        resp = authed_client.get("/api/v1/mcp/site-config", headers=headers)
        statuses.append(resp.status_code)
    assert statuses[:3] == [200, 200, 200]
    assert statuses[3] == 429
    body = authed_client.get("/api/v1/mcp/site-config", headers=headers)
    assert body.status_code == 429
    detail = body.json()["detail"]
    assert detail["error"] == "rate_limited"
    assert int(body.headers["Retry-After"]) >= 1
    assert body.headers["X-RateLimit-Limit"] == "3"
    assert body.headers["X-RateLimit-Remaining"] == "0"


def test_human_cookie_session_is_not_limited(authed_client, mcp_limit_on):
    for _ in range(5):
        resp = authed_client.get("/api/v1/mcp/site-config")
        assert resp.status_code == 200, resp.text


def test_limit_buckets_are_per_agent_key(authed_client, mcp_limit_on):
    token_a = _mint_agent_token(authed_client)
    token_b = _mint_agent_token(authed_client)
    for _ in range(3):
        assert (
            authed_client.get(
                "/api/v1/mcp/site-config",
                headers={"Authorization": f"Bearer {token_a}"},
            ).status_code
            == 200
        )
    assert (
        authed_client.get(
            "/api/v1/mcp/site-config",
            headers={"Authorization": f"Bearer {token_a}"},
        ).status_code
        == 429
    )
    assert (
        authed_client.get(
            "/api/v1/mcp/site-config",
            headers={"Authorization": f"Bearer {token_b}"},
        ).status_code
        == 200
    )


def test_non_mcp_paths_are_not_limited(authed_client, mcp_limit_on):
    token = _mint_agent_token(authed_client)
    headers = {"Authorization": f"Bearer {token}"}
    for _ in range(5):
        resp = authed_client.get("/api/health", headers=headers)
        assert resp.status_code == 200
