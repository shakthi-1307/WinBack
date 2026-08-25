"""Masking. Secrets are never printed whole — not in logs, not on camera."""

from __future__ import annotations


def mask(value: str) -> str:
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}{'*' * 8}{value[-4:]}"
