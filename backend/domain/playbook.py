"""The playbook: what is SMART to do for each kind of failure.

Advice, not permission. The playbook says what tends to work; the policy
engine says what is allowed. Nothing in this file enforces anything.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.domain.actions import Action
from backend.domain.failure_classes import FailureClass


@dataclass(frozen=True)
class Play:
    action: Action
    delay_days: int
    align_to_payday: bool = False
    """If true the delay is a floor, and the real date is pushed to the
    customer's next payday. Timing beats frequency for money problems."""
    max_attempts: int = 3
    rationale: str = ""


PLAYBOOK: dict[FailureClass, Play] = {
    FailureClass.TRANSIENT_SYSTEM: Play(
        Action.RETRY_NOW, 0, max_attempts=3,
        rationale=("A machine was down. Outages are short. Waiting a full day "
                   "wastes the window in which a retry is most likely to work."),
    ),
    FailureClass.TIMING: Play(
        Action.RETRY_SCHEDULED, 1, align_to_payday=True, max_attempts=3,
        rationale=("The customer is good for the money but not today. Retrying "
                   "tomorrow mostly fails; retrying just after payday mostly works. "
                   "This is the single biggest lever in the system."),
    ),
    FailureClass.PRESENT_FRICTION: Play(
        Action.REPROMPT, 0, max_attempts=2,
        rationale=("The customer was actively paying minutes ago. Intent peaks now "
                   "and decays fast. A silent retry throws that away."),
    ),
    FailureClass.CUSTOMER_ACTION_REQUIRED: Play(
        Action.NUDGE_FIX_INSTRUMENT, 0, max_attempts=2,
        rationale=("The instrument cannot work until the customer acts. Every "
                   "charge attempt is guaranteed to fail and costs a fee."),
    ),
    FailureClass.RISK_BLOCKED: Play(
        Action.OFFER_ALTERNATE_METHOD, 0, max_attempts=1,
        rationale=("The issuer flagged this. Repeated attempts lower issuer trust "
                   "for the whole merchant account, quietly reducing success rates "
                   "for unrelated customers."),
    ),
    FailureClass.INTENT_NEGATIVE: Play(
        Action.ABANDON, 0, max_attempts=0,
        rationale=("The customer chose to stop. Chasing converts a soft no into a "
                   "permanent one."),
    ),
    FailureClass.AMBIGUOUS: Play(
        Action.RETRY_SCHEDULED, 2, max_attempts=2,
        rationale=("The bank declined without saying why. The only class where a "
                   "lookup genuinely cannot decide — it needs customer history."),
    ),
}


def play_for(failure_class: FailureClass) -> Play:
    return PLAYBOOK[failure_class]
