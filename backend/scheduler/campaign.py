"""The campaign runner — one simulated day at a time.

Each tick fires the jobs due that day. Outcomes resolve, and whatever is
still unrecovered gets replanned for a later day. Everything else in the
system is a component; this is the loop they all sit in.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.domain.actions import CHARGE_ACTIONS, CONTACT_ACTIONS
from backend.domain.calendar import lands_in_payday_window
from backend.domain.classification import classify
from backend.domain.models import Attempt, Customer, FailedPayment, Trace
from backend.executor.executor import Executor
from backend.ledger import event_types as ev
from backend.ledger.store import Ledger
from backend.policy.engine import PolicyEngine
from backend.policy.limits import AttemptState
from backend.policy.plan import PlannedAction
from backend.scheduler.clock import HORIZON_DAYS, VirtualClock
from backend.scheduler.job_queue import Job, JobQueue


@dataclass
class Campaign:
    strategy: object
    payments: list[FailedPayment]
    customers: dict[str, Customer]
    policy: PolicyEngine
    executor: Executor
    ledger: Ledger | None = None
    horizon: int = HORIZON_DAYS

    clock: VirtualClock = field(default_factory=VirtualClock)
    queue: JobQueue = field(default_factory=JobQueue)
    traces: dict[str, Trace] = field(default_factory=dict)
    states: dict[str, AttemptState] = field(default_factory=dict)
    finished: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.clock.horizon = self.horizon
        self._index = {p.id: p for p in self.payments}
        for payment in self.payments:
            self.traces[payment.id] = Trace(txn_id=payment.id)
            self.states[payment.id] = AttemptState(
                amount_paise_snapshot=payment.amount_paise
            )
        for payment in self.payments:
            self._replan(payment, day=0)

    @property
    def day(self) -> int:
        return self.clock.day

    def _log(self, txn_id: str, type_: str, **payload) -> None:
        if self.ledger:
            self.ledger.append(self.day, txn_id, type_, **payload)

    def _stop(self, payment: FailedPayment, reason: str) -> None:
        trace = self.traces[payment.id]
        trace.abandoned_on_day = self.day
        trace.abandon_reason = reason
        self.finished.add(payment.id)
        self._log(payment.id, ev.ABANDONED, reason=reason)

    # -- planning ----------------------------------------------------

    def _replan(self, payment: FailedPayment, day: int) -> None:
        if payment.id in self.finished:
            return

        customer = self.customers[payment.customer_id]
        plan = self.strategy.plan(payment, customer, self.traces[payment.id], day)

        if plan is None:
            self._stop(payment, "Strategy chose to stop.")
            return

        if plan.day < day or plan.day > self.horizon:
            self._stop(payment, "No action remains inside the recovery window.")
            return

        self._log(payment.id, ev.PLANNED, action=plan.action.value,
                  scheduled_for_day=plan.day, rationale=plan.rationale)
        self.queue.schedule(plan.day, Job(payment.id, plan))

    # -- the tick ----------------------------------------------------

    def tick(self) -> int:
        jobs = self.queue.due(self.day)
        for job in jobs:
            self._fire(job)
        self.clock.advance()
        return len(jobs)

    def _fire(self, job: Job) -> None:
        payment = self._index[job.txn_id]
        if payment.id in self.finished:
            return

        customer = self.customers[payment.customer_id]
        trace = self.traces[payment.id]
        state = self.states[payment.id]
        state.days_elapsed = self.day

        verdict = self.policy.check(job.plan, payment, customer, state)
        if not verdict.approved:
            trace.blocks.append(f"{verdict.rule}: {verdict.reason}")
            self._log(payment.id, ev.BLOCKED, rule=verdict.rule, reason=verdict.reason)
            self._stop(payment, f"Blocked by {verdict.rule}.")
            return

        reason = classify(payment.reason_code)
        attempt_index = len(trace.attempts) + 1

        result = self.executor.execute(
            plan=job.plan,
            payment=payment,
            customer=customer,
            attempt_index=attempt_index,
            failure_class=reason.failure_class.value,
            payday_aligned=lands_in_payday_window(
                payment.failed_on_day, customer.payday, self.day
            ),
        )

        if result.error:
            self._handle_gateway_error(payment, job, result)
            return

        if result.replayed:
            self._log(payment.id, ev.DUPLICATE_SUPPRESSED, key=result.key)
            return

        self._record(payment, job, result, attempt_index)

    def _handle_gateway_error(self, payment, job, result) -> None:
        """Transport failed, so we do not know whether the charge landed.
        The SAME idempotency key is re-presented tomorrow rather than a
        fresh attempt being invented."""
        self._log(payment.id, ev.GATEWAY_ERROR, error=result.error, key=result.key)
        if self.day + 1 > self.horizon:
            self._stop(payment, "Gateway unreachable inside the window.")
            return
        self.queue.schedule(self.day + 1, Job(payment.id, PlannedAction(
            action=job.plan.action,
            day=self.day + 1,
            hour=job.plan.hour,
            channel=job.plan.channel,
            amount_paise=job.plan.amount_paise,
            rationale=job.plan.rationale + " [re-presented after gateway error]",
        )))

    def _record(self, payment, job, result, attempt_index) -> None:
        trace = self.traces[payment.id]
        state = self.states[payment.id]
        outcome = result.outcome
        is_charge = job.plan.action in CHARGE_ACTIONS
        is_contact = job.plan.action in CONTACT_ACTIONS

        trace.attempts.append(Attempt(
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
        ))

        self._log(
            payment.id, ev.EXECUTED,
            action=job.plan.action.value,
            key=result.key,
            order_id=result.gateway.order_id if result.gateway else None,
            payment_ref=result.gateway.payment_ref if result.gateway else None,
            gateway_accepted=bool(result.gateway),
            gateway_live=bool(result.gateway and result.gateway.live),
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
            self._log(payment.id, ev.RECOVERED,
                      amount_rupees=round(payment.amount_rupees))
            return

        self._replan(payment, self.day)

    # -- driver ------------------------------------------------------

    def run(self) -> dict[str, Trace]:
        while not self.clock.finished:
            self.tick()
        for txn_id, trace in self.traces.items():
            if txn_id not in self.finished:
                trace.abandoned_on_day = self.horizon
                trace.abandon_reason = "Recovery window closed."
        if self.ledger:
            self.ledger.commit()
        return self.traces
