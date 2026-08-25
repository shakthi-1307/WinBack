"""Baseline: do nothing.

The floor, and not a joke. The merchant loses nothing to fees, annoys
nobody, and damages no issuer relationships. A recovery strategy that barely
beats this one is not obviously worth running.
"""

from __future__ import annotations

from backend.domain.models import Customer, FailedPayment, Trace
from backend.policy.plan import PlannedAction


class DoNothing:
    name = "do_nothing"

    def plan(self, payment: FailedPayment, customer: Customer,
             trace: Trace, day: int) -> PlannedAction | None:
        return None
