"""Unit tests for the Theme Customize render-inspect harness (Slices 1–6).

Default CI does not launch Chromium. Optional
``@pytest.mark.playwright`` uses ``page.set_content`` on fixture HTML and
skips if the browser is missing.
"""

from __future__ import annotations

import hashlib
import threading
import time
from contextlib import contextmanager
from io import BytesIO

import pytest


from services.theme_render_inspect_service import (
    COMPUTED_STYLE_KEYS,
    DESCRIBE_SCREENSHOT_PROMPT,
    FINGERPRINT_BYTES,
    MAX_A11Y_DEPTH,
    MAX_A11Y_NAME,
    MAX_A11Y_NODES,
    MAX_BOX_SELECTORS,
    MAX_SELECTOR_LEN,
    NAV_TIMEOUT_MS,
    SCREENSHOT_CACHE_MISS_HINT,
    SCREENSHOT_CLIP_HINT,
    SCREENSHOT_INCLUDE_HINT,
    SCREENSHOT_MAX_FULL_PAGE_HEIGHT,
    THEME_INACTIVE_HINT,
    ThemeRenderInspectError,
    accessible_snapshot_on_page,
    build_describe_messages,
    build_preview_url,
    cache_screenshot_png,
    cap_a11y_tree,
    capture_png_on_page,
    capture_theme_screenshot,
    describe_element,
    describe_element_on_page,
    encode_screenshot_data_url,
    evaluate,
    fingerprint_on_page,
    fingerprint_png,
    get_accessible_snapshot,
    get_layout_boxes,
    get_render_fingerprint,
    goto_preview,
    inspect_envelope,
    invoke_inspect,
    layout_boxes_on_page,
    load_screenshot_png,
    open_inspect_page,
    parse_aria_snapshot_yaml,
    parse_describe_response,
    read_cached_screenshot_png,
    resolve_viewport,
    run_on_inspect_thread,
    screenshot_on_page,
    should_block_inspect_media,
    shutdown_inspect_browser,
    validate_css_selector,
    validate_selector_list,
)


ORIGIN = "http://127.0.0.1:8009"


DESCRIBE_OK = {
    "selector": "h1#t",
    "match_count": 1,
    "tag": "h1",
    "id": "t",
    "class_name": "",
    "computed": {
        "display": "block",
        "color": "rgb(255, 0, 0)",
        "font-size": "32px",
        "overflow": "visible",
    },
    "matched_rules": [
        {
            "selector": "h1",
            "href": None,
            "specificity": [0, 0, 1],
            "winning_props": ["color", "font-size"],
        }
    ],
    "skipped_cross_origin": 0,
}

BOXES_OK = {
    "boxes": [
        {
            "selector": "#hero",
            "x": 0,
            "y": 8,
            "w": 400,
            "h": 80,
            "visible": True,
            "clipping_ancestor": {
                "selector": "div.clip",
                "overflow": "hidden",
                "overflow_x": "hidden",
                "overflow_y": "hidden",
                "x": 0,
                "y": 0,
                "w": 200,
                "h": 40,
            },
        }
    ]
}

FIXTURE_HTML = """<!doctype html>
<html>
<head>
<style>
  .clip { overflow: hidden; width: 120px; height: 40px; }
  h1#t { color: rgb(255, 0, 0); font-size: 32px; margin: 0; }
</style>
</head>
<body>
  <div class="clip"><h1 id="t">Hello</h1></div>
</body>
</html>
"""

ARIA_YAML = """
- banner:
  - heading "Hello" [level=1]
  - navigation:
    - link "Home"
    - link "About"
- main:
  - paragraph "Welcome"
- button "Submit" [disabled]
"""

A11Y_EVAL_OK = {
    "snapshot": {
        "role": "document",
        "name": "",
        "visible": True,
        "children": [
            {
                "role": "heading",
                "name": "Hello",
                "visible": True,
                "children": [],
            }
        ],
    },
    "node_count": 2,
    "truncated": False,
}

# Valid IHDR width/height only; pixels are never decoded.
PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n"
    + b"\x00\x00\x00\rIHDR"
    + (1).to_bytes(4, "big")
    + (1).to_bytes(4, "big")
    + b"\x08\x06\x00\x00\x00fake"
)


class FakeLocator:
    """Duck-typed Playwright Locator."""

    def __init__(self, *, count=1, aria_yaml=None, screenshot_bytes=None):
        self._count = count
        self._aria_yaml = aria_yaml
        self._screenshot_bytes = screenshot_bytes
        self.first = self

    def count(self):
        return self._count

    def aria_snapshot(self, timeout=None):
        return self._aria_yaml

    def screenshot(self, type="png", **kwargs):
        return self._screenshot_bytes


class FakeLocatorNoAria:
    """Locator without ``aria_snapshot`` (forces evaluate fallback)."""

    def __init__(self, *, count=1, screenshot_bytes=None):
        self._count = count
        self._screenshot_bytes = screenshot_bytes
        self.first = self

    def count(self):
        return self._count

    def screenshot(self, type="png", **kwargs):
        return self._screenshot_bytes


class FakePage:
    """Duck-typed Playwright Page for unit tests (no Chromium)."""

    def __init__(
        self,
        *,
        goto_error: Exception | None = None,
        eval_result="Hello",
        locator=None,
        screenshot_bytes=None,
    ):
        self.goto_error = goto_error
        self.eval_result = eval_result
        self.html = None
        self.gotos = []
        self.last_expression = None
        self.last_arg = None
        self.last_selector = None
        self._locator = locator
        self.screenshot_bytes = screenshot_bytes
        self.viewport_size = {"width": 1280, "height": 800}
        self.last_screenshot_kwargs = None

    def evaluate(self, expression, arg=None):
        self.last_expression = expression
        self.last_arg = arg
        if callable(self.eval_result):
            return self.eval_result(expression, arg)
        return self.eval_result

    def goto(self, url, timeout=None, wait_until=None):
        self.gotos.append({"url": url, "timeout": timeout, "wait_until": wait_until})
        if self.goto_error is not None:
            raise self.goto_error
        return None

    def set_content(self, html, timeout=None):
        self.html = html

    def locator(self, selector):
        self.last_selector = selector
        if self._locator is not None:
            return self._locator
        return FakeLocatorNoAria(count=1, screenshot_bytes=self.screenshot_bytes)

    def screenshot(self, type="png", full_page=False, **kwargs):
        self.last_screenshot_kwargs = {"type": type, "full_page": full_page, **kwargs}
        return self.screenshot_bytes


@pytest.fixture
def preview_origin(monkeypatch):
    monkeypatch.delenv("PENCMS_PREVIEW_BASE_URL", raising=False)
    monkeypatch.setattr(
        "services.theme_render_inspect_service.get_preview_base_url",
        lambda: ORIGIN,
    )
    return ORIGIN


def _path_error(exc: ThemeRenderInspectError) -> None:
    assert exc.error == "PATH_REJECTED"
    assert exc.payload()["error"] == "PATH_REJECTED"
    assert "hint" in exc.payload()


def test_build_preview_url_forces_site(preview_origin):
    url = build_preview_url("wiki")
    assert url == "http://127.0.0.1:8009/blog/?site=wiki"


def test_build_preview_url_strips_model_site(preview_origin):
    url = build_preview_url("wiki", "/blog/?site=evil&slug=about")
    assert url.startswith("http://127.0.0.1:8009/blog/")
    assert "site=wiki" in url
    assert "site=evil" not in url
    assert "slug=about" in url


def test_build_preview_url_page_php(preview_origin):
    url = build_preview_url("wiki", "/blog/page.php?slug=about")
    assert url.startswith("http://127.0.0.1:8009/blog/page.php?")
    assert "site=wiki" in url
    assert "slug=about" in url


def test_build_preview_url_lang_prefix(preview_origin):
    url = build_preview_url("wiki", "/blog/fr/about/")
    assert url == "http://127.0.0.1:8009/blog/fr/about/?site=wiki"


@pytest.mark.parametrize(
    "path",
    [
        "http://evil.example/blog/",
        "https://127.0.0.1:8009/blog/",
        "//evil.example/blog/",
        "/blog/../admin/",
        "/blog/%2e%2e/admin",
        "/admin/",
        "/blog/:8008/",
        "/blog/user@host/",
        "ftp://127.0.0.1/blog/",
    ],
)
def test_build_preview_url_rejects_unsafe_paths(preview_origin, path):
    with pytest.raises(ThemeRenderInspectError) as caught:
        build_preview_url("wiki", path)
    _path_error(caught.value)


def test_build_preview_url_rejects_other_host_in_path(preview_origin):
    with pytest.raises(ThemeRenderInspectError) as caught:
        build_preview_url("wiki", "http://192.168.0.1:8009/blog/")
    _path_error(caught.value)


def test_unset_base_url_preview_unreachable(monkeypatch):
    monkeypatch.delenv("PENCMS_PREVIEW_BASE_URL", raising=False)
    monkeypatch.setattr(
        "services.theme_render_inspect_service.get_preview_base_url",
        lambda: None,
    )
    with pytest.raises(ThemeRenderInspectError) as caught:
        build_preview_url("wiki")
    assert caught.value.error == "PREVIEW_UNREACHABLE"
    assert "PENCMS_PREVIEW_BASE_URL" in caught.value.hint


def test_empty_base_url_preview_unreachable(monkeypatch):
    monkeypatch.setattr(
        "services.theme_render_inspect_service.get_preview_base_url",
        lambda: "",
    )
    with pytest.raises(ThemeRenderInspectError) as caught:
        build_preview_url("wiki")
    assert caught.value.error == "PREVIEW_UNREACHABLE"


@pytest.mark.parametrize("base", ["not-a-url", "ftp://127.0.0.1:8009", "http://"])
def test_malformed_base_url_preview_unreachable(monkeypatch, base):
    monkeypatch.setattr(
        "services.theme_render_inspect_service.get_preview_base_url",
        lambda: base,
    )
    with pytest.raises(ThemeRenderInspectError) as caught:
        build_preview_url("wiki")
    assert caught.value.error == "PREVIEW_UNREACHABLE"


def test_get_preview_base_url_env_wins(monkeypatch):
    import config

    monkeypatch.setenv("PENCMS_PREVIEW_BASE_URL", "http://127.0.0.1:8009/")
    assert config.get_preview_base_url() == "http://127.0.0.1:8009"


def test_get_preview_base_url_unset_does_not_raise(monkeypatch):
    import configparser

    import config

    monkeypatch.delenv("PENCMS_PREVIEW_BASE_URL", raising=False)
    monkeypatch.setattr(config, "_config", configparser.ConfigParser())
    assert config.get_preview_base_url() is None


def test_resolve_viewport_defaults_and_presets():
    assert resolve_viewport(None) == ("desktop", 1280, 800)
    assert resolve_viewport("desktop") == ("desktop", 1280, 800)
    assert resolve_viewport("mobile") == ("mobile", 390, 844)


def test_resolve_viewport_unknown():
    with pytest.raises(ThemeRenderInspectError) as caught:
        resolve_viewport("tablet")
    assert caught.value.error == "INVALID_VIEWPORT"


def test_envelope_inactive_theme_warns(monkeypatch):
    monkeypatch.setattr(
        "services.theme_render_inspect_service.get_theme_context",
        lambda site_id: {"active": False, "preview": {"live_serves_custom": False}},
    )
    env = inspect_envelope("wiki", "desktop", f"{ORIGIN}/blog/?site=wiki")
    assert env["ok"] is True
    assert env["theme_active"] is False
    assert env["hint"] == THEME_INACTIVE_HINT
    assert env["site_id"] == "wiki"
    assert env["viewport"] == "desktop"


def test_envelope_active_no_hint(monkeypatch):
    monkeypatch.setattr(
        "services.theme_render_inspect_service.get_theme_context",
        lambda site_id: {"active": True, "preview": {"live_serves_custom": True}},
    )
    env = inspect_envelope("wiki", "mobile", f"{ORIGIN}/blog/?site=wiki")
    assert env["theme_active"] is True
    assert env["hint"] is None
    assert env["viewport"] == "mobile"


def test_fake_page_evaluate():
    page = FakePage(eval_result="Hello")
    assert evaluate(page, "document.querySelector('#t').textContent") == "Hello"


def test_goto_net_error_preview_unreachable():
    page = FakePage(goto_error=RuntimeError("net::ERR_CONNECTION_REFUSED"))
    with pytest.raises(ThemeRenderInspectError) as caught:
        goto_preview(page, f"{ORIGIN}/blog/?site=wiki")
    assert caught.value.error == "PREVIEW_UNREACHABLE"
    assert page.gotos[0]["timeout"] == NAV_TIMEOUT_MS


def test_browser_unavailable(monkeypatch):
    def _boom():
        raise RuntimeError("Executable doesn't exist")

    monkeypatch.setattr(
        "services.theme_render_inspect_service._launch_chromium",
        _boom,
    )
    shutdown_inspect_browser()
    with pytest.raises(ThemeRenderInspectError) as caught:
        with open_inspect_page(html="<html></html>"):
            pass
    assert caught.value.error == "BROWSER_UNAVAILABLE"
    assert "playwright install" in caught.value.hint


def test_run_on_inspect_thread_reuses_same_thread():
    ids = []

    def job():
        ids.append(threading.get_ident())
        return threading.current_thread().name

    assert run_on_inspect_thread(job) == "pencms-theme-inspect"
    assert run_on_inspect_thread(job) == "pencms-theme-inspect"
    assert ids[0] == ids[1]
    assert ids[0] != threading.get_ident()


def test_invoke_inspect_maps_unexpected_to_browser_unavailable():
    def boom():
        raise RuntimeError("greenlet.error: Cannot switch to a different thread")

    with pytest.raises(ThemeRenderInspectError) as caught:
        invoke_inspect(boom)
    assert caught.value.error == "BROWSER_UNAVAILABLE"
    assert "greenlet" in caught.value.reason


def test_should_block_inspect_media_images_not_css():
    jpg = (
        "http://127.0.0.1:8009/api/assets/raw/sites/default/assets/"
        "images/content/page1/hero.jpg"
    )
    css = (
        "http://127.0.0.1:8009/api/assets/raw/sites/default/theme/"
        "assets/css/styles.css"
    )
    html = "http://127.0.0.1:8009/blog/?site=default"
    assert should_block_inspect_media(jpg) is True
    assert should_block_inspect_media(css) is False
    assert should_block_inspect_media(html) is False


def test_mcp_inspect_routes_registered():
    from main import app

    paths = [getattr(route, "path", "") or "" for route in app.routes]
    assert "/api/v1/mcp/theme/inspect/element" in paths
    assert "/api/v1/mcp/theme/inspect/boxes" in paths
    assert "/api/v1/mcp/theme/inspect/a11y" in paths
    assert "/api/v1/mcp/theme/inspect/fingerprint" in paths
    assert "/api/v1/mcp/theme/inspect/screenshot" in paths


def test_validate_css_selector_ok():
    assert validate_css_selector("  h1.hero  ") == "h1.hero"


@pytest.mark.parametrize(
    "selector",
    ["", "   ", "xpath=//h1", "js=document.body", "XPath=//div", "JS=1"],
)
def test_validate_css_selector_rejects(selector):
    with pytest.raises(ThemeRenderInspectError) as caught:
        validate_css_selector(selector)
    assert caught.value.error == "INVALID_SELECTOR"


def test_validate_css_selector_too_long():
    with pytest.raises(ThemeRenderInspectError) as caught:
        validate_css_selector("a" * (MAX_SELECTOR_LEN + 1))
    assert caught.value.error == "INVALID_SELECTOR"


def test_validate_selector_list_caps():
    with pytest.raises(ThemeRenderInspectError) as caught:
        validate_selector_list([".a"] * (MAX_BOX_SELECTORS + 1))
    assert caught.value.error == "INVALID_SELECTOR"
    with pytest.raises(ThemeRenderInspectError) as caught:
        validate_selector_list([])
    assert caught.value.error == "INVALID_SELECTOR"


def test_describe_element_on_page_known_styles():
    page = FakePage(eval_result=DESCRIBE_OK)
    payload = describe_element_on_page(page, "h1#t")
    assert payload["match_count"] == 1
    assert payload["computed"]["color"] == "rgb(255, 0, 0)"
    assert payload["matched_rules"][0]["winning_props"] == ["color", "font-size"]
    assert payload["skipped_cross_origin"] == 0
    assert page.last_arg == "h1#t"
    for key in ("display", "color", "font-size", "overflow"):
        assert key in payload["computed"]
    assert set(COMPUTED_STYLE_KEYS)  # exported subset used by the live JS


def test_describe_element_on_page_selector_miss():
    page = FakePage(
        eval_result={
            "error": "SELECTOR_NOT_FOUND",
            "match_count": 0,
            "candidates": [".masthead", ".site-title"],
        }
    )
    with pytest.raises(ThemeRenderInspectError) as caught:
        describe_element_on_page(page, ".missing")
    assert caught.value.error == "SELECTOR_NOT_FOUND"
    assert ".missing" in caught.value.reason
    assert ".masthead" in caught.value.hint
    assert ".site-title" in caught.value.hint


def test_layout_boxes_on_page_known_geometry():
    page = FakePage(eval_result=BOXES_OK)
    payload = layout_boxes_on_page(page, ["#hero"])
    box = payload["boxes"][0]
    assert box["selector"] == "#hero"
    assert box["x"] == 0
    assert box["w"] == 400
    assert box["visible"] is True
    assert box["clipping_ancestor"]["overflow"] == "hidden"
    assert payload["missing"] == []
    assert "candidates" not in payload
    assert page.last_arg == ["#hero"]


def test_layout_boxes_on_page_total_miss():
    page = FakePage(
        eval_result={
            "boxes": [],
            "missing": [".gone", ".also-gone"],
            "candidates": [".masthead", ".nav-menu"],
        }
    )
    with pytest.raises(ThemeRenderInspectError) as caught:
        layout_boxes_on_page(page, [".gone", ".also-gone"])
    assert caught.value.error == "SELECTOR_NOT_FOUND"
    assert ".gone" in caught.value.reason
    assert ".also-gone" in caught.value.reason
    assert ".masthead" in caught.value.hint


def test_layout_boxes_on_page_partial_miss_returns_hits():
    page = FakePage(
        eval_result={
            "boxes": list(BOXES_OK["boxes"]),
            "missing": [".brand"],
            "candidates": [".masthead", ".site-title"],
        }
    )
    payload = layout_boxes_on_page(page, ["#hero", ".brand"])
    assert payload["boxes"][0]["selector"] == "#hero"
    assert payload["missing"] == [".brand"]
    assert ".masthead" in payload["candidates"]


def test_describe_element_orchestrator_envelope(preview_origin, monkeypatch):
    monkeypatch.setattr(
        "services.theme_render_inspect_service.get_theme_context",
        lambda site_id: {"active": False},
    )

    @contextmanager
    def fake_open(**kwargs):
        yield FakePage(eval_result=DESCRIBE_OK)

    monkeypatch.setattr(
        "services.theme_render_inspect_service.open_inspect_page",
        fake_open,
    )
    result = describe_element("wiki", "h1#t", path="/blog/", viewport="desktop")
    assert result["ok"] is True
    assert result["site_id"] == "wiki"
    assert result["theme_active"] is False
    assert result["hint"] == THEME_INACTIVE_HINT
    assert result["url"] == "http://127.0.0.1:8009/blog/?site=wiki"
    assert result["match_count"] == 1
    assert result["computed"]["color"] == "rgb(255, 0, 0)"


def test_get_layout_boxes_orchestrator_envelope(preview_origin, monkeypatch):
    monkeypatch.setattr(
        "services.theme_render_inspect_service.get_theme_context",
        lambda site_id: {"active": True},
    )

    @contextmanager
    def fake_open(**kwargs):
        yield FakePage(eval_result=BOXES_OK)

    monkeypatch.setattr(
        "services.theme_render_inspect_service.open_inspect_page",
        fake_open,
    )
    result = get_layout_boxes("wiki", ["#hero"], viewport="mobile")
    assert result["ok"] is True
    assert result["theme_active"] is True
    assert result["hint"] is None
    assert result["viewport"] == "mobile"
    assert result["boxes"][0]["clipping_ancestor"]["selector"] == "div.clip"


def test_fake_page_evaluate_passes_arg():
    page = FakePage(eval_result="Hello")
    assert evaluate(page, "(s) => s", "#t") == "Hello"
    assert page.last_arg == "#t"


@pytest.mark.playwright
def test_set_content_evaluate_with_chromium():
    html = "<!doctype html><html><body><h1 id='t'>Hello</h1></body></html>"
    try:
        with open_inspect_page(html=html, viewport="desktop") as page:
            text = evaluate(page, "document.querySelector('#t').textContent")
    except ThemeRenderInspectError as exc:
        if exc.error == "BROWSER_UNAVAILABLE":
            pytest.skip(exc.reason)
        raise
    finally:
        shutdown_inspect_browser()
    assert text == "Hello"


@pytest.mark.playwright
def test_set_content_describe_and_boxes_with_chromium():
    try:
        with open_inspect_page(html=FIXTURE_HTML, viewport="desktop") as page:
            described = describe_element_on_page(page, "#t")
            boxes = layout_boxes_on_page(page, ["#t"])
    except ThemeRenderInspectError as exc:
        if exc.error == "BROWSER_UNAVAILABLE":
            pytest.skip(exc.reason)
        raise
    finally:
        shutdown_inspect_browser()
    assert described["match_count"] == 1
    assert described["tag"] == "h1"
    assert "rgb(255, 0, 0)" in described["computed"]["color"]
    assert described["computed"]["font-size"] == "32px"
    box = boxes["boxes"][0]
    assert box["visible"] is True
    assert box["w"] > 0
    assert box["clipping_ancestor"] is not None
    assert box["clipping_ancestor"]["overflow"] == "hidden"


def _assert_a11y_node(node):
    assert set(node.keys()) == {"role", "name", "visible", "children"}
    assert isinstance(node["role"], str)
    assert isinstance(node["name"], str)
    assert isinstance(node["visible"], bool)
    assert isinstance(node["children"], list)
    for child in node["children"]:
        _assert_a11y_node(child)


def test_parse_aria_snapshot_yaml_indent_tree():
    tree = parse_aria_snapshot_yaml(ARIA_YAML)
    _assert_a11y_node(tree)
    assert tree["role"] == "document"
    assert tree["visible"] is True
    roles = [c["role"] for c in tree["children"]]
    assert roles == ["banner", "main", "button"]
    banner = tree["children"][0]
    assert banner["children"][0]["role"] == "heading"
    assert banner["children"][0]["name"] == "Hello"
    assert banner["children"][0]["visible"] is True
    nav = banner["children"][1]
    assert nav["role"] == "navigation"
    assert [c["name"] for c in nav["children"]] == ["Home", "About"]
    assert tree["children"][2]["name"] == "Submit"
    assert "level" not in banner["children"][0]
    assert "disabled" not in tree["children"][2]


def test_parse_aria_snapshot_yaml_single_root():
    tree = parse_aria_snapshot_yaml('- heading "Title" [level=1]\n')
    assert tree["role"] == "heading"
    assert tree["name"] == "Title"
    assert tree["children"] == []


def test_parse_aria_snapshot_skips_url_properties():
    tree = parse_aria_snapshot_yaml(
        '- link "Home":\n  - /url: /home\n  - generic "x"\n'
    )
    assert tree["role"] == "link"
    assert tree["name"] == "Home"
    assert len(tree["children"]) == 1
    assert tree["children"][0]["name"] == "x"


def test_cap_a11y_tree_depth():
    node = {"role": "generic", "name": "r", "visible": True, "children": []}
    cur = node
    for i in range(MAX_A11Y_DEPTH + 1):
        child = {"role": "generic", "name": f"d{i}", "visible": True, "children": []}
        cur["children"].append(child)
        cur = child
    capped, count, truncated = cap_a11y_tree(node)
    assert truncated is True
    assert count <= MAX_A11Y_NODES

    def depth_of(n):
        if not n["children"]:
            return 1
        return 1 + max(depth_of(c) for c in n["children"])

    assert depth_of(capped) <= MAX_A11Y_DEPTH


def test_cap_a11y_tree_node_limit():
    tree = {
        "role": "document",
        "name": "",
        "visible": True,
        "children": [
            {"role": "generic", "name": f"c{i}", "visible": True, "children": []}
            for i in range(MAX_A11Y_NODES)
        ],
    }
    capped, count, truncated = cap_a11y_tree(tree)
    assert truncated is True
    assert count == MAX_A11Y_NODES
    assert len(capped["children"]) == MAX_A11Y_NODES - 1


def test_cap_a11y_tree_name_length():
    tree = {
        "role": "heading",
        "name": "x" * (MAX_A11Y_NAME + 1),
        "visible": True,
        "children": [],
    }
    capped, count, truncated = cap_a11y_tree(tree)
    assert truncated is True
    assert len(capped["name"]) == MAX_A11Y_NAME
    assert count == 1


def test_accessible_snapshot_on_page_aria_path():
    loc = FakeLocator(aria_yaml=ARIA_YAML)
    page = FakePage(locator=loc, eval_result={"error": "should-not-evaluate"})
    payload = accessible_snapshot_on_page(page)
    _assert_a11y_node(payload["snapshot"])
    assert payload["root"] is None
    assert payload["snapshot"]["role"] == "document"
    assert payload["node_count"] >= 1
    assert page.last_expression is None


def test_accessible_snapshot_on_page_evaluate_fallback():
    page = FakePage(
        locator=FakeLocatorNoAria(),
        eval_result=A11Y_EVAL_OK,
    )
    payload = accessible_snapshot_on_page(page, root=None)
    _assert_a11y_node(payload["snapshot"])
    assert payload["snapshot"]["children"][0]["name"] == "Hello"
    assert page.last_arg["max_depth"] == MAX_A11Y_DEPTH


def test_accessible_snapshot_on_page_root_miss():
    page = FakePage(locator=FakeLocator(count=0, aria_yaml=ARIA_YAML))
    with pytest.raises(ThemeRenderInspectError) as caught:
        accessible_snapshot_on_page(page, root=".missing")
    assert caught.value.error == "SELECTOR_NOT_FOUND"


def test_accessible_snapshot_orchestrator_envelope(preview_origin, monkeypatch):
    monkeypatch.setattr(
        "services.theme_render_inspect_service.get_theme_context",
        lambda site_id: {"active": False},
    )

    @contextmanager
    def fake_open(**kwargs):
        yield FakePage(locator=FakeLocator(aria_yaml=ARIA_YAML))

    monkeypatch.setattr(
        "services.theme_render_inspect_service.open_inspect_page",
        fake_open,
    )
    result = get_accessible_snapshot("wiki", root=".brand", path="/blog/")
    assert result["ok"] is True
    assert result["theme_active"] is False
    assert result["hint"] == THEME_INACTIVE_HINT
    assert result["root"] == ".brand"
    _assert_a11y_node(result["snapshot"])


def test_fingerprint_png_no_pixels():
    payload = fingerprint_png(PNG_1X1)
    expected = hashlib.sha256(PNG_1X1).digest()[:FINGERPRINT_BYTES].hex()
    assert payload == {"hash": expected, "width": 1, "height": 1}
    assert len(payload["hash"]) == 32
    assert set(payload.keys()) == {"hash", "width", "height"}


def test_fingerprint_on_page_viewport():
    page = FakePage(screenshot_bytes=PNG_1X1)
    payload = fingerprint_on_page(page)
    assert payload["width"] == 1
    assert payload["height"] == 1
    assert "data" not in payload
    assert "data_url" not in payload
    assert "png" not in payload
    assert "pixels" not in payload


def test_fingerprint_on_page_clip():
    loc = FakeLocator(count=1, screenshot_bytes=PNG_1X1)
    page = FakePage(locator=loc, screenshot_bytes=b"not-used")
    payload = fingerprint_on_page(page, selector="#t")
    assert payload["hash"] == hashlib.sha256(PNG_1X1).digest()[:16].hex()
    assert page.last_selector == "#t"


def test_fingerprint_on_page_clip_miss():
    page = FakePage(locator=FakeLocator(count=0, screenshot_bytes=PNG_1X1))
    with pytest.raises(ThemeRenderInspectError) as caught:
        fingerprint_on_page(page, selector=".gone")
    assert caught.value.error == "SELECTOR_NOT_FOUND"


def test_get_render_fingerprint_orchestrator_envelope(preview_origin, monkeypatch):
    monkeypatch.setattr(
        "services.theme_render_inspect_service.get_theme_context",
        lambda site_id: {"active": True},
    )

    @contextmanager
    def fake_open(**kwargs):
        yield FakePage(screenshot_bytes=PNG_1X1)

    monkeypatch.setattr(
        "services.theme_render_inspect_service.open_inspect_page",
        fake_open,
    )
    result = get_render_fingerprint("wiki", viewport="mobile")
    assert result["ok"] is True
    assert result["theme_active"] is True
    assert result["hint"] is None
    assert result["viewport"] == "mobile"
    assert result["width"] == 1
    assert "data_url" not in result


@pytest.mark.playwright
def test_set_content_a11y_and_fingerprint_with_chromium():
    html = """<!doctype html>
<html>
<body>
  <header class="brand"><h1>Hello</h1><nav><a href="/">Home</a></nav></header>
  <p id="t" style="background:red;width:40px;height:20px">Hi</p>
</body>
</html>"""
    try:
        with open_inspect_page(html=html, viewport="desktop") as page:
            a11y = accessible_snapshot_on_page(page)
            before = fingerprint_on_page(page)
            page.evaluate("document.body.style.background = 'blue'")
            after = fingerprint_on_page(page)
            clipped = fingerprint_on_page(page, "#t")
    except ThemeRenderInspectError as exc:
        if exc.error == "BROWSER_UNAVAILABLE":
            pytest.skip(exc.reason)
        raise
    finally:
        shutdown_inspect_browser()
    snap = a11y["snapshot"]
    _assert_a11y_node(snap)
    assert a11y["node_count"] >= 1
    assert before["hash"] != after["hash"]
    assert len(before["hash"]) == 32
    assert "data" not in before
    assert clipped["width"] > 0
    assert clipped["height"] > 0


@pytest.fixture
def inspect_cache(tmp_path, monkeypatch):
    root = tmp_path / "pencms-theme-inspect"
    monkeypatch.setattr(
        "services.theme_render_inspect_service.screenshot_cache_root",
        lambda: root,
    )
    return root


def test_capture_png_on_page_viewport():
    page = FakePage(screenshot_bytes=PNG_1X1)
    png = capture_png_on_page(page)
    assert png == PNG_1X1
    assert page.last_screenshot_kwargs["full_page"] is False
    assert "clip" not in page.last_screenshot_kwargs


def test_capture_png_on_page_clip():
    loc = FakeLocator(count=1, screenshot_bytes=PNG_1X1)
    page = FakePage(locator=loc, screenshot_bytes=b"not-used")
    png = capture_png_on_page(page, selector="#t")
    assert png == PNG_1X1
    assert page.last_selector == "#t"


def test_capture_png_on_page_clip_miss():
    page = FakePage(locator=FakeLocator(count=0, screenshot_bytes=PNG_1X1))
    with pytest.raises(ThemeRenderInspectError) as caught:
        capture_png_on_page(page, selector=".gone")
    assert caught.value.error == "SELECTOR_NOT_FOUND"


def test_capture_png_on_page_full_page_caps_height():
    page = FakePage(screenshot_bytes=PNG_1X1, eval_result=5000)
    png = capture_png_on_page(page, full_page=True)
    assert png == PNG_1X1
    kwargs = page.last_screenshot_kwargs
    assert kwargs["full_page"] is False
    assert kwargs["clip"] == {
        "x": 0,
        "y": 0,
        "width": 1280,
        "height": SCREENSHOT_MAX_FULL_PAGE_HEIGHT,
    }


def test_screenshot_on_page_default_omits_blob(inspect_cache):
    page = FakePage(screenshot_bytes=PNG_1X1)
    payload = screenshot_on_page(page, site_id="wiki")
    expected = hashlib.sha256(PNG_1X1).digest()[:FINGERPRINT_BYTES].hex()
    assert payload["hash"] == expected
    assert payload["width"] == 1
    assert payload["height"] == 1
    assert "data_url" not in payload
    assert "mime" not in payload
    assert payload["hint"] == SCREENSHOT_INCLUDE_HINT
    cached = inspect_cache / "wiki" / f"{expected}.png"
    assert cached.read_bytes() == PNG_1X1


def test_screenshot_on_page_include_image_tiny_png(inspect_cache):
    page = FakePage(screenshot_bytes=PNG_1X1)
    payload = screenshot_on_page(page, site_id="wiki", include_image=True)
    assert payload["mime"] == "image/png"
    assert payload["data_url"].startswith("data:image/png;base64,")
    assert "hint" not in payload


def test_screenshot_on_page_oversized_omits_blob(inspect_cache, monkeypatch):
    monkeypatch.setattr(
        "services.theme_render_inspect_service.SCREENSHOT_MAX_BYTES",
        10,
    )
    page = FakePage(screenshot_bytes=PNG_1X1)
    payload = screenshot_on_page(page, site_id="wiki", include_image=True)
    assert "data_url" not in payload
    assert "mime" not in payload
    assert payload["hint"] == SCREENSHOT_CLIP_HINT


def test_screenshot_cache_purges_expired(inspect_cache, monkeypatch):
    monkeypatch.setattr(
        "services.theme_render_inspect_service.SCREENSHOT_CACHE_TTL_S",
        1,
    )
    stale = inspect_cache / "wiki"
    stale.mkdir(parents=True)
    old = stale / "old.png"
    old.write_bytes(b"stale")
    past = time.time() - 10
    import os

    os.utime(old, (past, past))
    cache_screenshot_png("wiki", "abc", PNG_1X1)
    assert not old.exists()
    assert (stale / "abc.png").read_bytes() == PNG_1X1


def test_encode_screenshot_jpeg_when_png_over_cap(monkeypatch):
    from PIL import Image

    img = Image.new("RGB", (400, 400), (255, 0, 0))
    buf = BytesIO()
    img.save(buf, format="PNG")
    png = buf.getvalue()
    monkeypatch.setattr(
        "services.theme_render_inspect_service.SCREENSHOT_MAX_BYTES",
        max(len(png) - 1, 1),
    )
    encoded = encode_screenshot_data_url(png)
    assert encoded is not None
    mime, url = encoded
    assert mime == "image/jpeg"
    assert url.startswith("data:image/jpeg;base64,")


def test_capture_theme_screenshot_orchestrator_default(preview_origin, inspect_cache, monkeypatch):
    monkeypatch.setattr(
        "services.theme_render_inspect_service.get_theme_context",
        lambda site_id: {"active": False},
    )

    @contextmanager
    def fake_open(**kwargs):
        yield FakePage(screenshot_bytes=PNG_1X1)

    monkeypatch.setattr(
        "services.theme_render_inspect_service.open_inspect_page",
        fake_open,
    )
    result = capture_theme_screenshot("wiki", viewport="mobile")
    assert result["ok"] is True
    assert result["theme_active"] is False
    assert THEME_INACTIVE_HINT in result["hint"]
    assert SCREENSHOT_INCLUDE_HINT in result["hint"]
    assert "data_url" not in result
    assert "mime" not in result
    assert result["viewport"] == "mobile"


def test_capture_theme_screenshot_selector_wins_over_full_page(
    preview_origin, inspect_cache, monkeypatch
):
    monkeypatch.setattr(
        "services.theme_render_inspect_service.get_theme_context",
        lambda site_id: {"active": True},
    )
    loc = FakeLocator(count=1, screenshot_bytes=PNG_1X1)
    page = FakePage(locator=loc, screenshot_bytes=b"not-used")

    @contextmanager
    def fake_open(**kwargs):
        yield page

    monkeypatch.setattr(
        "services.theme_render_inspect_service.open_inspect_page",
        fake_open,
    )
    result = capture_theme_screenshot(
        "wiki", selector="#t", full_page=True, include_image=True
    )
    assert result["ok"] is True
    assert result["hint"] is None
    assert result["mime"] == "image/png"
    assert page.last_selector == "#t"
    assert page.last_screenshot_kwargs is None


@pytest.mark.playwright
def test_set_content_clipped_screenshot_default_omits_blob(inspect_cache):
    html = """<!doctype html>
<html>
<body>
  <p id="t" style="background:red;width:40px;height:20px">Hi</p>
</body>
</html>"""
    try:
        with open_inspect_page(html=html, viewport="desktop") as page:
            payload = screenshot_on_page(page, site_id="wiki", selector="#t")
            with_image = screenshot_on_page(
                page, site_id="wiki", selector="#t", include_image=True
            )
    except ThemeRenderInspectError as exc:
        if exc.error == "BROWSER_UNAVAILABLE":
            pytest.skip(exc.reason)
        raise
    finally:
        shutdown_inspect_browser()
    assert payload["width"] > 0
    assert payload["height"] > 0
    assert "data_url" not in payload
    assert "mime" not in payload
    assert with_image["data_url"].startswith("data:image/")
    assert with_image["mime"] in ("image/png", "image/jpeg")


def _png_hash() -> str:
    return hashlib.sha256(PNG_1X1).digest()[:FINGERPRINT_BYTES].hex()


def test_read_cached_screenshot_png_hit(inspect_cache):
    digest = _png_hash()
    cache_screenshot_png("wiki", digest, PNG_1X1)
    assert read_cached_screenshot_png("wiki", digest) == PNG_1X1


def test_read_cached_screenshot_png_miss(inspect_cache):
    digest = _png_hash()
    assert read_cached_screenshot_png("wiki", digest) is None


def test_read_cached_screenshot_png_expired(inspect_cache, monkeypatch):
    monkeypatch.setattr(
        "services.theme_render_inspect_service.SCREENSHOT_CACHE_TTL_S",
        1,
    )
    digest = _png_hash()
    path = cache_screenshot_png("wiki", digest, PNG_1X1)
    past = time.time() - 10
    import os

    os.utime(path, (past, past))
    assert read_cached_screenshot_png("wiki", digest) is None
    assert not path.exists()


def test_read_cached_screenshot_invalid_hash(inspect_cache):
    with pytest.raises(ThemeRenderInspectError) as caught:
        read_cached_screenshot_png("wiki", "../etc/passwd")
    assert caught.value.error == "SCREENSHOT_CACHE_MISS"
    assert SCREENSHOT_CACHE_MISS_HINT in caught.value.hint


def test_load_screenshot_cache_miss_without_recapture(inspect_cache):
    digest = _png_hash()
    with pytest.raises(ThemeRenderInspectError) as caught:
        load_screenshot_png("wiki", digest=digest)
    assert caught.value.error == "SCREENSHOT_CACHE_MISS"


def test_capture_from_hash_skips_playwright(preview_origin, inspect_cache, monkeypatch):
    digest = _png_hash()
    cache_screenshot_png("wiki", digest, PNG_1X1)
    monkeypatch.setattr(
        "services.theme_render_inspect_service.get_theme_context",
        lambda site_id: {"active": True},
    )

    def boom(**kwargs):
        raise AssertionError("open_inspect_page should not run on cache hit")

    monkeypatch.setattr(
        "services.theme_render_inspect_service.open_inspect_page",
        boom,
    )
    result = capture_theme_screenshot("wiki", include_image=True, digest=digest)
    assert result["hash"] == digest
    assert result["mime"] == "image/png"
    assert result["data_url"].startswith("data:image/png;base64,")
    assert "data_url" in result


def test_parse_describe_response_json():
    parsed = parse_describe_response(
        '{"description": "A red header", "findings": ["tight padding"]}'
    )
    assert parsed["description"] == "A red header"
    assert parsed["findings"] == ["tight padding"]


def test_parse_describe_response_fenced_and_fallback():
    fenced = parse_describe_response(
        '```json\n{"description": "Hero", "findings": []}\n```'
    )
    assert fenced["description"] == "Hero"
    assert fenced["findings"] == []
    raw = parse_describe_response("not json at all")
    assert raw["description"] == "not json at all"
    assert raw["findings"] == []


def test_build_describe_messages_multimodal():
    messages = build_describe_messages(PNG_1X1)
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    parts = messages[0]["content"]
    assert parts[0]["type"] == "text"
    assert DESCRIBE_SCREENSHOT_PROMPT in parts[0]["text"]
    assert parts[1]["type"] == "image_url"
    assert parts[1]["image_url"]["detail"] == "auto"
    assert parts[1]["image_url"]["url"].startswith("data:image/")
