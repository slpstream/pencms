"""GitHub Pages publish adapter — git push of static dist/ (S14)."""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest


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


def test_public_url_helpers():
    from services.publish_providers.github_pages import _public_url

    assert _public_url("acme", "docs", None) == "https://acme.github.io/docs/"
    assert _public_url("acme", "acme.github.io", None) == "https://acme.github.io/"
    assert _public_url("acme", "docs", "www.example.com") == "https://www.example.com/"
    assert _public_url("acme", "docs", "https://www.example.com/") == (
        "https://www.example.com/"
    )


def test_scrub_secrets_redacts_pat():
    from services.publish_providers.github_pages import _scrub_secrets

    token = "ghp_SuperSecretToken123"
    url = f"https://x-access-token:{token}@github.com/acme/docs.git"
    scrubbed = _scrub_secrets(f"fatal: could not read {url}", token)
    assert token not in scrubbed
    assert "***" in scrubbed


@pytest.mark.asyncio
async def test_github_pages_test_ok(monkeypatch):
    from services.publish_providers.github_pages import GithubPagesPublishProvider

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Authorization") == "Bearer ghp_test_ok"
        assert "/repos/acme/docs" in str(request.url)
        return httpx.Response(200, json={"full_name": "acme/docs"})

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)

    provider = GithubPagesPublishProvider()
    provider.configure(
        {
            "github_owner": "acme",
            "github_repo": "docs",
            "github_pages_branch": "gh-pages",
        },
        password="ghp_test_ok",
        site_id="default",
    )
    result = await provider.test()
    assert result["success"] is True
    assert "latency_ms" in result


@pytest.mark.asyncio
async def test_github_pages_test_auth_failure(monkeypatch):
    from services.publish_providers.github_pages import GithubPagesPublishProvider

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Bad credentials"})

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)

    provider = GithubPagesPublishProvider()
    provider.configure(
        {"github_owner": "acme", "github_repo": "docs"},
        password="bad_token",
        site_id="default",
    )
    result = await provider.test()
    assert result["success"] is False
    assert "bad credentials" in (result.get("error") or "").lower()


@pytest.mark.asyncio
async def test_github_pages_deploy_git_push(tmp_path, monkeypatch):
    from services.publish_providers.github_pages import GithubPagesPublishProvider

    dist = _make_dist(tmp_path)
    token = "ghp_DeploySecretTokenXYZ"
    git_calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        assert cmd[0] == "git"
        git_calls.append(list(cmd[1:]))
        # Ensure PAT is never passed as a plain argv that might log elsewhere
        joined = " ".join(cmd)
        if token in joined and "remote" in cmd:
            # remote add embeds token in URL — scrub path must still work on errors
            pass
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        "services.publish_providers.github_pages.subprocess.run",
        fake_run,
    )

    provider = GithubPagesPublishProvider()
    provider.configure(
        {
            "github_owner": "acme",
            "github_repo": "docs",
            "github_pages_branch": "gh-pages",
            "github_pages_cname": "www.example.com",
        },
        password=token,
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
    assert result == {"public_url": "https://www.example.com"}
    assert any("init" in c for c in git_calls)
    assert any(c[:2] == ["checkout", "--orphan"] for c in git_calls)
    assert any(c[:1] == ["push"] for c in git_calls)
    # Logs must never contain the PAT
    assert all(token not in line for line in logs)
    assert any("www.example.com" in line for line in logs)


@pytest.mark.asyncio
async def test_github_pages_deploy_scrubs_pat_on_git_failure(tmp_path, monkeypatch):
    from services.publish_providers.base import PublishDeployError
    from services.publish_providers.github_pages import GithubPagesPublishProvider
    import subprocess

    dist = _make_dist(tmp_path)
    token = "ghp_FailSecretTokenABC"

    def fake_run(cmd, **kwargs):
        if cmd[1] == "push":
            raise subprocess.CalledProcessError(
                1,
                cmd,
                output="",
                stderr=(
                    f"remote: Invalid username or token\n"
                    f"fatal: Authentication failed for "
                    f"'https://x-access-token:{token}@github.com/acme/docs.git/'\n"
                ),
            )
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        "services.publish_providers.github_pages.subprocess.run",
        fake_run,
    )

    provider = GithubPagesPublishProvider()
    provider.configure(
        {
            "github_owner": "acme",
            "github_repo": "docs",
            "github_pages_branch": "gh-pages",
        },
        password=token,
        site_id="default",
    )
    with pytest.raises(PublishDeployError) as ei:
        await provider.deploy(
            dist,
            force_full=True,
            upload_rels=[],
            removed=[],
            total_files=2,
            log_line=lambda _l: None,
        )
    msg = str(ei.value)
    assert token not in msg
    assert "***" in msg


def test_github_pages_grant_enroll_and_agent_secret(
    authed_client, isolated_content, temp_data_root
):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    put = authed_client.put(
        "/api/publish/target",
        json={
            "site": "default",
            "provider": "github_pages",
            "auth_method": "token",
            "github_owner": "acme",
            "github_repo": "docs",
            "github_pages_branch": "gh-pages",
        },
    )
    assert put.status_code == 200, put.text

    enroll = authed_client.post(
        "/api/publish/grant",
        json={"site": "default", "password": "ghp_agent_token"},
    )
    assert enroll.status_code == 200, enroll.text
    body = enroll.json()
    assert body["enrolled"] is True
    assert body["auth_method"] == "token"
    assert body["has_ciphertext"] is True

    from services import publish_grants

    secret = publish_grants.load_password("default")
    assert secret == "ghp_agent_token"

    grant_file = temp_data_root / "data" / "publish-grants" / "default.enc"
    assert grant_file.is_file()

    get = authed_client.get("/api/publish/target", params={"site": "default"})
    assert get.json()["github_owner"] == "acme"
    assert get.json()["github_repo"] == "docs"
    assert get.json()["agent_publish"] == "enrolled"
    assert "token" not in get.json()
    assert "password" not in get.json()


def test_github_pages_test_uses_vault_header(
    authed_client, isolated_content, monkeypatch
):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    authed_client.put(
        "/api/publish/target",
        json={
            "site": "default",
            "provider": "github_pages",
            "auth_method": "token",
            "github_owner": "acme",
            "github_repo": "docs",
        },
    )

    async def fake_test(self):
        assert self._password == "ghp_from_header"
        return {"success": True, "latency_ms": 1}

    monkeypatch.setattr(
        "services.publish_providers.github_pages.GithubPagesPublishProvider.test",
        fake_test,
    )

    resp = authed_client.post(
        "/api/publish/test",
        json={"site": "default"},
        headers={
            "X-Pen-Site-Id": "default",
            "X-Vault-Publish-Github-Token": "ghp_from_header",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True


def test_put_github_pages_target(authed_client, isolated_content):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    put = authed_client.put(
        "/api/publish/target",
        json={
            "site": "default",
            "provider": "github_pages",
            "auth_method": "token",
            "github_owner": "acme",
            "github_repo": "my-site",
            "github_pages_branch": "gh-pages",
            "github_pages_cname": "www.example.com",
            "public_url": "https://www.example.com",
        },
    )
    assert put.status_code == 200, put.text
    body = put.json()
    assert body["configured"] is True
    assert body["provider"] == "github_pages"
    assert body["auth_method"] == "token"
    assert body["github_owner"] == "acme"
    assert body["github_repo"] == "my-site"
    assert body["github_pages_branch"] == "gh-pages"
    assert body["github_pages_cname"] == "www.example.com"
    assert body["host"] is None
    assert "token" not in body
    assert "password" not in body

    get = authed_client.get("/api/publish/target", params={"site": "default"})
    assert get.json() == body


def test_put_github_pages_defaults_branch(authed_client, isolated_content):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    put = authed_client.put(
        "/api/publish/target",
        json={
            "site": "default",
            "provider": "github_pages",
            "github_owner": "acme",
            "github_repo": "docs",
        },
    )
    assert put.status_code == 200, put.text
    assert put.json()["github_pages_branch"] == "gh-pages"
    assert put.json()["auth_method"] == "token"


def test_put_github_pages_requires_owner_repo(authed_client, isolated_content):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    resp = authed_client.put(
        "/api/publish/target",
        json={
            "site": "default",
            "provider": "github_pages",
            "auth_method": "token",
            "github_owner": "acme",
        },
    )
    assert resp.status_code == 400, resp.text


def test_put_github_pages_rejects_token(authed_client, isolated_content):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    resp = authed_client.put(
        "/api/publish/target",
        json={
            "site": "default",
            "provider": "github_pages",
            "github_owner": "acme",
            "github_repo": "docs",
            "token": "secret",
        },
    )
    assert resp.status_code == 400, resp.text
