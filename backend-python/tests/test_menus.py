import pytest
from models.menu import MenuSlot, MenuItemCreate, MenuItemUpdate, ReorderItem
from services import menu_service

@pytest.fixture(autouse=True)
def clean_menus():
    import config
    path = config.CONTENT_DIR_PATH / "sites" / "default" / "menus.yaml"
    if path.exists():
        path.unlink()
    yield
    if path.exists():
        path.unlink()

# --- Pydantic model validation tests ---

def test_pydantic_target_validation():
    # Valid content target
    item = MenuItemCreate(
        menu=MenuSlot.primary,
        label="Home",
        target={"type": "content", "content_slug": "home-page", "content_type": "page"}
    )
    assert item.target.type == "content"
    assert item.target.content_slug == "home-page"

    localized = MenuItemCreate(
        menu=MenuSlot.primary,
        label="Home",
        labels={"FR": "Accueil", "pt_BR": "Início"},
        target={"type": "system", "content_slug": "home"},
    )
    assert localized.labels == {"fr": "Accueil", "pt-br": "Início"}

    with pytest.raises(ValueError, match="must be non-empty"):
        MenuItemCreate(
            menu=MenuSlot.primary,
            label="Home",
            labels={"fr": "  "},
            target={"type": "system", "content_slug": "home"},
        )

    # Valid custom target
    item = MenuItemCreate(
        menu=MenuSlot.primary,
        label="External",
        target={"type": "custom", "url": "https://google.com"}
    )
    assert item.target.type == "custom"
    assert item.target.url == "https://google.com"

    # Valid label target
    item = MenuItemCreate(
        menu=MenuSlot.primary,
        label="Separator",
        target={"type": "label"}
    )
    assert item.target.type == "label"

    # Invalid target type
    with pytest.raises(ValueError):
        MenuItemCreate(
            menu=MenuSlot.primary,
            label="Invalid",
            target={"type": "unknown"}
        )


# --- Service layer tests ---

@pytest.mark.asyncio
async def test_service_crud_and_nesting():
    # 1. Clean list
    menus = await menu_service.list_menus()
    assert menus == {"primary": [], "secondary": [], "footer": []}

    # 2. Create a top-level item
    item1 = await menu_service.create_menu_item(
        MenuSlot.primary,
        MenuItemCreate(
            menu=MenuSlot.primary,
            label="About",
            labels={"fr": "À propos"},
            target={"type": "content", "content_slug": "about-us", "content_type": "page"}
        )
    )
    assert item1.parent_id is None
    assert item1.order == 0
    assert item1.labels == {"fr": "À propos"}

    # 3. Create another top-level item, check relative order
    item2 = await menu_service.create_menu_item(
        MenuSlot.primary,
        MenuItemCreate(
            menu=MenuSlot.primary,
            label="Contact",
            target={"type": "content", "content_slug": "contact", "content_type": "page"}
        )
    )
    assert item2.order == 1

    # 4. Create nested item (depth 2 - valid)
    child = await menu_service.create_menu_item(
        MenuSlot.primary,
        MenuItemCreate(
            menu=MenuSlot.primary,
            label="History",
            target={"type": "content", "content_slug": "history", "content_type": "page"},
            parent_id=item1.id
        )
    )
    assert child.parent_id == item1.id
    assert child.order == 0

    # 5. Try creating a third level item (depth 3 - should fail)
    with pytest.raises(ValueError, match="Nesting limit exceeded"):
        await menu_service.create_menu_item(
            MenuSlot.primary,
            MenuItemCreate(
                menu=MenuSlot.primary,
                label="Sub-History",
                target={"type": "label"},
                parent_id=child.id
            )
        )

    # 6. Try nesting under nonexistent parent
    with pytest.raises(ValueError, match="does not exist"):
        await menu_service.create_menu_item(
            MenuSlot.primary,
            MenuItemCreate(
                menu=MenuSlot.primary,
                label="Orphan",
                target={"type": "label"},
                parent_id="nonexistent-id"
            )
        )

    # 7. Update parent validation: changing top-level to child when it has children
    with pytest.raises(ValueError, match="Nesting limit exceeded"):
        await menu_service.update_menu_item(
            MenuSlot.primary,
            item1.id,
            MenuItemUpdate(parent_id=item2.id)
        )

    # 8. Valid update
    updated = await menu_service.update_menu_item(
        MenuSlot.primary,
        child.id,
        MenuItemUpdate(label="Our History")
    )
    assert updated.label == "Our History"

    # 9. Delete cascade: deleting item1 should delete child too
    await menu_service.delete_menu_item(MenuSlot.primary, item1.id)
    slot_items = await menu_service.get_menu_slot(MenuSlot.primary)
    assert len(slot_items) == 1
    assert slot_items[0].id == item2.id


@pytest.mark.asyncio
async def test_service_round_trips_sparse_localized_labels_without_legacy_noise():
    import config
    import yaml

    localized = await menu_service.create_menu_item(
        MenuSlot.primary,
        MenuItemCreate(
            menu=MenuSlot.primary,
            label="Home",
            labels={"fr": "Accueil"},
            target={"type": "system", "content_slug": "home"},
        ),
    )
    await menu_service.create_menu_item(
        MenuSlot.footer,
        MenuItemCreate(
            menu=MenuSlot.footer,
            label="External",
            target={"type": "custom", "url": "https://example.test"},
        ),
    )

    reread = await menu_service.get_menu_slot(MenuSlot.primary)
    assert reread[0].id == localized.id
    assert reread[0].labels == {"fr": "Accueil"}

    path = config.CONTENT_DIR_PATH / "sites" / "default" / "menus.yaml"
    raw = yaml.safe_load(path.read_text())
    assert raw["primary"][0]["labels"] == {"fr": "Accueil"}
    assert "labels" not in raw["footer"][0]


@pytest.mark.asyncio
async def test_service_bulk_reorder():
    # Setup some items
    item1 = await menu_service.create_menu_item(
        MenuSlot.secondary,
        MenuItemCreate(menu=MenuSlot.secondary, label="One", target={"type": "label"})
    )
    item2 = await menu_service.create_menu_item(
        MenuSlot.secondary,
        MenuItemCreate(menu=MenuSlot.secondary, label="Two", target={"type": "label"})
    )

    # Perform bulk reorder
    reordered = await menu_service.reorder_menu_items(
        MenuSlot.secondary,
        [
            ReorderItem(id=item1.id, parent_id=None, order=1),
            ReorderItem(id=item2.id, parent_id=None, order=0)
        ]
    )
    assert reordered[0].id == item2.id
    assert reordered[1].id == item1.id

    # Check depth enforcement in bulk reorder (cycle/3rd level)
    child = await menu_service.create_menu_item(
        MenuSlot.secondary,
        MenuItemCreate(menu=MenuSlot.secondary, label="Child", target={"type": "label"}, parent_id=item1.id)
    )

    # Nesting parent under child (invalid)
    with pytest.raises(ValueError, match="Nesting limit exceeded"):
        await menu_service.reorder_menu_items(
            MenuSlot.secondary,
            [
                ReorderItem(id=item1.id, parent_id=child.id, order=0)
            ]
        )


@pytest.mark.asyncio
async def test_sibling_scoped_order_keeps_children_contiguous():
    """AI/MCP creates assign sibling-scoped order; list must not interleave families."""
    info = await menu_service.create_menu_item(
        MenuSlot.footer,
        MenuItemCreate(menu=MenuSlot.footer, label="Information", target={"type": "label"}),
    )
    categories = await menu_service.create_menu_item(
        MenuSlot.footer,
        MenuItemCreate(menu=MenuSlot.footer, label="Categories", target={"type": "label"}),
    )
    about = await menu_service.create_menu_item(
        MenuSlot.footer,
        MenuItemCreate(
            menu=MenuSlot.footer,
            label="About",
            target={"type": "label"},
            parent_id=info.id,
        ),
    )
    summer = await menu_service.create_menu_item(
        MenuSlot.footer,
        MenuItemCreate(
            menu=MenuSlot.footer,
            label="Summer",
            target={"type": "label"},
            parent_id=categories.id,
        ),
    )
    terms = await menu_service.create_menu_item(
        MenuSlot.footer,
        MenuItemCreate(
            menu=MenuSlot.footer,
            label="Terms",
            target={"type": "label"},
            parent_id=info.id,
        ),
    )
    winter = await menu_service.create_menu_item(
        MenuSlot.footer,
        MenuItemCreate(
            menu=MenuSlot.footer,
            label="Winter",
            target={"type": "label"},
            parent_id=categories.id,
        ),
    )

    # Sibling orders restart per parent (the interleaving bug trigger).
    assert about.order == 0 and summer.order == 0
    assert terms.order == 1 and winter.order == 1

    slot = await menu_service.get_menu_slot(MenuSlot.footer)
    labels = [item.label for item in slot]
    # Contiguous parent→children, not global-order interleave
    # (Information, About, Summer, Categories, Terms, Winter).
    assert labels == [
        "Information",
        "About",
        "Terms",
        "Categories",
        "Summer",
        "Winter",
    ]


def test_sort_menu_tree_unit():
    from models.menu import MenuItem
    from services.menu_service import sort_menu_tree

    a = MenuItem(menu=MenuSlot.footer, label="A", target={"type": "label"}, order=0)
    b = MenuItem(menu=MenuSlot.footer, label="B", target={"type": "label"}, order=1)
    a0 = MenuItem(
        menu=MenuSlot.footer,
        label="A0",
        target={"type": "label"},
        parent_id=a.id,
        order=0,
    )
    b0 = MenuItem(
        menu=MenuSlot.footer,
        label="B0",
        target={"type": "label"},
        parent_id=b.id,
        order=0,
    )
    # Deliberately interleaved like a global order sort would produce
    interleaved = [a, a0, b0, b]
    assert [x.label for x in sort_menu_tree(interleaved)] == ["A", "A0", "B", "B0"]


# --- REST API Endpoint tests ---

def test_api_menus_authentication(client):
    # Unauthenticated requests should be rejected
    assert client.get("/api/menus").status_code == 401
    assert client.get("/api/menus/primary").status_code == 401
    assert client.post("/api/menus/primary/items", json={}).status_code == 401
    assert client.put("/api/menus/primary/items/some-id", json={}).status_code == 401
    assert client.delete("/api/menus/primary/items/some-id").status_code == 401
    assert client.put("/api/menus/primary/reorder", json=[]).status_code == 401
    assert client.delete("/api/menus/primary").status_code == 401


def test_api_menus_crud_flow(authed_client):
    # 1. Fetch empty list
    resp = authed_client.get("/api/menus")
    assert resp.status_code == 200
    assert resp.json() == {"primary": [], "secondary": [], "footer": []}

    # 2. Create item
    payload = {
        "menu": "primary",
        "label": "About",
        "target": {"type": "content", "content_slug": "about", "content_type": "page"}
    }
    resp = authed_client.post("/api/menus/primary/items", json=payload)
    assert resp.status_code == 201
    item = resp.json()
    assert item["label"] == "About"
    assert item["order"] == 0
    assert item["parent_id"] is None
    item_id = item["id"]

    # 3. Fetch slot items
    resp = authed_client.get("/api/menus/primary")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["id"] == item_id

    # 4. Create child item
    child_payload = {
        "menu": "primary",
        "label": "Mission",
        "target": {"type": "custom", "url": "/mission"},
        "parent_id": item_id
    }
    resp = authed_client.post("/api/menus/primary/items", json=child_payload)
    assert resp.status_code == 201
    child_item = resp.json()
    assert child_item["parent_id"] == item_id
    child_id = child_item["id"]

    # 5. Invalid create (exceed depth)
    grandchild_payload = {
        "menu": "primary",
        "label": "Fail",
        "target": {"type": "label"},
        "parent_id": child_id
    }
    resp = authed_client.post("/api/menus/primary/items", json=grandchild_payload)
    assert resp.status_code == 400
    assert "Nesting limit exceeded" in resp.json()["detail"]

    # 6. Update item
    update_payload = {
        "label": "About Us"
    }
    resp = authed_client.put(f"/api/menus/primary/items/{item_id}", json=update_payload)
    assert resp.status_code == 200
    assert resp.json()["label"] == "About Us"

    # 7. Reorder items
    reorder_payload = [
        {"id": item_id, "parent_id": None, "order": 1},
        {"id": child_id, "parent_id": None, "order": 0}  # Move child to top level, order 0
    ]
    resp = authed_client.put("/api/menus/primary/reorder", json=reorder_payload)
    assert resp.status_code == 200
    reordered = resp.json()
    assert reordered[0]["id"] == child_id
    assert reordered[0]["parent_id"] is None
    assert reordered[1]["id"] == item_id

    # 8. Delete item
    resp = authed_client.delete(f"/api/menus/primary/items/{item_id}")
    assert resp.status_code == 204

    # Verify deleted
    resp = authed_client.get("/api/menus/primary")
    assert resp.status_code == 200
    assert len(resp.json()) == 1  # only child_id remains (item_id deleted)
    assert resp.json()[0]["id"] == child_id


def test_api_menus_clear_slot(authed_client):
    # Seed items in primary and secondary
    for slot, label in (("primary", "Home"), ("secondary", "About")):
        resp = authed_client.post(f"/api/menus/{slot}/items", json={
            "menu": slot,
            "label": label,
            "target": {"type": "content", "content_slug": label.lower(), "content_type": "page"}
        })
        assert resp.status_code == 201

    # Clear primary only
    resp = authed_client.delete("/api/menus/primary")
    assert resp.status_code == 204

    resp = authed_client.get("/api/menus/primary")
    assert resp.status_code == 200
    assert resp.json() == []

    # Secondary untouched
    resp = authed_client.get("/api/menus/secondary")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
