"""Named agent keys — create with label, reject duplicates / bad slugs."""

import jwt


def test_create_named_agent_key(authed_client):
    resp = authed_client.post(
        "/api/auth/keys",
        json={"name": "cursor", "scopes": ["read", "write"], "site_id": "default"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["name"] == "cursor"
    assert data["key_id"].startswith("ak_")
    assert data["key"].startswith("pen-sk-")
    assert set(data["scopes"]) == {"read", "write"}
    assert data["site_id"] == "default"

    listed = authed_client.get("/api/auth/keys")
    assert listed.status_code == 200
    names = [k["name"] for k in listed.json()["keys"]]
    assert "cursor" in names
    key_meta = next(k for k in listed.json()["keys"] if k["name"] == "cursor")
    assert key_meta["site_id"] == "default"

    # JWT carries site and non-secret named-key identity for provenance.
    tok = authed_client.post("/api/auth/token", json={"agent_key": data["key"]})
    assert tok.status_code == 200
    claims = jwt.decode(tok.json()["access_token"], options={"verify_signature": False})
    assert claims["site_id"] == "default"
    assert claims["agent_key_name"] == "cursor"
    assert claims["agent_key_id"] == data["key_id"]
    assert isinstance(claims["agent_key_index"], int)


def test_duplicate_name_rejected(authed_client):
    resp = authed_client.post(
        "/api/auth/keys", json={"name": "claude", "scopes": ["read"]}
    )
    assert resp.status_code == 200, resp.text

    resp = authed_client.post(
        "/api/auth/keys", json={"name": "claude", "scopes": ["read", "write"]}
    )
    assert resp.status_code == 400
    assert "already exists" in resp.json()["detail"]


def test_invalid_name_rejected(authed_client):
    for bad in ("", "A", "has space", "bad!", "x"):
        resp = authed_client.post(
            "/api/auth/keys", json={"name": bad, "scopes": ["read"]}
        )
        assert resp.status_code == 400, bad


def test_name_normalized_lowercase(authed_client):
    resp = authed_client.post(
        "/api/auth/keys", json={"name": "Writing-Partner", "scopes": ["read"]}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "writing-partner"
