from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, List
from routers.auth import get_current_user, UserPublic
from models.menu import MenuItem, MenuItemCreate, MenuItemUpdate, ReorderItem, MenuSlot
from services import menu_service
from services.authz import require_capability
from services.site_service import resolve_human_site_id

router = APIRouter(prefix="/menus", tags=["menus"])

@router.get("", response_model=Dict[str, List[MenuItem]])
async def get_all_menus(
    current_user: UserPublic = Depends(get_current_user),
    site_id: str = Depends(resolve_human_site_id),
):
    """List all menus for the active site."""
    try:
        return await menu_service.list_menus(site_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list menus: {e}")

@router.get("/{menu_slot}", response_model=List[MenuItem])
async def get_menu_slot(
    menu_slot: MenuSlot,
    current_user: UserPublic = Depends(get_current_user),
    site_id: str = Depends(resolve_human_site_id),
):
    """List items for one menu slot."""
    try:
        return await menu_service.get_menu_slot(menu_slot, site_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get menu slot {menu_slot}: {e}")

@router.post("/{menu_slot}/items", response_model=MenuItem, status_code=201)
async def create_menu_item(
    menu_slot: MenuSlot,
    item_create: MenuItemCreate,
    current_user: UserPublic = Depends(require_capability("write:menus")),
    site_id: str = Depends(resolve_human_site_id),
):
    """Create a new menu item in a slot.

    `item_create.menu` must equal path `menu_slot`. Depth max 2.
    Target types: content (page/post), taxonomy, system (home|blog|search|rss), custom, label.
    """
    if item_create.menu != menu_slot:
        raise HTTPException(status_code=400, detail="Slot path parameter and request body menu slot must match.")
    try:
        return await menu_service.create_menu_item(menu_slot, item_create, site_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create menu item: {e}")

@router.put("/{menu_slot}/items/{item_id}", response_model=MenuItem)
async def update_menu_item(
    menu_slot: MenuSlot,
    item_id: str,
    item_update: MenuItemUpdate,
    current_user: UserPublic = Depends(require_capability("write:menus")),
    site_id: str = Depends(resolve_human_site_id),
):
    """Update an existing menu item in a slot.

    Depth max 2. Same five target types as create (content, taxonomy, system, custom, label).
    """
    try:
        return await menu_service.update_menu_item(menu_slot, item_id, item_update, site_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update menu item: {e}")

@router.delete("/{menu_slot}/items/{item_id}", status_code=204)
async def delete_menu_item(
    menu_slot: MenuSlot,
    item_id: str,
    current_user: UserPublic = Depends(require_capability("write:menus")),
    site_id: str = Depends(resolve_human_site_id),
):
    """Delete a menu item."""
    try:
        await menu_service.delete_menu_item(menu_slot, item_id, site_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete menu item: {e}")

@router.put("/{menu_slot}/reorder", response_model=List[MenuItem])
async def reorder_menu_items(
    menu_slot: MenuSlot,
    reorder_items: List[ReorderItem],
    current_user: UserPublic = Depends(require_capability("write:menus")),
    site_id: str = Depends(resolve_human_site_id),
):
    """Bulk reorder menu items."""
    try:
        return await menu_service.reorder_menu_items(menu_slot, reorder_items, site_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reorder menu items: {e}")

@router.delete("/{menu_slot}", status_code=204)
async def clear_menu_slot(
    menu_slot: MenuSlot,
    current_user: UserPublic = Depends(require_capability("write:menus")),
    site_id: str = Depends(resolve_human_site_id),
):
    """Clear all menu items from a specific menu slot."""
    try:
        await menu_service.clear_menu_slot(menu_slot, site_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear menu slot: {e}")
