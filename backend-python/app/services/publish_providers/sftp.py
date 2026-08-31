"""SFTP publish provider — OpenSSH batch upload + ssh_client probe."""

from __future__ import annotations

import asyncio
import os
import shlex
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from services.publish_providers.base import PublishDeployError, PublishProvider
from services.ssh_client import (
    askpass_env,
    compose_uri,
    parse_sftp_uri,
    ssh_exec,
    ssh_opt_args,
)
from services.storage_provider import vault_secrets

# Cap paths per ``ssh … rm -f`` invocation to keep argv bounded.
_RM_CHUNK_SIZE = 40


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


def _ssh_opts_from_scp_opts(opts: List[str]) -> List[str]:
    """Convert scp ``-P`` port flags to ssh ``-p``."""
    ssh_opts: List[str] = []
    i = 0
    while i < len(opts):
        if opts[i] == "-P" and i + 1 < len(opts):
            ssh_opts += ["-p", opts[i + 1]]
            i += 2
            continue
        ssh_opts.append(opts[i])
        i += 1
    return ssh_opts


def _upload_session(
    target: Dict[str, Any],
    password: Optional[str],
) -> Tuple[Dict[str, str], Optional[str], List[str], List[str], str, str, str]:
    """Build env, askpass path, scp opts, ssh opts, and connection pieces."""
    host = target["host"]
    port = int(target.get("port") or 22)
    username = target["username"]
    remote_path = (target.get("remote_path") or "/").rstrip("/") or "/"

    use_password = bool(password)
    askpass_path: Optional[str] = None
    if use_password:
        env, askpass_path = askpass_env(password or "")
    else:
        env = {**os.environ}
        if "PATH" in env and "/usr/bin" not in env["PATH"]:
            env["PATH"] = env["PATH"] + ":/usr/bin:/bin"

    opts = ssh_opt_args(port, password=use_password)
    ssh_opts = _ssh_opts_from_scp_opts(opts)
    return env, askpass_path, opts, ssh_opts, host, username, remote_path


async def _ssh_mkdir(
    *,
    env: Dict[str, str],
    ssh_opts: List[str],
    host: str,
    username: str,
    remote_dir: str,
    log_line: Callable[[str], None],
) -> None:
    mkdir_args = (
        ["/usr/bin/ssh"]
        + ssh_opts
        + [f"{username}@{host}", f"mkdir -p {shlex.quote(remote_dir)}"]
    )
    rc, stdout, stderr = await _run_cmd(
        mkdir_args,
        env=env,
        timeout=60.0,
        start_new_session=True,
    )
    if stdout.strip():
        log_line(stdout.strip())
    if stderr.strip():
        log_line(stderr.strip())
    if rc != 0:
        raise PublishDeployError(
            f"Remote mkdir failed (exit {rc}): "
            f"{stderr.strip() or stdout.strip() or 'no output'}"
        )


async def _remote_delete_paths(
    *,
    env: Dict[str, str],
    ssh_opts: List[str],
    host: str,
    username: str,
    remote_path: str,
    rel_paths: List[str],
    log_line: Callable[[str], None],
) -> None:
    """Delete remote files under ``remote_path`` for the given relative paths."""
    if not rel_paths:
        return
    base = remote_path.rstrip("/") or "/"
    for i in range(0, len(rel_paths), _RM_CHUNK_SIZE):
        chunk = rel_paths[i : i + _RM_CHUNK_SIZE]
        remote_files = [f"{base}/{rel}" for rel in chunk]
        quoted = " ".join(shlex.quote(p) for p in remote_files)
        rm_args = (
            ["/usr/bin/ssh"]
            + ssh_opts
            + [f"{username}@{host}", f"rm -f -- {quoted}"]
        )
        log_line(f"Deleting {len(chunk)} remote file(s)…")
        rc, stdout, stderr = await _run_cmd(
            rm_args,
            env=env,
            timeout=120.0,
            start_new_session=True,
        )
        if stdout.strip():
            log_line(stdout.strip())
        if stderr.strip():
            log_line(stderr.strip())
        if rc != 0:
            raise PublishDeployError(
                f"Remote delete failed (exit {rc}): "
                f"{stderr.strip() or stdout.strip() or 'no output'}"
            )


def _tar_pipe_to_ssh_sync(
    *,
    env: Dict[str, str],
    ssh_opts: List[str],
    host: str,
    username: str,
    remote_path: str,
    dist_dir: Path,
    timeout: float = 600.0,
) -> tuple[int, str, str]:
    """Stream dist contents into remote_path: ``tar cf - | ssh … 'tar xf -'``."""
    import subprocess

    # Absolute tar, plus env= (PATH widened by _upload_session). Bare "tar"
    # inherits the API process PATH, which systemd may set to venv-only.
    tar_args = ["/usr/bin/tar", "-C", str(dist_dir), "-cf", "-", "."]
    remote_cmd = f"tar -C {shlex.quote(remote_path)} -xf -"
    ssh_args = ["/usr/bin/ssh"] + ssh_opts + [f"{username}@{host}", remote_cmd]

    try:
        tar_proc = subprocess.Popen(
            tar_args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
    except FileNotFoundError as e:
        raise PublishDeployError(
            "Cannot find tar "
            f"({e}). systemd PATH must include /usr/bin:/bin."
        ) from e
    assert tar_proc.stdout is not None
    try:
        ssh_proc = subprocess.Popen(
            ssh_args,
            stdin=tar_proc.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            start_new_session=True,
        )
    except FileNotFoundError as e:
        tar_proc.kill()
        tar_proc.wait(timeout=5)
        raise PublishDeployError(
            "Cannot find ssh "
            f"({e}). systemd PATH must include /usr/bin:/bin."
        ) from e
    except Exception:
        tar_proc.kill()
        tar_proc.wait(timeout=5)
        raise
    tar_proc.stdout.close()

    try:
        ssh_out_b, ssh_err_b = ssh_proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        ssh_proc.kill()
        tar_proc.kill()
        ssh_proc.communicate()
        tar_proc.wait(timeout=5)
        return 255, "", f"Upload timed out after {timeout}s"

    tar_err_b = tar_proc.stderr.read() if tar_proc.stderr else b""
    tar_rc = tar_proc.wait(timeout=30)

    stdout = (ssh_out_b or b"").decode(errors="replace")
    stderr = (
        (tar_err_b or b"").decode(errors="replace")
        + (ssh_err_b or b"").decode(errors="replace")
    )
    if tar_rc != 0:
        return tar_rc, stdout, stderr or f"tar exited {tar_rc}"
    return ssh_proc.returncode or 0, stdout, stderr


async def _tar_pipe_to_ssh(
    *,
    env: Dict[str, str],
    ssh_opts: List[str],
    host: str,
    username: str,
    remote_path: str,
    dist_dir: Path,
    timeout: float = 600.0,
) -> tuple[int, str, str]:
    return await asyncio.to_thread(
        _tar_pipe_to_ssh_sync,
        env=env,
        ssh_opts=ssh_opts,
        host=host,
        username=username,
        remote_path=remote_path,
        dist_dir=dist_dir,
        timeout=timeout,
    )


async def _scp_upload(
    target: Dict[str, Any],
    password: Optional[str],
    dist_dir: Path,
    *,
    log_line: Callable[[str], None],
    set_phase: Optional[Callable[[str], None]] = None,
) -> None:
    """Full-tree upload of ``dist/`` contents into ``remote_path`` (tar|ssh)."""
    env, askpass_path, _opts, ssh_opts, host, username, remote_path = _upload_session(
        target, password
    )

    try:
        auth_label = "password" if password else "key (BatchMode)"
        if set_phase:
            set_phase("uploading")
        log_line(f"Ensuring remote path {remote_path} exists ({auth_label})…")
        await _ssh_mkdir(
            env=env,
            ssh_opts=ssh_opts,
            host=host,
            username=username,
            remote_dir=remote_path,
            log_line=log_line,
        )

        remote = f"{username}@{host}:{remote_path}/"
        log_line(f"Uploading {dist_dir}/ → {remote} (tar|ssh)")
        rc, stdout, stderr = await _tar_pipe_to_ssh(
            env=env,
            ssh_opts=ssh_opts,
            host=host,
            username=username,
            remote_path=remote_path,
            dist_dir=dist_dir,
            timeout=600.0,
        )
        if stdout.strip():
            for line in stdout.splitlines():
                log_line(line)
        if stderr.strip():
            for line in stderr.splitlines():
                log_line(line)
        if rc != 0:
            raise PublishDeployError(
                f"Upload failed (exit {rc}): "
                f"{stderr.strip() or stdout.strip() or 'no output'}"
            )
    finally:
        if askpass_path and os.path.exists(askpass_path):
            try:
                os.unlink(askpass_path)
            except OSError:
                pass


async def _incremental_upload(
    target: Dict[str, Any],
    password: Optional[str],
    dist_dir: Path,
    upload_rels: List[str],
    *,
    log_line: Callable[[str], None],
    set_phase: Optional[Callable[[str], None]] = None,
) -> None:
    """Upload only the listed relative paths via per-file scp."""
    if not upload_rels:
        if set_phase:
            set_phase("uploading")
        log_line("No files to upload.")
        return

    env, askpass_path, opts, ssh_opts, host, username, remote_path = _upload_session(
        target, password
    )
    parents_made: set[str] = set()

    try:
        auth_label = "password" if password else "key (BatchMode)"
        if set_phase:
            set_phase("uploading")
        log_line(
            f"Incremental upload: {len(upload_rels)} file(s) "
            f"→ {remote_path} ({auth_label})"
        )
        await _ssh_mkdir(
            env=env,
            ssh_opts=ssh_opts,
            host=host,
            username=username,
            remote_dir=remote_path,
            log_line=log_line,
        )

        for rel in upload_rels:
            local = dist_dir / rel
            if not local.is_file():
                raise PublishDeployError(f"Local dist file missing: {rel}")
            parent = str(Path(rel).parent).replace("\\", "/")
            if parent and parent != ".":
                remote_parent = f"{remote_path}/{parent}"
                if remote_parent not in parents_made:
                    await _ssh_mkdir(
                        env=env,
                        ssh_opts=ssh_opts,
                        host=host,
                        username=username,
                        remote_dir=remote_parent,
                        log_line=log_line,
                    )
                    parents_made.add(remote_parent)

            dest = f"{username}@{host}:{remote_path}/{rel}"
            scp_args = ["/usr/bin/scp"] + opts + [str(local), dest]
            log_line(f"scp {rel}")
            rc, stdout, stderr = await _run_cmd(
                scp_args,
                env=env,
                timeout=120.0,
                start_new_session=True,
            )
            if stdout.strip():
                log_line(stdout.strip())
            if stderr.strip():
                log_line(stderr.strip())
            if rc != 0:
                raise PublishDeployError(
                    f"scp failed for {rel} (exit {rc}): "
                    f"{stderr.strip() or stdout.strip() or 'no output'}"
                )
    finally:
        if askpass_path and os.path.exists(askpass_path):
            try:
                os.unlink(askpass_path)
            except OSError:
                pass


async def _apply_remote_deletes(
    target: Dict[str, Any],
    password: Optional[str],
    removed: List[str],
    *,
    log_line: Callable[[str], None],
) -> None:
    """Delete remote orphans listed in ``removed`` (relative paths)."""
    if not removed:
        return
    env, askpass_path, _opts, ssh_opts, host, username, remote_path = _upload_session(
        target, password
    )
    try:
        await _remote_delete_paths(
            env=env,
            ssh_opts=ssh_opts,
            host=host,
            username=username,
            remote_path=remote_path,
            rel_paths=removed,
            log_line=log_line,
        )
    finally:
        if askpass_path and os.path.exists(askpass_path):
            try:
                os.unlink(askpass_path)
            except OSError:
                pass


class SftpPublishProvider(PublishProvider):
    """Default publish adapter: OpenSSH tar|ssh / scp + orphan deletes."""

    id = "sftp"
    label = "SFTP"
    enabled = True
    vault_http_alias = "X-Vault-Publish-Pass"

    def capabilities(self) -> Dict[str, Any]:
        return {
            "incremental": True,
            "auth_methods": ["password", "key"],
            "force_full": True,
        }

    def vault_key(self, site_id: str) -> Optional[str]:
        return f"PUBLISH_SFTP_PASS:{site_id}"

    def yaml_fields(self) -> List[str]:
        return ["host", "port", "username", "remote_path"]

    def is_configured(self, block: Optional[Dict[str, Any]]) -> bool:
        if not block or not isinstance(block, dict):
            return False
        return bool(
            self._opt_str(block.get("host"))
            and self._opt_str(block.get("username"))
            and self._opt_str(block.get("remote_path"))
        )

    def normalize(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        host = self._opt_str(payload.get("host"))
        username = self._opt_str(payload.get("username"))
        remote_path = self._opt_str(payload.get("remote_path"))
        if not host:
            raise ValueError("host is required")
        if not username:
            raise ValueError("username is required")
        if not remote_path:
            raise ValueError("remote_path is required")
        port_raw = payload.get("port", 22)
        try:
            port = (
                int(port_raw)
                if port_raw is not None and str(port_raw).strip() != ""
                else 22
            )
        except (TypeError, ValueError) as e:
            raise ValueError("port must be an integer") from e
        if port < 1 or port > 65535:
            raise ValueError("port must be between 1 and 65535")
        return {
            "host": host,
            "port": port,
            "username": username,
            "remote_path": remote_path,
        }

    def ui_schema(self) -> Dict[str, Any]:
        return {
            "fields": [
                {
                    "name": "host",
                    "label": "Host",
                    "type": "text",
                    "required": True,
                    "placeholder": "example.com",
                },
                {
                    "name": "port",
                    "label": "Port",
                    "type": "number",
                    "required": False,
                    "placeholder": "22",
                },
                {
                    "name": "username",
                    "label": "SFTP user",
                    "type": "text",
                    "required": True,
                    "placeholder": "deploy",
                },
                {
                    "name": "remote_path",
                    "label": "Remote path",
                    "type": "text",
                    "required": True,
                    "placeholder": "/var/www/html",
                },
            ],
            "secret": {
                "label": "SFTP password",
                "placeholder": "Enter SFTP password",
                "http_alias": self.vault_http_alias,
            },
            "public_url_help": (
                "Optional. Use the URL visitors should open after you publish "
                "to this host."
            ),
            "auth_hint": (
                "Unlock the vault, confirm the SFTP password in Settings, "
                "then Test Connection."
            ),
        }

    async def test(self) -> Dict[str, Any]:
        """Probe remote mkdir/write/rm via the Core SSH transport helper."""
        target = self._target
        site_id = self._site_id
        auth_method = (target.get("auth_method") or "password").strip().lower()
        if auth_method not in ("password", "key"):
            return {
                "success": False,
                "error": f"Unsupported publish auth_method: {auth_method}",
            }

        try:
            uri = compose_uri(
                target["host"],
                int(target.get("port") or 22),
                target["username"],
                target["remote_path"],
            )
            parsed = parse_sftp_uri(uri)
        except (TypeError, ValueError) as e:
            return {"success": False, "error": f"Invalid publish URI: {e}"}

        secret_key = f"PUBLISH_SFTP_PASS:{site_id}"
        password = None
        if auth_method == "password":
            password = (self._password or "").strip() or None
            if not password:
                password = vault_secrets.get().get(secret_key) or None
            if not password:
                return {
                    "success": False,
                    "error": (
                        "Publish SFTP password missing: unlock the vault and set "
                        f"{secret_key}, send X-Vault-Publish-Pass, or pass password "
                        "in the body for smoke"
                    ),
                }

        base = parsed["path"]
        probe = f"{base}/.pencms-probe"
        cmd = (
            f"echo PENCMS_OK && "
            f"mkdir -p {shlex.quote(base)} && "
            f"touch {shlex.quote(probe)} && "
            f"rm -f {shlex.quote(probe)}"
        )

        start = time.monotonic()
        try:
            rc, stdout, stderr = await asyncio.wait_for(
                ssh_exec(
                    user=parsed["user"],
                    host=parsed["host"],
                    port=parsed["port"],
                    command=cmd,
                    password=password,
                ),
                timeout=30,
            )
        except asyncio.TimeoutError:
            elapsed_ms = round((time.monotonic() - start) * 1000)
            return {
                "success": False,
                "error": f"Connection timed out after {elapsed_ms}ms",
            }
        except Exception as e:
            elapsed_ms = round((time.monotonic() - start) * 1000)
            return {
                "success": False,
                "error": f"SSH execution failed: {e}",
                "latency_ms": elapsed_ms,
            }

        elapsed_ms = round((time.monotonic() - start) * 1000)

        if rc != 0:
            error_msg = stderr.decode(errors="replace").strip()
            if not error_msg:
                error_msg = f"SSH exited with code {rc} (no error message)"
            return {"success": False, "error": error_msg, "latency_ms": elapsed_ms}

        output = stdout.decode(errors="replace").strip()
        err_output = stderr.decode(errors="replace").strip()
        if "PENCMS_OK" not in output:
            detail = f"Unexpected output: {output}"
            if err_output:
                detail += f" | stderr: {err_output}"
            return {"success": False, "error": detail, "latency_ms": elapsed_ms}

        return {"success": True, "latency_ms": elapsed_ms}

    async def deploy(
        self,
        dist_dir: Path,
        *,
        force_full: bool,
        upload_rels: List[str],
        removed: List[str],
        total_files: int,
        log_line: Callable[[str], None],
        set_phase: Optional[Callable[[str], None]] = None,
    ) -> Optional[Dict[str, Any]]:
        target = self._target
        password = self._password

        if force_full:
            await _scp_upload(
                target,
                password,
                dist_dir,
                log_line=log_line,
                set_phase=set_phase,
            )
        else:
            await _incremental_upload(
                target,
                password,
                dist_dir,
                upload_rels,
                log_line=log_line,
                set_phase=set_phase,
            )

        await _apply_remote_deletes(
            target,
            password,
            removed,
            log_line=log_line,
        )
        return None
