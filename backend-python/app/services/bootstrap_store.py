"""Agent-assisted key bootstrap: pending approve-codes (Option B).

File-backed in the same SQLite DB as OAuth (``data/oauth.db``). Human admin
approves a short user_code; the agent then verifies and receives ``pen-sk-…``.

Plaintext ``user_code`` is stored for the admin pending list (10-minute TTL);
it is not the agent secret.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


BOOTSTRAP_TTL_SECONDS = 600  # 10 minutes
REQUEST_CODE_MIN_INTERVAL_SECONDS = 2.0

_last_request_at: float = 0.0


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


def init_bootstrap_store() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bootstrap_codes (
                code_hash TEXT PRIMARY KEY,
                user_code TEXT NOT NULL,
                name TEXT NOT NULL,
                scopes TEXT NOT NULL,
                status TEXT NOT NULL,
                expires_at REAL NOT NULL,
                created_at REAL NOT NULL,
                sponsor_uuid TEXT
            )
            """
        )
        cols = {
            r[1]
            for r in conn.execute("PRAGMA table_info(bootstrap_codes)").fetchall()
        }
        if "user_code" not in cols:
            conn.execute(
                "ALTER TABLE bootstrap_codes ADD COLUMN user_code TEXT NOT NULL DEFAULT ''"
            )
        if "sponsor_uuid" not in cols:
            conn.execute(
                "ALTER TABLE bootstrap_codes ADD COLUMN sponsor_uuid TEXT"
            )
        if "site_id" not in cols:
            conn.execute(
                "ALTER TABLE bootstrap_codes ADD COLUMN site_id TEXT NOT NULL DEFAULT 'default'"
            )
        conn.commit()


def _generate_user_code() -> str:
    """Human-friendly 8-char code (no ambiguous 0/O/1/I)."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(8))


@dataclass
class BootstrapRecord:
    user_code: str
    name: str
    scopes: List[str]
    status: str
    expires_at: float
    created_at: float
    sponsor_uuid: Optional[str] = None
    site_id: str = "default"


def create_bootstrap_request(
    *,
    name: str,
    scopes: List[str],
    site_id: str = "default",
    ttl_seconds: Optional[int] = None,
) -> BootstrapRecord:
    """Create a pending bootstrap request. Raises ValueError if rate-limited."""
    global _last_request_at
    init_bootstrap_store()
    if ttl_seconds is None:
        ttl_seconds = BOOTSTRAP_TTL_SECONDS
    now = time.time()
    if now - _last_request_at < REQUEST_CODE_MIN_INTERVAL_SECONDS:
        raise ValueError("rate_limited")
    _last_request_at = now

    for _ in range(5):
        user_code = _generate_user_code()
        code_hash = _hash(user_code)
        with _connect() as conn:
            existing = conn.execute(
                "SELECT 1 FROM bootstrap_codes WHERE code_hash = ?",
                (code_hash,),
            ).fetchone()
            if existing is not None:
                continue
            expires_at = now + ttl_seconds
            conn.execute(
                """
                INSERT INTO bootstrap_codes (
                    code_hash, user_code, name, scopes, status, expires_at, created_at, site_id
                ) VALUES (?, ?, ?, ?, 'pending', ?, ?, ?)
                """,
                (code_hash, user_code, name, json.dumps(scopes), expires_at, now, site_id),
            )
            conn.commit()
            return BootstrapRecord(
                user_code=user_code,
                name=name,
                scopes=scopes,
                status="pending",
                expires_at=expires_at,
                created_at=now,
                site_id=site_id,
            )
    raise RuntimeError("Failed to allocate unique bootstrap code")


def _expire_stale(conn: sqlite3.Connection, now: float) -> None:
    conn.execute(
        """
        UPDATE bootstrap_codes SET status = 'expired'
        WHERE status IN ('pending', 'approved') AND expires_at < ?
        """,
        (now,),
    )


def list_pending_bootstrap() -> List[dict]:
    """List non-expired pending or approved-not-consumed requests."""
    init_bootstrap_store()
    now = time.time()
    with _connect() as conn:
        _expire_stale(conn, now)
        rows = conn.execute(
            """
            SELECT user_code, name, scopes, status, expires_at, created_at, site_id
            FROM bootstrap_codes
            WHERE status IN ('pending', 'approved') AND expires_at >= ?
            ORDER BY created_at ASC
            """,
            (now,),
        ).fetchall()
        conn.commit()
        return [
            {
                "user_code": r["user_code"],
                "name": r["name"],
                "scopes": json.loads(r["scopes"]),
                "status": r["status"],
                "expires_at": r["expires_at"],
                "created_at": r["created_at"],
                "site_id": r["site_id"] if "site_id" in r.keys() and r["site_id"] else "default",
            }
            for r in rows
        ]


def set_bootstrap_status(
    user_code: str, status: str, *, sponsor_uuid: Optional[str] = None
) -> Optional[dict]:
    """Set status to approved or denied. Returns public metadata or None."""
    init_bootstrap_store()
    normalized = user_code.strip().upper()
    code_hash = _hash(normalized)
    now = time.time()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM bootstrap_codes WHERE code_hash = ?",
            (code_hash,),
        ).fetchone()
        if row is None:
            return None
        if row["expires_at"] < now:
            conn.execute(
                "UPDATE bootstrap_codes SET status = 'expired' WHERE code_hash = ?",
                (code_hash,),
            )
            conn.commit()
            return None
        if status == "approved":
            if row["status"] not in ("pending", "approved"):
                return None
            if not sponsor_uuid:
                return None
            conn.execute(
                """
                UPDATE bootstrap_codes
                SET status = ?, sponsor_uuid = ?
                WHERE code_hash = ?
                """,
                (status, sponsor_uuid, code_hash),
            )
        elif status == "denied":
            if row["status"] not in ("pending", "approved"):
                return None
            conn.execute(
                "UPDATE bootstrap_codes SET status = ? WHERE code_hash = ?",
                (status, code_hash),
            )
        else:
            return None
        conn.commit()
        return {
            "user_code": row["user_code"],
            "name": row["name"],
            "scopes": json.loads(row["scopes"]),
            "status": status,
            "expires_at": row["expires_at"],
            "created_at": row["created_at"],
            "site_id": row["site_id"] if "site_id" in row.keys() and row["site_id"] else "default",
        }


def peek_bootstrap(user_code: str) -> Optional[BootstrapRecord]:
    """Read status without consuming."""
    init_bootstrap_store()
    code_hash = _hash(user_code.strip().upper())
    now = time.time()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM bootstrap_codes WHERE code_hash = ?",
            (code_hash,),
        ).fetchone()
        if row is None:
            return None
        status = row["status"]
        if row["expires_at"] < now and status in ("pending", "approved"):
            conn.execute(
                "UPDATE bootstrap_codes SET status = 'expired' WHERE code_hash = ?",
                (code_hash,),
            )
            conn.commit()
            status = "expired"
        return BootstrapRecord(
            user_code=row["user_code"],
            name=row["name"],
            scopes=json.loads(row["scopes"]),
            status=status,
            expires_at=row["expires_at"],
            created_at=row["created_at"],
            sponsor_uuid=row["sponsor_uuid"] if "sponsor_uuid" in row.keys() else None,
            site_id=(
                row["site_id"]
                if "site_id" in row.keys() and row["site_id"]
                else "default"
            ),
        )


def mark_bootstrap_consumed(user_code: str) -> bool:
    """Mark an approved bootstrap code as consumed. Returns False if not approved."""
    init_bootstrap_store()
    code_hash = _hash(user_code.strip().upper())
    with _connect() as conn:
        row = conn.execute(
            "SELECT status FROM bootstrap_codes WHERE code_hash = ?",
            (code_hash,),
        ).fetchone()
        if row is None or row["status"] != "approved":
            return False
        conn.execute(
            "UPDATE bootstrap_codes SET status = 'consumed' WHERE code_hash = ?",
            (code_hash,),
        )
        conn.commit()
        return True


def clear_bootstrap_store() -> None:
    """Test helper."""
    global _last_request_at
    init_bootstrap_store()
    _last_request_at = 0.0
    with _connect() as conn:
        conn.execute("DELETE FROM bootstrap_codes")
        conn.commit()
