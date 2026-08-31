"""Publish POST /api/publish/run + GET /api/publish/status."""

from __future__ import annotations

import shutil

import pytest
import yaml


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


def _target_body(**overrides):
    body = {
        "site": "default",
        "provider": "sftp",
        "host": "example.com",
        "port": 22,
        "username": "deploy",
        "remote_path": "/var/www/html",
        "auth_method": "password",
        "public_url": "https://example.com",
    }
    body.update(overrides)
    return body


def _configure_target(authed_client, **overrides):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    put = authed_client.put("/api/publish/target", json=_target_body(**overrides))
    assert put.status_code == 200, put.text
    return put.json()


def test_publish_run_unauthenticated(client, isolated_content):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    resp = client.post("/api/publish/run", json={"site": "default", "password": "x"})
    assert resp.status_code == 401


def test_publish_run_unknown_site(authed_client, isolated_content):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    resp = authed_client.post(
        "/api/publish/run",
        json={"site": "nosuchsite", "password": "x"},
    )
    assert resp.status_code == 404


def test_publish_run_unconfigured(authed_client, isolated_content):
    from services.site_service import ensure_sites_initialized

    ensure_sites_initialized()
    resp = authed_client.post(
        "/api/publish/run",
        json={"site": "default", "password": "x"},
    )
    assert resp.status_code == 400
    assert "not configured" in resp.json()["detail"].lower()


def test_publish_run_missing_password(authed_client, isolated_content):
    _configure_target(authed_client)
    resp = authed_client.post("/api/publish/run", json={"site": "default"})
    assert resp.status_code == 400
    assert "password" in resp.json()["detail"].lower()


def test_publish_run_key_auth_no_password(authed_client, isolated_content, monkeypatch):
    """Key auth starts a run without vault publish password."""
    _configure_target(authed_client, auth_method="key")
    seen = {}

    async def fake_run(site_id, vault, password=None, force_full=False):
        from services.publish_deploy import _mark_success

        seen["site_id"] = site_id
        seen["password"] = password
        seen["force_full"] = force_full
        seen["has_publish_pass"] = f"PUBLISH_SFTP_PASS:{site_id}" in vault
        _mark_success(site_id)

    monkeypatch.setattr("routers.publish.run_publish", fake_run)

    resp = authed_client.post("/api/publish/run", json={"site": "default"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "running"
    assert seen["site_id"] == "default"
    assert seen["password"] is None
    assert seen["force_full"] is False
    assert seen["has_publish_pass"] is False

    status = authed_client.get("/api/publish/status", params={"site": "default"})
    assert status.json()["status"] == "success"
    assert status.json()["last_status"] == "ok"


def test_publish_run_concurrent_rejected(authed_client, isolated_content):
    from services.publish_deploy import begin_run

    _configure_target(authed_client)
    first = begin_run("default")
    resp = authed_client.post(
        "/api/publish/run",
        json={"site": "default", "password": "x"},
    )
    assert resp.status_code == 409
    assert first["task_id"] in resp.json()["detail"]


def test_publish_status_idle(authed_client, isolated_content):
    _configure_target(authed_client)
    resp = authed_client.get("/api/publish/status", params={"site": "default"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "idle"
    assert data["site_id"] == "default"
    assert data["task_id"] is None
    assert data["log"] == []


def test_publish_status_unknown_task(authed_client, isolated_content):
    from services.publish_deploy import begin_run

    _configure_target(authed_client)
    begin_run("default")
    resp = authed_client.get(
        "/api/publish/status",
        params={"site": "default", "task_id": "not-the-real-task"},
    )
    assert resp.status_code == 404


def test_publish_run_success_updates_status(authed_client, isolated_content, monkeypatch):
    _configure_target(authed_client)

    async def fake_run(site_id, vault, password=None, force_full=False):
        from services.publish_deploy import _mark_success

        assert vault.get(f"PUBLISH_SFTP_PASS:{site_id}") == "s3cret"
        assert password == "s3cret"
        _mark_success(site_id)

    monkeypatch.setattr("routers.publish.run_publish", fake_run)

    resp = authed_client.post(
        "/api/publish/run",
        json={"site": "default", "password": "s3cret"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "running"
    assert body["site_id"] == "default"
    assert body["task_id"]

    status = authed_client.get("/api/publish/status", params={"site": "default"})
    assert status.status_code == 200
    data = status.json()
    assert data["status"] == "success"
    assert data["phase"] == "done"
    assert data["task_id"] == body["task_id"]
    assert data["last_status"] == "ok"
    assert data["last_published_at"]

    target = authed_client.get("/api/publish/target", params={"site": "default"})
    assert target.json()["last_status"] == "ok"
    assert target.json()["last_published_at"]
    assert "s3cret" not in target.text


def test_publish_run_force_full_flag(authed_client, isolated_content, monkeypatch):
    _configure_target(authed_client)
    seen = {}

    async def fake_run(site_id, vault, password=None, force_full=False):
        from services.publish_deploy import _mark_success

        seen["force_full"] = force_full
        _mark_success(site_id)

    monkeypatch.setattr("routers.publish.run_publish", fake_run)

    resp = authed_client.post(
        "/api/publish/run",
        json={"site": "default", "password": "x", "force_full": True},
    )
    assert resp.status_code == 200, resp.text
    assert seen["force_full"] is True


def test_publish_run_failure_sets_failed(authed_client, isolated_content, monkeypatch):
    _configure_target(authed_client)

    async def fake_run(site_id, vault, password=None, force_full=False):
        from services.publish_deploy import _mark_failed

        _mark_failed(site_id, "build.sh exited with code 1")

    monkeypatch.setattr("routers.publish.run_publish", fake_run)

    resp = authed_client.post(
        "/api/publish/run",
        json={"site": "default", "password": "x"},
    )
    assert resp.status_code == 200

    status = authed_client.get("/api/publish/status", params={"site": "default"})
    data = status.json()
    assert data["status"] == "error"
    assert "build.sh" in (data.get("error") or "")
    assert data["last_status"] == "failed"

    target = authed_client.get("/api/publish/target", params={"site": "default"})
    assert target.json()["last_status"] == "failed"
    # Failure must not invent a successful publish timestamp
    assert target.json()["last_published_at"] is None


def test_publish_run_vault_header(authed_client, isolated_content, monkeypatch):
    _configure_target(authed_client)
    seen = {}

    async def fake_run(site_id, vault, password=None, force_full=False):
        from services.publish_deploy import _mark_success

        seen["vault"] = dict(vault)
        seen["password"] = password
        _mark_success(site_id)

    monkeypatch.setattr("routers.publish.run_publish", fake_run)

    resp = authed_client.post(
        "/api/publish/run",
        json={"site": "default"},
        headers={
            "X-Pen-Site-Id": "default",
            "X-Vault-Publish-Pass": "vault-pass-xyz",
            "X-Vault-Content-Pass": "content-pass",
        },
    )
    assert resp.status_code == 200, resp.text
    assert seen["password"] == "vault-pass-xyz"
    assert seen["vault"]["PUBLISH_SFTP_PASS:default"] == "vault-pass-xyz"
    assert "CONTENT_SFTP_PASS" not in seen["vault"]


@pytest.mark.pro
def test_publish_run_content_vault_header(authed_client, isolated_content, monkeypatch):
    pytest.importorskip("pencms_pro", reason="content/assets SSH vault headers are Pro overlay")
    _configure_target(authed_client)
    seen = {}

    async def fake_run(site_id, vault, password=None, force_full=False):
        from services.publish_deploy import _mark_success

        seen["vault"] = dict(vault)
        _mark_success(site_id)

    monkeypatch.setattr("routers.publish.run_publish", fake_run)

    resp = authed_client.post(
        "/api/publish/run",
        json={"site": "default"},
        headers={
            "X-Pen-Site-Id": "default",
            "X-Vault-Publish-Pass": "vault-pass-xyz",
            "X-Vault-Content-Pass": "content-pass",
            "X-Vault-Assets-Pass": "assets-pass",
        },
    )
    assert resp.status_code == 200, resp.text
    assert seen["vault"]["CONTENT_SFTP_PASS"] == "content-pass"
    assert seen["vault"]["ASSETS_SFTP_PASS"] == "assets-pass"


def test_run_publish_build_then_scp(isolated_content, monkeypatch, tmp_path, temp_data_root):
    """Unit: first run (no manifest) full-uploads then saves manifest."""
    from services.site_service import ensure_sites_initialized, set_publish_target
    from services import publish_deploy as pd
    from services import publish_manifests as pm
    from services.publish_providers import sftp as sftp_mod

    ensure_sites_initialized()
    pm.clear_manifest("default")
    set_publish_target(
        "default",
        {
            "host": "example.com",
            "port": 22,
            "username": "deploy",
            "remote_path": "/var/www/html",
            "auth_method": "password",
            "public_url": "https://example.com",
        },
    )

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html></html>", encoding="utf-8")

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

    built = {}
    uploaded = {}
    deleted = {}

    async def fake_build(site_id, domain, vault):
        built["site_id"] = site_id
        built["domain"] = domain
        built["vault"] = dict(vault)

    async def fake_scp(target, password, dist_dir, *, log_line, set_phase=None):
        uploaded["host"] = target["host"]
        uploaded["password"] = password
        uploaded["dist"] = str(dist_dir)

    async def fake_incr(*_a, **_k):
        raise AssertionError("incremental should not run on first publish")

    async def fake_dels(target, password, removed, *, log_line):
        deleted["removed"] = list(removed)

    monkeypatch.setattr(pd, "_build_site", fake_build)
    monkeypatch.setattr(sftp_mod, "_scp_upload", fake_scp)
    monkeypatch.setattr(sftp_mod, "_incremental_upload", fake_incr)
    monkeypatch.setattr(sftp_mod, "_apply_remote_deletes", fake_dels)

    pd.begin_run("default")
    import asyncio

    asyncio.run(
        pd.run_publish(
            "default",
            {"PUBLISH_SFTP_PASS:default": "pw", "CONTENT_SFTP_PASS": "c"},
            password="pw",
        )
    )

    assert built["site_id"] == "default"
    assert built["domain"] == "example.com"
    assert built["vault"]["CONTENT_SFTP_PASS"] == "c"
    assert uploaded["host"] == "example.com"
    assert uploaded["password"] == "pw"
    assert deleted["removed"] == []

    status = pd.get_run_status("default")
    assert status["status"] == "success"
    from services.site_service import get_publish_target

    target = get_publish_target("default")
    assert target["last_status"] == "ok"
    assert target["last_published_at"]

    loaded = pm.load_manifest("default")
    assert loaded is not None
    assert "index.html" in loaded


def test_run_publish_incremental_skips_unchanged(
    isolated_content, monkeypatch, tmp_path, temp_data_root
):
    """Second run with unchanged dist uses incremental (0 uploads)."""
    from services.site_service import ensure_sites_initialized, set_publish_target
    from services import publish_deploy as pd
    from services import publish_manifests as pm
    from services.publish_providers import sftp as sftp_mod

    ensure_sites_initialized()
    set_publish_target(
        "default",
        {
            "host": "example.com",
            "port": 22,
            "username": "deploy",
            "remote_path": "/var/www/html",
            "auth_method": "password",
            "public_url": "https://example.com",
        },
    )

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html></html>", encoding="utf-8")
    (dist / "extra.html").write_text("old", encoding="utf-8")

    # Seed prior manifest matching current files.
    pm.save_manifest("default", pm.hash_dist_tree(dist))
    # Simulate a removed remote: prior had gone.html
    prior = pm.load_manifest("default")
    assert prior is not None
    prior["gone.html"] = "deadbeef" * 8
    pm.save_manifest("default", prior)

    # Drop extra from dist and change nothing else — wait, we want:
    # keep index, remove extra from disk so it's a delete, add change to one file
    (dist / "extra.html").unlink()
    (dist / "index.html").write_text("<html>changed</html>", encoding="utf-8")

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

    calls = {"full": 0, "incr": [], "dels": []}

    async def fake_build(site_id, domain, vault):
        pass

    async def fake_scp(*_a, **_k):
        calls["full"] += 1

    async def fake_incr(target, password, dist_dir, upload_rels, *, log_line, set_phase=None):
        calls["incr"].append(list(upload_rels))

    async def fake_dels(target, password, removed, *, log_line):
        calls["dels"].append(list(removed))

    monkeypatch.setattr(pd, "_build_site", fake_build)
    monkeypatch.setattr(sftp_mod, "_scp_upload", fake_scp)
    monkeypatch.setattr(sftp_mod, "_incremental_upload", fake_incr)
    monkeypatch.setattr(sftp_mod, "_apply_remote_deletes", fake_dels)

    pd.begin_run("default")
    import asyncio

    asyncio.run(
        pd.run_publish(
            "default",
            {"PUBLISH_SFTP_PASS:default": "pw"},
            password="pw",
        )
    )

    assert calls["full"] == 0
    assert calls["incr"] == [["index.html"]]
    assert sorted(calls["dels"][0]) == ["extra.html", "gone.html"]
    assert pd.get_run_status("default")["status"] == "success"
    loaded = pm.load_manifest("default")
    assert set(loaded) == {"index.html"}
    assert "gone.html" not in loaded
    assert "extra.html" not in loaded


def test_run_publish_force_full_uses_scp(
    isolated_content, monkeypatch, tmp_path, temp_data_root
):
    """force_full=True uses full scp even when a prior manifest exists."""
    from services.site_service import ensure_sites_initialized, set_publish_target
    from services import publish_deploy as pd
    from services import publish_manifests as pm
    from services.publish_providers import sftp as sftp_mod

    ensure_sites_initialized()
    set_publish_target(
        "default",
        {
            "host": "example.com",
            "port": 22,
            "username": "deploy",
            "remote_path": "/var/www/html",
            "auth_method": "password",
            "public_url": "https://example.com",
        },
    )

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html></html>", encoding="utf-8")
    pm.save_manifest("default", pm.hash_dist_tree(dist))

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

    calls = {"full": 0, "incr": 0}

    async def fake_build(*_a, **_k):
        pass

    async def fake_scp(*_a, **_k):
        calls["full"] += 1

    async def fake_incr(*_a, **_k):
        calls["incr"] += 1

    async def fake_dels(*_a, **_k):
        pass

    monkeypatch.setattr(pd, "_build_site", fake_build)
    monkeypatch.setattr(sftp_mod, "_scp_upload", fake_scp)
    monkeypatch.setattr(sftp_mod, "_incremental_upload", fake_incr)
    monkeypatch.setattr(sftp_mod, "_apply_remote_deletes", fake_dels)

    pd.begin_run("default")
    import asyncio

    asyncio.run(
        pd.run_publish(
            "default",
            {"PUBLISH_SFTP_PASS:default": "pw"},
            password="pw",
            force_full=True,
        )
    )

    assert calls["full"] == 1
    assert calls["incr"] == 0
    assert pd.get_run_status("default")["status"] == "success"


def test_run_publish_failure_keeps_old_manifest(
    isolated_content, monkeypatch, tmp_path, temp_data_root
):
    from services.site_service import ensure_sites_initialized, set_publish_target
    from services import publish_deploy as pd
    from services import publish_manifests as pm
    from services.publish_providers import sftp as sftp_mod

    ensure_sites_initialized()
    set_publish_target(
        "default",
        {
            "host": "example.com",
            "port": 22,
            "username": "deploy",
            "remote_path": "/var/www/html",
            "auth_method": "password",
            "public_url": "https://example.com",
        },
    )

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("v1", encoding="utf-8")
    old = pm.hash_dist_tree(dist)
    pm.save_manifest("default", old)

    (dist / "index.html").write_text("v2", encoding="utf-8")

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

    async def fake_build(*_a, **_k):
        pass

    async def fake_incr(*_a, **_k):
        raise pd.PublishDeployError("scp failed")

    monkeypatch.setattr(pd, "_build_site", fake_build)
    monkeypatch.setattr(sftp_mod, "_incremental_upload", fake_incr)

    pd.begin_run("default")
    import asyncio

    asyncio.run(
        pd.run_publish(
            "default",
            {"PUBLISH_SFTP_PASS:default": "pw"},
            password="pw",
        )
    )

    assert pd.get_run_status("default")["status"] == "error"
    assert pm.load_manifest("default") == old


def test_run_publish_key_auth_scp_no_password(isolated_content, monkeypatch, tmp_path, temp_data_root):
    """Unit: key auth builds then scp-uploads with password=None."""
    from services.site_service import ensure_sites_initialized, set_publish_target
    from services import publish_deploy as pd
    from services import publish_manifests as pm
    from services.publish_providers import sftp as sftp_mod

    ensure_sites_initialized()
    pm.clear_manifest("default")
    set_publish_target(
        "default",
        {
            "host": "example.com",
            "port": 22,
            "username": "deploy",
            "remote_path": "/var/www/html",
            "auth_method": "key",
            "public_url": "https://example.com",
        },
    )

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html></html>", encoding="utf-8")

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

    uploaded = {}

    async def fake_build(site_id, domain, vault):
        pass

    async def fake_scp(target, password, dist_dir, *, log_line, set_phase=None):
        uploaded["password"] = password
        uploaded["auth_method"] = target.get("auth_method")

    async def fake_dels(*_a, **_k):
        pass

    monkeypatch.setattr(pd, "_build_site", fake_build)
    monkeypatch.setattr(sftp_mod, "_scp_upload", fake_scp)
    monkeypatch.setattr(sftp_mod, "_apply_remote_deletes", fake_dels)

    pd.begin_run("default")
    import asyncio

    asyncio.run(pd.run_publish("default", {"CONTENT_SFTP_PASS": "c"}))

    assert uploaded["password"] is None
    assert uploaded["auth_method"] == "key"
    assert pd.get_run_status("default")["status"] == "success"


def test_password_not_in_yaml_after_run(authed_client, isolated_content, monkeypatch, temp_data_root):
    _configure_target(authed_client)

    async def fake_run(site_id, vault, password=None, force_full=False):
        from services.publish_deploy import _mark_success

        _mark_success(site_id)

    monkeypatch.setattr("routers.publish.run_publish", fake_run)

    authed_client.post(
        "/api/publish/run",
        json={"site": "default", "password": "super-secret-pass"},
    )
    raw = (temp_data_root / "data" / "sites.yaml").read_text()
    assert "super-secret-pass" not in raw
    site = next(s for s in yaml.safe_load(raw)["sites"] if s["id"] == "default")
    assert "password" not in (site.get("publish") or {})


def test_tar_stream_lands_contents_not_nested_dir(tmp_path):
    """Local stand-in for tar|ssh: contents of dist/ land flat in dest/, not dest/dist/."""
    import subprocess

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("ok", encoding="utf-8")
    (dist / "css").mkdir()
    (dist / "css" / "app.css").write_text("body{}", encoding="utf-8")
    dest = tmp_path / "remote"
    dest.mkdir()

    tar = subprocess.Popen(
        ["tar", "-C", str(dist), "-cf", "-", "."],
        stdout=subprocess.PIPE,
    )
    extract = subprocess.run(
        ["tar", "-C", str(dest), "-xf", "-"],
        stdin=tar.stdout,
        capture_output=True,
        check=False,
    )
    assert tar.wait() == 0
    assert extract.returncode == 0
    assert (dest / "index.html").read_text(encoding="utf-8") == "ok"
    assert (dest / "css" / "app.css").is_file()
    assert not (dest / "dist").exists()


def test_tar_pipe_uses_absolute_tar_and_passes_env(monkeypatch, tmp_path):
    """Full upload must not spawn bare 'tar' (venv-only systemd PATH)."""
    import subprocess

    from services.publish_providers import sftp as sftp_mod

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("ok", encoding="utf-8")

    captured: list[dict] = []

    class FakeProc:
        def __init__(self, args, **kwargs):
            captured.append({"args": list(args), "env": kwargs.get("env")})
            self.stdout = type("S", (), {"close": lambda self: None})()
            self.stderr = type("S", (), {"read": lambda self: b""})()
            self.returncode = 0

        def communicate(self, timeout=None):
            return b"", b""

        def wait(self, timeout=None):
            return 0

        def kill(self):
            pass

    monkeypatch.setattr(subprocess, "Popen", FakeProc)
    env = {"PATH": "/opt/pencms/.venv/bin:/usr/bin:/bin", "SSH_ASKPASS": "/tmp/x"}
    rc, _out, _err = sftp_mod._tar_pipe_to_ssh_sync(
        env=env,
        ssh_opts=["-p", "22"],
        host="example.com",
        username="deploy",
        remote_path="/var/www",
        dist_dir=dist,
    )
    assert rc == 0
    assert captured[0]["args"][0] == "/usr/bin/tar"
    assert captured[0]["env"] is env
    assert captured[1]["args"][0] == "/usr/bin/ssh"
    assert captured[1]["env"] is env


def test_tar_pipe_missing_tar_is_publish_error(monkeypatch, tmp_path):
    import subprocess

    from services.publish_providers import PublishDeployError
    from services.publish_providers import sftp as sftp_mod

    dist = tmp_path / "dist"
    dist.mkdir()

    def boom(*_a, **_k):
        raise FileNotFoundError(2, "No such file or directory", "tar")

    monkeypatch.setattr(subprocess, "Popen", boom)
    with pytest.raises(PublishDeployError, match="tar"):
        sftp_mod._tar_pipe_to_ssh_sync(
            env={"PATH": "/opt/pencms/.venv/bin"},
            ssh_opts=["-p", "22"],
            host="example.com",
            username="deploy",
            remote_path="/var/www",
            dist_dir=dist,
        )


def _stub_sftp_run(pd, sftp_mod, monkeypatch, tmp_path, *, fail_deploy=False):
    """Shared stubs for run_publish webhook tests (build + SFTP)."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html></html>", encoding="utf-8")

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

    async def fake_build(*_a, **_k):
        return None

    async def fake_scp(*_a, **_k):
        if fail_deploy:
            from services.publish_providers import PublishDeployError

            raise PublishDeployError("scp failed")

    async def fake_incr(*_a, **_k):
        raise AssertionError("incremental unexpected")

    async def fake_dels(*_a, **_k):
        return None

    monkeypatch.setattr(pd, "_build_site", fake_build)
    monkeypatch.setattr(sftp_mod, "_scp_upload", fake_scp)
    monkeypatch.setattr(sftp_mod, "_incremental_upload", fake_incr)
    monkeypatch.setattr(sftp_mod, "_apply_remote_deletes", fake_dels)


def test_webhook_fires_on_success(isolated_content, monkeypatch, tmp_path, temp_data_root):
    import asyncio
    import json

    import httpx
    from services.site_service import ensure_sites_initialized, set_publish_target
    from services import publish_deploy as pd
    from services import publish_manifests as pm
    from services.publish_providers import sftp as sftp_mod

    ensure_sites_initialized()
    pm.clear_manifest("default")
    set_publish_target(
        "default",
        {
            "host": "example.com",
            "port": 22,
            "username": "deploy",
            "remote_path": "/var/www/html",
            "auth_method": "password",
            "public_url": "https://example.com",
            "webhook_url": "https://hooks.example.com/publish",
        },
    )
    _stub_sftp_run(pd, sftp_mod, monkeypatch, tmp_path)

    posts = []

    class FakeResponse:
        status_code = 200

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def post(self, url, content=None, headers=None, json=None):
            posts.append(
                {
                    "url": url,
                    "content": content,
                    "headers": headers or {},
                    "json": json,
                }
            )
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    pd.begin_run("default")
    asyncio.run(
        pd.run_publish(
            "default",
            {"PUBLISH_SFTP_PASS:default": "pw"},
            password="pw",
        )
    )

    assert len(posts) == 1
    assert posts[0]["url"] == "https://hooks.example.com/publish"
    body = json.loads(posts[0]["content"].decode("utf-8"))
    assert body["event"] == "publish.success"
    assert body["site_id"] == "default"
    assert body["provider"] == "sftp"
    assert body["public_url"] == "https://example.com"
    assert body["published_at"]
    assert "X-PenCMS-Signature" not in posts[0]["headers"]
    assert pd.get_run_status("default")["status"] == "success"


def test_webhook_signs_when_secret_set(isolated_content, monkeypatch, tmp_path, temp_data_root):
    import asyncio
    import hashlib
    import hmac
    import json

    import httpx
    from services.site_service import ensure_sites_initialized, set_publish_target
    from services import publish_deploy as pd
    from services import publish_manifests as pm
    from services.publish_providers import sftp as sftp_mod

    ensure_sites_initialized()
    pm.clear_manifest("default")
    set_publish_target(
        "default",
        {
            "host": "example.com",
            "port": 22,
            "username": "deploy",
            "remote_path": "/var/www/html",
            "auth_method": "password",
            "public_url": "https://example.com",
            "webhook_url": "https://hooks.example.com/publish",
            "webhook_secret": "hook-secret",
        },
    )
    _stub_sftp_run(pd, sftp_mod, monkeypatch, tmp_path)

    posts = []

    class FakeResponse:
        status_code = 200

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def post(self, url, content=None, headers=None, json=None):
            posts.append(
                {
                    "url": url,
                    "content": content,
                    "headers": headers or {},
                }
            )
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    pd.begin_run("default")
    asyncio.run(
        pd.run_publish(
            "default",
            {"PUBLISH_SFTP_PASS:default": "pw"},
            password="pw",
        )
    )

    assert len(posts) == 1
    raw = posts[0]["content"]
    expected = hmac.new(b"hook-secret", raw, hashlib.sha256).hexdigest()
    assert posts[0]["headers"]["X-PenCMS-Signature"] == f"sha256={expected}"
    body = json.loads(raw.decode("utf-8"))
    assert body["event"] == "publish.success"


def test_webhook_skipped_when_missing(isolated_content, monkeypatch, tmp_path, temp_data_root):
    import asyncio

    import httpx
    from services.site_service import ensure_sites_initialized, set_publish_target
    from services import publish_deploy as pd
    from services import publish_manifests as pm
    from services.publish_providers import sftp as sftp_mod

    ensure_sites_initialized()
    pm.clear_manifest("default")
    set_publish_target(
        "default",
        {
            "host": "example.com",
            "port": 22,
            "username": "deploy",
            "remote_path": "/var/www/html",
            "auth_method": "password",
            "public_url": "https://example.com",
        },
    )
    _stub_sftp_run(pd, sftp_mod, monkeypatch, tmp_path)

    posts = []

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def post(self, url, content=None, headers=None, json=None):
            posts.append(url)
            raise AssertionError("webhook must not fire when URL missing")

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    pd.begin_run("default")
    asyncio.run(
        pd.run_publish(
            "default",
            {"PUBLISH_SFTP_PASS:default": "pw"},
            password="pw",
        )
    )
    assert posts == []
    assert pd.get_run_status("default")["status"] == "success"


def test_webhook_fires_on_failure(isolated_content, monkeypatch, tmp_path, temp_data_root):
    import asyncio
    import json

    import httpx
    from services.site_service import ensure_sites_initialized, set_publish_target, get_publish_target
    from services import publish_deploy as pd
    from services import publish_manifests as pm
    from services.publish_providers import sftp as sftp_mod

    ensure_sites_initialized()
    pm.clear_manifest("default")
    set_publish_target(
        "default",
        {
            "host": "example.com",
            "port": 22,
            "username": "deploy",
            "remote_path": "/var/www/html",
            "auth_method": "password",
            "public_url": "https://example.com",
            "webhook_url": "https://hooks.example.com/publish",
        },
    )
    _stub_sftp_run(pd, sftp_mod, monkeypatch, tmp_path, fail_deploy=True)

    posts = []

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def post(self, url, content=None, headers=None, json=None):
            posts.append(
                {
                    "url": url,
                    "content": content,
                    "headers": headers or {},
                }
            )
            return type("R", (), {"status_code": 200})()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    pd.begin_run("default")
    asyncio.run(
        pd.run_publish(
            "default",
            {"PUBLISH_SFTP_PASS:default": "pw"},
            password="pw",
        )
    )
    assert len(posts) == 1
    body = json.loads(posts[0]["content"].decode("utf-8"))
    assert body["event"] == "publish.failed"
    assert body["site_id"] == "default"
    assert body["error"]
    assert body["published_at"] is None
    assert pd.get_run_status("default")["status"] == "error"
    assert get_publish_target("default")["last_status"] == "failed"


def test_build_site_dist_widens_venv_only_path(monkeypatch, tmp_path):
    """systemd PATH=…/.venv/bin must still find bash/php/python3."""
    import asyncio

    from services import publish_deploy as pd

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html></html>", encoding="utf-8")
    build_sh = tmp_path / "build.sh"
    build_sh.write_text("#!/bin/bash\n", encoding="utf-8")

    monkeypatch.setattr(
        pd,
        "resolve_build_paths",
        lambda: {
            "repo_root": tmp_path,
            "build_sh": build_sh,
            "cli_dir": tmp_path,
            "dist_dir": dist,
        },
    )
    monkeypatch.setenv("PATH", "/opt/pencms/.venv/bin")

    captured: dict = {}

    async def fake_run(args, *, cwd=None, env=None, **_k):
        captured["env"] = env
        captured["args"] = args
        return 0, "", ""

    monkeypatch.setattr(pd, "_run_cmd", fake_run)

    result = asyncio.run(pd.build_site_dist("freehost", "freehost.website", {}))
    assert result == dist
    path = captured["env"]["PATH"]
    assert path.startswith("/opt/pencms/.venv/bin")
    assert "/usr/bin" in path
    assert "/bin" in path
    assert captured["args"][0] == "bash"
    assert captured["args"][1] == str(build_sh)