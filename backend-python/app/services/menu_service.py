"""Per-site navigation menus stored as ``sites/{id}/menus.yaml``."""

from __future__ import annotations

import asyncio
from typing import Dict, List, Optional
from uuid import uuid4

import yaml
from models.menu import (
    MenuItem,
    MenuItemCreate,
    MenuItemUpdate,
    ReorderItem,
    MenuSlot,
    MenuItemReplace,
)
from services.site_service import DEFAULT_SITE_ID, site_menus_relpath

_file_lock = asyncio.Lock()


def sort_menu_tree(items: List[MenuItem]) -> List[MenuItem]:
    """Order a flat menu list as contiguous parent→children groups.

    ``order`` is sibling-scoped. A global sort by ``order`` alone interleaves
    children of different parents, which breaks adjacency-based Structure UIs.
    Returns roots (by sibling order), each followed by its children (by sibling
    order). Orphans (missing parent) are appended at the end as top-level.
    """
    by_id = {item.id: item for item in items}
    roots = sorted(
        [item for item in items if item.parent_id is None],
        key=lambda x: x.order,
    )
    children_by_parent: Dict[Optional[str], List[MenuItem]] = {}
    for item in items:
        if item.parent_id is not None:
            children_by_parent.setdefault(item.parent_id, []).append(item)

    flat: List[MenuItem] = []
    placed = set()
    for root in roots:
        flat.append(root)
        placed.add(root.id)
        kids = sorted(children_by_parent.get(root.id, []), key=lambda x: x.order)
        for child in kids:
            flat.append(child)
            placed.add(child.id)

    orphans = sorted(
        [item for item in items if item.id not in placed],
        key=lambda x: x.order,
    )
    for orphan in orphans:
        if orphan.parent_id is not None and orphan.parent_id not in by_id:
            orphan.parent_id = None
        flat.append(orphan)

    return flat


def _empty_menus() -> Dict[str, List[MenuItem]]:
    return {slot.value: [] for slot in MenuSlot}


def _parse_menus_data(data: dict) -> Dict[str, List[MenuItem]]:
    parsed_menus = {}
    for slot in MenuSlot:
        slot_data = data.get(slot.value, []) if isinstance(data, dict) else []
        if not isinstance(slot_data, list):
            slot_data = []
        items = []
        for item in slot_data:
            try:
                items.append(MenuItem.model_validate(item))
            except Exception:
                continue
        parsed_menus[slot.value] = sort_menu_tree(items)
    return parsed_menus


async def read_menus(site_id: str = DEFAULT_SITE_ID) -> Dict[str, List[MenuItem]]:
    """Read all menu slots for a site from ``menus.yaml``."""
    from config import content_storage

    rel = site_menus_relpath(site_id)
    async with _file_lock:
        try:
            if not await content_storage.exists(rel):
                return _empty_menus()
            raw = await content_storage.read(rel)
            data = yaml.safe_load(raw) or {}
        except Exception:
            return _empty_menus()
        return _parse_menus_data(data)


async def write_menus(
    menus: Dict[str, List[MenuItem]], site_id: str = DEFAULT_SITE_ID
) -> None:
    """Write all menu slots for a site to ``menus.yaml``."""
    from config import content_storage

    rel = site_menus_relpath(site_id)
    async with _file_lock:
        data_to_write = {}
        for slot in MenuSlot:
            sorted_items = sort_menu_tree(menus.get(slot.value, []))
            serialized_items = []
            for item in sorted_items:
                serialized = item.model_dump(mode="json")
                if serialized.get("labels") is None:
                    serialized.pop("labels", None)
                serialized_items.append(serialized)
            data_to_write[slot.value] = serialized_items
        text = yaml.safe_dump(
            data_to_write,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )
        parent = "/".join(rel.split("/")[:-1])
        if parent:
            await content_storage.mkdir(parent)
        await content_storage.write(rel, text)


async def list_menus(site_id: str = DEFAULT_SITE_ID) -> Dict[str, List[MenuItem]]:
    return await read_menus(site_id)


async def get_menu_slot(
    slot: MenuSlot, site_id: str = DEFAULT_SITE_ID
) -> List[MenuItem]:
    menus = await read_menus(site_id)
    return menus.get(slot.value, [])


async def create_menu_item(
    slot: MenuSlot,
    item_create: MenuItemCreate,
    site_id: str = DEFAULT_SITE_ID,
) -> MenuItem:
    menus = await read_menus(site_id)
    slot_items = menus.get(slot.value, [])

    if item_create.parent_id is not None:
        parent = next((x for x in slot_items if x.id == item_create.parent_id), None)
        if not parent:
            raise ValueError(
                f"Parent item '{item_create.parent_id}' does not exist in slot '{slot.value}'"
            )
        if parent.parent_id is not None:
            raise ValueError(
                "Nesting limit exceeded: Parent item is already a child. Max depth is 2."
            )

    siblings = [x for x in slot_items if x.parent_id == item_create.parent_id]
    order = item_create.order
    if order is None:
        order = max([x.order for x in siblings]) + 1 if siblings else 0

    new_item = MenuItem(
        menu=slot,
        label=item_create.label,
        labels=item_create.labels,
        target=item_create.target,
        parent_id=item_create.parent_id,
        order=order,
        open_in_new_tab=item_create.open_in_new_tab,
    )

    slot_items.append(new_item)
    menus[slot.value] = slot_items
    await write_menus(menus, site_id)
    return new_item


async def update_menu_item(
    slot: MenuSlot,
    item_id: str,
    item_update: MenuItemUpdate,
    site_id: str = DEFAULT_SITE_ID,
) -> MenuItem:
    menus = await read_menus(site_id)
    slot_items = menus.get(slot.value, [])

    item_index = next((i for i, x in enumerate(slot_items) if x.id == item_id), None)
    if item_index is None:
        raise KeyError(f"Menu item '{item_id}' not found in slot '{slot.value}'")

    existing_item = slot_items[item_index]
    fields_to_update = item_update.model_fields_set

    if "parent_id" in fields_to_update:
        new_parent_id = item_update.parent_id
        if new_parent_id == item_id:
            raise ValueError("A menu item cannot be its own parent.")

        if new_parent_id is not None:
            parent = next((x for x in slot_items if x.id == new_parent_id), None)
            if not parent:
                raise ValueError(
                    f"Parent item '{new_parent_id}' does not exist in slot '{slot.value}'"
                )
            if parent.parent_id is not None:
                raise ValueError(
                    "Nesting limit exceeded: Parent item is already a child. Max depth is 2."
                )

            has_children = any(x.parent_id == item_id for x in slot_items)
            if has_children:
                raise ValueError(
                    "Nesting limit exceeded: Cannot nest an item that has children. Max depth is 2."
                )

    updated_data = existing_item.model_dump()
    for field in fields_to_update:
        updated_data[field] = getattr(item_update, field)

    updated_item = MenuItem.model_validate(updated_data)
    slot_items[item_index] = updated_item
    menus[slot.value] = slot_items
    await write_menus(menus, site_id)
    return updated_item


async def delete_menu_item(
    slot: MenuSlot, item_id: str, site_id: str = DEFAULT_SITE_ID
) -> None:
    menus = await read_menus(site_id)
    slot_items = menus.get(slot.value, [])

    existing = next((x for x in slot_items if x.id == item_id), None)
    if not existing:
        raise KeyError(f"Menu item '{item_id}' not found in slot '{slot.value}'")

    new_slot_items = [x for x in slot_items if x.id != item_id and x.parent_id != item_id]
    menus[slot.value] = new_slot_items
    await write_menus(menus, site_id)


async def reorder_menu_items(
    slot: MenuSlot,
    reorder_items: List[ReorderItem],
    site_id: str = DEFAULT_SITE_ID,
) -> List[MenuItem]:
    menus = await read_menus(site_id)
    slot_items = menus.get(slot.value, [])

    item_map = {x.id: x for x in slot_items}

    for reorder in reorder_items:
        if reorder.id not in item_map:
            raise KeyError(f"Menu item '{reorder.id}' not found in slot '{slot.value}'")

    virtual_parents = {}
    for item in slot_items:
        virtual_parents[item.id] = item.parent_id

    for reorder in reorder_items:
        virtual_parents[reorder.id] = reorder.parent_id

    for item_id, parent_id in virtual_parents.items():
        if parent_id is not None:
            if parent_id == item_id:
                raise ValueError(f"Menu item '{item_id}' cannot be its own parent.")
            if parent_id not in virtual_parents:
                raise ValueError(f"Parent item '{parent_id}' does not exist.")

            parent_parent_id = virtual_parents[parent_id]
            if parent_parent_id is not None:
                raise ValueError(
                    f"Nesting limit exceeded: Item '{item_id}' is nested under '{parent_id}', "
                    f"which is itself nested under '{parent_parent_id}'. Max depth is 2."
                )

    for reorder in reorder_items:
        item = item_map[reorder.id]
        item.parent_id = reorder.parent_id
        item.order = reorder.order

    slot_items = sort_menu_tree(slot_items)
    menus[slot.value] = slot_items
    await write_menus(menus, site_id)
    return slot_items


async def clear_menu_slot(slot: MenuSlot, site_id: str = DEFAULT_SITE_ID) -> None:
    menus = await read_menus(site_id)
    menus[slot.value] = []
    await write_menus(menus, site_id)


async def replace_menu_slot(
    slot: MenuSlot,
    items: List[MenuItemReplace],
    site_id: str = DEFAULT_SITE_ID,
) -> List[MenuItem]:
    menus = await read_menus(site_id)

    final_items: List[MenuItem] = []
    seen_ids = set()
    for idx, item in enumerate(items):
        if item.id:
            if item.id in seen_ids:
                raise ValueError(
                    f"Duplicate menu item ID '{item.id}' found in replace payload."
                )
            seen_ids.add(item.id)

        item_id = item.id if item.id else str(uuid4())
        if not item.id:
            seen_ids.add(item_id)

        order = item.order if item.order is not None else idx
        final_items.append(
            MenuItem(
                id=item_id,
                menu=slot,
                label=item.label,
                labels=item.labels,
                target=item.target,
                parent_id=item.parent_id,
                order=order,
                open_in_new_tab=item.open_in_new_tab,
            )
        )

    virtual_parents = {item.id: item.parent_id for item in final_items}

    for item in final_items:
        parent_id = item.parent_id
        if parent_id is not None:
            if parent_id == item.id:
                raise ValueError(f"Menu item '{item.id}' cannot be its own parent.")
            if parent_id not in virtual_parents:
                raise ValueError(
                    f"Parent item '{parent_id}' does not exist in the new items list."
                )

            parent_parent_id = virtual_parents[parent_id]
            if parent_parent_id is not None:
                raise ValueError(
                    f"Nesting limit exceeded: Item '{item.id}' is nested under '{parent_id}', "
                    f"which is itself nested under '{parent_parent_id}'. Max depth is 2."
                )

    final_items = sort_menu_tree(final_items)
    menus[slot.value] = final_items
    await write_menus(menus, site_id)
    return final_items
