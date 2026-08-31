"""Phase 6 edition grep gates — Core product source must not contain Pro tokens."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND / "scripts"))

from check_edition_gates import check  # noqa: E402


def test_edition_grep_gates():
    errors = check()
    assert errors == [], "\n".join(errors)
