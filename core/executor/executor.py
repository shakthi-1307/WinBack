"""
The executor — the Runner.

Carries out approved actions and nothing else. It has no opinions: by the
time an action reaches here it has already passed the policy engine, so the
executor's only jobs are to do it exactly once and to record honestly what
happened.

The two layers, made concrete
-----------------------------
For a charge, the executor asks two different systems two different questions:

    gateway.create_and_attempt()   did the API call work?
    simulator.resolve()            would the bank have approved?

Both answers are stored, separately, on the same attempt record. They must
never be collapsed into a single `status` field — "the integration worked and
the customer still would not have paid" is a distinct and important outcome,
and a schema that cannot express it loses the ability to say so.

Exactly once
------------
Every attempt derives an idempotency key from its own content. If the same
key is presented twice — a retried job, a duplicated queue message, an
operator clicking twice — the second call returns the first result and no
money moves. The key is checked locally *and* sent to the gateway, because
trusting one layer with duplicate suppression is how double charges happen.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from core.domain.models import Customer, FailedPayment
from core.executor.gateway import Gateway, GatewayError, GatewayResult
from core.policy.engine import CHARGE_ACTIONS, CONTACT_ACTIONS, PlannedAction
from sim.simulator import AttemptContext, Outcome, resolve


def idempotency_key(txn_id: str, attempt_index: int, plan: PlannedAction) -> str:
    """Derived from content, not generated randomly.

    A random key regenerated on retry defeats the entire purpose — the retry
    would look like a new attempt. Deriving it from (transaction, attempt,
    action, day, amount) means the same logical attempt always produces the
    same key, however many times the process crashes and restarts.
    """
    raw = f"{txn_id}|{attempt_index}|{plan.action.value}|{plan.day}|{plan.amount_paise}"
    return "wb_" + hashlib.sha256(raw.encode()).hexdigest()[:32]


@dataclass
class ExecutionResult:
    key: str
    executed: bool
    replayed: bool
    """True if this key had already been executed — no new side effects."""

    gateway: GatewayResult | None = None
    outcome: Outcome | None = None
    error: str = ""

    @property
    def recovered(self) -> bool:
        return bool(self.outcome and self.outcome.success)


@dataclass
class Executor:
    gateway: Gateway
    seen: dict[str, ExecutionResult] = field(default_factory=dict)
    gateway_errors: int = 0
    duplicate_suppressions: int = 0

    def execute(
        self,
        plan: PlannedAction,
        payment: FailedPayment,
        customer: Customer,
        attempt_index: int,
        failure_class: str,
        payday_aligned: bool,
    ) -> ExecutionResult:
        key = idempotency_key(payment.id, attempt_index, plan)

        if key in self.seen:
            self.duplicate_suppressions += 1
            prior = self.seen[key]
            return ExecutionResult(
                key=key,
                executed=False,
                replayed=True,
                gateway=prior.gateway,
                outcome=prior.outcome,
            )

        is_charge = plan.action in CHARGE_ACTIONS
        gateway_result: GatewayResult | None = None

        # --- layer one: mechanics -------------------------------------
        if is_charge:
            try:
                gateway_result = self.gateway.create_and_attempt(
                    idempotency_key=key,
                    amount_paise=plan.amount_paise,
                    txn_id=payment.id,
                    notes={"reason_code": payment.reason_code, "recovery_day": plan.day},
                )
            except GatewayError as e:
                # The call failed in transport. We do NOT know whether it
                # landed, so we record the failure and let the scheduler
                # re-present the SAME key later rather than inventing a new
                # attempt.
                self.gateway_errors += 1
                result = ExecutionResult(key=key, executed=False, replayed=False, error=str(e))
                return result

        # --- layer two: behaviour -------------------------------------
        outcome = resolve(
            AttemptContext(
                txn_id=payment.id,
                reason_code=payment.reason_code,
                failure_class=failure_class,
                action=plan.action.value,
                attempt_index=attempt_index,
                days_since_failure=plan.day,
                payday_aligned=payday_aligned,
            )
        )

        result = ExecutionResult(
            key=key,
            executed=True,
            replayed=False,
            gateway=gateway_result,
            outcome=outcome,
        )
        self.seen[key] = result
        return result

    @property
    def is_contact(self) -> set:
        return CONTACT_ACTIONS
