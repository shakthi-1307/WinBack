"""
The playbook: what is SMART to do for each kind of failure.

This is advice, not permission. The playbook says what tends to work.
The policy engine (core/policy) says what is allowed. Keeping them apart
is deliberate — see docs/architecture.md.

Nothing in this file enforces anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from core.domain.reason_codes import FailureClass


class Action(str, Enum):
    RETRY_NOW = "retry_now"
    """Try the same instrument again immediately."""

    RETRY_SCHEDULED = "retry_scheduled"
    """Try again on a specific future day, chosen deliberately."""

    REPROMPT = "reprompt"
    """Ask the customer to complete the payment again, now, while intent
    is still fresh."""

    NUDGE_FIX_INSTRUMENT = "nudge_fix_instrument"
    """Ask the customer to update or enable their payment method. Charging
    them is pointless until they do."""

    OFFER_ALTERNATE_METHOD = "offer_alternate_method"
    """Stop using this instrument. Offer a different rail (UPI, netbanking)."""

    ABANDON = "abandon"
    """Stop. Actively chosen, with a reason — not a fallthrough."""


@dataclass(frozen=True)
class Play:
    """What to do for one class of failure, and why."""

    action: Action
    delay_days: int
    """0 = act now. >0 = wait this many days."""

    align_to_payday: bool = False
    """If true, the delay is a floor and the real date is pushed to the
    customer's next payday. Timing beats frequency for money problems."""

    max_attempts: int = 3
    """Playbook's own suggested ceiling. The policy engine enforces the
    real one, which may be lower."""

    rationale: str = ""


# --------------------------------------------------------------------------
# The decision table.
#
# Ordered by how confident we are. The first four are near-certain; the
# ambiguous case is the only one that genuinely needs a model.
# --------------------------------------------------------------------------

PLAYBOOK: dict[FailureClass, Play] = {
    FailureClass.TRANSIENT_SYSTEM: Play(
        action=Action.RETRY_NOW,
        delay_days=0,
        max_attempts=3,
        rationale=(
            "A machine was down. Outages are short. Waiting a full day wastes "
            "the window in which a retry is most likely to succeed."
        ),
    ),
    FailureClass.TIMING: Play(
        action=Action.RETRY_SCHEDULED,
        delay_days=1,
        align_to_payday=True,
        max_attempts=3,
        rationale=(
            "The customer is good for the money but not today. Retrying "
            "tomorrow mostly fails; retrying just after payday mostly works. "
            "This is the single biggest lever in the whole system."
        ),
    ),
    FailureClass.PRESENT_FRICTION: Play(
        action=Action.REPROMPT,
        delay_days=0,
        max_attempts=2,
        rationale=(
            "The customer was actively trying to pay minutes ago. Intent is "
            "at its peak right now and decays fast. A silent retry throws "
            "that away — ask them to finish instead."
        ),
    ),
    FailureClass.CUSTOMER_ACTION_REQUIRED: Play(
        action=Action.NUDGE_FIX_INSTRUMENT,
        delay_days=0,
        max_attempts=2,
        rationale=(
            "The instrument physically cannot work until the customer acts. "
            "Every charge attempt is guaranteed to fail and costs a fee. "
            "Only a nudge can change the outcome."
        ),
    ),
    FailureClass.RISK_BLOCKED: Play(
        action=Action.OFFER_ALTERNATE_METHOD,
        delay_days=0,
        max_attempts=1,
        rationale=(
            "The issuer flagged this. Repeated attempts lower issuer trust "
            "for the merchant's whole account, quietly reducing success "
            "rates for unrelated customers. The cost is invisible and real."
        ),
    ),
    FailureClass.INTENT_NEGATIVE: Play(
        action=Action.ABANDON,
        delay_days=0,
        max_attempts=0,
        rationale=(
            "The customer chose to stop. This is a signal, not an obstacle. "
            "Chasing converts a soft no into a permanent one."
        ),
    ),
    FailureClass.AMBIGUOUS: Play(
        action=Action.RETRY_SCHEDULED,
        delay_days=2,
        max_attempts=2,
        rationale=(
            "The bank declined without saying why. This is the only class "
            "where a lookup genuinely cannot decide — it needs the customer's "
            "history. The rule tier gives a conservative default; the "
            "investigator model overrides it when it has evidence."
        ),
    ),
}


def play_for(failure_class: FailureClass) -> Play:
    return PLAYBOOK[failure_class]


def next_payday(day_of_month: int, payday: int) -> int:
    """Days from `day_of_month` until the customer's next payday.

    Salary lands on a fixed date for most Indian salaried customers, so this
    is a calendar question, not a prediction. Simplified to a 30-day month;
    the real implementation would use the actual calendar.
    """
    if payday > day_of_month:
        return payday - day_of_month
    return (30 - day_of_month) + payday
