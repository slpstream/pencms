from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Dict, List
from routers.auth import get_current_user
from routers.mcp_tools import require_scope, resolve_mcp_site_id
from models.user import UserPublic
from models.menu import MenuItem, MenuItemCreate, MenuItemUpdate, ReorderItem, MenuSlot, MenuItemReplace
from services import menu_service

router = APIRouter(prefix="/api/v1", tags=["mcp"])

CREATE_MENU_ITEM_DOC = """Create a new menu item in a specific menu slot.

`item_create.menu` MUST equal the path `menu_slot`.

Target shapes (six UI types → five API types):
1) Page:  {"type":"content","content_slug":"about","content_type":"page"}
2) Post:  {"type":"content","content_slug":"my-article","content_type":"post"}
3) Category/term: {"type":"taxonomy","content_slug":"primary/Winter","url":"/category/winter/"}
4) System: {"type":"system","content_slug":"blog","url":"/category/"}
   (content_slug one of: home, blog, search, rss)
5) Custom: {"type":"custom","url":"https://example.com"}
6) Label:  {"type":"label"}

Depth max 2: top-level items or children of top-level only (no grandchildren).

Example create body (Page):
{"menu":"primary","label":"About","target":{"type":"content","content_slug":"about","content_type":"page"},"parent_id":null}

Example (Taxonomy — highest failure mode for agents):
{"menu":"primary","label":"Winter","target":{"type":"taxonomy","content_slug":"primary/Winter","url":"/category/winter/"}}

Example (System):
{"menu":"primary","label":"Archives","target":{"type":"system","content_slug":"blog","url":"/category/"}}
"""

UPDATE_MENU_ITEM_DOC = """Update an existing menu item in a slot (partial update).

When changing `target`, use the same five API target shapes as create.

Target shapes (six UI types → five API types):
1) Page:  {"type":"content","content_slug":"about","content_type":"page"}
2) Post:  {"type":"content","content_slug":"my-article","content_type":"post"}
3) Category/term: {"type":"taxonomy","content_slug":"primary/Winter","url":"/category/winter/"}
4) System: {"type":"system","content_slug":"blog","url":"/category/"}
   (content_slug one of: home, blog, search, rss)
5) Custom: {"type":"custom","url":"https://example.com"}
6) Label:  {"type":"label"}

Depth max 2: top-level items or children of top-level only (no grandchildren).

Example (change to Taxonomy):
{"label":"Winter","target":{"type":"taxonomy","content_slug":"primary/Winter","url":"/category/winter/"}}

Example (change to System):
{"label":"Search","target":{"type":"system","content_slug":"search","url":"/search/"}}
"""

REPLACE_MENU_SLOT_DOC = """Replace all menu items in a slot wholesale.

Each item uses the same five API target shapes as create. Optional `id` values
may be supplied so children can reference parents via `parent_id` in the same list.

Target shapes (six UI types → five API types):
1) Page:  {"type":"content","content_slug":"about","content_type":"page"}
2) Post:  {"type":"content","content_slug":"my-article","content_type":"post"}
3) Category/term: {"type":"taxonomy","content_slug":"primary/Winter","url":"/category/winter/"}
4) System: {"type":"system","content_slug":"blog","url":"/category/"}
   (content_slug one of: home, blog, search, rss)
5) Custom: {"type":"custom","url":"https://example.com"}
6) Label:  {"type":"label"}

Depth max 2: top-level items or children of top-level only (no grandchildren).

Example (Taxonomy + System mixed slot):
[
  {"label":"Winter","target":{"type":"taxonomy","content_slug":"primary/Winter","url":"/category/winter/"}},
  {"label":"Blog","target":{"type":"system","content_slug":"blog","url":"/category/"}}
]
"""

@router.get(
    "/mcp/menus",
    operation_id="list_menus",
    dependencies=[Depends(require_scope("read"))],
)
async def list_menus(
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, List[MenuItem]]:
    """List all menus and their contents for the active MCP site."""
    site_id = resolve_mcp_site_id(request)
    try:
        return await menu_service.list_menus(site_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list menus: {e}")

@router.get(
    "/mcp/menus/{menu_slot}",
    operation_id="list_menu_items",
    dependencies=[Depends(require_scope("read"))],
)
async def list_menu_items(
    menu_slot: MenuSlot,
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> List[MenuItem]:
    """List all menu items inside a specific menu slot (primary, secondary, footer)."""
    site_id = resolve_mcp_site_id(request)
    try:
        return await menu_service.get_menu_slot(menu_slot, site_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get menu slot {menu_slot}: {e}")

@router.post(
    "/mcp/menus/{menu_slot}/items",
    operation_id="create_menu_item",
    dependencies=[Depends(require_scope("write:menus"))],
    status_code=201,
    summary="Create a menu item",
    description=CREATE_MENU_ITEM_DOC,
)
async def create_menu_item(
    menu_slot: MenuSlot,
    item_create: MenuItemCreate,
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> MenuItem:
    if item_create.menu != menu_slot:
        raise HTTPException(status_code=400, detail="Slot path parameter and request body menu slot must match.")
    site_id = resolve_mcp_site_id(request)
    try:
        return await menu_service.create_menu_item(menu_slot, item_create, site_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create menu item: {e}")

create_menu_item.__doc__ = CREATE_MENU_ITEM_DOC

@router.put(
    "/mcp/menus/{menu_slot}/items/{item_id}",
    operation_id="update_menu_item",
    dependencies=[Depends(require_scope("write:menus"))],
    summary="Update a menu item",
    description=UPDATE_MENU_ITEM_DOC,
)
async def update_menu_item(
    menu_slot: MenuSlot,
    item_id: str,
    item_update: MenuItemUpdate,
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> MenuItem:
    site_id = resolve_mcp_site_id(request)
    try:
        return await menu_service.update_menu_item(menu_slot, item_id, item_update, site_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update menu item: {e}")

update_menu_item.__doc__ = UPDATE_MENU_ITEM_DOC

@router.delete(
    "/mcp/menus/{menu_slot}/items/{item_id}",
    operation_id="delete_menu_item",
    dependencies=[Depends(require_scope("write:menus"))],
    status_code=204,
)
async def delete_menu_item(
    menu_slot: MenuSlot,
    item_id: str,
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
):
    """Delete an existing menu item. Automatically deletes its children."""
    site_id = resolve_mcp_site_id(request)
    try:
        await menu_service.delete_menu_item(menu_slot, item_id, site_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete menu item: {e}")

@router.put(
    "/mcp/menus/{menu_slot}/reorder",
    operation_id="reorder_menu_items",
    dependencies=[Depends(require_scope("write:menus"))],
)
async def reorder_menu_items(
    menu_slot: MenuSlot,
    reorder_items: List[ReorderItem],
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> List[MenuItem]:
    """Reorder items within a slot.
    Enforces a maximum depth of 2 (only top-level items and their immediate children, with no grandchildren permitted).
    """
    site_id = resolve_mcp_site_id(request)
    try:
        return await menu_service.reorder_menu_items(menu_slot, reorder_items, site_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reorder menu items: {e}")

@router.delete(
    "/mcp/menus/{menu_slot}",
    operation_id="clear_menu_slot",
    dependencies=[Depends(require_scope("write:menus"))],
    status_code=204,
)
async def clear_menu_slot(
    menu_slot: MenuSlot,
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
):
    """Clear all menu items from a specific menu slot (primary, secondary, footer)."""
    site_id = resolve_mcp_site_id(request)
    try:
        await menu_service.clear_menu_slot(menu_slot, site_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear menu slot: {e}")

@router.put(
    "/mcp/menus/{menu_slot}",
    operation_id="replace_menu_slot",
    dependencies=[Depends(require_scope("write:menus"))],
    summary="Replace a menu slot",
    description=REPLACE_MENU_SLOT_DOC,
)
async def replace_menu_slot(
    menu_slot: MenuSlot,
    items: List[MenuItemReplace],
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> List[MenuItem]:
    site_id = resolve_mcp_site_id(request)
    try:
        return await menu_service.replace_menu_slot(menu_slot, items, site_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to replace menu slot: {e}")

replace_menu_slot.__doc__ = REPLACE_MENU_SLOT_DOC
