/**
 * Shared flat Alpine ↔ nested API menu item conversion.
 * Used by settings-navigation.js (save) and ai-sidebar-navigation.js (AI prompt).
 */
(function (global) {
  "use strict";

  /**
   * Convert a flat UI item into the nested API MenuItemCreate / update payload shape.
   *
   * @param {string} slot - primary | secondary | footer
   * @param {object} flatItem - Alpine flat fields (target_type, content_slug, …)
   * @param {string|null} [parentId] - override parent_id; if omitted uses flatItem.parent_id
   * @returns {object}
   */
  function toApiItem(slot, flatItem, parentId) {
    const resolvedParent =
      parentId !== undefined
        ? parentId
        : flatItem.parent_id != null
          ? flatItem.parent_id
          : null;

    const payload = {
      menu: slot,
      label: flatItem.label,
      target: { type: flatItem.target_type || "label" },
      parent_id: resolvedParent,
      open_in_new_tab: !!flatItem.open_in_new_tab,
    };

    if (flatItem.id != null && flatItem.id !== "") {
      payload.id = flatItem.id;
    }
    if (flatItem.order != null) {
      payload.order = flatItem.order;
    }

    if (flatItem.target_type === "content") {
      payload.target.content_slug = flatItem.content_slug || "";
      payload.target.content_type =
        flatItem.content_type === "post" ? "post" : "page";
    } else if (flatItem.target_type === "custom") {
      payload.target.url = flatItem.url || "";
    } else if (
      flatItem.target_type === "taxonomy" ||
      flatItem.target_type === "system"
    ) {
      payload.target.content_slug = flatItem.content_slug || "";
      payload.target.url = flatItem.url || "";
    }

    return payload;
  }

  /**
   * Flatten a nested API MenuItem into Alpine UI fields.
   *
   * @param {object} apiItem
   * @returns {object}
   */
  function fromApiItem(apiItem) {
    const target = apiItem.target || {};
    return {
      id: apiItem.id,
      label: apiItem.label,
      parent_id: apiItem.parent_id || null,
      order: apiItem.order,
      open_in_new_tab: apiItem.open_in_new_tab || false,
      target_type: target.type || "label",
      content_slug: target.content_slug || "",
      content_type: target.content_type || "page",
      url: target.url || "",
    };
  }

  /**
   * Convert all slots of flat Alpine menus into nested API shape for prompts / APIs.
   *
   * @param {Record<string, object[]>} menus
   * @returns {Record<string, object[]>}
   */
  function menusToApiShape(menus) {
    const out = {};
    for (const slot of ["primary", "secondary", "footer"]) {
      out[slot] = (menus[slot] || []).map((item) =>
        toApiItem(slot, item, item.parent_id || null)
      );
    }
    return out;
  }

  global.PenMenuItemShape = {
    toApiItem,
    fromApiItem,
    menusToApiShape,
  };
})(typeof window !== "undefined" ? window : globalThis);
