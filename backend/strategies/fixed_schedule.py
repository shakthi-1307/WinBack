"""Baseline: a fixed spaced schedule, days 1 / 3 / 5.

The "sophisticated" version most dunning tools ship. Spacing attempts out is
a genuine improvement over hammering, but it still applies one schedule to
every kind of failure.
"""

from __future__ import annotations

from backend.domain.actions import Action
from backend.domain.models import Customer, FailedPayment, Trace
from backend.policy.plan import PlannedAction
from backend.strategies.base import charges_so_far

SCHEDULE = [1, 3, 5]


class FixedSchedule:
    name = "fixed_d1_d3_d5"

    def plan(self, payment: FailedPayment, customer: Customer,
             trace: Trace, day: int) -> PlannedAction | None:
        used = charges_so_far(trace)
        if used >= len(SCHEDULE):
            return None
        return PlannedAction(
            action=Action.RETRY_SCHEDULED,
            day=SCHEDULE[used],
            amount_paise=payment.amount_paise,
            rationale="Fixed spaced retry schedule; reason code ignored.",
        )
