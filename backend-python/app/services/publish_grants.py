"""Deploy Grant store — server-side ciphertext for agentic host publish.

Interactive admins keep secrets in the ZK vault. Agents cannot unlock the
vault, so an operator must explicitly enroll a Deploy Grant: the install holds
Fernet ciphertext under ``data/publish-grants/{site_id}.enc`` (password/token
path) or a flag-only enrollment (SFTP key path uses the install Ed25519 key).

Agents never receive host passwords or platform tokens; they only call publish
APIs with scope ``publish``. Revoking the grant is independent of revoking an
agent key.
"""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet, InvalidToken

from services.auth_service import JWT_SECRET
from services.site_service import (
    get_publish_target,
    get_site,
    set_publish_target,
    validate_site_id,
)


def _grants_dir() -> Path:
    from config import BASE_DIR

    return Path(BASE_DIR) / "data" / "publish-grants"


def _enc_path(site_id: str) -> Path:
    return _grants_dir() / f"{site_id}.enc"


def _fernet() -> Fernet:
    """Derive a Fernet key from JWT_SECRET (install-bound, not ZK)."""
    digest = hashlib.sha256(f"publish-grant:{JWT_SECRET}".encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _ensure_dir() -> Path:
    d = _grants_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def has_ciphertext(site_id: str) -> bool:
    sid = validate_site_id(site_id)
    return _enc_path(sid).is_file()


def is_enrolled(site_id: str) -> bool:
    """True when sites.yaml says enrolled (grant metadata)."""
    target = get_publish_target(site_id)
    return target.get("configured") and target.get("agent_publish") == "enrolled"


def grant_status(site_id: str) -> Dict[str, Any]:
    """Non-secret grant status for GET /api/publish/grant."""
    sid = validate_site_id(site_id)
    target = get_publish_target(sid)
    enrolled = bool(target.get("configured") and target.get("agent_publish") == "enrolled")
    auth_method = target.get("auth_method") if target.get("configured") else None
    return {
        "site_id": sid,
        "enrolled": enrolled,
        "auth_method": auth_method,
        "has_ciphertext": has_ciphertext(sid),
        "configured": bool(target.get("configured")),
    }


def _write_ciphertext(site_id: str, payload: Dict[str, Any]) -> None:
    _ensure_dir()
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    token = _fernet().encrypt(raw)
    path = _enc_path(site_id)
    path.write_bytes(token)
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _read_ciphertext(site_id: str) -> Optional[Dict[str, Any]]:
    path = _enc_path(site_id)
    if not path.is_file():
        return None
    try:
        raw = _fernet().decrypt(path.read_bytes())
    except InvalidToken as e:
        raise ValueError("Deploy Grant ciphertext is invalid or key mismatch") from e
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Deploy Grant payload is corrupt")
    return data


def load_password(site_id: str) -> Optional[str]:
    """Decrypt the enrolled secret (SFTP password or platform API key), or None for key-only grants."""
    sid = validate_site_id(site_id)
    data = _read_ciphertext(sid)
    if data is None:
        return None
    password = data.get("password")
    if password is None:
        return None
    return str(password)


def _target_write_payload(target: Dict[str, Any], *, agent_publish: str) -> Dict[str, Any]:
    """Build a set_publish_target payload that preserves provider-specific fields."""
    from services.publish_providers.registry import (
        ProviderNotEnabledError,
        UnknownPublishProviderError,
        get_provider,
    )

    provider = (target.get("provider") or "sftp").strip().lower() or "sftp"
    payload: Dict[str, Any] = {
        "provider": provider,
        "public_url": target.get("public_url"),
        "last_published_at": target.get("last_published_at"),
        "last_status": target.get("last_status"),
        "agent_publish": agent_publish,
        "webhook_url": target.get("webhook_url"),
    }
    try:
        adapter = get_provider(provider)
    except (UnknownPublishProviderError, ProviderNotEnabledError):
        adapter = None
    if adapter is None:
        payload["host"] = target.get("host")
        payload["port"] = target.get("port") or 22
        payload["username"] = target.get("username")
        payload["remote_path"] = target.get("remote_path")
        payload["auth_method"] = target.get("auth_method") or "password"
        return payload
    caps = adapter.capabilities() or {}
    methods = caps.get("auth_methods") or []
    if "token" in methods and "password" not in methods:
        payload["auth_method"] = "token"
    else:
        payload["host"] = target["host"]
        payload["port"] = target.get("port") or 22
        payload["username"] = target["username"]
        payload["remote_path"] = target["remote_path"]
        payload["auth_method"] = target.get("auth_method") or "password"
    for field in adapter.yaml_fields():
        if field in ("host", "port", "username", "remote_path"):
            continue
        payload[field] = target.get(field)
    return payload


def enroll(
    site_id: str,
    *,
    auth_method: str,
    password: Optional[str] = None,
) -> Dict[str, Any]:
    """Enroll a Deploy Grant for the site.

    Password/token auth requires a non-empty secret (copied from vault or re-entered).
    Key auth is flag-only: no ciphertext file.
    """
    sid = validate_site_id(site_id)
    if get_site(sid) is None:
        raise ValueError(f"Unknown site_id: {sid}")

    target = get_publish_target(sid)
    if not target.get("configured"):
        raise ValueError(
            "Publish target is not configured; save Settings first"
        )

    # Prefer the saved target auth_method so grant matches deploy path.
    saved_method = (target.get("auth_method") or "password").strip().lower()
    method = saved_method
    if method not in ("password", "key", "token"):
        raise ValueError("auth_method must be 'password', 'key', or 'token'")

    enrolled_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if method in ("password", "token"):
        pw = (password or "").strip()
        if not pw:
            kind = "API key" if method == "token" else "password"
            raise ValueError(
                f"{kind} is required to enroll a Deploy Grant "
                "(unlock vault or re-enter the secret)"
            )
        _write_ciphertext(
            sid,
            {
                "v": 1,
                "site_id": sid,
                "auth_method": method,
                "password": pw,
                "enrolled_at": enrolled_at,
            },
        )
    else:
        # Key path: remove any leftover password ciphertext from a prior enroll.
        path = _enc_path(sid)
        if path.is_file():
            path.unlink()

    set_publish_target(sid, _target_write_payload(target, agent_publish="enrolled"))
    return grant_status(sid)


def revoke(site_id: str) -> Dict[str, Any]:
    """Clear Deploy Grant ciphertext and set agent_publish=off."""
    sid = validate_site_id(site_id)
    if get_site(sid) is None:
        raise ValueError(f"Unknown site_id: {sid}")

    path = _enc_path(sid)
    if path.is_file():
        path.unlink()

    target = get_publish_target(sid)
    if target.get("configured"):
        set_publish_target(sid, _target_write_payload(target, agent_publish="off"))
    return grant_status(sid)
