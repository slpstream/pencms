"""Short-lived OAuth auth-code and rotating refresh-token store (Phase 1b).

File-backed SQLite under ``{BASE_DIR}/data/oauth.db``. Access-token JTIs are
never stored or enforced here — optional ``jti`` on JWTs is for a future
denylist only.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


AUTH_CODE_TTL_SECONDS = 300  # 5 minutes
REFRESH_TOKEN_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days


def _db_path() -> Path:
    from config import BASE_DIR

    return Path(BASE_DIR) / "data" / "oauth.db"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_oauth_store() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_codes (
                code_hash TEXT PRIMARY KEY,
                client_id TEXT NOT NULL,
                redirect_uri TEXT NOT NULL,
                code_challenge TEXT NOT NULL,
                code_challenge_method TEXT NOT NULL,
                resource TEXT NOT NULL,
                scopes TEXT NOT NULL,
                user_uuid TEXT NOT NULL,
                key_index INTEGER NOT NULL,
                key_id TEXT,
                expires_at REAL NOT NULL,
                used INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                token_hash TEXT PRIMARY KEY,
                client_id TEXT NOT NULL,
                resource TEXT NOT NULL,
                scopes TEXT NOT NULL,
                user_uuid TEXT NOT NULL,
                key_index INTEGER NOT NULL,
                key_id TEXT,
                expires_at REAL NOT NULL,
                revoked INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        for table in ("auth_codes", "refresh_tokens"):
            columns = {
                row["name"] for row in conn.execute(f"PRAGMA table_info({table})")
            }
            if "key_id" not in columns:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN key_id TEXT")
        conn.commit()


@dataclass
class AuthCodeRecord:
    client_id: str
    redirect_uri: str
    code_challenge: str
    code_challenge_method: str
    resource: str
    scopes: List[str]
    user_uuid: str
    key_index: int
    key_id: Optional[str]


@dataclass
class RefreshTokenRecord:
    client_id: str
    resource: str
    scopes: List[str]
    user_uuid: str
    key_index: int
    key_id: Optional[str]


def store_auth_code(
    code: str,
    *,
    client_id: str,
    redirect_uri: str,
    code_challenge: str,
    code_challenge_method: str,
    resource: str,
    scopes: List[str],
    user_uuid: str,
    key_index: int,
    key_id: str,
    ttl_seconds: int = AUTH_CODE_TTL_SECONDS,
) -> None:
    init_oauth_store()
    expires_at = time.time() + ttl_seconds
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO auth_codes (
                code_hash, client_id, redirect_uri, code_challenge,
                code_challenge_method, resource, scopes, user_uuid,
                key_index, key_id, expires_at, used
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                _hash(code),
                client_id,
                redirect_uri,
                code_challenge,
                code_challenge_method,
                resource,
                json.dumps(scopes),
                user_uuid,
                key_index,
                key_id,
                expires_at,
            ),
        )
        conn.commit()


def consume_auth_code(code: str) -> Optional[AuthCodeRecord]:
    """Return the auth-code record and mark it used (single-use)."""
    init_oauth_store()
    code_hash = _hash(code)
    now = time.time()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM auth_codes WHERE code_hash = ?",
            (code_hash,),
        ).fetchone()
        if row is None:
            return None
        if row["used"]:
            return None
        if row["expires_at"] < now:
            conn.execute("DELETE FROM auth_codes WHERE code_hash = ?", (code_hash,))
            conn.commit()
            return None
        conn.execute(
            "UPDATE auth_codes SET used = 1 WHERE code_hash = ?",
            (code_hash,),
        )
        conn.commit()
        return AuthCodeRecord(
            client_id=row["client_id"],
            redirect_uri=row["redirect_uri"],
            code_challenge=row["code_challenge"],
            code_challenge_method=row["code_challenge_method"],
            resource=row["resource"],
            scopes=json.loads(row["scopes"]),
            user_uuid=row["user_uuid"],
            key_index=int(row["key_index"]),
            key_id=row["key_id"],
        )


def store_refresh_token(
    token: str,
    *,
    client_id: str,
    resource: str,
    scopes: List[str],
    user_uuid: str,
    key_index: int,
    key_id: str,
    ttl_seconds: int = REFRESH_TOKEN_TTL_SECONDS,
) -> None:
    init_oauth_store()
    expires_at = time.time() + ttl_seconds
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO refresh_tokens (
                token_hash, client_id, resource, scopes, user_uuid,
                key_index, key_id, expires_at, revoked
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                _hash(token),
                client_id,
                resource,
                json.dumps(scopes),
                user_uuid,
                key_index,
                key_id,
                expires_at,
            ),
        )
        conn.commit()


def consume_refresh_token(token: str) -> Optional[RefreshTokenRecord]:
    """Validate and revoke a refresh token (rotation: caller issues a new one)."""
    init_oauth_store()
    token_hash = _hash(token)
    now = time.time()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM refresh_tokens WHERE token_hash = ?",
            (token_hash,),
        ).fetchone()
        if row is None:
            return None
        if row["revoked"]:
            return None
        if row["expires_at"] < now:
            conn.execute(
                "DELETE FROM refresh_tokens WHERE token_hash = ?",
                (token_hash,),
            )
            conn.commit()
            return None
        conn.execute(
            "UPDATE refresh_tokens SET revoked = 1 WHERE token_hash = ?",
            (token_hash,),
        )
        conn.commit()
        return RefreshTokenRecord(
            client_id=row["client_id"],
            resource=row["resource"],
            scopes=json.loads(row["scopes"]),
            user_uuid=row["user_uuid"],
            key_index=int(row["key_index"]),
            key_id=row["key_id"],
        )


def clear_oauth_store() -> None:
    """Test helper: wipe all OAuth state."""
    init_oauth_store()
    with _connect() as conn:
        conn.execute("DELETE FROM auth_codes")
        conn.execute("DELETE FROM refresh_tokens")
        conn.commit()
