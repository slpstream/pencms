"""Publish provider adapter interface (S10)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class PublishDeployError(Exception):
    """Deploy step failed (build or upload)."""


class PublishProvider(ABC):
    """One adapter per publish host type (SFTP, GitHub Pages, …)."""

    id: str
    label: str
    # When False, Settings shows the option but it is not selectable (S11+ stubs).
    enabled: bool = True
    # HTTP alias that AUTH.getHeaders / the vault-header registry use.
    vault_http_alias: Optional[str] = None

    def __init__(self) -> None:
        self._target: Dict[str, Any] = {}
        self._password: Optional[str] = None
        self._site_id: str = ""

    def configure(
        self,
        target: Dict[str, Any],
        *,
        password: Optional[str] = None,
        site_id: str,
    ) -> None:
        """Bind non-secret target + resolved secrets for this request/run."""
        self._target = dict(target or {})
        self._password = password
        self._site_id = site_id

    @staticmethod
    def _opt_str(value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def vault_key(self, site_id: str) -> Optional[str]:
        """Vault dict key for this adapter's secret, or None if unused."""
        return None

    def yaml_fields(self) -> List[str]:
        """Non-secret YAML field names this adapter persists."""
        return []

    def is_configured(self, block: Optional[Dict[str, Any]]) -> bool:
        """True when ``block`` has enough fields to count as connected."""
        return False

    def normalize(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Validate provider-specific fields; raise ValueError on bad input.

        Return a dict of yaml_fields only (no shared webhook/status keys).
        """
        return {}

    def ui_schema(self) -> Dict[str, Any]:
        """Admin Settings schema: fields + secret copy. Empty by default."""
        return {"fields": []}

    def missing_secret_detail(self, site_id: str) -> str:
        """HTTP 400 copy when the vault/header/body secret is absent."""
        key = self.vault_key(site_id) or ""
        alias = self.vault_http_alias or "X-Vault-Publish-Pass"
        schema = self.ui_schema() or {}
        label = (schema.get("secret") or {}).get("label") or "Publish secret"
        return (
            f"{label} missing: unlock the vault and set {key}, send {alias}, "
            "or pass password in the body for smoke"
        )

    @abstractmethod
    async def test(self) -> Dict[str, Any]:
        """Probe connectivity. Return ``{success, latency_ms?, error?}``."""

    @abstractmethod
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
        """Transfer ``dist_dir`` to the remote host. Raise on failure.

        Optional return may include ``public_url`` and other yaml_fields
        the adapter learns during deploy.
        """

    @abstractmethod
    def capabilities(self) -> Dict[str, Any]:
        """Feature flags for UI / orchestrator (incremental, auth_methods, …)."""
