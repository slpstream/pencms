"""Discovery document (llms.txt) resolution and overlay registration.

Core serves its clean discovery document at ``GET /llms.txt``.
When an overlay like ``pencms_pro`` is mounted, it can register an overlay
provider via ``register_llms_overlay`` so the runtime response dynamically
includes the overlay endpoints.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, List

_LLMS_FALLBACK = """# PenCMS MCP

- MCP endpoint: /api/mcp (Streamable HTTP); echo Mcp-Session-Id after initialize; scopes read | write; site-bound agent keys
- PRM: /.well-known/oauth-protected-resource
- AS: /.well-known/oauth-authorization-server
- Authorize: /oauth/authorize  Token: /oauth/token
- Automation: POST /api/auth/token  {"agent_key":"pen-sk-…"}
- Bootstrap: POST /api/auth/agent/request-code  {"name","scopes","site_id"}
- Sites: GET /api/sites
- Docs: core/docs/mcp_guide.md
"""

_LLMS_CANDIDATES = (
    Path(__file__).resolve().parent.parent.parent.parent / "core" / "docs" / "llms.txt",
    Path(__file__).resolve().parent.parent.parent / "docs" / "llms.txt",
    Path(__file__).resolve().parent.parent.parent.parent / "llms.txt",
)

_overlay_providers: List[Callable[[], str]] = []


def register_llms_overlay(provider: Callable[[], str]) -> None:
    """Register a callback that returns overlay text for ``/llms.txt``."""
    _overlay_providers.append(provider)


def clear_llms_overlays() -> None:
    """Clear registered overlay providers (primarily for tests)."""
    _overlay_providers.clear()


def get_llms_content() -> str:
    """Resolve base Core llms.txt and dynamically append any registered overlays."""
    base_text: str | None = None
    for path in _LLMS_CANDIDATES:
        try:
            if path.is_file():
                base_text = path.read_text(encoding="utf-8")
                break
        except OSError:
            continue

    if base_text is None:
        base_text = _LLMS_FALLBACK

    if not _overlay_providers:
        return base_text

    overlays: List[str] = []
    for provider in _overlay_providers:
        try:
            content = provider()
            if content and content.strip():
                overlays.append(content.strip())
        except Exception:
            continue

    if not overlays:
        return base_text

    if base_text.startswith("# PenCMS MCP"):
        base_text = base_text.replace("# PenCMS MCP", "# PenCMS MCP (Pro)", 1)

    return base_text.rstrip() + "\n\n" + "\n\n".join(overlays) + "\n"
