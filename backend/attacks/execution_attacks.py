"""The failure modes that actually cause double charges."""

from __future__ import annotations

from backend.attacks.fixtures import SNAPSHOT_PAISE, customer, payment
from backend.domain.actions import Action
from backend.executor.executor import Executor
from backend.executor.fake_gateway import FakeGateway
from backend.executor.idempotency import idempotency_key
from backend.policy.plan import PlannedAction


def run() -> list[tuple[str, str, bool, str]]:
    rows = []
    cust = customer()
    pay = payment(code="insufficient_funds")
    plan = PlannedAction(Action.RETRY_SCHEDULED, day=3, amount_paise=SNAPSHOT_PAISE)

    executor = Executor(gateway=FakeGateway(failure_rate=0.0))
    kwargs = dict(payment=pay, customer=cust, attempt_index=1,
                  failure_class="timing", payday_aligned=False)

    first = executor.execute(plan=plan, **kwargs)
    second = executor.execute(plan=plan, **kwargs)
    rows.append(("X1", "Same job fired twice (duplicate queue message)",
                 second.replayed and not second.executed
                 and executor.gateway.calls == 1,
                 "one gateway call, second suppressed"))

    rows.append(("X2", "Process restart re-presents the same action",
                 idempotency_key(pay.id, 1, plan) == first.key,
                 "key derived from content, not generated"))

    later = PlannedAction(Action.RETRY_SCHEDULED, day=7, amount_paise=SNAPSHOT_PAISE)
    rows.append(("X3", "A genuinely different attempt is not falsely suppressed",
                 idempotency_key(pay.id, 2, later) != first.key,
                 "over-suppression is a bug too"))
    return rows
