"""Publish POST /api/publish/export-zip — build + browser zip download."""

from __future__ import annotations

import io
import shutil
import zipfile

import pytest


@pytest.fixture(autouse=True)
def _clear_publish_runs():
    from services.publish_deploy import clear_runs

    clear_runs()
    yield
    clear_runs()


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


def test_export_zip_unauthenticated(client, isolated_content):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    resp = client.post("/api/publish/export-zip", json={"site": "default"})
    assert resp.status_code == 401


def test_export_zip_unknown_site(authed_client, isolated_content):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    resp = authed_client.post(
        "/api/publish/export-zip",
        json={"site": "nosuchsite"},
    )
    assert resp.status_code == 404


def test_export_zip_agent_forbidden(authed_client, isolated_content, agent_key):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    resp = authed_client.post(
        "/api/publish/export-zip",
        json={"site": "default"},
        headers={"Authorization": f"Bearer {agent_key}"},
    )
    assert resp.status_code == 403
    assert "human" in resp.json()["detail"].lower()


def test_export_zip_success_returns_attachment(
    authed_client, isolated_content, monkeypatch, tmp_path
):
    """Successful build returns application/zip with Content-Disposition."""
    from services.site_service import ensure_sites_initialized
    from services import publish_deploy as pd

    ensure_sites_initialized()

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html><body>ok</body></html>", encoding="utf-8")
    assets = dist / "assets"
    assets.mkdir()
    (assets / "app.css").write_text("body{}", encoding="utf-8")

    monkeypatch.setattr(
        pd,
        "resolve_build_paths",
        lambda: {
            "repo_root": tmp_path,
            "build_sh": tmp_path / "build.sh",
            "cli_dir": tmp_path,
            "dist_dir": dist,
        },
    )

    async def fake_build(site_id, domain, vault, *, log_line=None):
        assert site_id == "default"
        if log_line:
            log_line("fake build ok")
        return dist

    monkeypatch.setattr(pd, "build_site_dist", fake_build)

    resp = authed_client.post(
        "/api/publish/export-zip",
        json={"site": "default"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers.get("content-type", "").startswith("application/zip")
    disp = resp.headers.get("content-disposition", "")
    assert "attachment" in disp
    assert "default-static.zip" in disp

    raw = resp.content
    assert raw and len(raw) > 0
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = sorted(zf.namelist())
        assert "index.html" in names
        assert "assets/app.css" in names
        assert zf.read("index.html").decode() == "<html><body>ok</body></html>"


def test_export_zip_works_without_publish_host(
    authed_client, isolated_content, monkeypatch, tmp_path
):
    """Export does not require a configured publish target."""
    from services.site_service import ensure_sites_initialized
    from services import publish_deploy as pd

    ensure_sites_initialized()
    # default site has no publish block → configured false

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("x", encoding="utf-8")

    monkeypatch.setattr(
        pd,
        "resolve_build_paths",
        lambda: {
            "repo_root": tmp_path,
            "build_sh": tmp_path / "build.sh",
            "cli_dir": tmp_path,
            "dist_dir": dist,
        },
    )

    async def fake_build(site_id, domain, vault, *, log_line=None):
        return dist

    monkeypatch.setattr(pd, "build_site_dist", fake_build)

    resp = authed_client.post("/api/publish/export-zip", json={"site": "default"})
    assert resp.status_code == 200, resp.text
    assert len(resp.content) > 0


def test_export_zip_failed_build_no_bogus_zip(
    authed_client, isolated_content, monkeypatch, tmp_path
):
    """Failed build returns JSON error — not an empty/partial zip."""
    from services.site_service import ensure_sites_initialized
    from services import publish_deploy as pd
    from services.publish_providers import PublishDeployError

    ensure_sites_initialized()

    async def boom(site_id, domain, vault, *, log_line=None):
        raise PublishDeployError("build.sh exited with code 1")

    monkeypatch.setattr(pd, "build_site_dist", boom)

    resp = authed_client.post("/api/publish/export-zip", json={"site": "default"})
    assert resp.status_code == 400
    assert resp.headers.get("content-type", "").startswith("application/json")
    detail = resp.json()["detail"].lower()
    assert "build.sh" in detail or "exited" in detail
    # Body must not look like a zip (PK magic)
    assert not resp.content.startswith(b"PK")


def test_export_zip_empty_dist_rejected(
    authed_client, isolated_content, monkeypatch, tmp_path
):
    from services.site_service import ensure_sites_initialized
    from services import publish_deploy as pd

    ensure_sites_initialized()

    dist = tmp_path / "dist"
    dist.mkdir()

    async def fake_build(site_id, domain, vault, *, log_line=None):
        # Simulate a build that left an empty tree (build_site_dist would
        # normally reject this; exercise zip_dist_tree guard via export path).
        return dist

    monkeypatch.setattr(pd, "build_site_dist", fake_build)

    resp = authed_client.post("/api/publish/export-zip", json={"site": "default"})
    assert resp.status_code == 400
    assert "no files" in resp.json()["detail"].lower()
    assert not resp.content.startswith(b"PK")


def test_zip_dist_tree_unit(tmp_path):
    from services.publish_deploy import zip_dist_tree
    from services.publish_providers import PublishDeployError

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "a.html").write_text("a", encoding="utf-8")
    nested = dist / "css"
    nested.mkdir()
    (nested / "b.css").write_text("b", encoding="utf-8")

    data = zip_dist_tree(dist)
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        assert sorted(zf.namelist()) == ["a.html", "css/b.css"]

    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(PublishDeployError, match="no files"):
        zip_dist_tree(empty)


def test_export_busy_when_publish_running(
    authed_client, isolated_content, monkeypatch, tmp_path
):
    from services.site_service import ensure_sites_initialized
    from services import publish_deploy as pd

    ensure_sites_initialized()
    pd.begin_run("default")

    resp = authed_client.post("/api/publish/export-zip", json={"site": "default"})
    assert resp.status_code == 409
    assert "publish already running" in resp.json()["detail"].lower()
