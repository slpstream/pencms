"""MCP theme render-inspect tools (Slices 2–6)."""

from __future__ import annotations

import hashlib
import json
import secrets
from contextlib import contextmanager

import pytest


from services.theme_render_inspect_service import (
    DESCRIBE_TEXT_ONLY_HINT,
    FINGERPRINT_BYTES,
    SCREENSHOT_CACHE_MISS_HINT,
    SCREENSHOT_INCLUDE_HINT,
    THEME_INACTIVE_HINT,
    ThemeRenderInspectError,
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

ARIA_YAML = """
- banner:
  - heading "Hello" [level=1]
- button "Submit"
"""

PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n"
    + b"\x00\x00\x00\rIHDR"
    + (1).to_bytes(4, "big")
    + (1).to_bytes(4, "big")
    + b"\x08\x06\x00\x00\x00fake"
)


class FakeLocator:
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


class FakePage:
    """Duck-typed Playwright Page for unit tests (no Chromium)."""

    def __init__(self, *, eval_result=None, locator=None, screenshot_bytes=None):
        self.eval_result = eval_result
        self._locator = locator
        self.screenshot_bytes = screenshot_bytes

    def evaluate(self, expression, arg=None):
        return self.eval_result

    def locator(self, selector):
        if self._locator is not None:
            return self._locator
        return FakeLocator(
            count=1,
            aria_yaml=ARIA_YAML,
            screenshot_bytes=self.screenshot_bytes or PNG_1X1,
        )

    def screenshot(self, type="png", full_page=False, **kwargs):
        return self.screenshot_bytes if self.screenshot_bytes is not None else PNG_1X1


@pytest.fixture
def isolated_content(temp_data_root, monkeypatch):
    """Point content storage at the temp root and reset site registry."""
    import shutil

    import config
    from services.storage_provider import LocalStorageProvider
    import services.file_service as file_service

    content = temp_data_root / "content"
    content.mkdir(exist_ok=True)
    sites_yaml = temp_data_root / "data" / "sites.yaml"
    if sites_yaml.exists():
        sites_yaml.unlink()
    sites_dir = content / "sites"
    if sites_dir.exists():
        shutil.rmtree(sites_dir)
    for child in list(content.iterdir()):
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()

    provider = LocalStorageProvider(str(content))
    monkeypatch.setattr(config, "CONTENT_DIR_PATH", content)
    monkeypatch.setattr(config, "content_storage", provider)
    monkeypatch.setattr(file_service, "content_storage", provider)
    yield content


@pytest.fixture
def fixture_themes(tmp_path, monkeypatch):
    """Tiny install themes root with one base theme."""
    root = tmp_path / "themes"
    base = root / "basekit"
    (base / "templates").mkdir(parents=True)
    (base / "partials").mkdir(parents=True)
    (base / "assets" / "css").mkdir(parents=True)
    (base / "theme.json").write_text(
        json.dumps(
            {
                "name": "Base Kit",
                "version": "1.0.0",
                "type": "native",
            }
        ),
        encoding="utf-8",
    )
    (base / "templates" / "index.html.twig").write_text(
        "{# base index #}\n", encoding="utf-8"
    )
    (base / "partials" / "nav.twig").write_text("{# nav #}\n", encoding="utf-8")
    (base / "assets" / "css" / "styles.css").write_text(
        "body{}\n", encoding="utf-8"
    )

    import services.social_preview as social_preview

    monkeypatch.setattr(social_preview, "themes_root", lambda: root)
    monkeypatch.setattr(social_preview, "install_active_theme", lambda: "basekit")
    return root


@pytest.fixture
def site_ready(isolated_content, fixture_themes):
    from services.site_service import create_site, ensure_sites_initialized

    ensure_sites_initialized()
    create_site("wiki", "Wiki", theme="basekit")
    create_site("other", "Other", theme="basekit")
    return isolated_content


@pytest.fixture
def agent_token_factory(authed_client):
    def _create(scopes, site_id: str = "wiki"):
        resp = authed_client.post(
            "/api/auth/keys",
            json={
                "name": f"inspect-{secrets.token_hex(4)}",
                "scopes": scopes,
                "site_id": site_id,
            },
        )
        assert resp.status_code == 200, resp.text
        raw_key = resp.json()["key"]
        resp = authed_client.post("/api/auth/token", json={"agent_key": raw_key})
        assert resp.status_code == 200, resp.text
        return resp.json()["access_token"]

    return _create


@pytest.fixture
def inspect_stubs(monkeypatch, tmp_path):
    """Fake Page + preview origin; no Chromium, no PHP."""
    monkeypatch.delenv("PENCMS_PREVIEW_BASE_URL", raising=False)
    monkeypatch.setattr(
        "services.theme_render_inspect_service.get_preview_base_url",
        lambda: ORIGIN,
    )
    monkeypatch.setattr(
        "services.theme_render_inspect_service.get_theme_context",
        lambda site_id: {"active": False},
    )
    cache = tmp_path / "inspect-cache"
    monkeypatch.setattr(
        "services.theme_render_inspect_service.screenshot_cache_root",
        lambda: cache,
    )
    state = {"eval_result": DESCRIBE_OK, "locator_count": 1}

    @contextmanager
    def fake_open(**kwargs):
        yield FakePage(
            eval_result=state["eval_result"],
            locator=FakeLocator(
                count=state["locator_count"],
                aria_yaml=ARIA_YAML,
                screenshot_bytes=PNG_1X1,
            ),
            screenshot_bytes=PNG_1X1,
        )

    monkeypatch.setattr(
        "services.theme_render_inspect_service.open_inspect_page",
        fake_open,
    )
    return state


def test_unauthenticated_inspect_rejected(site_ready, client):
    assert (
        client.post(
            "/api/v1/mcp/theme/inspect/element",
            json={"selector": "h1"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/mcp/theme/inspect/boxes",
            json={"selectors": ["h1"]},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/mcp/theme/inspect/a11y",
            json={},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/mcp/theme/inspect/fingerprint",
            json={},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/mcp/theme/inspect/screenshot",
            json={},
        ).status_code
        == 401
    )


def test_write_scope_without_read_rejected(
    site_ready, authed_client, agent_token_factory, inspect_stubs
):
    token = agent_token_factory(["write"], site_id="wiki")
    headers = {"Authorization": f"Bearer {token}"}
    resp = authed_client.post(
        "/api/v1/mcp/theme/inspect/element",
        json={"selector": "h1"},
        headers=headers,
    )
    assert resp.status_code == 403
    assert "lacks required scope: read" in resp.json()["detail"]


def test_describe_element_read_scope_inactive_hint(
    site_ready, authed_client, agent_token_factory, inspect_stubs
):
    token = agent_token_factory(["read"], site_id="wiki")
    headers = {"Authorization": f"Bearer {token}"}
    resp = authed_client.post(
        "/api/v1/mcp/theme/inspect/element",
        json={"selector": "h1#t", "path": "/blog/", "viewport": "desktop"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["site_id"] == "wiki"
    assert body["theme_active"] is False
    assert body["hint"] == THEME_INACTIVE_HINT
    assert body["url"] == "http://127.0.0.1:8009/blog/?site=wiki"
    assert body["match_count"] == 1
    assert body["computed"]["color"] == "rgb(255, 0, 0)"


def test_get_layout_boxes_read_scope(
    site_ready, authed_client, agent_token_factory, inspect_stubs
):
    inspect_stubs["eval_result"] = BOXES_OK
    token = agent_token_factory(["read"], site_id="wiki")
    headers = {"Authorization": f"Bearer {token}"}
    resp = authed_client.post(
        "/api/v1/mcp/theme/inspect/boxes",
        json={"selectors": ["#hero"], "viewport": "mobile"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["viewport"] == "mobile"
    assert body["boxes"][0]["clipping_ancestor"]["overflow"] == "hidden"
    assert "site=wiki" in body["url"]


def test_inspect_site_binding(
    site_ready, authed_client, agent_token_factory, inspect_stubs
):
    wiki_token = agent_token_factory(["read"], site_id="wiki")
    other_token = agent_token_factory(["read"], site_id="other")
    wiki_resp = authed_client.post(
        "/api/v1/mcp/theme/inspect/element",
        json={"selector": "h1#t"},
        headers={"Authorization": f"Bearer {wiki_token}"},
    )
    other_resp = authed_client.post(
        "/api/v1/mcp/theme/inspect/element",
        json={"selector": "h1#t"},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert wiki_resp.status_code == 200, wiki_resp.text
    assert other_resp.status_code == 200, other_resp.text
    assert wiki_resp.json()["site_id"] == "wiki"
    assert other_resp.json()["site_id"] == "other"
    assert "site=wiki" in wiki_resp.json()["url"]
    assert "site=other" in other_resp.json()["url"]
    assert "site=other" not in wiki_resp.json()["url"]


def test_inspect_path_rejected(
    site_ready, authed_client, agent_token_factory, inspect_stubs
):
    token = agent_token_factory(["read"], site_id="wiki")
    resp = authed_client.post(
        "/api/v1/mcp/theme/inspect/element",
        json={"selector": "h1", "path": "/admin/"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400, resp.text
    detail = resp.json()["detail"]
    assert detail["error"] == "PATH_REJECTED"
    assert "hint" in detail


def test_inspect_selector_not_found(
    site_ready, authed_client, agent_token_factory, inspect_stubs
):
    inspect_stubs["eval_result"] = {
        "error": "SELECTOR_NOT_FOUND",
        "match_count": 0,
        "selector": ".missing",
    }
    token = agent_token_factory(["read"], site_id="wiki")
    resp = authed_client.post(
        "/api/v1/mcp/theme/inspect/element",
        json={"selector": ".missing"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400, resp.text
    detail = resp.json()["detail"]
    assert detail["error"] == "SELECTOR_NOT_FOUND"
    assert ".missing" in detail["reason"]


def test_inspect_boxes_selector_not_found(
    site_ready, authed_client, agent_token_factory, inspect_stubs
):
    inspect_stubs["eval_result"] = {
        "boxes": [],
        "missing": [".gone"],
        "candidates": [".masthead", ".nav-menu"],
    }
    token = agent_token_factory(["read"], site_id="wiki")
    resp = authed_client.post(
        "/api/v1/mcp/theme/inspect/boxes",
        json={"selectors": [".gone"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400, resp.text
    detail = resp.json()["detail"]
    assert detail["error"] == "SELECTOR_NOT_FOUND"
    assert ".gone" in detail["reason"]
    assert ".masthead" in detail["hint"]


def test_inspect_boxes_partial_miss_returns_hits(
    site_ready, authed_client, agent_token_factory, inspect_stubs
):
    inspect_stubs["eval_result"] = {
        "boxes": [
            {
                "selector": "header",
                "x": 0,
                "y": 0,
                "w": 1280,
                "h": 81,
                "visible": True,
                "clipping_ancestor": None,
            }
        ],
        "missing": [".brand"],
        "candidates": [".masthead", ".site-title"],
    }
    token = agent_token_factory(["read"], site_id="wiki")
    resp = authed_client.post(
        "/api/v1/mcp/theme/inspect/boxes",
        json={"selectors": ["header", ".brand"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["boxes"][0]["selector"] == "header"
    assert body["missing"] == [".brand"]
    assert ".masthead" in body["candidates"]


def test_inspect_preview_unreachable_is_400(
    site_ready, authed_client, agent_token_factory, monkeypatch
):
    monkeypatch.delenv("PENCMS_PREVIEW_BASE_URL", raising=False)
    monkeypatch.setattr(
        "services.theme_render_inspect_service.get_preview_base_url",
        lambda: None,
    )
    token = agent_token_factory(["read"], site_id="wiki")
    resp = authed_client.post(
        "/api/v1/mcp/theme/inspect/element",
        json={"selector": "h1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["detail"]["error"] == "PREVIEW_UNREACHABLE"


def test_inspect_browser_unavailable_is_400(
    site_ready, authed_client, agent_token_factory, monkeypatch
):
    monkeypatch.setattr(
        "services.theme_render_inspect_service.get_preview_base_url",
        lambda: ORIGIN,
    )

    @contextmanager
    def boom(**kwargs):
        raise ThemeRenderInspectError(
            "BROWSER_UNAVAILABLE",
            "Chromium is not available: Executable doesn't exist",
            "pip install playwright && playwright install chromium",
        )
        yield  # pragma: no cover

    monkeypatch.setattr(
        "services.theme_render_inspect_service.open_inspect_page",
        boom,
    )
    token = agent_token_factory(["read"], site_id="wiki")
    resp = authed_client.post(
        "/api/v1/mcp/theme/inspect/boxes",
        json={"selectors": ["h1"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["detail"]["error"] == "BROWSER_UNAVAILABLE"


def test_get_accessible_snapshot_read_scope_inactive_hint(
    site_ready, authed_client, agent_token_factory, inspect_stubs
):
    token = agent_token_factory(["read"], site_id="wiki")
    headers = {"Authorization": f"Bearer {token}"}
    resp = authed_client.post(
        "/api/v1/mcp/theme/inspect/a11y",
        json={"root": ".brand", "path": "/blog/", "viewport": "desktop"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["site_id"] == "wiki"
    assert body["theme_active"] is False
    assert body["hint"] == THEME_INACTIVE_HINT
    assert body["root"] == ".brand"
    snap = body["snapshot"]
    assert set(snap.keys()) == {"role", "name", "visible", "children"}
    assert body["node_count"] >= 1
    assert "data_url" not in body


def test_get_render_fingerprint_read_scope(
    site_ready, authed_client, agent_token_factory, inspect_stubs
):
    token = agent_token_factory(["read"], site_id="wiki")
    headers = {"Authorization": f"Bearer {token}"}
    resp = authed_client.post(
        "/api/v1/mcp/theme/inspect/fingerprint",
        json={"viewport": "mobile"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["viewport"] == "mobile"
    assert len(body["hash"]) == 32
    assert body["width"] == 1
    assert body["height"] == 1
    assert "data" not in body
    assert "data_url" not in body
    assert "png" not in body
    assert "pixels" not in body
    assert "site=wiki" in body["url"]


def test_inspect_a11y_site_binding(
    site_ready, authed_client, agent_token_factory, inspect_stubs
):
    wiki_token = agent_token_factory(["read"], site_id="wiki")
    other_token = agent_token_factory(["read"], site_id="other")
    wiki_resp = authed_client.post(
        "/api/v1/mcp/theme/inspect/a11y",
        json={},
        headers={"Authorization": f"Bearer {wiki_token}"},
    )
    other_resp = authed_client.post(
        "/api/v1/mcp/theme/inspect/fingerprint",
        json={},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert wiki_resp.status_code == 200, wiki_resp.text
    assert other_resp.status_code == 200, other_resp.text
    assert wiki_resp.json()["site_id"] == "wiki"
    assert other_resp.json()["site_id"] == "other"
    assert "site=wiki" in wiki_resp.json()["url"]
    assert "site=other" in other_resp.json()["url"]


def test_inspect_a11y_path_rejected(
    site_ready, authed_client, agent_token_factory, inspect_stubs
):
    token = agent_token_factory(["read"], site_id="wiki")
    resp = authed_client.post(
        "/api/v1/mcp/theme/inspect/a11y",
        json={"path": "/admin/"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400, resp.text
    detail = resp.json()["detail"]
    assert detail["error"] == "PATH_REJECTED"
    assert "hint" in detail


def test_inspect_fingerprint_selector_not_found(
    site_ready, authed_client, agent_token_factory, inspect_stubs
):
    inspect_stubs["locator_count"] = 0
    token = agent_token_factory(["read"], site_id="wiki")
    resp = authed_client.post(
        "/api/v1/mcp/theme/inspect/fingerprint",
        json={"selector": ".gone"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["detail"]["error"] == "SELECTOR_NOT_FOUND"


def test_inspect_a11y_preview_unreachable_is_400(
    site_ready, authed_client, agent_token_factory, monkeypatch
):
    monkeypatch.delenv("PENCMS_PREVIEW_BASE_URL", raising=False)
    monkeypatch.setattr(
        "services.theme_render_inspect_service.get_preview_base_url",
        lambda: None,
    )
    token = agent_token_factory(["read"], site_id="wiki")
    resp = authed_client.post(
        "/api/v1/mcp/theme/inspect/fingerprint",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["detail"]["error"] == "PREVIEW_UNREACHABLE"


def test_inspect_a11y_browser_unavailable_is_400(
    site_ready, authed_client, agent_token_factory, monkeypatch
):
    monkeypatch.setattr(
        "services.theme_render_inspect_service.get_preview_base_url",
        lambda: ORIGIN,
    )

    @contextmanager
    def boom(**kwargs):
        raise ThemeRenderInspectError(
            "BROWSER_UNAVAILABLE",
            "Chromium is not available: Executable doesn't exist",
            "pip install playwright && playwright install chromium",
        )
        yield  # pragma: no cover

    monkeypatch.setattr(
        "services.theme_render_inspect_service.open_inspect_page",
        boom,
    )
    token = agent_token_factory(["read"], site_id="wiki")
    resp = authed_client.post(
        "/api/v1/mcp/theme/inspect/a11y",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["detail"]["error"] == "BROWSER_UNAVAILABLE"


def test_capture_theme_screenshot_read_scope_default_omits_blob(
    site_ready, authed_client, agent_token_factory, inspect_stubs
):
    token = agent_token_factory(["read"], site_id="wiki")
    headers = {"Authorization": f"Bearer {token}"}
    resp = authed_client.post(
        "/api/v1/mcp/theme/inspect/screenshot",
        json={"viewport": "mobile"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["site_id"] == "wiki"
    assert body["theme_active"] is False
    assert THEME_INACTIVE_HINT in body["hint"]
    assert SCREENSHOT_INCLUDE_HINT in body["hint"]
    assert len(body["hash"]) == 32
    assert body["width"] == 1
    assert body["height"] == 1
    assert "data_url" not in body
    assert "mime" not in body
    assert "site=wiki" in body["url"]


def test_capture_theme_screenshot_include_image_query(
    site_ready, authed_client, agent_token_factory, inspect_stubs
):
    token = agent_token_factory(["read"], site_id="wiki")
    headers = {"Authorization": f"Bearer {token}"}
    resp = authed_client.post(
        "/api/v1/mcp/theme/inspect/screenshot?include_image=true",
        json={"selector": "#t"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["mime"] == "image/png"
    assert body["data_url"].startswith("data:image/png;base64,")
    assert THEME_INACTIVE_HINT in body["hint"]


def test_capture_theme_screenshot_include_image_body(
    site_ready, authed_client, agent_token_factory, inspect_stubs
):
    token = agent_token_factory(["read"], site_id="wiki")
    headers = {"Authorization": f"Bearer {token}"}
    resp = authed_client.post(
        "/api/v1/mcp/theme/inspect/screenshot",
        json={"include_image": True, "viewport": "desktop"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["mime"] == "image/png"
    assert body["data_url"].startswith("data:image/png;base64,")


def test_inspect_screenshot_path_rejected(
    site_ready, authed_client, agent_token_factory, inspect_stubs
):
    token = agent_token_factory(["read"], site_id="wiki")
    resp = authed_client.post(
        "/api/v1/mcp/theme/inspect/screenshot",
        json={"path": "/admin/"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400, resp.text
    detail = resp.json()["detail"]
    assert detail["error"] == "PATH_REJECTED"
    assert "hint" in detail


def test_inspect_screenshot_selector_not_found(
    site_ready, authed_client, agent_token_factory, inspect_stubs
):
    inspect_stubs["locator_count"] = 0
    token = agent_token_factory(["read"], site_id="wiki")
    resp = authed_client.post(
        "/api/v1/mcp/theme/inspect/screenshot",
        json={"selector": ".gone"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["detail"]["error"] == "SELECTOR_NOT_FOUND"


def test_screenshot_registered_in_openapi(client):
    spec = client.get("/api/openapi.json").json()
    path = spec["paths"]["/api/v1/mcp/theme/inspect/screenshot"]["post"]
    assert path["operationId"] == "capture_theme_screenshot"
    assert "describe_theme_screenshot" not in json.dumps(spec)


def _screenshot_hash() -> str:
    return hashlib.sha256(PNG_1X1).digest()[:FINGERPRINT_BYTES].hex()


def test_capture_theme_screenshot_include_image_from_hash_uses_cache(
    site_ready, authed_client, agent_token_factory, inspect_stubs, monkeypatch
):
    token = agent_token_factory(["read"], site_id="wiki")
    headers = {"Authorization": f"Bearer {token}"}
    first = authed_client.post(
        "/api/v1/mcp/theme/inspect/screenshot",
        json={"viewport": "desktop"},
        headers=headers,
    )
    assert first.status_code == 200, first.text
    digest = first.json()["hash"]
    assert digest == _screenshot_hash()

    def boom(**kwargs):
        raise AssertionError("open_inspect_page should not run on cache hit")

    monkeypatch.setattr(
        "services.theme_render_inspect_service.open_inspect_page",
        boom,
    )
    resp = authed_client.post(
        "/api/v1/mcp/theme/inspect/screenshot",
        json={"hash": digest, "include_image": True},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["hash"] == digest
    assert body["mime"] == "image/png"
    assert body["data_url"].startswith("data:image/png;base64,")


def test_screenshot_describe_from_hash_returns_text(
    site_ready, authed_client, agent_token_factory, inspect_stubs
):
    import httpx
    import respx

    token = agent_token_factory(["read"], site_id="wiki")
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Pen-AI-Key": "testkey",
        "X-Pen-AI-Model": "gpt-4o",
    }
    first = authed_client.post(
        "/api/v1/mcp/theme/inspect/screenshot",
        json={"viewport": "desktop"},
        headers=headers,
    )
    assert first.status_code == 200, first.text
    digest = first.json()["hash"]
    eval_response = {
        "description": "A 1x1 preview clip.",
        "findings": ["tiny canvas"],
    }
    with respx.mock(base_url="https://api.openai.com") as mock:
        mock.post("/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": json.dumps(eval_response),
                            }
                        }
                    ]
                },
            )
        )
        resp = authed_client.post(
            "/api/v1/mcp/theme/inspect/screenshot",
            json={"hash": digest, "describe": True},
            headers=headers,
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["hash"] == digest
    assert body["description"] == "A 1x1 preview clip."
    assert body["findings"] == ["tiny canvas"]
    assert "data_url" not in body
    assert "mime" not in body
    assert THEME_INACTIVE_HINT in (body.get("hint") or "")


def test_screenshot_describe_query_flag(
    site_ready, authed_client, agent_token_factory, inspect_stubs
):
    import httpx
    import respx

    token = agent_token_factory(["read"], site_id="wiki")
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Pen-AI-Key": "testkey",
        "X-Pen-AI-Model": "gpt-4o",
    }
    first = authed_client.post(
        "/api/v1/mcp/theme/inspect/screenshot",
        json={},
        headers=headers,
    )
    digest = first.json()["hash"]
    with respx.mock(base_url="https://api.openai.com") as mock:
        mock.post("/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": '{"description": "ok", "findings": []}',
                            }
                        }
                    ]
                },
            )
        )
        resp = authed_client.post(
            f"/api/v1/mcp/theme/inspect/screenshot?describe=true",
            json={"hash": digest},
            headers=headers,
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["description"] == "ok"
    assert "data_url" not in resp.json()


def test_screenshot_describe_cache_miss_without_recapture(
    site_ready, authed_client, agent_token_factory, inspect_stubs
):
    token = agent_token_factory(["read"], site_id="wiki")
    digest = _screenshot_hash()
    resp = authed_client.post(
        "/api/v1/mcp/theme/inspect/screenshot",
        json={"hash": digest, "describe": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400, resp.text
    detail = resp.json()["detail"]
    assert detail["error"] == "SCREENSHOT_CACHE_MISS"
    assert SCREENSHOT_CACHE_MISS_HINT in detail["hint"]


def test_screenshot_describe_image_input_not_supported(
    site_ready, authed_client, agent_token_factory, inspect_stubs
):
    import httpx
    import respx

    token = agent_token_factory(["read"], site_id="wiki")
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Pen-AI-Key": "testkey",
        "X-Pen-AI-Model": "gpt-4o",
    }
    first = authed_client.post(
        "/api/v1/mcp/theme/inspect/screenshot",
        json={},
        headers=headers,
    )
    digest = first.json()["hash"]
    with respx.mock(base_url="https://api.openai.com") as mock:
        mock.post("/v1/chat/completions").mock(
            return_value=httpx.Response(
                400,
                json={
                    "error": {
                        "message": "image_input_not_supported",
                    }
                },
            )
        )
        resp = authed_client.post(
            "/api/v1/mcp/theme/inspect/screenshot",
            json={"hash": digest, "describe": True},
            headers=headers,
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["description"] == ""
    assert body["findings"] == []
    assert DESCRIBE_TEXT_ONLY_HINT in (body.get("hint") or "")
    assert "data_url" not in body
