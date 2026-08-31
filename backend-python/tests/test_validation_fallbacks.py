import pytest
from models.page import Page, PageFrontmatter

def test_fallback_no_name_uses_hero_title():
    page = Page(
        frontmatter={"category": "summer", "hero_title": "Summer Guide"},
        content="some content"
    )
    assert page.frontmatter.name == "Summer Guide"
    assert page.frontmatter.hero_title == "Summer Guide"
    assert page.slug == "summer-guide"

def test_fallback_no_name_uses_slug():
    page = Page(
        frontmatter={"category": "summer"},
        slug="summer-guide",
        content="some content"
    )
    assert page.frontmatter.name == "Summer Guide"
    assert page.frontmatter.hero_title == "Summer Guide"
    assert page.slug == "summer-guide"

def test_fallback_no_hero_title_uses_name():
    page = Page(
        frontmatter={"category": "summer", "name": "Summer Guide"},
        content="some content"
    )
    assert page.frontmatter.name == "Summer Guide"
    assert page.frontmatter.hero_title == "Summer Guide"
    assert page.slug == "summer-guide"

def test_fallback_no_hero_title_uses_slug():
    page = Page(
        frontmatter={"category": "summer"},
        slug="summer-guide",
        content="some content"
    )
    assert page.frontmatter.name == "Summer Guide"
    assert page.frontmatter.hero_title == "Summer Guide"
    assert page.slug == "summer-guide"

def test_fallback_no_slug_uses_name():
    page = Page(
        frontmatter={"category": "summer", "name": "Summer Guide"},
        content="some content"
    )
    assert page.slug == "summer-guide"

def test_fallback_no_slug_uses_hero_title():
    page = Page(
        frontmatter={"category": "summer", "hero_title": "Summer Guide"},
        content="some content"
    )
    assert page.slug == "summer-guide"

def test_conflicting_values_are_preserved():
    page = Page(
        frontmatter={"category": "summer", "name": "Short Name", "hero_title": "Long Hero Title"},
        slug="short-name",
        content="some content"
    )
    assert page.frontmatter.name == "Short Name"
    assert page.frontmatter.hero_title == "Long Hero Title"
    assert page.slug == "short-name"

def test_api_fallback_mcp_write_no_name(authed_client):
    # Setup key with write scope
    resp = authed_client.post(
        "/api/auth/keys",
        json={"name": "fallback-write", "scopes": ["read", "write"]},
    )
    assert resp.status_code == 200, resp.text
    raw_key = resp.json()["key"]

    resp = authed_client.post("/api/auth/token", json={"agent_key": raw_key})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    
    headers = {"Authorization": f"Bearer {token}"}
    
    resp = authed_client.put(
        "/api/v1/mcp/pages/mcp-test-slug",
        json={
            "frontmatter": {"category": "summer", "hero_title": "MCP Summer Guide"},
            "body": "MCP body"
        },
        headers=headers
    )
    assert resp.status_code == 200, resp.text
    
    # Read it back and verify fields
    resp = authed_client.get("/api/v1/mcp/pages/mcp-test-slug/metadata", headers=headers)
    assert resp.status_code == 200
    fm = resp.json()["frontmatter"]
    assert fm["name"] == "MCP Summer Guide"
    assert fm["hero_title"] == "MCP Summer Guide"
    assert fm["slug"] == "mcp-test-slug"


def test_api_rejects_invalid_slugs(authed_client):
    # Test v1.py PUT endpoint with 'undefined'
    resp = authed_client.put(
        "/api/v1/content/collections/summer/entries/undefined",
        json={
            "frontmatter": {"name": "Test Entry"},
            "body": "Body"
        }
    )
    assert resp.status_code == 400
    assert "Invalid slug value" in resp.json()["detail"]

    # Test pages.py PUT endpoint with 'null'
    resp = authed_client.put(
        "/api/pages/null",
        json={
            "frontmatter": {"name": "Test Entry", "category": "summer"},
            "content": "Body"
        }
    )
    assert resp.status_code == 400
    assert "Invalid page ID" in resp.json()["detail"]

    # Test mcp_tools.py PUT endpoint with 'undefined'
    resp = authed_client.post(
        "/api/auth/keys",
        json={"name": "fallback-undef", "scopes": ["read", "write"]},
    )
    assert resp.status_code == 200
    raw_key = resp.json()["key"]
    resp = authed_client.post("/api/auth/token", json={"agent_key": raw_key})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = authed_client.put(
        "/api/v1/mcp/pages/undefined",
        json={
            "frontmatter": {"category": "summer", "name": "Test"},
            "body": "Body"
        },
        headers=headers
    )
    assert resp.status_code == 400
    assert "Invalid slug value" in resp.json()["detail"]


def test_format_validation_error():
    from models.page import PageFrontmatter, format_validation_error
    from pydantic import ValidationError

    try:
        # Empty install taxonomy only requires name + status for published posts.
        PageFrontmatter(category="summer", name="", status="published")
    except ValidationError as e:
        msg = format_validation_error(e)
        assert msg == "Published posts require Name"


def test_api_v1_save_validation_error_is_formatted(authed_client):
    # Site taxonomy can extend required_fields beyond the empty install default.
    authed_client.put(
        "/api/taxonomy/",
        json={
            "primary_vocabulary": "",
            "required_fields": ["name", "status", "deck", "trumpet"],
            "vocabularies": {},
        },
        headers={"X-Pen-Site-Id": "default"},
    )
    resp = authed_client.put(
        "/api/v1/content/collections/summer/entries/validation-test-post",
        json={
            "frontmatter": {
                "name": "Test Post",
                "status": "published",
            },
            "body": "Body text"
        }
    )
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert detail == "Published posts require Deck, Trumpet"
