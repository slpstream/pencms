"""Phase 1b: colocated AS — PKCE authorize/token, resource binding, refresh."""

from __future__ import annotations

import base64
import hashlib
import secrets
from urllib.parse import parse_qs, urlparse

import pytest

from services.auth_service import (
    JWT_ISSUER,
    MCP_RESOURCE_URL,
    decode_access_token,
    decode_agent_token,
)
from services.authz import ordered_allowed_scopes
from services.oauth_store import clear_oauth_store


@pytest.fixture(autouse=True)
def _clean_oauth_store():
    clear_oauth_store()
    yield
    clear_oauth_store()


def _pkce_pair():
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _create_agent_key(authed_client, scopes, name=None):
    import secrets

    name = name or f"oauth-{secrets.token_hex(4)}"
    resp = authed_client.post(
        "/api/auth/keys", json={"name": name, "scopes": scopes}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["key"]


def _authorize_params(challenge, *, scope="read", resource=None, method="S256"):
    return {
        "client_id": "pencms-dev",
        "redirect_uri": "http://127.0.0.1:8765/callback",
        "response_type": "code",
        "code_challenge": challenge,
        "code_challenge_method": method,
        "resource": resource if resource is not None else MCP_RESOURCE_URL,
        "scope": scope,
        "state": "xyz",
    }


def _complete_pkce_flow(authed_client, *, scopes=("read",), consent_scopes=None):
    """Happy-path: create key → consent → token. Returns token response JSON."""
    _create_agent_key(authed_client, list(scopes))
    verifier, challenge = _pkce_pair()
    params = _authorize_params(challenge, scope=" ".join(scopes))

    resp = authed_client.get("/oauth/authorize", params=params)
    assert resp.status_code == 200, resp.text
    assert "Agent key" in resp.text

    granted = list(consent_scopes if consent_scopes is not None else scopes)
    data = {k: v for k, v in params.items() if v is not None}
    data["key_index"] = "0"
    data["consent_scope"] = granted

    resp = authed_client.post(
        "/oauth/authorize/consent",
        data=data,
        follow_redirects=False,
    )
    assert resp.status_code == 302, resp.text
    location = resp.headers["location"]
    qs = parse_qs(urlparse(location).query)
    assert "code" in qs, location
    code = qs["code"][0]
    assert qs.get("state", [None])[0] == "xyz"
    assert qs.get("iss", [None])[0] == JWT_ISSUER

    resp = authed_client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": verifier,
            "redirect_uri": params["redirect_uri"],
            "client_id": params["client_id"],
            "resource": MCP_RESOURCE_URL,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_as_metadata_document(client):
    resp = client.get("/.well-known/oauth-authorization-server")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["issuer"] == JWT_ISSUER
    assert body["authorization_endpoint"] == f"{JWT_ISSUER}/oauth/authorize"
    assert body["token_endpoint"] == f"{JWT_ISSUER}/oauth/token"
    assert body["code_challenge_methods_supported"] == ["S256"]
    assert body["scopes_supported"] == ordered_allowed_scopes()
    assert "write:posts" in body["scopes_supported"]
    assert body["response_types_supported"] == ["code"]
    assert "authorization_code" in body["grant_types_supported"]
    assert "refresh_token" in body["grant_types_supported"]
    assert body["resource_indicators_supported"] is True
    assert body["authorization_response_iss_parameter_supported"] is True


def test_pkce_s256_success_mints_agent_token(authed_client):
    body = _complete_pkce_flow(authed_client, scopes=("read", "write"))
    assert body["token_type"] == "bearer"
    assert "access_token" in body
    assert "refresh_token" in body

    payload = decode_agent_token(body["access_token"])
    assert payload["iss"] == JWT_ISSUER
    assert payload["aud"] == MCP_RESOURCE_URL
    assert payload["type"] == "agent"
    assert set(payload["scopes"]) == {"read", "write"}
    assert "jti" in payload
    assert payload["agent_key_name"].startswith("oauth-")
    assert payload["agent_key_id"].startswith("ak_")
    assert payload["agent_key_index"] == 0


def test_pkce_plain_rejected_on_authorize(authed_client):
    _create_agent_key(authed_client, ["read"])
    verifier, challenge = _pkce_pair()
    params = _authorize_params(challenge, method="plain")
    resp = authed_client.get("/oauth/authorize", params=params)
    assert resp.status_code == 400
    assert "plain" in resp.text.lower() or "S256" in resp.text


def test_pkce_plain_rejected_on_token(authed_client):
    """Even if a code existed, token endpoint rejects explicit plain method."""
    _create_agent_key(authed_client, ["read"])
    verifier, challenge = _pkce_pair()
    params = _authorize_params(challenge)

    resp = authed_client.get("/oauth/authorize", params=params)
    assert resp.status_code == 200

    resp = authed_client.post(
        "/oauth/authorize/consent",
        data={**params, "key_index": "0", "consent_scope": "read"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    code = parse_qs(urlparse(resp.headers["location"]).query)["code"][0]

    resp = authed_client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": verifier,
            "code_challenge_method": "plain",
            "redirect_uri": params["redirect_uri"],
            "client_id": params["client_id"],
            "resource": MCP_RESOURCE_URL,
        },
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_request"
    assert "plain" in resp.json()["error_description"].lower()


def test_wrong_resource_rejected_on_authorize(authed_client):
    _create_agent_key(authed_client, ["read"])
    _, challenge = _pkce_pair()
    params = _authorize_params(challenge, resource="https://evil.example/api/mcp")
    resp = authed_client.get("/oauth/authorize", params=params, follow_redirects=False)
    # Usable redirect → OAuth error redirect, or direct 400
    assert resp.status_code in (302, 400), resp.text
    if resp.status_code == 302:
        qs = parse_qs(urlparse(resp.headers["location"]).query)
        assert qs.get("error", [None])[0] == "invalid_request"
        assert qs.get("iss", [None])[0] == JWT_ISSUER


def test_wrong_resource_rejected_on_token(authed_client):
    _create_agent_key(authed_client, ["read"])
    verifier, challenge = _pkce_pair()
    params = _authorize_params(challenge)

    resp = authed_client.get("/oauth/authorize", params=params)
    assert resp.status_code == 200
    resp = authed_client.post(
        "/oauth/authorize/consent",
        data={**params, "key_index": "0", "consent_scope": "read"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    code = parse_qs(urlparse(resp.headers["location"]).query)["code"][0]

    resp = authed_client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": verifier,
            "redirect_uri": params["redirect_uri"],
            "client_id": params["client_id"],
            "resource": "https://evil.example/api/mcp",
        },
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"] in ("invalid_target", "invalid_grant", "invalid_request")


def test_oauth_token_insufficient_scope_on_write(authed_client):
    body = _complete_pkce_flow(authed_client, scopes=("read",))
    token = body["access_token"]
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


def test_automation_token_still_works(authed_client):
    raw_key = _create_agent_key(authed_client, ["read"])
    resp = authed_client.post("/api/auth/token", json={"agent_key": raw_key})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    payload = decode_agent_token(token)
    assert payload["type"] == "agent"
    assert payload["aud"] == MCP_RESOURCE_URL

    resp = authed_client.get(
        "/api/v1/mcp/site-config",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


def test_human_cookie_bypasses_agent_scope_rules(authed_client):
    """Human pen_jwt session still reaches write tools without agent scopes."""
    # No agent token — only cookie from login fixture
    human = decode_access_token(authed_client.cookies.get("pen_jwt"))
    assert human.get("type") != "agent"
    assert "aud" not in human

    resp = authed_client.get("/api/v1/mcp/site-config")
    assert resp.status_code == 200


def test_refresh_token_rotation(authed_client):
    body = _complete_pkce_flow(authed_client, scopes=("read",))
    refresh = body["refresh_token"]

    resp = authed_client.post(
        "/oauth/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "client_id": "pencms-dev",
            "resource": MCP_RESOURCE_URL,
        },
    )
    assert resp.status_code == 200, resp.text
    new_body = resp.json()
    assert new_body["access_token"] != body["access_token"]
    assert new_body["refresh_token"] != refresh
    refreshed = decode_agent_token(new_body["access_token"])
    assert refreshed["agent_key_name"].startswith("oauth-")
    assert refreshed["agent_key_id"] == decode_agent_token(body["access_token"])["agent_key_id"]
    assert refreshed["agent_key_index"] == 0

    # Old refresh token is revoked
    resp = authed_client.post(
        "/oauth/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "client_id": "pencms-dev",
            "resource": MCP_RESOURCE_URL,
        },
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_grant"


def test_refresh_cannot_shift_to_another_key_after_revocation(authed_client):
    body = _complete_pkce_flow(authed_client, scopes=("read",))
    refresh = body["refresh_token"]
    original = decode_agent_token(body["access_token"])
    revoked = authed_client.delete("/api/auth/keys/0")
    assert revoked.status_code == 200, revoked.text
    _create_agent_key(
        authed_client,
        ["read", "write"],
        name=original["agent_key_name"],
    )

    response = authed_client.post(
        "/oauth/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "client_id": "pencms-dev",
            "resource": MCP_RESOURCE_URL,
        },
    )
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_grant"
    assert "revoked" in response.json()["error_description"].lower()


def test_authorize_requires_admin_session(client):
    _, challenge = _pkce_pair()
    params = _authorize_params(challenge)
    resp = client.get("/oauth/authorize", params=params)
    assert resp.status_code == 200
    assert "Sign in" in resp.text


def test_no_dcr_register_endpoint(client):
    """PenCMS rejects Dynamic Client Registration; CIMD / static allowlist only."""
    resp = client.post(
        "/oauth/register",
        json={
            "redirect_uris": ["http://127.0.0.1:8765/callback"],
            "client_name": "should-not-register",
        },
    )
    assert resp.status_code == 404


def _public_addrinfo(*_args, **_kwargs):
    import socket

    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]


class _ForbiddenAsyncClient:
    def __init__(self, *args, **kwargs):
        raise AssertionError("httpx.AsyncClient should not be constructed")


class _CimdHttpClient:
    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs
        self.requested_url = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, url, headers=None):
        self.requested_url = url
        _CimdHttpClient.last = self
        body = {
            "redirect_uris": ["http://127.0.0.1:8765/callback"],
        }
        import json

        raw = json.dumps(body).encode()

        class _Resp:
            status_code = 200
            content = raw

            @staticmethod
            def json():
                return body

        return _Resp()


@pytest.mark.parametrize(
    "client_id",
    [
        "http://cimd.example/client.json",
        "https://127.0.0.1/client.json",
        "https://localhost/client.json",
        "https://[::ffff:127.0.0.1]/client.json",
        "https://169.254.169.254/client.json",
        "https://192.168.1.1/client.json",
        "https://metadata.google.internal/client.json",
        "https://cimd.example:8443/client.json",
        "https://user:pass@cimd.example/client.json",
        "https://foo.internal/client.json",
        "https://127.1/client.json",
        "https://2130706433/client.json",
    ],
)
def test_cimd_ssrf_rejected_unauthenticated(client, client_id, monkeypatch):
    monkeypatch.setattr("services.url_safety.socket.getaddrinfo", _public_addrinfo)
    monkeypatch.setattr("routers.oauth_mcp.httpx.AsyncClient", _ForbiddenAsyncClient)
    _, challenge = _pkce_pair()
    params = _authorize_params(challenge)
    params["client_id"] = client_id
    resp = client.get("/oauth/authorize", params=params)
    assert resp.status_code == 400, resp.text
    assert "restricted" in resp.json()["detail"].lower() or "invalid" in resp.json()[
        "detail"
    ].lower()


def test_cimd_rejects_private_dns(client, monkeypatch):
    import socket

    monkeypatch.setattr(
        "services.url_safety.socket.getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))
        ],
    )
    monkeypatch.setattr("routers.oauth_mcp.httpx.AsyncClient", _ForbiddenAsyncClient)
    _, challenge = _pkce_pair()
    params = _authorize_params(challenge)
    params["client_id"] = "https://evil.example/client.json"
    resp = client.get("/oauth/authorize", params=params)
    assert resp.status_code == 400, resp.text


def test_unauthenticated_cimd_does_not_fetch(client, monkeypatch):
    monkeypatch.setattr("services.url_safety.socket.getaddrinfo", _public_addrinfo)
    monkeypatch.setattr("routers.oauth_mcp.httpx.AsyncClient", _ForbiddenAsyncClient)
    _, challenge = _pkce_pair()
    params = _authorize_params(challenge)
    params["client_id"] = "https://cimd.example/client.json"
    resp = client.get("/oauth/authorize", params=params)
    assert resp.status_code == 200, resp.text
    assert "Sign in" in resp.text


def test_authenticated_cimd_fetches_metadata(authed_client, monkeypatch):
    _CimdHttpClient.last = None
    monkeypatch.setattr("services.url_safety.socket.getaddrinfo", _public_addrinfo)
    monkeypatch.setattr("routers.oauth_mcp.httpx.AsyncClient", _CimdHttpClient)
    _create_agent_key(authed_client, ["read"])
    _, challenge = _pkce_pair()
    params = _authorize_params(challenge)
    params["client_id"] = "https://CIMD.example:443/client.json"
    resp = authed_client.get("/oauth/authorize", params=params)
    assert resp.status_code == 200, resp.text
    assert "Authorize client" in resp.text
    last = _CimdHttpClient.last
    assert last is not None
    assert last.requested_url == "https://cimd.example/client.json"
    assert last.kwargs.get("follow_redirects") is False
    assert last.kwargs.get("trust_env") is False
