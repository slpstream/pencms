/**
 * PenCMS AI Sidebar Controller for Theme Customize (ai-sidebar-customize.js)
 * Alpine.js component for theme-file tools (Twig + assets/css) — not content-editor / menus.
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
      return sanitizeAiMarkdownHtml(html);
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
    image({ href, title, text }) {
      const alt = escapeHtml(text || "");
      let attrs = `src="${escapeHtml(href)}" alt="${alt}"`;
      if (title) attrs += ` title="${escapeHtml(title)}"`;
      return `<img ${attrs} class="max-h-40 rounded border border-border my-1" style="display:block" />`;
    },
  },
});
md.use({ gfm: true, breaks: true });

function toolError(error, reason, hint, extra) {
  const out = { error, reason, hint };
  if (extra && typeof extra === "object") {
    Object.assign(out, extra);
  }
  return out;
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
    if (detail.reason) return String(detail.reason);
    if (detail.message) return String(detail.message);
    return JSON.stringify(detail);
  }
  return String(detail);
}

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
      "Unlock the vault and ensure the AI provider / MCP token has write scope.",
    );
  }

  const structured =
    rawDetail && typeof rawDetail === "object" && !Array.isArray(rawDetail)
      ? rawDetail
      : null;

  const inspectCodes = {
    PREVIEW_UNREACHABLE: true,
    BROWSER_UNAVAILABLE: true,
    PATH_REJECTED: true,
    SELECTOR_NOT_FOUND: true,
    INVALID_SELECTOR: true,
    INVALID_VIEWPORT: true,
    SCREENSHOT_CACHE_MISS: true,
  };
  if (structured && structured.error && inspectCodes[structured.error]) {
    return toolError(
      structured.error,
      structured.reason || reason,
      structured.hint || "",
    );
  }

  if (
    (structured && structured.error === "DESTRUCTIVE_WRITE") ||
    /DESTRUCTIVE_WRITE/i.test(reason)
  ) {
    const expectedSize =
      structured && structured.expected_size != null
        ? structured.expected_size
        : null;
    const revertAvailable =
      structured && typeof structured.revert_available === "boolean"
        ? structured.revert_available
        : /revert_available=true\b/i.test(reason) &&
          !/revert_available=false\b/i.test(reason);
    const reasonText =
      (structured && structured.reason) || reason;
    const hint =
      (structured && structured.hint) ||
      (revertAvailable
        ? `Prefer patch_theme_file for section edits. If a prior write corrupted the file, call revert_theme_file first. To force full overwrite, re-read and resubmit with force=true and expected_size=${expectedSize != null ? expectedSize : "<on-disk-bytes>"}.`
        : `Prefer patch_theme_file for section edits. No revision history for this path — do not call revert_theme_file. To force full overwrite, re-read and resubmit with force=true and expected_size=${expectedSize != null ? expectedSize : "<on-disk-bytes>"}.`);
    const extra = {
      revert_available: revertAvailable,
    };
    if (expectedSize != null) {
      extra.expected_size = expectedSize;
    }
    if (revertAvailable) {
      extra.suggested_action = "revert_theme_file";
    }
    return toolError("DESTRUCTIVE_WRITE", reasonText, hint, extra);
  }

  if (/TARGET_NOT_FOUND/i.test(reason)) {
    return toolError(
      "TARGET_NOT_FOUND",
      reason,
      "Target was not found exactly. Fuzzy fallback only covers CRLF→LF and whole-line trim (leading/trailing whitespace on full lines) — not internal or mid-line spaces. Re-read the file and copy the exact target bytes including whitespace.",
    );
  }

  if (/TARGET_AMBIGUOUS/i.test(reason)) {
    return toolError(
      "TARGET_AMBIGUOUS",
      reason,
      "Target text matched multiple places. Include more surrounding lines/context in target to make it unique.",
    );
  }

  if (/NO_REVISION/i.test(reason)) {
    return toolError(
      "NO_REVISION",
      reason,
      "No prior revision history exists for this file.",
    );
  }

  if (/theme\.json|allowlist|Slice|not writable|path|confinement|escape/i.test(reason)) {
    return toolError(
      "PATH_REJECTED",
      reason,
      "Only templates/** and partials/** (.html.twig / .twig) or assets/css/** (.css). Never write theme.json, fonts, images, or JS.",
    );
  }

  if (status === 400 || status === 404) {
    return toolError(
      "THEME_ERROR",
      reason,
      "Call get_theme_context / list_theme_files, then retry with an allowlisted path. Fork first if no site theme tree exists.",
    );
  }

  return toolError(
    "TOOL_FAILED",
    reason,
    "Inspect the error, adjust arguments, and retry.",
  );
}

function getCustomizeParent() {
  const el = document.querySelector('[x-data="customize"]');
  return el && window.Alpine ? Alpine.$data(el) : null;
}

const TOOL_DEFINITIONS = [
  {
    type: "function",
    function: {
      name: "get_theme_context",
      description:
        "Return site theme context: exists, active, parent, name, allowlist, preview (path, header_control, live_serves_custom). Call first when unsure whether a custom tree exists. preview.path is the public /blog/?site= URL; live_serves_custom is true only when the live site is serving this custom tree.",
      parameters: { type: "object", properties: {} },
    },
  },
  {
    type: "function",
    function: {
      name: "validate_theme",
      description:
        "Run structural validation on the site custom theme tree. Returns {ok, errors[], warnings[], error_count, warning_count}. Each issue includes severity ('error' or 'warning'). Advisory only — server never blocks writes. You may self-gate on ok===false / error_count>0; warnings alone should not stop writes. Prefer after Twig edits or before publish.",
      parameters: { type: "object", properties: {} },
    },
  },
  {
    type: "function",
    function: {
      name: "list_theme_files",
      description:
        "List allowlisted theme files under the site theme tree (templates/**, partials/**, assets/css/**) along with bytes and lines metadata.",
      parameters: { type: "object", properties: {} },
    },
  },
  {
    type: "function",
    function: {
      name: "read_theme_file",
      description:
        "Read an allowlisted theme file (Twig or CSS) by relative path. Returns content, size/bytes, line count, and a version token (mtime). If the file is unchanged since the last full read, the harness may omit content (unchanged=true).",
      parameters: {
        type: "object",
        properties: {
          path: {
            type: "string",
            description:
              "Relative path e.g. partials/nav.twig, templates/index.html.twig, or assets/css/styles.css",
          },
        },
        required: ["path"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "write_theme_file",
      description:
        "FULL REPLACEMENT of an allowlisted theme file on disk. For a single-section change, prefer patch_theme_file. Only use this tool for new files or full intentional rewrites. Editable: templates/** and partials/** (.html.twig / .twig), plus assets/css/** (.css only). Never write theme.json, fonts, images, or JS. Guardrail blocks shrinking writes (>80% reduction) unless force=true and matching expected_size are provided; errors report both expected and on-disk sizes when they differ. Success returns created/overwritten (mutually exclusive), previous_size when overwritten, guarded (true only on destructive-write override), and hint.",
      parameters: {
        type: "object",
        properties: {
          path: {
            type: "string",
            description: "Relative path under site theme/",
          },
          content: {
            type: "string",
            description: "Full file contents to persist",
          },
          force: {
            type: "boolean",
            description:
              "Set true to override DESTRUCTIVE_WRITE guardrail when shrinking file",
          },
          expected_size: {
            type: "integer",
            description:
              "Current on-disk byte size required when force=true (must match exactly)",
          },
        },
        required: ["path", "content"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "patch_theme_file",
      description:
        "Context-anchored section edit on an allowlisted theme file. Preferred primitive for editing sections/blocks. Replaces unique target text with replacement. Exact match first; if that fails, limited fuzzy fallback: crlf (CRLF→LF) then line_trim (whole-line leading/trailing strip only). match_mode only affects finding the target — replacement is always written literally (not trimmed/re-indented). Does NOT collapse internal or mid-line whitespace — re-read and copy exact bytes. Pass dry_run=true to preview matched_at_line, match_mode, and unified_diff without writing. Success returns created=false, overwritten=true, guarded=false, and hint.",
      parameters: {
        type: "object",
        properties: {
          path: {
            type: "string",
            description: "Relative path under site theme/",
          },
          target: {
            type: "string",
            description:
              "Unique target string to replace. Prefer exact on-disk bytes. Fuzzy fallback: CRLF→LF, or whole-line trim — not mid-line/internal spaces.",
          },
          replacement: {
            type: "string",
            description: "New replacement text",
          },
          dry_run: {
            type: "boolean",
            description:
              "If true, return match metadata and unified_diff without writing to disk",
          },
        },
        required: ["path", "target", "replacement"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "revert_theme_file",
      description:
        "Revert an allowlisted theme file to its last saved snapshot prior to the latest write/patch operation. Suggested after a bad write or when DESTRUCTIVE_WRITE indicates recovery is needed. Not the same as reset_theme_file (parent install restore).",
      parameters: {
        type: "object",
        properties: {
          path: {
            type: "string",
            description: "Relative path under site theme/",
          },
        },
        required: ["path"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "reset_theme_file",
      description:
        "Restore one allowlisted theme file from the parent install theme (theme.json.parent). No snapshot/history — stock restore, not undo-last-write (use revert_theme_file for that). Use when a file is mangled, the snapshot is gone, and you do not want whole-tree reset_site_theme. Fails if the path has no original on the parent.",
      parameters: {
        type: "object",
        properties: {
          path: {
            type: "string",
            description: "Relative path under site theme/",
          },
        },
        required: ["path"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "fork_site_theme",
      description:
        "Copy an install base into this site's private theme tree and set theme=custom. Use when get_theme_context.exists is false. Optional parent slug.",
      parameters: {
        type: "object",
        properties: {
          parent: {
            type: "string",
            description: "Install base slug to fork; omit to infer from effective theme",
          },
        },
      },
    },
  },
  {
    type: "function",
    function: {
      name: "reset_site_theme",
      description:
        "Re-copy the site theme tree from theme.json.parent (destroys local Twig edits). Prefer only when the user asks to reset.",
      parameters: { type: "object", properties: {} },
    },
  },
  {
    type: "function",
    function: {
      name: "get_site_config",
      description:
        "Returns CMS configuration. Prefer theme context already in the system prompt; call only if site identity is missing.",
      parameters: { type: "object", properties: {} },
    },
  },
  {
    type: "function",
    function: {
      name: "describe_element",
      description:
        "Inspect the live public preview for this site: computed style subset and same-origin matched CSS rules for the first match of one CSS selector. Returns match_count, computed (display, position, box model, overflow, flex/grid, font-size, color, background), matched_rules (selector, href, specificity, winning_props), and theme_active. Use for cascade / 'who won?' questions instead of telling the user to Preview. CSS only (max 200 chars; no xpath= / js=). Optional path (relative /blog/, default /blog/) and viewport (desktop 1280x800 or mobile 390x844). Inactive custom theme still succeeds with theme_active=false and a hint.",
      parameters: {
        type: "object",
        properties: {
          selector: {
            type: "string",
            description: "CSS selector (one). The first match is described; match_count is the live total.",
          },
          path: {
            type: "string",
            description: "Relative /blog/ path. Default /blog/. Absolute URLs are rejected.",
          },
          viewport: {
            type: "string",
            description: "desktop (1280x800) or mobile (390x844). Default desktop.",
          },
        },
        required: ["selector"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "get_layout_boxes",
      description:
        "Inspect the live public preview for this site: layout boxes for 1–20 CSS selectors (first match each): x, y, w, h, visible, plus clipping_ancestor when an ancestor has overflow hidden/auto/scroll. Use for collision / overflow / geometry questions instead of telling the user to Preview. Partial misses do not fail: hit selectors return boxes, misses are listed in missing with candidates (ready-to-use selectors from the live DOM, scoped by landmark, e.g. header .nav-menu); SELECTOR_NOT_FOUND only when nothing matched. CSS only (max 200 chars each; no xpath= / js=). Optional path (relative /blog/) and viewport (desktop or mobile). Inactive custom theme still succeeds with theme_active=false and a hint.",
      parameters: {
        type: "object",
        properties: {
          selectors: {
            type: "array",
            items: { type: "string" },
            description: "CSS selectors (1–20). One box per selector (first match).",
          },
          path: {
            type: "string",
            description: "Relative /blog/ path. Default /blog/. Absolute URLs are rejected.",
          },
          viewport: {
            type: "string",
            description: "desktop (1280x800) or mobile (390x844). Default desktop.",
          },
        },
        required: ["selectors"],
      },
    },
  },
  {
    type: "function",
    function: {
      name: "get_accessible_snapshot",
      description:
        "Inspect the live public preview for this site: compact accessibility tree {role, name, visible, children[]} for an optional root CSS selector (omit for the document). Caps: max depth 8, max 80 nodes, names truncated to 120 chars; truncated=true when a cap fired. Use for 'is it in the brand/nav?' questions. CSS only (max 200 chars; no xpath= / js=). Optional path (relative /blog/) and viewport (desktop or mobile). Inactive custom theme still succeeds with theme_active=false and a hint.",
      parameters: {
        type: "object",
        properties: {
          root: {
            type: "string",
            description: "Optional CSS selector to scope the tree. Omit for the document.",
          },
          path: {
            type: "string",
            description: "Relative /blog/ path. Default /blog/. Absolute URLs are rejected.",
          },
          viewport: {
            type: "string",
            description: "desktop (1280x800) or mobile (390x844). Default desktop.",
          },
        },
      },
    },
  },
  {
    type: "function",
    function: {
      name: "get_render_fingerprint",
      description:
        "Hash of the live public preview viewport (or a clipped element) as 16-byte hex plus PNG width/height. No pixels are returned. Use as a cheap before/after tripwire after CSS or Twig writes. Optional selector clip (CSS only, max 200 chars; no xpath= / js=), path (relative /blog/), and viewport (desktop or mobile). Inactive custom theme still succeeds with theme_active=false and a hint.",
      parameters: {
        type: "object",
        properties: {
          selector: {
            type: "string",
            description: "Optional CSS selector clip. Omit for the full viewport.",
          },
          path: {
            type: "string",
            description: "Relative /blog/ path. Default /blog/. Absolute URLs are rejected.",
          },
          viewport: {
            type: "string",
            description: "desktop (1280x800) or mobile (390x844). Default desktop.",
          },
        },
      },
    },
  },
  {
    type: "function",
    function: {
      name: "capture_theme_screenshot",
      description:
        "Screenshot the live public preview viewport or a clipped element. Default returns hash/width/height only (no pixels) so text-only models stay safe. Set include_image=true only when the operator asks to see pixels or a fingerprint changed, and prefer a CSS selector clip. Optional full_page is height-capped; selector clip wins. Inactive custom theme still succeeds with theme_active=false and a hint. The harness may attach a clip or the server returns a text description — do not invent a vision-describe tool.",
      parameters: {
        type: "object",
        properties: {
          selector: {
            type: "string",
            description: "Optional CSS selector clip. Omit for the viewport. Prefer clip over full viewport.",
          },
          path: {
            type: "string",
            description: "Relative /blog/ path. Default /blog/. Absolute URLs are rejected.",
          },
          viewport: {
            type: "string",
            description: "desktop (1280x800) or mobile (390x844). Default desktop.",
          },
          full_page: {
            type: "boolean",
            description: "Height-capped full page. Ignored when selector is set. Default false.",
          },
          include_image: {
            type: "boolean",
            description: "If true, include mime + data_url when the payload is under 100KB. Default false (omit pixels).",
          },
        },
      },
    },
  },
];

if (window.PenAiHandoff && window.PenAiHandoff.TOOL_DEFINITION) {
  TOOL_DEFINITIONS.push(window.PenAiHandoff.TOOL_DEFINITION);
}

const MCP_TOOL_MAP = {
  list_theme_files: { method: "GET", path: "/mcp/theme/files" },
  read_theme_file: { method: "GET", path: "/mcp/theme/file" },
  write_theme_file: { method: "PUT", path: "/mcp/theme/file" },
  patch_theme_file: { method: "PATCH", path: "/mcp/theme/file" },
  revert_theme_file: { method: "POST", path: "/mcp/theme/file/revert" },
  reset_theme_file: { method: "POST", path: "/mcp/theme/file/reset" },
  get_theme_context: { method: "GET", path: "/mcp/theme/context" },
  validate_theme: { method: "GET", path: "/mcp/theme/validate" },
  fork_site_theme: { method: "POST", path: "/mcp/theme/fork" },
  reset_site_theme: { method: "POST", path: "/mcp/theme/reset" },
  get_site_config: { method: "GET", path: "/mcp/site-config" },
  describe_element: { method: "POST", path: "/mcp/theme/inspect/element" },
  get_layout_boxes: { method: "POST", path: "/mcp/theme/inspect/boxes" },
  get_accessible_snapshot: { method: "POST", path: "/mcp/theme/inspect/a11y" },
  get_render_fingerprint: { method: "POST", path: "/mcp/theme/inspect/fingerprint" },
  capture_theme_screenshot: { method: "POST", path: "/mcp/theme/inspect/screenshot" },
};

const WRITE_TOOLS = [
  "write_theme_file",
  "patch_theme_file",
  "revert_theme_file",
  "reset_theme_file",
  "fork_site_theme",
  "reset_site_theme",
];

function registerCustomizeAiSidebar() {
  Alpine.data("aiSidebar", () => ({
    messages: [],
    prompt: "",
    attachedFiles: [],
    attachedImages: [],
    streaming: false,
    streamingWord: "STREAMING...",
    _streamingWordTimer: null,
    _streamingWords: [
      "STREAMING...", "SLEUTHING...", "THINKING...", "FIGURING...",
      "HONING...", "CRYSTALLIZING...", "PICTURING...", "PONDERING...",
      "FATHOMING...", "SIFTING...", "MULLING...", "WEIGHING...",
      "UNTANGLING...", "MUSING...",
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
    _visionAccepted: false,
    _visionRejected: false,
    themeChangeSet: [],
    themeReadVersions: {},

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
          this.chatStorageKey("pen_customize_messages"),
        );
        this.messages = storedMessages ? JSON.parse(storedMessages) : [];
      } catch (e) {
        this.messages = [];
      }
      try {
        const storedSet = sessionStorage.getItem(
          this.chatStorageKey("pen_customize_changeset"),
        );
        this.themeChangeSet = storedSet ? JSON.parse(storedSet) : [];
        if (!Array.isArray(this.themeChangeSet)) this.themeChangeSet = [];
      } catch (e) {
        this.themeChangeSet = [];
      }
      try {
        const storedVers = sessionStorage.getItem(
          this.chatStorageKey("pen_customize_read_versions"),
        );
        this.themeReadVersions = storedVers ? JSON.parse(storedVers) : {};
        if (
          !this.themeReadVersions ||
          typeof this.themeReadVersions !== "object" ||
          Array.isArray(this.themeReadVersions)
        ) {
          this.themeReadVersions = {};
        }
      } catch (e) {
        this.themeReadVersions = {};
      }
      this._restoreVisionFlagsFromMessages();
    },

    async init() {
      this.syncSiteContext();
      this.loadChatStateForSite();
      this.consumeIncomingHandoff("customize");

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
      sessionStorage.removeItem(this.chatStorageKey("pen_customize_messages"));
      sessionStorage.removeItem(this.chatStorageKey("pen_customize_changeset"));
      sessionStorage.removeItem(this.chatStorageKey("pen_customize_read_versions"));
      this.messages = [];
      this.attachedFiles = [];
      this.attachedImages = [];
      this._visionAccepted = false;
      this._visionRejected = false;
      this.themeChangeSet = [];
      this.themeReadVersions = {};
      this.showToast("New conversation started.");
    },

    showToast(message, type = "success") {
      window.dispatchEvent(
        new CustomEvent("pen:toast", { detail: { message, type } }),
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
      if (e.shiftKey) return;
      e.preventDefault();
      if (
        !this.streaming &&
        (this.prompt.trim() ||
          this.attachedFiles.length > 0 ||
          this.attachedImages.length > 0)
      )
        this.sendPrompt();
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
        // Empty displayContent is valid (image-only send). Do not fall through
        // to the multimodal array — bubble thumbs already render attachedImages.
        content =
          msgOrContent.displayContent != null
            ? msgOrContent.displayContent
            : msgOrContent.content || "";
        role = msgOrContent.role || "assistant";
        name = msgOrContent.name || "";
        toolCalls = msgOrContent.tool_calls || null;

        if (Array.isArray(content)) {
          const textParts = content
            .filter((p) => p.type === "text" && p.text)
            .map((p) => p.text);
          const hasBubbleThumbs =
            Array.isArray(msgOrContent.attachedImages) &&
            msgOrContent.attachedImages.length > 0;
          const imageParts = hasBubbleThumbs
            ? []
            : content.filter((p) => p.type === "image_url");
          let html = "";
          if (textParts.length) {
            html += textParts.join("\n\n");
          }
          if (imageParts.length) {
            html += "\n\n";
            for (const img of imageParts) {
              const url = img.image_url?.url || "";
              if (url) {
                html += `<img src="${url}" class="max-h-40 rounded border border-border my-1" style="display:block" />`;
              }
            }
          }
          content = html;
        }
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
      const parent = getCustomizeParent();
      const files = parent && Array.isArray(parent.files) ? parent.files : [];
      const selectedPath = parent ? parent.selectedPath : null;
      const context = parent && parent.context ? parent.context : {};
      const dirty = parent ? !!parent.dirty : false;

      this.syncSiteContext();
      const siteId = this.siteId || this.activeSiteId();
      const siteName = this.siteName || "PenCMS";

      const prompt = `You are PenCMS Theme Customize Assistant.
Your purpose is to help the operator edit Twig templates/partials and CSS under assets/css/ in this site's private custom theme tree.
This is a Theme Customization surface (Twig/CSS). No content persona / Text Generation voice applies; keep assistance professional and neutral.

## Peer surfaces (routing)
You are on the **Customize (Theme)** surface. Tools on sibling admin pages are out of reach here — do not invent or call them.
- **Content Editor** (open a post/page under Posts or Pages): prose, SEO, media, authors, document writes.
- **Navigation** (admin → Navigation): Primary, Secondary, and Footer menu items.
- **Customize** (admin → Customize): Twig templates/partials and CSS in the site custom theme.
If the ask clearly belongs on another surface: say so before declining, name that admin destination, briefly what belongs there vs here, and call \`handoff_to_surface\` with a concise \`goal\` (and useful \`facts\`). That tool only prepares a handoff — the operator must Cancel or Continue in the UI; do not assume navigation happened. Do not pretend you can act on the other surface.

## Tool selection rules (read first)
- Prefer data already in this prompt (file inventory, open path, context, this conversation's change-set) for discovery over re-listing unless verifying. Treat write/patch result fields \`created\` / \`overwritten\` / \`guarded\` / \`hint\` as authoritative for what just happened on disk — not the inventory alone. The change-set lists files you wrote this chat; prefer it over re-listing. Still re-read a path before a patch if you need exact bytes.
- Theme context, on-disk file inventory, and Open editor below are current as of this request — do not trust earlier turns for that state.
- If context.exists is false, call \`fork_site_theme\` before writing files.
- Prefer \`patch_theme_file\` for section edits. Exact match first; fuzzy fallback is only CRLF→LF (\`match_mode: crlf\`) or whole-line leading/trailing trim (\`match_mode: line_trim\`) — not internal/mid-line whitespace. \`replacement\` is always literal (line-trim does not strip it). On \`TARGET_NOT_FOUND\`, re-read and copy exact bytes.
- Use \`patch_theme_file\` with \`dry_run=true\` to preview \`matched_at_line\`, \`match_mode\`, and \`unified_diff\` before committing a patch.
- Use \`write_theme_file\` only for new files or intentional full rewrites (must send complete file contents).
- On \`DESTRUCTIVE_WRITE\`, prefer patch or re-read + full rewrite with correct \`expected_size\` (error reports expected vs on-disk) — do not blindly set \`force\`. Call \`revert_theme_file\` only when \`suggested_action\` is \`revert_theme_file\` (or \`revert_available=true\` in the reason); otherwise there is no snapshot and revert will return \`NO_REVISION\`.
- On a bad write, call \`revert_theme_file\` before reconstructing from memory when a revision exists; otherwise re-read disk and rewrite intentionally.
- Use \`reset_theme_file\` to restore one path from the parent install theme (stock original). Prefer it over \`reset_site_theme\` when only one file is wrong. Not the same as \`revert_theme_file\` (last write snapshot).
- Human Save is only for textarea edits the operator typed; do not tell them to Save after your write.
- Prefer \`validate_theme\` after meaningful Twig or CSS edits; it returns \`{ok, errors, warnings}\` with \`severity\` on each issue and is advisory only — the server never blocks writes. You may self-gate on \`ok===false\` / \`error_count>0\`; warnings alone should not stop write/patch.
- Styling is part of the job: when adding or changing visible markup in Twig, also update matching CSS under \`assets/css/**\` (reuse existing class patterns; read styles first). Do not leave new elements unstyled unless the user asks for markup-only.
- Never write \`theme.json\`, fonts, images, or JS. Editable: \`templates/**\` and \`partials/**\` with \`.html.twig\` / \`.twig\`, plus \`assets/css/**\` with \`.css\` only.
- Operator-attached images (paste / drop / paperclip) are vision **input** only — mockups or screenshots of the live site. Never write images into the theme tree.
- Never attempt to edit install base themes under blog/themes/.
- For visual / cascade / geometry / structure questions, call inspect tools against the live preview instead of telling the user to Preview: prefer \`describe_element\` (computed style + matched CSS rules), \`get_layout_boxes\` (x/y/w/h + clipping ancestor), and \`get_accessible_snapshot\` (role/name/visible tree — “is it in the brand/nav?”) first. Use \`get_render_fingerprint\` as a cheap before/after hash after CSS/Twig writes (no pixels). Call \`capture_theme_screenshot\` when the operator asks to see pixels or the fingerprint changed; prefer a CSS selector clip. Default omits the data URL — set \`include_image=true\` only then. The harness may attach a clip as vision input, or the server returns a text \`description\` / \`findings[]\` fallback — that is not a tool you can call; do not invent a vision-describe tool. Still mention header **Preview Site** when the human should look themselves. CSS selectors only (no xpath=/js=). Never write screenshots into the theme tree.
- Preview: **Preview Site** is in the **admin header** (not a Customize control-bar button). That link opens \`context.preview.path\` (\`/blog/?site=\` for this site). The live preview matches this custom tree on disk only when \`context.active\` / \`context.preview.live_serves_custom\` is true; otherwise the public site still serves the install theme. Inspect tools still succeed in that case with \`theme_active: false\` and a hint — results describe the live render, not the custom tree on disk.
- On tool failure, the result is JSON \`{ "error": "<CODE>", "reason": "...", "hint": "..." }\`. Read \`hint\`, fix args, and retry.
- Be concise and action-oriented. Do not explain tools to the user; just call them.

## Current Site
- Site ID: ${siteId}
- Name: ${siteName}
- All MCP theme tools operate only on this Content site.

## Theme context (from Customize UI)
${JSON.stringify(context, null, 2)}
- \`context.allowlist\` is the editable path/extension **policy** only (prefixes + extensions), not a file list.
- \`context.preview\` is the human **Preview Site** pointer (\`path\`, \`header_control\`, \`live_serves_custom\`). The live site matches this custom tree only when \`live_serves_custom\` is true.

## This conversation's change-set
Files you wrote/patched/reverted/reset in this chat. Authoritative for "what I changed"; the inventory below may lag.
${this.themeChangeSet && this.themeChangeSet.length
  ? JSON.stringify(this.themeChangeSet, null, 2)
  : "[]  → nothing written this chat."}

## On-disk file inventory (request-time snapshot)
This JSON is a filtered **disk walk** of editable paths with live \`bytes\`/\`lines\` — not the allowlist schema and not a registry of planned files. Presence means the file exists on disk as of this request.
${files.length ? JSON.stringify(files, null, 2) : "(empty — fork first if context.exists is false)"}

## Open editor
- selectedPath: ${selectedPath ? JSON.stringify(selectedPath) : "null"}
- dirty (unsaved human edits): ${dirty}
- (Snapshot for this request only; operator may change selection between turns.)

## Constraints
- Registry theme id for the custom tree is the fixed string \`custom\`; parent lives only in site theme.json (service-managed).
- Prefer editing existing partials/templates over inventing new paths unless the user asks.
- After writes succeed, do not re-list unless verifying.`;

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
      const parent = getCustomizeParent();
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
        const parent = getCustomizeParent();
        return !!(parent && parent.dirty);
      } catch (e) {
        return false;
      }
    },

    async saveBeforeHandoff() {
      try {
        const parent = getCustomizeParent();
        if (!parent || typeof parent.saveFile !== "function") return true;
        await parent.saveFile();
        return !parent.dirty;
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
        "customize",
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
      if (
        (!this.prompt.trim() &&
          this.attachedFiles.length === 0 &&
          this.attachedImages.length === 0) ||
        this.streaming
      )
        return;

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

      const validImages = this.attachedImages.filter(
        (img) => img.dataUrl && !img.encoding,
      );
      const hasImages = validImages.length > 0;
      const hasTextFiles = this.attachedFiles && this.attachedFiles.length > 0;

      let textBlock = "";
      if (hasTextFiles) {
        for (const file of this.attachedFiles) {
          textBlock += `<attached_file name="${file.name}">\n${file.content}\n</attached_file>\n\n`;
        }
      }
      const userPromptText = this.prompt;
      textBlock += userPromptText;

      let contentPayload;
      if (hasImages) {
        const parts = [];
        if (textBlock.trim()) {
          parts.push({ type: "text", text: textBlock });
        }
        for (const img of validImages) {
          parts.push({
            type: "image_url",
            image_url: { url: img.dataUrl, detail: "auto" },
          });
        }
        contentPayload = parts;
      } else {
        contentPayload = textBlock;
      }

      const userMessage = { role: "user", content: contentPayload };
      userMessage.displayContent = userPromptText;
      if (hasImages) {
        userMessage.attachedImages = validImages.map((i) => ({
          name: i.name,
          dataUrl: i.dataUrl,
        }));
      }
      if (hasTextFiles) {
        userMessage.attachedFiles = this.attachedFiles.map((f) => ({
          name: f.name,
          sizeKb: Math.round(f.content.length / 100) / 10,
        }));
      }

      this.messages.push(userMessage);
      this.saveMessages();
      this.prompt = "";
      this.attachedFiles = [];
      this.attachedImages = [];
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
        this._handleStreamError(err);
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

    _isImageInputNotSupported(err) {
      return (
        err.code === "image_input_not_supported" ||
        (err.message &&
          (err.message.includes("image_input_not_supported") ||
            err.message.includes("does not support image inputs")))
      );
    },

    _handleStreamError(err) {
      if (this.isHandoffNavNoise(err)) return;
      if (this._isImageInputNotSupported(err)) {
        this._visionRejected = true;
        this.messages.push({
          role: "assistant",
          content: "",
          errorType: "image_input_not_supported",
        });
        this.saveMessages();
        return;
      }
      this.showToast(err.message, "error");
      this.messages.push({
        role: "assistant",
        content: `Error: ${err.message}`,
      });
      this.saveMessages();
    },

    async streamCompletion() {
      if (this._handoffNavigating) return;

      if (this._handoffTurnDepth == null) this._handoffTurnDepth = 0;
      if (this._handoffTurnDepth === 0) {
        this._handoffForThisTurn = this.incomingHandoff;
        this.incomingHandoff = null;
      }
      this._handoffTurnDepth += 1;

      if (!this.abortController) {
        this.abortController = new AbortController();
      }

      const apiBase = window.AUTH.apiBase.replace("/v1", "");
      try {
        const systemPrompt = this.buildSystemPrompt();

        const payloadMessages = [{ role: "system", content: systemPrompt }];
        for (const msg of this.messages) {
          if (msg.role === "system") continue;
          const m = { role: msg.role };
          if (msg.content !== undefined && msg.content !== null) {
            m.content = msg.content;
          }
          if (msg.name) m.name = msg.name;
          if (msg.tool_calls) m.tool_calls = msg.tool_calls;
          if (msg.tool_call_id) m.tool_call_id = msg.tool_call_id;
          payloadMessages.push(m);
        }

        const requestBody = {
          messages: payloadMessages,
          stream: true,
          tools: TOOL_DEFINITIONS,
          tool_choice: "auto",
          surface: "customize",
        };

        const response = await fetch(`${apiBase}/ai/chat`, {
          method: "POST",
          headers: window.AUTH.getHeaders(),
          body: JSON.stringify(requestBody),
          signal: this.abortController.signal,
        });

        if (!response.ok) {
          const errJson = await response
            .json()
            .catch(() => ({ detail: "Unknown error" }));

          let errMsg = "";
          let errCode = null;
          if (errJson.detail && typeof errJson.detail === "object") {
            errMsg = errJson.detail.message || JSON.stringify(errJson.detail);
            errCode = errJson.detail.code || null;
          } else {
            errMsg = String(errJson.detail || response.statusText);
            if (errMsg.includes("image_input_not_supported")) {
              errCode = "image_input_not_supported";
            }
          }
          const error = new Error(errMsg);
          if (errCode) error.code = errCode;
          throw error;
        }

        if (this._payloadHasImageUrl(payloadMessages)) {
          this._visionAccepted = true;
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
                        function: { name: "", arguments: "" },
                      };
                    }
                    if (tc.id) this._pendingToolCalls[idx].id = tc.id;
                    if (tc.function?.name)
                      this._pendingToolCalls[idx].function.name += tc.function.name;
                    if (tc.function?.arguments)
                      this._pendingToolCalls[idx].function.arguments +=
                        tc.function.arguments;
                  }
                  this.$nextTick(() => this.scrollToBottom());
                }
              }
            } catch (e) {}
          }
        }

        const toolCalls = Object.values(this._pendingToolCalls);
        if (toolCalls.length > 0) {
          this.messages[assistantIdx].tool_calls = toolCalls.map((tc) => ({
            id: tc.id,
            type: "function",
            function: { name: tc.function.name, arguments: tc.function.arguments },
          }));
          this.saveMessages();

          const screenshotClips = [];
          for (const tc of toolCalls) {
            let result;
            let args = {};
            try {
              args = tc.function.arguments
                ? JSON.parse(tc.function.arguments)
                : {};
              result = await this.executeTool(tc.function.name, args);
            } catch (e) {
              result = toolError(
                "BAD_ARGUMENTS",
                `Failed to parse tool arguments: ${e.message}`,
                "Send valid JSON args matching the tool schema.",
              );
            }

            let clipDataUrl = null;
            if (
              tc.function.name === "capture_theme_screenshot" &&
              result &&
              !result.error
            ) {
              const prepared = await this._prepareScreenshotToolResult(
                result,
                args,
              );
              result = prepared.result;
              clipDataUrl = prepared.clipDataUrl || null;
            }

            const toolMsg = {
              role: "tool",
              name: tc.function.name,
              tool_call_id: tc.id,
              content: JSON.stringify(result),
            };
            if (tc.function.name === "capture_theme_screenshot") {
              toolMsg._screenshotArgs = args;
            }
            this.messages.push(toolMsg);
            this.saveMessages();
            if (clipDataUrl) {
              screenshotClips.push({
                dataUrl: clipDataUrl,
                hash: result && result.hash,
              });
            }
          }
          this._pendingToolCalls = {};
          this.$nextTick(() => this.scrollToBottom());

          if (!this.shouldPauseStreamForHandoff()) {
            await this._streamAfterScreenshotTools(screenshotClips);
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
        try {
          const result = await this.executeMcpToolOnServer(functionName, args);

          if (functionName === "read_theme_file" && result && !result.error) {
            this._rememberThemeRead(result);
          }

          if (WRITE_TOOLS.includes(functionName) && !result.error) {
            const parent = getCustomizeParent();
            if (parent) {
              if (
                functionName === "write_theme_file" ||
                functionName === "patch_theme_file" ||
                functionName === "revert_theme_file" ||
                functionName === "reset_theme_file"
              ) {
                // dry_run previews must not refresh the editor or toast a write.
                if (functionName === "patch_theme_file" && result.dry_run) {
                  const dryBase =
                    result && typeof result === "object" ? result : { ok: true };
                  const dryHint =
                    dryBase.hint ||
                    "Dry-run only — nothing written. Re-call patch_theme_file without dry_run to commit.";
                  return {
                    ...dryBase,
                    hint: dryHint.includes("Re-call patch_theme_file")
                      ? dryHint
                      : `${dryHint} Re-call patch_theme_file without dry_run to commit.`,
                  };
                }
                const path =
                  (args && args.path) ||
                  (result && result.path) ||
                  null;
                if (typeof parent.refreshAfterAiWrite === "function") {
                  await parent.refreshAfterAiWrite(path);
                }
                const msgMap = {
                  write_theme_file: "Theme file synchronized with server.",
                  patch_theme_file: "Theme file patched successfully.",
                  revert_theme_file: "Theme file reverted to snapshot.",
                  reset_theme_file: "Theme file restored from parent.",
                };
                this.showToast(msgMap[functionName] || "Theme file updated.");
                const openPath = parent.selectedPath || null;
                const base =
                  result && typeof result === "object" ? result : { ok: true };
                this._recordThemeChange(functionName, base);
                const lineageHint =
                  typeof base.hint === "string" && base.hint.trim()
                    ? base.hint.trim()
                    : "";
                const validateHint =
                  "Prefer validate_theme after Twig/CSS edits (advisory only; never blocks writes).";
                return {
                  ...base,
                  open_in_editor: openPath,
                  hint: lineageHint
                    ? `${lineageHint} ${validateHint}`
                    : validateHint,
                };
              } else if (typeof parent.refreshAfterAiTreeChange === "function") {
                await parent.refreshAfterAiTreeChange();
                this._clearThemeChangeSet();
                this.showToast(
                  functionName === "fork_site_theme"
                    ? "Custom theme forked — tree refreshed."
                    : "Theme reset — tree refreshed.",
                );
              }
            }
          }

          return result;
        } catch (e) {
          return shapeMcpError(e);
        }
      }
      return toolError(
        "UNKNOWN_TOOL",
        `Tool not implemented yet: ${functionName}`,
        "Use one of the theme customize tools listed in the system prompt.",
      );
    },

    async executeMcpToolOnServer(functionName, args) {
      return window.PenMcpClient.executeMcpTool({
        functionName,
        args,
        toolMap: MCP_TOOL_MAP,
        unwrapBodyKeys: [],
        prepareArgs: (fn, requestArgs) => {
          if (fn !== "read_theme_file") return requestArgs;
          const path = requestArgs && requestArgs.path;
          const known =
            path && this.themeReadVersions
              ? this.themeReadVersions[path]
              : null;
          if (!known) return requestArgs;
          return { ...requestArgs, if_version: known };
        },
      });
    },

    _payloadHasImageUrl(payloadMessages) {
      if (!Array.isArray(payloadMessages)) return false;
      return payloadMessages.some((m) => {
        if (!m || !Array.isArray(m.content)) return false;
        return m.content.some((part) => part && part.type === "image_url");
      });
    },

    _restoreVisionFlagsFromMessages() {
      this._visionAccepted = this._payloadHasImageUrl(this.messages);
      this._visionRejected = this.messages.some(
        (m) => m && m.errorType === "image_input_not_supported",
      );
    },

    _shouldAttachScreenshot() {
      return !this._visionRejected;
    },

    _stripScreenshotBlob(result) {
      if (!result || typeof result !== "object") return result;
      const next = { ...result };
      delete next.mime;
      delete next.data_url;
      return next;
    },

    _screenshotFollowUpArgs(args, hash) {
      const out = {};
      if (args && typeof args === "object") {
        if (args.selector) out.selector = args.selector;
        if (args.path) out.path = args.path;
        if (args.viewport) out.viewport = args.viewport;
        if (args.full_page) out.full_page = args.full_page;
      }
      if (hash) out.hash = hash;
      return out;
    },

    async _fetchScreenshotClip(hash, args) {
      if (!hash) return null;
      try {
        const fetched = await this.executeMcpToolOnServer(
          "capture_theme_screenshot",
          { ...this._screenshotFollowUpArgs(args, hash), include_image: true },
        );
        if (fetched && fetched.data_url && !fetched.error) {
          return fetched.data_url;
        }
      } catch (e) {
        /* fall through to describe */
      }
      return null;
    },

    async _describeCachedScreenshot(hash, args) {
      try {
        return await this.executeMcpToolOnServer("capture_theme_screenshot", {
          ...this._screenshotFollowUpArgs(args, hash),
          describe: true,
        });
      } catch (e) {
        return shapeMcpError(e);
      }
    },

    _mergeDescribeIntoResult(result, described) {
      const next = this._stripScreenshotBlob(result);
      if (!described || typeof described !== "object") return next;
      if (described.error) {
        next.hint = [next.hint, described.reason || described.hint]
          .filter(Boolean)
          .join(" ");
        return next;
      }
      if (described.description != null) next.description = described.description;
      if (Array.isArray(described.findings)) next.findings = described.findings;
      if (described.hint) {
        next.hint = [next.hint, described.hint].filter(Boolean).join(" ");
      }
      return next;
    },

    async _prepareScreenshotToolResult(result, args) {
      const clipFromCapture = result && result.data_url ? result.data_url : null;
      const stripped = this._stripScreenshotBlob(result);
      const hash = stripped && stripped.hash;

      if (!this._shouldAttachScreenshot() || !hash) {
        const described = await this._describeCachedScreenshot(hash, args);
        return {
          result: this._mergeDescribeIntoResult(stripped, described),
          clipDataUrl: null,
        };
      }

      let dataUrl = clipFromCapture;
      if (!dataUrl) {
        dataUrl = await this._fetchScreenshotClip(hash, args);
      }
      if (!dataUrl) {
        const described = await this._describeCachedScreenshot(hash, args);
        return {
          result: this._mergeDescribeIntoResult(stripped, described),
          clipDataUrl: null,
        };
      }
      return { result: stripped, clipDataUrl: dataUrl };
    },

    _pushScreenshotFollowUp(clips) {
      const parts = [
        {
          type: "text",
          text: "Live preview clip from capture_theme_screenshot.",
        },
      ];
      const attachedImages = [];
      clips.forEach((clip, i) => {
        parts.push({
          type: "image_url",
          image_url: { url: clip.dataUrl, detail: "auto" },
        });
        attachedImages.push({
          name: `theme-screenshot-${i + 1}.png`,
          dataUrl: clip.dataUrl,
        });
      });
      this.messages.push({
        role: "user",
        content: parts,
        displayContent: "Live preview clip",
        attachedImages,
        _screenshotFollowUp: true,
      });
      this.saveMessages();
    },

    _removeScreenshotFollowUpMessages() {
      this.messages = this.messages.filter((m) => !m || !m._screenshotFollowUp);
      this.saveMessages();
    },

    async _applyScreenshotDescribeFallback() {
      for (let i = 0; i < this.messages.length; i++) {
        const msg = this.messages[i];
        if (
          !msg ||
          msg.role !== "tool" ||
          msg.name !== "capture_theme_screenshot"
        ) {
          continue;
        }
        let parsed;
        try {
          parsed = JSON.parse(msg.content);
        } catch (e) {
          continue;
        }
        if (!parsed || parsed.error || parsed.description) continue;
        const hash = parsed.hash;
        if (!hash) continue;
        const described = await this._describeCachedScreenshot(
          hash,
          msg._screenshotArgs || {},
        );
        const next = this._mergeDescribeIntoResult(parsed, described);
        msg.content = JSON.stringify(next);
      }
      this.saveMessages();
    },

    async _streamAfterScreenshotTools(screenshotClips) {
      if (screenshotClips && screenshotClips.length > 0) {
        this._pushScreenshotFollowUp(screenshotClips);
        try {
          await this.streamCompletion();
          return;
        } catch (err) {
          if (!this._isImageInputNotSupported(err)) {
            throw err;
          }
          this._visionRejected = true;
          this._removeScreenshotFollowUpMessages();
          await this._applyScreenshotDescribeFallback();
        }
      }
      await this.streamCompletion();
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
      this.attachedFiles = [];
      this.attachedImages = [];
      this.focusPrompt();
    },

    handleFileSelect(e) {
      const files = e.target.files;
      if (!files) return;
      this.addFiles(files);
      e.target.value = "";
    },

    removeAttachedImage(index) {
      this.attachedImages.splice(index, 1);
    },

    removeImageFromChatAndPending(msg, imgIdx) {
      const img = msg.attachedImages[imgIdx];
      if (!img) return;
      msg.attachedImages.splice(imgIdx, 1);
      const pendingIdx = this.attachedImages.findIndex(
        (i) => i.name === img.name,
      );
      if (pendingIdx !== -1) {
        this.attachedImages.splice(pendingIdx, 1);
      }
      this.saveMessages();
    },

    _dismissVisionErrorCard() {
      const last = this.messages[this.messages.length - 1];
      if (
        last &&
        last.role === "assistant" &&
        last.errorType === "image_input_not_supported"
      ) {
        this.messages.pop();
      }
    },

    _stripImagesFromLastUserMessage() {
      let lastUserMsgIdx = -1;
      for (let i = this.messages.length - 1; i >= 0; i--) {
        if (this.messages[i].role === "user") {
          lastUserMsgIdx = i;
          break;
        }
      }
      if (lastUserMsgIdx === -1) return false;

      const userMsg = this.messages[lastUserMsgIdx];
      if (Array.isArray(userMsg.content)) {
        const textPart = userMsg.content.find((p) => p.type === "text");
        let text = textPart ? textPart.text : "";
        text = text.replace(
          /<attached_images>[\s\S]*?<\/attached_images>\n*/g,
          "",
        );
        userMsg.content = text;
      } else if (typeof userMsg.content === "string") {
        userMsg.content = userMsg.content.replace(
          /<attached_images>[\s\S]*?<\/attached_images>\n*/g,
          "",
        );
      }
      delete userMsg.attachedImages;
      const leftover = String(
        userMsg.displayContent || userMsg.content || "",
      ).trim();
      if (!leftover) {
        this.messages.splice(lastUserMsgIdx, 1);
        return false;
      }
      return true;
    },

    clearAttachedImages() {
      this.attachedImages = [];
      this._dismissVisionErrorCard();
      this._stripImagesFromLastUserMessage();
      this.saveMessages();
      this.$nextTick(() => this.scrollToBottom());
    },

    retryWithoutImages() {
      this._dismissVisionErrorCard();
      const hasText = this._stripImagesFromLastUserMessage();
      this.attachedImages = [];
      this.saveMessages();
      this.$nextTick(() => this.scrollToBottom());
      if (hasText) this._resumeAfterVisionError();
    },

    async _resumeAfterVisionError() {
      if (this.streaming) return;
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
        this._handleStreamError(err);
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

    handleFileDrop(e) {
      const files = e.dataTransfer?.files;
      if (files && files.length > 0) {
        this.addFiles(files);
      }
    },

    handlePaste(e) {
      const items = e.clipboardData?.items;
      if (!items) return;

      const imageFiles = [];
      for (const item of items) {
        if (item.type.startsWith("image/")) {
          const file = item.getAsFile();
          if (file) imageFiles.push(file);
        }
      }

      if (imageFiles.length > 0) {
        e.preventDefault();
        this.addFiles(imageFiles);
      }
    },

    addFiles(files) {
      const IMAGE_TYPES = [
        "image/png",
        "image/jpeg",
        "image/jpg",
        "image/gif",
        "image/webp",
      ];
      const TEXT_EXTS = ["txt", "md"];
      const IMAGE_EXTS = ["png", "jpg", "jpeg", "gif", "webp"];

      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const ext = file.name.split(".").pop().toLowerCase();
        const isImage =
          IMAGE_TYPES.includes(file.type) || IMAGE_EXTS.includes(ext);
        const isText = TEXT_EXTS.includes(ext) && !isImage;

        if (!isText && !isImage) {
          this.showToast(
            `Unsupported file type: ${file.name}. Use .txt, .md, or images (.png, .jpg, .gif, .webp).`,
            "error",
          );
          continue;
        }

        if (isImage) {
          const MAX_IMAGE_BYTES = 10 * 1024 * 1024;
          if (file.size > MAX_IMAGE_BYTES) {
            this.showToast(
              `Image ${file.name} is too large. Max allowed size is 10MB.`,
              "error",
            );
            continue;
          }
          if (this.attachedImages.some((f) => f.name === file.name)) {
            this.showToast(`Image ${file.name} is already attached.`, "error");
            continue;
          }

          const initialEntry = {
            name: file.name,
            dataUrl: null,
            type: file.type,
            size: file.size,
            encoding: true,
            width: null,
            height: null,
            estimatedTokens: null,
          };
          this.attachedImages.push(initialEntry);

          const reader = new FileReader();
          reader.onload = (event) => {
            const dataUrl = event.target.result;
            const imgEl = new Image();
            imgEl.onload = () => {
              const entry = this.attachedImages.find(
                (f) => f.name === file.name && f.encoding,
              );
              if (entry) {
                entry.dataUrl = dataUrl;
                entry.width = imgEl.naturalWidth;
                entry.height = imgEl.naturalHeight;
                const maxDim = Math.max(
                  imgEl.naturalWidth,
                  imgEl.naturalHeight,
                );
                entry.estimatedTokens = maxDim > 512 ? 1100 : 85;
                entry.encoding = false;
              }
            };
            imgEl.onerror = () => {
              const entry = this.attachedImages.find(
                (f) => f.name === file.name && f.encoding,
              );
              if (entry) {
                entry.dataUrl = dataUrl;
                entry.encoding = false;
              }
            };
            imgEl.src = dataUrl;
          };
          reader.onerror = () => {
            this.showToast(`Error reading image: ${file.name}`, "error");
            const idx = this.attachedImages.findIndex(
              (f) => f.name === file.name && f.encoding,
            );
            if (idx !== -1) {
              this.attachedImages.splice(idx, 1);
            }
          };
          reader.readAsDataURL(file);
        } else {
          const reader = new FileReader();
          reader.onload = (event) => {
            const content = event.target.result;
            if (content.length > 50000) {
              this.showToast(
                `File ${file.name} is too large. Max allowed size is 50KB.`,
                "error",
              );
              return;
            }
            if (this.attachedFiles.some((f) => f.name === file.name)) {
              this.showToast(`File ${file.name} is already attached.`, "error");
              return;
            }
            this.attachedFiles.push({
              name: file.name,
              content: content,
            });
          };
          reader.onerror = () => {
            this.showToast(`Error reading file: ${file.name}`, "error");
          };
          reader.readAsText(file);
        }
      }
    },

    removeAttachedFile(index) {
      this.attachedFiles.splice(index, 1);
    },

    saveMessages() {
      sessionStorage.setItem(
        this.chatStorageKey("pen_customize_messages"),
        JSON.stringify(this.messages),
      );
    },

    _saveThemeChangeState() {
      sessionStorage.setItem(
        this.chatStorageKey("pen_customize_changeset"),
        JSON.stringify(this.themeChangeSet || []),
      );
      sessionStorage.setItem(
        this.chatStorageKey("pen_customize_read_versions"),
        JSON.stringify(this.themeReadVersions || {}),
      );
    },

    _clearThemeChangeSet() {
      this.themeChangeSet = [];
      this.themeReadVersions = {};
      this._saveThemeChangeState();
    },

    _rememberThemeRead(result) {
      if (!result || typeof result !== "object" || !result.path) return;
      if (result.unchanged === true) return;
      if (result.content == null || !result.version) return;
      this.themeReadVersions = {
        ...(this.themeReadVersions || {}),
        [result.path]: result.version,
      };
      this._saveThemeChangeState();
    },

    _recordThemeChange(functionName, result) {
      const path = result && result.path;
      if (!path) return;
      const actionMap = {
        write_theme_file: "write",
        patch_theme_file: "patch",
        revert_theme_file: "revert",
        reset_theme_file: "reset",
      };
      const action = actionMap[functionName] || functionName;
      const entry = {
        path,
        action,
        bytes: result.bytes != null ? result.bytes : null,
        version: result.version || null,
      };
      const next = (this.themeChangeSet || []).filter((row) => row.path !== path);
      next.push(entry);
      this.themeChangeSet = next;
      const versions = { ...(this.themeReadVersions || {}) };
      delete versions[path];
      this.themeReadVersions = versions;
      this._saveThemeChangeState();
    },
  }));
}
if (window.Alpine) {
  registerCustomizeAiSidebar();
} else {
  document.addEventListener("alpine:init", registerCustomizeAiSidebar);
}

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
