"""Loads `.env` into the process environment. Nothing else."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT / ".env"

_loaded = False


def load_env(path: Path | None = None, *, override: bool = False) -> dict[str, str]:
    """Read KEY=VALUE pairs from a .env file.

    Real environment variables win by default, so CI and
    `export KEY=... python -m ...` override the file rather than fighting it.
    A missing file is a supported mode, not an error.

    Written against the standard library on purpose: a twenty-line parser is
    cheaper than a dependency, and a reviewer can see exactly what happens to
    their credentials in one screen.
    """
    global _loaded
    target = path or ENV_PATH
    found: dict[str, str] = {}

    if not target.exists():
        _loaded = True
        return found

    for raw in target.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]

        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if not key:
            continue

        found[key] = value
        if override or key not in os.environ:
            os.environ[key] = value

    _loaded = True
    return found


def ensure_loaded() -> None:
    if not _loaded:
        load_env()


load_env()
