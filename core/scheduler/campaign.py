"""
The campaign runner — the Calendar Keeper, and the loop everything sits in.

Recovery happens over days: retry after payday, nudge after 48 hours, give up
at day 21. Real cron makes that impossible to demonstrate — you would be
filming a screen where nothing happens for a fortnight.

So time is a number this module owns and advances. Each tick is a simulated
day. Jobs scheduled for that day fire, outcomes resolve, and whatever is still
unrecovered gets replanned for a later day. A 21-day campaign across 400
transactions completes in well under a second.

Two consequences beyond the demo: the eval harness can run a hundred campaigns
in CI, and there is no Celery, no Redis and no worker process to build, debug
or explain.

One deliberate constraint: **the agent reads the clock, it cannot set it.**
An agent able to move time could grant itself an extra retry window, which is
a small hole a good reviewer would find quickly.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from core.domain.models import Attempt, Customer, FailedPayment, Trace
from core.domain.reason_codes import classify
from core.executor.executor import Executor
from core.ledger import events as ev
from core.ledger.events import Ledger
from core.policy.engine import (
    CHARGE_ACTIONS,
    CONTACT_ACTIONS,
    AttemptState,
    PlannedAction,
    PolicyEngine,
)

HORIZON_DAYS = 21
PAYDAY_WINDOW = 3


def calendar_day(failed_on_day: int, days_since: int) -> int:
    return ((failed_on_day - 1 + days_since) % 30) + 1


def payday_aligned(payment: FailedPayment, customer: Customer, days_since: int) -> bool:
    day = calendar_day(payment.failed_on_day, days_since)
    return any(
        day == ((customer.payday - 1 + offset) % 30) + 1
        for offset in range(PAYDAY_WINDOW + 1)
    )


@dataclass
class Job:
    txn_id: str
    plan: PlannedAction


@dataclass
class Campaign:
    strategy: object
    payments: list[FailedPayment]
    customers: dict[str, Customer]
    policy: PolicyEngine
    executor: Executor
    ledger: Ledger | None = None
    horizon: int = HORIZON_DAYS

    traces: dict[str, Trace] = field(default_factory=dict)
    states: dict[str, AttemptState] = field(default_factory=dict)
    queue: dict[int, list[Job]] = field(default_factory=lambda: defaultdict(list))
    day: int = 0
    finished: set = field(default_factory=set)

    # -- setup ----------------------------------------------------------

    def __post_init__(self) -> None:
        for p in self.payments:
            self.traces[p.id] = Trace(txn_id=p.id)
            self.states[p.id] = AttemptState(amount_paise_snapshot=p.amount_paise)
        for p in self.payments:
            self._replan(p, day=0)

    def _by_id(self, txn_id: str) -> FailedPayment:
        return self._index[txn_id]

    @property
    def _index(self) -> dict[str, FailedPayment]:
        if not hasattr(self, "_idx_cache"):
            self._idx_cache = {p.id: p for p in self.payments}
        return self._idx_cache

    def _log(self, txn_id: str, type_: str, **payload) -> None:
        if self.ledger:
            self.ledger.append(self.day, txn_id, type_, **payload)

    # -- planning -------------------------------------------------------

    def _replan(self, payment: FailedPayment, day: int) -> None:
        if payment.id in self.finished:
            return

        customer = self.customers[payment.customer_id]
        trace = self.traces[payment.id]
        plan = self.strategy.plan(payment, customer, trace, day)

        if plan is None:
            trace.abandoned_on_day = day
            trace.abandon_reason = "Strategy chose to stop."
            self.finished.add(payment.id)
            self._log(payment.id, ev.ABANDONED, reason=trace.abandon_reason)
            return

        if plan.day < day or plan.day > self.horizon:
            trace.abandoned_on_day = day
            trace.abandon_reason = "No action remains inside the recovery window."
            self.finished.add(payment.id)
            self._log(payment.id, ev.ABANDONED, reason=trace.abandon_reason)
            return

        self._log(
            payment.id,
            ev.PLANNED,
            action=plan.action.value,
            scheduled_for_day=plan.day,
            rationale=plan.rationale,
        )
        self.queue[plan.day].append(Job(payment.id, plan))

    # -- the tick -------------------------------------------------------

    def tick(self) -> int:
        """Run one simulated day. Returns the number of jobs fired."""
        jobs = self.queue.pop(self.day, [])
        for job in jobs:
            self._fire(job)
        fired = len(jobs)
        self.day += 1
        return fired

    def _fire(self, job: Job) -> None:
        payment = self._by_id(job.txn_id)
        if payment.id in self.finished:
            return

        customer = self.customers[payment.customer_id]
        trace = self.traces[payment.id]
        state = self.states[payment.id]
        state.days_elapsed = self.day

        verdict = self.policy.check(job.plan, payment, customer, state)
        if not verdict.approved:
            trace.blocks.append(f"{verdict.rule}: {verdict.reason}")
            trace.abandoned_on_day = self.day
            trace.abandon_reason = f"Blocked by {verdict.rule}."
            self.finished.add(payment.id)
            self._log(payment.id, ev.BLOCKED, rule=verdict.rule, reason=verdict.reason)
            return

        rc = classify(payment.reason_code)
        attempt_index = len(trace.attempts) + 1

        result = self.executor.execute(
            plan=job.plan,
            payment=payment,
            customer=customer,
            attempt_index=attempt_index,
            failure_class=rc.failure_class.value,
            payday_aligned=payday_aligned(payment, customer, self.day),
        )

        # Transport failed. We do not know whether it landed, so the SAME
        # idempotency key is re-presented tomorrow rather than a fresh
        # attempt being invented.
        if result.error:
            self._log(payment.id, ev.GATEWAY_ERROR, error=result.error, key=result.key)
            if self.day + 1 <= self.horizon:
                retry = PlannedAction(
                    action=job.plan.action,
                    day=self.day + 1,
                    hour=job.plan.hour,
                    channel=job.plan.channel,
                    amount_paise=job.plan.amount_paise,
                    rationale=job.plan.rationale + " [re-presented after gateway error]",
                )
                self.queue[self.day + 1].append(Job(payment.id, retry))
            else:
                trace.abandoned_on_day = self.day
                trace.abandon_reason = "Gateway unreachable inside the window."
                self.finished.add(payment.id)
                self._log(payment.id, ev.ABANDONED, reason=trace.abandon_reason)
            return

        if result.replayed:
            self._log(payment.id, ev.DUPLICATE_SUPPRESSED, key=result.key)
            return

        is_charge = job.plan.action in CHARGE_ACTIONS
        is_contact = job.plan.action in CONTACT_ACTIONS
        outcome = result.outcome

        trace.attempts.append(
            Attempt(
                txn_id=payment.id,
                attempt_index=attempt_index,
                day=self.day,
                action=job.plan.action.value,
                success=outcome.success,
                probability=outcome.probability,
                is_charge=is_charge,
                contacted_customer=is_contact,
                damaged_issuer_trust=outcome.damaged_issuer_trust,
                reason=job.plan.rationale,
            )
        )

        self._log(
            payment.id,
            ev.EXECUTED,
            action=job.plan.action.value,
            key=result.key,
            order_id=result.gateway.order_id if result.gateway else None,
            payment_ref=result.gateway.payment_ref if result.gateway else None,
            gateway_accepted=bool(result.gateway),
            success=outcome.success,
            probability=outcome.probability,
            why=outcome.explanation,
        )

        if is_charge:
            state.charges_used += 1
            state.last_charge_day = self.day
        if is_contact:
            state.contacts_used += 1

        if outcome.success:
            trace.recovered = True
            trace.recovered_on_day = self.day
            self.finished.add(payment.id)
            self._log(payment.id, ev.RECOVERED, amount_rupees=round(payment.amount_rupees))
            return

        self._replan(payment, self.day)

    # -- driver ---------------------------------------------------------

    def run(self) -> dict[str, Trace]:
        while self.day <= self.horizon:
            self.tick()
        for txn_id, trace in self.traces.items():
            if txn_id not in self.finished:
                trace.abandoned_on_day = self.horizon
                trace.abandon_reason = "Recovery window closed."
        if self.ledger:
            self.ledger.commit()
        return self.traces
