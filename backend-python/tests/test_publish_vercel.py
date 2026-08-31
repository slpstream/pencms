"""Vercel publish adapter — file SHA upload + create deployment (S13). Pro overlay."""

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


def _make_dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>hi</html>", encoding="utf-8")
    (dist / "style.css").write_text("body{}", encoding="utf-8")
    return dist


@pytest.mark.asyncio
async def test_vercel_deploy_file_upload(tmp_path, monkeypatch):
    from pencms_pro.publish_providers.vercel import VercelPublishProvider

    dist = _make_dist(tmp_path)
    index_sha = hashlib.sha1(
        (dist / "index.html").read_bytes()
    ).hexdigest()

    calls: list[tuple[str, str]] = []
    poll_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, str(request.url)))
        path = request.url.path
        if request.method == "POST" and path.endswith("/v2/files"):
            digest = request.headers.get("x-vercel-digest")
            assert digest
            assert request.headers.get("content-type") == "application/octet-stream"
            return httpx.Response(200, json={})
        if request.method == "POST" and "/v13/deployments" in path:
            body = json.loads(request.content.decode())
            assert body["name"] == "my-project"
            assert body["target"] == "production"
            assert body["projectSettings"]["framework"] is None
            assert any(f["sha"] == index_sha for f in body["files"])
            assert "skipAutoDetectionConfirmation" in str(request.url)
            return httpx.Response(
                200,
                json={
                    "id": "dpl_abc",
                    "url": "my-project-abc.vercel.app",
                    "readyState": "INITIALIZING",
                },
            )
        if request.method == "GET" and "/v13/deployments/dpl_abc" in path:
            poll_count["n"] += 1
            if poll_count["n"] < 2:
                return httpx.Response(
                    200,
                    json={
                        "id": "dpl_abc",
                        "url": "my-project-abc.vercel.app",
                        "readyState": "BUILDING",
                    },
                )
            return httpx.Response(
                200,
                json={
                    "id": "dpl_abc",
                    "url": "my-project-abc.vercel.app",
                    "readyState": "READY",
                },
            )
        return httpx.Response(
            404, json={"error": {"message": f"unexpected {request.method} {path}"}}
        )

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)
    # Avoid sleeping in poll loop during tests.
    monkeypatch.setattr(
        "pencms_pro.publish_providers.vercel.time.sleep", lambda *_a, **_k: None
    )

    provider = VercelPublishProvider()
    provider.configure(
        {
            "vercel_project_name": "my-project",
            "vercel_team_id": "team_xyz",
        },
        password="vercel_token_test",
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
    assert result == {"public_url": "https://my-project-abc.vercel.app"}
    paths = [u for _, u in calls]
    assert any("/v2/files" in u for u in paths)
    assert any("/v13/deployments" in u for u in paths)
    assert any("teamId=team_xyz" in u for u in paths)


@pytest.mark.asyncio
async def test_vercel_test_auth_failure(monkeypatch):
    from pencms_pro.publish_providers.vercel import VercelPublishProvider

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"error": {"code": "forbidden", "message": "Not authorized"}},
        )

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)

    provider = VercelPublishProvider()
    provider.configure(
        {"vercel_project_name": "proj"},
        password="bad_token",
        site_id="default",
    )
    result = await provider.test()
    assert result["success"] is False
    assert "authorized" in (result.get("error") or "").lower() or "not" in (
        result.get("error") or ""
    ).lower()


def test_vercel_grant_enroll_and_agent_secret(
    authed_client, isolated_content, temp_data_root
):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    put = authed_client.put(
        "/api/publish/target",
        json={
            "site": "default",
            "provider": "vercel",
            "auth_method": "token",
            "vercel_project_name": "agent-project",
            "vercel_team_id": "team_agent",
        },
    )
    assert put.status_code == 200, put.text

    enroll = authed_client.post(
        "/api/publish/grant",
        json={"site": "default", "password": "vercel_agent_token"},
    )
    assert enroll.status_code == 200, enroll.text
    body = enroll.json()
    assert body["enrolled"] is True
    assert body["auth_method"] == "token"
    assert body["has_ciphertext"] is True

    from services import publish_grants

    secret = publish_grants.load_password("default")
    assert secret == "vercel_agent_token"

    grant_file = temp_data_root / "data" / "publish-grants" / "default.enc"
    assert grant_file.is_file()

    get = authed_client.get("/api/publish/target", params={"site": "default"})
    assert get.json()["vercel_project_name"] == "agent-project"
    assert get.json()["vercel_team_id"] == "team_agent"
    assert get.json()["agent_publish"] == "enrolled"


def test_vercel_test_uses_vault_header(
    authed_client, isolated_content, monkeypatch
):
    """POST /test with Vercel target + vault header reaches provider.test."""
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    authed_client.put(
        "/api/publish/target",
        json={
            "site": "default",
            "provider": "vercel",
            "auth_method": "token",
            "vercel_project_name": "proj",
        },
    )

    async def fake_test(self):
        assert self._password == "vercel_from_header"
        return {"success": True, "latency_ms": 1}

    monkeypatch.setattr(
        "pencms_pro.publish_providers.vercel.VercelPublishProvider.test",
        fake_test,
    )

    resp = authed_client.post(
        "/api/publish/test",
        json={"site": "default"},
        headers={
            "X-Pen-Site-Id": "default",
            "X-Vault-Publish-Vercel-Token": "vercel_from_header",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True


def test_put_vercel_target(authed_client, isolated_content):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    put = authed_client.put(
        "/api/publish/target",
        json={
            "site": "default",
            "provider": "vercel",
            "auth_method": "token",
            "vercel_project_name": "demo-site",
            "vercel_team_id": "team_demo",
            "public_url": "https://demo-site.vercel.app",
        },
    )
    assert put.status_code == 200, put.text
    body = put.json()
    assert body["configured"] is True
    assert body["provider"] == "vercel"
    assert body["auth_method"] == "token"
    assert body["vercel_project_name"] == "demo-site"
    assert body["vercel_team_id"] == "team_demo"
    assert body["host"] is None
    assert "token" not in body
    assert "api_key" not in body
    assert "password" not in body

    get = authed_client.get("/api/publish/target", params={"site": "default"})
    assert get.json() == body


def test_put_vercel_rejects_token(authed_client, isolated_content):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    resp = authed_client.put(
        "/api/publish/target",
        json={
            "site": "default",
            "provider": "vercel",
            "vercel_project_name": "proj",
            "token": "secret",
        },
    )
    assert resp.status_code == 400, resp.text


def test_put_vercel_requires_project_name(authed_client, isolated_content):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    resp = authed_client.put(
        "/api/publish/target",
        json={
            "site": "default",
            "provider": "vercel",
            "auth_method": "token",
        },
    )
    assert resp.status_code == 400, resp.text
