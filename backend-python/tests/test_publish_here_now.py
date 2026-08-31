"""here.now publish adapter — create/update → upload → finalize (S11). Pro overlay."""

from __future__ import annotations

import hashlib
import json
import shutil
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


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _make_dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>hi</html>", encoding="utf-8")
    (dist / "style.css").write_text("body{}", encoding="utf-8")
    return dist


@pytest.mark.asyncio
async def test_here_now_deploy_create_upload_finalize(tmp_path, monkeypatch):
    from pencms_pro.publish_providers.here_now import HereNowPublishProvider

    dist = _make_dist(tmp_path)
    index_bytes = (dist / "index.html").read_bytes()
    css_bytes = (dist / "style.css").read_bytes()

    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, str(request.url)))
        path = request.url.path
        if request.method == "POST" and path == "/api/v1/publish":
            return httpx.Response(
                200,
                json={
                    "slug": "bright-canvas-a7k2",
                    "siteUrl": "https://bright-canvas-a7k2.here.now",
                    "status": "pending",
                    "isLive": False,
                    "requiresFinalize": True,
                    "upload": {
                        "versionId": "ver_1",
                        "uploads": [
                            {
                                "path": "index.html",
                                "method": "PUT",
                                "url": "https://upload.example/index",
                                "headers": {"Content-Type": "text/html; charset=utf-8"},
                            },
                            {
                                "path": "style.css",
                                "method": "PUT",
                                "url": "https://upload.example/css",
                                "headers": {"Content-Type": "text/css; charset=utf-8"},
                            },
                        ],
                        "skipped": [],
                        "finalizeUrl": "https://here.now/api/v1/publish/bright-canvas-a7k2/finalize",
                        "expiresInSeconds": 3600,
                    },
                },
            )
        if request.method == "PUT" and "upload.example" in str(request.url):
            return httpx.Response(200, content=b"ok")
        if request.method == "POST" and path.endswith("/finalize"):
            body = json.loads(request.content.decode())
            assert body["versionId"] == "ver_1"
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "slug": "bright-canvas-a7k2",
                    "siteUrl": "https://bright-canvas-a7k2.here.now",
                    "currentVersionId": "ver_1",
                },
            )
        return httpx.Response(404, json={"message": f"unexpected {request.method} {path}"})

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)

    provider = HereNowPublishProvider()
    provider.configure({}, password="hnk_test", site_id="default")
    logs: list[str] = []
    result = await provider.deploy(
        dist,
        force_full=True,
        upload_rels=[],
        removed=[],
        total_files=2,
        log_line=logs.append,
    )
    assert result == {
        "public_url": "https://bright-canvas-a7k2.here.now",
        "here_now_slug": "bright-canvas-a7k2",
    }
    methods = [m for m, _ in calls]
    assert "POST" in methods
    assert methods.count("PUT") == 2
    assert any(u.endswith("/finalize") for _, u in calls)


@pytest.mark.asyncio
async def test_here_now_deploy_update_existing_slug(tmp_path, monkeypatch):
    from pencms_pro.publish_providers.here_now import HereNowPublishProvider

    dist = _make_dist(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "PUT" and path == "/api/v1/publish/my-site":
            return httpx.Response(
                200,
                json={
                    "slug": "my-site",
                    "siteUrl": "https://my-site.here.now",
                    "status": "pending",
                    "isLive": False,
                    "requiresFinalize": True,
                    "upload": {
                        "versionId": "ver_2",
                        "uploads": [
                            {
                                "path": "index.html",
                                "method": "PUT",
                                "url": "https://upload.example/index",
                                "headers": {"Content-Type": "text/html"},
                            },
                        ],
                        "skipped": ["style.css"],
                        "finalizeUrl": "https://here.now/api/v1/publish/my-site/finalize",
                        "expiresInSeconds": 3600,
                    },
                },
            )
        if request.method == "PUT" and "upload.example" in str(request.url):
            return httpx.Response(200)
        if request.method == "POST" and path.endswith("/finalize"):
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "slug": "my-site",
                    "siteUrl": "https://my-site.here.now",
                    "currentVersionId": "ver_2",
                },
            )
        return httpx.Response(500, json={"message": f"unexpected {request.method} {path}"})

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)

    provider = HereNowPublishProvider()
    provider.configure(
        {"here_now_slug": "my-site"},
        password="hnk_test",
        site_id="default",
    )
    result = await provider.deploy(
        dist,
        force_full=True,
        upload_rels=[],
        removed=[],
        total_files=2,
        log_line=lambda _m: None,
    )
    assert result["here_now_slug"] == "my-site"
    assert result["public_url"] == "https://my-site.here.now"


@pytest.mark.asyncio
async def test_here_now_test_auth_failure(monkeypatch):
    from pencms_pro.publish_providers.here_now import HereNowPublishProvider

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "unauthorized", "code": "unauthorized"})

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)

    provider = HereNowPublishProvider()
    provider.configure({}, password="hnk_bad", site_id="default")
    result = await provider.test()
    assert result["success"] is False
    assert "unauthorized" in (result.get("error") or "").lower()


def test_here_now_grant_enroll_and_agent_secret(authed_client, isolated_content, temp_data_root):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    put = authed_client.put(
        "/api/publish/target",
        json={
            "site": "default",
            "provider": "here_now",
            "auth_method": "token",
            "here_now_slug": "agent-site",
        },
    )
    assert put.status_code == 200, put.text

    enroll = authed_client.post(
        "/api/publish/grant",
        json={"site": "default", "password": "hnk_agent_key"},
    )
    assert enroll.status_code == 200, enroll.text
    body = enroll.json()
    assert body["enrolled"] is True
    assert body["auth_method"] == "token"
    assert body["has_ciphertext"] is True

    from services import publish_grants

    secret = publish_grants.load_password("default")
    assert secret == "hnk_agent_key"

    grant_file = temp_data_root / "data" / "publish-grants" / "default.enc"
    assert grant_file.is_file()


def test_here_now_test_uses_vault_header(authed_client, isolated_content, monkeypatch):
    """POST /test with here.now target + vault header reaches provider.test."""
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    authed_client.put(
        "/api/publish/target",
        json={"site": "default", "provider": "here_now", "auth_method": "token"},
    )

    async def fake_test(self):
        assert self._password == "hnk_from_header"
        return {"success": True, "latency_ms": 1}

    monkeypatch.setattr(
        "pencms_pro.publish_providers.here_now.HereNowPublishProvider.test",
        fake_test,
    )

    resp = authed_client.post(
        "/api/publish/test",
        json={"site": "default"},
        headers={
            "X-Pen-Site-Id": "default",
            "X-Vault-Publish-Here-Now-Key": "hnk_from_header",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True
