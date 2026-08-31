"""Phase 5: sites CRUD routes are unmounted on a Core boot."""

from __future__ import annotations


def test_config_edition_is_core(client):
    resp = client.get("/api/config")
    assert resp.status_code == 200, resp.text
    assert resp.json()["edition"] == "core"


def test_sites_create_unmounted(authed_client):
    """GET remains, so Starlette returns 405 (not 404) for unmounted POST."""
    resp = authed_client.post(
        "/api/sites",
        json={"id": "core-orphan", "name": "Core Orphan"},
    )
    assert resp.status_code == 405, resp.text


def test_sites_delete_unmounted(authed_client):
    """PATCH remains, so Starlette returns 405 for unmounted DELETE."""
    resp = authed_client.request(
        "DELETE",
        "/api/sites/default",
        json={"confirm": True, "revoke_keys": True},
    )
    assert resp.status_code == 405, resp.text


def test_sites_list_returns_default_only(authed_client):
    resp = authed_client.get("/api/sites")
    assert resp.status_code == 200, resp.text
    ids = [s["id"] for s in resp.json()["sites"]]
    assert ids == ["default"]


def test_patch_default_still_saves_seo(authed_client):
    resp = authed_client.patch(
        "/api/sites/default",
        json={"sitename": "Core SEO Sitename"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["sitename"] == "Core SEO Sitename"


def test_sites_crud_absent_from_live_openapi(client):
    resp = client.get("/api/openapi.json")
    assert resp.status_code == 200, resp.text
    paths = resp.json().get("paths", {})
    sites = paths.get("/api/sites") or {}
    assert "get" in sites
    assert "post" not in sites
    site_id = paths.get("/api/sites/{site_id}") or {}
    assert "patch" in site_id
    assert "delete" not in site_id
    assert "/api/sites/{site_id}/og-preview" in paths
    assert "/api/sites/move-content" not in paths
    assert "/api/sites/{site_id}/rename" not in paths


def test_all_sites_cli_refused_on_core(tmp_path):
    import os
    import shutil
    import subprocess
    from pathlib import Path

    php = shutil.which("php")
    if php is None:
        import pytest

        pytest.skip("php not on PATH")
    repo = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PENCMS_INTERNAL_API_URL"] = "http://127.0.0.1:1/api"
    result = subprocess.run(
        [
            php,
            str(repo / "frontend-php" / "cli-tools" / "generate-static.php"),
            "--all-sites",
            "--domain=example.test",
            f"--output={tmp_path / 'dist-all'}",
        ],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode != 0
    combined = (result.stdout or "") + (result.stderr or "")
    assert "pro" in combined.lower()
