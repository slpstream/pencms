"""MCP tools for Theme Customize render inspect.

Slice 2: ``describe_element`` and ``get_layout_boxes``.
Slice 3: ``get_accessible_snapshot`` and ``get_render_fingerprint``.
Slice 5: ``capture_theme_screenshot`` (pixels opt-in via ``include_image``).
Slice 6: screenshot ``describe`` / ``hash`` sub-path (harness-only; same
``operation_id``, not a new inspect tool).
Thin wrappers around ``theme_render_inspect_service``. JWT ``site_id`` is
authoritative; agents pass a relative ``/blog/`` path, never an origin.
``tags=["mcp"]`` so fastapi-mcp publishes them.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

from models.user import UserPublic
from routers.auth import get_current_user
from routers.mcp_tools import _call_llm_chat, require_scope, resolve_mcp_site_id
from services.theme_render_inspect_service import (
    DESCRIBE_TEXT_ONLY_HINT,
    ThemeRenderInspectError,
    build_describe_messages,
    capture_theme_screenshot,
    describe_element,
    get_accessible_snapshot,
    get_layout_boxes,
    get_render_fingerprint,
    invoke_inspect,
    load_screenshot_for_describe,
    parse_describe_response,
)

router = APIRouter(prefix="/api/v1", tags=["mcp"])

DESCRIBE_ELEMENT_DOC = """Inspect computed style and same-origin matched CSS rules for one element.

Navigates the bound site's public preview (``/blog/?site={jwt site_id}``) and
describes the **first** match of a CSS selector: computed-style subset (display,
position, box model, overflow, flex/grid, font-size, color, background) plus
matched rules (selector, href, specificity, winning props). ``match_count`` is
the live total; only the first match is described.

Pass a relative ``/blog/`` path (default ``/blog/``), never an absolute URL.
``viewport`` is ``desktop`` (1280x800) or ``mobile`` (390x844). CSS selectors
only (max 200 chars; no ``xpath=`` / ``js=``).

If the custom theme is not active, the call still succeeds with
``theme_active: false`` and a hint — results describe the live render, not the
custom tree on disk.

Errors: ``PREVIEW_UNREACHABLE``, ``BROWSER_UNAVAILABLE``, ``PATH_REJECTED``,
``SELECTOR_NOT_FOUND``, ``INVALID_SELECTOR``, ``INVALID_VIEWPORT``.

Examples:
{"selector":".site-header"}
{"selector":"h1.hero-title","path":"/blog/page.php?slug=about","viewport":"mobile"}
"""

GET_LAYOUT_BOXES_DOC = """Inspect layout geometry for one or more CSS selectors.

Navigates the bound site's public preview and returns one box per selector
(first match): ``{selector, x, y, w, h, visible}`` plus ``clipping_ancestor``
when an ancestor has overflow hidden/auto/scroll.

Pass 1–20 CSS selectors (each max 200 chars; no ``xpath=`` / ``js=``). Relative
``/blog/`` path only; ``viewport`` is ``desktop`` or ``mobile``. Inactive custom
theme warns via ``theme_active`` / ``hint``; it does not refuse.

Partial misses do not fail: hit selectors return boxes; missed selectors are
listed in ``missing`` and ``candidates`` suggests ready-to-use selectors from
the live DOM, scoped by landmark (e.g. ``header .nav-menu``).
``SELECTOR_NOT_FOUND`` is raised only when nothing matched.

Errors: ``PREVIEW_UNREACHABLE``, ``BROWSER_UNAVAILABLE``, ``PATH_REJECTED``,
``SELECTOR_NOT_FOUND``, ``INVALID_SELECTOR``, ``INVALID_VIEWPORT``.

Examples:
{"selectors":[".site-header",".site-footer"]}
{"selectors":[".hero"],"path":"/blog/","viewport":"desktop"}
"""

GET_ACCESSIBLE_SNAPSHOT_DOC = """Inspect a compact accessibility tree of the live preview.

Navigates the bound site's public preview and returns one JSON node
``{role, name, visible, children[]}`` (never YAML). Optional ``root`` CSS
selector scopes the tree; omit for the document. Caps: max depth 8, max 80
nodes, names truncated to 120 characters. ``truncated`` is true when a cap
fired. ``visible`` is true for Playwright aria-snapshot nodes (hidden nodes
are omitted); the evaluate fallback uses computed style.

Pass a relative ``/blog/`` path (default ``/blog/``), never an absolute URL.
``viewport`` is ``desktop`` (1280x800) or ``mobile`` (390x844). CSS selectors
only (max 200 chars; no ``xpath=`` / ``js=``). Inactive custom theme warns
via ``theme_active`` / ``hint``; it does not refuse.

Errors: ``PREVIEW_UNREACHABLE``, ``BROWSER_UNAVAILABLE``, ``PATH_REJECTED``,
``SELECTOR_NOT_FOUND``, ``INVALID_SELECTOR``, ``INVALID_VIEWPORT``.

Examples:
{"root":".site-header"}
{"path":"/blog/","viewport":"mobile"}
"""

GET_RENDER_FINGERPRINT_DOC = """Hash of a live preview viewport (or clipped element) PNG.

Navigates the bound site's public preview, screenshots the viewport (or the
first match of optional ``selector``), and returns ``{hash, width, height}``.
``hash`` is 16 bytes of SHA-256 as 32 lowercase hex characters. ``width`` /
``height`` come from the PNG header. **No pixels** are returned.

Pass a relative ``/blog/`` path (default ``/blog/``), never an absolute URL.
``viewport`` is ``desktop`` or ``mobile``. CSS selectors only (max 200 chars;
no ``xpath=`` / ``js=``). Inactive custom theme warns via ``theme_active`` /
``hint``; it does not refuse.

Errors: ``PREVIEW_UNREACHABLE``, ``BROWSER_UNAVAILABLE``, ``PATH_REJECTED``,
``SELECTOR_NOT_FOUND``, ``INVALID_SELECTOR``, ``INVALID_VIEWPORT``.

Examples:
{}
{"selector":".site-header","viewport":"desktop"}
"""

CAPTURE_THEME_SCREENSHOT_DOC = """Screenshot the live preview viewport or a clipped element.

Navigates the bound site's public preview and captures a PNG of the viewport
(or the first match of optional ``selector``). Optional ``full_page`` (default
false) is height-capped; a selector clip wins over ``full_page``.

Default response is ``{hash, width, height}`` with **no** ``data_url`` so
text-only models stay safe. Pass query (or body) ``include_image=true`` to
include ``mime`` + ``data_url`` when the encoded payload is under 100KB;
otherwise the hash is returned with a hint to clip. Prefer
``describe_element`` / ``get_layout_boxes`` first; use this when the operator
asks to see pixels or a fingerprint changed.

Harness-only sub-path (not a separate MCP tool): ``hash`` reads the site-scoped
temp PNG cache (TTL 600s) and recaptures only on miss when path/selector/
``full_page`` are set. ``describe=true`` runs a one-shot Vault chat completion
(no tools) and returns ``{description, findings[]}`` as text — never
``mime`` / ``data_url``. If the chat model rejects image inputs, the call
still succeeds with a hint to use text inspect tools. Do not invent a
vision-describe tool.

Pass a relative ``/blog/`` path (default ``/blog/``), never an absolute URL.
``viewport`` is ``desktop`` or ``mobile``. CSS selectors only (max 200 chars;
no ``xpath=`` / ``js=``). Inactive custom theme warns via ``theme_active`` /
``hint``; it does not refuse.

Errors: ``PREVIEW_UNREACHABLE``, ``BROWSER_UNAVAILABLE``, ``PATH_REJECTED``,
``SELECTOR_NOT_FOUND``, ``INVALID_SELECTOR``, ``INVALID_VIEWPORT``,
``SCREENSHOT_CACHE_MISS``.

Examples:
{}
{"selector":".site-header","viewport":"desktop"}
{"selector":".site-footer","include_image":true}
"""


def _map_inspect_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ThemeRenderInspectError) and getattr(exc, "payload", None):
        return HTTPException(status_code=400, detail=exc.payload())
    return HTTPException(status_code=400, detail=str(exc))


class DescribeElementBody(BaseModel):
    selector: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="CSS selector (one). The first match is described; match_count is the live total.",
    )
    path: Optional[str] = Field(
        default=None,
        description="Relative /blog/ path. Default /blog/. Absolute URLs are rejected.",
    )
    viewport: Optional[str] = Field(
        default="desktop",
        description="desktop (1280x800) or mobile (390x844).",
    )


class LayoutBoxesBody(BaseModel):
    selectors: List[str] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="CSS selectors (1–20). One box per selector (first match).",
    )
    path: Optional[str] = Field(
        default=None,
        description="Relative /blog/ path. Default /blog/. Absolute URLs are rejected.",
    )
    viewport: Optional[str] = Field(
        default="desktop",
        description="desktop (1280x800) or mobile (390x844).",
    )


@router.post(
    "/mcp/theme/inspect/element",
    operation_id="describe_element",
    dependencies=[Depends(require_scope("read"))],
    summary="Describe a live element's computed style and matched CSS rules",
    description=DESCRIBE_ELEMENT_DOC,
)
async def mcp_describe_element(
    body: DescribeElementBody,
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    site_id = resolve_mcp_site_id(request)
    try:
        return await asyncio.to_thread(
            invoke_inspect,
            describe_element,
            site_id,
            body.selector,
            body.path,
            body.viewport,
        )
    except ThemeRenderInspectError as e:
        raise _map_inspect_error(e) from e


mcp_describe_element.__doc__ = DESCRIBE_ELEMENT_DOC


@router.post(
    "/mcp/theme/inspect/boxes",
    operation_id="get_layout_boxes",
    dependencies=[Depends(require_scope("read"))],
    summary="Get layout boxes and clipping ancestors for CSS selectors",
    description=GET_LAYOUT_BOXES_DOC,
)
async def mcp_get_layout_boxes(
    body: LayoutBoxesBody,
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    site_id = resolve_mcp_site_id(request)
    try:
        return await asyncio.to_thread(
            invoke_inspect,
            get_layout_boxes,
            site_id,
            body.selectors,
            body.path,
            body.viewport,
        )
    except ThemeRenderInspectError as e:
        raise _map_inspect_error(e) from e


mcp_get_layout_boxes.__doc__ = GET_LAYOUT_BOXES_DOC


class AccessibleSnapshotBody(BaseModel):
    root: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Optional CSS selector to scope the a11y tree. Omit for the document.",
    )
    path: Optional[str] = Field(
        default=None,
        description="Relative /blog/ path. Default /blog/. Absolute URLs are rejected.",
    )
    viewport: Optional[str] = Field(
        default="desktop",
        description="desktop (1280x800) or mobile (390x844).",
    )


class RenderFingerprintBody(BaseModel):
    selector: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Optional CSS selector clip. Omit for the full viewport.",
    )
    path: Optional[str] = Field(
        default=None,
        description="Relative /blog/ path. Default /blog/. Absolute URLs are rejected.",
    )
    viewport: Optional[str] = Field(
        default="desktop",
        description="desktop (1280x800) or mobile (390x844).",
    )


class ScreenshotBody(BaseModel):
    selector: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Optional CSS selector clip. Omit for the viewport (or full_page).",
    )
    path: Optional[str] = Field(
        default=None,
        description="Relative /blog/ path. Default /blog/. Absolute URLs are rejected.",
    )
    viewport: Optional[str] = Field(
        default="desktop",
        description="desktop (1280x800) or mobile (390x844).",
    )
    full_page: bool = Field(
        default=False,
        description="Capture a height-capped full page. Ignored when selector is set.",
    )
    include_image: Optional[bool] = Field(
        default=None,
        description="Also accepted in JSON for HTTP clients that POST all args in the body. Canonical flag is the include_image query param.",
    )
    hash: Optional[str] = Field(
        default=None,
        description="Harness-only. 32-hex cache key from a prior capture. Recaptures only on miss when path/selector/full_page are set.",
    )
    describe: Optional[bool] = Field(
        default=None,
        description="Harness-only. If true, return {description, findings[]} from a one-shot Vault completion (no tools, no data_url). Also accepted as a query flag.",
    )


@router.post(
    "/mcp/theme/inspect/a11y",
    operation_id="get_accessible_snapshot",
    dependencies=[Depends(require_scope("read"))],
    summary="Get a compact accessibility tree of the live preview",
    description=GET_ACCESSIBLE_SNAPSHOT_DOC,
)
async def mcp_get_accessible_snapshot(
    body: AccessibleSnapshotBody,
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    site_id = resolve_mcp_site_id(request)
    try:
        return await asyncio.to_thread(
            invoke_inspect,
            get_accessible_snapshot,
            site_id,
            body.root,
            body.path,
            body.viewport,
        )
    except ThemeRenderInspectError as e:
        raise _map_inspect_error(e) from e


mcp_get_accessible_snapshot.__doc__ = GET_ACCESSIBLE_SNAPSHOT_DOC


@router.post(
    "/mcp/theme/inspect/fingerprint",
    operation_id="get_render_fingerprint",
    dependencies=[Depends(require_scope("read"))],
    summary="Hash a live preview viewport or clipped element (no pixels)",
    description=GET_RENDER_FINGERPRINT_DOC,
)
async def mcp_get_render_fingerprint(
    body: RenderFingerprintBody,
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> Dict[str, Any]:
    site_id = resolve_mcp_site_id(request)
    try:
        return await asyncio.to_thread(
            invoke_inspect,
            get_render_fingerprint,
            site_id,
            body.selector,
            body.path,
            body.viewport,
        )
    except ThemeRenderInspectError as e:
        raise _map_inspect_error(e) from e


mcp_get_render_fingerprint.__doc__ = GET_RENDER_FINGERPRINT_DOC


def _merge_inspect_hints(*parts: Optional[str]) -> Optional[str]:
    bits = [str(p).strip() for p in parts if p and str(p).strip()]
    return " ".join(bits) or None


def _is_image_input_not_supported(exc: BaseException) -> bool:
    detail = ""
    if isinstance(exc, HTTPException):
        detail = str(exc.detail or "")
    else:
        detail = str(exc)
    lowered = detail.lower()
    return (
        "image_input_not_supported" in lowered
        or "does not support image inputs" in lowered
    )


@router.post(
    "/mcp/theme/inspect/screenshot",
    operation_id="capture_theme_screenshot",
    dependencies=[Depends(require_scope("read"))],
    summary="Screenshot a live preview viewport or clipped element",
    description=CAPTURE_THEME_SCREENSHOT_DOC,
)
async def mcp_capture_theme_screenshot(
    body: ScreenshotBody,
    request: Request,
    include_image: bool = Query(
        False,
        description="If true, include mime + data_url when the payload is under 100KB. Default omits pixels.",
    ),
    describe: bool = Query(
        False,
        description="Harness-only. If true, return a text description from a one-shot Vault completion (no tools).",
    ),
    current_user: UserPublic = Depends(get_current_user),
    x_pen_ai_key: Optional[str] = Header(None, alias="X-Pen-AI-Key"),
    x_pen_ai_base_url: Optional[str] = Header(None, alias="X-Pen-AI-Base-URL"),
    x_pen_ai_model: Optional[str] = Header(None, alias="X-Pen-AI-Model"),
) -> Dict[str, Any]:
    site_id = resolve_mcp_site_id(request)
    want_image = bool(include_image) or bool(body.include_image)
    want_describe = bool(describe) or bool(body.describe)
    digest = (body.hash or "").strip() or None
    try:
        if want_describe:
            png, env = await asyncio.to_thread(
                invoke_inspect,
                load_screenshot_for_describe,
                site_id,
                body.selector,
                body.path,
                body.viewport,
                body.full_page,
                digest,
            )
            env.pop("mime", None)
            env.pop("data_url", None)
            parsed = await _describe_screenshot_completion(
                png,
                x_pen_ai_key=x_pen_ai_key,
                x_pen_ai_base_url=x_pen_ai_base_url,
                x_pen_ai_model=x_pen_ai_model,
            )
            env["description"] = parsed["description"]
            env["findings"] = parsed["findings"]
            extra = parsed.get("hint")
            env["hint"] = _merge_inspect_hints(env.get("hint"), extra)
            return env
        return await asyncio.to_thread(
            invoke_inspect,
            capture_theme_screenshot,
            site_id,
            body.selector,
            body.path,
            body.viewport,
            body.full_page,
            want_image,
            digest,
        )
    except ThemeRenderInspectError as e:
        raise _map_inspect_error(e) from e


async def _describe_screenshot_completion(
    png: bytes,
    *,
    x_pen_ai_key: Optional[str],
    x_pen_ai_base_url: Optional[str],
    x_pen_ai_model: Optional[str],
) -> Dict[str, Any]:
    """One-shot Vault chat (no tools). Image rejection becomes a text hint."""
    model = x_pen_ai_model
    if not model:
        return {
            "description": "",
            "findings": [],
            "hint": DESCRIBE_TEXT_ONLY_HINT,
        }
    base_url = x_pen_ai_base_url or "https://api.openai.com/v1"
    try:
        raw_text = await _call_llm_chat(
            messages=build_describe_messages(png),
            base_url=base_url,
            model=model,
            api_key=x_pen_ai_key,
            temperature=0.2,
        )
    except HTTPException as exc:
        if _is_image_input_not_supported(exc):
            return {
                "description": "",
                "findings": [],
                "hint": DESCRIBE_TEXT_ONLY_HINT,
            }
        return {
            "description": "",
            "findings": [],
            "hint": f"Vision describe failed: {exc.detail}. Use describe_element / get_layout_boxes / get_accessible_snapshot.",
        }
    except Exception as exc:
        return {
            "description": "",
            "findings": [],
            "hint": f"Vision describe failed: {exc}. Use describe_element / get_layout_boxes / get_accessible_snapshot.",
        }
    parsed = parse_describe_response(raw_text)
    return {"description": parsed["description"], "findings": parsed["findings"]}


mcp_capture_theme_screenshot.__doc__ = CAPTURE_THEME_SCREENSHOT_DOC
