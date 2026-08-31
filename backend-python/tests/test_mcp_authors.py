import pytest


@pytest.fixture(autouse=True)
def clean_authors():
    import config

    path = config.CONTENT_DIR_PATH / "sites" / "default" / "authors.yaml"
    if path.exists():
        path.unlink()
    yield
    if path.exists():
        path.unlink()


@pytest.fixture
def agent_token_factory(authed_client):
    def _create(scopes):
        import secrets

        resp = authed_client.post(
            "/api/auth/keys",
            json={"name": f"author-{secrets.token_hex(4)}", "scopes": scopes},
        )
        assert resp.status_code == 200, resp.text
        raw_key = resp.json()["key"]

        resp = authed_client.post("/api/auth/token", json={"agent_key": raw_key})
        assert resp.status_code == 200, resp.text
        return resp.json()["access_token"]

    return _create


def test_unauthenticated_mcp_author_endpoints_rejected(client):
    assert client.get("/api/v1/mcp/authors").status_code == 401
    assert client.get("/api/v1/mcp/authors/jane-doe").status_code == 401
    assert client.post("/api/v1/mcp/authors", json={"name": "Jane"}).status_code == 401
    assert client.put("/api/v1/mcp/authors/jane-doe", json={"bio": "x"}).status_code == 401
    assert client.delete("/api/v1/mcp/authors/jane-doe").status_code == 401


def test_read_scoped_key_allowed_on_read_author_endpoints(
    authed_client, agent_token_factory
):
    token = agent_token_factory(["read"])
    headers = {"Authorization": f"Bearer {token}"}

    resp = authed_client.get("/api/v1/mcp/authors", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []

    resp = authed_client.get("/api/v1/mcp/authors/missing", headers=headers)
    assert resp.status_code == 404


def test_read_scoped_key_rejected_on_write_author_endpoints(
    authed_client, agent_token_factory
):
    token = agent_token_factory(["read"])
    headers = {"Authorization": f"Bearer {token}"}

    resp = authed_client.post(
        "/api/v1/mcp/authors",
        json={"name": "Jane Doe"},
        headers=headers,
    )
    assert resp.status_code == 403
    assert "lacks required scope: write:authors" in resp.json()["detail"]


def test_write_scoped_key_mcp_author_crud_flow(authed_client, agent_token_factory):
    write_token = agent_token_factory(["write", "read"])
    headers = {"Authorization": f"Bearer {write_token}"}

    # Create — slug derived from name
    resp = authed_client.post(
        "/api/v1/mcp/authors",
        json={"name": "Jane Doe", "bio": "Writer", "role": "Editor"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    author = resp.json()
    assert author["name"] == "Jane Doe"
    assert author["slug"] == "jane-doe"
    assert author["bio"] == "Writer"
    slug = author["slug"]

    # Get
    resp = authed_client.get(f"/api/v1/mcp/authors/{slug}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Jane Doe"

    # List
    resp = authed_client.get("/api/v1/mcp/authors", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["slug"] == slug

    # Partial update — slug immutable
    resp = authed_client.put(
        f"/api/v1/mcp/authors/{slug}",
        json={"bio": "Updated bio", "role": "Senior Editor"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    updated = resp.json()
    assert updated["slug"] == slug
    assert updated["bio"] == "Updated bio"
    assert updated["role"] == "Senior Editor"
    assert updated["name"] == "Jane Doe"

    # Delete
    resp = authed_client.delete(f"/api/v1/mcp/authors/{slug}", headers=headers)
    assert resp.status_code == 204

    resp = authed_client.get(f"/api/v1/mcp/authors/{slug}", headers=headers)
    assert resp.status_code == 404


def test_mcp_author_tools_registered_in_openapi(client):
    resp = client.get("/api/openapi.json")
    assert resp.status_code == 200
    openapi = resp.json()
    paths = openapi.get("paths", {})

    assert "/api/v1/mcp/authors" in paths
    assert "/api/v1/mcp/authors/{slug}" in paths
    assert "get" in paths["/api/v1/mcp/authors"]
    assert "post" in paths["/api/v1/mcp/authors"]
    assert "get" in paths["/api/v1/mcp/authors/{slug}"]
    assert "put" in paths["/api/v1/mcp/authors/{slug}"]
    assert "delete" in paths["/api/v1/mcp/authors/{slug}"]

    list_route = paths["/api/v1/mcp/authors"]["get"]
    assert "mcp" in list_route["tags"]
    assert list_route.get("operationId") == "list_authors"
    assert paths["/api/v1/mcp/authors"]["post"].get("operationId") == "create_author"
    assert paths["/api/v1/mcp/authors/{slug}"]["get"].get("operationId") == "get_author"
    assert paths["/api/v1/mcp/authors/{slug}"]["put"].get("operationId") == "update_author"
    assert (
        paths["/api/v1/mcp/authors/{slug}"]["delete"].get("operationId") == "delete_author"
    )
