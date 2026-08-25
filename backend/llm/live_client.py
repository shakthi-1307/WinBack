"""A real model endpoint. OpenAI-compatible, so Groq works unchanged."""

from __future__ import annotations

import json
import os
from typing import Any

from backend.config.env import ensure_loaded
from backend.llm.base import Usage

DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "llama-3.1-8b-instant"
TIMEOUT_SECONDS = 30


class LiveClient:
    def __init__(self, model: str | None = None) -> None:
        ensure_loaded()
        self.model = model or os.environ.get("WINBACK_MODEL", DEFAULT_MODEL)
        self.base_url = os.environ.get("WINBACK_BASE_URL", DEFAULT_BASE_URL)
        self.api_key = os.environ["WINBACK_API_KEY"]
        self.usage = Usage()

    def complete_json(self, system: str, user: str,
                      schema_keys: list[str]) -> dict[str, Any]:
        import urllib.request

        body = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
        }).encode()

        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read())

        usage = payload.get("usage", {})
        self.usage.calls += 1
        self.usage.prompt_tokens += usage.get("prompt_tokens", 0)
        self.usage.completion_tokens += usage.get("completion_tokens", 0)

        content = payload["choices"][0]["message"]["content"]
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # A model returning unparseable JSON gets ignored, not allowed to
            # crash a 400-transaction batch.
            return {}
