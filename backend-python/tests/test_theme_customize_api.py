"""Theme Customize Session 2 — admin REST auth, round-trip, cross-site."""

from __future__ import annotations

import json

import pytest


@pytest.fixture
def isolated_content(temp_data_root, monkeypatch):
    """Point content storage at the temp root and reset site registry."""
    import shutil
    from pathlib import Path

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
    return isolated_content


def test_fork_unauthenticated(site_ready, client):
    resp = client.post("/api/sites/wiki/theme/fork", json={"parent": "basekit"})
    assert resp.status_code in (401, 403)


def test_fork_non_admin_forbidden(site_ready, authed_client, login_author):
    login_author(capabilities=["write:posts"], username="theme-denied")
    resp = authed_client.post(
        "/api/sites/wiki/theme/fork", json={"parent": "basekit"}
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["detail"] == "missing_capability: write:theme"


def test_unknown_site_404(site_ready, authed_client):
    resp = authed_client.post(
        "/api/sites/nosuch/theme/fork", json={"parent": "basekit"}
    )
    assert resp.status_code == 404, resp.text

    resp = authed_client.get("/api/sites/nosuch/theme/context")
    assert resp.status_code == 404, resp.text


def test_rest_fork_tree_file_context_delete_roundtrip(site_ready, authed_client):
    from services.site_service import get_site
    from services.theme_customize_service import has_site_custom_theme

    fork = authed_client.post(
        "/api/sites/wiki/theme/fork", json={"parent": "basekit"}
    )
    assert fork.status_code == 200, fork.text
    body = fork.json()
    assert body["theme"] == "custom"
    assert body["parent"] == "basekit"
    assert get_site("wiki").theme == "custom"

    tree = authed_client.get("/api/sites/wiki/theme/tree")
    assert tree.status_code == 200, tree.text
    files = tree.json()["files"]
    paths = [f["path"] if isinstance(f, dict) else f for f in files]
    assert "templates/index.html.twig" in paths
    assert "partials/nav.twig" in paths
    assert "assets/css/styles.css" in paths

    put = authed_client.put(
        "/api/sites/wiki/theme/file",
        json={"path": "templates/index.html.twig", "content": "{# edited #}\n"},
    )
    assert put.status_code == 200, put.text

    got = authed_client.get(
        "/api/sites/wiki/theme/file",
        params={"path": "templates/index.html.twig"},
    )
    assert got.status_code == 200, got.text
    assert "{# edited #}" in got.json()["content"]

    css_put = authed_client.put(
        "/api/sites/wiki/theme/file",
        json={"path": "assets/css/styles.css", "content": "body{color:#abc}\n"},
    )
    assert css_put.status_code == 200, css_put.text

    css_got = authed_client.get(
        "/api/sites/wiki/theme/file",
        params={"path": "assets/css/styles.css"},
    )
    assert css_got.status_code == 200, css_got.text
    assert "color:#abc" in css_got.json()["content"]

    reject_img = authed_client.put(
        "/api/sites/wiki/theme/file",
        json={"path": "assets/images/x.png", "content": "x"},
    )
    assert reject_img.status_code == 400, reject_img.text

    ctx = authed_client.get("/api/sites/wiki/theme/context")
    assert ctx.status_code == 200, ctx.text
    ctx_body = ctx.json()
    assert ctx_body["exists"] is True
    assert ctx_body["active"] is True
    assert ctx_body["parent"] == "basekit"
    assert ctx_body["registry_theme"] == "custom"
    assert "assets/css/" in ctx_body["allowlist"]["prefixes"]
    assert ".css" in ctx_body["allowlist"]["extensions"]
    assert ctx_body["preview"] == {
        "path": "/blog/?site=wiki",
        "header_control": "Preview Site",
        "live_serves_custom": True,
    }

    deleted = authed_client.delete("/api/sites/wiki/theme")
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deleted"] is True
    assert deleted.json()["reverted_theme"] == "basekit"
    assert not has_site_custom_theme("wiki")
    assert get_site("wiki").theme == "basekit"

    ctx2 = authed_client.get("/api/sites/wiki/theme/context")
    assert ctx2.status_code == 200, ctx2.text
    ctx2_body = ctx2.json()
    assert ctx2_body["exists"] is False
    assert ctx2_body["active"] is False
    assert ctx2_body["preview"]["live_serves_custom"] is False
    assert ctx2_body["preview"]["path"] == "/blog/?site=wiki"
    assert ctx2_body["preview"]["header_control"] == "Preview Site"


def test_patch_custom_requires_tree_and_base_keeps_tree(site_ready, authed_client):
    # No tree yet → cannot PATCH theme=custom
    bad = authed_client.patch("/api/sites/wiki", json={"theme": "custom"})
    assert bad.status_code == 400, bad.text
    assert "custom" in bad.json()["detail"].lower()

    fork = authed_client.post(
        "/api/sites/wiki/theme/fork", json={"parent": "basekit"}
    )
    assert fork.status_code == 200, fork.text

    # Switch to base — tree must remain
    to_base = authed_client.patch("/api/sites/wiki", json={"theme": "basekit"})
    assert to_base.status_code == 200, to_base.text
    assert to_base.json()["theme"] == "basekit"

    ctx = authed_client.get("/api/sites/wiki/theme/context")
    assert ctx.status_code == 200
    ctx_body = ctx.json()
    assert ctx_body["exists"] is True
    assert ctx_body["active"] is False
    assert ctx_body["preview"]["live_serves_custom"] is False

    # Switch back to custom
    to_custom = authed_client.patch("/api/sites/wiki", json={"theme": "custom"})
    assert to_custom.status_code == 200, to_custom.text
    assert to_custom.json()["theme"] == "custom"

    ctx2 = authed_client.get("/api/sites/wiki/theme/context")
    ctx2_body = ctx2.json()
    assert ctx2_body["exists"] is True
    assert ctx2_body["active"] is True
    assert ctx2_body["preview"]["live_serves_custom"] is True


def test_rest_cross_site_custom_isolation(site_ready, authed_client):
    from services.site_service import create_site
    from services.theme_customize_service import has_site_custom_theme, site_theme_root

    create_site("blog", "Blog", theme="basekit")

    fork = authed_client.post(
        "/api/sites/wiki/theme/fork", json={"parent": "basekit"}
    )
    assert fork.status_code == 200, fork.text

    put = authed_client.put(
        "/api/sites/wiki/theme/file",
        json={"path": "templates/index.html.twig", "content": "WIKI_ONLY\n"},
    )
    assert put.status_code == 200, put.text

    blog_ctx = authed_client.get("/api/sites/blog/theme/context")
    assert blog_ctx.status_code == 200
    assert blog_ctx.json()["exists"] is False
    assert not has_site_custom_theme("blog")

    # blog tree ops fail until forked; wiki tree untouched
    blog_tree = authed_client.get("/api/sites/blog/theme/tree")
    assert blog_tree.status_code == 400, blog_tree.text

    wiki_got = authed_client.get(
        "/api/sites/wiki/theme/file",
        params={"path": "templates/index.html.twig"},
    )
    assert wiki_got.status_code == 200
    assert "WIKI_ONLY" in wiki_got.json()["content"]

    # fork blog separately — must not see wiki edits
    blog_fork = authed_client.post(
        "/api/sites/blog/theme/fork", json={"parent": "basekit"}
    )
    assert blog_fork.status_code == 200, blog_fork.text
    blog_file = authed_client.get(
        "/api/sites/blog/theme/file",
        params={"path": "templates/index.html.twig"},
    )
    assert blog_file.status_code == 200
    assert "WIKI_ONLY" not in blog_file.json()["content"]
    assert (site_theme_root("wiki") / "templates" / "index.html.twig").read_text(
        encoding="utf-8"
    ).startswith("WIKI_ONLY")


def test_validate_unauthenticated(site_ready, client):
    resp = client.post("/api/sites/wiki/theme/validate")
    assert resp.status_code in (401, 403)


def test_validate_non_admin_forbidden(site_ready, authed_client, login_author):
    login_author(capabilities=["write:posts"], username="theme-val-denied")
    resp = authed_client.post("/api/sites/wiki/theme/validate")
    assert resp.status_code == 403, resp.text
    assert resp.json()["detail"] == "missing_capability: write:theme"


def test_validate_no_tree_and_unknown_site(site_ready, authed_client):
    resp = authed_client.post("/api/sites/wiki/theme/validate")
    assert resp.status_code == 400, resp.text

    resp = authed_client.post("/api/sites/nosuch/theme/validate")
    assert resp.status_code == 404, resp.text


def test_validate_after_fork_reports_shape_and_known_failure(
    site_ready, authed_client, isolated_content
):
    """Validate returns structured issues; Save still works when ok is false."""
    from services.theme_customize_service import site_theme_root

    fork = authed_client.post(
        "/api/sites/wiki/theme/fork", json={"parent": "basekit"}
    )
    assert fork.status_code == 200, fork.text

    # Minimal fixture lacks many required files → expect errors, HTTP 200
    resp = authed_client.post("/api/sites/wiki/theme/validate")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["site_id"] == "wiki"
    assert "ok" in body
    assert isinstance(body["errors"], list)
    assert isinstance(body["warnings"], list)
    assert body["error_count"] == len(body["errors"])
    assert body["warning_count"] == len(body["warnings"])
    assert body["ok"] is False
    codes = {e["code"] for e in body["errors"]}
    assert "missing_template_post" in codes
    assert "missing_skin" in codes

    # Introduce an extra known failure: remove index after adding a stub post
    root = site_theme_root("wiki")
    (root / "templates" / "post.html.twig").write_text(
        '<div class="article-content traven-preview">x</div>\n',
        encoding="utf-8",
    )
    (root / "templates" / "index.html.twig").unlink()

    resp2 = authed_client.post("/api/sites/wiki/theme/validate")
    assert resp2.status_code == 200, resp2.text
    body2 = resp2.json()
    assert body2["ok"] is False
    codes2 = {e["code"] for e in body2["errors"]}
    assert "missing_template_index" in codes2
    assert "missing_template_post" not in codes2

    # Soft: PUT still succeeds despite validate errors
    put = authed_client.put(
        "/api/sites/wiki/theme/file",
        json={
            "path": "partials/nav.twig",
            "content": "{# still saved #}\n",
        },
    )
    assert put.status_code == 200, put.text
    assert (
        root / "partials" / "nav.twig"
    ).read_text(encoding="utf-8") == "{# still saved #}\n"

    # Severity stamped on every issue
    assert all(e.get("severity") == "error" for e in body["errors"])
    assert all(w.get("severity") == "warning" for w in body["warnings"])
    assert all(e.get("severity") == "error" for e in body2["errors"])


def test_reset_file_round_trip(site_ready, authed_client, fixture_themes):
    fork = authed_client.post(
        "/api/sites/wiki/theme/fork", json={"parent": "basekit"}
    )
    assert fork.status_code == 200, fork.text

    put = authed_client.put(
        "/api/sites/wiki/theme/file",
        json={"path": "partials/nav.twig", "content": "{# custom #}\n"},
    )
    assert put.status_code == 200, put.text

    resp = authed_client.post(
        "/api/sites/wiki/theme/reset-file",
        json={"path": "partials/nav.twig"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["restored"] is True
    assert body["parent"] == "basekit"
    assert body["path"] == "partials/nav.twig"

    parent_content = (
        fixture_themes / "basekit" / "partials" / "nav.twig"
    ).read_text(encoding="utf-8")
    got = authed_client.get(
        "/api/sites/wiki/theme/file",
        params={"path": "partials/nav.twig"},
    )
    assert got.status_code == 200
    assert got.json()["content"] == parent_content

    bad = authed_client.post(
        "/api/sites/wiki/theme/reset-file",
        json={"path": "assets/js/app.js"},
    )
    assert bad.status_code == 400

    missing = authed_client.post(
        "/api/sites/wiki/theme/reset-file",
        json={"path": "partials/does-not-exist-on-parent.twig"},
    )
    assert missing.status_code == 400
    assert "No parent original" in missing.json()["detail"]


def test_reset_file_no_tree(site_ready, authed_client):
    resp = authed_client.post(
        "/api/sites/wiki/theme/reset-file",
        json={"path": "partials/nav.twig"},
    )
    assert resp.status_code == 400
    assert "No site theme tree" in resp.json()["detail"]
