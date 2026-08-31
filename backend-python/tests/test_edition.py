"""Phase 0 edition seam — overlay presence, not a config flag."""

from __future__ import annotations

import pytest


def test_config_reports_core_edition(client):
    resp = client.get("/api/config")
    assert resp.status_code == 200, resp.text
    assert resp.json()["edition"] == "core"


def test_session_reports_core_edition(authed_client):
    resp = authed_client.get("/api/auth/me")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["edition"] == "core"


def test_login_payload_includes_edition(authed_client):
    # authed_client already logged in; login again to see the login shape.
    resp = authed_client.post(
        "/api/auth/login",
        json={"username": "testadmin", "password": "testpass123"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["edition"] == "core"


def test_core_publish_catalog_is_sftp_and_github_pages():
    from services.publish_providers import list_providers

    catalog = list_providers()
    ids = [p["id"] for p in catalog]
    assert ids == ["sftp", "github_pages"]


def test_core_storage_types_are_local_and_git():
    from services.storage_registry import list_storage_types

    assert list_storage_types() == ["local", "git"]


def test_set_edition_rejects_unknown():
    from services.edition import get_edition, set_edition

    previous = get_edition()
    try:
        with pytest.raises(ValueError, match="edition must be"):
            set_edition("enterprise")
        assert get_edition() == previous
    finally:
        set_edition(previous)


def test_register_publish_provider_replaces_by_id():
    from services.publish_providers.base import PublishProvider
    from services.publish_providers.registry import (
        _CATALOG,
        get_provider,
        register_publish_provider,
    )

    snapshot = list(_CATALOG)

    class _StubProvider(PublishProvider):
        id = "sftp"
        label = "SFTP stub"
        enabled = True

        async def test(self):
            return {"success": True}

        async def deploy(self, dist_dir, *, force_full, upload_rels, removed, total_files, log_line, set_phase=None):
            return None

        def capabilities(self):
            return {"incremental": False, "auth_methods": ["password"]}

    try:
        register_publish_provider(_StubProvider)
        assert get_provider("sftp").label == "SFTP stub"
    finally:
        _CATALOG[:] = snapshot
        assert get_provider("sftp").id == "sftp"
        assert get_provider("sftp").label != "SFTP stub"
