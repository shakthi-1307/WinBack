"""Chooses a client based on configuration. One decision, one file."""

from __future__ import annotations

import os

from backend.config.env import ensure_loaded
from backend.llm.base import LLMClient
from backend.llm.live_client import LiveClient
from backend.llm.scripted_client import ScriptedClient


def default_client() -> LLMClient:
    ensure_loaded()
    if os.environ.get("WINBACK_API_KEY"):
        return LiveClient()
    return ScriptedClient()
