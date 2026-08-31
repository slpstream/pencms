"""Theme workshop routes are mounted on a Core boot."""

from __future__ import annotations


def test_config_edition_is_core(client):
    resp = client.get("/api/config")
    assert resp.status_code == 200, resp.text
    assert resp.json()["edition"] == "core"


def test_theme_package_zip_mounted(client):
    resp = client.post(
        "/api/sites/default/theme/package-zip",
        json={"slug": "my-theme"},
    )
    assert resp.status_code != 404, resp.text
    assert resp.status_code in (401, 403, 422), resp.text


def test_theme_install_mounted(client):
    resp = client.post("/api/themes/install")
    assert resp.status_code != 404, resp.text
    assert resp.status_code in (401, 422), resp.text


def test_mcp_theme_workshop_present_in_openapi(client):
    resp = client.get("/api/openapi.json")
    assert resp.status_code == 200, resp.text
    paths = resp.json().get("paths", {})
    assert "/api/v1/mcp/theme/files" in paths
    assert "/api/v1/mcp/theme/inspect/element" in paths
    assert "/api/v1/mcp/themes" in paths
    assert paths["/api/v1/mcp/themes"]["get"].get("operationId") == "list_themes"


def test_theme_customize_rest_still_mounted(client):
    resp = client.get("/api/openapi.json")
    assert resp.status_code == 200, resp.text
    paths = resp.json().get("paths", {})
    assert "/api/sites/{site_id}/theme/fork" in paths
    assert "/api/sites/{site_id}/theme/style" in paths
    assert "/api/sites/{site_id}/theme/package-zip" in paths
    assert "/api/themes/install" in paths
