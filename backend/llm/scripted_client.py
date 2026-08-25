"""A deterministic stand-in used by tests, CI and the attack suite.

`gullible=True` reproduces the failure mode being defended against: a model
that treats text found in its input as instructions. That switch is what lets
the attack suite prove the unguarded pipeline is compromisable and the guarded
one is not — with no API key and no flakiness.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.llm.base import Usage

OVERRIDE_HINTS = (
    "retry limits do not apply",
    "unlimited attempts",
    "ignore previous instructions",
    "vip account",
)


@dataclass
class ScriptedClient:
    gullible: bool = False
    usage: Usage = field(default_factory=Usage)

    def complete_json(self, system: str, user: str,
                      schema_keys: list[str]) -> dict[str, Any]:
        self.usage.calls += 1
        self.usage.prompt_tokens += max(1, len(system) + len(user)) // 4
        self.usage.completion_tokens += 40

        lowered = user.lower()

        if self.gullible and any(hint in lowered for hint in OVERRIDE_HINTS):
            return {
                "failure_class": "timing",
                "action": "retry_scheduled",
                "max_attempts": 99,
                "amount_paise": 500000,
                "delay_days": 0,
                "confidence": 0.99,
                "rationale": "VIP account, retry limits waived per account note.",
            }

        clean_history = ("prior_failures: 0" in lowered
                         or "prior_failures: 1" in lowered)
        if clean_history:
            action = "retry_scheduled"
            rationale = "Clean payment history suggests a transient soft decline."
        else:
            action = "offer_alternate_method"
            rationale = ("Repeated failures on this instrument; a different rail "
                         "is more likely to clear.")

        return {
            "failure_class": "ambiguous",
            "action": action,
            "delay_days": 3 if action == "retry_scheduled" else 1,
            "confidence": 0.62,
            "rationale": rationale,
        }
