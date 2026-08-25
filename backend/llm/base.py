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

    @property
    def cost_paise(self) -> float:
        """Groq-class small-model pricing, rounded. Stated openly so the
        cost-per-decision figure can be argued with."""
        return (
            self.prompt_tokens / 1e6 * RUPEES_PER_MILLION_INPUT
            + self.completion_tokens / 1e6 * RUPEES_PER_MILLION_OUTPUT
        ) * 100


class LLMClient(Protocol):
    usage: Usage

    def complete_json(
        self, system: str, user: str, schema_keys: list[str]
    ) -> dict[str, Any]: ...
