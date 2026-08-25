"""Loads the frozen assumptions. Also supports a sensitivity override.

The override exists so the harness can ask "does the ranking survive if my
priors are wrong?" — the honest answer to "you wrote the world your agent
competes in". The product never touches it.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ASSUMPTIONS_PATH = Path(__file__).parent / "assumptions.yaml"

_override: dict[str, Any] | None = None


@lru_cache(maxsize=1)
def _load_frozen() -> dict[str, Any]:
    with ASSUMPTIONS_PATH.open() as handle:
        return yaml.safe_load(handle)


def load_assumptions() -> dict[str, Any]:
    return _override if _override is not None else _load_frozen()


def set_assumptions_override(assumptions: dict[str, Any] | None) -> None:
    global _override
    _override = assumptions


def assumptions_fingerprint() -> str:
    """SHA-256 of the assumptions file, printed with every result set. If
    this changes between runs, the results are not comparable — and the
    change is visible rather than silent."""
    return hashlib.sha256(ASSUMPTIONS_PATH.read_bytes()).hexdigest()[:16]
