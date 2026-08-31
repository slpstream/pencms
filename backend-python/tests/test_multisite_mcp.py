"""Cross-site MCP enforcement (Option C slice 3). Pro overlay."""

from __future__ import annotations

import jwt
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
        pass  # already exists
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


def test_agent_token_carries_site_id(authed_client, two_sites):
    token = _mint_token(authed_client, "default-bot", "default")
    claims = jwt.decode(token, options={"verify_signature": False})
    assert claims["site_id"] == "default"
    assert claims["type"] == "agent"


def test_unknown_site_on_mint_rejected(authed_client, two_sites):
    resp = authed_client.post(
        "/api/auth/keys",
        json={"name": "nope", "scopes": ["read"], "site_id": "does-not-exist"},
    )
    assert resp.status_code == 400
    assert "Unknown site_id" in resp.json()["detail"]


def test_cross_site_read_write_denied(authed_client, two_sites):
    default_token = _mint_token(authed_client, "site-default-agent", "default")
    other_token = _mint_token(authed_client, "site-other-agent", "other")

    # Write a page on default
    resp = authed_client.put(
        "/api/v1/mcp/pages/default-only-post",
        json={
            "frontmatter": {"name": "Default Only", "category": "summer", "status": "stub"},
            "body": "default body",
        },
        headers={"Authorization": f"Bearer {default_token}"},
    )
    assert resp.status_code == 200, resp.text

    # Other-site agent cannot read it
    resp = authed_client.get(
        "/api/v1/mcp/pages/default-only-post/content",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 404

    # Write on other site
    resp = authed_client.put(
        "/api/v1/mcp/pages/other-only-post",
        json={
            "frontmatter": {"name": "Other Only", "category": "summer", "status": "stub"},
            "body": "other body",
        },
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 200, resp.text

    # Default agent cannot read other site's page
    resp = authed_client.get(
        "/api/v1/mcp/pages/other-only-post/content",
        headers={"Authorization": f"Bearer {default_token}"},
    )
    assert resp.status_code == 404

    # Default agent can still read its own
    resp = authed_client.get(
        "/api/v1/mcp/pages/default-only-post/content",
        headers={"Authorization": f"Bearer {default_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["body"] == "default body"
    assert resp.json()["site_id"] == "default"


def test_list_entries_scoped_to_site(authed_client, two_sites):
    import asyncio
    from config import content_storage
    from services.cache_service import sync_cache_with_storage

    default_token = _mint_token(authed_client, "list-default", "default")
    other_token = _mint_token(authed_client, "list-other", "other")

    for token, slug in (
        (default_token, "listed-default"),
        (other_token, "listed-other"),
    ):
        resp = authed_client.put(
            f"/api/v1/mcp/pages/{slug}",
            json={
                "frontmatter": {"name": slug, "category": "summer", "status": "stub"},
                "body": "x",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200, resp.text

    asyncio.run(sync_cache_with_storage(content_storage))

    resp = authed_client.get(
        "/api/v1/mcp/collections/summer/entries?limit=200",
        headers={"Authorization": f"Bearer {default_token}"},
    )
    assert resp.status_code == 200
    slugs = {i["slug"] for i in resp.json()["items"]}
    assert "listed-default" in slugs
    assert "listed-other" not in slugs
