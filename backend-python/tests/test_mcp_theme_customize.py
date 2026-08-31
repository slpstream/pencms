"""MCP theme-file customize tools (Session 4)."""

from __future__ import annotations

import json
import secrets
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def isolated_content(temp_data_root, monkeypatch):
    """Point content storage at the temp root and reset site registry."""
    import shutil

    import config
    from services.storage_provider import LocalStorageProvider
    import services.file_service as file_service

    content = temp_data_root / "content"
    content.mkdir(exist_ok=True)
    sites_yaml = temp_data_root / "data" / "sites.yaml"
    if sites_yaml.exists():
        sites_yaml.unlink()
    sites_dir = content / "sites"
    if sites_dir.exists():
        shutil.rmtree(sites_dir)
    for child in list(content.iterdir()):
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()

    provider = LocalStorageProvider(str(content))
    monkeypatch.setattr(config, "CONTENT_DIR_PATH", content)
    monkeypatch.setattr(config, "content_storage", provider)
    monkeypatch.setattr(file_service, "content_storage", provider)
    yield content


@pytest.fixture
def fixture_themes(tmp_path, monkeypatch):
    """Tiny install themes root with one base theme."""
    root = tmp_path / "themes"
    base = root / "basekit"
    (base / "templates").mkdir(parents=True)
    (base / "partials").mkdir(parents=True)
    (base / "assets" / "css").mkdir(parents=True)
    (base / "theme.json").write_text(
        json.dumps(
            {
                "name": "Base Kit",
                "version": "1.0.0",
                "type": "native",
            }
        ),
        encoding="utf-8",
    )
    (base / "templates" / "index.html.twig").write_text(
        "{# base index #}\n", encoding="utf-8"
    )
    (base / "partials" / "nav.twig").write_text("{# nav #}\n", encoding="utf-8")
    (base / "assets" / "css" / "styles.css").write_text(
        "body{}\n", encoding="utf-8"
    )

    import services.social_preview as social_preview

    monkeypatch.setattr(social_preview, "themes_root", lambda: root)
    monkeypatch.setattr(social_preview, "install_active_theme", lambda: "basekit")
    return root


@pytest.fixture
def site_ready(isolated_content, fixture_themes):
    from services.site_service import create_site, ensure_sites_initialized

    ensure_sites_initialized()
    create_site("wiki", "Wiki", theme="basekit")
    create_site("other", "Other", theme="basekit")
    return isolated_content


@pytest.fixture
def agent_token_factory(authed_client):
    def _create(scopes, site_id: str = "wiki"):
        resp = authed_client.post(
            "/api/auth/keys",
            json={
                "name": f"theme-{secrets.token_hex(4)}",
                "scopes": scopes,
                "site_id": site_id,
            },
        )
        assert resp.status_code == 200, resp.text
        raw_key = resp.json()["key"]
        resp = authed_client.post("/api/auth/token", json={"agent_key": raw_key})
        assert resp.status_code == 200, resp.text
        return resp.json()["access_token"]

    return _create


def test_unauthenticated_theme_mcp_rejected(site_ready, client):
    assert client.get("/api/v1/mcp/theme/files").status_code == 401
    assert client.get("/api/v1/mcp/theme/context").status_code == 401
    assert client.get("/api/v1/mcp/theme/validate").status_code == 401
    assert (
        client.get(
            "/api/v1/mcp/theme/file", params={"path": "partials/nav.twig"}
        ).status_code
        == 401
    )
    assert (
        client.put(
            "/api/v1/mcp/theme/file",
            json={"path": "partials/nav.twig", "content": "x"},
        ).status_code
        == 401
    )
    assert client.post("/api/v1/mcp/theme/fork", json={}).status_code == 401
    assert client.post("/api/v1/mcp/theme/reset").status_code == 401
    assert (
        client.post(
            "/api/v1/mcp/theme/file/reset",
            json={"path": "partials/nav.twig"},
        ).status_code
        == 401
    )


def test_read_scoped_allowed_write_rejected(site_ready, authed_client, agent_token_factory):
    token = agent_token_factory(["read"], site_id="wiki")
    headers = {"Authorization": f"Bearer {token}"}

    # Fork needs write — reject
    resp = authed_client.post(
        "/api/v1/mcp/theme/fork", json={"parent": "basekit"}, headers=headers
    )
    assert resp.status_code == 403
    assert "lacks required scope: write:theme" in resp.json()["detail"]

    # Seed tree via admin REST so read endpoints have something
    fork = authed_client.post(
        "/api/sites/wiki/theme/fork", json={"parent": "basekit"}
    )
    assert fork.status_code == 200, fork.text

    resp = authed_client.get("/api/v1/mcp/theme/context", headers=headers)
    assert resp.status_code == 200, resp.text
    ctx = resp.json()
    assert ctx["exists"] is True
    assert ctx["active"] is True
    assert ctx["preview"]["path"] == "/blog/?site=wiki"
    assert ctx["preview"]["header_control"] == "Preview Site"
    assert ctx["preview"]["live_serves_custom"] is True

    resp = authed_client.get("/api/v1/mcp/theme/files", headers=headers)
    assert resp.status_code == 200, resp.text
    files = resp.json()["files"]
    paths = [f["path"] for f in files]
    assert "partials/nav.twig" in paths
    assert "templates/index.html.twig" in paths
    assert "bytes" in files[0]
    assert "lines" in files[0]

    resp = authed_client.get(
        "/api/v1/mcp/theme/file",
        params={"path": "partials/nav.twig"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "{# nav #}" in body["content"]
    assert "bytes" in body
    assert "lines" in body

    resp = authed_client.put(
        "/api/v1/mcp/theme/file",
        json={"path": "partials/nav.twig", "content": "{# no #}\n"},
        headers=headers,
    )
    assert resp.status_code == 403


def test_mcp_theme_context_preview_fields(
    site_ready, authed_client, agent_token_factory
):
    token = agent_token_factory(["read"], site_id="wiki")
    headers = {"Authorization": f"Bearer {token}"}

    before = authed_client.get("/api/v1/mcp/theme/context", headers=headers)
    assert before.status_code == 200, before.text
    before_body = before.json()
    assert before_body["exists"] is False
    assert before_body["active"] is False
    assert before_body["preview"] == {
        "path": "/blog/?site=wiki",
        "header_control": "Preview Site",
        "live_serves_custom": False,
    }

    fork = authed_client.post(
        "/api/sites/wiki/theme/fork", json={"parent": "basekit"}
    )
    assert fork.status_code == 200, fork.text

    active = authed_client.get("/api/v1/mcp/theme/context", headers=headers)
    assert active.status_code == 200, active.text
    active_body = active.json()
    assert active_body["exists"] is True
    assert active_body["active"] is True
    assert active_body["preview"]["path"] == "/blog/?site=wiki"
    assert active_body["preview"]["header_control"] == "Preview Site"
    assert active_body["preview"]["live_serves_custom"] is True

    to_base = authed_client.patch("/api/sites/wiki", json={"theme": "basekit"})
    assert to_base.status_code == 200, to_base.text

    inactive = authed_client.get("/api/v1/mcp/theme/context", headers=headers)
    assert inactive.status_code == 200, inactive.text
    inactive_body = inactive.json()
    assert inactive_body["exists"] is True
    assert inactive_body["active"] is False
    assert inactive_body["preview"]["live_serves_custom"] is False
    assert inactive_body["preview"]["path"] == "/blog/?site=wiki"


def test_write_round_trip_under_allowlist(
    site_ready, authed_client, agent_token_factory, isolated_content
):
    token = agent_token_factory(["write", "read"], site_id="wiki")
    headers = {"Authorization": f"Bearer {token}"}

    resp = authed_client.post(
        "/api/v1/mcp/theme/fork", json={"parent": "basekit"}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["theme"] == "custom"
    assert resp.json()["parent"] == "basekit"

    disk = isolated_content / "sites" / "wiki" / "theme" / "partials" / "nav.twig"
    assert disk.is_file()

    new_content = "{# agent wrote #}\n<nav>ok</nav>\n"
    resp = authed_client.put(
        "/api/v1/mcp/theme/file",
        json={"path": "partials/nav.twig", "content": new_content},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["path"] == "partials/nav.twig"
    assert disk.read_text(encoding="utf-8") == new_content

    resp = authed_client.get(
        "/api/v1/mcp/theme/file",
        params={"path": "partials/nav.twig"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == new_content

    resp = authed_client.post("/api/v1/mcp/theme/reset", headers=headers)
    assert resp.status_code == 200, resp.text
    assert disk.read_text(encoding="utf-8") == "{# nav #}\n"


def test_write_rejects_theme_json_and_escape(
    site_ready, authed_client, agent_token_factory
):
    token = agent_token_factory(["write", "read"], site_id="wiki")
    headers = {"Authorization": f"Bearer {token}"}

    assert (
        authed_client.post(
            "/api/v1/mcp/theme/fork", json={"parent": "basekit"}, headers=headers
        ).status_code
        == 200
    )

    resp = authed_client.put(
        "/api/v1/mcp/theme/file",
        json={"path": "theme.json", "content": "{}"},
        headers=headers,
    )
    assert resp.status_code == 400, resp.text

    resp = authed_client.put(
        "/api/v1/mcp/theme/file",
        json={"path": "assets/images/logo.png", "content": "x"},
        headers=headers,
    )
    assert resp.status_code == 400, resp.text

    resp = authed_client.put(
        "/api/v1/mcp/theme/file",
        json={"path": "assets/js/app.js", "content": "x"},
        headers=headers,
    )
    assert resp.status_code == 400, resp.text

    resp = authed_client.put(
        "/api/v1/mcp/theme/file",
        json={"path": "assets/fonts/font.woff2", "content": "x"},
        headers=headers,
    )
    assert resp.status_code == 400, resp.text

    resp = authed_client.put(
        "/api/v1/mcp/theme/file",
        json={"path": "assets/css/extra.js", "content": "x"},
        headers=headers,
    )
    assert resp.status_code == 400, resp.text

    resp = authed_client.put(
        "/api/v1/mcp/theme/file",
        json={"path": "templates/../../etc/passwd", "content": "x"},
        headers=headers,
    )
    assert resp.status_code == 400, resp.text


def test_write_css_round_trip(
    site_ready, authed_client, agent_token_factory, isolated_content
):
    token = agent_token_factory(["write", "read"], site_id="wiki")
    headers = {"Authorization": f"Bearer {token}"}

    assert (
        authed_client.post(
            "/api/v1/mcp/theme/fork", json={"parent": "basekit"}, headers=headers
        ).status_code
        == 200
    )

    files = authed_client.get("/api/v1/mcp/theme/files", headers=headers)
    assert files.status_code == 200, files.text
    paths = [f["path"] for f in files.json()["files"]]
    assert "assets/css/styles.css" in paths

    css_content = "body{background:#fafafa}\n"
    resp = authed_client.put(
        "/api/v1/mcp/theme/file",
        json={"path": "assets/css/styles.css", "content": css_content},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["path"] == "assets/css/styles.css"

    disk = (
        isolated_content / "sites" / "wiki" / "theme" / "assets" / "css" / "styles.css"
    )
    assert disk.read_text(encoding="utf-8") == css_content

    got = authed_client.get(
        "/api/v1/mcp/theme/file",
        params={"path": "assets/css/styles.css"},
        headers=headers,
    )
    assert got.status_code == 200
    assert got.json()["content"] == css_content


def test_theme_mcp_site_binding(
    site_ready, authed_client, agent_token_factory, isolated_content
):
    """JWT site_id is authoritative; writes only touch the bound site."""
    wiki_token = agent_token_factory(["write", "read"], site_id="wiki")
    wiki_headers = {"Authorization": f"Bearer {wiki_token}"}

    other_token = agent_token_factory(["write", "read"], site_id="other")
    other_headers = {"Authorization": f"Bearer {other_token}"}

    assert (
        authed_client.post(
            "/api/v1/mcp/theme/fork",
            json={"parent": "basekit"},
            headers=wiki_headers,
        ).status_code
        == 200
    )
    assert (
        authed_client.post(
            "/api/v1/mcp/theme/fork",
            json={"parent": "basekit"},
            headers=other_headers,
        ).status_code
        == 200
    )

    marker = "{# wiki-only #}\n"
    resp = authed_client.put(
        "/api/v1/mcp/theme/file",
        json={"path": "partials/nav.twig", "content": marker},
        headers=wiki_headers,
    )
    assert resp.status_code == 200, resp.text

    wiki_disk = (
        isolated_content / "sites" / "wiki" / "theme" / "partials" / "nav.twig"
    )
    other_disk = (
        isolated_content / "sites" / "other" / "theme" / "partials" / "nav.twig"
    )
    assert wiki_disk.read_text(encoding="utf-8") == marker
    assert other_disk.read_text(encoding="utf-8") == "{# nav #}\n"

    # Other agent cannot see wiki's write via its own binding
    resp = authed_client.get(
        "/api/v1/mcp/theme/file",
        params={"path": "partials/nav.twig"},
        headers=other_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == "{# nav #}\n"


def test_validate_theme_read_scope(
    site_ready, authed_client, agent_token_factory
):
    token = agent_token_factory(["read"], site_id="wiki")
    headers = {"Authorization": f"Bearer {token}"}

    resp = authed_client.get("/api/v1/mcp/theme/validate", headers=headers)
    assert resp.status_code == 400, resp.text

    fork = authed_client.post(
        "/api/sites/wiki/theme/fork", json={"parent": "basekit"}
    )
    assert fork.status_code == 200, fork.text

    resp = authed_client.get("/api/v1/mcp/theme/validate", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["site_id"] == "wiki"
    assert isinstance(body["errors"], list)
    assert isinstance(body["warnings"], list)
    assert body["ok"] is False
    assert any(e["code"] == "missing_template_post" for e in body["errors"])
    assert all(e.get("severity") == "error" for e in body["errors"])
    assert all(w.get("severity") == "warning" for w in body["warnings"])


def test_validate_theme_site_binding(
    site_ready, authed_client, agent_token_factory, isolated_content
):
    wiki_token = agent_token_factory(["read"], site_id="wiki")
    other_token = agent_token_factory(["read"], site_id="other")
    wiki_headers = {"Authorization": f"Bearer {wiki_token}"}
    other_headers = {"Authorization": f"Bearer {other_token}"}

    assert (
        authed_client.post(
            "/api/sites/wiki/theme/fork", json={"parent": "basekit"}
        ).status_code
        == 200
    )

    wiki_val = authed_client.get(
        "/api/v1/mcp/theme/validate", headers=wiki_headers
    )
    assert wiki_val.status_code == 200, wiki_val.text
    assert wiki_val.json()["site_id"] == "wiki"

    other_val = authed_client.get(
        "/api/v1/mcp/theme/validate", headers=other_headers
    )
    assert other_val.status_code == 400, other_val.text

    assert (
        authed_client.post(
            "/api/sites/other/theme/fork", json={"parent": "basekit"}
        ).status_code
        == 200
    )
    other_val2 = authed_client.get(
        "/api/v1/mcp/theme/validate", headers=other_headers
    )
    assert other_val2.status_code == 200, other_val2.text
    assert other_val2.json()["site_id"] == "other"
    wiki_root = (isolated_content / "sites" / "wiki" / "theme").resolve()
    other_root = (isolated_content / "sites" / "other" / "theme").resolve()
    assert wiki_root.is_dir() and other_root.is_dir()
    assert wiki_root != other_root


def test_mcp_theme_tools_registered_in_openapi(client):
    resp = client.get("/api/openapi.json")
    assert resp.status_code == 200
    paths = resp.json().get("paths", {})

    assert "/api/v1/mcp/theme/files" in paths
    assert "/api/v1/mcp/theme/file" in paths
    assert "/api/v1/mcp/theme/context" in paths
    assert "/api/v1/mcp/theme/fork" in paths
    assert "/api/v1/mcp/theme/reset" in paths
    assert "/api/v1/mcp/theme/validate" in paths

    files_get = paths["/api/v1/mcp/theme/files"]["get"]
    assert "mcp" in files_get["tags"]
    assert files_get.get("operationId") == "list_theme_files"

    file_ops = paths["/api/v1/mcp/theme/file"]
    assert file_ops["get"].get("operationId") == "read_theme_file"
    assert "mcp" in file_ops["get"]["tags"]
    assert file_ops["put"].get("operationId") == "write_theme_file"
    assert "mcp" in file_ops["put"]["tags"]

    assert paths["/api/v1/mcp/theme/context"]["get"].get("operationId") == (
        "get_theme_context"
    )
    assert paths["/api/v1/mcp/theme/fork"]["post"].get("operationId") == (
        "fork_site_theme"
    )
    assert paths["/api/v1/mcp/theme/reset"]["post"].get("operationId") == (
        "reset_site_theme"
    )
    assert paths["/api/v1/mcp/theme/validate"]["get"].get("operationId") == (
        "validate_theme"
    )

    assert file_ops["patch"].get("operationId") == "patch_theme_file"
    assert "mcp" in file_ops["patch"]["tags"]

    assert "/api/v1/mcp/theme/file/revert" in paths
    revert_post = paths["/api/v1/mcp/theme/file/revert"]["post"]
    assert revert_post.get("operationId") == "revert_theme_file"
    assert "mcp" in revert_post["tags"]

    assert "/api/v1/mcp/theme/file/reset" in paths
    reset_file_post = paths["/api/v1/mcp/theme/file/reset"]["post"]
    assert reset_file_post.get("operationId") == "reset_theme_file"
    assert "mcp" in reset_file_post["tags"]


def test_mcp_patch_revert_and_guardrails(
    site_ready, authed_client, agent_token_factory
):
    token = agent_token_factory(["write", "read"], site_id="wiki")
    headers = {"Authorization": f"Bearer {token}"}

    # Fork tree
    assert (
        authed_client.post(
            "/api/v1/mcp/theme/fork", json={"parent": "basekit"}, headers=headers
        ).status_code
        == 200
    )

    rel = "templates/index.html.twig"
    large_text = "{# " + ("long template content " * 10) + " #}\n<div>hello</div>\n"
    res = authed_client.put(
        "/api/v1/mcp/theme/file",
        json={"path": rel, "content": large_text},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    first_body = res.json()
    assert first_body["overwritten"] is True
    assert first_body["created"] is False
    assert first_body["guarded"] is False
    assert "previous_size" in first_body
    cur_bytes = first_body["bytes"]
    assert cur_bytes > 100

    # Guardrail block on shrink write
    bad_write = authed_client.put(
        "/api/v1/mcp/theme/file",
        json={"path": rel, "content": "short"},
        headers=headers,
    )
    assert bad_write.status_code == 400
    bad_detail = bad_write.json()["detail"]
    assert isinstance(bad_detail, dict)
    assert bad_detail["error"] == "DESTRUCTIVE_WRITE"
    assert bad_detail["revert_available"] is True
    assert bad_detail["suggested_action"] == "revert_theme_file"
    assert bad_detail["expected_size"] == cur_bytes
    assert "revert_theme_file" in bad_detail["reason"]
    assert "call revert_theme_file first" in bad_detail["hint"]

    # Override with force=True and matching expected_size
    ok_write = authed_client.put(
        "/api/v1/mcp/theme/file",
        json={"path": rel, "content": "short\n", "force": True, "expected_size": cur_bytes},
        headers=headers,
    )
    assert ok_write.status_code == 200, ok_write.text
    forced_body = ok_write.json()
    assert forced_body["created"] is False
    assert forced_body["overwritten"] is True
    assert forced_body["guarded"] is True
    assert forced_body["previous_size"] == cur_bytes
    assert "destructive-write override" in forced_body["hint"]

    # Create a brand-new allowlisted path
    create_rel = "partials/_mcp_create_probe.twig"
    created = authed_client.put(
        "/api/v1/mcp/theme/file",
        json={"path": create_rel, "content": "{# new #}\n"},
        headers=headers,
    )
    assert created.status_code == 200, created.text
    created_body = created.json()
    assert created_body["created"] is True
    assert created_body["overwritten"] is False
    assert created_body["guarded"] is False
    assert "previous_size" not in created_body
    assert created_body["hint"] == "Created new file"

    # Revert restores large_text
    rev = authed_client.post(
        "/api/v1/mcp/theme/file/revert",
        json={"path": rel},
        headers=headers,
    )
    assert rev.status_code == 200, rev.text
    assert rev.json()["reverted"] is True

    got = authed_client.get(
        "/api/v1/mcp/theme/file", params={"path": rel}, headers=headers
    )
    assert got.status_code == 200
    assert got.json()["content"] == large_text

    # Patch operation
    patch_res = authed_client.patch(
        "/api/v1/mcp/theme/file",
        json={"path": rel, "target": "<div>hello</div>", "replacement": "<div>patched</div>"},
        headers=headers,
    )
    assert patch_res.status_code == 200, patch_res.text
    body = patch_res.json()
    assert body["replacements"] == 1
    assert body["match_mode"] == "exact"
    assert body["matched_at_line"] >= 1
    assert body["dry_run"] is False
    assert body["created"] is False
    assert body["overwritten"] is True
    assert body["guarded"] is False
    assert body["hint"] == "Modified existing file (section patch)"

    got2 = authed_client.get(
        "/api/v1/mcp/theme/file", params={"path": rel}, headers=headers
    )
    assert "<div>patched</div>" in got2.json()["content"]

    # dry_run does not mutate disk
    before = got2.json()["content"]
    dry = authed_client.patch(
        "/api/v1/mcp/theme/file",
        json={
            "path": rel,
            "target": "<div>patched</div>",
            "replacement": "<div>preview-only</div>",
            "dry_run": True,
        },
        headers=headers,
    )
    assert dry.status_code == 200, dry.text
    dry_body = dry.json()
    assert dry_body["dry_run"] is True
    assert dry_body["match_mode"] == "exact"
    assert dry_body["created"] is False
    assert dry_body["overwritten"] is True
    assert dry_body["guarded"] is False
    assert dry_body["hint"] == "Dry-run preview only — nothing written"
    assert "preview-only" in dry_body["unified_diff"]
    assert dry_body["bytes_after"] > 0

    got3 = authed_client.get(
        "/api/v1/mcp/theme/file", params={"path": rel}, headers=headers
    )
    assert got3.json()["content"] == before

    # Mismatched expected_size surfaces both sizes
    shrink = authed_client.put(
        "/api/v1/mcp/theme/file",
        json={
            "path": rel,
            "content": "tiny",
            "force": True,
            "expected_size": got3.json()["bytes"] + 9,
        },
        headers=headers,
    )
    assert shrink.status_code == 400
    detail = shrink.json()["detail"]
    assert isinstance(detail, dict)
    assert detail["error"] == "DESTRUCTIVE_WRITE"
    assert "expected_size" in detail
    assert detail["current_bytes"] is not None
    assert isinstance(detail["revert_available"], bool)

    # Create-only path: shrink with no revision history
    create_only = "partials/_mcp_no_rev_probe.twig"
    large_new = "{# " + ("create only content " * 12) + " #}\n"
    made = authed_client.put(
        "/api/v1/mcp/theme/file",
        json={"path": create_only, "content": large_new},
        headers=headers,
    )
    assert made.status_code == 200, made.text
    assert made.json()["created"] is True
    no_rev = authed_client.put(
        "/api/v1/mcp/theme/file",
        json={"path": create_only, "content": "tiny"},
        headers=headers,
    )
    assert no_rev.status_code == 400
    no_rev_detail = no_rev.json()["detail"]
    assert isinstance(no_rev_detail, dict)
    assert no_rev_detail["error"] == "DESTRUCTIVE_WRITE"
    assert no_rev_detail["revert_available"] is False
    assert "suggested_action" not in no_rev_detail
    assert "do not call revert_theme_file" in no_rev_detail["reason"]
    assert "do not call revert_theme_file" in no_rev_detail["hint"]
    assert no_rev_detail["expected_size"] == made.json()["bytes"]


def test_mcp_reset_theme_file(
    site_ready, authed_client, agent_token_factory, fixture_themes
):
    token = agent_token_factory(["write", "read"], site_id="wiki")
    headers = {"Authorization": f"Bearer {token}"}

    # Read scope cannot reset
    read_token = agent_token_factory(["read"], site_id="wiki")
    read_headers = {"Authorization": f"Bearer {read_token}"}

    fork = authed_client.post(
        "/api/v1/mcp/theme/fork", json={"parent": "basekit"}, headers=headers
    )
    assert fork.status_code == 200, fork.text

    denied = authed_client.post(
        "/api/v1/mcp/theme/file/reset",
        json={"path": "partials/nav.twig"},
        headers=read_headers,
    )
    assert denied.status_code == 403

    mangled = "{# agent mangled #}\n"
    put = authed_client.put(
        "/api/v1/mcp/theme/file",
        json={"path": "partials/nav.twig", "content": mangled},
        headers=headers,
    )
    assert put.status_code == 200, put.text

    # Revert restores last snapshot (pre-mangle); reset restores parent stock
    rev = authed_client.post(
        "/api/v1/mcp/theme/file/revert",
        json={"path": "partials/nav.twig"},
        headers=headers,
    )
    assert rev.status_code == 200, rev.text
    assert rev.json()["reverted"] is True

    put2 = authed_client.put(
        "/api/v1/mcp/theme/file",
        json={"path": "partials/nav.twig", "content": mangled},
        headers=headers,
    )
    assert put2.status_code == 200, put2.text

    reset = authed_client.post(
        "/api/v1/mcp/theme/file/reset",
        json={"path": "partials/nav.twig"},
        headers=headers,
    )
    assert reset.status_code == 200, reset.text
    body = reset.json()
    assert body["restored"] is True
    assert body["parent"] == "basekit"

    parent_content = (
        fixture_themes / "basekit" / "partials" / "nav.twig"
    ).read_text(encoding="utf-8")
    got = authed_client.get(
        "/api/v1/mcp/theme/file",
        params={"path": "partials/nav.twig"},
        headers=headers,
    )
    assert got.status_code == 200
    assert got.json()["content"] == parent_content


def test_mcp_theme_file_version_and_if_version(
    site_ready, authed_client, agent_token_factory
):
    token = agent_token_factory(["write", "read"], site_id="wiki")
    headers = {"Authorization": f"Bearer {token}"}
    assert (
        authed_client.post(
            "/api/v1/mcp/theme/fork", json={"parent": "basekit"}, headers=headers
        ).status_code
        == 200
    )

    first = authed_client.get(
        "/api/v1/mcp/theme/file",
        params={"path": "partials/nav.twig"},
        headers=headers,
    )
    assert first.status_code == 200, first.text
    body = first.json()
    assert "content" in body
    assert body["unchanged"] is False
    version = body["version"]
    assert version
    assert float(version) > 0

    same = authed_client.get(
        "/api/v1/mcp/theme/file",
        params={"path": "partials/nav.twig", "if_version": version},
        headers=headers,
    )
    assert same.status_code == 200, same.text
    same_body = same.json()
    assert same_body["unchanged"] is True
    assert same_body["version"] == version
    assert "content" not in same_body
    assert "bytes" in same_body
    assert "lines" in same_body

    written = authed_client.put(
        "/api/v1/mcp/theme/file",
        json={"path": "partials/nav.twig", "content": "{# versioned #}\n"},
        headers=headers,
    )
    assert written.status_code == 200, written.text
    write_body = written.json()
    assert write_body["version"]
    assert write_body["version"] != version

    stale = authed_client.get(
        "/api/v1/mcp/theme/file",
        params={"path": "partials/nav.twig", "if_version": version},
        headers=headers,
    )
    assert stale.status_code == 200, stale.text
    stale_body = stale.json()
    assert stale_body["unchanged"] is False
    assert "{# versioned #}" in stale_body["content"]
    assert stale_body["version"] == write_body["version"]

    patched = authed_client.patch(
        "/api/v1/mcp/theme/file",
        json={
            "path": "partials/nav.twig",
            "target": "{# versioned #}",
            "replacement": "{# patched #}",
        },
        headers=headers,
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["version"]
    assert patched.json()["dry_run"] is False
