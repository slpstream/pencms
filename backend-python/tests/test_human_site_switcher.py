"""Human content site-switcher: X-Pen-Site-Id / pen_site_id cookie. Pro overlay."""

from __future__ import annotations

import asyncio

import pytest

pytestmark = pytest.mark.pro
pytest.importorskip("pencms_pro", reason="sites CRUD is Pro overlay")


@pytest.fixture
def two_sites(authed_client, temp_data_root):
    from services.site_service import create_site, ensure_sites_initialized

    ensure_sites_initialized()
    try:
        create_site("other", "Other Site")
    except ValueError:
        pass
    return ("default", "other")


def _mint_token(authed_client, name: str, site_id: str) -> str:
    resp = authed_client.post(
        "/api/auth/keys",
        json={"name": name, "scopes": ["read", "write"], "site_id": site_id},
    )
    assert resp.status_code == 200, resp.text
    raw = resp.json()["key"]
    resp = authed_client.post("/api/auth/token", json={"agent_key": raw})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _entry_body(name: str, body: str = "hello") -> dict:
    return {
        "frontmatter": {
            "name": name,
            "title": name,
            "category": "summer",
            "status": "stub",
            "published": False,
        },
        "body": body,
    }


def test_human_header_writes_under_other_site(authed_client, two_sites, temp_data_root):
    resp = authed_client.put(
        "/api/v1/content/collections/summer/entries/wiki-page",
        json=_entry_body("Wiki Page", "wiki body"),
        headers={"X-Pen-Site-Id": "other"},
    )
    assert resp.status_code == 200, resp.text

    from services.site_service import get_site_content_prefix
    from config import CONTENT_DIR_PATH, content_storage
    from services.cache_service import sync_cache_with_storage

    prefix = get_site_content_prefix("other")
    expected = CONTENT_DIR_PATH / prefix / "wiki-page" / "index.md"
    assert expected.is_file(), f"expected {expected}"

    asyncio.run(sync_cache_with_storage(content_storage))

    resp = authed_client.get(
        "/api/v1/content/collections/summer/entries?limit=200",
        headers={"X-Pen-Site-Id": "other"},
    )
    assert resp.status_code == 200
    slugs = {i["slug"] for i in resp.json()["items"]}
    assert "wiki-page" in slugs


def test_human_cookie_alone_selects_site(authed_client, two_sites):
    from config import content_storage
    from services.cache_service import sync_cache_with_storage

    resp = authed_client.put(
        "/api/v1/content/collections/summer/entries/cookie-page",
        json=_entry_body("Cookie Page"),
        cookies={"pen_site_id": "other"},
    )
    assert resp.status_code == 200, resp.text

    asyncio.run(sync_cache_with_storage(content_storage))

    resp = authed_client.get(
        "/api/v1/content/collections/summer/entries?limit=200",
        cookies={"pen_site_id": "other"},
    )
    assert resp.status_code == 200
    slugs = {i["slug"] for i in resp.json()["items"]}
    assert "cookie-page" in slugs

    # Without cookie/header → default should not list it
    resp = authed_client.get(
        "/api/v1/content/collections/summer/entries?limit=200",
    )
    assert resp.status_code == 200
    slugs = {i["slug"] for i in resp.json()["items"]}
    assert "cookie-page" not in slugs


def test_unknown_site_id_returns_400(authed_client, two_sites):
    resp = authed_client.get(
        "/api/v1/content/collections",
        headers={"X-Pen-Site-Id": "does-not-exist"},
    )
    assert resp.status_code == 400
    assert "Unknown site_id" in resp.json()["detail"]


def test_invalid_site_id_returns_400(authed_client, two_sites):
    resp = authed_client.get(
        "/api/v1/content/collections",
        headers={"X-Pen-Site-Id": "BAD SITE"},
    )
    assert resp.status_code == 400


def test_missing_preference_defaults_to_default(authed_client, two_sites):
    from config import content_storage
    from services.cache_service import sync_cache_with_storage

    resp = authed_client.put(
        "/api/v1/content/collections/summer/entries/default-page",
        json=_entry_body("Default Page"),
    )
    assert resp.status_code == 200, resp.text

    asyncio.run(sync_cache_with_storage(content_storage))

    resp = authed_client.get(
        "/api/v1/content/collections/summer/entries?limit=200",
    )
    assert resp.status_code == 200
    slugs = {i["slug"] for i in resp.json()["items"]}
    assert "default-page" in slugs


def test_cross_site_isolation_human_v1(authed_client, two_sites):
    from config import content_storage
    from services.cache_service import sync_cache_with_storage

    resp = authed_client.put(
        "/api/v1/content/collections/summer/entries/only-default",
        json=_entry_body("Only Default"),
        headers={"X-Pen-Site-Id": "default"},
    )
    assert resp.status_code == 200, resp.text

    resp = authed_client.put(
        "/api/v1/content/collections/summer/entries/only-other",
        json=_entry_body("Only Other"),
        headers={"X-Pen-Site-Id": "other"},
    )
    assert resp.status_code == 200, resp.text

    asyncio.run(sync_cache_with_storage(content_storage))

    resp = authed_client.get(
        "/api/v1/content/collections/summer/entries?limit=200",
        headers={"X-Pen-Site-Id": "default"},
    )
    assert resp.status_code == 200
    slugs = {i["slug"] for i in resp.json()["items"]}
    assert "only-default" in slugs
    assert "only-other" not in slugs

    resp = authed_client.get(
        "/api/v1/content/collections/summer/entries?limit=200",
        headers={"X-Pen-Site-Id": "other"},
    )
    assert resp.status_code == 200
    slugs = {i["slug"] for i in resp.json()["items"]}
    assert "only-other" in slugs
    assert "only-default" not in slugs


def test_agent_jwt_ignores_site_header_override(authed_client, two_sites):
    """Agent JWT site_id wins; X-Pen-Site-Id must not retarget the agent."""
    from config import content_storage
    from services.cache_service import sync_cache_with_storage

    default_token = _mint_token(authed_client, "no-override-agent", "default")
    other_token = _mint_token(authed_client, "other-writer", "other")

    # Seed a page on other via other agent
    resp = authed_client.put(
        "/api/v1/mcp/pages/secret-other",
        json={
            "frontmatter": {"name": "Secret Other", "category": "summer", "status": "stub"},
            "body": "secret",
        },
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 200, resp.text

    # Default agent cannot read it even with X-Pen-Site-Id: other
    resp = authed_client.get(
        "/api/v1/mcp/pages/secret-other/content",
        headers={
            "Authorization": f"Bearer {default_token}",
            "X-Pen-Site-Id": "other",
        },
    )
    assert resp.status_code == 404

    # Default agent write with override header still lands on default
    resp = authed_client.put(
        "/api/v1/mcp/pages/forced-default",
        json={
            "frontmatter": {"name": "Forced Default", "category": "summer", "status": "stub"},
            "body": "on default",
        },
        headers={
            "Authorization": f"Bearer {default_token}",
            "X-Pen-Site-Id": "other",
        },
    )
    assert resp.status_code == 200, resp.text

    # Confirm via read (returns site_id) that it landed on default
    resp = authed_client.get(
        "/api/v1/mcp/pages/forced-default/content",
        headers={"Authorization": f"Bearer {default_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["site_id"] == "default"
    assert resp.json()["body"] == "on default"

    asyncio.run(sync_cache_with_storage(content_storage))

    # Other agent can list other but not forced-default
    resp = authed_client.get(
        "/api/v1/mcp/collections/summer/entries?limit=200",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 200
    slugs = {i["slug"] for i in resp.json()["items"]}
    assert "secret-other" in slugs
    assert "forced-default" not in slugs


def test_human_mcp_honors_site_header(authed_client, two_sites):
    """Human cookie session MCP tools follow X-Pen-Site-Id (not hardcoded default)."""
    from config import content_storage
    from services.cache_service import sync_cache_with_storage

    # Write via MCP human session with other site header
    resp = authed_client.put(
        "/api/v1/mcp/pages/human-other-page",
        json={
            "frontmatter": {"name": "Human Other", "category": "summer", "status": "stub"},
            "body": "from human mcp",
        },
        headers={"X-Pen-Site-Id": "other"},
    )
    assert resp.status_code == 200, resp.text

    asyncio.run(sync_cache_with_storage(content_storage))

    resp = authed_client.get(
        "/api/v1/mcp/pages/human-other-page/content",
        headers={"X-Pen-Site-Id": "other"},
    )
    assert resp.status_code == 200
    assert resp.json()["body"] == "from human mcp"
    assert resp.json()["site_id"] == "other"

    # Same page invisible under default
    resp = authed_client.get(
        "/api/v1/mcp/pages/human-other-page/content",
        headers={"X-Pen-Site-Id": "default"},
    )
    assert resp.status_code == 404
