"""Winback, rule tier — the deterministic two-thirds of the real agent.

Reads the reason code, looks up the playbook, and picks both the action and
the timing. No model is involved anywhere in this file.

Most of Winback's advantage lives here rather than in the model. The model
adds robustness on triage and judgement on ambiguous declines; it does not
replace this.
"""

from __future__ import annotations

from backend.domain.actions import CONTACT_ACTIONS, Action
from backend.domain.calendar import days_until_payday
from backend.domain.classification import classify
from backend.domain.failure_classes import FailureClass
from backend.domain.models import Channel, Customer, FailedPayment, Trace
from backend.domain.playbook import Play, play_for
from backend.policy.plan import PlannedAction
from backend.strategies.base import charges_so_far, contacts_so_far

MAX_DAY = 21
CONTACT_HOUR = 11
ESCALATE_AFTER_ATTEMPTS = 1


class WinbackRules:
    name = "winback_rules"

    def plan(self, payment: FailedPayment, customer: Customer,
             trace: Trace, day: int) -> PlannedAction | None:
        reason = classify(payment.reason_code)
        play = play_for(reason.failure_class)

        # Some failures are worth nothing at all. Say so explicitly rather
        # than quietly running out of attempts.
        if play.action is Action.ABANDON:
            return None

        if not payment.mandate_valid:
            return self._reauthorise(payment, customer, trace)

        used = self._attempts_used(trace, play)
        if used >= play.max_attempts:
            return None

        target_day = self._timing(payment, customer, play, used)
        if target_day is None:
            return None

        action = self._escalate(play.action, reason.failure_class, used)
        contacts = action in CONTACT_ACTIONS

        return PlannedAction(
            action=action,
            day=target_day,
            hour=CONTACT_HOUR,
            channel=self.channel_for(customer) if contacts else None,
            amount_paise=payment.amount_paise,
            rationale=play.rationale,
        )

    # -- pieces ------------------------------------------------------

    def _reauthorise(self, payment, customer, trace) -> PlannedAction | None:
        """A dead mandate means no charge is possible, ever. Ask the customer
        to re-authorise rather than burning attempts on a closed door."""
        if contacts_so_far(trace) >= 1:
            return None
        return PlannedAction(
            action=Action.NUDGE_FIX_INSTRUMENT,
            day=0,
            hour=CONTACT_HOUR,
            channel=self.channel_for(customer),
            amount_paise=payment.amount_paise,
            rationale="Mandate is dead. Only re-authorisation can fix this.",
        )

    def _attempts_used(self, trace: Trace, play: Play) -> int:
        if play.action in {Action.RETRY_NOW, Action.RETRY_SCHEDULED}:
            return charges_so_far(trace)
        return contacts_so_far(trace)

    def _escalate(self, action: Action, failure_class: FailureClass,
                  used: int) -> Action:
        """If the playbook's first move already failed, switching rail beats
        repeating yourself."""
        if used >= ESCALATE_AFTER_ATTEMPTS and failure_class in {
            FailureClass.PRESENT_FRICTION, FailureClass.AMBIGUOUS
        }:
            return Action.OFFER_ALTERNATE_METHOD
        return action

    def _timing(self, payment: FailedPayment, customer: Customer,
                play: Play, used: int) -> int | None:
        """Where the money is actually made.

        For timing failures the target is the customer's payday, not a fixed
        offset. For everything else, a widening gap between attempts.
        """
        if play.align_to_payday:
            to_payday = days_until_payday(payment.failed_on_day, customer.payday)
            target = to_payday + 1 + (used * 7)
        else:
            base = play.delay_days
            target = base + used * (2 if base == 0 else 3)
        return target if target <= MAX_DAY else None

    def channel_for(self, customer: Customer) -> Channel:
        """DND-registered customers can still be emailed. Choosing email for
        them means the policy engine approves rather than blocks — a strategy
        that anticipates the rules instead of colliding with them."""
        return Channel.EMAIL if customer.dnd else customer.preferred_channel
