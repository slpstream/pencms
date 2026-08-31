/**
 * PenCMS AI Sidebar Controller for Navigation Builder (ai-sidebar-navigation.js)
 * Alpine.js component for the AI Assistant sidebar card specifically for menus and navigation.
 */

const DEBUG_AI = false;

let _currentRole = "assistant";

const innerMd = new marked.Marked();
innerMd.use({
  renderer: {
    paragraph({ tokens }) {
      return "<p>" + this.parser.parseInline(tokens) + "</p>";
    },
    codespan({ text }) {
      return (
        '<code class="bg-[#fcfbf9] px-1.5 py-0.5 rounded font-mono text-xs border border-border/80">' +
        escapeHtml(text) +
        "</code>"
      );
    },
  },
});
innerMd.use({ gfm: true, breaks: true });

const md = new marked.Marked();

md.use({
  hooks: {
    preprocess(src) {
      const lines = src.split("\n");
      const out = [];
      let inBQ = false;
      let bqLines = [];
      const flush = () => {
        if (bqLines.length === 0) return;
        if (out.length && out[out.length - 1].trim() !== "") out.push("");
        const innerText = bqLines.join("\n");
        const innerHtml = innerMd.parse(innerText);
        out.push(
          '<blockquote class="border-l-2 border-rust/60 pl-3 my-2 italic leading-snug text-steel-muted">' +
            innerHtml +
            "</blockquote>",
        );
        out.push("");
        bqLines = [];
      };
      for (const line of lines) {
        const m = line.match(/^( {0,3})>+ ?(.*)$/);
        if (m) {
          if (!inBQ) {
            inBQ = true;
            bqLines = [];
          }
          bqLines.push(m[2]);
        } else {
          if (inBQ) {
            flush();
            inBQ = false;
          }
          out.push(line);
        }
      }
      if (inBQ) flush();
      return out.join("\n");
    },
    postprocess(html) {
      return html
        .replace(/<script\b[\s\S]*?<\/script>/gi, "")
        .replace(/<iframe\b[\s\S]*?<\/iframe>/gi, "")
        .replace(/<style\b[\s\S]*?<\/style>/gi, "")
        .replace(/<object\b[\s\S]*?<\/object>/gi, "")
        .replace(/<embed\b[\s\S]*?<\/embed>/gi, "")
        .replace(/\s+on[a-z]+\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]*)/gi, "")
        .replace(
          /(\b(?:href|src|xlink:href|formaction)\s*=\s*)(?:"([^"]*)"|'([^']*)'|([^\s>]+))/gi,
          (_m, prefix, q1, q2, q3) => {
            const raw =
              q1 !== undefined ? q1 : q2 !== undefined ? q2 : q3 || "";
            const decoded = raw.replace(
              /&(?:#x[0-9a-f]+|#[0-9]+|[a-z][a-z0-9]+);/gi,
              (ent) => {
                try {
                  const d = document.createElement("textarea");
                  d.innerHTML = ent;
                  return d.value;
                } catch (e) {
                  return ent;
                }
              },
            );
            if (
              /^(?:j[\s\x00-\x1f]*a[\s\x00-\x1f]*v[\s\x00-\x1f]*a[\s\x00-\x1f]*s[\s\x00-\x1f]*c[\s\x00-\x1f]*r[\s\x00-\x1f]*i[\s\x00-\x1f]*p[\s\x00-\x1f]*t[\s\x00-\x1f]*:|v[\s\x00-\x1f]*b[\s\x00-\x1f]*s[\s\x00-\x1f]*c[\s\x00-\x1f]*r[\s\x00-\x1f]*i[\s\x00-\x1f]*p[\s\x00-\x1f]*t[\s\x00-\x1f]*:|d[\s\x00-\x1f]*a[\s\x00-\x1f]*t[\s\x00-\x1f]*:)/i.test(
                decoded,
              )
            ) {
              return prefix + '"#"';
            }
            return _m;
          },
        );
    },
  },
  renderer: {
    paragraph({ tokens }) {
      const cls = _currentRole === "user" ? "leading-tight" : "leading-relaxed";
      return `<p class="mb-2 ${cls}">${this.parser.parseInline(tokens)}</p>`;
    },
    codespan({ text }) {
      return (
        '<code class="bg-[#fcfbf9] px-1.5 py-0.5 rounded font-mono text-xs border border-border/80">' +
        escapeHtml(text) +
        "</code>"
      );
    },
    code({ text, lang }) {
      const langLabel =
        lang && /^[a-zA-Z0-9+#-]{1,16}$/.test(lang)
          ? `<span class="text-steel-muted block mb-1.5 select-none font-sans font-bold uppercase tracking-wider text-[10px]">${lang}</span>`
          : "";
      return (
        '<div class="relative group my-2">' +
        '<pre class="bg-[#fcfbf9] border border-border/80 p-3 rounded font-mono text-xs overflow-x-auto select-text">' +
        langLabel +
        '<code class="font-mono text-xs">' +
        escapeHtml(text) +
        "</code></pre>" +
        '<button class="copy-code-btn absolute top-2 right-2 p-1.5 rounded border border-border/80 bg-[#fcfbf9] hover:bg-[#f5f3f0] text-forge-mid hover:text-rust opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity duration-150 shadow-sm" title="Copy code to clipboard">' +
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-4 h-4"><rect width="256" height="256" fill="none"/><polyline points="168 168 216 168 216 40 88 40 88 88" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/><rect x="40" y="88" width="128" height="128" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/></svg>' +
        "</button>" +
        "</div>"
      );
    },
    heading({ tokens, depth }) {
      const tag = "h" + Math.min(depth, 4);
      const text = this.parser.parseInline(tokens);
      if (depth === 1)
        return `<${tag} class="text-xl font-bold mt-4 mb-2 leading-none text-forge-black">${text}</${tag}>`;
      if (depth === 2)
        return `<${tag} class="text-lg font-bold mt-4 mb-2 leading-tight text-forge-black">${text}</${tag}>`;
      if (depth === 3)
        return `<${tag} class="text-base font-bold mt-3 mb-1 leading-snug text-forge-black">${text}</${tag}>`;
      return `<${tag} class="text-sm font-bold mt-3 mb-1 leading-normal text-forge-black">${text}</${tag}>`;
    },
    image({ href, title, tokens }) {
      const alt = tokens ? this.parser.parseInline(tokens) : "";
      let attrs = `src="${escapeHtml(href)}" alt="${alt}"`;
      if (title) attrs += ` title="${escapeHtml(title)}"`;
      return `<img ${attrs} class="max-h-40 rounded border border-border my-1" style="display:block" />`;
    },
  },
});
md.use({ gfm: true, breaks: true });

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

/** Catalog size cap so system prompts stay within token budget. */
const NAV_CATALOG_LIMIT = 150;

/**
 * Must stay in sync with settings-navigation.js termToCategorySlug /
 * TaxonomySlug::termToCategorySlug (PHP).
 */
function navTermToCategorySlug(term) {
  let leaf = String(term || "").trim();
  const m = leaf.match(/^([a-z0-9_]+)\/(.+)$/i);
  if (m) leaf = m[2];
  const sep = leaf.lastIndexOf(" / ");
  if (sep !== -1) leaf = leaf.slice(sep + 3);
  return leaf.trim().toLowerCase().replace(/ /g, "-");
}

const MENU_TARGET_PROPERTIES = {
  type: {
    type: "string",
    enum: ["content", "custom", "label", "taxonomy", "system"],
    description:
      "Target kind. Page/Post use content; Categories use taxonomy; System pages use system; Custom Link uses custom; Label uses label.",
  },
  content_slug: {
    type: "string",
    description:
      "For content: page/post slug. For taxonomy: '{vocabKey}/{termPath}' (e.g. 'primary/Winter'). For system: the system page id ('home'|'blog'|'search'|'rss') — not a content slug. Omit for custom/label.",
  },
  content_type: {
    type: "string",
    enum: ["page", "post"],
    description:
      "ONLY for type=content (required). page = static page (frontmatter.page true); post = article. Omit entirely for taxonomy, system, custom, and label — never set content_type on those.",
  },
  url: {
    type: "string",
    description:
      "For custom: the href. For taxonomy: use Taxonomies catalog url_formula (and each term's url). For system: from the System Pages catalog. Optional/advisory for taxonomy/system — ThemeEngine resolves at render time. Omit for content/label.",
  },
};

const MENU_TARGET_SCHEMA = {
  type: "object",
  properties: MENU_TARGET_PROPERTIES,
  required: ["type"],
};

const CREATE_TARGET_DESCRIPTION = `Create a menu item. Depth max 2 (top-level or child of top-level only). item_create.menu MUST equal menu_slot.

Required fields by target.type (omit everything else on target):
- content: content_slug, content_type
- taxonomy: content_slug, url
- system: content_slug (system page id); url optional
- custom: url
- label: (none)

Target shapes (six UI types → five API types):
1) Page:  {"type":"content","content_slug":"about","content_type":"page"}
2) Post:  {"type":"content","content_slug":"my-article","content_type":"post"}
3) Category/term: {"type":"taxonomy","content_slug":"primary/Winter","url":"/category/winter/"}
4) System: {"type":"system","content_slug":"blog","url":"/category/"}
5) Custom: {"type":"custom","url":"https://example.com"}
6) Label:  {"type":"label"}

Example create args (omit parent_id / open_in_new_tab for top-level defaults):
{"menu_slot":"primary","item_create":{"menu":"primary","label":"About","target":{"type":"content","content_slug":"about","content_type":"page"}}}

Defaults: parent_id omitted/null = top-level; open_in_new_tab omitted = false. Only set these when nesting or opening in a new tab.`;

const SYSTEM_PAGE_IDS = new Set(["home", "blog", "search", "rss"]);
const VALID_SLOTS = new Set(["primary", "secondary", "footer"]);

/**
 * Structured tool failure for the model (and UI JSON).
 * @param {string} error - short machine code
 * @param {string} reason - what went wrong
 * @param {string} hint - how to fix / retry
 */
function toolError(error, reason, hint) {
  return { error, reason, hint };
}

function detailToString(detail) {
  if (detail == null) return "";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        if (typeof d === "string") return d;
        const loc = Array.isArray(d.loc) ? d.loc.join(".") : "";
        const msg = d.msg || d.message || JSON.stringify(d);
        return loc ? `${loc}: ${msg}` : msg;
      })
      .join("; ");
  }
  if (typeof detail === "object") {
    if (detail.message) return String(detail.message);
    return JSON.stringify(detail);
  }
  return String(detail);
}

/**
 * Map MCP / API failures into { error, reason, hint }.
 * @param {Error & { status?: number, detail?: unknown }} err
 */
function shapeMcpError(err) {
  const status = err && err.status != null ? err.status : null;
  const rawDetail = err && err.detail !== undefined ? err.detail : null;
  const reason =
    detailToString(rawDetail) ||
    (err && err.message) ||
    "Tool execution failed.";

  if (status === 401 || status === 403) {
    return toolError(
      "AUTH_ERROR",
      reason,
      "Unlock the vault and ensure the AI provider / MCP token has write scope."
    );
  }

  if (/Nesting limit exceeded/i.test(reason)) {
    return toolError(
      "NESTING_LIMIT",
      reason,
      "Max depth is 2. parent_id must be a top-level item (parent_id null). Children cannot have children."
    );
  }

  if (/cannot be its own parent/i.test(reason)) {
    return toolError(
      "INVALID_PARENT",
      reason,
      "Use a different parent_id, or set parent_id to null for a top-level item."
    );
  }

  if (/Parent item .* does not exist/i.test(reason)) {
    return toolError(
      "PARENT_NOT_FOUND",
      reason,
      "Call list_menu_items for this slot and use a real top-level item id as parent_id."
    );
  }

  if (/not found in slot/i.test(reason) || (status === 404 && /not found/i.test(reason))) {
    return toolError(
      "ITEM_NOT_FOUND",
      reason,
      "Call list_menu_items for this slot and use an id that exists there."
    );
  }

  if (/must match/i.test(reason)) {
    return toolError(
      "SLOT_MISMATCH",
      reason,
      "Set item_create.menu (or replace items) so menu equals the path menu_slot."
    );
  }

  if (/Duplicate menu item ID/i.test(reason)) {
    return toolError(
      "DUPLICATE_ID",
      reason,
      "Each item id in replace_menu_slot must be unique, or omit id to auto-generate."
    );
  }

  if (Array.isArray(rawDetail) && rawDetail.length) {
    const first = rawDetail[0];
    const loc = Array.isArray(first.loc) ? first.loc.join(".") : "";
    const hint = loc.includes("target")
      ? "Fix target fields per type: content→content_slug+content_type; taxonomy→content_slug+url; system→content_slug (home|blog|search|rss); custom→url; label→none. Never put content_type on non-content targets."
      : "Fix the invalid field and retry with the required shape for this tool.";
    return toolError("VALIDATION_ERROR", reason, hint);
  }

  if (status === 422 || /validation|field required|type_error/i.test(reason)) {
    return toolError(
      "VALIDATION_ERROR",
      reason,
      "Check required fields by target.type (see Target field requirements). Omit fields that do not apply."
    );
  }

  if (status != null && status >= 500) {
    return toolError(
      "SERVER_ERROR",
      reason,
      "Retry once. If it persists, list_menu_items to verify state, then try a smaller change."
    );
  }

  return toolError(
    "TOOL_ERROR",
    reason,
    "Inspect the reason, fix the args using the catalogs / target field table, and retry."
  );
}

function getNavParentData() {
  try {
    const el = document.querySelector('[x-data="navigationSettings"]');
    if (el && window.Alpine) return Alpine.$data(el);
  } catch (_) {}
  return null;
}

/**
 * Validate a single nested target object. Returns toolError or null.
 * @param {object} target
 * @param {{ pages?: object[], taxonomy?: object, systemPages?: object[] }|null} catalogs
 */
function validateMenuTarget(target, catalogs) {
  if (!target || typeof target !== "object") {
    return toolError(
      "INVALID_TARGET",
      "target is missing or not an object.",
      "Send target as { type, ... } with fields from the required-fields table."
    );
  }

  const type = target.type;
  if (!type) {
    return toolError(
      "INVALID_TARGET",
      "target.type is required.",
      "Use one of: content, taxonomy, system, custom, label."
    );
  }

  const unexpectedContentType =
    type !== "content" &&
    Object.prototype.hasOwnProperty.call(target, "content_type") &&
    target.content_type != null &&
    target.content_type !== "";

  if (unexpectedContentType) {
    return toolError(
      "INVALID_TARGET_FIELDS",
      `type="${type}" must not include content_type (got "${target.content_type}").`,
      "Omit content_type. It is only valid when type is \"content\"."
    );
  }

  if (type === "content") {
    if (!target.content_slug) {
      return toolError(
        "MISSING_FIELD",
        'type="content" requires content_slug.',
        "Pick a slug from the Pages or Posts catalog."
      );
    }
    if (target.content_type !== "page" && target.content_type !== "post") {
      return toolError(
        "MISSING_FIELD",
        'type="content" requires content_type "page" or "post".',
        "Use content_type \"page\" for Pages catalog entries, \"post\" for Posts."
      );
    }
    if (catalogs && Array.isArray(catalogs.pages)) {
      const match = catalogs.pages.find((p) => p.id === target.content_slug);
      if (!match) {
        const kind = target.content_type === "page" ? "page" : "post";
        return toolError(
          "INVALID_SLUG",
          `No ${kind} with slug '${target.content_slug}' exists in the catalog.`,
          `Use a slug from the ${kind === "page" ? "Pages" : "Posts"} catalog, or search_content / create the content first.`
        );
      }
      const isPage = !!(
        match.frontmatter &&
        (match.frontmatter.page === true || match.frontmatter.page === "true")
      );
      if (target.content_type === "page" && !isPage) {
        return toolError(
          "INVALID_CONTENT_TYPE",
          `Slug '${target.content_slug}' is a post, but content_type was "page".`,
          'Use content_type "post", or pick a slug from the Pages catalog.'
        );
      }
      if (target.content_type === "post" && isPage) {
        return toolError(
          "INVALID_CONTENT_TYPE",
          `Slug '${target.content_slug}' is a page, but content_type was "post".`,
          'Use content_type "page", or pick a slug from the Posts catalog.'
        );
      }
    }
    return null;
  }

  if (type === "taxonomy") {
    if (!target.content_slug) {
      return toolError(
        "MISSING_FIELD",
        'type="taxonomy" requires content_slug ("{vocabKey}/{termPath}").',
        "Copy content_slug (and url) from a Taxonomies catalog term entry."
      );
    }
    if (!target.url) {
      return toolError(
        "MISSING_FIELD",
        'type="taxonomy" requires url (e.g. "/category/spring/").',
        "Use the term's url from the Taxonomies catalog (see url_formula)."
      );
    }
    if (catalogs && catalogs.taxonomy) {
      const slash = target.content_slug.indexOf("/");
      if (slash === -1) {
        return toolError(
          "INVALID_SLUG",
          `Taxonomy content_slug '${target.content_slug}' must be "{vocabKey}/{termPath}".`,
          "Example: seasons_of_the_year/Spring — copy from the Taxonomies catalog."
        );
      }
      const vocabKey = target.content_slug.slice(0, slash);
      const termPath = target.content_slug.slice(slash + 1);
      const vocabs = catalogs.taxonomy.raw?.vocabularies || {};
      const vocab = vocabs[vocabKey];
      if (!vocab) {
        return toolError(
          "INVALID_SLUG",
          `Unknown vocabulary key '${vocabKey}'.`,
          "Use a vocab key from the Taxonomies catalog (not a guessed name like categories/tags)."
        );
      }
      const terms = Array.isArray(vocab.terms) ? vocab.terms : [];
      if (terms.length && !terms.includes(termPath)) {
        return toolError(
          "INVALID_SLUG",
          `Term '${termPath}' is not in vocabulary '${vocabKey}'.`,
          "Pick term_path / content_slug from that vocabulary's terms in the Taxonomies catalog."
        );
      }
    }
    return null;
  }

  if (type === "system") {
    if (!target.content_slug) {
      return toolError(
        "MISSING_FIELD",
        'type="system" requires content_slug (the system page id).',
        "Use one of: home, blog, search, rss (from the System Pages catalog)."
      );
    }
    if (!SYSTEM_PAGE_IDS.has(target.content_slug)) {
      return toolError(
        "INVALID_SYSTEM_ID",
        `Unknown system page id '${target.content_slug}'.`,
        "content_slug for system targets must be one of: home, blog, search, rss."
      );
    }
    return null;
  }

  if (type === "custom") {
    if (!target.url) {
      return toolError(
        "MISSING_FIELD",
        'type="custom" requires url.',
        'Example: {"type":"custom","url":"https://example.com"}'
      );
    }
    return null;
  }

  if (type === "label") {
    return null;
  }

  return toolError(
    "INVALID_TARGET",
    `Unknown target.type "${type}".`,
    "Use one of: content, taxonomy, system, custom, label."
  );
}

/**
 * Client-side preflight before MCP write calls.
 * @returns {object|null} toolError payload or null if ok
 */
function preflightNavTool(functionName, args) {
  const a = args && typeof args === "object" ? args : {};
  const parent = getNavParentData();
  const catalogs = parent
    ? {
        pages: parent.pages || [],
        taxonomy: parent.taxonomy || null,
        systemPages: parent.systemPages || [],
      }
    : null;

  if (a.menu_slot != null && !VALID_SLOTS.has(a.menu_slot)) {
    return toolError(
      "INVALID_SLOT",
      `Invalid menu_slot '${a.menu_slot}'.`,
      "Use primary, secondary, or footer."
    );
  }

  if (functionName === "create_menu_item") {
    const item = a.item_create;
    if (!item || typeof item !== "object") {
      return toolError(
        "MISSING_FIELD",
        "item_create is required.",
        'Pass { menu_slot, item_create: { menu, label, target, ... } }.'
      );
    }
    if (a.menu_slot && item.menu && a.menu_slot !== item.menu) {
      return toolError(
        "SLOT_MISMATCH",
        `menu_slot "${a.menu_slot}" does not match item_create.menu "${item.menu}".`,
        "Set both to the same slot (primary | secondary | footer)."
      );
    }
    if (!item.label) {
      return toolError(
        "MISSING_FIELD",
        "item_create.label is required.",
        "Provide a visible label string."
      );
    }
    return validateMenuTarget(item.target, catalogs);
  }

  if (functionName === "update_menu_item") {
    const item = a.item_update;
    if (item && item.target) {
      return validateMenuTarget(item.target, catalogs);
    }
    return null;
  }

  if (functionName === "replace_menu_slot") {
    const items = a.items;
    if (!Array.isArray(items)) {
      return toolError(
        "MISSING_FIELD",
        "items must be an array of menu items.",
        "Pass { menu_slot, items: [ { label, target, ... }, ... ] }."
      );
    }
    for (let i = 0; i < items.length; i++) {
      const err = validateMenuTarget(items[i] && items[i].target, catalogs);
      if (err) {
        return toolError(
          err.error,
          `items[${i}]: ${err.reason}`,
          err.hint
        );
      }
    }
    return null;
  }

  return null;
}

function menusToApiShape(menus) {
  return window.PenMenuItemShape.menusToApiShape(menus);
}

function buildContentCatalog(pages) {
  const pageList = [];
  const postList = [];
  for (const p of pages || []) {
    const isPage = !!(
      p.frontmatter &&
      (p.frontmatter.page === true || p.frontmatter.page === "true")
    );
    const entry = {
      slug: p.id,
      title: p.frontmatter?.title || p.frontmatter?.name || p.title || p.id,
      status: (p.frontmatter?.status || "").toLowerCase() || "unknown",
      kind: isPage ? "page" : "post",
    };
    if (isPage) pageList.push(entry);
    else postList.push(entry);
  }
  const truncate = (arr, kind) => {
    if (arr.length <= NAV_CATALOG_LIMIT) return { items: arr, truncated: false };
    return {
      items: arr.slice(0, NAV_CATALOG_LIMIT),
      truncated: true,
      note: `Showing first ${NAV_CATALOG_LIMIT} of ${arr.length} ${kind}s. Use search_content for the rest.`,
    };
  };
  return {
    pages: truncate(pageList, "page"),
    posts: truncate(postList, "post"),
  };
}

function buildTaxonomyCatalog(taxonomy) {
  if (!taxonomy) return { primary_vocabulary: null, vocabularies: {} };
  const primary =
    taxonomy.parsed?.primary_vocabulary ||
    (taxonomy.raw?.vocabularies ? Object.keys(taxonomy.raw.vocabularies)[0] : null) ||
    null;
  const vocabs = taxonomy.raw?.vocabularies || {};
  const out = {};
  for (const [key, vocab] of Object.entries(vocabs)) {
    const terms = Array.isArray(vocab.terms) ? vocab.terms : [];
    const termEntries = terms.slice(0, NAV_CATALOG_LIMIT).map((termPath) => {
      const slug = navTermToCategorySlug(`${key}/${termPath}`);
      return {
        term_path: termPath,
        content_slug: `${key}/${termPath}`,
        url: slug ? `/category/${slug}/` : null,
      };
    });
    out[key] = {
      label: vocab.label || key,
      type: vocab.type || "flat",
      controlled: vocab.controlled !== false,
      term_count: terms.length,
      truncated: terms.length > NAV_CATALOG_LIMIT,
      terms: termEntries,
    };
  }
  return {
    primary_vocabulary: primary,
    url_formula:
      "All taxonomy archives use /category/{leaf-slug}/ (no /tag/ path). Leaf = last segment after ' / ' in the term path; lowercase; spaces→hyphens. Vocab key is stored in content_slug but NOT in the public URL.",
    note:
      "There is often no vocabulary named 'categories'. Use the vocabularies listed here (primary may be labeled Topic). Post frontmatter category fields may reference vocabulary: primary.",
    vocabularies: out,
  };
}

const TOOL_DEFINITIONS = [
  {
    type: "function",
    function: {
      name: "list_menus",
      description: "List all site menus and their contents.",
      parameters: { type: "object", properties: {} },
    },
  },
  {
    type: "function",
    function: {
      name: "list_menu_items",
      description: "List all menu items inside a specific menu slot.",
      parameters: {
        type: "object",
        properties: {
          menu_slot: {
            type: "string",
            enum: ["primary", "secondary", "footer"],
            description: "The slot to query.",
          },
        },
        required: ["menu_slot"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "create_menu_item",
      description: CREATE_TARGET_DESCRIPTION,
      parameters: {
        type: "object",
        properties: {
          menu_slot: {
            type: "string",
            enum: ["primary", "secondary", "footer"],
            description: "Slot path; must match item_create.menu.",
          },
          item_create: {
            type: "object",
            properties: {
              menu: {
                type: "string",
                enum: ["primary", "secondary", "footer"],
                description: "Must equal menu_slot.",
              },
              label: { type: "string", description: "Visible menu label." },
              target: MENU_TARGET_SCHEMA,
              parent_id: {
                type: "string",
                description:
                  "Optional; default null (top-level). Omit for top-level items. Set only to nest under a top-level item UUID in the same slot (depth max 2).",
              },
              open_in_new_tab: {
                type: "boolean",
                default: false,
                description:
                  "Optional; default false. Omit unless the link should open in a new tab.",
              },
            },
            required: ["menu", "label", "target"],
          },
        },
        required: ["menu_slot", "item_create"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "update_menu_item",
      description:
        "Partial update of an existing menu item. Only include fields to change. Depth max 2. Target types: content|custom|label|taxonomy|system (same shapes as create_menu_item).",
      parameters: {
        type: "object",
        properties: {
          menu_slot: {
            type: "string",
            enum: ["primary", "secondary", "footer"],
          },
          item_id: { type: "string", description: "UUID of the item to update." },
          item_update: {
            type: "object",
            properties: {
              label: { type: "string" },
              target: MENU_TARGET_SCHEMA,
              parent_id: {
                type: "string",
                description:
                  "Optional. New parent UUID (top-level only), or null to promote to top-level. Omit to leave parent unchanged.",
              },
              open_in_new_tab: {
                type: "boolean",
                description:
                  "Optional. Omit to leave unchanged; set true/false only when changing new-tab behavior.",
              },
              order: { type: "integer" },
            },
          },
        },
        required: ["menu_slot", "item_id", "item_update"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "delete_menu_item",
      description: "Delete an existing menu item and its children.",
      parameters: {
        type: "object",
        properties: {
          menu_slot: {
            type: "string",
            enum: ["primary", "secondary", "footer"],
          },
          item_id: { type: "string" },
        },
        required: ["menu_slot", "item_id"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "reorder_menu_items",
      description:
        "Reorder items within a slot. Pass the full sibling-aware list (id, parent_id, order). Depth max 2. Prefer this over delete+recreate when rearranging existing items. On success returns the full updated slot as { menu_slot, items } (same item shape as list_menu_items) — no need to re-list.",
      parameters: {
        type: "object",
        properties: {
          menu_slot: {
            type: "string",
            enum: ["primary", "secondary", "footer"],
          },
          reorder_items: {
            type: "array",
            items: {
              type: "object",
              properties: {
                id: { type: "string" },
                parent_id: { type: "string" },
                order: { type: "integer" },
              },
              required: ["id", "order"],
            },
          },
        },
        required: ["menu_slot", "reorder_items"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "clear_menu_slot",
      description: "Clear all menu items from a specific menu slot.",
      parameters: {
        type: "object",
        properties: {
          menu_slot: {
            type: "string",
            enum: ["primary", "secondary", "footer"],
          },
        },
        required: ["menu_slot"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "replace_menu_slot",
      description:
        "Replace all menu items in a slot wholesale. Depth max 2. Use the same target shapes as create_menu_item (content|custom|label|taxonomy|system). Prefer incremental create/update/reorder unless rebuilding the whole slot.",
      parameters: {
        type: "object",
        properties: {
          menu_slot: {
            type: "string",
            enum: ["primary", "secondary", "footer"],
          },
          items: {
            type: "array",
            items: {
              type: "object",
              properties: {
                id: {
                  type: "string",
                  description: "Optional; generated if omitted. Use stable ids when nesting via parent_id.",
                },
                label: { type: "string" },
                target: MENU_TARGET_SCHEMA,
                parent_id: {
                  type: "string",
                  description:
                    "Optional; default null (top-level). Omit for top-level; set only when nesting under another item's id in this list.",
                },
                open_in_new_tab: {
                  type: "boolean",
                  default: false,
                  description:
                    "Optional; default false. Omit unless opening in a new tab.",
                },
              },
              required: ["label", "target"],
            },
          },
        },
        required: ["menu_slot", "items"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "get_site_config",
      description:
        "Returns CMS configuration, collection schemas, and taxonomy vocabularies. Prefer the Taxonomies / Pages / Posts catalogs already in the system prompt; call this only if those catalogs are missing or incomplete.",
      parameters: { type: "object", properties: {} },
    },
  },
  {
    type: "function",
    function: {
      name: "search_content",
      description:
        "Full-text search for page/post slugs to link as content targets. Prefer the Pages/Posts catalogs in the system prompt first. query is required and is sent as a GET query parameter.",
      parameters: {
        type: "object",
        properties: {
          query: { type: "string", description: "Search phrase (required)." },
          limit: { type: "integer", default: 10 },
        },
        required: ["query"],
      },
    },
  },
];

if (window.PenAiHandoff && window.PenAiHandoff.TOOL_DEFINITION) {
  TOOL_DEFINITIONS.push(window.PenAiHandoff.TOOL_DEFINITION);
}

const MCP_TOOL_MAP = {
  list_menus: { method: "GET", path: "/mcp/menus" },
  list_menu_items: { method: "GET", path: "/mcp/menus/{menu_slot}" },
  create_menu_item: { method: "POST", path: "/mcp/menus/{menu_slot}/items" },
  update_menu_item: { method: "PUT", path: "/mcp/menus/{menu_slot}/items/{item_id}" },
  delete_menu_item: { method: "DELETE", path: "/mcp/menus/{menu_slot}/items/{item_id}" },
  reorder_menu_items: { method: "PUT", path: "/mcp/menus/{menu_slot}/reorder" },
  clear_menu_slot: { method: "DELETE", path: "/mcp/menus/{menu_slot}" },
  replace_menu_slot: { method: "PUT", path: "/mcp/menus/{menu_slot}" },
  get_site_config: { method: "GET", path: "/mcp/site-config" },
  search_content: { method: "GET", path: "/mcp/search" }
};

document.addEventListener("alpine:init", () => {
  Alpine.data("aiSidebar", () => ({
    messages: [],
    prompt: "",
    streaming: false,
    streamingWord: 'STREAMING...',
    _streamingWordTimer: null,
    _streamingWords: [
      'STREAMING...', 'SLEUTHING...', 'THINKING...', 'FIGURING...',
      'HONING...', 'CRYSTALLIZING...', 'PICTURING...', 'PONDERING...',
      'FATHOMING...', 'SIFTING...', 'MULLING...', 'WEIGHING...',
      'UNTANGLING...', 'MUSING...',
    ],
    vaultUnlocked: false,
    vaultPassword: "",
    showVaultPassword: false,
    vaultUnlockError: "",
    isUnlockingVault: false,
    copiedMessageIndex: null,
    siteId: "default",
    siteName: "PenCMS",
    abortController: null,
    incomingHandoff: null,
    _handoffForThisTurn: null,
    pendingOutgoingHandoff: null,
    _handoffConfirmBusy: false,
    _handoffNavigating: false,
    _pendingToolCalls: {},

    activeSiteId() {
      try {
        const app = window.Alpine && Alpine.store("app");
        if (app && app.activeSiteId) {
          return String(app.activeSiteId).trim() || "default";
        }
      } catch (e) {}
      if (window.AUTH && window.AUTH.siteId) {
        return String(window.AUTH.siteId).trim() || "default";
      }
      return "default";
    },

    chatStorageKey(base) {
      return `${base}:${this.activeSiteId()}`;
    },

    syncSiteContext() {
      this.siteId = this.activeSiteId();
      try {
        const app = window.Alpine && Alpine.store("app");
        if (app && typeof app.resolveActiveSitename === "function") {
          this.siteName = app.resolveActiveSitename();
        } else if (app && app.sitename) {
          this.siteName = app.sitename;
        }
      } catch (e) {
        /* keep previous */
      }
    },

    loadChatStateForSite() {
      try {
        const storedMessages = sessionStorage.getItem(
          this.chatStorageKey("pen_nav_messages"),
        );
        this.messages = storedMessages ? JSON.parse(storedMessages) : [];
      } catch (e) {
        this.messages = [];
      }
    },

    async init() {
      this.syncSiteContext();
      this.loadChatStateForSite();
      this.consumeIncomingHandoff("navigation");

      try {
        this.$watch(
          () => {
            const app = window.Alpine && Alpine.store("app");
            return (app && app.activeSiteId) || "default";
          },
          (next, prev) => {
            if (next === prev) return;
            this.syncSiteContext();
            this.loadChatStateForSite();
          },
        );
      } catch (e) {
        /* Alpine watch unavailable */
      }

      if (window.VAULT) {
        window.VAULT.ready.then(() => {
          this.vaultUnlocked = window.VAULT.unlocked;
        });
        window.addEventListener("pen:vault-unlocked", () => {
          this.vaultUnlocked = true;
        });
      }
    },

    newConversation() {
      sessionStorage.removeItem(this.chatStorageKey("pen_nav_messages"));
      this.messages = [];
      this.showToast("New conversation started.");
    },

    showToast(message, type = "success") {
      window.dispatchEvent(
        new CustomEvent("pen:toast", { detail: { message, type } })
      );
    },

    async unlockVault() {
      if (!this.vaultPassword.trim() || !window.VAULT) return;

      this.isUnlockingVault = true;
      this.vaultUnlockError = "";

      try {
        await window.VAULT.unlock(this.vaultPassword);
        this.vaultUnlocked = true;
        this.vaultPassword = "";
        window.dispatchEvent(new CustomEvent("pen:vault-unlocked"));
        this.showToast("Vault unlocked successfully");

        this.$nextTick(() => {
          const input = document.getElementById("ai-prompt-textarea");
          if (input) input.focus();
        });
      } catch (e) {
        this.vaultUnlockError = "Incorrect password";
        this.$refs.vaultPasswordInput?.focus();
      } finally {
        this.isUnlockingVault = false;
      }
    },

    autoGrow(el) {
      if (!el) return;
      el.style.height = "auto";
      el.style.height = Math.min(el.scrollHeight, 320) + "px";
    },

    handleEnterKey(e) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        this.sendPrompt();
      }
    },

    scrollToBottom() {
      const container = document.getElementById("ai-chat-messages-container");
      if (container) {
        requestAnimationFrame(() => {
          container.scrollTop = container.scrollHeight;
        });
      }
    },

    focusPrompt() {
      this.$nextTick(() => {
        this.scrollToBottom();
        requestAnimationFrame(() => {
          const ta = document.getElementById("ai-prompt-textarea");
          if (ta && !ta.disabled) ta.focus();
        });
      });
    },

    renderMsg(msgOrContent, isLast = false) {
      if (!msgOrContent) return "";

      let content = "";
      let role = "assistant";
      let name = "";
      let toolCalls = null;

      if (typeof msgOrContent === "object" && msgOrContent !== null) {
        content = msgOrContent.displayContent || msgOrContent.content || "";
        role = msgOrContent.role || "assistant";
        name = msgOrContent.name || "";
        toolCalls = msgOrContent.tool_calls || null;
      } else {
        content = String(msgOrContent);
      }

      if (content) {
        content = content.replace(/\r\n/g, "\n");
        content = content.replace(/```tool_call[\s\S]*?```/g, "");
        content = content.replace(/```json[\s\S]*?```/g, "");
        content = content.replace(/脚本/g, "");

        const rawJsonRegex = /\{[\s\S]*?\}/g;
        content = content.replace(rawJsonRegex, (match) => {
          try {
            const parsed = JSON.parse(match);
            if (
              parsed.name ||
              parsed.query ||
              parsed.slug ||
              parsed.filename ||
              parsed.collection_name
            ) {
              return "";
            }
          } catch (e) {}
          return match;
        });

        content = content.trim();
      }

      if (role === "tool") {
        return `<div class="text-[10px] font-mono text-steel-muted flex flex-col gap-1.5 py-0 select-text">
          <div class="flex items-center gap-1.5">
            <svg class="w-3.5 h-3.5 text-steel-muted shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path>
              <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
            </svg>
            <span>Tool <strong>${name || "mcp"}</strong> executed.</span>
          </div>
        </div>`;
      }

      if (
        role === "assistant" &&
        toolCalls &&
        toolCalls.length > 0 &&
        !content
      ) {
        const toolNames = toolCalls.map((tc) => tc.function.name).join(", ");
        if (this.streaming && isLast) {
          return `<div class="text-[10px] font-mono text-rust flex items-center gap-1.5 py-0">
            <svg class="w-3.5 h-3.5 text-rust animate-spin shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
            </svg>
            <span>Calling tool: <strong>${toolNames}</strong>...</span>
          </div>`;
        } else {
          return `<div class="text-[10px] font-mono text-steel-muted flex items-center gap-1.5 py-0 select-text">
            <svg class="w-3.5 h-3.5 text-steel-muted shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path>
            </svg>
            <span>Requested tool: <strong>${toolNames}</strong></span>
          </div>`;
        }
      }

      if (!content) return "";

      _currentRole = role;
      return md.parse(content);
    },

    copyToClipboard(text, idx) {
      if (!navigator.clipboard) return;
      navigator.clipboard.writeText(text).then(() => {
        this.copiedMessageIndex = idx;
        setTimeout(() => {
          this.copiedMessageIndex = null;
        }, 2000);
      });
    },

    buildSystemPrompt() {
      const parent =
        window.Alpine &&
        Alpine.$data(document.querySelector('[x-data="navigationSettings"]'));
      const menus = parent
        ? parent.menus
        : { primary: [], secondary: [], footer: [] };
      const currentActiveTab = parent ? parent.activeTab : "primary";
      const pages = parent ? parent.pages || [] : [];
      const taxonomy = parent ? parent.taxonomy : null;
      const systemPages = parent
        ? parent.systemPages || []
        : [
            { id: "home", title: "Home Page", url: "/" },
            { id: "blog", title: "Archives", url: "/category/" },
            { id: "search", title: "Search Page", url: "/search/" },
            { id: "rss", title: "RSS Feed", url: "/feed.xml" },
          ];

      const apiMenus = menusToApiShape(menus);
      const catalog = buildContentCatalog(pages);
      const taxCatalog = buildTaxonomyCatalog(taxonomy);

      this.syncSiteContext();
      const siteId = this.siteId || this.activeSiteId();
      const siteName = this.siteName || "PenCMS";

      const pagesBlock = catalog.pages.truncated
        ? `${JSON.stringify(catalog.pages.items, null, 2)}\n(${catalog.pages.note})`
        : JSON.stringify(catalog.pages.items, null, 2);
      const postsBlock = catalog.posts.truncated
        ? `${JSON.stringify(catalog.posts.items, null, 2)}\n(${catalog.posts.note})`
        : JSON.stringify(catalog.posts.items, null, 2);

      const prompt = `You are PenCMS Site Navigation Assistant.
Your purpose is to help the user manage the website's navigation menus: Primary, Secondary, and Footer.
This is a Navigation Menus surface. No content persona / Text Generation voice applies; keep assistance professional and neutral.

## Peer surfaces (routing)
You are on the **Navigation** surface. Tools on sibling admin pages are out of reach here — do not invent or call them.
- **Content Editor** (open a post/page under Posts or Pages): prose, SEO, media, authors, document writes.
- **Navigation** (admin → Navigation): Primary, Secondary, and Footer menu items.
- **Customize** (admin → Customize): Twig templates/partials and CSS in the site custom theme.
If the ask clearly belongs on another surface: say so before declining, name that admin destination, briefly what belongs there vs here, and call \`handoff_to_surface\` with a concise \`goal\` (and useful \`facts\`). That tool only prepares a handoff — the operator must Cancel or Continue in the UI; do not assume navigation happened. Do not pretend you can act on the other surface.

## Tool selection rules (read first)
- Prefer data already in this prompt (menus, Pages/Posts catalogs, Taxonomies, System Pages) over calling \`search_content\` or \`get_site_config\`.
- If an item the user wants is already in the active menu (or another slot), prefer \`reorder_menu_items\` / \`update_menu_item\` over creating a duplicate.
- Use \`create_menu_item\` with the exact target shapes in "How to add each menu item type" below. Do not invent URL patterns.
- Call \`search_content\` only when a slug is missing from the Pages/Posts catalogs. The \`query\` argument is required and is sent as a GET query parameter.
- After write tools succeed, the UI refreshes automatically — do not re-list unless verifying. \`reorder_menu_items\` already returns \`{ menu_slot, items }\` with the full updated slot.
- \`item_create.menu\` MUST equal \`menu_slot\`.
- Omit \`parent_id\` for top-level items (default null) and omit \`open_in_new_tab\` unless true (default false).
- On tool failure, the result is JSON \`{ "error": "<CODE>", "reason": "...", "hint": "..." }\`. Read \`hint\`, fix the args, and retry — do not invent a different target shape.
- Be concise and action-oriented. Do not explain tools to the user; just call them.

## Current Site
- Site ID: ${siteId}
- Name: ${siteName}
- All MCP tools operate only on this Content site. Do not assume menus or content from other sites exist or are writable.

## Current Workspace Context
Active Menu Slot: ${currentActiveTab}

### Menus (API shape — use this with tools)
Menus below use nested \`target: { type, ... }\`. The admin UI stores the same data flattened as \`target_type\` / \`content_slug\` / \`url\`; those map 1:1 to \`target.type\` / fields on \`target\`. Always send nested \`target\` in tool calls.
${JSON.stringify(apiMenus, null, 2)}

### Pages catalog (content_type: "page")
Entries where frontmatter.page === true. Public path: /{slug}/
${pagesBlock}

### Posts catalog (content_type: "post")
Entries where frontmatter.page is not true. Public path: /{slug}/
${postsBlock}

### Taxonomies (target type: "taxonomy")
${JSON.stringify(taxCatalog, null, 2)}

### System Pages (target type: "system")
${JSON.stringify(systemPages, null, 2)}

## Target field requirements
Only include the fields listed for that \`type\`. Never put \`content_type\` on taxonomy/system/custom/label.

| type | required fields |
|------|-----------------|
| content | content_slug, content_type |
| taxonomy | content_slug, url |
| system | content_slug (system page id: home, blog, search, or rss) |
| custom | url |
| label | — |

Taxonomy public URLs: see Taxonomies catalog \`url_formula\` above (canonical). Each term entry already includes a ready-to-use \`url\`.

## How to add each menu item type
Pass args as \`{ "menu_slot": "<slot>", "item_create": { ... } }\`. Examples use menu_slot "primary".

1. **Page** — static page from Pages catalog:
\`\`\`json
{"menu_slot":"primary","item_create":{"menu":"primary","label":"About","target":{"type":"content","content_slug":"about","content_type":"page"}}}
\`\`\`

2. **Post** — article from Posts catalog:
\`\`\`json
{"menu_slot":"primary","item_create":{"menu":"primary","label":"My Article","target":{"type":"content","content_slug":"my-article","content_type":"post"}}}
\`\`\`

3. **Category / taxonomy term** — from Taxonomies catalog (\`content_slug\` + \`url\` from the term entry):
\`\`\`json
{"menu_slot":"primary","item_create":{"menu":"primary","label":"Winter","target":{"type":"taxonomy","content_slug":"primary/Winter","url":"/category/winter/"}}}
\`\`\`

4. **System** — from System Pages catalog (\`content_slug\` is the system page id, not a content slug):
\`\`\`json
{"menu_slot":"primary","item_create":{"menu":"primary","label":"Archives","target":{"type":"system","content_slug":"blog","url":"/category/"}}}
\`\`\`

5. **Custom Link** (set \`open_in_new_tab\` only when true):
\`\`\`json
{"menu_slot":"footer","item_create":{"menu":"footer","label":"GitHub","target":{"type":"custom","url":"https://github.com/example"},"open_in_new_tab":true}}
\`\`\`

6. **Label** — non-link heading/separator (common for footer columns):
\`\`\`json
{"menu_slot":"footer","item_create":{"menu":"footer","label":"Legal","target":{"type":"label"}}}
\`\`\`

### Nesting (parent + child)
Max depth 2. Omit \`parent_id\` for top-level. Set \`parent_id\` only when nesting under a top-level item id in the same slot. Children cannot have children.
\`\`\`json
{"menu_slot":"footer","item_create":{"menu":"footer","label":"Privacy","target":{"type":"content","content_slug":"privacy","content_type":"page"},"parent_id":"<parent-uuid>"}}
\`\`\`

## Constraints
- Depth: only top-level (omit \`parent_id\`) or direct child of a top-level item.
- Slots: primary | secondary | footer.
- Prefer existing catalog slugs/terms over guessing.
- Do not invent a separate "categories" or "tags" vocabulary — use the Taxonomies catalog above.
- Defaults: \`parent_id\` omitted = top-level; \`open_in_new_tab\` omitted = false.`;

      const handoff = this._handoffForThisTurn || this.incomingHandoff;
      if (handoff && window.PenAiHandoff) {
        return prompt + window.PenAiHandoff.formatPromptBlock(handoff);
      }
      return prompt;
    },

    consumeIncomingHandoff(expectedTo) {
      if (!window.PenAiHandoff) return;
      const siteId = this.siteId || this.activeSiteId() || "default";
      const token = window.PenAiHandoff.consume(siteId, expectedTo);
      if (!token) return;
      this.incomingHandoff = token;
      this.expandAiAssistant();
    },

    dismissIncomingHandoff() {
      this.incomingHandoff = null;
      this._handoffForThisTurn = null;
    },

    handoffFromLabel() {
      const from = this.incomingHandoff && this.incomingHandoff.from;
      if (!from) return "";
      return window.PenAiHandoff
        ? window.PenAiHandoff.surfaceLabel(from)
        : from;
    },

    expandAiAssistant() {
      const parent =
        window.Alpine &&
        Alpine.$data(document.querySelector('[x-data="navigationSettings"]'));
      if (parent && parent.workspacePrefs) {
        parent.workspacePrefs.aiAssistantCollapsed = false;
        if (typeof parent.saveWorkspacePrefs === "function") {
          parent.saveWorkspacePrefs();
        }
      }
    },

    beginHandoffNavigate(url, to) {
      this._handoffNavigating = true;
      const label = window.PenAiHandoff
        ? window.PenAiHandoff.surfaceLabel(to)
        : to;
      this.showToast(`Opening ${label}…`);
      setTimeout(() => {
        location.assign(url);
      }, 550);
    },

    shouldPauseStreamForHandoff() {
      return !!(this._handoffNavigating || this.pendingOutgoingHandoff);
    },

    isHandoffNavNoise(err) {
      if (!this._handoffNavigating) return false;
      if (!err) return true;
      if (err.name === "AbortError") return true;
      const msg = String(err.message || err);
      return /NetworkError|Failed to fetch|Load failed|fetch resource/i.test(
        msg,
      );
    },

    isOriginDirty() {
      try {
        const parent =
          window.Alpine &&
          Alpine.$data(document.querySelector('[x-data="navigationSettings"]'));
        if (!parent) return false;
        if (typeof parent.hasChanges === "function" && parent.hasChanges()) {
          return true;
        }
        return parent.saveStatus === "unsaved";
      } catch (e) {
        return false;
      }
    },

    async saveBeforeHandoff() {
      try {
        const parent =
          window.Alpine &&
          Alpine.$data(document.querySelector('[x-data="navigationSettings"]'));
        if (!parent || typeof parent.saveChanges !== "function") return true;
        await parent.saveChanges({ silent: true });
        if (typeof parent.hasChanges === "function" && parent.hasChanges()) {
          return false;
        }
        return parent.saveStatus !== "unsaved";
      } catch (e) {
        this.showToast(e.message || "Save failed.", "error");
        return false;
      }
    },

    outgoingHandoffLabel() {
      const to = this.pendingOutgoingHandoff && this.pendingOutgoingHandoff.to;
      if (!to) return "";
      return window.PenAiHandoff
        ? window.PenAiHandoff.surfaceLabel(to)
        : to;
    },

    cancelOutgoingHandoff() {
      if (window.PenAiHandoff) {
        window.PenAiHandoff.clear(this.siteId || this.activeSiteId() || "default");
      }
      this.pendingOutgoingHandoff = null;
      this._handoffConfirmBusy = false;
      this.showToast("Handoff cancelled — staying here.");
    },

    async confirmOutgoingHandoff() {
      const pending = this.pendingOutgoingHandoff;
      if (!pending || this._handoffConfirmBusy || this._handoffNavigating) return;

      const dirty = this.isOriginDirty();
      if (dirty) {
        if (pending.saveChoice !== "save" && pending.saveChoice !== "discard") {
          this.showToast("Choose whether to save your changes first.", "error");
          return;
        }
        if (pending.saveChoice === "save") {
          this._handoffConfirmBusy = true;
          try {
            const ok = await this.saveBeforeHandoff();
            if (!ok) return;
          } finally {
            this._handoffConfirmBusy = false;
          }
        }
      }

      const { url, to } = pending;
      this.pendingOutgoingHandoff = null;
      this.beginHandoffNavigate(url, to);
    },

    continueIncomingHandoff() {
      if (!this.incomingHandoff || this.streaming) return;
      const goal = (this.incomingHandoff.goal || "").trim();
      if (!goal) return;
      this.prompt = goal;
      this.sendPrompt();
    },

    handoff_to_surface(args) {
      if (!window.PenAiHandoff) {
        return { error: "Handoff helper unavailable." };
      }
      if (this.pendingOutgoingHandoff) {
        return {
          error:
            "A handoff is already waiting for confirmation. Ask the operator to Cancel or Continue first.",
        };
      }
      const siteId = this.siteId || this.activeSiteId() || "default";
      const result = window.PenAiHandoff.executeHandoff(
        args || {},
        "navigation",
        siteId,
      );
      if (result.error) return result;
      this.pendingOutgoingHandoff = {
        to: result.to,
        url: result.url,
        goal: result.goal || (args && args.goal) || "",
        saveChoice: null,
      };
      this.expandAiAssistant();
      this.showToast("Confirm handoff with Cancel or Continue below.");
      this.$nextTick(() => this.scrollToBottom());
      return {
        ok: true,
        pending_confirmation: true,
        to: result.to,
        message:
          "Handoff ready. Waiting for the operator to Cancel or Continue in the chat UI — do not assume navigation happened.",
      };
    },

    async sendPrompt() {
      if (!this.prompt.trim() || this.streaming) return;

      if (window.VAULT?.ready) await window.VAULT.ready;

      if (!window.VAULT?.unlocked) {
        this.showToast("Unlock vault first.", "error");
        return;
      }

      const ai = window.VAULT.getSecret("AI_PROVIDER_CONFIG");
      if (!ai) {
        this.showToast("Configure an AI provider in Vault first.", "error");
        return;
      }

      const userText = this.prompt;
      this.prompt = "";
      this.messages.push({ role: "user", content: userText });
      this.saveMessages();
      this.$nextTick(() => {
        this.scrollToBottom();
        const ta = document.getElementById("ai-prompt-textarea");
        if (ta) this.autoGrow(ta);
      });

      this.streaming = true;
      let wordIdx = 0;
      this.streamingWord = this._streamingWords[wordIdx];
      this._streamingWordTimer = setInterval(() => {
        wordIdx = (wordIdx + 1) % this._streamingWords.length;
        this.streamingWord = this._streamingWords[wordIdx];
      }, 3000);

      this.abortController = new AbortController();

      try {
        await this.streamCompletion();
      } catch (err) {
        if (!this.isHandoffNavNoise(err)) {
          this.showToast(err.message, "error");
          this.messages.push({ role: "assistant", content: `Error: ${err.message}` });
          this.saveMessages();
        }
      } finally {
        this.streaming = false;
        if (this._streamingWordTimer) {
          clearInterval(this._streamingWordTimer);
          this._streamingWordTimer = null;
        }
        this.abortController = null;
        if (!this._handoffNavigating) {
          this.focusPrompt();
        }
      }
    },

    async streamCompletion() {
      if (this._handoffNavigating) return;

      if (this._handoffTurnDepth == null) this._handoffTurnDepth = 0;
      if (this._handoffTurnDepth === 0) {
        this._handoffForThisTurn = this.incomingHandoff;
        this.incomingHandoff = null;
      }
      this._handoffTurnDepth += 1;

      const apiBase = window.AUTH.apiBase.replace("/v1", "");
      try {
        const systemPrompt = this.buildSystemPrompt();

        const payloadMessages = [
          { role: "system", content: systemPrompt },
          ...this.messages.filter(m => m.role !== "system")
        ];

        const requestBody = {
          messages: payloadMessages,
          stream: true,
          tools: TOOL_DEFINITIONS,
          tool_choice: "auto",
          surface: "navigation",
        };

        const response = await fetch(`${apiBase}/ai/chat`, {
          method: "POST",
          headers: window.AUTH.getHeaders(),
          body: JSON.stringify(requestBody),
          signal: this.abortController.signal
        });

        if (!response.ok) {
          const errJson = await response.json().catch(() => ({ detail: "Unknown error" }));
          throw new Error(errJson.detail?.message || errJson.detail || response.statusText);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        this.messages.push({ role: "assistant", content: "" });
        this.saveMessages();
        const assistantIdx = this.messages.length - 1;
        this.$nextTick(() => this.scrollToBottom());

        this._pendingToolCalls = {};

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop();

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed || !trimmed.startsWith("data:")) continue;

            const data = trimmed.slice(5).trim();
            if (data === "[DONE]") continue;

            try {
              const json = JSON.parse(data);
              const delta = json.choices?.[0]?.delta;
              if (delta) {
                if (delta.content) {
                  this.messages[assistantIdx].content += delta.content;
                  this.$nextTick(() => this.scrollToBottom());
                }
                if (delta.tool_calls) {
                  for (const tc of delta.tool_calls) {
                    const idx = tc.index;
                    if (!this._pendingToolCalls[idx]) {
                      this._pendingToolCalls[idx] = {
                        id: tc.id || "",
                        type: "function",
                        function: { name: "", arguments: "" }
                      };
                    }
                    if (tc.id) this._pendingToolCalls[idx].id = tc.id;
                    if (tc.function?.name) this._pendingToolCalls[idx].function.name += tc.function.name;
                    if (tc.function?.arguments) this._pendingToolCalls[idx].function.arguments += tc.function.arguments;
                  }
                  this.$nextTick(() => this.scrollToBottom());
                }
              }
            } catch (e) {}
          }
        }

        const toolCalls = Object.values(this._pendingToolCalls);
        if (toolCalls.length > 0) {
          this.messages[assistantIdx].tool_calls = toolCalls.map(tc => ({
            id: tc.id,
            type: "function",
            function: { name: tc.function.name, arguments: tc.function.arguments }
          }));
          this.saveMessages();

          for (const tc of toolCalls) {
            let result;
            try {
              const args = tc.function.arguments ? JSON.parse(tc.function.arguments) : {};
              result = await this.executeTool(tc.function.name, args);
            } catch (e) {
              result = toolError(
                "BAD_ARGUMENTS",
                `Failed to parse tool arguments: ${e.message}`,
                "Send valid JSON args matching the tool schema."
              );
            }

            this.messages.push({
              role: "tool",
              name: tc.function.name,
              tool_call_id: tc.id,
              content: JSON.stringify(result)
            });
            this.saveMessages();
          }
          this._pendingToolCalls = {};
          this.$nextTick(() => this.scrollToBottom());

          // Recurse to let LLM respond to tool output (skip when handoff pending/navigating)
          if (!this.shouldPauseStreamForHandoff()) {
            await this.streamCompletion();
          }
        } else {
          this.saveMessages();
        }
      } finally {
        this._handoffTurnDepth -= 1;
        if (this._handoffTurnDepth <= 0) {
          this._handoffTurnDepth = 0;
          this._handoffForThisTurn = null;
        }
      }
    },

    async executeTool(functionName, args) {
      if (functionName === "handoff_to_surface") {
        return this.handoff_to_surface(args);
      }
      if (MCP_TOOL_MAP[functionName]) {
        const preflight = preflightNavTool(functionName, args);
        if (preflight) return preflight;

        try {
          const result = await this.executeMcpToolOnServer(functionName, args);
          
          const isWriteAction = [
            "create_menu_item", "update_menu_item", "delete_menu_item",
            "reorder_menu_items", "clear_menu_slot", "replace_menu_slot"
          ].includes(functionName);
          
          if (isWriteAction && !result.error) {
            const parent = window.Alpine && Alpine.$data(document.querySelector('[x-data="navigationSettings"]'));
            if (parent && typeof parent.fetchMenus === "function") {
              await parent.fetchMenus();
            }
            this.showToast("Menus structure synchronized with server.");
          }

          // Surface full slot after reorder so the model can verify without list_menu_items.
          if (
            functionName === "reorder_menu_items" &&
            !result.error &&
            Array.isArray(result)
          ) {
            return { menu_slot: args.menu_slot, items: result };
          }

          return result;
        } catch (e) {
          return shapeMcpError(e);
        }
      }
      return toolError(
        "UNKNOWN_TOOL",
        `Tool not implemented yet: ${functionName}`,
        "Use one of the navigation tools listed in the system prompt."
      );
    },

    async executeMcpToolOnServer(functionName, args) {
      return window.PenMcpClient.executeMcpTool({
        functionName,
        args,
        toolMap: MCP_TOOL_MAP,
        unwrapBodyKeys: [
          "item_create",
          "item_update",
          "reorder_items",
          "items",
        ],
      });
    },

    cleanup() {
      if (this.abortController) {
        this.abortController.abort();
        this.abortController = null;
      }
      this.streaming = false;
      if (this._streamingWordTimer) {
        clearInterval(this._streamingWordTimer);
        this._streamingWordTimer = null;
      }
      this.focusPrompt();
    },

    handlePaste(e) {
      // No-op for navigation AI assistant
    },

    saveMessages() {
      sessionStorage.setItem(
        this.chatStorageKey("pen_nav_messages"),
        JSON.stringify(this.messages),
      );
    }
  }));
});

// Click delegation for copy-code-btn (copied from ai-sidebar.js)
document.addEventListener("click", (e) => {
  const btn = e.target.closest(".copy-code-btn");
  if (!btn) return;

  if (!navigator.clipboard) {
    console.warn("Clipboard access not supported in this browser.");
    return;
  }
  const pre = btn.previousElementSibling;
  if (!pre) return;
  const code = pre.querySelector("code");
  if (!code) return;

  const text = code.textContent;

  navigator.clipboard
    .writeText(text)
    .then(() => {
      const aiSidebarEl = document.querySelector('[x-data="aiSidebar"]');
      if (aiSidebarEl && window.Alpine) {
        const aiSidebar = window.Alpine.$data(aiSidebarEl);
        if (aiSidebar && typeof aiSidebar.showToast === "function") {
          aiSidebar.showToast("Copied code block to clipboard.");
        }
      }

      const originalHTML = btn.innerHTML;
      btn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" class="w-4 h-4"><rect width="256" height="256" fill="none"/><polyline points="40 144 96 200 224 72" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="24"/></svg>`;
      btn.classList.add("text-green-600");
      btn.classList.remove("text-forge-mid", "hover:text-rust");

      setTimeout(() => {
        btn.innerHTML = originalHTML;
        btn.classList.remove("text-green-600");
        btn.classList.add("text-forge-mid", "hover:text-rust");
      }, 2000);
    })
    .catch((err) => {
      console.error("Failed to copy code block: ", err);
    });
});
