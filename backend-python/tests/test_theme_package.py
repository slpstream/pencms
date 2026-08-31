"""Theme packaging / export — service and REST."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest


from services.theme_install_service import install_from_zip
from services.theme_package_service import (
    PACKAGED_CSS_MARKER_START,
    build_site_package_zip,
    export_installed_theme_zip,
    install_site_package,
)


def _build_zip(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, content in files.items():
            zf.writestr(path, content)
    return buf.getvalue()


@pytest.fixture
def isolated_content(temp_data_root, monkeypatch):
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
def package_theme_root(tmp_path, monkeypatch):
    root = tmp_path / "themes"
    base = root / "basekit"
    (base / "templates").mkdir(parents=True)
    (base / "partials").mkdir(parents=True)
    (base / "assets" / "css").mkdir(parents=True)
    style_schema = {
        "dark_scope": {"selector": ".cm-wysiwym-dark"},
        "groups": [
            {
                "id": "colors",
                "label": "Colors",
                "fields": [
                    {
                        "id": "bg",
                        "label": "Background",
                        "type": "color",
                        "var": "--traven-bg",
                        "default": "#ffffff",
                        "dark_default": "#0f172a",
                    },
                    {
                        "id": "font-body",
                        "label": "Body Font",
                        "type": "select",
                        "var": "--traven-font-body",
                        "default": "'Roboto', sans-serif",
                        "options": [
                            {"value": "", "label": "Theme default"},
                            {"value": "'Roboto', sans-serif", "label": "Roboto"},
                        ],
                    },
                ],
            }
        ],
    }
    (base / "theme.json").write_text(
        json.dumps(
            {
                "name": "Base Kit",
                "version": "1.0.0",
                "type": "native",
                "license": "MIT",
                "style": style_schema,
            }
        ),
        encoding="utf-8",
    )
    (base / "templates" / "index.html.twig").write_text("{# index #}\n", encoding="utf-8")
    (base / "templates" / "post.html.twig").write_text("{# post #}\n", encoding="utf-8")
    (base / "templates" / "page.html.twig").write_text("{# page #}\n", encoding="utf-8")
    (base / "templates" / "search.html.twig").write_text("{# search #}\n", encoding="utf-8")
    (base / "assets" / "css" / "skin-basekit.css").write_text(
        ":root { --traven-bg: #ffffff; }\n", encoding="utf-8"
    )

    import services.social_preview as social_preview

    monkeypatch.setattr(social_preview, "themes_root", lambda: root)
    monkeypatch.setattr(social_preview, "install_active_theme", lambda: "basekit")
    return root


@pytest.fixture
def font_registry(tmp_path, monkeypatch):
    fonts_dir = tmp_path / "fonts"
    fonts_dir.mkdir()
    woff = fonts_dir / "roboto-400.woff2"
    woff.write_bytes(b"woff2-placeholder")
    registry = {
        "roboto": {
            "label": "Roboto",
            "family": "Roboto",
            "stack": "'Roboto', sans-serif",
            "license": "Apache-2.0",
            "files": {"400": "roboto-400.woff2"},
        }
    }
    (fonts_dir / "fonts.json").write_text(json.dumps(registry), encoding="utf-8")
    import services.theme_style_service as tss
    import services.theme_package_service as tps

    monkeypatch.setattr(tss, "font_registry_path", lambda: fonts_dir / "fonts.json")
    monkeypatch.setattr(tps, "font_registry_path", lambda: fonts_dir / "fonts.json")
    return fonts_dir


@pytest.fixture
def site_ready(isolated_content, package_theme_root, font_registry):
    from services.site_service import create_site, ensure_sites_initialized, update_site

    ensure_sites_initialized()
    create_site("wiki", "Wiki", theme="basekit")
    update_site(
        "wiki",
        style_overrides={
            "theme": "basekit",
            "values": {
                "bg": "#abcdef",
                "font-body": "'Roboto', sans-serif",
            },
            "dark": {"bg": "#112233"},
        },
    )
    return isolated_content


@pytest.fixture(autouse=True)
def _mock_screenshot_capture(monkeypatch):
    """Default: successful screenshot capture for all package tests."""

    def _fake_capture(site_id: str, dest: Path):
        from PIL import Image

        dest.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (2, 2), color=(200, 100, 50)).save(dest, "WEBP")
        return None

    monkeypatch.setattr(
        "services.theme_package_service.capture_theme_card_webp",
        _fake_capture,
    )


def _read_zip_manifest(zip_bytes: bytes, slug: str) -> dict:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        raw = zf.read(f"{slug}/theme.json").decode("utf-8")
        return json.loads(raw)


def _read_zip_skin(zip_bytes: bytes, slug: str) -> str:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        return zf.read(f"{slug}/assets/css/skin-basekit.css").decode("utf-8")


def test_package_bakes_style_and_strips_fork_metadata(site_ready):
    from services.theme_customize_service import fork

    fork("wiki", parent_slug="basekit")
    data, _filename, _warnings = build_site_package_zip(
        "wiki",
        "exported-kit",
        name="Exported Kit",
        author="Tester",
    )
    manifest = _read_zip_manifest(data, "exported-kit")
    assert manifest.get("parent") is None
    assert manifest.get("origin") is None
    assert manifest.get("customized_at") is None
    assert manifest["slug"] == "exported-kit"
    assert manifest["name"] == "Exported Kit"
    assert manifest["author"] == "Tester"
    assert manifest["license"] == "MIT"

    bg_field = manifest["style"]["groups"][0]["fields"][0]
    assert bg_field["default"] == "#abcdef"
    assert bg_field["dark_default"] == "#112233"

    skin = _read_zip_skin(data, "exported-kit")
    assert PACKAGED_CSS_MARKER_START in skin
    assert "#abcdef" in skin
    assert "#112233" in skin


def test_package_vendors_registry_fonts(site_ready):
    data, _, _ = build_site_package_zip("wiki", "font-kit", name="Font Kit")
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = zf.namelist()
        assert "font-kit/assets/fonts/roboto-400.woff2" in names
        skin = zf.read("font-kit/assets/css/skin-basekit.css").decode("utf-8")
        assert "PenCMS packaged registry fonts" in skin
        assert "@font-face" in skin
        assert "url('../fonts/roboto-400.woff2')" in skin
    manifest = _read_zip_manifest(data, "font-kit")
    assert manifest.get("supports", {}).get("custom_fonts") is True


def test_package_zip_round_trips_through_install(site_ready, package_theme_root):
    data, _, _ = build_site_package_zip("wiki", "roundtrip", name="Round Trip")
    result = install_from_zip(data, overwrite=False)
    assert result["slug"] == "roundtrip"
    assert (package_theme_root / "roundtrip" / "theme.json").is_file()


def test_package_install_writes_new_slug(site_ready, package_theme_root):
    result = install_site_package(
        "wiki",
        "saved-kit",
        name="Saved Kit",
        author="Ops",
        overwrite=False,
    )
    assert result["slug"] == "saved-kit"
    assert result["name"] == "Saved Kit"
    assert (package_theme_root / "saved-kit" / "theme.json").is_file()


def test_package_install_conflict(site_ready):
    install_site_package("wiki", "dupe", name="One", overwrite=False)
    with pytest.raises(Exception) as exc:
        install_site_package("wiki", "dupe", name="Two", overwrite=False)
    assert "already exists" in str(exc.value).lower()


def test_raw_export_does_not_bake(site_ready):
    data, filename = export_installed_theme_zip("basekit")
    assert filename == "basekit.zip"
    manifest = _read_zip_manifest(data, "basekit")
    bg_field = manifest["style"]["groups"][0]["fields"][0]
    assert bg_field["default"] == "#ffffff"
    skin = _read_zip_skin(data, "basekit")
    assert PACKAGED_CSS_MARKER_START not in skin


def test_export_custom_slug_rejected():
    with pytest.raises(Exception) as exc:
        export_installed_theme_zip("custom")
    assert "reserved" in str(exc.value).lower()


def test_package_zip_unauthenticated(client, site_ready):
    resp = client.post(
        "/api/sites/wiki/theme/package-zip",
        json={"slug": "x"},
    )
    assert resp.status_code == 401


def test_package_zip_agent_forbidden(authed_client, site_ready, agent_key):
    resp = authed_client.post(
        "/api/sites/wiki/theme/package-zip",
        json={"slug": "x"},
        headers={"Authorization": f"Bearer {agent_key}"},
    )
    assert resp.status_code == 403
    assert "human" in resp.json()["detail"].lower()


def test_package_zip_success(authed_client, site_ready):
    resp = authed_client.post(
        "/api/sites/wiki/theme/package-zip",
        json={"slug": "api-export", "name": "API Export", "author": "Admin"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers.get("content-type", "").startswith("application/zip")
    assert "attachment" in resp.headers.get("content-disposition", "")
    assert resp.content.startswith(b"PK")
    manifest = _read_zip_manifest(resp.content, "api-export")
    assert manifest["slug"] == "api-export"


def test_package_install_api_conflict(authed_client, site_ready):
    first = authed_client.post(
        "/api/sites/wiki/theme/package-install",
        json={"slug": "api-dupe", "name": "One"},
    )
    assert first.status_code == 200, first.text

    second = authed_client.post(
        "/api/sites/wiki/theme/package-install",
        json={"slug": "api-dupe", "name": "Two"},
    )
    assert second.status_code == 409, second.text


def test_raw_export_zip_api(authed_client, site_ready):
    resp = authed_client.get("/api/themes/basekit/export-zip")
    assert resp.status_code == 200, resp.text
    assert resp.headers.get("content-type", "").startswith("application/zip")
    manifest = _read_zip_manifest(resp.content, "basekit")
    assert manifest["name"] == "Base Kit"


def test_package_includes_recaptured_screenshot(site_ready, package_theme_root):
    stale = package_theme_root / "basekit" / "screenshot.webp"
    stale.write_bytes(b"stale-parent-shot")

    data, _, warnings = build_site_package_zip("wiki", "with-shot", name="With Shot")
    assert not warnings
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        assert "with-shot/screenshot.webp" in zf.namelist()
        shot = zf.read("with-shot/screenshot.webp")
    assert shot != b"stale-parent-shot"
    assert len(shot) > 20


def test_package_omits_screenshot_when_capture_fails(site_ready, monkeypatch):
    def _fail(_site_id, _dest):
        return "Screenshot capture skipped: Preview origin did not respond"

    monkeypatch.setattr(
        "services.theme_package_service.capture_theme_card_webp",
        _fail,
    )

    data, _, warnings = build_site_package_zip("wiki", "no-shot", name="No Shot")
    assert warnings
    assert any("screenshot" in w.lower() for w in warnings)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        assert "no-shot/screenshot.webp" not in zf.namelist()


def test_package_zip_api_returns_warning_header(site_ready, monkeypatch, authed_client):
    def _fail(_site_id, _dest):
        return "Screenshot capture skipped: browser unavailable"

    monkeypatch.setattr(
        "services.theme_package_service.capture_theme_card_webp",
        _fail,
    )

    resp = authed_client.post(
        "/api/sites/wiki/theme/package-zip",
        json={"slug": "warn-export", "name": "Warn"},
    )
    assert resp.status_code == 200, resp.text
    assert "screenshot" in resp.headers.get("X-Pen-Package-Warnings", "").lower()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        assert "warn-export/screenshot.webp" not in zf.namelist()


def test_package_zip_api_unicode_warning_header_is_latin1(
    site_ready, monkeypatch, authed_client
):
    """Inspect hints include em dashes; HTTP headers must still encode as latin-1."""

    def _fail(_site_id, _dest):
        return (
            "Screenshot capture skipped: Preview origin did not respond: "
            "Page.goto: Timeout 15000ms exceeded.\nCall log:\n"
            "  - navigating to http://127.0.0.1:8009/blog/\n"
            "(If PHP runs via `php -S`, start it with PHP_CLI_SERVER_WORKERS>=4 "
            "\u2014 the admin /api proxy occupies a worker.)"
        )

    monkeypatch.setattr(
        "services.theme_package_service.capture_theme_card_webp",
        _fail,
    )

    resp = authed_client.post(
        "/api/sites/wiki/theme/package-zip",
        json={"slug": "unicode-warn", "name": "Warn"},
    )
    assert resp.status_code == 200, resp.text
    header = resp.headers.get("X-Pen-Package-Warnings", "")
    assert header
    header.encode("latin-1")
    assert "\n" not in header
    assert "\u2014" not in header
    assert "screenshot" in header.lower()
