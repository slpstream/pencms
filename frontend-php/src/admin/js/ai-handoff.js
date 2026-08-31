/**
 * Concierge Tier 2 — cross-surface AI handoff tokens (sessionStorage, TTL'd).
 * Loaded before ai-sidebar*.js on editor / navigation / customize pages.
 */
(function (global) {
  "use strict";

  const STORAGE_BASE = "pen_ai_handoff";
  const TTL_MS = 10 * 60 * 1000;
  const SURFACES = ["editor", "navigation", "customize"];
  const MENU_SLOTS = ["primary", "secondary", "footer"];
  const MAX_GOAL = 280;
  const MAX_NOTE = 160;
  const MAX_FACT_STR = 200;

  const SURFACE_LABELS = {
    editor: "Content Editor",
    navigation: "Navigation",
    customize: "Customize",
  };

  const FACT_KEYS = ["slug", "menu_slot", "theme_path", "note"];

  function siteKey(siteId) {
    return `${STORAGE_BASE}:${siteId || "default"}`;
  }

  function clampStr(value, max) {
    const s = String(value == null ? "" : value).trim();
    if (!s) return "";
    return s.length > max ? s.slice(0, max) : s;
  }

  /**
   * @param {unknown} payload
   * @returns {{ ok: true, token: object } | { ok: false, error: string }}
   */
  function validateAndNormalize(payload) {
    if (!payload || typeof payload !== "object") {
      return { ok: false, error: "Invalid handoff payload." };
    }
    const from = payload.from;
    const to = payload.to;
    if (!SURFACES.includes(from)) {
      return { ok: false, error: `Invalid from surface: ${from}` };
    }
    if (!SURFACES.includes(to)) {
      return { ok: false, error: `Invalid to surface: ${to}` };
    }
    if (from === to) {
      return { ok: false, error: "Handoff to must differ from the current surface." };
    }
    const goal = clampStr(payload.goal, MAX_GOAL);
    if (!goal) {
      return { ok: false, error: "goal is required." };
    }

    const factsIn =
      payload.facts && typeof payload.facts === "object" ? payload.facts : {};
    const facts = {};
    for (const key of Object.keys(factsIn)) {
      if (!FACT_KEYS.includes(key)) {
        return { ok: false, error: `Unknown facts key: ${key}` };
      }
    }
    if (factsIn.slug != null && String(factsIn.slug).trim()) {
      facts.slug = clampStr(factsIn.slug, MAX_FACT_STR);
    }
    if (factsIn.menu_slot != null && String(factsIn.menu_slot).trim()) {
      const slot = String(factsIn.menu_slot).trim();
      if (!MENU_SLOTS.includes(slot)) {
        return { ok: false, error: `Invalid menu_slot: ${slot}` };
      }
      facts.menu_slot = slot;
    }
    if (factsIn.theme_path != null && String(factsIn.theme_path).trim()) {
      facts.theme_path = clampStr(factsIn.theme_path, MAX_FACT_STR);
    }
    if (factsIn.note != null && String(factsIn.note).trim()) {
      facts.note = clampStr(factsIn.note, MAX_NOTE);
    }

    const createdAt =
      typeof payload.createdAt === "number" && Number.isFinite(payload.createdAt)
        ? payload.createdAt
        : Date.now();

    return {
      ok: true,
      token: {
        v: 1,
        from,
        to,
        goal,
        facts,
        createdAt,
      },
    };
  }

  /**
   * @param {string} siteId
   * @param {object} payload  raw or partial; from/to/goal required
   * @returns {{ ok: true, token: object } | { ok: false, error: string }}
   */
  function write(siteId, payload) {
    const normalized = validateAndNormalize({
      ...payload,
      createdAt: Date.now(),
      v: 1,
    });
    if (!normalized.ok) return normalized;
    try {
      sessionStorage.setItem(siteKey(siteId), JSON.stringify(normalized.token));
    } catch (e) {
      return { ok: false, error: "Failed to store handoff token." };
    }
    return normalized;
  }

  /**
   * Read + remove. Returns token only if to matches and not expired.
   * @param {string} siteId
   * @param {string} expectedTo
   * @returns {object|null}
   */
  function consume(siteId, expectedTo) {
    const key = siteKey(siteId);
    let raw;
    try {
      raw = sessionStorage.getItem(key);
    } catch (e) {
      return null;
    }
    if (!raw) return null;

    try {
      sessionStorage.removeItem(key);
    } catch (e) {
      /* ignore */
    }

    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch (e) {
      return null;
    }

    const normalized = validateAndNormalize(parsed);
    if (!normalized.ok) return null;
    const token = normalized.token;
    if (token.to !== expectedTo) return null;
    if (Date.now() - token.createdAt > TTL_MS) return null;
    return token;
  }

  /**
   * @param {object} token
   * @returns {string}
   */
  function formatPromptBlock(token) {
    if (!token) return "";
    const fromLabel = SURFACE_LABELS[token.from] || token.from;
    const facts =
      token.facts && Object.keys(token.facts).length
        ? JSON.stringify(token.facts)
        : "(none)";
    return `

## Incoming handoff
Continuing from the **${fromLabel}** surface. Operator goal: ${token.goal}
Facts: ${facts}
Treat this as the active task for this surface. Do not ask them to restate it. Act with this surface's tools. Clear once you have started (harness will drop this block after the first send).`;
  }

  /**
   * @param {string} to
   * @param {object} [facts]
   * @param {(path: string, params?: object) => string} adminPathFn
   * @returns {string}
   */
  function targetHref(to, facts, adminPathFn) {
    const f = facts || {};
    if (typeof adminPathFn !== "function") {
      if (to === "navigation") return "admin-settings-navigation.php";
      if (to === "customize") return "admin-customize.php";
      if (to === "editor" && f.slug) {
        return `admin-editor.php?id=${encodeURIComponent(f.slug)}`;
      }
      return "admin-editor.php";
    }
    if (to === "navigation") {
      return adminPathFn("admin-settings-navigation.php");
    }
    if (to === "customize") {
      return adminPathFn("admin-customize.php");
    }
    if (to === "editor") {
      return f.slug
        ? adminPathFn("admin-editor.php", { id: f.slug })
        : adminPathFn("admin-editor.php");
    }
    return adminPathFn("admin-editor.php");
  }

  function surfaceLabel(surface) {
    return SURFACE_LABELS[surface] || surface;
  }

  const TOOL_DEFINITION = {
    type: "function",
    function: {
      name: "handoff_to_surface",
      description:
        "Offer a handoff of the operator's goal to a sibling AI surface (Navigation, Customize/Theme, or Content Editor). Writes a continuity token and shows Cancel/Continue in the chat UI — does NOT navigate until the operator confirms. Use when the ask clearly belongs elsewhere. Do not invent tools on the other surface.",
      parameters: {
        type: "object",
        properties: {
          to: {
            type: "string",
            enum: ["editor", "navigation", "customize"],
            description: "Target surface (must differ from the current one).",
          },
          goal: {
            type: "string",
            description:
              "Concise operator-language intent for the target surface (max ~280 chars).",
          },
          facts: {
            type: "object",
            description:
              "Optional allowlisted facts only: slug, menu_slot (primary|secondary|footer), theme_path, note.",
            properties: {
              slug: { type: "string" },
              menu_slot: {
                type: "string",
                enum: ["primary", "secondary", "footer"],
              },
              theme_path: { type: "string" },
              note: { type: "string" },
            },
          },
        },
        required: ["to", "goal"],
      },
    },
  };

  /**
   * Remove any stored handoff for this site (e.g. operator cancelled).
   * @param {string} siteId
   */
  function clear(siteId) {
    try {
      sessionStorage.removeItem(siteKey(siteId));
    } catch (e) {
      /* ignore */
    }
  }

  /**
   * Execute handoff: validate, store, return url; caller navigates after confirm.
   * @param {object} args tool args
   * @param {string} fromSurface
   * @param {string} siteId
   * @returns {{ ok: true, to: string, url: string, goal: string } | { error: string }}
   */
  function executeHandoff(args, fromSurface, siteId) {
    const adminPathFn =
      global.Alpine &&
      Alpine.store("app") &&
      typeof Alpine.store("app").adminPath === "function"
        ? Alpine.store("app").adminPath.bind(Alpine.store("app"))
        : null;

    const result = write(siteId, {
      from: fromSurface,
      to: args && args.to,
      goal: args && args.goal,
      facts: (args && args.facts) || {},
    });
    if (!result.ok) {
      return { error: result.error };
    }
    const url = targetHref(result.token.to, result.token.facts, adminPathFn);
    return {
      ok: true,
      to: result.token.to,
      url,
      goal: result.token.goal,
    };
  }

  global.PenAiHandoff = {
    STORAGE_BASE,
    TTL_MS,
    SURFACES,
    TOOL_DEFINITION,
    siteKey,
    validateAndNormalize,
    write,
    consume,
    clear,
    formatPromptBlock,
    targetHref,
    surfaceLabel,
    executeHandoff,
  };
})(typeof window !== "undefined" ? window : globalThis);
