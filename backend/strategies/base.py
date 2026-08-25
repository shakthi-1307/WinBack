"""What a strategy is, and the small helpers every strategy needs.

A strategy answers one question, repeatedly: given everything that has
happened to this transaction so far, what should we do next — and when?

Returning None means STOP. Stopping is a decision, and the strategies that
cannot make it are exactly the ones that lose money.
"""

from __future__ import annotations

from typing import Protocol

from backend.domain.models import Customer, FailedPayment, Trace
from backend.policy.plan import PlannedAction


class Strategy(Protocol):
    name: str

    def plan(self, payment: FailedPayment, customer: Customer,
             trace: Trace, day: int) -> PlannedAction | None: ...


def charges_so_far(trace: Trace) -> int:
    return sum(1 for attempt in trace.attempts if attempt.is_charge)


def contacts_so_far(trace: Trace) -> int:
    return sum(1 for attempt in trace.attempts if attempt.contacted_customer)
