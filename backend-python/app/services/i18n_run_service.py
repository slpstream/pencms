"""Bounded, body-free telemetry for externally orchestrated i18n runs."""

from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path
from typing import Any, Iterable, Optional

from models.page import utc_now_iso
from services.site_service import validate_site_id


MAX_RUN_RECORDS = 500
MAX_ERROR_LENGTH = 160
MAX_TARGET_LANGUAGES = 32
ALLOWED_MODES = {
    "translate",
    "transliterate",
    "translate_then_transliterate",
    "manual",
}
ALLOWED_STATUSES = {"running", "completed", "failed", "cancelled"}
COUNT_KEYS = {"discovered", "attempted", "created", "updated", "skipped", "failed"}
_RUN_ID_RE = re.compile(r"^run_[0-9a-f]{32}$")


def _runs_dir() -> Path:
    from config import BASE_DIR

    return Path(BASE_DIR) / "data" / "i18n-runs"


def _run_path(site_id: str) -> Path:
    return _runs_dir() / f"{validate_site_id(site_id)}.jsonl"


def _sanitize_counts(raw: Optional[dict[str, Any]]) -> dict[str, int]:
    counts = {key: 0 for key in sorted(COUNT_KEYS)}
    for key, value in (raw or {}).items():
        if key not in COUNT_KEYS:
            raise ValueError(f"Unknown translation run count: {key}")
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"Translation run count '{key}' must be a non-negative integer")
        counts[key] = value
    return counts


def _sanitize_error(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    raw = str(value)
    text = " ".join(raw.split())
    if not text:
        return None
    if (
        "\n" in raw
        or "\r" in raw
        or len(text) > MAX_ERROR_LENGTH
        or len(text.split()) > 12
    ):
        return "[redacted external error; see caller logs]"
    return text


def _sanitize_target_languages(values: Optional[list[str]]) -> list[str]:
    unique: list[str] = []
    for value in values or []:
        if not isinstance(value, str) or not value or len(value) > 35:
            raise ValueError("Translation run target languages must be short language tags")
        if value not in unique:
            unique.append(value)
    if len(unique) > MAX_TARGET_LANGUAGES:
        raise ValueError(
            f"Translation runs support at most {MAX_TARGET_LANGUAGES} target languages"
        )
    return unique


def _read_records(site_id: str) -> list[dict[str, Any]]:
    path = _run_path(site_id)
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except (TypeError, ValueError):
            continue
        if isinstance(row, dict):
            records.append(row)
    return records[-MAX_RUN_RECORDS:]


def _write_records(site_id: str, records: Iterable[dict[str, Any]]) -> None:
    path = _run_path(site_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    bounded = list(records)[-MAX_RUN_RECORDS:]
    payload = "".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
        for row in bounded
    )
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temp.write_text(payload, encoding="utf-8")
    os.replace(temp, path)


def start_run(
    *,
    site_id: str,
    actor: str,
    actor_id: str,
    mode: str,
    target_languages: Optional[list[str]] = None,
    policy_snapshot: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    if mode not in ALLOWED_MODES:
        raise ValueError(f"Unsupported translation run mode: {mode}")
    now = utc_now_iso()
    snapshot = policy_snapshot or {}
    record = {
        "run_id": f"run_{uuid.uuid4().hex}",
        "site_id": validate_site_id(site_id),
        "actor": actor,
        "actor_id": actor_id,
        "mode": mode,
        "target_languages": _sanitize_target_languages(target_languages),
        "policy_applied": bool(snapshot.get("policy_applied", False)),
        "model": snapshot.get("model"),
        "agent_key_id": snapshot.get("agent_key_id"),
        "agent_key_name": snapshot.get("agent_key_name"),
        "review_policy": snapshot.get("review_policy", "require_review"),
        "started_at": now,
        "updated_at": now,
        "finished_at": None,
        "status": "running",
        "counts": _sanitize_counts(None),
        "error": None,
    }
    records = _read_records(site_id)
    records.append(record)
    _write_records(site_id, records)
    return dict(record)


def get_run(site_id: str, run_id: str) -> Optional[dict[str, Any]]:
    if not _RUN_ID_RE.match(run_id or ""):
        return None
    return next(
        (row for row in reversed(_read_records(site_id)) if row.get("run_id") == run_id),
        None,
    )


def update_run(
    *,
    site_id: str,
    run_id: str,
    actor: str,
    actor_id: str,
    status: Optional[str] = None,
    counts: Optional[dict[str, Any]] = None,
    error: Optional[str] = None,
) -> dict[str, Any]:
    if status is not None and status not in ALLOWED_STATUSES:
        raise ValueError(f"Unsupported translation run status: {status}")
    records = _read_records(site_id)
    index = next(
        (i for i in range(len(records) - 1, -1, -1) if records[i].get("run_id") == run_id),
        None,
    )
    if index is None:
        raise KeyError(run_id)
    current = dict(records[index])
    if current.get("actor") != actor or current.get("actor_id") != actor_id:
        raise PermissionError("Translation run belongs to a different actor")
    if current.get("status") != "running":
        raise ValueError("Finished translation runs are immutable")
    if counts is not None:
        current["counts"] = _sanitize_counts(counts)
    if status is not None:
        current["status"] = status
    if error is not None:
        current["error"] = _sanitize_error(error)
    now = utc_now_iso()
    current["updated_at"] = now
    if current["status"] != "running":
        current["finished_at"] = now
    records[index] = current
    _write_records(site_id, records)
    return dict(current)


def list_runs(site_id: str, *, limit: int = 25) -> list[dict[str, Any]]:
    bounded = max(1, min(int(limit), 100))
    return list(reversed(_read_records(site_id)))[0:bounded]
