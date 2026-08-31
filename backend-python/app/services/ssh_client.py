"""OpenSSH transport used by Core SFTP publish (probe + upload helpers).

Content/assets ``storage_type=ssh`` is Pro. This module is the shared client
``SftpPublishProvider`` (and the overlay SSH storage backend) call.
"""

from __future__ import annotations

import asyncio
import os
import shlex
import socket as _socket
import tempfile
from typing import Dict, List, Optional
from urllib.parse import urlparse


def control_paths() -> tuple[str, str]:
    control_dir = os.environ.get("XDG_RUNTIME_DIR", os.path.expanduser("~/.ssh"))
    control_path = f"{control_dir}/pencms_ssh_%h_%p_%r"
    known_hosts = f"{control_dir}/pencms_known_hosts"
    return control_path, known_hosts


def compose_uri(host: str, port: int, username: str, path: str) -> str:
    """Compose an sftp:// URI from decomposed fields."""
    port_str = f":{port}" if port != 22 else ""
    path = path if path.startswith("/") else f"/{path}"
    return f"sftp://{username}@{host}{port_str}{path}"


def decompose_uri(uri: str) -> dict:
    """Decompose an sftp:// URI into user-friendly fields (no password)."""
    if not uri or not uri.startswith("sftp://"):
        return {"host": "", "port": 22, "username": "", "path": ""}
    parsed = urlparse(uri)
    return {
        "host": parsed.hostname or "",
        "port": parsed.port or 22,
        "username": parsed.username or "",
        "path": parsed.path or "/",
    }


def parse_sftp_uri(uri: str) -> dict:
    """Parse an sftp:// URI into exec fields. Raises ValueError on bad input."""
    parsed = urlparse(uri)
    if parsed.scheme != "sftp":
        raise ValueError(f"Expected sftp:// URI, got: {uri}")
    user = parsed.username
    if not user:
        raise ValueError(f"SFTP URI must include a username: {uri}")
    host = parsed.hostname
    if not host:
        raise ValueError(f"SFTP URI must include a hostname: {uri}")
    path = parsed.path or "/"
    return {
        "user": user,
        "password": parsed.password,
        "host": host,
        "port": parsed.port or 22,
        "path": path.rstrip("/") or "/",
    }


def write_askpass(password: str) -> str:
    """Write a short-lived askpass script under /dev/shm; return its path."""
    fd = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".sh",
        prefix=".pen_askpass_",
        delete=False,
        dir="/dev/shm",
    )
    safe_pass = shlex.quote(password)
    fd.write(f'#!/bin/sh\nprintf "%s" {safe_pass}\n')
    fd.close()
    os.chmod(fd.name, 0o700)
    return fd.name


def ssh_opt_args(port: int, *, password: bool) -> List[str]:
    """Shared OpenSSH ``-o`` / ``-P`` flags for ssh and scp (password or key)."""
    control_path, known_hosts = control_paths()
    args = [
        "-o",
        "ConnectTimeout=10",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        f"UserKnownHostsFile={known_hosts}",
        "-o",
        "ControlMaster=auto",
        "-o",
        f"ControlPath={control_path}",
        "-o",
        "ControlPersist=600",
    ]
    if password:
        args += [
            "-o",
            "BatchMode=no",
            "-o",
            "PreferredAuthentications=password",
            "-o",
            "PubkeyAuthentication=no",
        ]
    else:
        args += ["-o", "BatchMode=yes"]
    args += ["-P", str(port)]
    return args


def askpass_env(password: str) -> tuple[Dict[str, str], Optional[str]]:
    env = {**os.environ}
    if "PATH" in env and "/usr/bin" not in env["PATH"]:
        env["PATH"] = env["PATH"] + ":/usr/bin:/bin"
    askpass_path = write_askpass(password)
    env["SSH_ASKPASS"] = askpass_path
    env["SSH_ASKPASS_REQUIRE"] = "force"
    env["DISPLAY"] = "none:0"
    return env, askpass_path


def cleanup_stale_socket(user: str, host: str, port: int) -> None:
    """Remove stale ControlMaster socket if it exists but no master is running."""
    control_path, _known_hosts = control_paths()
    sock_path = (
        control_path.replace("%h", host)
        .replace("%p", str(port))
        .replace("%r", user)
    )
    if not os.path.exists(sock_path):
        return
    try:
        s = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
        s.settimeout(1.0)
        s.connect(sock_path)
        s.close()
    except (ConnectionRefusedError, FileNotFoundError, _socket.timeout, OSError):
        print(f"[SSH] Removing stale or unresponsive control socket: {sock_path}", flush=True)
        try:
            os.remove(sock_path)
        except OSError:
            pass


def _ssh_base_args(user: str, host: str, port: int, *, password: bool) -> list:
    control_path, known_hosts = control_paths()
    args = [
        "/usr/bin/ssh",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        f"UserKnownHostsFile={known_hosts}",
        "-o",
        "ControlMaster=auto",
        "-o",
        f"ControlPath={control_path}",
        "-o",
        "ControlPersist=600",
        "-p",
        str(port),
    ]
    if password:
        args += [
            "-o",
            "BatchMode=no",
            "-o",
            "PreferredAuthentications=password",
            "-o",
            "PubkeyAuthentication=no",
        ]
    else:
        args += ["-o", "BatchMode=yes"]
    args.append(f"{user}@{host}")
    return args


async def ssh_exec(
    *,
    user: str,
    host: str,
    port: int,
    command: str,
    password: Optional[str] = None,
    input_data: Optional[bytes] = None,
) -> tuple[int, bytes, bytes]:
    """Run ``command`` on the remote host via OpenSSH.

    Returns ``(returncode, stdout_bytes, stderr_bytes)``.
    """
    cleanup_stale_socket(user, host, port)
    active_password = (password or "").strip() or None
    args = _ssh_base_args(user, host, port, password=bool(active_password)) + [command]
    env = {**os.environ}
    askpass_path = None

    if active_password:
        if "PATH" in env and "/usr/bin" not in env["PATH"]:
            env["PATH"] = env["PATH"] + ":/usr/bin:/bin"
        askpass_path = write_askpass(active_password)
        env["SSH_ASKPASS"] = askpass_path
        env["SSH_ASKPASS_REQUIRE"] = "force"
        env["DISPLAY"] = "none:0"
        print(
            f"[DEBUG SSH] Creating askpass: {askpass_path} with password len {len(active_password)}",
            flush=True,
        )
        with open(askpass_path, "r") as debug_f:
            print(f"[DEBUG SSH] askpass content: {debug_f.read().strip()}", flush=True)

    print(f"[DEBUG SSH] Executing: {' '.join(args)}", flush=True)
    print(
        f"[DEBUG SSH] SSH_ASKPASS={env.get('SSH_ASKPASS')} "
        f"SSH_ASKPASS_REQUIRE={env.get('SSH_ASKPASS_REQUIRE')} DISPLAY={env.get('DISPLAY')}",
        flush=True,
    )

    stdout = b""
    stderr = b""
    returncode = 255
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE if input_data is not None else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            start_new_session=bool(active_password),
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=input_data), timeout=25.0
            )
            returncode = proc.returncode if proc.returncode is not None else 255
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except OSError:
                pass
            return 255, b"", b"SSH Error: Command timed out after 25s"
    except FileNotFoundError:
        raise RuntimeError("SSH binary not found. Ensure OpenSSH client is installed.")
    finally:
        if askpass_path and os.path.exists(askpass_path):
            try:
                os.unlink(askpass_path)
            except OSError:
                pass

    print(
        f"[SSH exec] rc={returncode} stdout={stdout[:300]!r} stderr={stderr[:300]!r}",
        flush=True,
    )
    return returncode, stdout, stderr
