"""Publish path→hash manifests for incremental SFTP upload (S9).

After each successful publish, store relative dist paths and SHA-256 digests
under ``data/publish-manifests/{site_id}.json``. The next run diffs the rebuilt
dist against this file to upload only adds/changes and delete remote orphans.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.site_service import validate_site_id

MANIFEST_VERSION = 1


def _manifests_dir() -> Path:
    from config import BASE_DIR

    return Path(BASE_DIR) / "data" / "publish-manifests"


def manifest_path(site_id: str) -> Path:
    sid = validate_site_id(site_id)
    return _manifests_dir() / f"{sid}.json"


def _ensure_dir() -> Path:
    d = _manifests_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _normalize_rel_path(rel: str) -> str:
    """Return a safe POSIX relative path; raise ValueError if unsafe."""
    cleaned = (rel or "").replace("\\", "/").strip("/")
    if not cleaned:
        raise ValueError("empty relative path")
    if cleaned.startswith("/") or cleaned.startswith("~"):
        raise ValueError(f"absolute path not allowed: {rel!r}")
    parts = cleaned.split("/")
    if any(p in ("", ".", "..") for p in parts):
        raise ValueError(f"unsafe relative path: {rel!r}")
    return "/".join(parts)


def hash_file(path: Path) -> str:
    """SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def hash_dist_tree(dist_dir: Path) -> Dict[str, str]:
    """Walk ``dist_dir`` and return ``{rel_posix_path: sha256}`` for all files."""
    root = Path(dist_dir).resolve()
    if not root.is_dir():
        raise ValueError(f"dist_dir is not a directory: {dist_dir}")

    files: Dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError as e:
            raise ValueError(f"path escapes dist_dir: {path}") from e
        safe = _normalize_rel_path(rel)
        files[safe] = hash_file(path)
    return files


def load_manifest(site_id: str) -> Optional[Dict[str, str]]:
    """Load path→hash map, or None if missing / unreadable."""
    path = manifest_path(site_id)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    files = raw.get("files")
    if not isinstance(files, dict):
        return None
    out: Dict[str, str] = {}
    for k, v in files.items():
        if not isinstance(k, str) or not isinstance(v, str):
            continue
        try:
            out[_normalize_rel_path(k)] = v
        except ValueError:
            continue
    return out


def save_manifest(site_id: str, files: Dict[str, str]) -> Path:
    """Write path→hash manifest; returns the file path."""
    sid = validate_site_id(site_id)
    normalized: Dict[str, str] = {}
    for k, v in files.items():
        if not isinstance(v, str) or not v:
            raise ValueError(f"invalid hash for {k!r}")
        normalized[_normalize_rel_path(k)] = v

    _ensure_dir()
    path = manifest_path(sid)
    payload: Dict[str, Any] = {
        "version": MANIFEST_VERSION,
        "updated_at": _utcnow_iso(),
        "files": dict(sorted(normalized.items())),
    }
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def diff_manifests(
    old: Optional[Dict[str, str]],
    new: Dict[str, str],
) -> Dict[str, List[str]]:
    """Compare prior and new path→hash maps.

    Returns keys: added, changed, removed, unchanged (lists of relative paths).
    """
    old = old or {}
    added: List[str] = []
    changed: List[str] = []
    unchanged: List[str] = []
    for path, digest in sorted(new.items()):
        if path not in old:
            added.append(path)
        elif old[path] != digest:
            changed.append(path)
        else:
            unchanged.append(path)
    removed = sorted(p for p in old if p not in new)
    return {
        "added": added,
        "changed": changed,
        "removed": removed,
        "unchanged": unchanged,
    }


def clear_manifest(site_id: str) -> bool:
    """Delete manifest file if present. Returns True if removed."""
    path = manifest_path(site_id)
    if path.is_file():
        path.unlink()
        return True
    return False
