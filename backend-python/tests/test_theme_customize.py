"""Theme Customize Session 1 — fork / confinement / dual-root resolve."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest


@pytest.fixture
def isolated_content(temp_data_root, monkeypatch):
    """Point content storage at the temp root and reset site registry."""
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
    """Tiny install themes root with one base theme (+ reserved custom trap)."""
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
                "social_preview": {"og_accent_color": "#111111"},
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

    # Rogue install folder named custom — must never be listed as a base
    trap = root / "custom"
    trap.mkdir()
    (trap / "theme.json").write_text(
        json.dumps({"name": "Should Not List"}), encoding="utf-8"
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


def test_list_skips_install_custom_and_appends_site_custom(site_ready):
    from services.social_preview import list_installed_themes
    from services.theme_customize_service import fork

    themes = list_installed_themes()
    ids = [t["id"] for t in themes]
    assert "basekit" in ids
    assert "custom" not in ids

    fork("wiki", "basekit")
    with_site = list_installed_themes(site_id="wiki")
    custom = [t for t in with_site if t["id"] == "custom"]
    assert len(custom) == 1
    assert custom[0]["source"] == "site"
    assert custom[0]["parent"] == "basekit"
    assert "Base Kit (custom)" in custom[0]["label"]

    other = list_installed_themes(site_id="default")
    assert not any(t["id"] == "custom" for t in other)


def test_fork_metadata_and_registry(site_ready):
    from services.site_service import get_site
    from services.theme_customize_service import fork, site_theme_root

    result = fork("wiki", "basekit")
    assert result["theme"] == "custom"
    assert result["parent"] == "basekit"

    site = get_site("wiki")
    assert site is not None
    assert site.theme == "custom"

    root = site_theme_root("wiki")
    assert (root / "theme.json").is_file()
    assert (root / "templates" / "index.html.twig").is_file()
    assert (root / "assets" / "css" / "styles.css").is_file()

    meta = json.loads((root / "theme.json").read_text(encoding="utf-8"))
    assert meta["parent"] == "basekit"
    assert meta["origin"] == "site-custom"
    assert meta["name"] == "Base Kit (custom)"
    assert "customized_at" in meta


def test_resolve_custom_vs_base(site_ready):
    from services.theme_customize_service import (
        ThemeCustomizeError,
        fork,
        resolve_theme_dir,
        site_theme_root,
    )

    base_dir = resolve_theme_dir("wiki", "basekit")
    assert base_dir.name == "basekit"

    with pytest.raises(ThemeCustomizeError, match="no valid theme tree"):
        resolve_theme_dir("wiki", "custom")

    fork("wiki", "basekit")
    custom_dir = resolve_theme_dir("wiki", "custom")
    assert custom_dir == site_theme_root("wiki").resolve()


def test_confinement_rejects_traversal_and_absolute(site_ready):
    from services.theme_customize_service import (
        ThemeCustomizeError,
        confine_theme_path,
        fork,
        write_file,
    )

    fork("wiki", "basekit")

    with pytest.raises(ThemeCustomizeError, match="traversal"):
        confine_theme_path("wiki", "../theme.json")
    with pytest.raises(ThemeCustomizeError, match="traversal"):
        confine_theme_path("wiki", "templates/../../etc/passwd")
    with pytest.raises(ThemeCustomizeError, match="Absolute"):
        confine_theme_path("wiki", "/etc/passwd")

    with pytest.raises(ThemeCustomizeError, match="theme.json"):
        write_file("wiki", "theme.json", "{}")
    with pytest.raises(ThemeCustomizeError, match="allowlist"):
        write_file("wiki", "templates/notes.md", "x")
    with pytest.raises(ThemeCustomizeError, match="allowlist"):
        write_file("wiki", "assets/images/logo.png", "x")
    with pytest.raises(ThemeCustomizeError, match="allowlist"):
        write_file("wiki", "assets/js/app.js", "x")
    with pytest.raises(ThemeCustomizeError, match="allowlist"):
        write_file("wiki", "assets/fonts/font.woff2", "x")
    with pytest.raises(ThemeCustomizeError, match="allowlist"):
        write_file("wiki", "assets/css/extra.js", "x")
    with pytest.raises(ThemeCustomizeError, match="allowlist"):
        write_file("wiki", "templates/style.css", "x")


def test_write_read_list_editable(site_ready):
    from services.theme_customize_service import fork, list_files, read_file, write_file

    fork("wiki", "basekit")
    overwrite = write_file("wiki", "templates/index.html.twig", "{# customized #}\n")
    assert overwrite["created"] is False
    assert overwrite["overwritten"] is True
    assert overwrite["guarded"] is False
    assert "previous_size" in overwrite
    assert "Overwrote existing file" in overwrite["hint"]
    assert "{# customized #}" in read_file("wiki", "templates/index.html.twig")

    created = write_file(
        "wiki", "partials/_observability_probe.twig", "{# probe #}\n"
    )
    assert created["created"] is True
    assert created["overwritten"] is False
    assert created["guarded"] is False
    assert "previous_size" not in created
    assert created["hint"] == "Created new file"

    write_file("wiki", "assets/css/styles.css", "body{color:red}\n")
    assert "color:red" in read_file("wiki", "assets/css/styles.css")
    files = list_files("wiki")
    paths = [f["path"] for f in files]
    assert "templates/index.html.twig" in paths
    assert "partials/nav.twig" in paths
    assert "partials/_observability_probe.twig" in paths
    assert "assets/css/styles.css" in paths
    assert "theme.json" not in paths
    assert not any(p.startswith("assets/images/") for p in paths)
    assert not any(p.startswith("assets/js/") for p in paths)


def test_cross_site_isolation(site_ready):
    from services.site_service import create_site
    from services.theme_customize_service import (
        ThemeCustomizeError,
        fork,
        read_file,
        write_file,
    )

    create_site("blog", "Blog", theme="basekit")
    fork("wiki", "basekit")
    write_file("wiki", "templates/index.html.twig", "WIKI\n")

    with pytest.raises(ThemeCustomizeError, match="No site theme tree"):
        read_file("blog", "templates/index.html.twig")

    fork("blog", "basekit")
    assert "WIKI" not in read_file("blog", "templates/index.html.twig")
    assert "WIKI" in read_file("wiki", "templates/index.html.twig")


def test_reset_and_delete(site_ready):
    from services.site_service import get_site
    from services.theme_customize_service import (
        delete,
        fork,
        has_site_custom_theme,
        read_file,
        reset,
        site_theme_root,
        write_file,
    )

    fork("wiki", "basekit")
    write_file("wiki", "templates/index.html.twig", "{# dirty #}\n")
    reset("wiki")
    assert "{# dirty #}" not in read_file("wiki", "templates/index.html.twig")
    assert get_site("wiki").theme == "custom"

    parent_before = json.loads(
        (site_theme_root("wiki") / "theme.json").read_text(encoding="utf-8")
    )["parent"]
    result = delete("wiki")
    assert result["deleted"] is True
    assert result["reverted_theme"] == parent_before
    assert not has_site_custom_theme("wiki")
    assert get_site("wiki").theme == "basekit"


def test_theme_json_path_custom_requires_tree(site_ready):
    from services.social_preview import theme_json_path
    from services.theme_customize_service import fork

    with pytest.raises(ValueError, match="requires site_id"):
        theme_json_path("custom")

    with pytest.raises(FileNotFoundError, match="no valid custom theme"):
        theme_json_path("custom", site_id="wiki")

    fork("wiki", "basekit")
    path = theme_json_path("custom", site_id="wiki")
    assert path.is_file()
    assert path.name == "theme.json"


def test_cannot_fork_from_custom_slug(site_ready):
    from services.theme_customize_service import ThemeCustomizeError, fork

    with pytest.raises(ThemeCustomizeError, match="reserved"):
        fork("wiki", "custom")


def test_assets_raw_theme_path_allowed(site_ready, authed_client):
    """Theme assets under sites/{id}/theme/assets are reachable; templates are not."""
    from services.theme_customize_service import fork, site_theme_prefix

    fork("wiki", "basekit")
    prefix = site_theme_prefix("wiki")

    ok = authed_client.get(f"/api/assets/raw/{prefix}/assets/css/styles.css")
    assert ok.status_code == 200, ok.text
    assert b"body" in ok.content

    # templates must not be served via the theme/assets allow rule
    denied = authed_client.get(f"/api/assets/raw/{prefix}/templates/index.html.twig")
    assert denied.status_code == 404

    # ``..`` segments are rejected (or normalized away to a non-assets path → 404)
    trav = authed_client.get(
        "/api/assets/raw/sites/wiki/theme/assets/../templates/index.html.twig"
    )
    assert trav.status_code in (400, 404)


def test_assets_raw_head_exists_only(site_ready, authed_client):
    """HEAD probes (PHP assetExists) get 200/404 without a body — never 405."""
    from services.theme_customize_service import fork, site_theme_prefix

    fork("wiki", "basekit")
    prefix = site_theme_prefix("wiki")

    ok = authed_client.head(f"/api/assets/raw/{prefix}/assets/css/styles.css")
    assert ok.status_code == 200, ok.text
    assert ok.content == b""

    missing = authed_client.head(f"/api/assets/raw/{prefix}/assets/css/nope.css")
    assert missing.status_code == 404


def test_service_write_guardrail_and_override(site_ready):
    from services.theme_customize_service import ThemeCustomizeError, fork, read_file, write_file

    fork("wiki", "basekit")
    rel = "templates/index.html.twig"
    large_content = "{# " + ("large index template content " * 10) + " #}\n<h1>Welcome</h1>\n"
    write_file("wiki", rel, large_content)
    cur_size = len(large_content.encode("utf-8"))
    assert cur_size > 100

    # Guardrail blocks small write without force/expected_size
    with pytest.raises(ThemeCustomizeError, match="DESTRUCTIVE_WRITE"):
        write_file("wiki", rel, "x\n", enforce_guardrail=True)

    # Force alone is insufficient
    with pytest.raises(ThemeCustomizeError, match="DESTRUCTIVE_WRITE"):
        write_file("wiki", rel, "x\n", enforce_guardrail=True, force=True)

    # Mismatched expected_size reports both numbers; prior overwrite left a revision
    with pytest.raises(ThemeCustomizeError, match="DESTRUCTIVE_WRITE") as mismatched:
        write_file(
            "wiki",
            rel,
            "x\n",
            enforce_guardrail=True,
            force=True,
            expected_size=cur_size + 5,
        )
    detail = str(mismatched.value)
    assert f"expected_size={cur_size + 5}" in detail
    assert f"on-disk size {cur_size}" in detail
    assert f"expected_size={cur_size}" in detail
    assert "revert_available=true" in detail
    assert "revert_theme_file" in detail
    assert mismatched.value.payload is not None
    assert mismatched.value.payload["revert_available"] is True
    assert mismatched.value.payload["suggested_action"] == "revert_theme_file"
    assert mismatched.value.payload["expected_size"] == cur_size
    assert "call revert_theme_file first" in mismatched.value.payload["hint"]

    # Valid override succeeds
    forced = write_file(
        "wiki", rel, "x\n", enforce_guardrail=True, force=True, expected_size=cur_size
    )
    assert forced["created"] is False
    assert forced["overwritten"] is True
    assert forced["guarded"] is True
    assert forced["previous_size"] == cur_size
    assert "destructive-write override" in forced["hint"]
    assert read_file("wiki", rel) == "x\n"

    # Human admin save (enforce_guardrail=False) bypasses guardrail
    write_file("wiki", rel, large_content)
    bypass = write_file("wiki", rel, "small\n", enforce_guardrail=False)
    assert bypass["guarded"] is False
    assert bypass["overwritten"] is True
    assert read_file("wiki", rel) == "small\n"


def test_destructive_write_no_revision_for_create_only(site_ready):
    """Fresh creates have no snapshot; DESTRUCTIVE_WRITE must not suggest revert."""
    from services.theme_customize_service import ThemeCustomizeError, fork, write_file

    fork("wiki", "basekit")
    rel = "partials/_create_only_probe.twig"
    large = "{# " + ("freshly created content " * 10) + " #}\n"
    created = write_file("wiki", rel, large)
    assert created["created"] is True
    cur_size = created["bytes"]
    assert cur_size > 100

    with pytest.raises(ThemeCustomizeError, match="DESTRUCTIVE_WRITE") as blocked:
        write_file("wiki", rel, "x\n", enforce_guardrail=True)
    detail = str(blocked.value)
    assert "revert_available=false" in detail
    assert "do not call revert_theme_file" in detail
    # Recovery path still present
    assert f"expected_size={cur_size}" in detail
    assert "patch_theme_file" in detail
    assert blocked.value.payload is not None
    assert blocked.value.payload["revert_available"] is False
    assert "suggested_action" not in blocked.value.payload
    assert blocked.value.payload["expected_size"] == cur_size
    assert "do not call revert_theme_file" in blocked.value.payload["hint"]
    assert f"expected_size={cur_size}" in blocked.value.payload["hint"]


def test_service_patch_exact_and_fuzzy_and_errors(site_ready):
    from services.theme_customize_service import (
        ThemeCustomizeError,
        fork,
        patch_file,
        read_file,
        write_file,
    )

    fork("wiki", "basekit")
    rel = "templates/index.html.twig"
    initial = "{# header #}\n<main class=\"container\">\n  <p>Hello World</p>\n</main>\n"
    write_file("wiki", rel, initial)

    # Empty target rejected
    with pytest.raises(ThemeCustomizeError, match="TARGET_NOT_FOUND"):
        patch_file("wiki", rel, "", "<p>Updated</p>")

    # Exact unique replace
    res = patch_file("wiki", rel, "<p>Hello World</p>", "<p>Hello PenCMS</p>")
    assert res["ok"] is True
    assert res["replacements"] == 1
    assert res["match_mode"] == "exact"
    assert res["matched_at_line"] == 3
    assert res["dry_run"] is False
    assert res["created"] is False
    assert res["overwritten"] is True
    assert res["guarded"] is False
    assert res["hint"] == "Modified existing file (section patch)"
    assert "@@" in res["unified_diff"]
    assert "<p>Hello PenCMS</p>" in read_file("wiki", rel)

    # dry_run previews without writing
    before_dry = read_file("wiki", rel)
    dry = patch_file(
        "wiki",
        rel,
        "<p>Hello PenCMS</p>",
        "<p>Would Change</p>",
        dry_run=True,
    )
    assert dry["ok"] is True
    assert dry["dry_run"] is True
    assert dry["match_mode"] == "exact"
    assert dry["matched_at_line"] == 3
    assert dry["created"] is False
    assert dry["overwritten"] is True
    assert dry["guarded"] is False
    assert dry["hint"] == "Dry-run preview only — nothing written"
    assert "Would Change" in dry["unified_diff"]
    assert dry["bytes_after"] > 0
    assert dry["lines_after"] > 0
    assert read_file("wiki", rel) == before_dry

    # Fuzzy whitespace replace
    res2 = patch_file("wiki", rel, "  <p>Hello PenCMS</p>  ", "<p>Fuzzy Updated</p>")
    assert res2["ok"] is True
    assert res2["match_mode"] == "line_trim"
    assert "<p>Fuzzy Updated</p>" in read_file("wiki", rel)

    # Ambiguous target (multiple matches)
    write_file("wiki", rel, "<div>test</div>\n<div>test</div>\n")
    with pytest.raises(ThemeCustomizeError, match="TARGET_AMBIGUOUS"):
        patch_file("wiki", rel, "<div>test</div>", "<div>changed</div>")

    # Target not found (mid-line / internal whitespace is not fuzzy-matched)
    with pytest.raises(ThemeCustomizeError, match="TARGET_NOT_FOUND") as missing:
        patch_file("wiki", rel, "<nonexistent>", "<div>changed</div>")
    assert "whole-line trim" in str(missing.value)
    assert "Re-read" in str(missing.value)

    with pytest.raises(ThemeCustomizeError, match="TARGET_NOT_FOUND") as mid_ws:
        patch_file("wiki", rel, "<div>  test  </div>", "<div>changed</div>")
    assert "internal or mid-line" in str(mid_ws.value)

    # CRLF normalization match mode (target has CRLF; on-disk text is LF after read)
    write_file("wiki", rel, "line1\nKEEP\nline3\n")
    crlf = patch_file("wiki", rel, "KEEP\r\n", "CHANGED\n")
    assert crlf["match_mode"] == "crlf"
    assert "CHANGED" in read_file("wiki", rel)


def test_service_revert_and_revision_cap(site_ready):
    from services.theme_customize_service import (
        ThemeCustomizeError,
        delete,
        fork,
        read_file,
        reset,
        revert_file,
        write_file,
    )

    fork("wiki", "basekit")
    rel = "partials/nav.twig"
    write_file("wiki", rel, "v1\n")
    write_file("wiki", rel, "v2\n")

    # Revert restores v1
    rev = revert_file("wiki", rel)
    assert rev["reverted"] is True
    assert read_file("wiki", rel) == "v1\n"

    # Revert again restores original initial from basekit
    revert_file("wiki", rel)
    assert "{# nav #}" in read_file("wiki", rel)

    # Revert when no history raises error
    with pytest.raises(ThemeCustomizeError, match="NO_REVISION"):
        revert_file("wiki", rel)

    from services.theme_customize_service import _rev_key, _site_revisions_root

    # Check capping at 10
    for i in range(15):
        write_file("wiki", rel, f"version_{i}\n")

    key_dir = _site_revisions_root("wiki") / _rev_key(rel)
    assert len(list(key_dir.glob("*.txt"))) == 10

    # Reset clears revisions
    reset("wiki")
    with pytest.raises(ThemeCustomizeError, match="NO_REVISION"):
        revert_file("wiki", rel)

    # Delete clears revisions
    write_file("wiki", rel, "v_new\n")
    write_file("wiki", rel, "v_newer\n")
    delete("wiki")
    fork("wiki", "basekit")
    with pytest.raises(ThemeCustomizeError, match="NO_REVISION"):
        revert_file("wiki", rel)


def test_service_reset_file_restores_from_parent(site_ready, fixture_themes):
    from services.theme_customize_service import (
        ThemeCustomizeError,
        fork,
        read_file,
        reset_file,
        write_file,
    )

    fork("wiki", "basekit")
    rel = "partials/nav.twig"
    parent_content = (fixture_themes / "basekit" / "partials" / "nav.twig").read_text(
        encoding="utf-8"
    )
    write_file("wiki", rel, "{# mangled #}\n")
    assert read_file("wiki", rel) == "{# mangled #}\n"

    result = reset_file("wiki", rel)
    assert result["ok"] is True
    assert result["restored"] is True
    assert result["path"] == rel
    assert result["parent"] == "basekit"
    assert result["bytes"] > 0
    assert read_file("wiki", rel) == parent_content

    # Recreate if deleted from custom tree
    from services.theme_customize_service import site_theme_root

    (site_theme_root("wiki") / "partials" / "nav.twig").unlink()
    reset_file("wiki", rel)
    assert read_file("wiki", rel) == parent_content

    with pytest.raises(ThemeCustomizeError, match="allowlist|theme.json"):
        reset_file("wiki", "theme.json")

    with pytest.raises(ThemeCustomizeError, match="No parent original"):
        reset_file("wiki", "partials/only-in-custom.twig")


def test_service_validate_stamps_severity(site_ready):
    from services.theme_customize_service import fork, validate

    fork("wiki", "basekit")
    body = validate("wiki")
    assert "ok" in body
    for err in body["errors"]:
        assert err["severity"] == "error"
    for warn in body["warnings"]:
        assert warn["severity"] == "warning"


def test_themes_root_dynamic_after_early_service_import(
    isolated_content, tmp_path, monkeypatch
):
    """Regression: theme services must not keep a stale ``themes_root`` alias.

    Full-suite collection/import order can load theme services before fixtures
    monkeypatch ``social_preview.themes_root``. Resolving through the module
    keeps synthetic fixture themes (e.g. ``basekit``) visible.
    """
    # Import *before* patching — historical failure mode with ``from … import themes_root``.
    import services.social_preview as social_preview
    import services.theme_customize_service as tcs
    import services.theme_style_service as tss
    from services.site_service import create_site, ensure_sites_initialized

    root = tmp_path / "themes-early-import"
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
        "{# base #}\n", encoding="utf-8"
    )
    (base / "partials" / "nav.twig").write_text("{# nav #}\n", encoding="utf-8")
    (base / "assets" / "css" / "styles.css").write_text(
        "body{}\n", encoding="utf-8"
    )

    monkeypatch.setattr(social_preview, "themes_root", lambda: root)
    monkeypatch.setattr(social_preview, "install_active_theme", lambda: "basekit")

    ensure_sites_initialized()
    create_site("wiki", "Wiki", theme="basekit")

    resolved = tcs.resolve_theme_dir("wiki", "basekit")
    assert resolved == base.resolve()

    # theme_style_service.font_registry_path() also calls themes_root()
    assert social_preview.themes_root() == root
    _ = tss.font_registry_path()

    result = tcs.fork("wiki", "basekit")
    assert result["parent"] == "basekit"
    assert result["theme"] == "custom"
