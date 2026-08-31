"""Storage type registry — Core seed is local + git.

SSH as a content/assets storage type registers from ``pencms_pro.init_pro``.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

StorageFactory = Callable[..., Any]

# Insertion order is catalog order for Settings (local, git, then Pro ssh).
_FACTORIES: Dict[str, StorageFactory] = {}

SSH_STORAGE_PRO_POINTER = (
    "SSH content/assets storage (storage_type=ssh) requires PenCMS Pro. "
    "Load the overlay (PYTHONPATH to pencms-pro) or switch this path to local/git. "
    "The remote URI was not rewritten."
)


def register_storage_type(type_id: str, factory: StorageFactory) -> None:
    """Register or replace a storage-type factory by id. Last writer wins."""
    tid = (type_id or "").strip().lower()
    if not tid:
        raise ValueError("storage type id must be non-empty")
    if factory is None:
        raise ValueError("storage type factory is required")
    _FACTORIES[tid] = factory


def get_storage_type(type_id: str) -> Optional[StorageFactory]:
    return _FACTORIES.get((type_id or "").strip().lower())


def list_storage_types() -> List[str]:
    return list(_FACTORIES.keys())


def _seed_core_storage_types() -> None:
    from services.storage_provider import GitStorageProvider, LocalStorageProvider

    register_storage_type("local", lambda path, **_k: LocalStorageProvider(str(path)))
    register_storage_type("git", lambda path, **_k: GitStorageProvider(str(path)))


_seed_core_storage_types()
