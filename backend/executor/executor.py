"""The executor — the Runner.

Carries out approved actions and nothing else. By the time an action arrives
here it has already passed the policy engine, so the executor's only jobs are
to do it exactly once and to record honestly what happened.

The two layers, made concrete. For a charge it asks two different systems two
different questions:

    gateway.create_and_attempt()   did the API call work?
    simulator.resolve()            would the bank have approved?

Both answers are stored separately on the same attempt. They must never
collapse into one status field — "the integration worked and the customer
still would not have paid" is a distinct and important outcome, and a schema
that cannot express it loses the ability to say so.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.domain.actions import CHARGE_ACTIONS
from backend.domain.models import Customer, FailedPayment
from backend.executor.gateway_base import Gateway, GatewayError, GatewayResult
from backend.executor.idempotency import idempotency_key
from backend.policy.plan import PlannedAction
from simulation.simulator import AttemptContext, Outcome, resolve


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
    live_gateway_calls: int = 0
    substituted_gateway_calls: int = 0

    def execute(self, plan: PlannedAction, payment: FailedPayment,
                customer: Customer, attempt_index: int, failure_class: str,
                payday_aligned: bool) -> ExecutionResult:
        key = idempotency_key(payment.id, attempt_index, plan)

        if key in self.seen:
            self.duplicate_suppressions += 1
            prior = self.seen[key]
            return ExecutionResult(key=key, executed=False, replayed=True,
                                   gateway=prior.gateway, outcome=prior.outcome)

        gateway_result: GatewayResult | None = None

        if plan.action in CHARGE_ACTIONS:
            try:
                gateway_result = self.gateway.create_and_attempt(
                    idempotency_key=key,
                    amount_paise=plan.amount_paise,
                    txn_id=payment.id,
                    notes={"reason_code": payment.reason_code,
                           "recovery_day": plan.day},
                )
            except GatewayError as error:
                # Transport failed. We do NOT know whether it landed, so
                # nothing is recorded and nothing is cached — the same key
                # gets re-presented rather than a new attempt invented.
                self.gateway_errors += 1
                return ExecutionResult(key=key, executed=False, replayed=False,
                                       error=str(error))
            else:
                if gateway_result.live:
                    self.live_gateway_calls += 1
                else:
                    self.substituted_gateway_calls += 1

        outcome = resolve(AttemptContext(
            txn_id=payment.id,
            reason_code=payment.reason_code,
            failure_class=failure_class,
            action=plan.action.value,
            attempt_index=attempt_index,
            days_since_failure=plan.day,
            payday_aligned=payday_aligned,
        ))

        result = ExecutionResult(key=key, executed=True, replayed=False,
                                 gateway=gateway_result, outcome=outcome)
        self.seen[key] = result
        return result
