"""A real model endpoint. OpenAI-compatible, so Groq works unchanged.

Failure policy
--------------
This client NEVER raises. A model provider returning 403, timing out, or
emitting malformed JSON is an operational event, not a reason to abandon a
recovery campaign — and in this system it is a survivable one, because the
lookup table already decides four fifths of every batch and the rule tier is
a complete strategy on its own.

So a failed call returns an empty payload, the validation layer substitutes
the conservative default, and the transaction is handled by rules. Losing the
model costs a percent or two of recovery, not the run.

After three consecutive failures the circuit opens and no further calls are
attempted. A provider that is down stays down for a few seconds at least, and
400 doomed HTTP requests help nobody.
"""

from __future__ import annotations

import json
import os
from typing import Any

from backend.config.env import ensure_loaded
from backend.llm.base import Usage

DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "llama-3.1-8b-instant"
TIMEOUT_SECONDS = 30
CIRCUIT_TRIPS_AFTER = 3


class LiveClient:
    def __init__(self, model: str | None = None) -> None:
        ensure_loaded()
        self.model = model or os.environ.get("WINBACK_MODEL", DEFAULT_MODEL)
        self.base_url = os.environ.get("WINBACK_BASE_URL", DEFAULT_BASE_URL)
        self.api_key = os.environ["WINBACK_API_KEY"]
        self.usage = Usage()

    # -- the one place a model failure is turned into a shrug ----------

    def _record_failure(self, message: str) -> dict[str, Any]:
        self.usage.failures += 1
        self.usage.consecutive_failures += 1
        self.usage.last_error = message[:500]
        if self.usage.consecutive_failures >= CIRCUIT_TRIPS_AFTER:
            self.usage.circuit_open = True
        return {}

    def _record_success(self) -> None:
        self.usage.consecutive_failures = 0

    def complete_json(self, system: str, user: str,
                      schema_keys: list[str]) -> dict[str, Any]:
        if self.usage.circuit_open:
            return {}

        import urllib.error
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

        self.usage.calls += 1

        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                payload = json.loads(response.read())
        except urllib.error.HTTPError as error:
            # The body carries the provider's actual complaint — an expired
            # key, a decommissioned model, a rate limit. Keep it: a useless
            # error message costs more debugging time than the outage.
            detail = ""
            try:
                detail = json.loads(error.read() or b"{}").get("error", {}).get("message", "")
            except Exception:
                pass
            return self._record_failure(
                f"HTTP {error.code} from {self.base_url}: {detail or error.reason}"
            )
        except Exception as error:
            return self._record_failure(f"{type(error).__name__}: {error}")

        try:
            usage = payload.get("usage", {})
            self.usage.prompt_tokens += usage.get("prompt_tokens", 0)
            self.usage.completion_tokens += usage.get("completion_tokens", 0)
            content = payload["choices"][0]["message"]["content"]
            parsed = json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
            return self._record_failure(f"unusable response: {error}")

        self._record_success()
        return parsed if isinstance(parsed, dict) else {}
