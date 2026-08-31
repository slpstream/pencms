"""Slice 7 admin translation contracts and file-backed UI strings."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import frontmatter
import pytest


@pytest.fixture
def slice7_site(authed_client, temp_data_root: Path, monkeypatch):
    from services.cache_service import get_db_connection, init_db
    from services.site_service import ensure_sites_initialized
    import services.ui_strings_service as ui_strings

    sites_yaml = temp_data_root / "data" / "sites.yaml"
    if sites_yaml.exists():
        sites_yaml.unlink()
    sites_root = temp_data_root / "content" / "sites"
    if sites_root.exists():
        shutil.rmtree(sites_root)
    ensure_sites_initialized()
    init_db()
    with get_db_connection() as conn:
        conn.execute("DELETE FROM entries")
        conn.execute("INSERT INTO entries_fts(entries_fts) VALUES('rebuild')")
        conn.commit()

    theme = temp_data_root / "slice7-theme"
    theme.mkdir(exist_ok=True)
    (theme / "strings.json").write_text(
        json.dumps(
            {
                "home": "Theme home",
                "themeOnly": "Theme only",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(ui_strings, "resolve_theme_dir", lambda _site_id: theme)
    return temp_data_root / "content" / "sites"


def _activate(client, site_id: str = "default", paused: bool = False):
    response = client.patch(
        f"/api/sites/{site_id}",
        json={
            "language": "en",
            "languages": ["en", "fr"],
            "translation_automation_paused": paused,
        },
    )
    assert response.status_code == 200, response.text


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
                "taxonomy_seasons": "summer",
            },
            "body": "English",
        },
    )
    assert response.status_code == 200, response.text


def _agent_token(client, name: str = "slice7-agent") -> str:
    created = client.post(
        "/api/auth/keys",
        json={"name": name, "scopes": ["read", "write"], "site_id": "default"},
    )
    assert created.status_code == 200, created.text
    token = client.post(
        "/api/auth/token",
        json={"agent_key": created.json()["key"]},
    )
    assert token.status_code == 200, token.text
    return token.json()["access_token"]


def test_ui_string_layers_sparse_reset_and_disk_authority(
    authed_client, slice7_site
):
    _activate(authed_client)
    site = slice7_site / "default"
    strings = site / "strings"
    strings.mkdir()
    (strings / "en.json").write_text(
        '{"home":"Site home","defaultOnly":"Default only"}\n',
        encoding="utf-8",
    )
    (strings / "fr.json").write_text(
        '{"home":"Accueil","search":"Chercher"}\n',
        encoding="utf-8",
    )

    response = authed_client.get("/api/v1/translations/strings?language=fr")
    assert response.status_code == 200, response.text
    bundle = response.json()
    assert bundle["language"] == "fr"
    assert bundle["strings"]["home"] == {
        "effective": "Accueil",
        "source": "site_target",
        "override": "Accueil",
    }
    assert bundle["strings"]["themeOnly"]["source"] == "theme"
    assert bundle["strings"]["defaultOnly"]["source"] == "site_default"
    assert bundle["strings"]["archive"]["source"] == "engine"

    saved = authed_client.put(
        "/api/v1/translations/strings?language=fr",
        json={"overrides": {"search": "Recherche", "newChrome": "Nouveau"}},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["strings"]["home"]["effective"] == "Site home"
    assert saved.json()["strings"]["home"]["source"] == "site_default"
    assert saved.json()["strings"]["search"]["effective"] == "Recherche"
    assert json.loads((strings / "fr.json").read_text(encoding="utf-8")) == {
        "newChrome": "Nouveau",
        "search": "Recherche",
    }

    reset = authed_client.put(
        "/api/v1/translations/strings?language=fr",
        json={"overrides": {}},
    )
    assert reset.status_code == 200, reset.text
    assert not (strings / "fr.json").exists()
    assert reset.json()["strings"]["search"]["source"] == "engine"

    invalid = authed_client.put(
        "/api/v1/translations/strings?language=fr",
        json={"overrides": {"bad key": "No"}},
    )
    assert invalid.status_code == 400
    assert "valid identifier" in invalid.json()["detail"]


def test_inactive_gate_monolingual_read_and_agent_write_denial(
    authed_client, slice7_site
):
    site = slice7_site / "default"
    strings = site / "strings"
    strings.mkdir()
    (strings / "en.json").write_text('{"home":"Ignored while inactive"}')

    inactive = authed_client.get("/api/v1/translations/strings")
    assert inactive.status_code == 200, inactive.text
    assert inactive.json()["config"]["i18n_active"] is False
    assert inactive.json()["strings"]["home"]["source"] == "engine"

    denied = authed_client.put(
        "/api/v1/translations/strings?language=en",
        json={"overrides": {"home": "No"}},
    )
    assert denied.status_code == 400
    assert "inactive" in denied.json()["detail"].lower()

    _activate(authed_client)
    token = _agent_token(authed_client)
    agent_denied = authed_client.put(
        "/api/v1/translations/strings?language=fr",
        headers={"Authorization": f"Bearer {token}"},
        json={"overrides": {"home": "Agent"}},
    )
    assert agent_denied.status_code == 403
    assert "human admin" in agent_denied.json()["detail"].lower()


def test_coverage_collection_manual_review_pause_and_identity(
    authed_client, slice7_site
):
    _activate(authed_client, paused=True)
    _source(authed_client, "guide")

    coverage = authed_client.get("/api/v1/translations/coverage?language=fr")
    assert coverage.status_code == 200, coverage.text
    row = coverage.json()["items"][0]
    assert row["slug"] == "guide"
    assert row["collection"] == "summer"
    assert row["gap_codes"] == ["fr:missing"]

    # Pause applies to agents, never the manual admin door.
    created = authed_client.post(
        "/api/v1/content/collections/summer/entries/guide/translations",
        json={"language": "fr"},
    )
    assert created.status_code == 201, created.text
    target = frontmatter.load(
        slice7_site / "default" / "guide" / "fr" / "index.md"
    )
    source = frontmatter.load(slice7_site / "default" / "guide" / "index.md")
    assert target.content == ""
    assert target["status"] == "draft"
    assert target["category"] == source["category"]
    assert target["taxonomy_seasons"] == source["taxonomy_seasons"]
    assert target["translation_group"] == source["translation_group"]

    approved = authed_client.post(
        "/api/v1/translations/guide/fr/review",
        json={"decision": "approve"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["entry"]["frontmatter"]["status"] == "published"
    assert approved.json()["entry"]["frontmatter"]["published"] is True

    rejected = authed_client.post(
        "/api/v1/translations/guide/fr/review",
        json={"decision": "reject"},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["entry"]["frontmatter"]["review_decision"] == "rejected"

    token = _agent_token(authed_client, "paused-slice7")
    blocked = authed_client.put(
        "/api/v1/content/collections/summer/entries/guide?language=fr",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "frontmatter": {"name": "Blocked", "category": "summer"},
            "body": "Blocked",
        },
    )
    assert blocked.status_code == 403


def test_ui_strings_are_multisite_isolated(authed_client, slice7_site):
    from services.site_service import create_site, update_site

    _activate(authed_client)
    create_site("other", "Other")
    update_site("other", language="en", languages=["en", "fr"])

    other = authed_client.put(
        "/api/v1/translations/strings?language=fr",
        headers={"X-Pen-Site-Id": "other"},
        json={"overrides": {"home": "Autre"}},
    )
    assert other.status_code == 200, other.text
    assert other.json()["strings"]["home"]["effective"] == "Autre"

    default = authed_client.get(
        "/api/v1/translations/strings?language=fr",
        headers={"X-Pen-Site-Id": "default"},
    )
    assert default.status_code == 200, default.text
    assert default.json()["strings"]["home"]["effective"] != "Autre"
    assert (slice7_site / "other" / "strings" / "fr.json").exists()
    assert not (slice7_site / "default" / "strings" / "fr.json").exists()


def test_openapi_slice7_admin_contracts():
    import yaml

    spec = yaml.safe_load(
        (
            Path(__file__).resolve().parents[2] / "core" / "openapi.yaml"
        ).read_text(encoding="utf-8")
    )
    paths = spec["paths"]
    assert {"get", "put"}.issubset(paths["/translations/strings"])
    coverage = spec["components"]["schemas"]["TranslationCoverageItem"]
    assert "collection" in coverage["required"]
    assert "UiStringBundle" in spec["components"]["schemas"]
    assert "UiStringOverrides" in spec["components"]["schemas"]
