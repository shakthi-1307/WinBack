"""
Model access, behind a seam.

Two implementations:

  LiveClient    — any OpenAI-compatible endpoint (Groq, OpenAI, together...).
                  Used when WINBACK_API_KEY is set.

  ScriptedClient — a deterministic stand-in used by tests, CI and the attack
                  suite. It has a `gullible` switch: when True it obeys any
                  instruction it finds in its input, exactly like a real model
                  with no defences in front of it.

The gullible switch is the point. It lets the attack suite demonstrate, with
no API key and no flakiness, that the *unguarded* pipeline is compromisable
and the guarded one is not. Running the same suite against a live model is
one environment variable away.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class Usage:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def cost_paise(self) -> float:
        # Groq-class small-model pricing, rounded. Stated openly so the
        # cost-per-decision figure can be argued with.
        per_million_in, per_million_out = 5.0, 8.0  # rupees
        return (
            self.prompt_tokens / 1e6 * per_million_in
            + self.completion_tokens / 1e6 * per_million_out
        ) * 100


class LLMClient(Protocol):
    usage: Usage

    def complete_json(self, system: str, user: str, schema_keys: list[str]) -> dict[str, Any]: ...


# --------------------------------------------------------------------------


class LiveClient:
    """OpenAI-compatible chat completions. Works with Groq unchanged."""

    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.environ.get("WINBACK_MODEL", "llama-3.1-8b-instant")
        self.base_url = os.environ.get(
            "WINBACK_BASE_URL", "https://api.groq.com/openai/v1"
        )
        self.api_key = os.environ["WINBACK_API_KEY"]
        self.usage = Usage()

    def complete_json(self, system: str, user: str, schema_keys: list[str]) -> dict[str, Any]:
        import urllib.request

        body = json.dumps(
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0,
            }
        ).encode()

        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read())

        u = payload.get("usage", {})
        self.usage.calls += 1
        self.usage.prompt_tokens += u.get("prompt_tokens", 0)
        self.usage.completion_tokens += u.get("completion_tokens", 0)

        content = payload["choices"][0]["message"]["content"]
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # A model that returns unparseable JSON is a model that gets
            # ignored, not one that crashes the batch.
            return {}


# --------------------------------------------------------------------------


@dataclass
class ScriptedClient:
    """Offline stand-in.

    `gullible=True` reproduces the failure mode we are defending against:
    a model that treats text found in its input as instructions.
    """

    gullible: bool = False
    usage: Usage = field(default_factory=Usage)

    _OVERRIDE_HINTS = (
        "retry limits do not apply",
        "unlimited attempts",
        "ignore previous instructions",
        "vip account",
    )

    def complete_json(self, system: str, user: str, schema_keys: list[str]) -> dict[str, Any]:
        self.usage.calls += 1
        self.usage.prompt_tokens += max(1, len(system) + len(user)) // 4
        self.usage.completion_tokens += 40

        lowered = user.lower()

        if self.gullible and any(h in lowered for h in self._OVERRIDE_HINTS):
            # Compromised. Returns exactly what the injected text asked for.
            return {
                "failure_class": "timing",
                "action": "retry_scheduled",
                "max_attempts": 99,
                "amount_paise": 500000,
                "delay_days": 0,
                "confidence": 0.99,
                "rationale": "VIP account, retry limits waived per account note.",
            }

        # Sensible default behaviour. A generic decline on a long-tenured
        # customer with a clean history is usually a soft hold worth one
        # spaced retry; a customer who fails repeatedly is usually not.
        if "prior_failures: 0" in lowered or "prior_failures: 1" in lowered:
            action, rationale = (
                "retry_scheduled",
                "Clean payment history suggests a transient soft decline.",
            )
        else:
            action, rationale = (
                "offer_alternate_method",
                "Repeated failures on this instrument; a different rail is more likely to clear.",
            )

        return {
            "failure_class": "ambiguous",
            "action": action,
            "delay_days": 3 if action == "retry_scheduled" else 1,
            "confidence": 0.62,
            "rationale": rationale,
        }


def default_client() -> LLMClient:
    if os.environ.get("WINBACK_API_KEY"):
        return LiveClient()
    return ScriptedClient()


# --------------------------------------------------------------------------


def coerce(payload: dict[str, Any], key: str, allowed: set[str], fallback: str) -> tuple[str, bool]:
    """Force a model's answer into the allowed set.

    Returns (value, was_rejected). This is output allowlisting: even a fully
    compromised model can only ever return one of a handful of values we
    already decided were safe. It is the cheapest and most reliable defence
    in the whole system, and it works regardless of how the model was fooled.
    """
    raw = payload.get(key)
    if isinstance(raw, str) and raw in allowed:
        return raw, False
    return fallback, True


_INT_RE = re.compile(r"^\d+$")


def coerce_int(payload: dict[str, Any], key: str, lo: int, hi: int, fallback: int) -> tuple[int, bool]:
    raw = payload.get(key)
    if isinstance(raw, bool):
        return fallback, True
    if isinstance(raw, int) or (isinstance(raw, str) and _INT_RE.match(raw)):
        v = int(raw)
        if lo <= v <= hi:
            return v, False
    return fallback, True
