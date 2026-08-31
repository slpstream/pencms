import pytest


@pytest.fixture(autouse=True)
def restore_taxonomy():
    import config
    from services.site_service import _empty_taxonomy_dict

    path = config.CONTENT_DIR_PATH / "sites" / "default" / "taxonomy.yaml"
    original = path.read_text(encoding="utf-8") if path.exists() else None
    yield
    path.parent.mkdir(parents=True, exist_ok=True)
    if original is None:
        import yaml

        path.write_text(
            yaml.safe_dump(_empty_taxonomy_dict(), default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )
    else:
        path.write_text(original, encoding="utf-8")
    config.invalidate_taxonomy_cache("default")


@pytest.fixture
def agent_token_factory(authed_client):
    def _create(scopes):
        import secrets

        resp = authed_client.post(
            "/api/auth/keys",
            json={"name": f"tax-{secrets.token_hex(4)}", "scopes": scopes},
        )
        assert resp.status_code == 200, resp.text
        raw_key = resp.json()["key"]

        resp = authed_client.post("/api/auth/token", json={"agent_key": raw_key})
        assert resp.status_code == 200, resp.text
        return resp.json()["access_token"]

    return _create


def test_unauthenticated_mcp_taxonomy_endpoints_rejected(client):
    assert client.get("/api/v1/mcp/taxonomy").status_code == 401
    assert client.put(
        "/api/v1/mcp/taxonomy",
        json={"primary_vocabulary": "topics", "vocabularies": {}},
    ).status_code == 401
    assert client.put(
        "/api/v1/mcp/taxonomy/vocabularies/topics",
        json={"label": "Topics"},
    ).status_code == 401
    assert client.delete("/api/v1/mcp/taxonomy/vocabularies/topics").status_code == 401
    assert client.post(
        "/api/v1/mcp/taxonomy/vocabularies/topics/terms",
        json={"term": "News"},
    ).status_code == 401
    assert client.delete(
        "/api/v1/mcp/taxonomy/vocabularies/topics/terms",
        params={"term": "News"},
    ).status_code == 401
    assert client.post(
        "/api/v1/mcp/taxonomy/primary",
        json={"key": "topics"},
    ).status_code == 401


def test_read_scoped_key_allowed_on_get_taxonomy(authed_client, agent_token_factory):
    token = agent_token_factory(["read"])
    headers = {"Authorization": f"Bearer {token}"}

    resp = authed_client.get("/api/v1/mcp/taxonomy", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["site_id"] == "default"
    assert "vocabularies" in body
    assert "primary_vocabulary" in body
    assert "primary_terms" in body
    assert "required_fields" not in body


def test_read_scoped_key_rejected_on_write_taxonomy(authed_client, agent_token_factory):
    token = agent_token_factory(["read"])
    headers = {"Authorization": f"Bearer {token}"}

    resp = authed_client.put(
        "/api/v1/mcp/taxonomy",
        json={
            "primary_vocabulary": "topics",
            "vocabularies": {
                "topics": {"label": "Topics", "type": "flat", "terms": ["News"]},
            },
        },
        headers=headers,
    )
    assert resp.status_code == 403
    assert "lacks required scope: write:taxonomy" in resp.json()["detail"]


def test_write_taxonomy_bootstrap_and_terms(authed_client, agent_token_factory):
    token = agent_token_factory(["read", "write:taxonomy"])
    headers = {"Authorization": f"Bearer {token}"}

    resp = authed_client.put(
        "/api/v1/mcp/taxonomy",
        json={
            "primary_vocabulary": "topics",
            "vocabularies": {
                "topics": {
                    "label": "Topics",
                    "type": "flat",
                    "controlled": True,
                    "required": False,
                    "terms": ["News"],
                },
            },
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["primary_vocabulary"] == "topics"
    assert body["vocabularies"]["topics"]["terms"] == ["News"]
    assert "news" in body["primary_terms"]

    resp = authed_client.post(
        "/api/v1/mcp/taxonomy/vocabularies/topics/terms",
        json={"term": "Notes"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert "Notes" in resp.json()["vocabularies"]["topics"]["terms"]

    resp = authed_client.delete(
        "/api/v1/mcp/taxonomy/vocabularies/topics/terms",
        params={"term": "News"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["vocabularies"]["topics"]["terms"] == ["Notes"]

    resp = authed_client.put(
        "/api/v1/mcp/taxonomy/vocabularies/tags",
        json={"label": "Tags", "controlled": False, "terms": ["alpha"]},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert "tags" in resp.json()["vocabularies"]
    assert resp.json()["primary_vocabulary"] == "topics"

    resp = authed_client.post(
        "/api/v1/mcp/taxonomy/primary",
        json={"key": "tags"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["primary_vocabulary"] == "tags"

    resp = authed_client.delete(
        "/api/v1/mcp/taxonomy/vocabularies/topics",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert "topics" not in resp.json()["vocabularies"]


def test_legacy_write_scope_can_replace_taxonomy(authed_client, agent_token_factory):
    token = agent_token_factory(["read", "write"])
    headers = {"Authorization": f"Bearer {token}"}
    resp = authed_client.put(
        "/api/v1/mcp/taxonomy",
        json={
            "primary_vocabulary": "topics",
            "vocabularies": {
                "topics": {"label": "Topics", "terms": ["One"]},
            },
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["primary_vocabulary"] == "topics"


def test_replace_taxonomy_refuses_reserved_category(authed_client, agent_token_factory):
    token = agent_token_factory(["read", "write:taxonomy"])
    headers = {"Authorization": f"Bearer {token}"}
    resp = authed_client.put(
        "/api/v1/mcp/taxonomy",
        json={
            "primary_vocabulary": "category",
            "vocabularies": {
                "category": {"label": "Category", "terms": ["News"]},
            },
        },
        headers=headers,
    )
    assert resp.status_code == 400, resp.text
    assert "reserved" in resp.json()["detail"].lower()


def test_cannot_delete_primary_vocabulary(authed_client, agent_token_factory):
    token = agent_token_factory(["read", "write:taxonomy"])
    headers = {"Authorization": f"Bearer {token}"}
    authed_client.put(
        "/api/v1/mcp/taxonomy",
        json={
            "primary_vocabulary": "topics",
            "vocabularies": {
                "topics": {"label": "Topics", "terms": ["News"]},
                "tags": {"label": "Tags", "terms": []},
            },
        },
        headers=headers,
    )
    resp = authed_client.delete(
        "/api/v1/mcp/taxonomy/vocabularies/topics",
        headers=headers,
    )
    assert resp.status_code == 400, resp.text
    assert "primary" in resp.json()["detail"].lower()


def test_replace_taxonomy_preserves_required_fields(authed_client, agent_token_factory):
    import yaml
    import config

    path = config.CONTENT_DIR_PATH / "sites" / "default" / "taxonomy.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "primary_vocabulary": "",
                "required_fields": ["name", "status", "deck"],
                "vocabularies": {},
            },
            default_flow_style=False,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    config.invalidate_taxonomy_cache("default")

    token = agent_token_factory(["read", "write:taxonomy"])
    headers = {"Authorization": f"Bearer {token}"}
    resp = authed_client.put(
        "/api/v1/mcp/taxonomy",
        json={
            "primary_vocabulary": "topics",
            "vocabularies": {
                "topics": {"label": "Topics", "terms": ["News"]},
            },
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    on_disk = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert on_disk["required_fields"] == ["name", "status", "deck"]
    assert "required_fields" not in resp.json()


def test_mcp_taxonomy_tools_registered_in_openapi(client):
    resp = client.get("/api/openapi.json")
    assert resp.status_code == 200
    paths = resp.json().get("paths", {})

    assert "/api/v1/mcp/taxonomy" in paths
    assert "/api/v1/mcp/taxonomy/vocabularies/{key}" in paths
    assert "/api/v1/mcp/taxonomy/vocabularies/{key}/terms" in paths
    assert "/api/v1/mcp/taxonomy/primary" in paths

    assert paths["/api/v1/mcp/taxonomy"]["get"].get("operationId") == "get_taxonomy"
    assert paths["/api/v1/mcp/taxonomy"]["put"].get("operationId") == "replace_taxonomy"
    assert paths["/api/v1/mcp/taxonomy/vocabularies/{key}"]["put"].get(
        "operationId"
    ) == "upsert_vocabulary"
    assert paths["/api/v1/mcp/taxonomy/vocabularies/{key}"]["delete"].get(
        "operationId"
    ) == "delete_vocabulary"
    assert paths["/api/v1/mcp/taxonomy/vocabularies/{key}/terms"]["post"].get(
        "operationId"
    ) == "add_taxonomy_term"
    assert paths["/api/v1/mcp/taxonomy/vocabularies/{key}/terms"]["delete"].get(
        "operationId"
    ) == "remove_taxonomy_term"
    assert paths["/api/v1/mcp/taxonomy/primary"]["post"].get(
        "operationId"
    ) == "set_primary_vocabulary"
    assert "mcp" in paths["/api/v1/mcp/taxonomy"]["get"]["tags"]
