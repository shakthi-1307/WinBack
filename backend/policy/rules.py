"""One function per rule.

Each returns a Verdict when it objects, or None when it has no opinion.
Splitting them out means every limit is independently readable, independently
testable, and impossible to disable by accident while editing another.

No model, no prompt, no judgement anywhere in this file.
"""

from __future__ import annotations

from collections.abc import Callable

from backend.domain.actions import CHARGE_ACTIONS, CONTACT_ACTIONS
from backend.domain.models import Customer, FailedPayment
from backend.policy.limits import AttemptState, Limits
from backend.policy.plan import PlannedAction, Verdict

Rule = Callable[[PlannedAction, FailedPayment, Customer, AttemptState, Limits],
                "Verdict | None"]


def mandate_must_be_valid(plan, payment, customer, state, limits):
    if plan.action in CHARGE_ACTIONS and not payment.mandate_valid:
        return Verdict(False, "MANDATE_INVALID",
                       "The customer's payment permission has expired or been "
                       "revoked. No charge may be attempted at all.")
    return None


def amount_must_match_snapshot(plan, payment, customer, state, limits):
    """The amount is fixed at the moment of failure. There is no code path by
    which anything downstream — including a model — can change it."""
    if plan.action in CHARGE_ACTIONS and plan.amount_paise != state.amount_paise_snapshot:
        return Verdict(False, "AMOUNT_TAMPERED",
                       f"Attempted to charge {plan.amount_paise} against a "
                       f"snapshot of {state.amount_paise_snapshot}.")
    return None


def must_be_inside_recovery_window(plan, payment, customer, state, limits):
    if plan.day > limits.max_recovery_window_days:
        return Verdict(False, "WINDOW_EXPIRED",
                       f"Day {plan.day} is past the "
                       f"{limits.max_recovery_window_days}-day recovery window. "
                       "Continuing to chase costs more than it returns.")
    return None


def charge_cap_not_exceeded(plan, payment, customer, state, limits):
    if plan.action in CHARGE_ACTIONS and state.charges_used >= limits.max_charge_attempts:
        return Verdict(False, "CHARGE_CAP",
                       f"Already used {state.charges_used} of "
                       f"{limits.max_charge_attempts} permitted charge attempts.")
    return None


def contact_cap_not_exceeded(plan, payment, customer, state, limits):
    if plan.action in CONTACT_ACTIONS and state.contacts_used >= limits.max_contacts:
        return Verdict(False, "CONTACT_CAP",
                       f"Already sent {state.contacts_used} of "
                       f"{limits.max_contacts} permitted messages.")
    return None


def charge_cooldown_respected(plan, payment, customer, state, limits):
    if (plan.action in CHARGE_ACTIONS
            and state.last_charge_day is not None
            and plan.day - state.last_charge_day < limits.min_days_between_charges):
        return Verdict(False, "COOLDOWN",
                       f"Last charge was on day {state.last_charge_day}. "
                       f"Minimum gap is {limits.min_days_between_charges} day(s).")
    return None


def dnd_registration_respected(plan, payment, customer, state, limits):
    if (plan.action in CONTACT_ACTIONS
            and customer.dnd
            and plan.channel in limits.dnd_blocked_channels):
        return Verdict(False, "DND",
                       f"Customer is DND-registered; {plan.channel} is not "
                       "permitted. Email remains available.")
    return None


def outside_quiet_hours(plan, payment, customer, state, limits):
    if plan.action in CONTACT_ACTIONS and (
        plan.hour >= limits.quiet_hours_start or plan.hour < limits.quiet_hours_end
    ):
        return Verdict(False, "QUIET_HOURS",
                       f"Hour {plan.hour:02d}:00 falls inside quiet hours "
                       f"({limits.quiet_hours_start}:00-{limits.quiet_hours_end}:00).")
    return None


# Order matters: the most absolute checks run first, so the reported reason is
# the most fundamental one rather than whichever happened to be evaluated.
ALL_RULES: list[Rule] = [
    mandate_must_be_valid,
    amount_must_match_snapshot,
    must_be_inside_recovery_window,
    charge_cap_not_exceeded,
    contact_cap_not_exceeded,
    charge_cooldown_respected,
    dnd_registration_respected,
    outside_quiet_hours,
]
