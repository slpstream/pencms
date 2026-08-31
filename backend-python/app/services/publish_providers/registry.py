"""Publish provider registry — Core seed is SFTP + GitHub Pages.

Cloud adapters (Cloudflare Pages, Vercel, Netlify, here.now) register from
``pencms_pro.init_pro``. Catalog is a registerable list; last writer wins by id.
"""

from __future__ import annotations

from typing import Any, Dict, List, Type

from services.publish_providers.base import PublishProvider
from services.publish_providers.github_pages import GithubPagesPublishProvider
from services.publish_providers.sftp import SftpPublishProvider


class UnknownPublishProviderError(ValueError):
    """Raised when a provider id is not registered (or not implemented for deploy)."""


class ProviderNotEnabledError(ValueError):
    """Raised when a catalog stub is selected for test/deploy."""


# Catalog order for Settings UI. Only ``enabled=True`` adapters can deploy/test.
_CATALOG: List[Type[PublishProvider]] = []


# Future providers — listed for the picker, not selectable until implemented.
_STUBS: List[Dict[str, Any]] = []


def register_publish_provider(cls: Type[PublishProvider]) -> None:
    """Append or replace a publish adapter by ``cls.id``. Last writer wins."""
    pid = getattr(cls, "id", None)
    if not pid or not str(pid).strip():
        raise ValueError("PublishProvider subclass must define a non-empty id")
    pid = str(pid).strip().lower()
    for i, existing in enumerate(_CATALOG):
        if existing.id == pid:
            _CATALOG[i] = cls
            return
    _CATALOG.append(cls)


def registered_provider_classes() -> List[Type[PublishProvider]]:
    return list(_CATALOG)


def _impl_map() -> Dict[str, Type[PublishProvider]]:
    return {cls.id: cls for cls in _CATALOG}


def list_providers() -> List[Dict[str, Any]]:
    """Return catalog entries for Settings (implemented + disabled stubs)."""
    out: List[Dict[str, Any]] = []
    for cls in _CATALOG:
        inst = cls()
        vault = inst.vault_key("{site}")
        out.append(
            {
                "id": inst.id,
                "label": inst.label,
                "enabled": bool(inst.enabled),
                "capabilities": inst.capabilities(),
                "yaml_fields": inst.yaml_fields(),
                "vault_key": vault,
                "http_alias": inst.vault_http_alias,
                "ui_schema": inst.ui_schema(),
            }
        )
    out.extend(_STUBS)
    return out


def get_provider(provider_id: str | None) -> PublishProvider:
    """Instantiate an enabled adapter. Unknown / stub ids raise."""
    pid = (provider_id or "sftp").strip().lower() or "sftp"
    impl = _impl_map().get(pid)
    if impl is not None:
        return impl()
    stub_ids = {s["id"] for s in _STUBS}
    if pid in stub_ids:
        raise ProviderNotEnabledError(
            f"Publish provider '{pid}' is not available yet"
        )
    raise UnknownPublishProviderError(
        f"Unknown publish provider: {pid}"
    )


def _seed_default_catalog() -> None:
    """Core catalog: SFTP + GitHub Pages. Cloud four register from init_pro."""
    for cls in (
        SftpPublishProvider,
        GithubPagesPublishProvider,
    ):
        register_publish_provider(cls)


_seed_default_catalog()
