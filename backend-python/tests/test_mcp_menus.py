import pytest

@pytest.fixture(autouse=True)
def clean_menus():
    import config
    path = config.CONTENT_DIR_PATH / "sites" / "default" / "menus.yaml"
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
            json={"name": f"menu-{secrets.token_hex(4)}", "scopes": scopes},
        )
        assert resp.status_code == 200, resp.text
        raw_key = resp.json()["key"]

        resp = authed_client.post("/api/auth/token", json={"agent_key": raw_key})
        assert resp.status_code == 200, resp.text
        return resp.json()["access_token"]

    return _create


def test_unauthenticated_mcp_endpoints_rejected(client):
    # No cookies or Bearer headers -> 401
    assert client.get("/api/v1/mcp/menus").status_code == 401
    assert client.get("/api/v1/mcp/menus/primary").status_code == 401
    assert client.post("/api/v1/mcp/menus/primary/items", json={}).status_code == 401
    assert client.put("/api/v1/mcp/menus/primary/items/some-id", json={}).status_code == 401
    assert client.delete("/api/v1/mcp/menus/primary/items/some-id").status_code == 401
    assert client.put("/api/v1/mcp/menus/primary/reorder", json=[]).status_code == 401


def test_read_scoped_key_allowed_on_read_endpoints(authed_client, agent_token_factory):
    token = agent_token_factory(["read"])
    headers = {"Authorization": f"Bearer {token}"}

    # GET all menus
    resp = authed_client.get("/api/v1/mcp/menus", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == {"primary": [], "secondary": [], "footer": []}

    # GET primary menu
    resp = authed_client.get("/api/v1/mcp/menus/primary", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


def test_read_scoped_key_rejected_on_write_endpoints(authed_client, agent_token_factory):
    token = agent_token_factory(["read"])
    headers = {"Authorization": f"Bearer {token}"}

    # Try creating an item
    payload = {
        "menu": "primary",
        "label": "About",
        "target": {"type": "content", "content_slug": "about", "content_type": "page"}
    }
    resp = authed_client.post("/api/v1/mcp/menus/primary/items", json=payload, headers=headers)
    assert resp.status_code == 403
    assert "lacks required scope: write:menus" in resp.json()["detail"]


def test_write_scoped_key_mcp_crud_flow(authed_client, agent_token_factory):
    write_token = agent_token_factory(["write", "read"])
    headers = {"Authorization": f"Bearer {write_token}"}

    # 1. Create a menu item
    payload = {
        "menu": "primary",
        "label": "About",
        "target": {"type": "content", "content_slug": "about", "content_type": "page"}
    }
    resp = authed_client.post("/api/v1/mcp/menus/primary/items", json=payload, headers=headers)
    assert resp.status_code == 201
    item = resp.json()
    assert item["label"] == "About"
    item_id = item["id"]

    # 2. Create child item
    child_payload = {
        "menu": "primary",
        "label": "History",
        "target": {"type": "label"},
        "parent_id": item_id
    }
    resp = authed_client.post("/api/v1/mcp/menus/primary/items", json=child_payload, headers=headers)
    assert resp.status_code == 201
    child_id = resp.json()["id"]

    # 3. Fail depth limit check (3rd level)
    fail_payload = {
        "menu": "primary",
        "label": "Fail",
        "target": {"type": "label"},
        "parent_id": child_id
    }
    resp = authed_client.post("/api/v1/mcp/menus/primary/items", json=fail_payload, headers=headers)
    assert resp.status_code == 400
    assert "Nesting limit exceeded" in resp.json()["detail"]

    # 4. Update the item
    update_payload = {
        "label": "About Us"
    }
    resp = authed_client.put(f"/api/v1/mcp/menus/primary/items/{item_id}", json=update_payload, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["label"] == "About Us"

    # 5. Bulk reorder items
    reorder_payload = [
        {"id": item_id, "parent_id": None, "order": 1},
        {"id": child_id, "parent_id": None, "order": 0}
    ]
    resp = authed_client.put("/api/v1/mcp/menus/primary/reorder", json=reorder_payload, headers=headers)
    assert resp.status_code == 200
    reordered = resp.json()
    assert reordered[0]["id"] == child_id
    assert reordered[0]["parent_id"] is None

    # 6. Delete item
    resp = authed_client.delete(f"/api/v1/mcp/menus/primary/items/{item_id}", headers=headers)
    assert resp.status_code == 204

    # Verify deleted on read endpoint
    resp = authed_client.get("/api/v1/mcp/menus/primary", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["id"] == child_id


def test_clear_menu_slot(authed_client, agent_token_factory):
    write_token = agent_token_factory(["write", "read"])
    headers = {"Authorization": f"Bearer {write_token}"}

    # 1. Create a menu item
    payload = {
        "menu": "primary",
        "label": "About",
        "target": {"type": "content", "content_slug": "about", "content_type": "page"}
    }
    resp = authed_client.post("/api/v1/mcp/menus/primary/items", json=payload, headers=headers)
    assert resp.status_code == 201

    # Verify item exists
    resp = authed_client.get("/api/v1/mcp/menus/primary", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # 2. Clear the slot
    resp = authed_client.delete("/api/v1/mcp/menus/primary", headers=headers)
    assert resp.status_code == 204

    # Verify slot is empty
    resp = authed_client.get("/api/v1/mcp/menus/primary", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 0


def test_replace_menu_slot_success(authed_client, agent_token_factory):
    write_token = agent_token_factory(["write", "read"])
    headers = {"Authorization": f"Bearer {write_token}"}

    # Populate the slot with wholesale replacement
    payload = [
        {
            "id": "parent-1",
            "label": "Home",
            "target": {"type": "custom", "url": "/"}
        },
        {
            "id": "child-1",
            "label": "Inner Page",
            "target": {"type": "content", "content_slug": "inner", "content_type": "page"},
            "parent_id": "parent-1"
        }
    ]
    resp = authed_client.put("/api/v1/mcp/menus/primary", json=payload, headers=headers)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2
    assert items[0]["id"] == "parent-1"
    assert items[1]["id"] == "child-1"
    assert items[1]["parent_id"] == "parent-1"


def test_replace_menu_slot_validation(authed_client, agent_token_factory):
    write_token = agent_token_factory(["write", "read"])
    headers = {"Authorization": f"Bearer {write_token}"}

    # 1. Depth violation (3 levels)
    payload_depth = [
        {
            "id": "l1",
            "label": "L1",
            "target": {"type": "label"}
        },
        {
            "id": "l2",
            "label": "L2",
            "target": {"type": "label"},
            "parent_id": "l1"
        },
        {
            "id": "l3",
            "label": "L3",
            "target": {"type": "label"},
            "parent_id": "l2"
        }
    ]
    resp = authed_client.put("/api/v1/mcp/menus/primary", json=payload_depth, headers=headers)
    assert resp.status_code == 400
    assert "Nesting limit exceeded" in resp.json()["detail"]

    # 2. Self-parenting
    payload_self = [
        {
            "id": "self",
            "label": "Self",
            "target": {"type": "label"},
            "parent_id": "self"
        }
    ]
    resp = authed_client.put("/api/v1/mcp/menus/primary", json=payload_self, headers=headers)
    assert resp.status_code == 400
    assert "cannot be its own parent" in resp.json()["detail"]

    # 3. Duplicate IDs in the replace payload
    payload_dup = [
        {
            "id": "dup-id",
            "label": "Duplicate 1",
            "target": {"type": "label"}
        },
        {
            "id": "dup-id",
            "label": "Duplicate 2",
            "target": {"type": "label"}
        }
    ]
    resp = authed_client.put("/api/v1/mcp/menus/primary", json=payload_dup, headers=headers)
    assert resp.status_code == 400
    assert "Duplicate menu item ID" in resp.json()["detail"]



def test_mcp_tools_registered_in_openapi(client):
    resp = client.get("/api/openapi.json")
    assert resp.status_code == 200
    openapi = resp.json()
    paths = openapi.get("paths", {})
    
    assert "/api/v1/mcp/menus" in paths
    assert "/api/v1/mcp/menus/{menu_slot}" in paths
    assert "delete" in paths["/api/v1/mcp/menus/{menu_slot}"]
    assert "put" in paths["/api/v1/mcp/menus/{menu_slot}"]
    assert "/api/v1/mcp/menus/{menu_slot}/items" in paths
    assert "/api/v1/mcp/menus/{menu_slot}/items/{item_id}" in paths
    assert "/api/v1/mcp/menus/{menu_slot}/reorder" in paths
    
    get_menus_route = paths["/api/v1/mcp/menus"]["get"]
    assert "mcp" in get_menus_route["tags"]
