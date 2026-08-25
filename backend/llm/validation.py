"""Output allowlisting — the load-bearing defence.

A compromised model can only ever return a value that was already on the
list. This works regardless of how the model was fooled, because it never
reads the text at all.
"""

from __future__ import annotations

import re
from typing import Any

_INT_RE = re.compile(r"^\d+$")


def coerce(payload: dict[str, Any], key: str, allowed: set[str],
           fallback: str) -> tuple[str, bool]:
    """Returns (value, was_rejected)."""
    raw = payload.get(key)
    if isinstance(raw, str) and raw in allowed:
        return raw, False
    return fallback, True


def coerce_int(payload: dict[str, Any], key: str, lo: int, hi: int,
               fallback: int) -> tuple[int, bool]:
    raw = payload.get(key)
    if isinstance(raw, bool):
        return fallback, True
    if isinstance(raw, int) or (isinstance(raw, str) and _INT_RE.match(raw)):
        value = int(raw)
        if lo <= value <= hi:
            return value, False
    return fallback, True


def coerce_confidence(payload: dict[str, Any], key: str = "confidence") -> float:
    raw = payload.get(key, 0.5)
    if isinstance(raw, (int, float)) and not isinstance(raw, bool) and 0 <= raw <= 1:
        return float(raw)
    return 0.5


def coerce_text(payload: dict[str, Any], key: str, limit: int = 400) -> str:
    raw = payload.get(key, "")
    return raw[:limit] if isinstance(raw, str) else ""
