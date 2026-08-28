"""The model seam: what any client must provide, and how usage is counted."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

RUPEES_PER_MILLION_INPUT = 5.0
RUPEES_PER_MILLION_OUTPUT = 8.0


@dataclass
class Usage:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0

    failures: int = 0
    """Calls that did not return a usable answer — HTTP errors, timeouts,
    unparseable JSON. Counted rather than raised: a model provider having a
    bad afternoon must not stop a merchant recovering money."""

    consecutive_failures: int = 0
    circuit_open: bool = False
    """Once tripped, no further calls are attempted for the rest of the run."""

    last_error: str = ""

    @property
    def cost_paise(self) -> float:
        """Groq-class small-model pricing, rounded. Stated openly so the
        cost-per-decision figure can be argued with."""
        return (
            self.prompt_tokens / 1e6 * RUPEES_PER_MILLION_INPUT
            + self.completion_tokens / 1e6 * RUPEES_PER_MILLION_OUTPUT
        ) * 100

    @property
    def healthy(self) -> bool:
        return self.failures == 0 and not self.circuit_open


class LLMClient(Protocol):
    usage: Usage

    def complete_json(
        self, system: str, user: str, schema_keys: list[str]
    ) -> dict[str, Any]: ...
