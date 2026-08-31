"""Tests for the theme install .zip endpoint."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any, Dict

import pytest


def _build_zip(files: Dict[str, str]) -> bytes:
    """Build a zip archive in memory from a dict of {path: content}."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, content in files.items():
            zf.writestr(path, content)
    return buf.getvalue()


@pytest.fixture
def fixture_themes(tmp_path, monkeypatch):
    """Tiny install themes root isolated per test."""
    root = tmp_path / "themes"
    root.mkdir()
    import services.social_preview as social_preview

    monkeypatch.setattr(social_preview, "themes_root", lambda: root)
    monkeypatch.setattr(social_preview, "install_active_theme", lambda: "basekit")
    return root


@pytest.fixture
def admin_client(authed_client):
    """Authed client with an admin session already set up."""
    return authed_client


def _install_zip(client, zip_bytes: bytes, overwrite: bool = False):
    return client.post(
        "/api/themes/install",
        data={"overwrite": "true" if overwrite else "false"},
        files={"file": ("theme.zip", io.BytesIO(zip_bytes), "application/zip")},
    )


def _valid_theme_files(name: str = "Imported Theme", slug: str = "imported") -> Dict[str, str]:
    return {
        "theme.json": json.dumps(
            {
                "name": name,
                "slug": slug,
                "version": "1.2.3",
                "type": "native",
            }
        ),
        "templates/index.html.twig": "{# index #}\n",
        "templates/post.html.twig": "{# post #}\n",
        "templates/page.html.twig": "{# page #}\n",
        "templates/search.html.twig": "{# search #}\n",
        f"assets/css/skin-{slug}.css": ":root { --traven-bg: #fff; }\n",
    }


def test_install_happy_path(fixture_themes, admin_client):
    files = _valid_theme_files()
    zip_bytes = _build_zip(files)
    resp = _install_zip(admin_client, zip_bytes)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["slug"] == "imported"
    assert data["name"] == "Imported Theme"
    assert data["version"] == "1.2.3"
    assert data["overwrote"] is False
    assert isinstance(data["warnings"], list)
    assert len(data["warnings"]) == 0

    assert (fixture_themes / "imported" / "theme.json").is_file()
    assert (fixture_themes / "imported" / "templates" / "index.html.twig").is_file()


def test_install_single_folder_prefix(fixture_themes, admin_client):
    """GitHub-style download: theme.json under a single top-level folder."""
    inner = _valid_theme_files(slug="folder-theme")
    files = {f"repo-main/{k}": v for k, v in inner.items()}
    zip_bytes = _build_zip(files)
    resp = _install_zip(admin_client, zip_bytes)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["slug"] == "folder-theme"
    assert (fixture_themes / "folder-theme" / "theme.json").is_file()


def test_install_conflict_and_overwrite(fixture_themes, admin_client):
    files = _valid_theme_files(name="Original", slug="dupe")
    resp = _install_zip(admin_client, _build_zip(files))
    assert resp.status_code == 200

    new_files = _valid_theme_files(name="Updated", slug="dupe")
    resp2 = _install_zip(admin_client, _build_zip(new_files), overwrite=False)
    assert resp2.status_code == 409, resp2.text
    detail = resp2.json()["detail"]
    assert "dupe" in detail

    resp3 = _install_zip(admin_client, _build_zip(new_files), overwrite=True)
    assert resp3.status_code == 200, resp3.text
    data = resp3.json()
    assert data["overwrote"] is True
    assert data["name"] == "Updated"
    assert (fixture_themes / "dupe" / "theme.json").is_file()


def test_install_slug_derived_from_name(fixture_themes, admin_client):
    files = _valid_theme_files()
    del files["theme.json"]
    files["theme.json"] = json.dumps({"name": "My Great Theme"})
    zip_bytes = _build_zip(files)
    resp = _install_zip(admin_client, zip_bytes)
    assert resp.status_code == 200, resp.text
    assert resp.json()["slug"] == "my-great-theme"


def test_install_missing_manifest(fixture_themes, admin_client):
    files = {"templates/index.html.twig": "{# index #}\n"}
    resp = _install_zip(admin_client, _build_zip(files))
    assert resp.status_code == 400, resp.text
    assert "theme.json" in resp.json()["detail"]


def test_install_invalid_json(fixture_themes, admin_client):
    files = {"theme.json": "{not json"}
    resp = _install_zip(admin_client, _build_zip(files))
    assert resp.status_code == 400, resp.text
    assert "theme.json" in resp.json()["detail"]


def test_install_reserved_slug_custom(fixture_themes, admin_client):
    files = _valid_theme_files(slug="custom")
    resp = _install_zip(admin_client, _build_zip(files))
    assert resp.status_code == 400, resp.text
    assert "reserved" in resp.json()["detail"].lower()


def test_install_underscored_slug(fixture_themes, admin_client):
    files = _valid_theme_files(slug="_hidden")
    resp = _install_zip(admin_client, _build_zip(files))
    assert resp.status_code == 400, resp.text


def test_install_zip_slip_traversal(fixture_themes, admin_client):
    files = _valid_theme_files()
    files["../evil.txt"] = "pwned"
    resp = _install_zip(admin_client, _build_zip(files))
    assert resp.status_code == 400, resp.text
    assert (fixture_themes.parent / "evil.txt").exists() is False


def test_install_symlink_entry(fixture_themes, admin_client):
    """Symlinks must be rejected even if they point inside the archive."""
    files = _valid_theme_files()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, content in files.items():
            zf.writestr(path, content)
        # Add a symlink entry pointing at theme.json
        info = zipfile.ZipInfo("link.json")
        info.external_attr = (0o120777 << 16) | 0o777
        zf.writestr(info, "theme.json")
    resp = _install_zip(admin_client, buf.getvalue())
    assert resp.status_code == 400, resp.text
    assert "symlink" in resp.json()["detail"].lower()


def test_install_wrong_file_type(fixture_themes, admin_client):
    resp = admin_client.post(
        "/api/themes/install",
        files={"file": ("theme.txt", io.BytesIO(b"not a zip"), "text/plain")},
    )
    assert resp.status_code == 400, resp.text
    assert ".zip" in resp.json()["detail"]


def test_install_unauthenticated(client, fixture_themes):
    files = _valid_theme_files()
    resp = _install_zip(client, _build_zip(files))
    assert resp.status_code in (401, 403)


def test_install_non_admin_forbidden(fixture_themes, authed_client, login_author):
    login_author(capabilities=["write:posts"], username="install-denied")
    files = _valid_theme_files()
    resp = _install_zip(authed_client, _build_zip(files))
    assert resp.status_code == 403, resp.text
    assert resp.json()["detail"] == "missing_capability: write:theme"


def test_install_warnings_for_missing_assets(fixture_themes, admin_client):
    files = {
        "theme.json": json.dumps({"name": "Bare", "slug": "bare"}),
    }
    resp = _install_zip(admin_client, _build_zip(files))
    assert resp.status_code == 200, resp.text
    warnings = resp.json()["warnings"]
    assert any("skin" in w for w in warnings)
    assert any("template" in w for w in warnings)


def _build_zip_with_dir_entries(files: Dict[str, str], trailing_slash: bool = True) -> bytes:
    """Build a zip with explicit directory entries.

    Some zip tools use trailing slashes, some rely on external_attr. We test
    both shapes.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        dirs_seen: set[str] = set()
        for path in files:
            parent = Path(path).parent.as_posix()
            while parent and parent != "." and parent not in dirs_seen:
                dirs_seen.add(parent)
                arcname = parent + "/" if trailing_slash else parent
                info = zipfile.ZipInfo(arcname)
                info.external_attr = (0o040755 << 16)  # directory mode
                zf.writestr(info, "")
                parent = Path(parent).parent.as_posix()
            zf.writestr(path, files[path])
    return buf.getvalue()


@pytest.mark.parametrize("trailing_slash", [True, False])
def test_install_directory_entries(fixture_themes, admin_client, trailing_slash):
    """Regression: zip tools that write directory entries explicitly."""
    files = _valid_theme_files(slug="dirmode")
    zip_bytes = _build_zip_with_dir_entries(files, trailing_slash=trailing_slash)
    resp = _install_zip(admin_client, zip_bytes)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["slug"] == "dirmode"
    assert (fixture_themes / "dirmode" / "assets" / "css" / "skin-dirmode.css").is_file()
    assert (fixture_themes / "dirmode" / "theme.json").is_file()


def test_list_installed_themes_api(fixture_themes, admin_client):
    manifest = {
        "name": "Listed Theme",
        "version": "2.0.0",
        "author": "Pen",
        "description": "For admin list",
        "color_mode": "light",
        "supports": ["blog"],
    }
    theme_dir = fixture_themes / "listed"
    theme_dir.mkdir()
    (theme_dir / "theme.json").write_text(json.dumps(manifest), encoding="utf-8")
    (theme_dir / "screenshot.webp").write_bytes(b"RIFF")

    resp = admin_client.get("/api/themes")
    assert resp.status_code == 200, resp.text
    slugs = [t["slug"] for t in resp.json()["themes"]]
    assert "listed" in slugs
    listed = next(t for t in resp.json()["themes"] if t["slug"] == "listed")
    assert listed["name"] == "Listed Theme"
    assert listed["has_screenshot"] is True
    assert listed["color_mode"] == "light"


def _install_from_url(client, url: str, overwrite: bool = False):
    return client.post(
        "/api/themes/install-from-url",
        json={"url": url, "overwrite": overwrite},
    )


def test_install_from_url_happy_path(fixture_themes, admin_client, monkeypatch):
    zip_bytes = _build_zip(_valid_theme_files(slug="remote-theme"))

    def fake_install_from_url(url: str, overwrite: bool = False):
        from services.theme_install_service import install_from_zip

        return install_from_zip(zip_bytes, overwrite=overwrite)

    monkeypatch.setattr(
        "routers.theme_install.install_from_url",
        fake_install_from_url,
    )

    resp = _install_from_url(
        admin_client,
        "https://github.com/acme/remote-theme.git",
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["slug"] == "remote-theme"
    assert (fixture_themes / "remote-theme" / "theme.json").is_file()


def test_install_from_url_conflict_and_overwrite(fixture_themes, admin_client, monkeypatch):
    zip_bytes = _build_zip(_valid_theme_files(name="Original", slug="remote-dupe"))

    def fake_install_from_url(url: str, overwrite: bool = False):
        from services.theme_install_service import install_from_zip

        return install_from_zip(zip_bytes, overwrite=overwrite)

    monkeypatch.setattr(
        "routers.theme_install.install_from_url",
        fake_install_from_url,
    )

    resp = _install_from_url(admin_client, "https://github.com/acme/remote-dupe.git")
    assert resp.status_code == 200

    resp2 = _install_from_url(
        admin_client,
        "https://github.com/acme/remote-dupe.git",
        overwrite=False,
    )
    assert resp2.status_code == 409, resp2.text
    assert "remote-dupe" in resp2.json()["detail"]

    resp3 = _install_from_url(
        admin_client,
        "https://github.com/acme/remote-dupe.git",
        overwrite=True,
    )
    assert resp3.status_code == 200, resp3.text
    assert resp3.json()["overwrote"] is True


def test_install_from_url_invalid_url(fixture_themes, admin_client):
    resp = _install_from_url(admin_client, "http://github.com/acme/repo.git")
    assert resp.status_code == 400, resp.text
    assert "HTTPS" in resp.json()["detail"]


def test_install_from_url_unauthenticated(client, fixture_themes):
    resp = _install_from_url(client, "https://github.com/acme/repo.git")
    assert resp.status_code == 401


def test_install_from_url_non_admin_forbidden(fixture_themes, authed_client, login_author):
    login_author(capabilities=["read"])
    resp = _install_from_url(authed_client, "https://github.com/acme/repo.git")
    assert resp.status_code == 403
