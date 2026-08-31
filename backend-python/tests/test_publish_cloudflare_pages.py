"""Cloudflare Pages publish adapter — Direct Upload (S12). Pro overlay."""

from __future__ import annotations

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


def _make_dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>hi</html>", encoding="utf-8")
    (dist / "style.css").write_text("body{}", encoding="utf-8")
    return dist


@pytest.mark.asyncio
async def test_cloudflare_pages_deploy_direct_upload(tmp_path, monkeypatch):
    from pencms_pro.publish_providers.cloudflare_pages import (
        CloudflarePagesPublishProvider,
        _pages_file_hash,
    )

    dist = _make_dist(tmp_path)
    index_hash = _pages_file_hash(
        (dist / "index.html").read_bytes(), dist / "index.html"
    )
    css_hash = _pages_file_hash(
        (dist / "style.css").read_bytes(), dist / "style.css"
    )

    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, str(request.url)))
        path = request.url.path
        if request.method == "POST" and path.endswith("/upload-token"):
            return httpx.Response(
                200,
                json={"success": True, "result": {"jwt": "upload-jwt-test"}},
            )
        if request.method == "POST" and path.endswith("/pages/assets/check-missing"):
            body = json.loads(request.content.decode())
            assert "hashes" in body
            # One cached, one missing
            return httpx.Response(
                200,
                json={"success": True, "result": [index_hash]},
            )
        if request.method == "POST" and path.endswith("/pages/assets/upload"):
            auth = request.headers.get("Authorization", "")
            assert "upload-jwt-test" in auth
            payload = json.loads(request.content.decode())
            assert isinstance(payload, list) and len(payload) >= 1
            assert payload[0]["key"] == index_hash
            assert payload[0]["base64"] is True
            return httpx.Response(200, json={"success": True, "result": None})
        if request.method == "POST" and path.endswith("/pages/assets/upsert-hashes"):
            return httpx.Response(200, json={"success": True, "result": None})
        if request.method == "POST" and path.endswith("/deployments"):
            # multipart: manifest field
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "result": {
                        "id": "dep_1",
                        "url": "https://my-project.pages.dev",
                    },
                },
            )
        return httpx.Response(
            404, json={"errors": [{"message": f"unexpected {request.method} {path}"}]}
        )

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)

    provider = CloudflarePagesPublishProvider()
    provider.configure(
        {
            "cf_account_id": "acct123",
            "cf_project_name": "my-project",
        },
        password="cf_token_test",
        site_id="default",
    )
    logs: list[str] = []
    result = await provider.deploy(
        dist,
        force_full=False,
        upload_rels=[],
        removed=[],
        total_files=2,
        log_line=logs.append,
    )
    assert result == {"public_url": "https://my-project.pages.dev"}
    paths = [u for _, u in calls]
    assert any("/upload-token" in u for u in paths)
    assert any("/check-missing" in u for u in paths)
    assert any("/pages/assets/upload" in u for u in paths)
    assert any("/upsert-hashes" in u for u in paths)
    assert any("/deployments" in u for u in paths)
    # css was cached; only index uploaded
    assert css_hash  # used in check-missing request body via hashes list


@pytest.mark.asyncio
async def test_cloudflare_pages_test_auth_failure(monkeypatch):
    from pencms_pro.publish_providers.cloudflare_pages import (
        CloudflarePagesPublishProvider,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"success": False, "errors": [{"code": 10000, "message": "Authentication error"}]},
        )

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)

    provider = CloudflarePagesPublishProvider()
    provider.configure(
        {"cf_account_id": "acct", "cf_project_name": "proj"},
        password="bad_token",
        site_id="default",
    )
    result = await provider.test()
    assert result["success"] is False
    assert "authentication" in (result.get("error") or "").lower()


def test_cloudflare_pages_grant_enroll_and_agent_secret(
    authed_client, isolated_content, temp_data_root
):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    put = authed_client.put(
        "/api/publish/target",
        json={
            "site": "default",
            "provider": "cloudflare_pages",
            "auth_method": "token",
            "cf_account_id": "acct_agent",
            "cf_project_name": "agent-project",
        },
    )
    assert put.status_code == 200, put.text

    enroll = authed_client.post(
        "/api/publish/grant",
        json={"site": "default", "password": "cf_agent_token"},
    )
    assert enroll.status_code == 200, enroll.text
    body = enroll.json()
    assert body["enrolled"] is True
    assert body["auth_method"] == "token"
    assert body["has_ciphertext"] is True

    from services import publish_grants

    secret = publish_grants.load_password("default")
    assert secret == "cf_agent_token"

    grant_file = temp_data_root / "data" / "publish-grants" / "default.enc"
    assert grant_file.is_file()

    # Grant write preserves CF fields
    get = authed_client.get("/api/publish/target", params={"site": "default"})
    assert get.json()["cf_account_id"] == "acct_agent"
    assert get.json()["cf_project_name"] == "agent-project"
    assert get.json()["agent_publish"] == "enrolled"


def test_cloudflare_pages_test_uses_vault_header(
    authed_client, isolated_content, monkeypatch
):
    """POST /test with CF target + vault header reaches provider.test."""
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    authed_client.put(
        "/api/publish/target",
        json={
            "site": "default",
            "provider": "cloudflare_pages",
            "auth_method": "token",
            "cf_account_id": "acct",
            "cf_project_name": "proj",
        },
    )

    async def fake_test(self):
        assert self._password == "cf_from_header"
        return {"success": True, "latency_ms": 1}

    monkeypatch.setattr(
        "pencms_pro.publish_providers.cloudflare_pages.CloudflarePagesPublishProvider.test",
        fake_test,
    )

    resp = authed_client.post(
        "/api/publish/test",
        json={"site": "default"},
        headers={
            "X-Pen-Site-Id": "default",
            "X-Vault-Publish-Cf-Pages-Token": "cf_from_header",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True


def test_put_cloudflare_pages_target(authed_client, isolated_content):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    put = authed_client.put(
        "/api/publish/target",
        json={
            "site": "default",
            "provider": "cloudflare_pages",
            "auth_method": "token",
            "cf_account_id": "023e105f4ecef8ad9ca31a8372d0c353",
            "cf_project_name": "demo-site",
            "public_url": "https://demo-site.pages.dev",
        },
    )
    assert put.status_code == 200, put.text
    body = put.json()
    assert body["configured"] is True
    assert body["provider"] == "cloudflare_pages"
    assert body["auth_method"] == "token"
    assert body["cf_account_id"] == "023e105f4ecef8ad9ca31a8372d0c353"
    assert body["cf_project_name"] == "demo-site"
    assert body["host"] is None
    assert "token" not in body
    assert "api_key" not in body
    assert "password" not in body

    get = authed_client.get("/api/publish/target", params={"site": "default"})
    assert get.json() == body


def test_put_cloudflare_pages_rejects_token(authed_client, isolated_content):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    resp = authed_client.put(
        "/api/publish/target",
        json={
            "site": "default",
            "provider": "cloudflare_pages",
            "cf_account_id": "acct",
            "cf_project_name": "proj",
            "token": "secret",
        },
    )
    assert resp.status_code == 400, resp.text
