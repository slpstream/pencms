"""Install edition: ``core`` unless ``pencms_pro.init_pro`` loaded successfully.

Edition is overlay presence, not a config.ini flag. ``main.py`` calls
``set_edition("pro")`` after a successful import; everything else reads
``get_edition()``.
"""

from __future__ import annotations

from typing import Literal

Edition = Literal["core", "pro"]

_edition: Edition = "core"


def get_edition() -> Edition:
    return _edition


def set_edition(name: str) -> None:
    """Set the process edition. Raises ValueError on unknown names."""
    global _edition
    n = (name or "").strip().lower()
    if n not in ("core", "pro"):
        raise ValueError(f"edition must be 'core' or 'pro', got {name!r}")
    _edition = n  # type: ignore[assignment]
