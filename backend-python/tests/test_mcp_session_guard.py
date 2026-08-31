"""Streamable HTTP session header: curl-friendly 400, discovery stays 401."""

from __future__ import annotations

import secrets

from services.mcp_session_guard import (
    SESSION_REQUIRED_DETAIL,
    compat_accept_value,
    inject_session_id_json,
)

TOOLS_LIST = {
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list",
    "params": {},
}
INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "pytest-session-guard", "version": "0"},
    },
}


def _mint_agent_token(authed_client, scopes=None) -> str:
    resp = authed_client.post(
        "/api/auth/keys",
        json={
            "name": f"sess-{secrets.token_hex(4)}",
            "scopes": scopes or ["read"],
            "site_id": "default",
        },
    )
    assert resp.status_code == 200, resp.text
    raw_key = resp.json()["key"]
    resp = authed_client.post("/api/auth/token", json={"agent_key": raw_key})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def test_compat_accept_defaults_star_and_empty():
    assert compat_accept_value("") == "application/json, text/event-stream"
    assert compat_accept_value("*/*") == "application/json, text/event-stream"
    assert compat_accept_value("application/json") == "application/json, text/event-stream"
    assert compat_accept_value("application/json, text/event-stream") is None
    assert compat_accept_value("text/html") is None


def test_inject_session_id_json_sets_result_field():
    raw = b'{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-06-18"}}'
    out = inject_session_id_json(raw, "abc")
    import json

    assert json.loads(out)["result"]["sessionId"] == "abc"


def test_unauthenticated_tools_list_still_401(client):
    resp = client.post("/api/mcp", json=TOOLS_LIST)
    assert resp.status_code == 401


def test_bearer_tools_list_without_session_is_400(authed_client):
    token = _mint_agent_token(authed_client)
    resp = authed_client.post(
        "/api/mcp",
        json=TOOLS_LIST,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert body["error"] == "mcp_session_required"
    assert "Mcp-Session-Id" in body["detail"]
    assert body["detail"] == SESSION_REQUIRED_DETAIL


def test_mcp_http_compat_initialize_and_session(authed_client):
    """One FastApiMCP process: omitted Accept, sessionId in JSON, then tools/list."""
    token = _mint_agent_token(authed_client)
    init = authed_client.post(
        "/api/mcp",
        json=INITIALIZE,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert init.status_code != 406, init.text
    assert init.status_code == 200, init.text
    session = init.headers.get("mcp-session-id")
    assert session
    assert init.json()["result"]["sessionId"] == session

    listed = authed_client.post(
        "/api/mcp",
        json=TOOLS_LIST,
        headers={
            "Authorization": f"Bearer {token}",
            "mcp-session-id": session,
        },
    )
    assert listed.status_code != 400, listed.text
    assert listed.status_code == 200, listed.text
