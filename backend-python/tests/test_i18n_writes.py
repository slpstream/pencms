"""Slice 6 exact-language REST/MCP write, review, coverage, and run contracts."""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

import frontmatter
import jwt
import pytest


@pytest.fixture
def slice6_site(authed_client, temp_data_root: Path):
    from services.cache_service import get_db_connection, init_db
    from services.site_service import ensure_sites_initialized

    sites_yaml = temp_data_root / "data" / "sites.yaml"
    if sites_yaml.exists():
        sites_yaml.unlink()
    sites_root = temp_data_root / "content" / "sites"
    if sites_root.exists():
        shutil.rmtree(sites_root)
    runs_root = temp_data_root / "data" / "i18n-runs"
    if runs_root.exists():
        shutil.rmtree(runs_root)
    ensure_sites_initialized()
    init_db()
    with get_db_connection() as conn:
        conn.execute("DELETE FROM entries")
        conn.execute("INSERT INTO entries_fts(entries_fts) VALUES('rebuild')")
        conn.commit()
    response = authed_client.patch(
        "/api/sites/default",
        json={"language": "en", "languages": ["en", "fr"]},
    )
    assert response.status_code == 200, response.text
    return temp_data_root / "content" / "sites" / "default"


def _source(client, slug: str, *, body: str = "English"):
    response = client.put(
        f"/api/v1/content/collections/summer/entries/{slug}",
        json={
            "frontmatter": {
                "name": slug.replace("-", " ").title(),
                "category": "summer",
                "status": "draft",
                "published": False,
            },
            "body": body,
        },
    )
    assert response.status_code == 200, response.text
    return response


def _agent(client, name: str = "daily-localizer", site_id: str = "default"):
    response = client.post(
        "/api/auth/keys",
        json={"name": name, "scopes": ["read", "write"], "site_id": site_id},
    )
    assert response.status_code == 200, response.text
    raw = response.json()["key"]
    token = client.post("/api/auth/token", json={"agent_key": raw})
    assert token.status_code == 200, token.text
    return raw, token.json()["access_token"]


def test_named_agent_claim_and_rest_atomic_crud_review(
    authed_client, slice6_site
):
    _source(authed_client, "guide")
    raw, token = _agent(authed_client)
    claims = jwt.decode(token, options={"verify_signature": False})
    assert claims["agent_key_name"] == "daily-localizer"
    assert claims["site_id"] == "default"

    created = authed_client.post(
        "/api/v1/content/collections/summer/entries/guide/translations",
        json={
            "language": "fr",
            "frontmatter": {"name": "Guide français", "category": "summer"},
            "body": "Français",
        },
    )
    assert created.status_code == 201, created.text
    entry = created.json()["entry"]
    assert entry["language"] == "fr"
    assert entry["provenance"]["created_by"] == "human"
    assert entry["provenance"]["created_by_id"] == "testadmin"
    assert entry["provenance"]["needs_review"] is False
    assert (slice6_site / "guide" / "fr" / "index.md").exists()
    source = frontmatter.load(slice6_site / "guide" / "index.md")
    target = frontmatter.load(slice6_site / "guide" / "fr" / "index.md")
    assert source["translation_group"] == target["translation_group"]

    duplicate = authed_client.post(
        "/api/v1/content/collections/summer/entries/guide/translations",
        json={"language": "fr", "body": "Overwrite"},
    )
    assert duplicate.status_code == 409
    assert frontmatter.load(slice6_site / "guide" / "fr" / "index.md").content == "Français"

    updated = authed_client.put(
        "/api/v1/content/collections/summer/entries/guide?language=fr",
        json={
            "frontmatter": {"name": "Guide révisé", "category": "summer"},
            "body": "Révision",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["entry"]["provenance"]["created_by_id"] == "testadmin"
    read_back = authed_client.get(
        "/api/v1/content/collections/summer/entries/guide?language=fr"
    )
    assert read_back.status_code == 200, read_back.text
    assert read_back.json()["provenance"]["created_by_id"] == "testadmin"

    approved = authed_client.post(
        "/api/v1/translations/guide/fr/review",
        json={"decision": "approve"},
    )
    assert approved.status_code == 200, approved.text
    approved_fm = approved.json()["entry"]["frontmatter"]
    assert approved_fm["status"] == "published"
    assert approved_fm["published"] is True
    assert approved_fm["review_decision"] == "approved"
    assert approved_fm["reviewed_by"] == "testadmin"

    # Reject withholds evidence rather than deleting it.
    rejected = authed_client.post(
        "/api/v1/translations/guide/fr/review",
        json={"decision": "reject"},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["entry"]["frontmatter"]["status"] == "draft"
    assert rejected.json()["entry"]["frontmatter"]["review_decision"] == "rejected"

    deleted = authed_client.delete(
        "/api/v1/content/collections/summer/entries/guide?language=fr"
    )
    assert deleted.status_code == 200, deleted.text
    assert not (slice6_site / "guide" / "fr").exists()


def test_default_delete_requires_explicit_whole_group_request(
    authed_client, slice6_site
):
    _source(authed_client, "delete-group")
    sibling = authed_client.post(
        "/api/v1/content/collections/summer/entries/delete-group/translations",
        json={"language": "fr", "body": "Français"},
    )
    assert sibling.status_code == 201, sibling.text

    blocked = authed_client.delete(
        "/api/v1/content/collections/summer/entries/delete-group"
    )
    assert blocked.status_code == 409
    assert "whole-group" in blocked.json()["detail"]

    _, token = _agent(authed_client, "group-delete-agent")
    agent_delete = authed_client.delete(
        "/api/v1/content/collections/summer/entries/delete-group",
        params={"delete_group": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert agent_delete.status_code == 403

    deleted = authed_client.delete(
        "/api/v1/content/collections/summer/entries/delete-group",
        params={"delete_group": True},
    )
    assert deleted.status_code == 200, deleted.text
    assert not (slice6_site / "delete-group").exists()
    assert authed_client.get("/api/pages/delete-group").status_code == 404


def test_first_sibling_failure_rolls_back_source_group_and_target(
    authed_client, slice6_site, monkeypatch
):
    from services import file_service
    from services.translation_service import ActorContext, create_translation_sibling

    _source(authed_client, "rollback")
    original_write = file_service.content_storage.write
    failed = False

    async def fail_target(path, content):
        nonlocal failed
        if path.endswith("/rollback/fr/index.md") and not failed:
            failed = True
            raise OSError("injected target failure")
        return await original_write(path, content)

    monkeypatch.setattr(file_service.content_storage, "write", fail_target)
    with pytest.raises(OSError, match="injected target failure"):
        asyncio.run(
            create_translation_sibling(
                collection="summer",
                slug="rollback",
                language="fr",
                actor=ActorContext("human", "testadmin", "default"),
                body="Ne doit pas rester",
            )
        )

    source = frontmatter.load(slice6_site / "rollback" / "index.md")
    assert "translation_group" not in source.metadata
    assert "language" not in source.metadata
    assert not (slice6_site / "rollback" / "fr" / "index.md").exists()


def test_agent_provenance_spoof_pause_and_human_override(
    authed_client, slice6_site
):
    _source(authed_client, "agent-guide")
    source_live = authed_client.put(
        "/api/v1/content/collections/summer/entries/agent-guide",
        json={
            "frontmatter": {
                "name": "Agent Guide",
                "category": "summer",
                "status": "published",
                "published": True,
            },
            "body": "English",
        },
    )
    assert source_live.status_code == 200, source_live.text
    _, token = _agent(authed_client, "nightly-fr")
    headers = {"Authorization": f"Bearer {token}"}

    spoof = authed_client.post(
        "/api/v1/mcp/translations/agent-guide",
        headers=headers,
        json={
            "language": "fr",
            "collection": "summer",
            "frontmatter": {"created_by": "human"},
            "body": "Non",
        },
    )
    assert spoof.status_code == 400
    assert "server-owned" in spoof.json()["detail"].lower()

    created = authed_client.post(
        "/api/v1/mcp/translations/agent-guide",
        headers=headers,
        json={
            "language": "fr",
            "collection": "summer",
            "frontmatter": {"name": "Guide agent", "category": "summer"},
            "body": "Brouillon",
        },
    )
    assert created.status_code == 200, created.text
    provenance = created.json()["entry"]["provenance"]
    assert provenance["created_by"] == "agent"
    assert provenance["created_by_id"] == "nightly-fr"
    assert provenance["needs_review"] is True
    assert provenance["review_decision"] == "pending"

    legacy_bypass = authed_client.patch(
        "/api/pages/agent-guide/approve?language=fr",
        headers={
            **headers,
            "X-Pen-Site-Id": "default",
        },
    )
    assert legacy_bypass.status_code == 403

    agent_review = authed_client.post(
        "/api/v1/mcp/translations/agent-guide/fr/review",
        headers=headers,
        json={"decision": "approve"},
    )
    assert agent_review.status_code == 403

    publish_bypass = authed_client.put(
        "/api/pages/agent-guide?language=fr",
        json={
            "frontmatter": {
                "name": "Guide agent édité",
                "category": "summer",
                "status": "published",
                "published": True,
            },
            "content": "Tentative de publication",
        },
    )
    assert publish_bypass.status_code == 200, publish_bypass.text
    bypass_metadata = publish_bypass.json()["frontmatter"]
    assert bypass_metadata["status"] == "draft"
    assert bypass_metadata["published"] is False
    assert bypass_metadata["needs_review"] is True
    public_before_review = authed_client.get(
        "/api/pages/agent-guide",
        params={"language": "fr", "live_only": True},
    )
    assert public_before_review.status_code == 404

    human_review = authed_client.post(
        "/api/v1/translations/agent-guide/fr/review",
        json={"decision": "approve", "note": "Checked against the source."},
    )
    assert human_review.status_code == 200, human_review.text
    reviewed = human_review.json()["entry"]["frontmatter"]
    assert reviewed["review_decision"] == "approved"
    assert reviewed["review_note"] == "Checked against the source."
    assert reviewed["status"] == "published"
    assert reviewed["published"] is True
    public_after_review = authed_client.get(
        "/api/pages/agent-guide",
        params={"language": "fr", "live_only": True},
    )
    assert public_after_review.status_code == 200, public_after_review.text

    _source(authed_client, "agent-delete")
    made_for_delete = authed_client.post(
        "/api/v1/mcp/translations/agent-delete",
        headers=headers,
        json={
            "language": "fr",
            "collection": "summer",
            "body": "Temporary",
        },
    )
    assert made_for_delete.status_code == 200, made_for_delete.text
    removed = authed_client.delete(
        "/api/v1/mcp/translations/agent-delete/fr?collection=summer",
        headers=headers,
    )
    assert removed.status_code == 200, removed.text

    open_run = authed_client.post(
        "/api/v1/mcp/i18n-runs",
        headers=headers,
        json={"mode": "translate", "target_languages": ["fr"]},
    )
    assert open_run.status_code == 200, open_run.text
    disabled = authed_client.put(
        "/api/v1/translations/config",
        json={
            "language": "en",
            "languages": [],
            "language_labels": {},
            "translation_automation_paused": False,
        },
    )
    assert disabled.status_code == 200, disabled.text
    finished_while_inactive = authed_client.post(
        "/api/v1/mcp/i18n-runs",
        headers=headers,
        json={
            "run_id": open_run.json()["run_id"],
            "run_status": "completed",
            "counts": {"created": 0},
        },
    )
    assert finished_while_inactive.status_code == 200, finished_while_inactive.text

    paused = authed_client.put(
        "/api/v1/translations/config",
        json={
            "language": "en",
            "languages": ["en", "fr"],
            "language_labels": {},
            "translation_automation_paused": True,
        },
    )
    assert paused.status_code == 200, paused.text
    blocked = authed_client.put(
        "/api/v1/mcp/pages/agent-guide",
        headers=headers,
        json={
            "language": "fr",
            "frontmatter": {"name": "Blocked", "category": "summer"},
            "body": "Blocked",
        },
    )
    assert blocked.status_code == 403

    _source(authed_client, "human-guide")
    human = authed_client.post(
        "/api/v1/content/collections/summer/entries/human-guide/translations",
        json={"language": "fr", "body": "Manuel"},
    )
    assert human.status_code == 201, human.text


def test_default_writes_reject_spoofed_provenance_and_stamp_actor(
    authed_client, slice6_site
):
    _, token = _agent(authed_client, "default-writer")
    headers = {"Authorization": f"Bearer {token}"}
    spoof = authed_client.put(
        "/api/v1/mcp/pages/spoof-default",
        headers=headers,
        json={
            "frontmatter": {
                "name": "Spoof",
                "category": "summer",
                "created_by": "human",
            },
            "body": "No",
        },
    )
    assert spoof.status_code == 400

    written = authed_client.put(
        "/api/v1/mcp/pages/actor-default",
        headers=headers,
        json={
            "frontmatter": {"name": "Actor", "category": "summer"},
            "body": "Yes",
        },
    )
    assert written.status_code == 200, written.text
    metadata = authed_client.get(
        "/api/v1/mcp/pages/actor-default/metadata", headers=headers
    )
    assert metadata.status_code == 200
    assert metadata.json()["frontmatter"]["created_by"] == "agent"
    assert metadata.json()["frontmatter"]["created_by_id"] == "default-writer"

    human_spoof = authed_client.put(
        "/api/v1/content/collections/summer/entries/human-spoof",
        json={
            "frontmatter": {
                "name": "Human spoof",
                "category": "summer",
                "reviewed_by": "someone-else",
            },
            "body": "No",
        },
    )
    assert human_spoof.status_code == 400


def test_pages_editor_rejects_provenance_spoofing_and_stamps_human(
    authed_client, slice6_site
):
    spoof = authed_client.post(
        "/api/pages/",
        json={
            "slug": "editor-spoof",
            "frontmatter": {
                "name": "Editor spoof",
                "category": "summer",
                "created_by": "agent",
            },
            "content": "No",
        },
    )
    assert spoof.status_code == 400

    created = authed_client.post(
        "/api/pages/",
        json={
            "slug": "editor-human",
            "frontmatter": {
                "name": "Editor human",
                "category": "summer",
                "status": "draft",
                "published": False,
            },
            "content": "Human",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["frontmatter"]["created_by"] == "human"
    assert created.json()["frontmatter"]["created_by_id"] == "testadmin"

    update_spoof = authed_client.put(
        "/api/pages/editor-human",
        json={
            "frontmatter": {
                "name": "Editor human",
                "category": "summer",
                "reviewed_by": "forged",
            },
            "content": "No",
        },
    )
    assert update_spoof.status_code == 400

    updated = authed_client.put(
        "/api/pages/editor-human",
        json={
            "frontmatter": {
                "name": "Editor human revised",
                "category": "summer",
                "status": "draft",
                "published": False,
            },
            "content": "Revised",
        },
    )
    assert updated.status_code == 200, updated.text
    metadata = updated.json()["frontmatter"]
    assert metadata["created_by_id"] == "testadmin"
    assert metadata["updated_by_id"] == "testadmin"


def test_v1_agent_scope_and_active_default_review_enforcement(
    authed_client, slice6_site
):
    from services.ai_settings_service import load_ai_settings, save_ai_settings

    read_key = authed_client.post(
        "/api/auth/keys",
        json={"name": "read-only-rest", "scopes": ["read"], "site_id": "default"},
    )
    assert read_key.status_code == 200, read_key.text
    denied = authed_client.put(
        "/api/v1/content/collections/summer/entries/denied",
        headers={"X-Pen-API-Key": read_key.json()["key"]},
        json={
            "frontmatter": {"name": "Denied", "category": "summer"},
            "body": "No",
        },
    )
    assert denied.status_code == 403

    draft = authed_client.put(
        "/api/v1/content/collections/summer/entries/live-source",
        json={
            "frontmatter": {
                "name": "Live Source",
                "category": "summer",
                "status": "draft",
                "published": False,
            },
            "body": "Draft",
        },
    )
    assert draft.status_code == 200, draft.text
    _, token = _agent(authed_client, "source-editor")
    headers = {"Authorization": f"Bearer {token}"}

    blocked = authed_client.put(
        "/api/v1/mcp/pages/live-source",
        headers=headers,
        json={
            "frontmatter": {
                "name": "Live Source",
                "category": "summer",
                "status": "published",
                "published": True,
            },
            "body": "Should not publish",
        },
    )
    assert blocked.status_code == 400, blocked.text
    assert "not allowed to set status" in blocked.json()["detail"]

    existing = load_ai_settings("default")
    save_ai_settings("default", {**existing, "ai_publish_autonomy": "autonomous"})
    try:
        published = authed_client.put(
            "/api/v1/mcp/pages/live-source",
            headers=headers,
            json={
                "frontmatter": {
                    "name": "Live Source Edited",
                    "category": "summer",
                    "status": "published",
                    "published": True,
                },
                "body": "Live edit",
            },
        )
        assert published.status_code == 200, published.text
        fm = frontmatter.load(slice6_site / "live-source" / "index.md")
        assert fm["status"] == "published"
        assert fm["published"] is True
        assert not fm.get("needs_review")
    finally:
        save_ai_settings("default", existing)


def test_mcp_translation_update_preserves_composite_partials(
    authed_client, slice6_site
):
    source = authed_client.put(
        "/api/v1/content/collections/summer/entries/composite",
        json={
            "frontmatter": {
                "name": "Composite",
                "category": "summer",
                "status": "draft",
                "published": False,
            },
            "body": "Source",
            "composite": True,
            "partials": {"bio": "Source bio"},
        },
    )
    assert source.status_code == 200, source.text
    _, token = _agent(authed_client, "composite-writer")
    headers = {"Authorization": f"Bearer {token}"}
    sibling = authed_client.post(
        "/api/v1/mcp/translations/composite",
        headers=headers,
        json={
            "language": "fr",
            "collection": "summer",
            "body": "Cible",
            "composite": True,
            "partials": {"bio": "Biographie"},
        },
    )
    assert sibling.status_code == 200, sibling.text

    updated = authed_client.put(
        "/api/v1/mcp/pages/composite",
        headers=headers,
        json={
            "language": "fr",
            "frontmatter": {"name": "Composite FR", "category": "summer"},
            "body": "Cible révisée",
        },
    )
    assert updated.status_code == 200, updated.text
    assert (slice6_site / "composite" / "fr" / "_bio.md").read_text() == "Biographie"

    human_update = authed_client.put(
        "/api/pages/composite?language=fr",
        json={
            "frontmatter": {
                "name": "Composite manuel",
                "category": "summer",
                "status": "draft",
                "published": False,
            },
            "content": "Révision manuelle",
        },
    )
    assert human_update.status_code == 200, human_update.text
    assert (slice6_site / "composite" / "fr" / "_bio.md").read_text() == "Biographie"


def test_exact_coverage_and_fallback_never_counts(
    authed_client, slice6_site
):
    _source(authed_client, "covered")
    _source(authed_client, "missing")
    created = authed_client.post(
        "/api/v1/content/collections/summer/entries/covered/translations",
        json={"language": "fr", "body": "Exact"},
    )
    assert created.status_code == 201, created.text

    coverage = authed_client.get("/api/v1/translations/coverage?language=fr")
    assert coverage.status_code == 200, coverage.text
    data = coverage.json()
    assert data["totals"] == {
        "eligible": 2,
        "existing": 1,
        "published": 0,
        "draft": 1,
        "needs_review": 0,
        "rejected": 0,
        "missing": 1,
    }
    rows = {row["slug"]: row for row in data["items"]}
    assert rows["missing"]["gap_codes"] == ["fr:missing"]

    # A merged list can return the default row, but coverage remains exact.
    merged = authed_client.get(
        "/api/v1/content/collections/summer/entries?language=fr&fallback=default"
    )
    assert merged.status_code == 200, merged.text
    assert any(
        item["slug"] == "missing" and item["is_fallback"] is True
        for item in merged.json()["items"]
    )
    again = authed_client.get("/api/v1/translations/coverage?language=fr")
    assert again.json()["totals"]["existing"] == 1


def test_run_telemetry_is_bounded_body_free_and_pause_blocks_start(
    authed_client, slice6_site, temp_data_root, monkeypatch
):
    import services.i18n_run_service as runs

    monkeypatch.setattr(runs, "MAX_RUN_RECORDS", 2)
    _, token = _agent(authed_client, "run-reporter")
    headers = {"Authorization": f"Bearer {token}"}
    run_ids = []
    for _ in range(3):
        started = authed_client.post(
            "/api/v1/mcp/i18n-runs",
            headers=headers,
            json={"mode": "translate", "target_languages": ["fr"]},
        )
        assert started.status_code == 200, started.text
        run_id = started.json()["run_id"]
        run_ids.append(run_id)
        finished = authed_client.post(
            "/api/v1/mcp/i18n-runs",
            headers=headers,
            json={
                "run_id": run_id,
                "run_status": "completed",
                "counts": {"created": 1},
                "error": (
                    "this deliberately long translated body shaped message must "
                    "never be retained in operational telemetry or logs"
                ),
            },
        )
        assert finished.status_code == 200, finished.text

    path = temp_data_root / "data" / "i18n-runs" / "default.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    records = [json.loads(line) for line in lines]
    assert all("body" not in record and "content" not in record for record in records)
    assert all("translated body shaped" not in json.dumps(record) for record in records)
    assert all(
        record["error"] == "[redacted external error; see caller logs]"
        for record in records
    )
    assert run_ids[0] not in {record["run_id"] for record in records}

    paused = authed_client.patch(
        "/api/sites/default", json={"translation_automation_paused": True}
    )
    assert paused.status_code == 200
    blocked = authed_client.post(
        "/api/v1/mcp/i18n-runs",
        headers=headers,
        json={"mode": "translate"},
    )
    assert blocked.status_code == 403


def test_raw_key_site_binding_and_inactive_gate(
    authed_client, slice6_site
):
    from services.site_service import create_site, update_site

    create_site("other", "Other")
    update_site("other", language="en", languages=["en", "fr"])
    _source(authed_client, "default-only")
    raw, _ = _agent(authed_client, "rest-site-key", "default")

    response = authed_client.get(
        "/api/v1/translations/coverage",
        headers={"X-Pen-API-Key": raw, "X-Pen-Site-Id": "other"},
    )
    assert response.status_code == 200, response.text
    assert {row["slug"] for row in response.json()["items"]} == {"default-only"}

    other_write = authed_client.put(
        "/api/v1/content/collections/summer/entries/other-only",
        headers={"X-Pen-Site-Id": "other"},
        json={
            "frontmatter": {"name": "Other only", "category": "summer"},
            "body": "Other",
        },
    )
    assert other_write.status_code == 200, other_write.text
    _, default_token = _agent(authed_client, "page-read-default", "default")
    cross_site = authed_client.get(
        "/api/pages/other-only",
        headers={
            "Authorization": f"Bearer {default_token}",
            "X-Pen-Site-Id": "other",
        },
    )
    assert cross_site.status_code == 404

    disabled = authed_client.put(
        "/api/v1/translations/config",
        json={
            "language": "en",
            "languages": [],
            "language_labels": {},
            "translation_automation_paused": False,
        },
    )
    assert disabled.status_code == 200
    monolingual = authed_client.put(
        "/api/v1/content/collections/summer/entries/mono",
        json={
            "frontmatter": {"name": "Mono", "category": "summer"},
            "body": "Legacy shape",
        },
    )
    assert monolingual.status_code == 200, monolingual.text
    mono_json = monolingual.json()
    assert mono_json["message"] == "Entry saved successfully"
    assert mono_json.get("version")
    assert "entry" not in mono_json
    mono_fm = frontmatter.load(slice6_site / "mono" / "index.md")
    assert "created_by_id" not in mono_fm.metadata
    inactive = authed_client.post(
        "/api/v1/content/collections/summer/entries/default-only/translations",
        json={"language": "fr", "body": "No"},
    )
    assert inactive.status_code == 400


def test_agent_sibling_publish_honors_autonomy(authed_client, slice6_site):
    from services.ai_settings_service import load_ai_settings, save_ai_settings

    _source(authed_client, "auton-sib")
    _, token = _agent(authed_client, "auton-localizer")
    headers = {"Authorization": f"Bearer {token}"}

    blocked = authed_client.post(
        "/api/v1/mcp/translations/auton-sib",
        headers=headers,
        json={
            "language": "fr",
            "collection": "summer",
            "frontmatter": {
                "name": "Auton",
                "category": "summer",
                "status": "published",
                "published": True,
            },
            "body": "Non",
        },
    )
    assert blocked.status_code == 400, blocked.text
    assert "not allowed to set status" in blocked.json()["detail"]
    assert not (slice6_site / "auton-sib" / "fr" / "index.md").exists()

    existing = load_ai_settings("default")
    save_ai_settings("default", {**existing, "ai_publish_autonomy": "autonomous"})
    try:
        created = authed_client.post(
            "/api/v1/mcp/translations/auton-sib",
            headers=headers,
            json={
                "language": "fr",
                "collection": "summer",
                "frontmatter": {
                    "name": "Auton",
                    "category": "summer",
                    "status": "published",
                    "published": True,
                },
                "body": "Oui",
            },
        )
        assert created.status_code == 200, created.text
        fm = created.json()["entry"]["frontmatter"]
        assert fm["status"] == "published"
        assert fm["published"] is True
        assert created.json()["entry"]["provenance"]["needs_review"] is False

        updated = authed_client.put(
            "/api/v1/mcp/pages/auton-sib",
            headers=headers,
            json={
                "language": "fr",
                "frontmatter": {"name": "Auton révisé", "category": "summer"},
                "body": "Oui, révisé",
            },
        )
        assert updated.status_code == 200, updated.text
        sibling = frontmatter.load(slice6_site / "auton-sib" / "fr" / "index.md")
        assert sibling["status"] == "published"
        assert sibling["published"] is True
        assert sibling.content.strip() == "Oui, révisé"
        assert not sibling.get("needs_review")
    finally:
        save_ai_settings("default", existing)


def test_openapi_slice6_contracts():
    import yaml

    spec = yaml.safe_load(
        (
            Path(__file__).resolve().parents[2] / "core" / "openapi.yaml"
        ).read_text(encoding="utf-8")
    )
    paths = spec["paths"]
    assert "post" in paths[
        "/content/collections/{collection}/entries/{slug}/translations"
    ]
    assert "put" in paths["/content/collections/{collection}/entries/{slug}"]
    assert "delete" in paths["/content/collections/{collection}/entries/{slug}"]
    assert "get" in paths["/translations/coverage"]
    assert "post" in paths["/translations/{slug}/{language}/review"]
    assert "post" in paths["/translations/runs"]
    assert "get" in paths["/mcp/translations/config"]
    assert "get" in paths["/mcp/translations/gaps"]
    assert "post" in paths["/mcp/translations/{slug}"]
    assert "delete" in paths["/mcp/translations/{slug}/{language}"]
    assert "post" in paths["/mcp/i18n-runs"]
    delete_parameters = paths[
        "/content/collections/{collection}/entries/{slug}"
    ]["delete"]["parameters"]
    assert any(parameter.get("name") == "delete_group" for parameter in delete_parameters)
    schemas = spec["components"]["schemas"]
    for name in (
        "ContentProvenance",
        "TranslationCoverageResponse",
        "TranslationRun",
    ):
        assert name in schemas
    assert "review_note" in schemas["ContentProvenance"]["properties"]
    assert set(
        schemas["TranslationConfigUpdate"]["allOf"][1]["required"]
    ) == {
        "language",
        "languages",
        "language_labels",
        "translation_automation_paused",
    }
