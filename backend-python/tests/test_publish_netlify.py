"""Netlify publish adapter — zip upload deploy (S13). Pro overlay."""

from __future__ import annotations

import shutil
import zipfile
from io import BytesIO
from pathlib import Path

import httpx
import pytest

pytestmark = pytest.mark.pro
pytest.importorskip("pencms_pro", reason="cloud publish is Pro overlay")


@pytest.fixture
def isolated_content(temp_data_root, monkeypatch):
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


def _make_dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>hi</html>", encoding="utf-8")
    (dist / "style.css").write_text("body{}", encoding="utf-8")
    return dist


@pytest.mark.asyncio
async def test_netlify_deploy_zip_upload(tmp_path, monkeypatch):
    from pencms_pro.publish_providers.netlify import NetlifyPublishProvider

    dist = _make_dist(tmp_path)
    calls: list[tuple[str, str]] = []
    poll_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, str(request.url)))
        path = request.url.path
        if request.method == "POST" and path.endswith("/deploys"):
            assert request.headers.get("content-type") == "application/zip"
            raw = request.content
            assert raw and len(raw) > 20
            with zipfile.ZipFile(BytesIO(raw)) as zf:
                names = set(zf.namelist())
            assert "index.html" in names
            assert "style.css" in names
            assert not any(n.startswith("dist/") for n in names)
            return httpx.Response(
                200,
                json={
                    "id": "dep_xyz",
                    "state": "uploaded",
                    "ssl_url": "https://mysite.netlify.app",
                },
            )
        if request.method == "GET" and "/deploys/dep_xyz" in path:
            poll_count["n"] += 1
            if poll_count["n"] < 2:
                return httpx.Response(
                    200,
                    json={"id": "dep_xyz", "state": "processing"},
                )
            return httpx.Response(
                200,
                json={
                    "id": "dep_xyz",
                    "state": "ready",
                    "ssl_url": "https://mysite.netlify.app",
                    "url": "http://mysite.netlify.app",
                },
            )
        return httpx.Response(
            404, json={"message": f"unexpected {request.method} {path}"}
        )

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)
    monkeypatch.setattr(
        "pencms_pro.publish_providers.netlify.time.sleep", lambda *_a, **_k: None
    )

    provider = NetlifyPublishProvider()
    provider.configure(
        {"netlify_site_id": "site-uuid-123"},
        password="netlify_token_test",
        site_id="default",
    )
    logs: list[str] = []
    result = await provider.deploy(
        dist,
        force_full=True,
        upload_rels=[],
        removed=[],
        total_files=2,
        log_line=logs.append,
    )
    assert result == {"public_url": "https://mysite.netlify.app"}
    paths = [u for _, u in calls]
    assert any("/sites/site-uuid-123/deploys" in u for u in paths)
    assert any("/deploys/dep_xyz" in u for u in paths)


@pytest.mark.asyncio
async def test_netlify_test_auth_failure(monkeypatch):
    from pencms_pro.publish_providers.netlify import NetlifyPublishProvider

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Access Denied"})

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)

    provider = NetlifyPublishProvider()
    provider.configure(
        {"netlify_site_id": "site1"},
        password="bad_token",
        site_id="default",
    )
    result = await provider.test()
    assert result["success"] is False
    assert "denied" in (result.get("error") or "").lower() or "access" in (
        result.get("error") or ""
    ).lower()


def test_netlify_grant_enroll_and_agent_secret(
    authed_client, isolated_content, temp_data_root
):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    put = authed_client.put(
        "/api/publish/target",
        json={
            "site": "default",
            "provider": "netlify",
            "auth_method": "token",
            "netlify_site_id": "agent-site-id",
        },
    )
    assert put.status_code == 200, put.text

    enroll = authed_client.post(
        "/api/publish/grant",
        json={"site": "default", "password": "netlify_agent_token"},
    )
    assert enroll.status_code == 200, enroll.text
    body = enroll.json()
    assert body["enrolled"] is True
    assert body["auth_method"] == "token"
    assert body["has_ciphertext"] is True

    from services import publish_grants

    secret = publish_grants.load_password("default")
    assert secret == "netlify_agent_token"

    grant_file = temp_data_root / "data" / "publish-grants" / "default.enc"
    assert grant_file.is_file()

    get = authed_client.get("/api/publish/target", params={"site": "default"})
    assert get.json()["netlify_site_id"] == "agent-site-id"
    assert get.json()["agent_publish"] == "enrolled"


def test_netlify_test_uses_vault_header(
    authed_client, isolated_content, monkeypatch
):
    """POST /test with Netlify target + vault header reaches provider.test."""
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    authed_client.put(
        "/api/publish/target",
        json={
            "site": "default",
            "provider": "netlify",
            "auth_method": "token",
            "netlify_site_id": "mysite",
        },
    )

    async def fake_test(self):
        assert self._password == "netlify_from_header"
        return {"success": True, "latency_ms": 1}

    monkeypatch.setattr(
        "pencms_pro.publish_providers.netlify.NetlifyPublishProvider.test",
        fake_test,
    )

    resp = authed_client.post(
        "/api/publish/test",
        json={"site": "default"},
        headers={
            "X-Pen-Site-Id": "default",
            "X-Vault-Publish-Netlify-Token": "netlify_from_header",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True


def test_put_netlify_target(authed_client, isolated_content):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    put = authed_client.put(
        "/api/publish/target",
        json={
            "site": "default",
            "provider": "netlify",
            "auth_method": "token",
            "netlify_site_id": "demo-site.netlify.app",
            "public_url": "https://demo-site.netlify.app",
        },
    )
    assert put.status_code == 200, put.text
    body = put.json()
    assert body["configured"] is True
    assert body["provider"] == "netlify"
    assert body["auth_method"] == "token"
    assert body["netlify_site_id"] == "demo-site.netlify.app"
    assert body["host"] is None
    assert "token" not in body
    assert "api_key" not in body
    assert "password" not in body

    get = authed_client.get("/api/publish/target", params={"site": "default"})
    assert get.json() == body


def test_put_netlify_rejects_token(authed_client, isolated_content):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    resp = authed_client.put(
        "/api/publish/target",
        json={
            "site": "default",
            "provider": "netlify",
            "netlify_site_id": "site1",
            "token": "secret",
        },
    )
    assert resp.status_code == 400, resp.text


def test_put_netlify_requires_site_id(authed_client, isolated_content):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    resp = authed_client.put(
        "/api/publish/target",
        json={
            "site": "default",
            "provider": "netlify",
            "auth_method": "token",
        },
    )
    assert resp.status_code == 400, resp.text
