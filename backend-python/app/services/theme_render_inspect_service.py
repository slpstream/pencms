"""In-process Playwright harness for Theme Customize render inspect.

Slice 1: browser lifecycle, SSRF URL builder, viewports, structured errors.
Slice 2: describe_element / get_layout_boxes evaluate helpers.
Slice 3: get_accessible_snapshot / get_render_fingerprint.
Slice 5: capture_theme_screenshot (pixels opt-in; HTTP lives in
``mcp_theme_inspect``).
Slice 6: cache read + vision-describe completion input (one-shot, no tools).
"""

from __future__ import annotations

import atexit
import base64
import hashlib
import json
import logging
import posixpath
import queue
import re
import tempfile
import threading
import time
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Tuple
from urllib.parse import parse_qsl, unquote, urlencode, urlparse, urlunparse

from config import get_preview_base_url
from services.theme_customize_service import get_theme_context

logger = logging.getLogger("pencms.theme_render_inspect")

NAV_TIMEOUT_MS = 15_000
TOTAL_BUDGET_S = 25.0
IDLE_TEARDOWN_S = 60.0
_MEDIA_EXT_RE = re.compile(
    r"\.(?:png|jpe?g|gif|webp|svg|ico|woff2?|ttf|otf)(?:\?|$)",
    re.IGNORECASE,
)

VIEWPORTS: Dict[str, Tuple[int, int]] = {
    "desktop": (1280, 800),
    "mobile": (390, 844),
}

PREVIEW_HINT = (
    "Set PENCMS_PREVIEW_BASE_URL or [Preview] base_url to the PHP origin the "
    "API process can GET /blog/ from (this machine: http://127.0.0.1:8009). "
    "If PHP runs via `php -S`, start it with PHP_CLI_SERVER_WORKERS>=4 — the "
    "admin /api proxy occupies a worker during inspect, and a single-worker "
    "server deadlocks preview navigation. Unset or unreachable preview "
    "returns PREVIEW_UNREACHABLE, never a 500."
)
BROWSER_HINT = (
    "pip install playwright && playwright install --only-shell "
    "(headless Chromium). Restart the API after installing."
)
PATH_HINT = (
    "Pass a relative path under /blog/ (default /blog/). Absolute URLs, other "
    "hosts, credentials, ports, and '..' are rejected. The server forces "
    "site= to the bound site_id."
)
THEME_INACTIVE_HINT = (
    "Custom theme is not active; the live site is still serving the install "
    "theme. Inspect results describe the live render, not the custom tree on disk."
)
SELECTOR_HINT = (
    "Pass a CSS selector (max 200 chars). Playwright engine prefixes "
    "xpath= and js= are not allowed."
)
BOXES_HINT = (
    "Pass 1–20 CSS selectors (each max 200 chars). xpath= and js= are not allowed."
)
SELECTOR_NOT_FOUND_HINT = (
    "No element matched the CSS selector. Check class names against the live "
    "DOM (Twig output), not source-only comments."
)
SCREENSHOT_INCLUDE_HINT = (
    "Pixels omitted (default). Set include_image=true to return a compact data "
    "URL when the payload is under 100KB. Prefer a CSS selector clip over the "
    "full viewport."
)
SCREENSHOT_CLIP_HINT = (
    "Screenshot exceeded the 100KB payload cap. Pass a CSS selector clip "
    "(or omit full_page) and retry with include_image=true."
)
SCREENSHOT_CACHE_MISS_HINT = (
    "No cached PNG for that hash (TTL 600s, site-scoped temp). Re-call "
    "capture_theme_screenshot with path/viewport/selector to recapture."
)
DESCRIBE_TEXT_ONLY_HINT = (
    "Chat model does not accept image inputs. Use describe_element, "
    "get_layout_boxes, and get_accessible_snapshot."
)
DESCRIBE_SCREENSHOT_PROMPT = (
    "You are describing a live theme-preview screenshot for a CMS customize "
    "agent. Return ONLY a JSON object with this exact shape:\n"
    '{"description": "<1-3 sentence caption of the clip>", '
    '"findings": ["<short visual observation>", ...]}\n'
    "findings should list layout, contrast, overflow, spacing, or other "
    "visual issues. Use [] if none. No markdown, no extra keys."
)

MAX_SELECTOR_LEN = 200
MAX_BOX_SELECTORS = 20
MAX_DESCRIBE_MATCHES = 5
MAX_A11Y_DEPTH = 8
MAX_A11Y_NODES = 80
MAX_A11Y_NAME = 120
FINGERPRINT_BYTES = 16
SCREENSHOT_MAX_BYTES = 100_000
SCREENSHOT_MAX_EDGE = 1280
SCREENSHOT_MAX_FULL_PAGE_HEIGHT = 2400
SCREENSHOT_CACHE_TTL_S = 600
SCREENSHOT_CACHE_DIR_NAME = "pencms-theme-inspect"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_SAFE_SITE_ID_RE = re.compile(r"[^A-Za-z0-9._-]+")
_SCREENSHOT_HASH_RE = re.compile(r"^[0-9a-f]{32}$")
_ARIA_LINE_RE = re.compile(
    r"^(?P<role>[A-Za-z][\w-]*)"
    r"(?:\s+\"(?P<name>(?:\\.|[^\"\\])*)\")?"
    r"(?:\s+\[[^\]]*\])*"
    r"\s*:?\s*$"
)

COMPUTED_STYLE_KEYS: Tuple[str, ...] = (
    "display",
    "position",
    "top",
    "right",
    "bottom",
    "left",
    "margin",
    "margin-top",
    "margin-right",
    "margin-bottom",
    "margin-left",
    "padding",
    "padding-top",
    "padding-right",
    "padding-bottom",
    "padding-left",
    "width",
    "height",
    "max-width",
    "max-height",
    "overflow",
    "overflow-x",
    "overflow-y",
    "visibility",
    "opacity",
    "z-index",
    "box-sizing",
    "flex",
    "flex-direction",
    "flex-wrap",
    "flex-grow",
    "flex-shrink",
    "flex-basis",
    "align-items",
    "justify-content",
    "gap",
    "grid-template-columns",
    "grid-template-rows",
    "font-size",
    "color",
    "background-color",
    "transform",
)

_DESCRIBE_ELEMENT_JS = """(selector) => {
  const KEYS = ["display","position","top","right","bottom","left","margin","margin-top","margin-right","margin-bottom","margin-left","padding","padding-top","padding-right","padding-bottom","padding-left","width","height","max-width","max-height","overflow","overflow-x","overflow-y","visibility","opacity","z-index","box-sizing","flex","flex-direction","flex-wrap","flex-grow","flex-shrink","flex-basis","align-items","justify-content","gap","grid-template-columns","grid-template-rows","font-size","color","background-color","transform"];
  function specificity(sel) {
    const s = String(sel || "");
    const ids = (s.match(/#[A-Za-z0-9_-]+/g) || []).length;
    const classes = (s.match(/\\.[A-Za-z0-9_-]+/g) || []).length;
    const attrs = (s.match(/\\[[^\\]]+\\]/g) || []).length;
    const pseudoEls = (s.match(/::[A-Za-z0-9_-]+/g) || []).length;
    const pseudos = (s.match(/:[A-Za-z0-9_-]+/g) || []).length - pseudoEls;
    const stripped = s.replace(/#[A-Za-z0-9_-]+/g, " ").replace(/\\.[A-Za-z0-9_-]+/g, " ").replace(/\\[[^\\]]+\\]/g, " ").replace(/::[A-Za-z0-9_-]+/g, " ").replace(/:[A-Za-z0-9_-]+/g, " ");
    const elements = (stripped.match(/[A-Za-z][A-Za-z0-9_-]*/g) || []).length;
    return [ids, classes + attrs + Math.max(0, pseudos), elements + pseudoEls];
  }
  function candidateSelectors() {
    const out = [];
    const seen = {};
    const scopes = ["header", "nav", "main", "footer", "aside", "body"];
    for (const scope of scopes) {
      const rootEl = document.querySelector(scope);
      if (!rootEl) continue;
      const prefix = scope === "body" ? "" : scope + " ";
      const els = rootEl.querySelectorAll("[class],[id]");
      for (let i = 0; i < els.length && out.length < 20; i++) {
        const el = els[i];
        if (el.id && !seen["#" + el.id]) { seen["#" + el.id] = 1; out.push("#" + el.id); }
        if (el.className && typeof el.className === "string") {
          const parts = el.className.trim().split(/\\s+/).filter(Boolean).slice(0, 2);
          for (const c of parts) {
            if (!seen["." + c]) { seen["." + c] = 1; out.push(prefix + "." + c); }
            if (out.length >= 20) break;
          }
        }
      }
      if (out.length >= 20) break;
    }
    return out;
  }
  let list;
  try {
    list = document.querySelectorAll(selector);
  } catch (e) {
    return { error: "INVALID_SELECTOR", reason: String(e && e.message ? e.message : e) };
  }
  const match_count = list.length;
  if (!match_count) return { error: "SELECTOR_NOT_FOUND", match_count: 0, candidates: candidateSelectors() };
  const el = list[0];
  const cs = getComputedStyle(el);
  const computed = {};
  for (const k of KEYS) computed[k] = cs.getPropertyValue(k);
  const matched = [];
  let skipped_cross_origin = 0;
  const sheets = document.styleSheets;
  for (let i = 0; i < sheets.length; i++) {
    const sheet = sheets[i];
    let rules;
    try { rules = sheet.cssRules; } catch (e) { skipped_cross_origin += 1; continue; }
    if (!rules) continue;
    const href = sheet.href || null;
    const styleRules = [];
    for (let j = 0; j < rules.length; j++) {
      const rule = rules[j];
      if (rule.type === 1 && rule.selectorText) styleRules.push(rule);
      else if (rule.type === 4 && rule.cssRules) {
        let applies = true;
        try {
          if (rule.conditionText && typeof matchMedia === "function") {
            applies = matchMedia(rule.conditionText).matches;
          }
        } catch (e) {}
        if (!applies) continue;
        for (let k = 0; k < rule.cssRules.length; k++) {
          if (rule.cssRules[k].type === 1 && rule.cssRules[k].selectorText) {
            styleRules.push(rule.cssRules[k]);
          }
        }
      }
    }
    for (const r of styleRules) {
      let ok = false;
      try { ok = el.matches(r.selectorText); } catch (e) { continue; }
      if (!ok) continue;
      const declared = [];
      for (const prop of KEYS) {
        if (r.style.getPropertyValue(prop)) declared.push(prop);
      }
      matched.push({
        selector: r.selectorText,
        href: href,
        specificity: specificity(r.selectorText),
        winning_props: declared,
        _declared: declared
      });
    }
  }
  const inlineDeclared = [];
  if (el.style) {
    for (const prop of KEYS) {
      if (el.style.getPropertyValue(prop)) inlineDeclared.push(prop);
    }
  }
  if (inlineDeclared.length) {
    matched.push({
      selector: ":inline",
      href: null,
      specificity: [1, 0, 0],
      winning_props: inlineDeclared,
      _declared: inlineDeclared
    });
  }
  const winner = {};
  for (const m of matched) {
    for (const p of m._declared) winner[p] = m;
  }
  for (const m of matched) {
    m.winning_props = m._declared.filter((p) => winner[p] === m);
    delete m._declared;
  }
  return {
    selector: selector,
    match_count: match_count,
    tag: el.tagName ? el.tagName.toLowerCase() : "",
    id: el.id || null,
    class_name: (el.className && typeof el.className === "string") ? el.className : "",
    computed: computed,
    matched_rules: matched,
    skipped_cross_origin: skipped_cross_origin
  };
}"""

_LAYOUT_BOXES_JS = """(selectors) => {
  const CLIP = { hidden: true, auto: true, scroll: true };
  function nodeLabel(el) {
    let s = el.tagName ? el.tagName.toLowerCase() : "node";
    if (el.id) s += "#" + el.id;
    if (el.className && typeof el.className === "string") {
      const parts = el.className.trim().split(/\\s+/).filter(Boolean).slice(0, 3);
      if (parts.length) s += "." + parts.join(".");
    }
    return s;
  }
  function clippingAncestor(el) {
    let node = el.parentElement;
    while (node && node !== document.documentElement) {
      const cs = getComputedStyle(node);
      if (CLIP[cs.overflow] || CLIP[cs.overflowX] || CLIP[cs.overflowY]) {
        const pr = node.getBoundingClientRect();
        return {
          selector: nodeLabel(node),
          overflow: cs.overflow,
          overflow_x: cs.overflowX,
          overflow_y: cs.overflowY,
          x: Math.round(pr.x),
          y: Math.round(pr.y),
          w: Math.round(pr.width),
          h: Math.round(pr.height)
        };
      }
      node = node.parentElement;
    }
    return null;
  }
  function candidateSelectors() {
    const out = [];
    const seen = {};
    const scopes = ["header", "nav", "main", "footer", "aside", "body"];
    for (const scope of scopes) {
      const rootEl = document.querySelector(scope);
      if (!rootEl) continue;
      const prefix = scope === "body" ? "" : scope + " ";
      const els = rootEl.querySelectorAll("[class],[id]");
      for (let i = 0; i < els.length && out.length < 20; i++) {
        const el = els[i];
        if (el.id && !seen["#" + el.id]) { seen["#" + el.id] = 1; out.push("#" + el.id); }
        if (el.className && typeof el.className === "string") {
          const parts = el.className.trim().split(/\\s+/).filter(Boolean).slice(0, 2);
          for (const c of parts) {
            if (!seen["." + c]) { seen["." + c] = 1; out.push(prefix + "." + c); }
            if (out.length >= 20) break;
          }
        }
      }
      if (out.length >= 20) break;
    }
    return out;
  }
  const boxes = [];
  const missing = [];
  for (const selector of selectors) {
    let list;
    try {
      list = document.querySelectorAll(selector);
    } catch (e) {
      return { error: "INVALID_SELECTOR", selector: selector, reason: String(e && e.message ? e.message : e) };
    }
    if (!list.length) {
      missing.push(selector);
      continue;
    }
    const el = list[0];
    const rect = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    const visible = cs.display !== "none" && cs.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
    boxes.push({
      selector: selector,
      x: Math.round(rect.x),
      y: Math.round(rect.y),
      w: Math.round(rect.width),
      h: Math.round(rect.height),
      visible: visible,
      clipping_ancestor: clippingAncestor(el)
    });
  }
  const result = { boxes: boxes, missing: missing };
  if (missing.length) result.candidates = candidateSelectors();
  return result;
}"""

_A11Y_SNAPSHOT_JS = """(opts) => {
  const maxDepth = opts.max_depth || 8;
  const maxNodes = opts.max_nodes || 80;
  const maxText = opts.max_text || 120;
  const TAG_ROLE = {
    html: "document", body: "generic", nav: "navigation", main: "main",
    header: "banner", footer: "contentinfo", aside: "complementary",
    section: "region", article: "article", form: "form",
    h1: "heading", h2: "heading", h3: "heading", h4: "heading",
    h5: "heading", h6: "heading", a: "link", button: "button",
    img: "img", input: "textbox", textarea: "textbox", select: "combobox",
    ul: "list", ol: "list", li: "listitem", table: "table",
    thead: "rowgroup", tbody: "rowgroup", tr: "row", td: "cell", th: "columnheader",
    label: "label", p: "paragraph"
  };
  function roleOf(el) {
    const explicit = el.getAttribute("role");
    if (explicit) return explicit;
    const tag = (el.tagName || "").toLowerCase();
    if (tag === "input") {
      const t = (el.getAttribute("type") || "text").toLowerCase();
      if (t === "checkbox") return "checkbox";
      if (t === "radio") return "radio";
      if (t === "button" || t === "submit" || t === "reset") return "button";
      if (t === "hidden") return "none";
      return "textbox";
    }
    return TAG_ROLE[tag] || "generic";
  }
  function nameOf(el) {
    const al = el.getAttribute("aria-label");
    if (al) return String(al);
    if (el.alt) return String(el.alt);
    const labelled = el.getAttribute("aria-labelledby");
    if (labelled) {
      const parts = String(labelled).split(/\\s+/).map((id) => {
        const n = document.getElementById(id);
        return n ? String(n.textContent || "") : "";
      });
      const s = parts.join(" ").replace(/\\s+/g, " ").trim();
      if (s) return s;
    }
    if (el.title) return String(el.title);
    const tag = (el.tagName || "").toLowerCase();
    if (tag === "input" || tag === "textarea") {
      return String(el.value || el.placeholder || "");
    }
    let t = "";
    if (el.childNodes) {
      for (const n of el.childNodes) {
        if (n.nodeType === 3) t += n.textContent || "";
      }
    }
    t = t.replace(/\\s+/g, " ").trim();
    if (t) return t;
    return String(el.innerText || "").replace(/\\s+/g, " ").trim();
  }
  function visibleOf(el) {
    const cs = getComputedStyle(el);
    return cs.display !== "none" && cs.visibility !== "hidden" && cs.opacity !== "0";
  }
  let count = 0;
  let truncated = false;
  function walk(el, depth) {
    if (count >= maxNodes) { truncated = true; return null; }
    if (depth > maxDepth) { truncated = true; return null; }
    count += 1;
    let name = nameOf(el);
    if (name.length > maxText) {
      name = name.slice(0, maxText);
      truncated = true;
    }
    const node = { role: roleOf(el), name: name, visible: visibleOf(el), children: [] };
    if (depth >= maxDepth) {
      if (el.children && el.children.length) truncated = true;
      return node;
    }
    const kids = el.children || [];
    for (let i = 0; i < kids.length; i++) {
      if (count >= maxNodes) { truncated = true; break; }
      const child = walk(kids[i], depth + 1);
      if (child) node.children.push(child);
    }
    return node;
  }
  let root;
  if (opts.root) {
    try { root = document.querySelector(opts.root); }
    catch (e) {
      return { error: "INVALID_SELECTOR", reason: String(e && e.message ? e.message : e) };
    }
    if (!root) return { error: "SELECTOR_NOT_FOUND", selector: opts.root, match_count: 0 };
  } else {
    root = document.documentElement || document.body;
  }
  const snapshot = walk(root, 1);
  return { snapshot: snapshot, node_count: count, truncated: truncated };
}"""

_INSPECT_LOCK = threading.Lock()
_playwright: Any = None
_browser: Any = None
_browser_thread: Optional[threading.Thread] = None
_idle_timer: Optional[threading.Timer] = None


class _InspectWorker:
    """Single thread that owns the Playwright sync API (greenlets are thread-bound)."""

    def __init__(self) -> None:
        self._q: queue.Queue = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._start_lock = threading.Lock()

    def is_current(self) -> bool:
        return self._thread is not None and threading.current_thread() is self._thread

    def ensure_started(self) -> None:
        with self._start_lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._thread = threading.Thread(
                target=self._loop,
                name="pencms-theme-inspect",
                daemon=True,
            )
            self._thread.start()

    def _loop(self) -> None:
        while True:
            item = self._q.get()
            if item is None:
                try:
                    _shutdown_browser_unlocked()
                except Exception:
                    logger.debug("Inspect worker shutdown failed", exc_info=True)
                break
            fn, args, kwargs, out = item
            try:
                out.put((True, fn(*args, **kwargs)))
            except BaseException as exc:
                out.put((False, exc))

    def submit(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        if self.is_current():
            return fn(*args, **kwargs)
        self.ensure_started()
        out: queue.Queue = queue.Queue()
        self._q.put((fn, args, kwargs, out))
        ok, payload = out.get()
        if ok:
            return payload
        raise payload


_INSPECT_WORKER = _InspectWorker()


def run_on_inspect_thread(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Run ``fn`` on the Playwright-owning thread. Safe to call from any thread."""
    return _INSPECT_WORKER.submit(fn, *args, **kwargs)


def invoke_inspect(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Router entry: pin Playwright to one thread; never leak greenlet errors as 500."""
    try:
        return run_on_inspect_thread(fn, *args, **kwargs)
    except ThemeRenderInspectError:
        raise
    except Exception as exc:
        logger.exception("Inspect browser failed")
        _raise(
            "BROWSER_UNAVAILABLE",
            f"Inspect browser failed: {exc}",
            BROWSER_HINT,
        )


class ThemeRenderInspectError(Exception):
    """Structured inspect failure: ``{error, reason, hint}``."""

    def __init__(self, error: str, reason: str, hint: str):
        super().__init__(reason)
        self.error = error
        self.reason = reason
        self.hint = hint

    def payload(self) -> Dict[str, str]:
        return {"error": self.error, "reason": self.reason, "hint": self.hint}


def _raise(error: str, reason: str, hint: str) -> None:
    raise ThemeRenderInspectError(error, reason, hint)


def resolve_viewport(name: Optional[str] = None) -> Tuple[str, int, int]:
    """Return ``(name, width, height)``. Default ``desktop``."""
    key = (name or "desktop").strip().lower() or "desktop"
    if key not in VIEWPORTS:
        _raise(
            "INVALID_VIEWPORT",
            f"Unknown viewport {name!r}; use desktop or mobile.",
            "viewport must be 'desktop' (1280x800) or 'mobile' (390x844).",
        )
    width, height = VIEWPORTS[key]
    return key, width, height


def _configured_origin() -> str:
    base = get_preview_base_url()
    if not base:
        _raise(
            "PREVIEW_UNREACHABLE",
            "Preview base URL is not configured.",
            PREVIEW_HINT,
        )
    parsed = urlparse(base)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        _raise(
            "PREVIEW_UNREACHABLE",
            f"Preview base URL is not an http(s) origin: {base!r}.",
            PREVIEW_HINT,
        )
    if parsed.username or parsed.password:
        _raise(
            "PREVIEW_UNREACHABLE",
            "Preview base URL must not include credentials.",
            PREVIEW_HINT,
        )
    return f"{parsed.scheme}://{parsed.netloc}"


def build_preview_url(site_id: str, path: Optional[str] = None) -> str:
    """Join configured origin with a relative ``/blog/`` path; force ``site=``.

    Raises ``PREVIEW_UNREACHABLE`` if the origin is unset/invalid, or
    ``PATH_REJECTED`` if the path is not a same-origin ``/blog/`` relative path.
    """
    origin = _configured_origin()
    bound = (site_id or "").strip()
    if not bound:
        _raise("PATH_REJECTED", "site_id is required to build a preview URL.", PATH_HINT)

    raw = (path or "").strip() or "/blog/"
    lowered = raw.lower()
    if lowered.startswith(("http:", "https:", "ftp:", "file:", "javascript:", "data:")):
        _raise("PATH_REJECTED", "Absolute URLs are not allowed; pass a relative /blog/ path.", PATH_HINT)
    if "://" in raw or raw.startswith("//"):
        _raise("PATH_REJECTED", "Protocol-relative and absolute URLs are not allowed.", PATH_HINT)
    if "\\" in raw or "%5c" in lowered or "%5C" in raw:
        _raise("PATH_REJECTED", "Backslashes are not allowed in preview paths.", PATH_HINT)
    if "@" in raw:
        _raise("PATH_REJECTED", "Credentials are not allowed in preview paths.", PATH_HINT)

    if not raw.startswith("/"):
        raw = "/" + raw

    parsed = urlparse(raw)
    if parsed.scheme or parsed.netloc:
        _raise("PATH_REJECTED", "Preview path must not include a host.", PATH_HINT)

    path_part = parsed.path or "/"
    decoded = unquote(path_part)
    if ".." in decoded or ".." in raw:
        _raise("PATH_REJECTED", "Path traversal ('..') is not allowed.", PATH_HINT)
    if ":" in path_part or ":" in decoded:
        _raise("PATH_REJECTED", "Ports and colons are not allowed in the preview path.", PATH_HINT)

    normalized = posixpath.normpath(decoded)
    if normalized != "/blog" and not normalized.startswith("/blog/"):
        _raise(
            "PATH_REJECTED",
            f"Preview path must be under /blog/; got {path_part!r}.",
            PATH_HINT,
        )

    if normalized == "/blog":
        out_path = "/blog/"
    else:
        out_path = normalized
        if decoded.endswith("/") and not out_path.endswith("/"):
            out_path += "/"

    query_pairs = [
        (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k != "site"
    ]
    query_pairs.append(("site", bound))
    origin_parsed = urlparse(origin)
    final = urlunparse(
        (
            origin_parsed.scheme,
            origin_parsed.netloc,
            out_path,
            "",
            urlencode(query_pairs),
            "",
        )
    )
    final_parsed = urlparse(final)
    if (
        final_parsed.scheme != origin_parsed.scheme
        or final_parsed.hostname != origin_parsed.hostname
        or final_parsed.port != origin_parsed.port
        or final_parsed.netloc != origin_parsed.netloc
    ):
        _raise("PATH_REJECTED", "Preview URL host must match the configured origin.", PATH_HINT)
    return final


def inspect_envelope(site_id: str, viewport: str, url: str) -> Dict[str, Any]:
    """Shared success envelope. Inactive custom warns; it does not refuse."""
    ctx = get_theme_context(site_id)
    active = bool(ctx.get("active"))
    return {
        "ok": True,
        "site_id": site_id,
        "theme_active": active,
        "viewport": viewport,
        "url": url,
        "hint": None if active else THEME_INACTIVE_HINT,
    }


def evaluate(page: Any, expression: str, arg: Any = None) -> Any:
    """Thin ``page.evaluate`` wrapper. Pass ``arg`` through when given."""
    if arg is None:
        return page.evaluate(expression)
    return page.evaluate(expression, arg)


def validate_css_selector(selector: Optional[str]) -> str:
    """CSS-only selector; max 200 chars. Rejects ``xpath=`` / ``js=`` prefixes."""
    if selector is None or not str(selector).strip():
        _raise("INVALID_SELECTOR", "selector is required.", SELECTOR_HINT)
    sel = str(selector).strip()
    if len(sel) > MAX_SELECTOR_LEN:
        _raise(
            "INVALID_SELECTOR",
            f"Selector exceeds {MAX_SELECTOR_LEN} characters.",
            SELECTOR_HINT,
        )
    lowered = sel.lower()
    if lowered.startswith("xpath=") or lowered.startswith("js="):
        _raise(
            "INVALID_SELECTOR",
            "Only CSS selectors are allowed (not xpath= or js=).",
            SELECTOR_HINT,
        )
    return sel


def validate_selector_list(selectors: Any) -> List[str]:
    """1–20 CSS selectors for ``get_layout_boxes``."""
    if not isinstance(selectors, (list, tuple)):
        _raise(
            "INVALID_SELECTOR",
            "selectors must be a list of CSS selectors.",
            BOXES_HINT,
        )
    if len(selectors) < 1:
        _raise(
            "INVALID_SELECTOR",
            "selectors must contain at least one CSS selector.",
            BOXES_HINT,
        )
    if len(selectors) > MAX_BOX_SELECTORS:
        _raise(
            "INVALID_SELECTOR",
            f"At most {MAX_BOX_SELECTORS} selectors are allowed.",
            BOXES_HINT,
        )
    return [validate_css_selector(s) for s in selectors]


def _clean_candidates(raw: Any) -> List[str]:
    if not isinstance(raw, list):
        return []
    return [str(s) for s in raw if isinstance(s, str) and s][:20]


def _not_found_hint(candidates: List[str]) -> str:
    if not candidates:
        return SELECTOR_NOT_FOUND_HINT
    return (
        SELECTOR_NOT_FOUND_HINT
        + " Selectors present on this page: "
        + ", ".join(candidates)
        + "."
    )


def _raise_from_page_error(raw: Dict[str, Any], fallback_selector: str) -> None:
    err = raw.get("error")
    sel = raw.get("selector") or fallback_selector
    if err == "INVALID_SELECTOR":
        _raise(
            "INVALID_SELECTOR",
            str(raw.get("reason") or f"Invalid CSS selector {sel!r}."),
            SELECTOR_HINT,
        )
    if err == "SELECTOR_NOT_FOUND":
        _raise(
            "SELECTOR_NOT_FOUND",
            f"No element matched {sel!r}.",
            _not_found_hint(_clean_candidates(raw.get("candidates"))),
        )


def describe_element_on_page(page: Any, selector: str) -> Dict[str, Any]:
    """Computed-style subset + matched rules for the first CSS match."""
    sel = validate_css_selector(selector)
    raw = evaluate(page, _DESCRIBE_ELEMENT_JS, sel)
    if not isinstance(raw, dict):
        _raise(
            "SELECTOR_NOT_FOUND",
            f"No element matched {sel!r}.",
            SELECTOR_NOT_FOUND_HINT,
        )
    if raw.get("error"):
        _raise_from_page_error(raw, sel)
    match_count = int(raw.get("match_count") or 0)
    if match_count < 1:
        _raise(
            "SELECTOR_NOT_FOUND",
            f"No element matched {sel!r}.",
            SELECTOR_NOT_FOUND_HINT,
        )
    return raw


def layout_boxes_on_page(page: Any, selectors: Sequence[str]) -> Dict[str, Any]:
    """Geometry boxes (first match per selector) plus clipping ancestor.

    Partial misses do not fail the call: hit selectors return boxes, missed
    selectors are listed in ``missing`` with ``candidates`` from the live DOM.
    Only a total miss (zero boxes) raises ``SELECTOR_NOT_FOUND``.
    """
    cleaned = validate_selector_list(list(selectors))
    raw = evaluate(page, _LAYOUT_BOXES_JS, cleaned)
    if not isinstance(raw, dict):
        _raise(
            "SELECTOR_NOT_FOUND",
            f"No element matched {cleaned[0]!r}.",
            SELECTOR_NOT_FOUND_HINT,
        )
    if raw.get("error"):
        _raise_from_page_error(raw, cleaned[0])
    boxes = raw.get("boxes")
    if not isinstance(boxes, list):
        _raise(
            "SELECTOR_NOT_FOUND",
            f"No element matched {cleaned[0]!r}.",
            SELECTOR_NOT_FOUND_HINT,
        )
    missing = [s for s in (raw.get("missing") or []) if isinstance(s, str)]
    candidates = _clean_candidates(raw.get("candidates"))
    if not boxes and missing:
        _raise(
            "SELECTOR_NOT_FOUND",
            "No element matched any selector: " + ", ".join(missing) + ".",
            _not_found_hint(candidates),
        )
    payload: Dict[str, Any] = {"boxes": boxes, "missing": missing}
    if missing and candidates:
        payload["candidates"] = candidates
    return payload


def _aria_line_to_node(body: str) -> Dict[str, Any]:
    """Parse one Playwright aria line (role, optional quoted name, dropped attrs)."""
    text = (body or "").strip()
    if text.endswith(":"):
        text = text[:-1].rstrip()
    match = _ARIA_LINE_RE.match(text)
    if not match:
        role = text.split()[0] if text else "generic"
        return {"role": role, "name": "", "visible": True, "children": []}
    name = match.group("name") or ""
    if name:
        name = name.replace('\\"', '"')
    return {
        "role": match.group("role"),
        "name": name,
        "visible": True,
        "children": [],
    }


def parse_aria_snapshot_yaml(text: str) -> Dict[str, Any]:
    """Playwright ``aria_snapshot()`` YAML → one ``{role, name, visible, children}`` node.

    Structure comes from indentation and ``- role "name"`` inline syntax, not
    explicit key-value pairs. Property lines (``/url:``) are skipped.

    ``visible`` is always ``True`` on this path: Playwright omits hidden nodes
    and the YAML has no visibility flag. Known limitation vs the evaluate
    fallback (computed style). Same JSON shape; do not mix path semantics
    when diffing ``visible``.
    """
    roots: List[Dict[str, Any]] = []
    stack: List[Tuple[int, Dict[str, Any]]] = []
    for raw in (text or "").splitlines():
        if not raw.strip():
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        stripped = raw.strip()
        if not stripped.startswith("-"):
            continue
        body = stripped[1:].lstrip()
        if body.startswith("/"):
            continue
        node = _aria_line_to_node(body)
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if stack:
            stack[-1][1]["children"].append(node)
        else:
            roots.append(node)
        stack.append((indent, node))
    if not roots:
        return {"role": "document", "name": "", "visible": True, "children": []}
    if len(roots) == 1:
        return roots[0]
    return {
        "role": "document",
        "name": "",
        "visible": True,
        "children": roots,
    }


def cap_a11y_tree(snapshot: Optional[Dict[str, Any]]) -> Tuple[Dict[str, Any], int, bool]:
    """Enforce max depth 8, 80 nodes, 120-char names. Returns (tree, count, truncated)."""
    truncated = False
    count = 0

    def walk(node: Any, depth: int) -> Optional[Dict[str, Any]]:
        nonlocal truncated, count
        if not isinstance(node, dict):
            return None
        if count >= MAX_A11Y_NODES:
            truncated = True
            return None
        if depth > MAX_A11Y_DEPTH:
            truncated = True
            return None
        count += 1
        name = str(node.get("name") or "")
        if len(name) > MAX_A11Y_NAME:
            name = name[:MAX_A11Y_NAME]
            truncated = True
        out: Dict[str, Any] = {
            "role": str(node.get("role") or "generic"),
            "name": name,
            "visible": bool(node.get("visible", True)),
            "children": [],
        }
        kids = node.get("children") or []
        if not isinstance(kids, list):
            kids = []
        if depth >= MAX_A11Y_DEPTH:
            if kids:
                truncated = True
            return out
        for child in kids:
            if count >= MAX_A11Y_NODES:
                truncated = True
                break
            capped = walk(child, depth + 1)
            if capped is not None:
                out["children"].append(capped)
        return out

    empty = {"role": "document", "name": "", "visible": True, "children": []}
    if snapshot is None:
        return empty, 0, False
    capped = walk(snapshot, 1)
    if capped is None:
        return empty, count, truncated
    return capped, count, truncated


def png_ihdr_size(data: bytes) -> Tuple[int, int]:
    """Width/height from PNG IHDR (no pixel decode)."""
    raw = bytes(data) if not isinstance(data, bytes) else data
    if len(raw) < 24 or raw[:8] != _PNG_MAGIC:
        _raise(
            "BROWSER_UNAVAILABLE",
            "Screenshot did not return a PNG.",
            BROWSER_HINT,
        )
    width = int.from_bytes(raw[16:20], "big")
    height = int.from_bytes(raw[20:24], "big")
    return width, height


def fingerprint_png(data: bytes) -> Dict[str, Any]:
    """16-byte hex of PNG bytes plus IHDR size. No pixels in the result."""
    raw = bytes(data)
    digest = hashlib.sha256(raw).digest()[:FINGERPRINT_BYTES].hex()
    width, height = png_ihdr_size(raw)
    return {"hash": digest, "width": width, "height": height}


def _locator_first(page: Any, selector: str) -> Any:
    locator_fn = getattr(page, "locator", None)
    if not callable(locator_fn):
        return None
    loc = locator_fn(selector)
    count_fn = getattr(loc, "count", None)
    if callable(count_fn) and count_fn() == 0:
        _raise(
            "SELECTOR_NOT_FOUND",
            f"No element matched {selector!r}.",
            SELECTOR_NOT_FOUND_HINT,
        )
    first = getattr(loc, "first", loc)
    return first


def _try_aria_snapshot_tree(page: Any, root_sel: Optional[str]) -> Optional[Dict[str, Any]]:
    loc = _locator_first(page, root_sel or "html")
    if loc is None or not hasattr(loc, "aria_snapshot"):
        return None
    try:
        yaml_text = loc.aria_snapshot()
    except ThemeRenderInspectError:
        raise
    except Exception:
        logger.debug("aria_snapshot failed; falling back to evaluate", exc_info=True)
        return None
    if not isinstance(yaml_text, str):
        return None
    return parse_aria_snapshot_yaml(yaml_text)


def accessible_snapshot_on_page(page: Any, root: Optional[str] = None) -> Dict[str, Any]:
    """Compact a11y tree for a root selector or the document."""
    root_sel = None
    if root is not None and str(root).strip():
        root_sel = validate_css_selector(root)

    tree = _try_aria_snapshot_tree(page, root_sel)
    if tree is None:
        raw = evaluate(
            page,
            _A11Y_SNAPSHOT_JS,
            {
                "root": root_sel,
                "max_depth": MAX_A11Y_DEPTH,
                "max_nodes": MAX_A11Y_NODES,
                "max_text": MAX_A11Y_NAME,
            },
        )
        if not isinstance(raw, dict):
            _raise(
                "SELECTOR_NOT_FOUND",
                f"No element matched {root_sel or 'html'!r}.",
                SELECTOR_NOT_FOUND_HINT,
            )
        if raw.get("error"):
            _raise_from_page_error(raw, root_sel or "html")
        tree = raw.get("snapshot")

    snapshot, node_count, truncated = cap_a11y_tree(tree)
    return {
        "root": root_sel,
        "snapshot": snapshot,
        "node_count": node_count,
        "truncated": truncated,
    }


def _page_viewport_size(page: Any) -> Tuple[int, int]:
    vp = getattr(page, "viewport_size", None)
    if callable(vp):
        vp = vp()
    if isinstance(vp, dict):
        w = int(vp.get("width") or VIEWPORTS["desktop"][0])
        h = int(vp.get("height") or VIEWPORTS["desktop"][1])
        return max(w, 1), max(h, 1)
    return VIEWPORTS["desktop"]


def _document_scroll_height(page: Any, fallback: int) -> int:
    try:
        raw = evaluate(
            page,
            "() => Math.max("
            "document.documentElement ? document.documentElement.scrollHeight : 0,"
            "document.body ? document.body.scrollHeight : 0"
            ")",
        )
    except Exception:
        logger.debug("scrollHeight evaluate failed", exc_info=True)
        return fallback
    try:
        height = int(raw)
    except (TypeError, ValueError):
        return fallback
    return max(height, 1)


def _screenshot_full_page_capped(page: Any) -> Any:
    width, height = _page_viewport_size(page)
    doc_h = _document_scroll_height(page, fallback=height)
    cap_h = min(doc_h, SCREENSHOT_MAX_FULL_PAGE_HEIGHT)
    return page.screenshot(
        type="png",
        full_page=False,
        clip={"x": 0, "y": 0, "width": width, "height": cap_h},
    )


def capture_png_on_page(
    page: Any,
    selector: Optional[str] = None,
    full_page: bool = False,
) -> bytes:
    """Viewport, clipped element, or height-capped full-page PNG bytes."""
    png: Any = None
    if selector is not None and str(selector).strip():
        sel = validate_css_selector(selector)
        loc = _locator_first(page, sel)
        if loc is None or not hasattr(loc, "screenshot"):
            _raise(
                "BROWSER_UNAVAILABLE",
                "Page locator cannot screenshot a clip.",
                BROWSER_HINT,
            )
        png = loc.screenshot(type="png")
    elif full_page:
        png = _screenshot_full_page_capped(page)
    else:
        png = page.screenshot(type="png", full_page=False)
    if not isinstance(png, (bytes, bytearray)):
        _raise(
            "BROWSER_UNAVAILABLE",
            "Screenshot did not return PNG bytes.",
            BROWSER_HINT,
        )
    return bytes(png)


def fingerprint_on_page(page: Any, selector: Optional[str] = None) -> Dict[str, Any]:
    """Hash of viewport (or clipped element) PNG. No pixels returned."""
    return fingerprint_png(capture_png_on_page(page, selector, full_page=False))


def screenshot_cache_root() -> Path:
    """Site-scoped temp dir for inspect PNGs (not under theme/)."""
    return Path(tempfile.gettempdir()) / SCREENSHOT_CACHE_DIR_NAME


def _safe_cache_site_id(site_id: str) -> str:
    raw = (site_id or "").strip() or "unknown"
    cleaned = _SAFE_SITE_ID_RE.sub("_", raw).replace("..", "_")
    if not cleaned or cleaned in (".", ".."):
        return "unknown"
    return cleaned[:64]


def _purge_expired_cache(site_dir: Path, now: Optional[float] = None) -> None:
    if not site_dir.is_dir():
        return
    stamp = time.time() if now is None else now
    for path in site_dir.iterdir():
        if not path.is_file():
            continue
        try:
            if stamp - path.stat().st_mtime > SCREENSHOT_CACHE_TTL_S:
                path.unlink()
        except OSError:
            logger.debug("Inspect screenshot cache purge failed for %s", path, exc_info=True)


def cache_screenshot_png(site_id: str, digest: str, png: bytes) -> Path:
    """Write PNG under the site temp cache; purge expired files first."""
    site_dir = screenshot_cache_root() / _safe_cache_site_id(site_id)
    site_dir.mkdir(parents=True, exist_ok=True)
    _purge_expired_cache(site_dir)
    path = site_dir / f"{digest}.png"
    path.write_bytes(png)
    return path


def encode_screenshot_data_url(png: bytes) -> Optional[Tuple[str, str]]:
    """JPEG (or tiny PNG) data URL if encoded payload ≤ cap; else None."""
    raw = bytes(png)
    if len(raw) <= SCREENSHOT_MAX_BYTES:
        b64 = base64.b64encode(raw).decode("ascii")
        return "image/png", f"data:image/png;base64,{b64}"
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        img = Image.open(BytesIO(raw))
        if img.mode != "RGB":
            img = img.convert("RGB")
        w, h = img.size
        max_edge = max(w, h)
        if max_edge > SCREENSHOT_MAX_EDGE:
            scale = SCREENSHOT_MAX_EDGE / float(max_edge)
            img = img.resize(
                (max(1, int(w * scale)), max(1, int(h * scale))),
                Image.Resampling.LANCZOS,
            )
        for quality in (80, 70, 60, 50, 40):
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            data = buf.getvalue()
            if len(data) <= SCREENSHOT_MAX_BYTES:
                b64 = base64.b64encode(data).decode("ascii")
                return "image/jpeg", f"data:image/jpeg;base64,{b64}"
    except Exception:
        logger.debug("Screenshot JPEG encode failed", exc_info=True)
        return None
    return None


def encode_describe_data_url(png: bytes) -> Tuple[str, str]:
    """Data URL for a one-shot describe completion. Not bound by the 100KB MCP cap."""
    raw = bytes(png)
    if len(raw) <= SCREENSHOT_MAX_BYTES:
        b64 = base64.b64encode(raw).decode("ascii")
        return "image/png", f"data:image/png;base64,{b64}"
    try:
        from PIL import Image
    except ImportError:
        b64 = base64.b64encode(raw).decode("ascii")
        return "image/png", f"data:image/png;base64,{b64}"
    try:
        img = Image.open(BytesIO(raw))
        if img.mode != "RGB":
            img = img.convert("RGB")
        w, h = img.size
        max_edge = max(w, h)
        if max_edge > SCREENSHOT_MAX_EDGE:
            scale = SCREENSHOT_MAX_EDGE / float(max_edge)
            img = img.resize(
                (max(1, int(w * scale)), max(1, int(h * scale))),
                Image.Resampling.LANCZOS,
            )
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=80, optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return "image/jpeg", f"data:image/jpeg;base64,{b64}"
    except Exception:
        logger.debug("Describe JPEG encode failed; sending PNG", exc_info=True)
        b64 = base64.b64encode(raw).decode("ascii")
        return "image/png", f"data:image/png;base64,{b64}"


def validate_screenshot_hash(digest: Optional[str]) -> str:
    """32 lowercase hex chars (16-byte fingerprint). Rejects path traversal."""
    raw = (digest or "").strip().lower()
    if not _SCREENSHOT_HASH_RE.fullmatch(raw):
        _raise(
            "SCREENSHOT_CACHE_MISS",
            f"Invalid screenshot hash {digest!r}.",
            SCREENSHOT_CACHE_MISS_HINT,
        )
    return raw


def read_cached_screenshot_png(
    site_id: str,
    digest: str,
    now: Optional[float] = None,
) -> Optional[bytes]:
    """TTL-aware read of a site-scoped cached PNG. None on miss or expiry."""
    key = validate_screenshot_hash(digest)
    path = screenshot_cache_root() / _safe_cache_site_id(site_id) / f"{key}.png"
    if not path.is_file():
        return None
    stamp = time.time() if now is None else now
    try:
        if stamp - path.stat().st_mtime > SCREENSHOT_CACHE_TTL_S:
            try:
                path.unlink()
            except OSError:
                logger.debug("Expired inspect screenshot unlink failed for %s", path, exc_info=True)
            return None
        return path.read_bytes()
    except OSError:
        logger.debug("Inspect screenshot cache read failed for %s", path, exc_info=True)
        return None


def _has_recapture_args(
    selector: Optional[str],
    path: Optional[str],
    full_page: bool,
) -> bool:
    if selector is not None and str(selector).strip():
        return True
    if path is not None and str(path).strip():
        return True
    return bool(full_page)


def load_screenshot_png(
    site_id: str,
    *,
    selector: Optional[str] = None,
    path: Optional[str] = None,
    viewport: Optional[str] = None,
    full_page: bool = False,
    digest: Optional[str] = None,
) -> Tuple[bytes, str, str]:
    """Return ``(png, viewport_name, url)``. Cache hit skips Playwright.

    Recapture on miss only when selector, path, or full_page is set.
    """
    vp_name, _, _ = resolve_viewport(viewport)
    url = build_preview_url(site_id, path)
    if digest is not None and str(digest).strip():
        png = read_cached_screenshot_png(site_id, digest)
        if png is not None:
            return png, vp_name, url
        if not _has_recapture_args(selector, path, full_page):
            _raise(
                "SCREENSHOT_CACHE_MISS",
                f"No cached screenshot for hash {str(digest).strip()!r}.",
                SCREENSHOT_CACHE_MISS_HINT,
            )
    sel = None
    if selector is not None and str(selector).strip():
        sel = validate_css_selector(selector)
    with open_inspect_page(site_id=site_id, path=path, viewport=viewport) as page:
        png = capture_png_on_page(page, sel, full_page=bool(full_page) and sel is None)
    cache_screenshot_png(site_id, fingerprint_png(png)["hash"], png)
    return png, vp_name, url


def load_screenshot_for_describe(
    site_id: str,
    selector: Optional[str] = None,
    path: Optional[str] = None,
    viewport: Optional[str] = None,
    full_page: bool = False,
    digest: Optional[str] = None,
) -> Tuple[bytes, Dict[str, Any]]:
    """PNG + inspect envelope/meta for the vision-describe sub-path."""
    png, vp_name, url = load_screenshot_png(
        site_id,
        selector=selector,
        path=path,
        viewport=viewport,
        full_page=full_page,
        digest=digest,
    )
    env = inspect_envelope(site_id, vp_name, url)
    env.update(fingerprint_png(png))
    return png, env


def build_describe_messages(png: bytes) -> List[Dict[str, Any]]:
    """One-shot multimodal user message for a screenshot describe completion."""
    _mime, data_url = encode_describe_data_url(png)
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": DESCRIBE_SCREENSHOT_PROMPT},
                {
                    "type": "image_url",
                    "image_url": {"url": data_url, "detail": "auto"},
                },
            ],
        }
    ]


def parse_describe_response(text: str) -> Dict[str, Any]:
    """Parse ``{description, findings[]}``; raw text on JSON failure."""
    raw = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if fenced:
        json_str = fenced.group(1)
    else:
        bare = re.search(r"\{.*\}", raw, re.DOTALL)
        json_str = bare.group(0) if bare else raw
    try:
        parsed = json.loads(json_str)
    except (json.JSONDecodeError, TypeError, ValueError):
        return {"description": raw, "findings": []}
    if not isinstance(parsed, dict):
        return {"description": raw, "findings": []}
    description = parsed.get("description")
    if description is None:
        description = raw
    else:
        description = str(description)
    findings = parsed.get("findings", [])
    if not isinstance(findings, list):
        findings = [str(findings)] if findings else []
    else:
        findings = [str(item) for item in findings]
    return {"description": description, "findings": findings}


def _merge_hints(*parts: Optional[str]) -> Optional[str]:
    bits = [str(p).strip() for p in parts if p and str(p).strip()]
    return " ".join(bits) or None


def screenshot_on_page(
    page: Any,
    *,
    site_id: str,
    selector: Optional[str] = None,
    full_page: bool = False,
    include_image: bool = False,
) -> Dict[str, Any]:
    """Capture PNG, cache it, hash it; data URL only when opted in and under cap."""
    sel = None
    if selector is not None and str(selector).strip():
        sel = validate_css_selector(selector)
    png = capture_png_on_page(page, sel, full_page=bool(full_page) and sel is None)
    meta = fingerprint_png(png)
    cache_screenshot_png(site_id, meta["hash"], png)
    payload: Dict[str, Any] = dict(meta)
    extra_hint = None
    if include_image:
        encoded = encode_screenshot_data_url(png)
        if encoded:
            payload["mime"], payload["data_url"] = encoded
        else:
            extra_hint = SCREENSHOT_CLIP_HINT
    else:
        extra_hint = SCREENSHOT_INCLUDE_HINT
    if extra_hint:
        payload["hint"] = extra_hint
    return payload


def describe_element(
    site_id: str,
    selector: str,
    path: Optional[str] = None,
    viewport: Optional[str] = None,
) -> Dict[str, Any]:
    """Navigate the bound preview and describe the first matching element."""
    sel = validate_css_selector(selector)
    vp_name, _, _ = resolve_viewport(viewport)
    url = build_preview_url(site_id, path)
    with open_inspect_page(
        site_id=site_id, path=path, viewport=viewport, block_media=True
    ) as page:
        payload = describe_element_on_page(page, sel)
    env = inspect_envelope(site_id, vp_name, url)
    env.update(payload)
    return env


def get_layout_boxes(
    site_id: str,
    selectors: Sequence[str],
    path: Optional[str] = None,
    viewport: Optional[str] = None,
) -> Dict[str, Any]:
    """Navigate the bound preview and return layout boxes for each selector."""
    cleaned = validate_selector_list(list(selectors))
    vp_name, _, _ = resolve_viewport(viewport)
    url = build_preview_url(site_id, path)
    with open_inspect_page(
        site_id=site_id, path=path, viewport=viewport, block_media=True
    ) as page:
        payload = layout_boxes_on_page(page, cleaned)
    env = inspect_envelope(site_id, vp_name, url)
    env.update(payload)
    return env


def get_accessible_snapshot(
    site_id: str,
    root: Optional[str] = None,
    path: Optional[str] = None,
    viewport: Optional[str] = None,
) -> Dict[str, Any]:
    """Navigate the bound preview and return a capped a11y tree."""
    root_sel = None
    if root is not None and str(root).strip():
        root_sel = validate_css_selector(root)
    vp_name, _, _ = resolve_viewport(viewport)
    url = build_preview_url(site_id, path)
    with open_inspect_page(
        site_id=site_id, path=path, viewport=viewport, block_media=True
    ) as page:
        payload = accessible_snapshot_on_page(page, root_sel)
    env = inspect_envelope(site_id, vp_name, url)
    env.update(payload)
    return env


def get_render_fingerprint(
    site_id: str,
    selector: Optional[str] = None,
    path: Optional[str] = None,
    viewport: Optional[str] = None,
) -> Dict[str, Any]:
    """Navigate the bound preview and return a 16-byte PNG hash (no pixels)."""
    sel = None
    if selector is not None and str(selector).strip():
        sel = validate_css_selector(selector)
    vp_name, _, _ = resolve_viewport(viewport)
    url = build_preview_url(site_id, path)
    with open_inspect_page(site_id=site_id, path=path, viewport=viewport) as page:
        payload = fingerprint_on_page(page, sel)
    env = inspect_envelope(site_id, vp_name, url)
    env.update(payload)
    return env


def capture_theme_screenshot(
    site_id: str,
    selector: Optional[str] = None,
    path: Optional[str] = None,
    viewport: Optional[str] = None,
    full_page: bool = False,
    include_image: bool = False,
    digest: Optional[str] = None,
) -> Dict[str, Any]:
    """Screenshot viewport or clip; optional cache hit via ``digest``.

    Default omits ``data_url``. Pixels are returned only when ``include_image``
    is true and the encoded payload is under ``SCREENSHOT_MAX_BYTES``.
    """
    png, vp_name, url = load_screenshot_png(
        site_id,
        selector=selector,
        path=path,
        viewport=viewport,
        full_page=full_page,
        digest=digest,
    )
    meta = fingerprint_png(png)
    payload: Dict[str, Any] = dict(meta)
    extra_hint = None
    if include_image:
        encoded = encode_screenshot_data_url(png)
        if encoded:
            payload["mime"], payload["data_url"] = encoded
        else:
            extra_hint = SCREENSHOT_CLIP_HINT
    else:
        extra_hint = SCREENSHOT_INCLUDE_HINT
    env = inspect_envelope(site_id, vp_name, url)
    env.update(payload)
    env["hint"] = _merge_hints(env.get("hint"), extra_hint)
    return env


def goto_preview(page: Any, url: str, timeout_ms: int = NAV_TIMEOUT_MS) -> None:
    """Navigate with the inspect timeout; map net/timeout to PREVIEW_UNREACHABLE."""
    try:
        page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
    except ThemeRenderInspectError:
        raise
    except Exception as exc:
        logger.info("Preview navigation failed for %s: %s", url, exc)
        _raise(
            "PREVIEW_UNREACHABLE",
            f"Preview origin did not respond: {exc}",
            PREVIEW_HINT,
        )


def _launch_chromium() -> Tuple[Any, Any]:
    """Start Playwright and launch headless Chromium. Tests may monkeypatch this."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise ThemeRenderInspectError(
            "BROWSER_UNAVAILABLE",
            f"Playwright is not installed: {exc}",
            BROWSER_HINT,
        ) from exc
    playwright = sync_playwright().start()
    try:
        browser = playwright.chromium.launch(headless=True)
    except Exception:
        try:
            playwright.stop()
        except Exception:
            pass
        raise
    return playwright, browser


def _shutdown_browser_unlocked() -> None:
    global _playwright, _browser, _browser_thread, _idle_timer
    if _idle_timer is not None:
        _idle_timer.cancel()
        _idle_timer = None
    if _browser is not None:
        try:
            _browser.close()
        except Exception:
            logger.debug("Error closing inspect browser", exc_info=True)
        _browser = None
    if _playwright is not None:
        try:
            _playwright.stop()
        except Exception:
            logger.debug("Error stopping playwright", exc_info=True)
        _playwright = None
    _browser_thread = None


def shutdown_inspect_browser() -> None:
    """Close the singleton Chromium (tests / atexit).

    Playwright sync objects must be closed on the thread that created them.
    """
    global _browser_thread
    _cancel_idle_timer()
    owner = _browser_thread
    me = threading.current_thread()
    if owner is None or owner is me:
        with _INSPECT_LOCK:
            _shutdown_browser_unlocked()
        return
    if owner is _INSPECT_WORKER._thread and owner.is_alive():
        try:
            run_on_inspect_thread(_shutdown_browser_unlocked)
            return
        except Exception:
            logger.debug("Inspect worker shutdown failed", exc_info=True)
    with _INSPECT_LOCK:
        _shutdown_browser_unlocked()


def _cancel_idle_timer() -> None:
    global _idle_timer
    if _idle_timer is not None:
        _idle_timer.cancel()
        _idle_timer = None


def _idle_teardown() -> None:
    try:
        shutdown_inspect_browser()
    except Exception:
        logger.debug("Idle teardown of inspect Chromium failed", exc_info=True)


def _schedule_idle_teardown() -> None:
    global _idle_timer
    _cancel_idle_timer()
    _idle_timer = threading.Timer(IDLE_TEARDOWN_S, _idle_teardown)
    _idle_timer.daemon = True
    _idle_timer.start()


def _ensure_browser() -> Any:
    global _playwright, _browser, _browser_thread
    if _browser is not None:
        if _browser_thread is threading.current_thread():
            return _browser
        logger.info("Inspect browser was created on another thread; launching a new one")
        _playwright = None
        _browser = None
        _browser_thread = None
    try:
        _playwright, _browser = _launch_chromium()
        _browser_thread = threading.current_thread()
    except ThemeRenderInspectError:
        _shutdown_browser_unlocked()
        raise
    except Exception as exc:
        _shutdown_browser_unlocked()
        logger.info("Chromium launch failed: %s", exc)
        raise ThemeRenderInspectError(
            "BROWSER_UNAVAILABLE",
            f"Chromium is not available: {exc}",
            BROWSER_HINT,
        ) from exc
    return _browser


def _remaining_timeout_ms(started: float) -> int:
    remaining_s = TOTAL_BUDGET_S - (time.monotonic() - started)
    remaining_ms = int(remaining_s * 1000)
    if remaining_ms < 1:
        _raise(
            "PREVIEW_UNREACHABLE",
            "Inspect exceeded the total budget before navigation finished.",
            PREVIEW_HINT,
        )
    return min(NAV_TIMEOUT_MS, remaining_ms)


def should_block_inspect_media(url: str) -> bool:
    """True for images/fonts. CSS under /api/assets/ is not blocked (computed style)."""
    path = urlparse(url).path or ""
    return bool(_MEDIA_EXT_RE.search(path))


def _media_route_handler(route: Any) -> None:
    """Abort image/font requests; ``continue_`` everything else (including the document)."""
    try:
        url = route.request.url
        if should_block_inspect_media(url):
            route.abort()
        else:
            route.continue_()
    except Exception:
        logger.debug("Inspect media route failed", exc_info=True)
        try:
            route.continue_()
        except Exception:
            pass


@contextmanager
def open_inspect_page(
    *,
    viewport: Optional[str] = None,
    html: Optional[str] = None,
    url: Optional[str] = None,
    site_id: Optional[str] = None,
    path: Optional[str] = None,
    block_media: bool = False,
) -> Iterator[Any]:
    """Lock, lazy-launch Chromium, new context+page; ``set_content`` or ``goto``.

    ``html=`` is for tests (fixture HTML, no PHP). Live inspect passes ``site_id``
    (and optional ``path`` / ``url``). ``block_media`` skips images/fonts so
    text inspect (a11y/boxes/describe) is not blocked by hero assets.
    Fingerprint/screenshots must leave it false.

    Chromium launch is not counted against the navigation timeout. Playwright
    sync API must run on one thread; routers use ``invoke_inspect``.
    """
    vp_name, width, height = resolve_viewport(viewport)
    del vp_name
    target = url
    if html is None:
        if target is None:
            if not site_id:
                raise ValueError("open_inspect_page requires html=, url=, or site_id=")
            target = build_preview_url(site_id, path)

    with _INSPECT_LOCK:
        _cancel_idle_timer()
        try:
            browser = _ensure_browser()
        except ThemeRenderInspectError:
            raise
        except Exception as exc:
            logger.info("Inspect browser attach failed: %s", exc)
            _raise(
                "BROWSER_UNAVAILABLE",
                f"Inspect browser failed: {exc}",
                BROWSER_HINT,
            )
        started = time.monotonic()
        try:
            context = browser.new_context(viewport={"width": width, "height": height})
            page = context.new_page()
        except ThemeRenderInspectError:
            raise
        except Exception as exc:
            logger.info("Inspect context failed: %s", exc)
            _raise(
                "BROWSER_UNAVAILABLE",
                f"Inspect browser failed: {exc}",
                BROWSER_HINT,
            )
        try:
            if block_media and hasattr(context, "route"):
                context.route("**/*", _media_route_handler)
            timeout_ms = _remaining_timeout_ms(started)
            if html is not None:
                page.set_content(html, timeout=timeout_ms)
            else:
                goto_preview(page, target, timeout_ms=timeout_ms)
            yield page
        finally:
            try:
                context.close()
            except Exception:
                logger.debug("Error closing inspect context", exc_info=True)
            _schedule_idle_teardown()


atexit.register(shutdown_inspect_browser)
