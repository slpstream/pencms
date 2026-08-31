"""Slice 10 optional localization policy and external-run integration."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import frontmatter
import pytest


@pytest.fixture
def slice10_site(authed_client, temp_data_root: Path):
    from services.cache_service import get_db_connection, init_db
    from services.site_service import ensure_sites_initialized

    for path in (
        temp_data_root / "data" / "sites.yaml",
        temp_data_root / "data" / "ai-settings",
        temp_data_root / "data" / "i18n-runs",
        temp_data_root / "content" / "sites",
    ):
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    ensure_sites_initialized()
    init_db()
    with get_db_connection() as conn:
        conn.execute("DELETE FROM entries")
        conn.execute("INSERT INTO entries_fts(entries_fts) VALUES('rebuild')")
        conn.commit()
    response = authed_client.patch(
        "/api/sites/default",
        json={"language": "en", "languages": ["en", "fr", "sr-latn"]},
    )
    assert response.status_code == 200, response.text
    return temp_data_root


def _agent(
    client, name: str, *, site_id: str = "default", scopes: list[str] | None = None
):
    created = client.post(
        "/api/auth/keys",
        json={
            "name": name,
            "scopes": scopes or ["read", "write"],
            "site_id": site_id,
        },
    )
    assert created.status_code == 200, created.text
    data = created.json()
    token = client.post("/api/auth/token", json={"agent_key": data["key"]})
    assert token.status_code == 200, token.text
    data["token"] = token.json()["access_token"]
    return data


def _policy(
    key_id: str,
    *,
    operation: str = "translate",
    model: str = "provider/localizer-v1",
    review_policy: str = "require_review",
    language: str = "fr",
):
    return {
        "enabled": True,
        "targets": {
            language: {
                "operation": operation,
                "model": model,
                "agent_key_id": key_id,
                "review_policy": review_policy,
            }
        },
    }


def _save_config(client, policy, *, site_id: str = "default", languages=None):
    return client.put(
        "/api/v1/translations/config",
        headers={"X-Pen-Site-Id": site_id},
        json={
            "language": "en",
            "languages": languages or ["en", "fr", "sr-latn"],
            "language_labels": {},
            "translation_automation_paused": False,
            "automation_policy": policy,
        },
    )


def _source(client, slug: str, *, site_id: str = "default"):
    response = client.put(
        f"/api/v1/content/collections/summer/entries/{slug}",
        headers={"X-Pen-Site-Id": site_id},
        json={
            "frontmatter": {
                "name": slug.title(),
                "category": "summer",
                "status": "draft",
                "published": False,
            },
            "body": "Source",
        },
    )
    assert response.status_code == 200, response.text


def test_policy_defaults_validation_and_non_secret_disk_storage(
    authed_client, slice10_site
):
    default = authed_client.get("/api/v1/translations/config")
    assert default.status_code == 200, default.text
    assert default.json()["automation_policy"] == {
        "enabled": False,
        "targets": {},
        "policy_valid": True,
        "policy_error": None,
    }
    wrong_surface = authed_client.put(
        "/api/ai/settings",
        json={"i18n_localization_policy": {"enabled": False, "targets": {}}},
    )
    assert wrong_surface.status_code == 400
    assert "/api/v1/translations/config" in wrong_surface.json()["detail"]

    writer = _agent(authed_client, "policy-writer")
    bad_operation = _save_config(
        authed_client, _policy(writer["key_id"], operation="summarize")
    )
    assert bad_operation.status_code == 400
    assert "operation" in bad_operation.json()["detail"].lower()

    bad_target = _save_config(
        authed_client,
        _policy(writer["key_id"], language="de"),
    )
    assert bad_target.status_code == 400
    assert "configured non-default" in bad_target.json()["detail"]

    read_only = _agent(
        authed_client, "policy-reader", scopes=["read"]
    )
    bad_scope = _save_config(authed_client, _policy(read_only["key_id"]))
    assert bad_scope.status_code == 400
    assert "write" in bad_scope.json()["detail"]

    saved = _save_config(
        authed_client,
        _policy(
            writer["key_id"],
            operation="translate_then_transliterate",
            review_policy="allow_unreviewed_draft",
        ),
    )
    assert saved.status_code == 200, saved.text
    target = saved.json()["automation_policy"]["targets"]["fr"]
    assert target["operation"] == "translate_then_transliterate"
    assert target["agent_key_name"] == "policy-writer"
    assert target["binding_valid"] is True

    stored_path = (
        slice10_site / "data" / "ai-settings" / "default.json"
    )
    stored = json.loads(stored_path.read_text(encoding="utf-8"))
    assert stored["i18n_localization_policy"]["targets"]["fr"]["agent_key_id"] == writer[
        "key_id"
    ]
    serialized = json.dumps(stored)
    assert writer["key"] not in serialized
    assert "apiKey" not in serialized


def test_policy_selects_run_snapshot_and_controls_review_provenance(
    authed_client, slice10_site
):
    writer = _agent(authed_client, "nightly-localizer")
    saved = _save_config(
        authed_client,
        _policy(
            writer["key_id"],
            operation="translate_then_transliterate",
            model="provider/script-aware-v2",
            review_policy="allow_unreviewed_draft",
        ),
    )
    assert saved.status_code == 200, saved.text
    _source(authed_client, "planned")
    headers = {"Authorization": f"Bearer {writer['token']}"}

    mismatch = authed_client.post(
        "/api/v1/mcp/i18n-runs",
        headers=headers,
        json={"mode": "translate", "target_languages": ["fr"]},
    )
    assert mismatch.status_code == 400
    assert "does not match" in mismatch.json()["detail"]

    started = authed_client.post(
        "/api/v1/mcp/i18n-runs",
        headers=headers,
        json={
            "mode": "translate_then_transliterate",
            "target_languages": ["fr"],
        },
    )
    assert started.status_code == 200, started.text
    run = started.json()
    assert run["policy_applied"] is True
    assert run["model"] == "provider/script-aware-v2"
    assert run["agent_key_id"] == writer["key_id"]
    assert run["agent_key_name"] == "nightly-localizer"
    assert run["review_policy"] == "allow_unreviewed_draft"

    created = authed_client.post(
        "/api/v1/mcp/translations/planned",
        headers=headers,
        json={
            "language": "fr",
            "collection": "summer",
            "body": "Résultat externe",
            "run_id": run["run_id"],
        },
    )
    assert created.status_code == 200, created.text
    provenance = created.json()["entry"]["provenance"]
    assert provenance["created_by"] == "agent"
    assert provenance["created_by_id"] == "nightly-localizer"
    assert provenance["run_id"] == run["run_id"]
    assert provenance["needs_review"] is False
    assert created.json()["entry"]["frontmatter"]["status"] == "draft"
    assert created.json()["entry"]["frontmatter"]["published"] is False

    _source(authed_client, "planned-live")
    blocked_publish = authed_client.post(
        "/api/v1/mcp/translations/planned-live",
        headers=headers,
        json={
            "language": "fr",
            "collection": "summer",
            "frontmatter": {
                "name": "Planned Live",
                "category": "summer",
                "status": "published",
                "published": True,
            },
            "body": "Toujours brouillon",
            "run_id": run["run_id"],
        },
    )
    assert blocked_publish.status_code == 400, blocked_publish.text
    assert "not allowed to set status" in blocked_publish.json()["detail"]

    from services.ai_settings_service import load_ai_settings, save_ai_settings

    existing = load_ai_settings("default")
    save_ai_settings("default", {**existing, "ai_publish_autonomy": "autonomous"})
    try:
        live = authed_client.post(
            "/api/v1/mcp/translations/planned-live",
            headers=headers,
            json={
                "language": "fr",
                "collection": "summer",
                "frontmatter": {
                    "name": "Planned Live",
                    "category": "summer",
                    "status": "published",
                    "published": True,
                },
                "body": "En ligne",
                "run_id": run["run_id"],
            },
        )
        assert live.status_code == 200, live.text
        live_fm = live.json()["entry"]["frontmatter"]
        assert live_fm["status"] == "published"
        assert live_fm["published"] is True
        assert live.json()["entry"]["provenance"]["needs_review"] is False
    finally:
        save_ai_settings("default", existing)

    finished = authed_client.post(
        "/api/v1/mcp/i18n-runs",
        headers=headers,
        json={
            "run_id": run["run_id"],
            "run_status": "completed",
            "counts": {"discovered": 1, "attempted": 1, "created": 1},
        },
    )
    assert finished.status_code == 200, finished.text
    assert finished.json()["status"] == "completed"
    coverage = authed_client.get("/api/v1/translations/coverage?language=fr")
    totals = coverage.json()["totals"]
    assert totals["existing"] == 2

    log = (
        slice10_site / "data" / "i18n-runs" / "default.jsonl"
    ).read_text(encoding="utf-8")
    assert "provider/script-aware-v2" in log
    assert writer["key"] not in log
    assert "Résultat externe" not in log


def test_pause_revocation_and_manual_ai_disabled_compatibility(
    authed_client, slice10_site
):
    writer = _agent(authed_client, "revocable-localizer")
    assert _save_config(
        authed_client, _policy(writer["key_id"])
    ).status_code == 200
    _source(authed_client, "agent-blocked")
    headers = {"Authorization": f"Bearer {writer['token']}"}

    started = authed_client.post(
        "/api/v1/mcp/i18n-runs",
        headers=headers,
        json={"mode": "translate", "target_languages": ["fr"]},
    )
    assert started.status_code == 200, started.text

    keys = authed_client.get("/api/auth/keys").json()["keys"]
    key_index = next(key["id"] for key in keys if key["key_id"] == writer["key_id"])
    revoked = authed_client.delete(f"/api/auth/keys/{key_index}")
    assert revoked.status_code == 200

    effective = authed_client.get("/api/v1/translations/config").json()
    assert effective["automation_policy"]["targets"]["fr"]["binding_valid"] is False
    assert (
        effective["automation_policy"]["targets"]["fr"]["binding_error"]
        == "missing_or_revoked"
    )
    unrelated_ai_save = authed_client.put(
        "/api/ai/settings",
        json={"text_generation_prompt": "Keep the existing localization policy."},
    )
    assert unrelated_ai_save.status_code == 200, unrelated_ai_save.text
    denied_write = authed_client.post(
        "/api/v1/mcp/translations/agent-blocked",
        headers=headers,
        json={"language": "fr", "collection": "summer", "body": "No"},
    )
    assert denied_write.status_code == 403
    assert "revoked" in denied_write.json()["detail"].lower()
    denied_run = authed_client.post(
        "/api/v1/mcp/i18n-runs",
        headers=headers,
        json={"mode": "translate", "target_languages": ["fr"]},
    )
    assert denied_run.status_code == 403

    # Reporting can close an already-started record; it cannot write content.
    finish = authed_client.post(
        "/api/v1/mcp/i18n-runs",
        headers=headers,
        json={"run_id": started.json()["run_id"], "run_status": "cancelled"},
    )
    assert finish.status_code == 200, finish.text

    paused = authed_client.patch(
        "/api/sites/default", json={"translation_automation_paused": True}
    )
    assert paused.status_code == 200
    _source(authed_client, "manual-still-works")
    manual = authed_client.post(
        "/api/v1/content/collections/summer/entries/manual-still-works/translations",
        json={"language": "fr", "body": "Écrit à la main"},
    )
    assert manual.status_code == 201, manual.text
    fm = frontmatter.load(
        slice10_site
        / "content"
        / "sites"
        / "default"
        / "manual-still-works"
        / "fr"
        / "index.md"
    )
    assert fm["created_by"] == "human"
    assert fm["needs_review"] is False


def test_policy_and_run_binding_are_multisite_isolated(
    authed_client, slice10_site
):
    from services.site_service import create_site, update_site

    create_site("other", "Other")
    update_site("other", language="en", languages=["en", "fr"])
    default_key = _agent(authed_client, "default-localizer")
    other_key = _agent(authed_client, "other-localizer", site_id="other")

    default_saved = _save_config(
        authed_client,
        _policy(default_key["key_id"], model="model/default"),
    )
    assert default_saved.status_code == 200, default_saved.text
    other_saved = _save_config(
        authed_client,
        _policy(other_key["key_id"], model="model/other"),
        site_id="other",
        languages=["en", "fr"],
    )
    assert other_saved.status_code == 200, other_saved.text

    default_config = authed_client.get(
        "/api/v1/translations/config",
        headers={"X-Pen-Site-Id": "default"},
    ).json()
    other_config = authed_client.get(
        "/api/v1/translations/config",
        headers={"X-Pen-Site-Id": "other"},
    ).json()
    assert default_config["automation_policy"]["targets"]["fr"]["model"] == "model/default"
    assert other_config["automation_policy"]["targets"]["fr"]["model"] == "model/other"

    cross_site = authed_client.post(
        "/api/v1/mcp/i18n-runs",
        headers={
            "Authorization": f"Bearer {default_key['token']}",
            "X-Pen-Site-Id": "other",
        },
        json={"mode": "translate", "target_languages": ["fr"]},
    )
    assert cross_site.status_code == 200, cross_site.text
    assert cross_site.json()["site_id"] == "default"
    assert cross_site.json()["model"] == "model/default"


def test_enabled_policy_requires_bound_run_for_agent_sibling_writes(
    authed_client, slice10_site
):
    writer = _agent(authed_client, "bound-localizer")
    unbound = _agent(authed_client, "unbound-localizer")
    assert _save_config(
        authed_client, _policy(writer["key_id"])
    ).status_code == 200
    _source(authed_client, "policy-guarded")

    unbound_write = authed_client.post(
        "/api/v1/mcp/translations/policy-guarded",
        headers={"Authorization": f"Bearer {unbound['token']}"},
        json={
            "language": "fr",
            "collection": "summer",
            "body": "Unbound",
        },
    )
    assert unbound_write.status_code == 403
    assert "bound" in unbound_write.json()["detail"].lower()

    runless_write = authed_client.post(
        "/api/v1/mcp/translations/policy-guarded",
        headers={"Authorization": f"Bearer {writer['token']}"},
        json={
            "language": "fr",
            "collection": "summer",
            "body": "No run",
        },
    )
    assert runless_write.status_code == 403
    assert "run" in runless_write.json()["detail"].lower()

    started = authed_client.post(
        "/api/v1/mcp/i18n-runs",
        headers={"Authorization": f"Bearer {writer['token']}"},
        json={"mode": "translate", "target_languages": ["fr"]},
    )
    assert started.status_code == 200, started.text
    created = authed_client.post(
        "/api/v1/mcp/translations/policy-guarded",
        headers={"Authorization": f"Bearer {writer['token']}"},
        json={
            "language": "fr",
            "collection": "summer",
            "body": "Bound run",
            "run_id": started.json()["run_id"],
        },
    )
    assert created.status_code == 200, created.text

    runless_update = authed_client.put(
        "/api/v1/content/collections/summer/entries/policy-guarded?language=fr",
        headers={"Authorization": f"Bearer {writer['token']}"},
        json={
            "frontmatter": {"name": "Runless update", "category": "summer"},
            "body": "No run",
        },
    )
    assert runless_update.status_code == 403

    bound_update = authed_client.put(
        "/api/v1/content/collections/summer/entries/policy-guarded?language=fr",
        headers={"Authorization": f"Bearer {writer['token']}"},
        json={
            "frontmatter": {"name": "Bound update", "category": "summer"},
            "body": "Updated through REST",
            "run_id": started.json()["run_id"],
        },
    )
    assert bound_update.status_code == 200, bound_update.text

    unbound_delete = authed_client.delete(
        "/api/v1/mcp/translations/policy-guarded/fr?collection=summer",
        headers={"Authorization": f"Bearer {unbound['token']}"},
    )
    assert unbound_delete.status_code == 403
    assert "bound" in unbound_delete.json()["detail"].lower()

    bound_delete = authed_client.delete(
        "/api/v1/mcp/translations/policy-guarded/fr?collection=summer",
        headers={"Authorization": f"Bearer {writer['token']}"},
    )
    assert bound_delete.status_code == 200, bound_delete.text


def test_disabled_policy_preserves_legacy_agent_and_manual_workflows(
    authed_client, slice10_site
):
    writer = _agent(authed_client, "legacy-localizer")
    disabled = _save_config(
        authed_client,
        {"enabled": False, "targets": {}},
    )
    assert disabled.status_code == 200, disabled.text
    _source(authed_client, "legacy-agent")

    headers = {"Authorization": f"Bearer {writer['token']}"}
    run = authed_client.post(
        "/api/v1/mcp/i18n-runs",
        headers=headers,
        json={"mode": "transliterate", "target_languages": ["sr-latn"]},
    )
    assert run.status_code == 200, run.text
    assert run.json()["policy_applied"] is False
    assert run.json()["model"] is None
    assert run.json()["review_policy"] == "require_review"

    agent = authed_client.post(
        "/api/v1/mcp/translations/legacy-agent",
        headers=headers,
        json={
            "language": "sr-latn",
            "collection": "summer",
            "body": "Spoljni nacrt",
            "run_id": run.json()["run_id"],
        },
    )
    assert agent.status_code == 200, agent.text
    assert agent.json()["entry"]["provenance"]["needs_review"] is True

    _source(authed_client, "manual-no-ai")
    manual = authed_client.post(
        "/api/v1/content/collections/summer/entries/manual-no-ai/translations",
        json={"language": "fr", "body": "Manuel"},
    )
    assert manual.status_code == 201, manual.text


def test_openapi_slice10_policy_and_run_snapshot_contracts():
    import yaml

    spec = yaml.safe_load(
        (
            Path(__file__).resolve().parents[2] / "core" / "openapi.yaml"
        ).read_text(encoding="utf-8")
    )
    schemas = spec["components"]["schemas"]
    assert schemas["TranslationConfigUpdate"]["allOf"][1]["properties"][
        "automation_policy"
    ]["$ref"].endswith("/LocalizationAutomationPolicy")
    target = schemas["LocalizationTargetPolicy"]["properties"]
    assert target["operation"]["enum"] == [
        "translate",
        "transliterate",
        "translate_then_transliterate",
    ]
    assert target["review_policy"]["enum"] == [
        "require_review",
        "allow_unreviewed_draft",
    ]
    assert schemas["EntryDetail"]["properties"]["run_id"]["writeOnly"] is True
    run = schemas["TranslationRun"]
    assert {"policy_applied", "review_policy"}.issubset(run["required"])
    assert {"model", "agent_key_id", "agent_key_name"}.issubset(run["properties"])


def test_root_and_served_discovery_document_external_only_localization():
    repo = Path(__file__).resolve().parents[2]
    for path in (repo / "llms.txt", repo / "core" / "docs" / "llms.txt"):
        text = path.read_text(encoding="utf-8")
        assert "Translation automation (external only)" in text
        assert "does not execute a model" in text
        assert "active bound run_id" in text
        assert "Agent writes honor `ai_publish_autonomy`" in text
        assert "Human Approve publishes" in text
