"""Vault-header registry — map HTTP aliases to per-request vault keys.

``get_current_user`` / ``get_optional_user`` iterate this registry against
``request.headers``. Core seeds SFTP + GitHub Pages publish secrets. Pro
``init_pro`` registers cloud publish tokens and content/assets SSH passes.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Tuple

KeyFn = Callable[[str], str]

# Ordered (alias, key_fn) pairs. Last writer wins by case-insensitive alias.
_REGISTRY: List[Tuple[str, KeyFn]] = []


def register_vault_header(http_alias: str, key_fn: KeyFn) -> None:
    """Register or replace a header alias → vault-key mapping."""
    alias = (http_alias or "").strip()
    if not alias:
        raise ValueError("vault header alias must be non-empty")
    if key_fn is None:
        raise ValueError("vault header key_fn is required")
    for i, (existing, _) in enumerate(_REGISTRY):
        if existing.lower() == alias.lower():
            _REGISTRY[i] = (alias, key_fn)
            return
    _REGISTRY.append((alias, key_fn))


def list_vault_headers() -> List[Tuple[str, KeyFn]]:
    return list(_REGISTRY)


def secrets_from_request(headers, site_id: str) -> Dict[str, str]:
    """Build the vault_secrets dict from inbound headers vs the registry."""
    secrets: Dict[str, str] = {}
    sid = (site_id or "").strip() or "default"
    for alias, key_fn in _REGISTRY:
        value = headers.get(alias)
        if value:
            secrets[key_fn(sid)] = value
    return secrets


def _seed_core_vault_headers() -> None:
    register_vault_header(
        "X-Vault-Publish-Pass", lambda site: f"PUBLISH_SFTP_PASS:{site}"
    )
    register_vault_header(
        "X-Vault-Publish-Github-Token",
        lambda site: f"PUBLISH_GITHUB_TOKEN:{site}",
    )


_seed_core_vault_headers()
