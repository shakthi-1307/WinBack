"""Baseline: retry three times, immediately.

The most common real-world behaviour. Ignores the reason code entirely and
assumes that trying harder and sooner is trying better.
"""

from __future__ import annotations

from backend.domain.actions import Action
from backend.domain.models import Customer, FailedPayment, Trace
from backend.policy.plan import PlannedAction
from backend.strategies.base import charges_so_far

SCHEDULE = [0, 1, 2]


class RetryThriceImmediate:
    name = "retry_x3_immediate"

    def plan(self, payment: FailedPayment, customer: Customer,
             trace: Trace, day: int) -> PlannedAction | None:
        used = charges_so_far(trace)
        if used >= len(SCHEDULE):
            return None
        return PlannedAction(
            action=Action.RETRY_NOW if used == 0 else Action.RETRY_SCHEDULED,
            day=SCHEDULE[used],
            amount_paise=payment.amount_paise,
            rationale="Fixed aggressive retry schedule; reason code ignored.",
        )
