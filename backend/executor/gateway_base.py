"""What a payment gateway must provide, and what its answer means.

A gateway answers exactly one question: *did the API call work?*

It does not, and cannot, answer whether the customer's bank would have
approved. Razorpay's test mode returns whatever the sandbox is configured to
return; there is no real customer and no real balance. That second question
belongs to the frozen simulator, and keeping the two apart is the central
design decision of this project.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class GatewayError(RuntimeError):
    """A transport-level failure. The attempt may or may not have landed —
    which is precisely why idempotency keys exist."""


@dataclass(frozen=True)
class GatewayResult:
    order_id: str
    payment_ref: str
    accepted: bool
    """Whether the GATEWAY accepted the request. Not whether the customer paid."""
    raw: dict


class Gateway(Protocol):
    def create_and_attempt(self, *, idempotency_key: str, amount_paise: int,
                           txn_id: str, notes: dict) -> GatewayResult: ...
