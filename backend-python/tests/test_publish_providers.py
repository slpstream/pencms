"""Publish provider registry + adapter seam (S10/S11)."""

from __future__ import annotations

import shutil

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


def test_get_provider_sftp_default():
    from services.publish_providers import SftpPublishProvider, get_provider

    p = get_provider(None)
    assert isinstance(p, SftpPublishProvider)
    assert p.id == "sftp"
    caps = p.capabilities()
    assert caps["incremental"] is True
    assert "password" in caps["auth_methods"]


@pytest.mark.pro
def test_get_provider_here_now_enabled():
    pytest.importorskip("pencms_pro", reason="cloud publish is Pro overlay")
    from pencms_pro.publish_providers.here_now import HereNowPublishProvider
    from services.publish_providers.registry import (
        _CATALOG,
        get_provider,
        register_publish_provider,
    )

    snapshot = list(_CATALOG)
    try:
        register_publish_provider(HereNowPublishProvider)
        p = get_provider("here_now")
        assert isinstance(p, HereNowPublishProvider)
        assert p.enabled is True
        caps = p.capabilities()
        assert caps["incremental"] is False
        assert caps["auth_methods"] == ["token"]
    finally:
        _CATALOG[:] = snapshot


@pytest.mark.pro
def test_get_provider_cloudflare_pages_enabled():
    pytest.importorskip("pencms_pro", reason="cloud publish is Pro overlay")
    from pencms_pro.publish_providers.cloudflare_pages import CloudflarePagesPublishProvider
    from services.publish_providers.registry import (
        _CATALOG,
        get_provider,
        register_publish_provider,
    )

    snapshot = list(_CATALOG)
    try:
        register_publish_provider(CloudflarePagesPublishProvider)
        p = get_provider("cloudflare_pages")
        assert isinstance(p, CloudflarePagesPublishProvider)
        assert p.enabled is True
        caps = p.capabilities()
        assert caps["incremental"] is False
        assert caps["auth_methods"] == ["token"]
    finally:
        _CATALOG[:] = snapshot


@pytest.mark.pro
def test_get_provider_vercel_enabled():
    pytest.importorskip("pencms_pro", reason="cloud publish is Pro overlay")
    from pencms_pro.publish_providers.vercel import VercelPublishProvider
    from services.publish_providers.registry import (
        _CATALOG,
        get_provider,
        register_publish_provider,
    )

    snapshot = list(_CATALOG)
    try:
        register_publish_provider(VercelPublishProvider)
        p = get_provider("vercel")
        assert isinstance(p, VercelPublishProvider)
        assert p.enabled is True
        caps = p.capabilities()
        assert caps["incremental"] is False
        assert caps["auth_methods"] == ["token"]
    finally:
        _CATALOG[:] = snapshot


@pytest.mark.pro
def test_get_provider_netlify_enabled():
    pytest.importorskip("pencms_pro", reason="cloud publish is Pro overlay")
    from pencms_pro.publish_providers.netlify import NetlifyPublishProvider
    from services.publish_providers.registry import (
        _CATALOG,
        get_provider,
        register_publish_provider,
    )

    snapshot = list(_CATALOG)
    try:
        register_publish_provider(NetlifyPublishProvider)
        p = get_provider("netlify")
        assert isinstance(p, NetlifyPublishProvider)
        assert p.enabled is True
        caps = p.capabilities()
        assert caps["incremental"] is False
        assert caps["auth_methods"] == ["token"]
    finally:
        _CATALOG[:] = snapshot


def test_get_provider_github_pages_enabled():
    from services.publish_providers import GithubPagesPublishProvider, get_provider

    p = get_provider("github_pages")
    assert isinstance(p, GithubPagesPublishProvider)
    assert p.enabled is True
    caps = p.capabilities()
    assert caps["incremental"] is False
    assert caps["auth_methods"] == ["token"]


def test_get_provider_unknown_raises():
    from services.publish_providers import UnknownPublishProviderError, get_provider

    with pytest.raises(UnknownPublishProviderError, match="Unknown"):
        get_provider("not_a_real_provider")


def test_list_providers_includes_enabled():
    from services.publish_providers import list_providers

    catalog = list_providers()
    by_id = {p["id"]: p for p in catalog}
    assert set(by_id) == {"sftp", "github_pages"}
    assert by_id["sftp"]["enabled"] is True
    assert by_id["github_pages"]["enabled"] is True
    assert len(catalog) == 2


def test_run_rejects_unknown_provider(authed_client, isolated_content, monkeypatch):
    """POST /run with an unknown provider id returns 400."""
    from services.publish_deploy import clear_runs

    clear_runs()
    monkeypatch.setattr(
        "routers.publish.get_publish_target",
        lambda site: {
            "site_id": "default",
            "configured": True,
            "provider": "azure_static_web",
            "host": "example.com",
            "port": 22,
            "username": "deploy",
            "remote_path": "/var/www/html",
            "auth_method": "password",
        },
    )
    resp = authed_client.post(
        "/api/publish/run",
        json={"site": "default", "password": "pw"},
    )
    assert resp.status_code == 400, resp.text
    detail = resp.json()["detail"].lower()
    assert "unknown" in detail or "azure" in detail
