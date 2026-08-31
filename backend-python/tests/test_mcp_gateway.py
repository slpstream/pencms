import base64
import json
import os

import pytest
from models.page import Page, PageFrontmatter
from services.cache_service import search_entries, sync_cache_with_storage
from services.file_service import write_page


@pytest.fixture
def agent_token_factory(authed_client):
    def _create(scopes):
        import secrets

        resp = authed_client.post(
            "/api/auth/keys",
            json={"name": f"gw-{secrets.token_hex(4)}", "scopes": scopes},
        )
        assert resp.status_code == 200, resp.text
        raw_key = resp.json()["key"]

        resp = authed_client.post("/api/auth/token", json={"agent_key": raw_key})
        assert resp.status_code == 200, resp.text
        return resp.json()["access_token"]

    return _create


def test_read_scoped_key_allowed_on_read_tools(authed_client, agent_token_factory):
    token = agent_token_factory(["read"])
    headers = {"Authorization": f"Bearer {token}"}

    # Check site-config
    resp = authed_client.get("/api/v1/mcp/site-config", headers=headers)
    assert resp.status_code == 200
    assert "collections" in resp.json()

    # Check list collections
    resp = authed_client.get("/api/v1/mcp/collections", headers=headers)
    assert resp.status_code == 200


def test_read_scoped_key_rejected_on_write_tools(authed_client, agent_token_factory):
    token = agent_token_factory(["read"])
    headers = {"Authorization": f"Bearer {token}"}

    # Try writing a page
    resp = authed_client.put(
        "/api/v1/mcp/pages/test-slug",
        json={
            "frontmatter": {"title": "Test Title", "category": "summer"},
            "body": "Test body content",
        },
        headers=headers,
    )
    assert resp.status_code == 403
    assert "lacks required scope: write:posts" in resp.json()["detail"]

    # Try uploading media
    resp = authed_client.post(
        "/api/v1/mcp/media",
        json={
            "filename": "test.png",
            "content_base64": base64.b64encode(b"dummy").decode("utf-8"),
        },
        headers=headers,
    )
    assert resp.status_code == 403
    assert "lacks required scope: write:media" in resp.json()["detail"]


def test_write_scoped_key_allowed_on_all_tools(authed_client, agent_token_factory):
    token = agent_token_factory(["read", "write"])
    headers = {"Authorization": f"Bearer {token}"}

    # Write page
    resp = authed_client.put(
        "/api/v1/mcp/pages/test-write-slug",
        json={
            "frontmatter": {"title": "Written Title", "category": "summer"},
            "body": "Written content",
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    # Read page content
    resp = authed_client.get(
        "/api/v1/mcp/pages/test-write-slug/content", headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["body"] == "Written content"


def test_write_content_file_preserves_existing_frontmatter(authed_client):
    """A partial `write_content_file` payload (only a subset of frontmatter
    fields) must NOT destroy optional fields already on disk. The MCP write
    tool is a *partial* writer — the AI frequently sends only `{name, category,
    status}` and omits `hero_title`, `deck`, `trumpet`, `hero_image`, etc.

    Regression guard for the frontmatter-preservation merge in
    `mcp_tools.write_content_file`. Without the merge, this test fails because
    the second write wipes `hero_title` and `deck`.
    """
    # 1. Create the page with rich frontmatter (simulating a human-curated
    #    post or a previous AI write that included presentation fields).
    initial_fm = {
        "name": "Sanremo Travel Post",
        "category": "summer",
        "status": "draft",
        "hero_title": "Sanremo: The Empress and the Palms",
        "deck": "A walking tour of the Passeggiata Imperatrice.",
        "trumpet": "Travel",
        "hero_image": "images/content/sanremo/hero.jpg",
        "author": "Pietro",
    }
    resp = authed_client.put(
        "/api/v1/mcp/pages/preserve-test",
        json={"frontmatter": initial_fm, "body": "# Sanremo\n\nOriginal body."},
    )
    assert resp.status_code == 200, resp.text

    # 2. The AI sends a PARTIAL payload: only name + category + status + body.
    #    It omits hero_title, deck, trumpet, hero_image, author — these must
    #    be preserved from disk, not lost.
    partial_fm = {
        "name": "Sanremo Travel Post",
        "category": "summer",
        "status": "draft",
    }
    resp = authed_client.put(
        "/api/v1/mcp/pages/preserve-test",
        json={
            "frontmatter": partial_fm,
            "body": "# Sanremo\n\nUpdated body with Fifi the dog.",
        },
    )
    assert resp.status_code == 200, resp.text

    # 3. Read back and assert the omitted fields survived.
    resp = authed_client.get("/api/v1/mcp/pages/preserve-test/content")
    assert resp.status_code == 200
    data = resp.json()
    assert data["body"] == "# Sanremo\n\nUpdated body with Fifi the dog."

    # Re-fetch metadata to inspect the persisted frontmatter.
    resp = authed_client.get("/api/v1/mcp/pages/preserve-test/metadata")
    assert resp.status_code == 200
    fm = resp.json()["frontmatter"]

    assert fm.get("hero_title") == "Sanremo: The Empress and the Palms", (
        f"hero_title was destroyed by partial write: {fm!r}"
    )
    assert fm.get("deck") == "A walking tour of the Passeggiata Imperatrice."
    assert fm.get("trumpet") == "Travel"
    assert fm.get("hero_image") == "images/content/sanremo/hero.jpg"
    assert fm.get("author") == "Pietro"


def test_update_frontmatter_field_patches_one_key(authed_client):
    resp = authed_client.put(
        "/api/v1/mcp/pages/deck-patch-test",
        json={
            "frontmatter": {
                "name": "Deck Patch",
                "category": "summer",
                "status": "draft",
                "hero_title": "Keep me",
                "deck": "One line.",
            },
            "body": "# Original body\n",
        },
    )
    assert resp.status_code == 200, resp.text

    patched = authed_client.patch(
        "/api/v1/mcp/pages/deck-patch-test/frontmatter",
        json={
            "key": "deck",
            "value": "One line.\nTwo.\nThree.",
        },
    )
    assert patched.status_code == 200, patched.text

    meta = authed_client.get("/api/v1/mcp/pages/deck-patch-test/metadata")
    assert meta.status_code == 200
    fm = meta.json()["frontmatter"]
    assert fm.get("deck") == "One line.\nTwo.\nThree."
    assert fm.get("hero_title") == "Keep me"
    assert fm.get("category") == "summer"
    content = authed_client.get("/api/v1/mcp/pages/deck-patch-test/content")
    assert content.json()["body"].strip() == "# Original body"


def test_update_frontmatter_field_patches_faqs(authed_client):
    resp = authed_client.put(
        "/api/v1/mcp/pages/faqs-patch-test",
        json={
            "frontmatter": {
                "name": "FAQ Patch",
                "category": "summer",
                "status": "draft",
                "hero_title": "Keep me",
                "deck": "One line.",
            },
            "body": "# Original body\n",
        },
    )
    assert resp.status_code == 200, resp.text

    items = [
        {"q": "What is PenCMS?", "a": "A blog CMS."},
        {"q": "Does every URL need FAQs?", "a": "No."},
    ]
    patched = authed_client.patch(
        "/api/v1/mcp/pages/faqs-patch-test/frontmatter",
        json={"key": "faqs", "value": items},
    )
    assert patched.status_code == 200, patched.text

    meta = authed_client.get("/api/v1/mcp/pages/faqs-patch-test/metadata")
    assert meta.status_code == 200
    fm = meta.json()["frontmatter"]
    assert fm.get("faqs") == items
    assert fm.get("hero_title") == "Keep me"
    assert fm.get("deck") == "One line."
    content = authed_client.get("/api/v1/mcp/pages/faqs-patch-test/content")
    assert content.json()["body"].strip() == "# Original body"

    cleared = authed_client.patch(
        "/api/v1/mcp/pages/faqs-patch-test/frontmatter",
        json={"key": "faqs", "value": []},
    )
    assert cleared.status_code == 200, cleared.text
    cleared_fm = authed_client.get("/api/v1/mcp/pages/faqs-patch-test/metadata").json()[
        "frontmatter"
    ]
    assert not cleared_fm.get("faqs")


def test_update_frontmatter_field_faqs_invalid_rejected(authed_client):
    authed_client.put(
        "/api/v1/mcp/pages/faqs-invalid-test",
        json={
            "frontmatter": {
                "name": "FAQ Invalid",
                "category": "summer",
                "status": "draft",
            },
            "body": "x",
        },
    )
    as_string = authed_client.patch(
        "/api/v1/mcp/pages/faqs-invalid-test/frontmatter",
        json={"key": "faqs", "value": "not-an-array"},
    )
    assert as_string.status_code == 422

    missing_q = authed_client.patch(
        "/api/v1/mcp/pages/faqs-invalid-test/frontmatter",
        json={"key": "faqs", "value": [{"a": "only an answer"}]},
    )
    assert missing_q.status_code == 422


def test_update_frontmatter_field_read_scope_rejected(authed_client, agent_token_factory):
    token = agent_token_factory(["read"])
    headers = {"Authorization": f"Bearer {token}"}
    authed_client.put(
        "/api/v1/mcp/pages/deck-ro-test",
        json={
            "frontmatter": {"name": "RO", "category": "summer", "status": "draft"},
            "body": "x",
        },
    )
    resp = authed_client.patch(
        "/api/v1/mcp/pages/deck-ro-test/frontmatter",
        json={"key": "deck", "value": "nope"},
        headers=headers,
    )
    assert resp.status_code == 403


def test_update_frontmatter_field_in_openapi(client):
    paths = client.get("/api/openapi.json").json()["paths"]
    route = paths["/api/v1/mcp/pages/{slug}/frontmatter"]["patch"]
    assert "mcp" in route["tags"]
    assert route.get("operationId") == "update_frontmatter_field"
    write = paths["/api/v1/mcp/pages/{slug}"]["put"]
    blob = (write.get("summary") or "") + "\n" + (write.get("description") or "")
    assert "Partial frontmatter merge" in blob


def test_write_content_file_omitted_body_keeps_markdown(authed_client):
    authed_client.put(
        "/api/v1/mcp/pages/omit-body-test",
        json={
            "frontmatter": {
                "name": "Omit Body",
                "category": "summer",
                "status": "draft",
                "deck": "old",
            },
            "body": "# Keep this body\n",
        },
    )
    resp = authed_client.put(
        "/api/v1/mcp/pages/omit-body-test",
        json={"frontmatter": {"deck": "new dek"}},
    )
    assert resp.status_code == 200, resp.text
    content = authed_client.get("/api/v1/mcp/pages/omit-body-test/content")
    assert content.json()["body"].strip() == "# Keep this body"
    meta = authed_client.get("/api/v1/mcp/pages/omit-body-test/metadata")
    assert meta.json()["frontmatter"].get("deck") == "new dek"


def test_write_content_file_new_page_requires_body(authed_client):
    resp = authed_client.put(
        "/api/v1/mcp/pages/brand-new-omit-body",
        json={"frontmatter": {"name": "Nope", "category": "summer", "status": "draft"}},
    )
    assert resp.status_code == 400
    assert "body is required" in resp.json()["detail"]


def test_optimistic_concurrency_version_tokens(authed_client, temp_data_root):
    """Reads return a version token; matching writes succeed; stale tokens 409."""
    resp = authed_client.put(
        "/api/v1/mcp/pages/version-token-test",
        json={
            "frontmatter": {"name": "Version Token Test", "category": "summer", "status": "draft"},
            "body": "# v1",
        },
    )
    assert resp.status_code == 200, resp.text
    write_data = resp.json()
    assert "version" in write_data
    assert write_data["version"] is not None
    assert "version_warning" not in write_data

    meta = authed_client.get("/api/v1/mcp/pages/version-token-test/metadata")
    assert meta.status_code == 200
    meta_data = meta.json()
    assert meta_data["version"] == write_data["version"]

    content = authed_client.get("/api/v1/mcp/pages/version-token-test/content")
    assert content.status_code == 200
    content_data = content.json()
    assert content_data["version"] == write_data["version"]
    assert content_data["body"].strip() == "# v1"

    # Matching expected_version: write succeeds, returns a (possibly new) version.
    resp = authed_client.put(
        "/api/v1/mcp/pages/version-token-test",
        json={
            "frontmatter": {"name": "Version Token Test", "category": "summer", "status": "draft"},
            "body": "# v2",
            "expected_version": meta_data["version"],
        },
    )
    assert resp.status_code == 200, resp.text
    matched = resp.json()
    assert matched.get("version") is not None
    assert "version_warning" not in matched

    stale = matched["version"]
    file_path = authed_client.get("/api/pages/version-token-test").json()["file_path"]
    path = temp_data_root / "content" / file_path
    stat = path.stat()
    os.utime(path, (stat.st_atime, stat.st_mtime + 2.0))

    # Mismatched expected_version: 409, disk unchanged.
    resp = authed_client.put(
        "/api/v1/mcp/pages/version-token-test",
        json={
            "frontmatter": {"name": "Version Token Test", "category": "summer", "status": "draft"},
            "body": "# v3",
            "expected_version": stale,
        },
    )
    assert resp.status_code == 409, resp.text
    detail = resp.json()["detail"]
    assert detail["error"] == "version_conflict"
    assert detail["expected_version"] == stale

    content = authed_client.get("/api/v1/mcp/pages/version-token-test/content")
    assert content.status_code == 200
    assert content.json()["body"].strip() == "# v2"

    # Explicit force overwrite succeeds.
    forced = authed_client.put(
        "/api/v1/mcp/pages/version-token-test",
        json={
            "frontmatter": {"name": "Version Token Test", "category": "summer", "status": "draft"},
            "body": "# v3",
            "expected_version": stale,
            "force": True,
        },
    )
    assert forced.status_code == 200, forced.text
    content = authed_client.get("/api/v1/mcp/pages/version-token-test/content")
    assert content.json()["body"].strip() == "# v3"


def test_legacy_key_treated_as_full_access(authed_client, temp_data_root):
    # 1. Create a key
    resp = authed_client.post(
        "/api/auth/keys", json={"name": "legacy-test", "scopes": ["read"]}
    )
    assert resp.status_code == 200
    raw_key = resp.json()["key"]

    # 2. Modify the stored user YAML directly to remove 'scopes'
    import yaml

    users_dir = temp_data_root / "data" / "users"
    user_file = list(users_dir.glob("*.yaml"))[0]
    with open(user_file, "r") as f:
        data = yaml.safe_load(f)

    # Strip scopes to simulate legacy shape
    for key_meta in data["auth"]["agent_keys"]:
        if "scopes" in key_meta:
            del key_meta["scopes"]

    with open(user_file, "w") as f:
        yaml.safe_dump(data, f)

    # 3. Request token
    resp = authed_client.post("/api/auth/token", json={"agent_key": raw_key})
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    # 4. Check if write tool is allowed
    headers = {"Authorization": f"Bearer {token}"}
    resp = authed_client.put(
        "/api/v1/mcp/pages/test-legacy-slug",
        json={
            "frontmatter": {"title": "Legacy Test", "category": "summer"},
            "body": "Legacy body content",
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text


def test_human_session_bypasses_scope_check(authed_client):
    # authed_client already has cookie login. Call write endpoint without Authorization header.
    resp = authed_client.put(
        "/api/v1/mcp/pages/test-human-slug",
        json={
            "frontmatter": {"title": "Human Title", "category": "summer"},
            "body": "Human body content",
        },
    )
    assert resp.status_code == 200, resp.text


def test_unauthenticated_mcp_call_rejected(client):
    # Call without auth cookie or authorization header
    resp = client.get("/api/v1/mcp/collections")
    assert resp.status_code == 401


def test_media_path_traversal_protection(authed_client, agent_token_factory):
    token = agent_token_factory(["read", "write"])
    headers = {"Authorization": f"Bearer {token}"}

    # Try traversing out of the directory
    resp = authed_client.post(
        "/api/v1/mcp/media",
        json={
            "filename": "../../etc/passwd",
            "content_base64": base64.b64encode(b"malicious").decode("utf-8"),
        },
        headers=headers,
    )
    assert resp.status_code == 400
    assert "Directory traversal is not allowed" in resp.json()["detail"]


def test_fts5_search_relevance_and_quoting(authed_client, agent_token_factory):
    token = agent_token_factory(["read", "write"])
    headers = {"Authorization": f"Bearer {token}"}

    # Seed 3 pages
    pages = [
        ("page1", "Unique Keyword Red", "Red apple apple apple."),
        ("page2", "Unique Keyword Blue", "Blue sky blue sky."),
        ("page3", "Unique Keyword Green", "Green grass green grass."),
    ]
    for slug, title, body in pages:
        resp = authed_client.put(
            f"/api/v1/mcp/pages/{slug}",
            json={"frontmatter": {"title": title, "category": "summer"}, "body": body},
            headers=headers,
        )
        assert resp.status_code == 200

    # Search Blue
    resp = authed_client.get("/api/v1/mcp/search?query=Blue", headers=headers)
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) > 0
    assert results[0]["slug"] == "page2"
    assert "<mark>Blue</mark>" in results[0]["excerpt"]

    # Test phrase injection quoting (searching for quote marks or operators shouldn't crash)
    resp = authed_client.get("/api/v1/mcp/search?query=Blue OR Green", headers=headers)
    assert resp.status_code == 200


def test_write_content_file_cleans_partial_keys(authed_client):
    """If the client provides partial keys with leading underscores and .md extensions,
    the backend must clean them so that files are saved as clean paths and the manifest
    preserves correct IDs.
    """
    resp = authed_client.put(
        "/api/v1/mcp/pages/test-partial-clean",
        json={
            "frontmatter": {
                "name": "Test Partial Clean",
                "category": "summer",
                "composite": True,
            },
            "body": "Main composite body",
            "composite": True,
            "partials": {
                "_background-info.md": "Background info content",
                "_primer.md": "Primer content",
            }
        },
    )
    assert resp.status_code == 200, resp.text

    # Read the page back and assert that the partial keys returned are clean
    resp = authed_client.get("/api/v1/mcp/pages/test-partial-clean/content")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "background-info" in data["partials"]
    assert "primer" in data["partials"]
    assert data["partials"]["background-info"] == "Background info content"
    assert data["partials"]["primer"] == "Primer content"

    # Also retrieve metadata and verify the posts list in frontmatter has correct IDs and contents
    resp = authed_client.get("/api/v1/mcp/pages/test-partial-clean/metadata")
    assert resp.status_code == 200, resp.text
    fm = resp.json()["frontmatter"]
    posts = fm.get("posts", [])
    
    # Assert background-info was saved correctly
    bg_post = next((a for a in posts if a.get("id") == "background-info"), None)
    assert bg_post is not None
    assert bg_post.get("content") == "_background-info.md"

    # Assert primer was saved correctly
    primer_post = next((a for a in posts if a.get("id") == "primer"), None)
    assert primer_post is not None
    assert primer_post.get("content") == "_primer.md"


def test_split_section_endpoint(authed_client):
    # 1. Create a simple page
    resp = authed_client.put(
        "/api/v1/mcp/pages/test-split-simple",
        json={
            "frontmatter": {
                "name": "Test Split Simple",
                "category": "summer",
            },
            "body": "Some intro text.\n\n## Performance Section\nHere is performance details.\n\n## Next Section\nMore details.",
            "composite": False
        },
    )
    assert resp.status_code == 200, resp.text
    
    # 2. Call split_section
    resp = authed_client.post(
        "/api/v1/mcp/pages/test-split-simple/split",
        json={
            "source_slug": "index",
            "new_fragment_slug": "performance-metrics",
            "split_marker": "Performance Section"
        }
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["new_fragment_slug"] == "performance-metrics"
    
    # 3. Read it back and verify it's composite and has the partial
    resp = authed_client.get("/api/v1/mcp/pages/test-split-simple/content")
    assert resp.status_code == 200, resp.text
    content_data = resp.json()
    assert content_data["composite"] is True
    assert "performance-metrics" in content_data["partials"]
    assert "Performance Section" in content_data["partials"]["performance-metrics"]
    assert "Here is performance details" in content_data["partials"]["performance-metrics"]
    # Check that it's removed from main body
    assert "Performance Section" not in content_data["body"]
    assert "Next Section" in content_data["body"]


def test_merge_sections_endpoint(authed_client):
    # 1. Create a composite page with two partials
    resp = authed_client.put(
        "/api/v1/mcp/pages/test-merge-comp",
        json={
            "frontmatter": {
                "name": "Test Merge Comp",
                "category": "summer",
                "composite": True,
            },
            "body": "Intro text.",
            "composite": True,
            "partials": {
                "first-part": "## First Part\nSome content.",
                "second-part": "## Second Part\nMore content."
            }
        },
    )
    assert resp.status_code == 200, resp.text
    
    # 2. Merge first-part and second-part into index (main body)
    resp = authed_client.post(
        "/api/v1/mcp/pages/test-merge-comp/merge",
        json={
            "fragment_slugs": ["first-part", "second-part"],
            "into_slug": "index"
        }
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # Since all fragments are merged, it should be simple (composite=False)
    assert data["composite"] is False

    # 3. Read it back
    resp = authed_client.get("/api/v1/mcp/pages/test-merge-comp/content")
    assert resp.status_code == 200, resp.text
    content_data = resp.json()
    assert content_data["composite"] is False
    assert "First Part" in content_data["body"]
    assert "Second Part" in content_data["body"]
    assert not content_data["partials"]


def test_move_section_endpoint(authed_client):
    # 1. Create a composite page with two partials
    resp = authed_client.put(
        "/api/v1/mcp/pages/test-move-comp",
        json={
            "frontmatter": {
                "name": "Test Move Comp",
                "category": "summer",
                "composite": True,
                "posts": [
                    {"id": "index", "title": "Index", "content": "index.md"},
                    {"id": "part-a", "title": "Part A", "content": "_part-a.md"},
                    {"id": "part-b", "title": "Part B", "content": "_part-b.md"}
                ]
            },
            "body": "Intro text.",
            "composite": True,
            "partials": {
                "part-a": "Content A",
                "part-b": "Content B"
            }
        },
    )
    assert resp.status_code == 200, resp.text
    
    # 2. Move part-b before part-a
    resp = authed_client.post(
        "/api/v1/mcp/pages/test-move-comp/move",
        json={
            "heading_path": "part-b",
            "before_or_after": "before",
            "target_heading_path": "part-a"
        }
    )
    assert resp.status_code == 200, resp.text
    
    # 3. Read metadata and verify order
    resp = authed_client.get("/api/v1/mcp/pages/test-move-comp/metadata")
    assert resp.status_code == 200, resp.text
    fm = resp.json()["frontmatter"]
    posts = fm["posts"]
    assert posts[0]["id"] == "index"
    assert posts[1]["id"] == "part-b"
    assert posts[2]["id"] == "part-a"


def test_write_content_file_enforces_guardrails(authed_client):
    """Verify that backend write_content_file endpoint enforces AI settings guardrails."""
    import json
    import config
    from services.ai_settings_service import settings_path_for_site

    # Ensure data dir exists
    data_dir = config.BASE_DIR / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    settings_file = settings_path_for_site("default")
    settings_file.parent.mkdir(parents=True, exist_ok=True)

    # 1. Test publish autonomy: require_approval
    with open(settings_file, "w", encoding="utf-8") as f:
        json.dump({
            "ai_publish_autonomy": "require_approval",
            "ai_metadata_scope": "allow_metadata",
            "ai_prevent_empty_media": True
        }, f)
        
    # Attempt to write page with status=published
    resp = authed_client.put(
        "/api/v1/mcp/pages/guardrail-test",
        json={
            "frontmatter": {"name": "Test Post", "status": "published", "category": "summer"},
            "body": "Body content."
        }
    )
    assert resp.status_code == 400
    assert "Permission Denied: AI is not allowed to set status" in resp.json()["detail"]
    
    # 2. Test publish autonomy: restricted (status change blocked)
    # First create a page with draft status
    with open(settings_file, "w", encoding="utf-8") as f:
        json.dump({
            "ai_publish_autonomy": "autonomous",
            "ai_metadata_scope": "allow_metadata",
            "ai_prevent_empty_media": True
        }, f)
    resp = authed_client.put(
        "/api/v1/mcp/pages/guardrail-test",
        json={
            "frontmatter": {"name": "Test Post", "status": "draft", "category": "summer"},
            "body": "Body content."
        }
    )
    assert resp.status_code == 200

    # Now set restricted and try to change it to stub
    with open(settings_file, "w", encoding="utf-8") as f:
        json.dump({
            "ai_publish_autonomy": "restricted",
            "ai_metadata_scope": "allow_metadata",
            "ai_prevent_empty_media": True
        }, f)
    resp = authed_client.put(
        "/api/v1/mcp/pages/guardrail-test",
        json={
            "frontmatter": {"name": "Test Post", "status": "stub", "category": "summer"},
            "body": "Body content."
        }
    )
    assert resp.status_code == 400
    assert "Permission Denied: AI is prohibited from modifying the status field." in resp.json()["detail"]

    # 3. Test metadata scope: body_only
    with open(settings_file, "w", encoding="utf-8") as f:
        json.dump({
            "ai_publish_autonomy": "autonomous",
            "ai_metadata_scope": "body_only",
            "ai_prevent_empty_media": True
        }, f)
    # Attempting to change frontmatter field 'tags'
    resp = authed_client.put(
        "/api/v1/mcp/pages/guardrail-test",
        json={
            "frontmatter": {"name": "Test Post", "status": "draft", "category": "summer", "tags": ["tech"]},
            "body": "Body content."
        }
    )
    assert resp.status_code == 400
    assert "AI is restricted to body-only edits and cannot modify frontmatter field" in resp.json()["detail"]

    # 4. Test prevent empty media paths
    with open(settings_file, "w", encoding="utf-8") as f:
        json.dump({
            "ai_publish_autonomy": "autonomous",
            "ai_metadata_scope": "allow_metadata",
            "ai_prevent_empty_media": True
        }, f)
    resp = authed_client.put(
        "/api/v1/mcp/pages/guardrail-test",
        json={
            "frontmatter": {"name": "Test Post", "status": "draft", "category": "summer"},
            "body": "Body [image src=\"\" align=\"center\"]. text"
        }
    )
    assert resp.status_code == 400
    assert "Integrity Violation: Image source path cannot be empty." in resp.json()["detail"]

    # API-style public_url paths are normalized to relative before warn/persist.
    # Missing relative target → soft "not found" warning (not public_url warning).
    resp = authed_client.put(
        "/api/v1/mcp/pages/guardrail-test",
        json={
            "frontmatter": {"name": "Test Post", "status": "draft", "category": "summer"},
            "body": "Body [image src=\"/api/assets/raw/images/content/photo.jpg\" align=\"center\"]. text"
        }
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "media_path_warnings" in data
    assert any("images/content/photo.jpg" in w for w in data["media_path_warnings"])
    assert not any("public_url" in w for w in data["media_path_warnings"])
    stored = authed_client.get("/api/v1/mcp/pages/guardrail-test/content")
    assert stored.status_code == 200
    assert 'src="images/content/photo.jpg"' in stored.json()["body"]
    assert "/api/assets/raw/" not in stored.json()["body"]
    
    # Cleanup settings file for other tests
    if settings_file.exists():
        settings_file.unlink()


def test_write_content_file_i18n_active_honors_autonomous_publish(
    authed_client, agent_token_factory
):
    """i18n-active default-language writes use the same publish autonomy dial."""
    from services.ai_settings_service import load_ai_settings, save_ai_settings

    listed = authed_client.get("/api/sites")
    assert listed.status_code == 200, listed.text
    prior_site = next(s for s in listed.json()["sites"] if s["id"] == "default")
    prior_settings = load_ai_settings("default")
    token = agent_token_factory(["read", "write"])
    headers = {"Authorization": f"Bearer {token}"}
    try:
        enabled = authed_client.patch(
            "/api/sites/default",
            json={"language": "en", "languages": ["en", "fr"]},
        )
        assert enabled.status_code == 200, enabled.text
        save_ai_settings("default", {**prior_settings, "ai_publish_autonomy": "autonomous"})

        resp = authed_client.put(
            "/api/v1/mcp/pages/i18n-auton-pub",
            headers=headers,
            json={
                "frontmatter": {
                    "name": "I18n Auton",
                    "status": "published",
                    "category": "summer",
                    "published": True,
                },
                "body": "Live with i18n on.",
            },
        )
        assert resp.status_code == 200, resp.text
        meta = authed_client.get(
            "/api/v1/mcp/pages/i18n-auton-pub/metadata", headers=headers
        )
        assert meta.status_code == 200, meta.text
        fm = meta.json()["frontmatter"]
        assert fm["status"] == "published"
        assert fm.get("published") is True
        assert not fm.get("needs_review")
    finally:
        save_ai_settings("default", prior_settings)
        authed_client.patch(
            "/api/sites/default",
            json={
                "language": prior_site.get("language") or "en",
                "languages": prior_site.get("languages") or [],
                "language_labels": prior_site.get("language_labels") or {},
            },
        )


def test_write_content_file_media_path_soft_warnings(authed_client):
    """Missing / invented media paths soft-warn but do not block the write."""
    import base64
    import json
    import config
    from services.ai_settings_service import settings_path_for_site

    data_dir = config.BASE_DIR / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    settings_file = settings_path_for_site("default")
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    with open(settings_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "ai_publish_autonomy": "autonomous",
                "ai_metadata_scope": "allow_metadata",
                "ai_prevent_empty_media": True,
            },
            f,
        )

    try:
        # Missing body shortcode path
        resp = authed_client.put(
            "/api/v1/mcp/pages/media-warn-body",
            json={
                "frontmatter": {
                    "name": "Media Warn Body",
                    "status": "draft",
                    "category": "summer",
                },
                "body": 'Hello [image src="does-not-exist.png" alt="x"].',
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "media_path_warnings" in data
        assert any("does-not-exist.png" in w for w in data["media_path_warnings"])

        # Missing hero_image frontmatter
        resp = authed_client.put(
            "/api/v1/mcp/pages/media-warn-hero",
            json={
                "frontmatter": {
                    "name": "Media Warn Hero",
                    "status": "draft",
                    "category": "summer",
                    "hero_image": "hero.jpg",
                },
                "body": "No images in body.",
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "media_path_warnings" in data
        assert any("hero.jpg" in w for w in data["media_path_warnings"])

        # Real uploaded asset — no media warnings
        tiny_png = base64.b64encode(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
            b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
            b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        ).decode("ascii")
        upload = authed_client.post(
            "/api/v1/mcp/media",
            json={
                "filename": "images/content/media-warn-ok.png",
                "content_base64": tiny_png,
            },
        )
        assert upload.status_code == 200, upload.text
        up = upload.json()
        assert up.get("relative_path") == "images/content/media-warn-ok.png"
        assert up.get("use_for_embedding") == "images/content/media-warn-ok.png"

        resp = authed_client.put(
            "/api/v1/mcp/pages/media-warn-ok",
            json={
                "frontmatter": {
                    "name": "Media Warn Ok",
                    "status": "draft",
                    "category": "summer",
                    "hero_image": "images/content/media-warn-ok.png",
                },
                "body": (
                    'Ok [image src="images/content/media-warn-ok.png" alt="ok"].'
                ),
            },
        )
        assert resp.status_code == 200, resp.text
        assert "media_path_warnings" not in resp.json()

        # public_url form for an existing asset is normalized; no media warnings
        resp = authed_client.put(
            "/api/v1/mcp/pages/media-warn-normalize",
            json={
                "frontmatter": {
                    "name": "Media Warn Normalize",
                    "status": "draft",
                    "category": "summer",
                    "hero_image": (
                        "/api/assets/raw/sites/default/assets/"
                        "images/content/media-warn-ok.png"
                    ),
                },
                "body": (
                    'Ok [image src="/api/assets/raw/sites/default/assets/'
                    'images/content/media-warn-ok.png" alt="ok"].'
                ),
            },
        )
        assert resp.status_code == 200, resp.text
        assert "media_path_warnings" not in resp.json()
        stored = authed_client.get(
            "/api/v1/mcp/pages/media-warn-normalize/content"
        )
        assert stored.status_code == 200
        body = stored.json()["body"]
        assert 'src="images/content/media-warn-ok.png"' in body
        assert "/api/assets/raw/" not in body
        meta = authed_client.get(
            "/api/v1/mcp/pages/media-warn-normalize/metadata"
        )
        assert meta.status_code == 200
        assert (
            meta.json()["frontmatter"]["hero_image"]
            == "images/content/media-warn-ok.png"
        )

        # Negative: genuine typo / missing path is NOT rewritten by normalize —
        # soft-warn and persist the exact string the agent submitted (case,
        # punctuation, and order untouched — guards against over-helpful
        # refactors that pass a looser "still contains path" check).
        typo_src = "Images/Content/Typo-Does-NOT-Exist_xyz.jpg"
        body_in = f'Bad [image src="{typo_src}" alt="typo"].'
        resp = authed_client.put(
            "/api/v1/mcp/pages/media-warn-typo",
            json={
                "frontmatter": {
                    "name": "Media Warn Typo",
                    "status": "draft",
                    "category": "summer",
                    "hero_image": typo_src,
                },
                "body": body_in,
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "media_path_warnings" in data
        assert any(typo_src in w for w in data["media_path_warnings"])
        assert not any("public_url" in w for w in data["media_path_warnings"])
        stored = authed_client.get("/api/v1/mcp/pages/media-warn-typo/content")
        assert stored.status_code == 200
        assert stored.json()["body"] == body_in
        meta = authed_client.get("/api/v1/mcp/pages/media-warn-typo/metadata")
        assert meta.status_code == 200
        assert meta.json()["frontmatter"]["hero_image"] == typo_src
    finally:
        if settings_file.exists():
            settings_file.unlink()


def test_normalize_public_media_paths_leaves_typos_untouched():
    """Unit: only /api/assets/raw/... forms are rewritten; typos stay byte-identical."""
    from routers.mcp_tools import normalize_public_media_paths

    # Mixed case + underscore: must round-trip with exact string equality
    # (not merely "still looks similar" after re-casing / reordering).
    typo = "Images/Content/Typo-Does-NOT-Exist_xyz.jpg"
    assert normalize_public_media_paths(typo) == typo
    body_typo = f'[image src="{typo}" alt="x"]'
    assert normalize_public_media_paths(body_typo) == body_typo
    mixed = (
        'A [image src="/api/assets/raw/sites/default/assets/'
        'images/content/ok.png"] and '
        f'[image src="{typo}"].'
    )
    out = normalize_public_media_paths(mixed)
    assert out == (
        'A [image src="images/content/ok.png"] and '
        f'[image src="{typo}"].'
    )


def test_write_content_file_guardrails_are_per_site(authed_client):
    """MCP writes enforce the JWT site's AI guardrails, not another site's."""
    import json
    import secrets

    from services.ai_settings_service import settings_path_for_site
    from services.site_service import create_site, ensure_sites_initialized, get_site

    ensure_sites_initialized()
    if get_site("grdwiki") is None:
        create_site("grdwiki", "Guardrail Wiki")

    default_settings = settings_path_for_site("default")
    wiki_settings = settings_path_for_site("grdwiki")
    default_settings.parent.mkdir(parents=True, exist_ok=True)

    with open(default_settings, "w", encoding="utf-8") as f:
        json.dump(
            {
                "ai_publish_autonomy": "autonomous",
                "ai_metadata_scope": "allow_metadata",
            },
            f,
        )

    def _mint(site_id: str) -> dict:
        resp = authed_client.post(
            "/api/auth/keys",
            json={
                "name": f"grd-{site_id}-{secrets.token_hex(3)}",
                "scopes": ["read", "write"],
                "site_id": site_id,
            },
        )
        assert resp.status_code == 200, resp.text
        raw_key = resp.json()["key"]
        resp = authed_client.post("/api/auth/token", json={"agent_key": raw_key})
        assert resp.status_code == 200, resp.text
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    try:
        wiki_headers = _mint("grdwiki")

        # Seed a draft under wiki while autonomy is open
        with open(wiki_settings, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "ai_publish_autonomy": "autonomous",
                    "ai_metadata_scope": "allow_metadata",
                },
                f,
            )
        resp = authed_client.put(
            "/api/v1/mcp/pages/grd-site-test",
            json={
                "frontmatter": {"name": "Guardrail Site", "status": "draft", "category": "summer"},
                "body": "Body.",
            },
            headers=wiki_headers,
        )
        assert resp.status_code == 200, resp.text

        with open(wiki_settings, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "ai_publish_autonomy": "restricted",
                    "ai_metadata_scope": "allow_metadata",
                },
                f,
            )

        # Wiki agent cannot change status (restricted) even though default is autonomous
        resp = authed_client.put(
            "/api/v1/mcp/pages/grd-site-test",
            json={
                "frontmatter": {"name": "Guardrail Site", "status": "published", "category": "summer"},
                "body": "Body.",
            },
            headers=wiki_headers,
        )
        assert resp.status_code == 400
        assert "prohibited from modifying the status field" in resp.json()["detail"]

        # Default-site agent can publish (autonomous)
        default_headers = _mint("default")
        resp = authed_client.put(
            "/api/v1/mcp/pages/grd-default-test",
            json={
                "frontmatter": {"name": "Guardrail Default", "status": "published", "category": "summer"},
                "body": "Body.",
            },
            headers=default_headers,
        )
        assert resp.status_code == 200, resp.text
    finally:
        for p in (default_settings, wiki_settings):
            if p.exists():
                p.unlink()


def test_review_post_endpoint(authed_client, agent_token_factory):
    """Verify that backend review endpoint evaluates the page correctly using mocked LLM response."""
    import respx
    import httpx

    token = agent_token_factory(["read", "write"])
    headers = {"Authorization": f"Bearer {token}"}
    
    # Let's ensure a test page exists
    authed_client.put(
        "/api/v1/mcp/pages/review-test-post",
        json={
            "frontmatter": {"name": "Review Test Post", "status": "draft", "category": "summer"},
            "body": "This is a post body to review."
        },
        headers=headers,
    )
    
    eval_response = {
        "overall_score": 85,
        "criteria": [
            {
                "name": "Title & Meta",
                "score": 90,
                "notes": "Good title.",
                "suggested_edit": "None needed."
            }
        ],
        "top_improvements": [
            "Add a call to action."
        ]
    }
    
    import json
    
    with respx.mock(base_url="https://api.openai.com") as mock:
        mock.post("/v1/chat/completions").mock(
            return_value=httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": json.dumps(eval_response)
                            }
                        }
                    ]
                }
            )
        )
        
        # Test review with default checklist
        resp = authed_client.post(
            "/api/v1/mcp/pages/review-test-post/review",
            headers={
                "X-Pen-AI-Key": "testkey",
                "X-Pen-AI-Model": "gpt-4o",
                "Authorization": f"Bearer {token}"
            }
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["overall_score"] == 85
        assert data["criteria"][0]["name"] == "Title & Meta"
        assert data["top_improvements"][0] == "Add a call to action."
        assert data["slug"] == "review-test-post"


def test_create_post_endpoint(authed_client, agent_token_factory):
    token = agent_token_factory(["read", "write"])
    headers = {"Authorization": f"Bearer {token}"}

    from services.file_service import delete_page
    import asyncio

    created_slugs = ["testing-the-waters", "body-only-test-post"]

    # Setup cleanup (in case previous runs failed/aborted)
    for slug in created_slugs:
        try:
            asyncio.run(delete_page(slug))
        except Exception:
            pass

    try:
        # 1. Successful creation
        resp = authed_client.post(
            "/api/v1/mcp/posts",
            json={"name": "Testing the Waters"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["slug"] == "testing-the-waters"
        assert "Testing the Waters" in data["message"]
        assert "category" in data
        assert data["status"] == "stub"
        assert data["published"] is False
        assert data["ai_publish_autonomy"] == "require_approval"
        assert "write_content_file" in data["next"]

        # Verify the stub file actually exists on disk
        resp = authed_client.get(
            "/api/v1/mcp/pages/testing-the-waters/content",
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["body"] == ""

        # Verify metadata
        resp = authed_client.get(
            "/api/v1/mcp/pages/testing-the-waters/metadata",
            headers=headers,
        )
        assert resp.status_code == 200
        meta = resp.json()["frontmatter"]
        assert meta["status"] == "stub"
        assert meta["name"] == "Testing the Waters"

        # 2. Collision: keep display name, unique-ify slug with a timestamp
        resp = authed_client.post(
            "/api/v1/mcp/posts",
            json={"name": "Testing the Waters"},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        dup = resp.json()
        unique_slug = dup["slug"]
        created_slugs.append(unique_slug)
        assert unique_slug.startswith("testing-the-waters-")
        assert unique_slug != "testing-the-waters"
        meta_dup = authed_client.get(
            f"/api/v1/mcp/pages/{unique_slug}/metadata",
            headers=headers,
        )
        assert meta_dup.status_code == 200
        assert meta_dup.json()["frontmatter"]["name"] == "Testing the Waters"

        # 3. Empty name validation
        resp = authed_client.post(
            "/api/v1/mcp/posts",
            json={"name": "   "},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "name cannot be empty" in resp.json()["detail"].lower()

        # 4. Respecting ai_metadata_scope = body_only
        from services.ai_settings_service import settings_path_for_site
        settings_file = settings_path_for_site("default")
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump({
                "ai_metadata_scope": "body_only"
            }, f)

        try:
            # Category set is rejected when body_only is active
            resp = authed_client.post(
                "/api/v1/mcp/posts",
                json={"name": "Body Only Test Post", "category": "some-cat"},
                headers=headers,
            )
            assert resp.status_code == 400
            assert "restricted to body-only edits and cannot set custom metadata" in resp.json()["detail"]

            # No category is fine (defaults to system default category)
            resp = authed_client.post(
                "/api/v1/mcp/posts",
                json={"name": "Body Only Test Post"},
                headers=headers,
            )
            assert resp.status_code == 200
            assert resp.json()["slug"] == "body-only-test-post"
        finally:
            if settings_file.exists():
                settings_file.unlink()
    finally:
        for slug in created_slugs:
            try:
                asyncio.run(delete_page(slug))
            except Exception:
                pass




