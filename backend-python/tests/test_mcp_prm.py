"""Phase 0 / 1a: PRM discovery, gateway 401 challenge, aud/iss enforcement."""

from datetime import timedelta

import jwt
import pytest

from services.auth_service import (
    AGENT_TOKEN_EXPIRE_MINUTES,
    JWT_ALGORITHM,
    JWT_ISSUER,
    JWT_SECRET,
    MCP_RESOURCE_URL,
    create_access_token,
    create_agent_access_token,
    decode_access_token,
    decode_agent_token,
    prm_metadata_url,
)
from services.authz import ordered_allowed_scopes


@pytest.fixture
def agent_token_factory(authed_client):
    def _create(scopes):
        import secrets

        resp = authed_client.post(
            "/api/auth/keys",
            json={"name": f"prm-{secrets.token_hex(4)}", "scopes": scopes},
        )
        assert resp.status_code == 200, resp.text
        raw_key = resp.json()["key"]

        resp = authed_client.post("/api/auth/token", json={"agent_key": raw_key})
        assert resp.status_code == 200, resp.text
        return resp.json()["access_token"]

    return _create


def test_prm_document_fields(client):
    for path in (
        "/.well-known/oauth-protected-resource",
        "/.well-known/oauth-protected-resource/api/mcp",
    ):
        resp = client.get(path)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["resource"] == MCP_RESOURCE_URL
        assert body["authorization_servers"] == [JWT_ISSUER]
        assert body["scopes_supported"] == ordered_allowed_scopes()
        assert "read" in body["scopes_supported"]
        assert "write" in body["scopes_supported"]
        assert "publish" in body["scopes_supported"]
        assert "write:posts" in body["scopes_supported"]


def test_unauthenticated_mcp_gateway_returns_401_with_resource_metadata(client):
    resp = client.post("/api/mcp")
    assert resp.status_code == 401
    www = resp.headers.get("www-authenticate", "")
    assert "Bearer" in www
    assert f'resource_metadata="{prm_metadata_url()}"' in www
    assert 'scope="read"' in www


def test_agent_token_carries_iss_aud_and_short_ttl(authed_client, agent_token_factory):
    token = agent_token_factory(["read"])
    payload = decode_agent_token(token)
    assert payload["iss"] == JWT_ISSUER
    assert payload["aud"] == MCP_RESOURCE_URL
    assert payload["type"] == "agent"
    assert "read" in payload["scopes"]
    assert payload.get("site_id") == "default"

    # exp should be roughly AGENT_TOKEN_EXPIRE_MINUTES, not the 7-day human TTL
    import time

    remaining = payload["exp"] - time.time()
    assert remaining <= AGENT_TOKEN_EXPIRE_MINUTES * 60 + 30
    assert remaining > 0


def test_human_token_omits_aud(authed_client):
    # Cookie login JWT from fixture — decode without audience
    token = authed_client.cookies.get("pen_jwt")
    assert token
    payload = decode_access_token(token)
    assert "aud" not in payload
    assert payload.get("type") != "agent"


def test_wrong_aud_rejected_on_gateway(authed_client):
    bad = create_access_token(
        {
            "sub": "someone",
            "role": "admin",
            "scopes": ["read", "write"],
            "type": "agent",
        },
        expires_delta=timedelta(minutes=15),
        issuer=JWT_ISSUER,
        audience="https://evil.example/api/mcp",
    )
    resp = authed_client.post(
        "/api/mcp",
        headers={"Authorization": f"Bearer {bad}"},
    )
    assert resp.status_code == 401
    www = resp.headers.get("www-authenticate", "")
    assert "resource_metadata=" in www


def test_wrong_aud_rejected_on_rest_tools(authed_client):
    human = decode_access_token(authed_client.cookies.get("pen_jwt"))
    bad = create_access_token(
        {
            "sub": human["sub"],
            "role": "admin",
            "scopes": ["read"],
            "type": "agent",
        },
        expires_delta=timedelta(minutes=15),
        issuer=JWT_ISSUER,
        audience="https://evil.example/api/mcp",
    )
    resp = authed_client.get(
        "/api/v1/mcp/site-config",
        headers={"Authorization": f"Bearer {bad}"},
    )
    assert resp.status_code == 401
    assert "resource_metadata=" in resp.headers.get("www-authenticate", "")


def test_valid_agent_token_works_on_rest_tools(authed_client, agent_token_factory):
    token = agent_token_factory(["read"])
    resp = authed_client.get(
        "/api/v1/mcp/site-config",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert "collections" in resp.json()


def test_insufficient_scope_includes_www_authenticate(authed_client, agent_token_factory):
    token = agent_token_factory(["read"])
    resp = authed_client.put(
        "/api/v1/mcp/pages/test-slug",
        json={
            "frontmatter": {"title": "T", "category": "summer"},
            "body": "x",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    www = resp.headers.get("www-authenticate", "")
    assert 'error="insufficient_scope"' in www
    assert 'scope="write:posts"' in www


def test_create_agent_access_token_helper():
    token = create_agent_access_token(
        {"sub": "u1", "role": "admin", "scopes": ["read"], "type": "agent"}
    )
    payload = jwt.decode(
        token,
        JWT_SECRET,
        algorithms=[JWT_ALGORITHM],
        audience=MCP_RESOURCE_URL,
        issuer=JWT_ISSUER,
    )
    assert payload["aud"] == MCP_RESOURCE_URL
    assert payload["iss"] == JWT_ISSUER
