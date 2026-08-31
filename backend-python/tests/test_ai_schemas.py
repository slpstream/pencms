"""Phase 5 invariants for `GET /api/ai/schemas` and `collections.yaml`.

These tests lock in the contract documented in
`core/docs/AI-PenCMS-implementation_plan.md` § "Phase 5 — Dynamic Schema
Discovery". The endpoint is the bridge between the YAML file the user
edits and the system prompt the sidebar emits, so a regression here would
silently degrade every AI response.

Scope:
- Auth (401 without cookie/bearer).
- Response shape (`collections`, `taxonomy`, `required_fields`).
- The `posts` collection is present and advertises the canonical headline
  field as `name` (NOT `title`) — this is the settled decision in the plan.
- The `required:` flags on each field mirror the Pydantic declaration in
  `models/page.py` `PageFrontmatter`. This is the rule the user explicitly
  agreed to in the review session: Pydantic optionality is the source of
  truth, not `taxonomy.yaml`'s `required_fields` list.
- The `conditional_required` block mirrors `validate_required_fields_for_non_stubs`.
"""

from __future__ import annotations

from typing import Any, Dict

import pytest

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_schemas_requires_authentication(client):
    """No cookie, no bearer → 401. Schemas aren't secret, but the endpoint
    must not be a free enumeration surface for anonymous crawlers."""
    resp = client.get("/api/ai/schemas")
    assert resp.status_code == 401


def test_schemas_accepts_bearer_token(authed_client):
    """Agent Bearer tokens (the MCP gateway auth path) must work too —
    MCP tools will consume this same endpoint."""
    resp = authed_client.post(
        "/api/auth/keys", json={"name": "ai-schemas-bearer", "scopes": ["read"]}
    )
    assert resp.status_code == 200
    raw_key = resp.json()["key"]

    resp = authed_client.post("/api/auth/token", json={"agent_key": raw_key})
    assert resp.status_code == 200
    bearer = resp.json()["access_token"]

    resp = authed_client.get(
        "/api/ai/schemas",
        headers={"Authorization": f"Bearer {bearer}"},
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------


@pytest.fixture
def schemas(authed_client) -> Dict[str, Any]:
    resp = authed_client.get("/api/ai/schemas")
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_schemas_response_shape(schemas):
    assert set(schemas.keys()) >= {
        "collections",
        "taxonomy",
        "required_fields",
    }
    assert isinstance(schemas["collections"], dict)
    assert isinstance(schemas["taxonomy"], dict)
    assert isinstance(schemas["required_fields"], list)


def test_schemas_taxonomy_surface(schemas):
    """The taxonomy block mirrors what `/api/taxonomy/` serves, so the
    sidebar can render allowed `category` terms into the prompt without
    a second round-trip."""
    tax = schemas["taxonomy"]
    assert "vocabularies" in tax
    assert "primary_vocabulary" in tax
    # Install seed is an empty slate — no thematic demo vocabularies.
    assert tax["vocabularies"] == {}
    assert not tax["primary_vocabulary"]

    # The frontmatter field `category` is validated against the PRIMARY
    # vocabulary, NOT against a vocabulary literally named `category`.
    # collections.yaml reflects this with `vocabulary: primary` on the
    # `category` field — see renderCollectionSchema in ai-sidebar.js for
    # the client-side resolution. This invariant is the historical source
    # of a confusion bug and is locked in here.
    posts = schemas["collections"]["posts"]
    cat_field = next(f for f in posts["frontmatter"] if f["name"] == "category")
    assert cat_field["vocabulary"] == "primary", (
        "The `category` frontmatter field must declare `vocabulary: primary` "
        "so the sidebar resolves it to primary_vocabulary's terms, NOT to "
        "a vocabulary literally named `category`. See the validate_category "
        "validator in models/page.py — it checks config.PRIMARY_TERMS."
    )


# ---------------------------------------------------------------------------
# The `posts` collection
# ---------------------------------------------------------------------------


def test_posts_collection_present(schemas):
    assert "posts" in schemas["collections"]
    posts = schemas["collections"]["posts"]
    assert posts["label"] == "Posts"
    assert posts["directory"].endswith("/")
    assert "frontmatter" in posts
    assert isinstance(posts["frontmatter"], list)


def test_posts_collection_advertises_name_not_title(schemas):
    """The settled decision: the canonical headline field is `name`, not
    `title`. Teaching the AI `title` invites silent breakage if the
    `alias_type_to_category` validator is ever removed."""
    posts = schemas["collections"]["posts"]
    field_names = {f["name"] for f in posts["frontmatter"]}
    assert "name" in field_names
    assert "title" not in field_names


def test_posts_collection_required_fields_match_pydantic(schemas):
    """Every field's `required` flag must mirror `PageFrontmatter` in
    `models/page.py`. This is the rule the user agreed to in the review:
    Pydantic optionality is the source of truth, not `taxonomy.yaml`'s
    `required_fields` list (which is the *conditional* requirement for
    non-stub statuses — a different concept, tested below).
    """
    posts = schemas["collections"]["posts"]
    by_name = {f["name"]: f for f in posts["frontmatter"]}

    # Required by Pydantic (no Optional, no default).
    required_true = {"name", "category"}
    # Optional with a default — explicitly NOT required at the Pydantic level.
    required_false_with_default = {
        "domain",  # = "blog"
        "status",  # = "stub"   ← the plan draft had this wrong
        "published",  # = False
        "tags",  # = []
        "created_by",  # = "human"
        "needs_review",  # = False
        "pinned",  # = False
        "noindex",  # = False
        "faqs",  # = []
    }
    # Optional without a default — also NOT required at the Pydantic level.
    required_false_no_default = {
        "date",
        "publish_at",
        "author",
        "main_image",
        "notes",
        "confidence",
        "source",
        "deck",
        "summary",
        "trumpet",
        "hero_image",
        "hero_title",
    }

    for name in required_true:
        assert by_name[name]["required"] is True, (
            f"Field `{name}` is required by PageFrontmatter but the YAML "
            f"marks required=false. The AI would be told it can omit a "
            f"field that the backend will reject."
        )

    for name in required_false_with_default | required_false_no_default:
        assert name in by_name, f"Field `{name}` is missing from the YAML"
        assert by_name[name]["required"] is False, (
            f"Field `{name}` is Optional in PageFrontmatter but the YAML "
            f"marks required=true. The AI would over-promise a field that "
            f"the backend accepts as missing."
        )


def test_posts_collection_advertises_faqs(schemas):
    """First-class Q&A is a typed optional list; empty [] is valid and default."""
    posts = schemas["collections"]["posts"]
    by_name = {f["name"]: f for f in posts["frontmatter"]}
    assert "faqs" in by_name, "Field `faqs` is missing from collections.yaml"
    faqs = by_name["faqs"]
    assert faqs["required"] is False
    assert faqs["default"] == []
    assert faqs["type"] == "list"


def test_posts_collection_conditional_required_block(schemas):
    """The `conditional_required` block must mirror
    `validate_required_fields_for_non_stubs` in `PageFrontmatter` and
    `required_fields` in `taxonomy.yaml`."""
    posts = schemas["collections"]["posts"]
    assert "conditional_required" in posts
    cond = posts["conditional_required"]

    assert cond["when_status_in"] == ["unpublished", "published"]
    # Cross-check against config.REQUIRED_FIELDS (which is loaded from
    # taxonomy.yaml's `required_fields` list — the source of truth for the
    # conditional validator).
    from config import REQUIRED_FIELDS

    assert set(cond["fields"]) == set(REQUIRED_FIELDS), (
        f"collections.yaml conditional_required.fields={cond['fields']} "
        f"does not match taxonomy.yaml required_fields={REQUIRED_FIELDS}. "
        f"These two must stay in sync — the conditional validator in "
        f"PageFrontmatter reads REQUIRED_FIELDS, not the YAML."
    )


# ---------------------------------------------------------------------------
# Reload behaviour
# ---------------------------------------------------------------------------


def test_reload_collections_schema_picks_up_new_file(tmp_path, monkeypatch):
    """`reload_collections_schema()` must re-read the file from disk so a
    future admin 'reload schemas' endpoint can pick up edits without a
    full server restart. This matches `reload_taxonomy()`'s contract."""
    import config

    new_yaml = tmp_path / "collections.yaml"
    new_yaml.write_text(
        """
collections:
  test_collection:
    label: Test Collection
    directory: test/
    frontmatter:
      - name: title
        type: string
        required: true
""",
        encoding="utf-8",
    )

    monkeypatch.setattr(config, "COLLECTIONS_SCHEMA_PATH", new_yaml)
    config.reload_collections_schema()

    assert "test_collection" in config.COLLECTIONS_SCHEMA
    assert config.COLLECTIONS_SCHEMA["test_collection"]["label"] == "Test Collection"

    # Restore real state so other tests aren't affected.
    monkeypatch.undo()
    config.reload_collections_schema()


def test_reload_collections_schema_handles_missing_file(monkeypatch):
    """A missing collections.yaml must not crash the server — every
    collection-aware caller treats an empty dict as 'no schema
    advertised'. This is what lets a fresh checkout boot before Phase 5
    adds the file."""
    from pathlib import Path

    import config

    missing = Path("/tmp/__pencms_definitely_does_not_exist__.yaml")
    if missing.exists():  # extremely unlikely
        missing.unlink()
    monkeypatch.setattr(config, "COLLECTIONS_SCHEMA_PATH", missing)
    config.reload_collections_schema()

    assert config.COLLECTIONS_SCHEMA == {}
