"""Actions that break a hard rule.

These involve no model at all. The rule is enforced regardless of how the
action came to be proposed — by a model, a bug, or a compromised upstream
service.
"""

from __future__ import annotations

from backend.attacks.fixtures import SNAPSHOT_PAISE, customer, payment
from backend.domain.actions import Action
from backend.domain.models import Channel
from backend.policy.engine import PolicyEngine
from backend.policy.limits import AttemptState
from backend.policy.plan import PlannedAction

ATTACKS = [
    ("P1", "Fourth charge attempt when the cap is three",
     PlannedAction(Action.RETRY_SCHEDULED, day=8, amount_paise=SNAPSHOT_PAISE),
     dict(charges_used=3), dict(), "CHARGE_CAP"),
    ("P2", "Message scheduled for 02:40",
     PlannedAction(Action.NUDGE_FIX_INSTRUMENT, day=2, hour=2, channel=Channel.SMS),
     dict(), dict(), "QUIET_HOURS"),
    ("P3", "SMS to a DND-registered customer",
     PlannedAction(Action.NUDGE_FIX_INSTRUMENT, day=2, hour=11, channel=Channel.SMS),
     dict(), dict(dnd=True), "DND"),
    ("P4", "Charge against a revoked mandate",
     PlannedAction(Action.RETRY_SCHEDULED, day=2, amount_paise=SNAPSHOT_PAISE),
     dict(), dict(mandate=False), "MANDATE_INVALID"),
    ("P5", "Charge inflated above the failure snapshot",
     PlannedAction(Action.RETRY_SCHEDULED, day=2, amount_paise=500000),
     dict(), dict(), "AMOUNT_TAMPERED"),
    ("P6", "Action scheduled past the 21-day window",
     PlannedAction(Action.RETRY_SCHEDULED, day=40, amount_paise=SNAPSHOT_PAISE),
     dict(), dict(), "WINDOW_EXPIRED"),
    ("P7", "Second charge inside the cooldown",
     PlannedAction(Action.RETRY_SCHEDULED, day=3, amount_paise=SNAPSHOT_PAISE),
     dict(charges_used=1, last_charge_day=3), dict(), "COOLDOWN"),
]


def run() -> list[tuple[str, str, bool, str]]:
    engine = PolicyEngine()
    rows = []
    for attack_id, name, plan, state_kwargs, context, expected in ATTACKS:
        cust = customer(dnd=context.get("dnd", False))
        pay = payment(mandate=context.get("mandate", True))
        state = AttemptState(amount_paise_snapshot=SNAPSHOT_PAISE, **state_kwargs)
        verdict = engine.check(plan, pay, cust, state)
        held = not verdict.approved and verdict.rule == expected
        rows.append((attack_id, name, held, verdict.rule or "APPROVED"))
    return rows
