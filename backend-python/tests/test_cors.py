"""CORS allowlist: admin UI origins only; non-browser agents omit Origin."""

from __future__ import annotations


def test_allowed_origin_reflected(client):
    origin = "http://127.0.0.1:8009"
    resp = client.get("/api/health", headers={"Origin": origin})
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == origin


def test_disallowed_origin_not_reflected(client):
    resp = client.get(
        "/api/health",
        headers={"Origin": "https://evil.example"},
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") is None


def test_preflight_allowed_origin(client):
    origin = "http://localhost:8009"
    resp = client.options(
        "/api/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == origin


def test_request_without_origin_ok(client):
    """Non-browser MCP agents typically omit Origin."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") is None


def test_llms_txt_served(client):
    resp = client.get("/llms.txt")
    assert resp.status_code == 200
    body = resp.text
    assert "/api/mcp" in body
    assert "oauth-protected-resource" in body
    assert "/api/auth/token" in body


def test_llms_txt_clean_core(client):
    """Core llms.txt must not advertise Pro-only overlay endpoints."""
    from services.llms_service import clear_llms_overlays

    clear_llms_overlays()
    resp = client.get("/llms.txt")
    assert resp.status_code == 200
    body = resp.text
    assert body.startswith("# PenCMS MCP\n") or body.startswith("# PenCMS MCP\r\n")
    assert not body.startswith("# PenCMS MCP (Pro)")
    assert "/api/users*" not in body
    assert "move-content" not in body


def test_llms_txt_overlay_dynamic_injection(client):
    """Overlays can dynamically append discovery notes and update the headline at runtime."""
    from services.llms_service import clear_llms_overlays, register_llms_overlay

    clear_llms_overlays()
    register_llms_overlay(lambda: "## Custom Overlay\n- GET /api/custom")
    try:
        resp = client.get("/llms.txt")
        assert resp.status_code == 200
        body = resp.text
        assert body.startswith("# PenCMS MCP (Pro)")
        assert "## Custom Overlay" in body
        assert "GET /api/custom" in body
    finally:
        clear_llms_overlays()
