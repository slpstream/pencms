"""Publish deploy orchestration: build static site + provider upload.

After ``build.sh --site=``, uploads ``frontend-php/dist/`` via the configured
publish provider (default SFTP / OpenSSH). Default is incremental (path→hash
manifest); ``force_full`` or a missing manifest uses full-tree upload. Does not
loop per-file SSH content writes. Interactive vault passwords are snapshotted
at request time (ContextVar does not survive BackgroundTasks).

Also owns browser export: build + zip of ``dist/`` (no host upload).
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import io
import json
import os
import threading
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx

from services.publish_manifests import (
    diff_manifests,
    hash_dist_tree,
    load_manifest,
    save_manifest,
)
from services.publish_providers import (
    PublishDeployError,
    get_provider,
)
from services.publish_providers.registry import (
    ProviderNotEnabledError,
    UnknownPublishProviderError,
)
from services.site_service import (
    get_publish_target,
    get_publish_webhook_secret,
    get_site,
    set_publish_target,
)

# Truncate run logs so status payloads stay bounded (S5 will surface these).
_MAX_LOG_LINES = 500

# In-memory run registry (MCP PUSH_TASKS pattern). Keyed by site_id.
_RUNS: Dict[str, Dict[str, Any]] = {}
_LOCK = threading.Lock()

# Sites currently building a browser export zip (shares dist/ with publish).
_EXPORT_BUSY: set = set()


class PublishBusyError(Exception):
    """Raised when a publish run is already in progress for the site."""

    def __init__(self, site_id: str, task_id: str):
        self.site_id = site_id
        self.task_id = task_id
        super().__init__(f"Publish already running for site '{site_id}' (task {task_id})")


class ExportBusyError(Exception):
    """Raised when an export zip is already in progress for the site."""

    def __init__(self, site_id: str):
        self.site_id = site_id
        super().__init__(f"Export already running for site '{site_id}'")


# Re-export for callers/tests that import from publish_deploy.
__all__ = [
    "ExportBusyError",
    "PublishBusyError",
    "PublishDeployError",
    "begin_run",
    "build_site_dist",
    "clear_runs",
    "domain_for_site",
    "export_site_zip",
    "get_run_status",
    "resolve_build_paths",
    "run_publish",
    "zip_dist_tree",
]


def _repo_root() -> Path:
    # backend-python/app/services/this_file.py → repo root (not config.BASE_DIR;
    # tests monkeypatch BASE_DIR to a temp tree).
    return Path(__file__).resolve().parent.parent.parent.parent


def resolve_build_paths() -> Dict[str, Path]:
    """Return paths for build.sh, its cwd, and the dist output tree."""
    root = _repo_root()
    cli = root / "frontend-php" / "cli-tools"
    return {
        "repo_root": root,
        "build_sh": cli / "build.sh",
        "cli_dir": cli,
        "dist_dir": root / "frontend-php" / "dist",
    }


def domain_for_site(target: Dict[str, Any], site_id: str) -> str:
    """Hostname for ``build.sh --domain``: public_url host, else registry domain."""
    public_url = (target.get("public_url") or "").strip()
    if public_url:
        parsed = urlparse(
            public_url if "://" in public_url else f"https://{public_url}"
        )
        if parsed.hostname:
            return parsed.hostname
        # Bare host/path without parseable hostname
        cleaned = public_url.replace("https://", "").replace("http://", "").strip("/")
        if cleaned:
            return cleaned.split("/")[0]
    site = get_site(site_id)
    if site and site.domain:
        return site.domain
    return ""


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _append_log(run: Dict[str, Any], line: str) -> None:
    log: List[str] = run.setdefault("log", [])
    log.append(line.rstrip("\n"))
    if len(log) > _MAX_LOG_LINES:
        del log[: len(log) - _MAX_LOG_LINES]


def _run_snapshot(run: Dict[str, Any]) -> Dict[str, Any]:
    """Public status payload (no secrets)."""
    return {
        "task_id": run.get("task_id"),
        "site_id": run.get("site_id"),
        "status": run.get("status"),
        "phase": run.get("phase"),
        "started_at": run.get("started_at"),
        "finished_at": run.get("finished_at"),
        "error": run.get("error"),
        "log": list(run.get("log") or []),
    }


def get_run_status(site_id: str, task_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Return the in-memory run for a site, or None if none recorded."""
    with _LOCK:
        run = _RUNS.get(site_id)
        if run is None:
            return None
        if task_id and run.get("task_id") != task_id:
            return None
        return _run_snapshot(run)


def clear_runs() -> None:
    """Test helper: wipe the in-memory registry."""
    with _LOCK:
        _RUNS.clear()
        _EXPORT_BUSY.clear()


def begin_run(site_id: str) -> Dict[str, Any]:
    """Register a new running task for site_id. Raises PublishBusyError if busy."""
    task_id = str(uuid.uuid4())
    with _LOCK:
        existing = _RUNS.get(site_id)
        if existing and existing.get("status") == "running":
            raise PublishBusyError(site_id, existing.get("task_id") or "")
        run = {
            "task_id": task_id,
            "site_id": site_id,
            "status": "running",
            "phase": "building",
            "started_at": _utcnow_iso(),
            "finished_at": None,
            "error": None,
            "log": [],
        }
        _RUNS[site_id] = run
        return _run_snapshot(run)


def _update_run(site_id: str, **fields: Any) -> None:
    with _LOCK:
        run = _RUNS.get(site_id)
        if not run:
            return
        for key, value in fields.items():
            if key == "log_line":
                _append_log(run, str(value))
            else:
                run[key] = value


def _mark_failed(site_id: str, error: str) -> None:
    _update_run(
        site_id,
        status="error",
        phase="done",
        finished_at=_utcnow_iso(),
        error=error,
        log_line=f"ERROR: {error}",
    )
    try:
        set_publish_target(site_id, {"last_status": "failed"})
    except Exception as e:  # noqa: BLE001 — status persistence must not hide deploy error
        _update_run(site_id, log_line=f"WARN: failed to persist last_status: {e}")


def _mark_success(
    site_id: str,
    *,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    published_at = _utcnow_iso()
    _update_run(
        site_id,
        status="success",
        phase="done",
        finished_at=published_at,
        error=None,
        log_line="Publish completed successfully.",
    )
    try:
        payload: Dict[str, Any] = {
            "last_status": "ok",
            "last_published_at": published_at,
        }
        if extra:
            if extra.get("public_url"):
                payload["public_url"] = extra["public_url"]
            try:
                current = get_publish_target(site_id)
                adapter = get_provider(current.get("provider") or "sftp")
                for field in adapter.yaml_fields():
                    if extra.get(field):
                        payload[field] = extra[field]
            except (UnknownPublishProviderError, ProviderNotEnabledError):
                pass
        set_publish_target(site_id, payload)
    except Exception as e:  # noqa: BLE001
        _update_run(site_id, log_line=f"WARN: failed to persist last_status: {e}")


async def _maybe_fire_webhook(
    site_id: str,
    *,
    webhook_url: Optional[str],
    webhook_secret: Optional[str] = None,
    event: str,
    provider: Optional[str] = None,
    public_url: Optional[str] = None,
    published_at: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    """POST publish event JSON to webhook_url; no-op if unset. Never raises.

    When ``webhook_secret`` is set, signs the exact request body with
    ``X-PenCMS-Signature: sha256=<hex>``.
    """
    url = (webhook_url or "").strip()
    if not url:
        return
    lower = url.lower()
    if not (lower.startswith("http://") or lower.startswith("https://")):
        _update_run(
            site_id,
            log_line=f"WARN: webhook skipped (invalid URL scheme): {url}",
        )
        return

    body: Dict[str, Any] = {
        "event": event,
        "site_id": site_id,
        "provider": provider or None,
        "public_url": public_url or None,
        "published_at": published_at or None,
    }
    if event == "publish.failed":
        body["error"] = error or "Unknown publish error"

    body_bytes = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    secret = (webhook_secret or "").strip()
    if secret:
        digest = hmac.new(
            secret.encode("utf-8"), body_bytes, hashlib.sha256
        ).hexdigest()
        headers["X-PenCMS-Signature"] = f"sha256={digest}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, content=body_bytes, headers=headers)
            if resp.status_code >= 400:
                _update_run(
                    site_id,
                    log_line=(
                        f"WARN: webhook returned HTTP {resp.status_code} "
                        f"for {url}"
                    ),
                )
            else:
                _update_run(
                    site_id,
                    log_line=f"Webhook notified ({resp.status_code}): {url}",
                )
    except httpx.HTTPError as e:
        _update_run(site_id, log_line=f"WARN: webhook failed: {e}")
    except Exception as e:  # noqa: BLE001 — never fail the publish for webhook
        _update_run(site_id, log_line=f"WARN: webhook failed: {e}")


async def _run_cmd(
    args: List[str],
    *,
    cwd: Optional[Path] = None,
    env: Optional[Dict[str, str]] = None,
    timeout: Optional[float] = None,
    start_new_session: bool = False,
) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        *args,
        cwd=str(cwd) if cwd else None,
        env=env,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=start_new_session,
    )
    try:
        if timeout is not None:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        else:
            stdout_b, stderr_b = await proc.communicate()
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except OSError:
            pass
        return 255, "", f"Command timed out after {timeout}s"
    stdout = (stdout_b or b"").decode(errors="replace")
    stderr = (stderr_b or b"").decode(errors="replace")
    return proc.returncode or 0, stdout, stderr


async def build_site_dist(
    site_id: str,
    domain: str,
    vault: Dict[str, str],
    *,
    log_line: Optional[Callable[[str], None]] = None,
) -> Path:
    """Run ``build.sh --site=`` and return the ``dist/`` path.

    Raises ``PublishDeployError`` on missing script, missing bash/php on PATH,
    non-zero exit, or empty / missing dist (never treat a failed build as a
    usable tree).
    """
    def _log(msg: str) -> None:
        if log_line:
            log_line(msg)

    paths = resolve_build_paths()
    build_sh = paths["build_sh"]
    if not build_sh.is_file():
        raise PublishDeployError(f"build.sh not found at {build_sh}")

    env = {**os.environ}
    env["PENCMS_SKIP_INDEXNOW"] = "1"
    if vault.get("CONTENT_SFTP_PASS"):
        env["VAULT_CONTENT_PASS"] = vault["CONTENT_SFTP_PASS"]
    if vault.get("ASSETS_SFTP_PASS"):
        env["VAULT_ASSETS_PASS"] = vault["ASSETS_SFTP_PASS"]
    # systemd Environment=PATH=…/.venv/bin replaces PATH; build.sh needs
    # bash, php, and python3 from the host (same append as SFTP askpass).
    if "PATH" in env and "/usr/bin" not in env["PATH"]:
        env["PATH"] = env["PATH"] + ":/usr/bin:/bin"

    args = ["bash", str(build_sh), f"--site={site_id}", "--domain", domain]
    _log(f"Building: {' '.join(args)}")
    try:
        rc, stdout, stderr = await _run_cmd(args, cwd=paths["cli_dir"], env=env)
    except FileNotFoundError as e:
        raise PublishDeployError(
            "Cannot find bash/php on PATH "
            f"({e}). systemd PATH must include /usr/bin:/bin."
        ) from e
    for line in (stdout + stderr).splitlines():
        if line.strip():
            _log(line)
    if rc != 0:
        raise PublishDeployError(f"build.sh exited with code {rc}")

    dist = paths["dist_dir"]
    if not dist.is_dir():
        raise PublishDeployError(f"Build produced no dist directory at {dist}")
    # Require at least one entry so we do not ship an empty tree silently.
    if not any(dist.iterdir()):
        raise PublishDeployError(f"Build produced an empty dist directory at {dist}")
    return dist


async def _build_site(
    site_id: str,
    domain: str,
    vault: Dict[str, str],
) -> None:
    """Publish-run wrapper: build with status-registry logging."""
    _update_run(site_id, phase="building")

    def log(msg: str) -> None:
        _update_run(site_id, log_line=msg)

    await build_site_dist(site_id, domain, vault, log_line=log)


def zip_dist_tree(dist_dir: Path) -> bytes:
    """Zip contents of ``dist/`` with archive-root paths (no wrapping folder).

    Raises ``PublishDeployError`` if there are no files (never return empty zip
    as a successful export).
    """
    buf = io.BytesIO()
    count = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(dist_dir.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(dist_dir).as_posix()
            if not rel or rel.startswith(".."):
                continue
            zf.write(path, rel)
            count += 1
    if count == 0:
        raise PublishDeployError("dist/ has no files to export")
    return buf.getvalue()


def _assert_dist_idle(site_id: str) -> None:
    """Reject when publish or export already owns ``dist/`` for this site."""
    with _LOCK:
        run = _RUNS.get(site_id)
        if run and run.get("status") == "running":
            raise PublishBusyError(site_id, run.get("task_id") or "")
        if site_id in _EXPORT_BUSY:
            raise ExportBusyError(site_id)


async def export_site_zip(
    site_id: str,
    vault: Dict[str, str],
) -> Tuple[bytes, str]:
    """Build the site and return ``(zip_bytes, filename)``.

    Does not require a configured publish host. Autostart for the UI means
    the browser begins the download after this returns — no offline preview
    helper is bundled in the archive.
    """
    _assert_dist_idle(site_id)
    with _LOCK:
        if site_id in _EXPORT_BUSY:
            raise ExportBusyError(site_id)
        _EXPORT_BUSY.add(site_id)

    try:
        # May be unconfigured; still supplies public_url / validates site exists.
        target = get_publish_target(site_id)
        domain = domain_for_site(target, site_id)
        dist = await build_site_dist(site_id, domain, vault)
        data = zip_dist_tree(dist)
        filename = f"{site_id}-static.zip"
        return data, filename
    finally:
        with _LOCK:
            _EXPORT_BUSY.discard(site_id)


async def run_publish(
    site_id: str,
    vault: Dict[str, str],
    *,
    password: Optional[str] = None,
    force_full: bool = False,
) -> None:
    """Background worker: build then upload via provider adapter. Updates registry."""
    try:
        target = get_publish_target(site_id)
        if not target.get("configured"):
            raise PublishDeployError("Publish target is not configured")

        provider_id = (target.get("provider") or "sftp").strip().lower() or "sftp"
        auth_method = (target.get("auth_method") or "password").strip().lower()
        if auth_method not in ("password", "key", "token"):
            raise PublishDeployError(f"Unsupported publish auth_method: {auth_method}")

        passwd: Optional[str] = None
        if auth_method == "password":
            secret_key = f"PUBLISH_SFTP_PASS:{site_id}"
            passwd = (password or "").strip() or vault.get(secret_key) or ""
            if not passwd:
                raise PublishDeployError(
                    f"Publish SFTP password missing ({secret_key})"
                )
        elif auth_method == "token":
            try:
                adapter = get_provider(provider_id)
                secret_key = adapter.vault_key(site_id) or ""
            except (UnknownPublishProviderError, ProviderNotEnabledError):
                secret_key = ""
            if not secret_key:
                raise PublishDeployError(
                    f"Publish API token vault key missing for provider '{provider_id}'"
                )
            passwd = (password or "").strip() or vault.get(secret_key) or ""
            if not passwd:
                raise PublishDeployError(
                    f"Publish API token missing ({secret_key})"
                )
        # key auth: passwd stays None → BatchMode scp with install id_ed25519

        try:
            provider = get_provider(provider_id)
        except (UnknownPublishProviderError, ProviderNotEnabledError) as e:
            raise PublishDeployError(str(e)) from e

        domain = domain_for_site(target, site_id)
        await _build_site(site_id, domain, vault)

        paths = resolve_build_paths()
        dist_dir = paths["dist_dir"]
        new_files = hash_dist_tree(dist_dir)
        prior = load_manifest(site_id)
        diff = diff_manifests(prior, new_files)
        upload_rels = sorted(diff["added"] + diff["changed"])
        removed = diff["removed"]
        do_full = force_full or prior is None

        # Providers without incremental always full-upload.
        caps = provider.capabilities()
        if not caps.get("incremental", False):
            do_full = True

        if do_full:
            reason = "forced" if force_full else "first"
            _update_run(
                site_id,
                log_line=(
                    f"Full upload ({reason}): {len(new_files)} file(s), "
                    f"{len(removed)} remote delete(s)"
                ),
            )
        else:
            _update_run(
                site_id,
                log_line=(
                    f"Incremental: {len(upload_rels)} upload, "
                    f"{len(removed)} delete, {len(diff['unchanged'])} unchanged"
                ),
            )

        provider.configure(target, password=passwd, site_id=site_id)

        def log_line(msg: str) -> None:
            _update_run(site_id, log_line=msg)

        def set_phase(phase: str) -> None:
            _update_run(site_id, phase=phase)

        deploy_result = await provider.deploy(
            dist_dir,
            force_full=do_full,
            upload_rels=upload_rels,
            removed=removed,
            total_files=len(new_files),
            log_line=log_line,
            set_phase=set_phase,
        )

        save_manifest(site_id, new_files)
        _update_run(
            site_id,
            log_line=f"Manifest saved ({len(new_files)} file(s)).",
        )
        extra = deploy_result if isinstance(deploy_result, dict) else None
        _mark_success(site_id, extra=extra)

        # Re-read target so public_url reflects any provider-updated value.
        fresh = get_publish_target(site_id)
        try:
            from services.indexnow import maybe_ping_indexnow

            ping_rels = None if do_full else sorted(diff["added"] + diff["changed"])
            maybe_ping_indexnow(
                site_id,
                fresh.get("public_url") or target.get("public_url"),
                dist_dir,
                ping_rels,
                log_line=lambda msg: _update_run(site_id, log_line=msg),
            )
        except Exception as exc:  # noqa: BLE001 — never fail publish on ping
            _update_run(
                site_id,
                log_line=f"IndexNow ping failed (publish continues): {exc}",
            )

        webhook_url = target.get("webhook_url") or fresh.get("webhook_url")
        await _maybe_fire_webhook(
            site_id,
            webhook_url=webhook_url,
            webhook_secret=get_publish_webhook_secret(site_id),
            event="publish.success",
            provider=fresh.get("provider") or target.get("provider"),
            public_url=fresh.get("public_url") or target.get("public_url"),
            published_at=fresh.get("last_published_at"),
        )
    except PublishDeployError as e:
        _mark_failed(site_id, str(e))
        try:
            failed_target = get_publish_target(site_id)
        except ValueError:
            failed_target = {}
        try:
            failed_secret = get_publish_webhook_secret(site_id)
        except ValueError:
            failed_secret = None
        await _maybe_fire_webhook(
            site_id,
            webhook_url=failed_target.get("webhook_url"),
            webhook_secret=failed_secret,
            event="publish.failed",
            provider=failed_target.get("provider"),
            public_url=failed_target.get("public_url"),
            published_at=None,
            error=str(e),
        )
    except Exception as e:  # noqa: BLE001 — surface unexpected failures in status
        err_msg = f"Unexpected publish error: {e}"
        _mark_failed(site_id, err_msg)
        try:
            failed_target = get_publish_target(site_id)
        except ValueError:
            failed_target = {}
        try:
            failed_secret = get_publish_webhook_secret(site_id)
        except ValueError:
            failed_secret = None
        await _maybe_fire_webhook(
            site_id,
            webhook_url=failed_target.get("webhook_url"),
            webhook_secret=failed_secret,
            event="publish.failed",
            provider=failed_target.get("provider"),
            public_url=failed_target.get("public_url"),
            published_at=None,
            error=err_msg,
        )
