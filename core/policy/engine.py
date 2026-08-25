"""
The policy engine — the limits.

This module contains no model, no prompt and no judgement. It is a checklist.
It receives a proposed action and answers APPROVED or DENIED against fixed
rules, and it cannot be reasoned with.

That is the entire point. The triage and policy agents are language models,
and language models can be persuaded — by a hostile support note, by an
unusual phrasing, by their own confident reasoning. Anything that can be
persuaded is not a limit.

Every denial here happens BEFORE the executor runs, so a denied action costs
zero API calls and zero rupees.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.domain.models import Channel, Customer, FailedPayment
from core.domain.playbook import Action

CHARGE_ACTIONS = {Action.RETRY_NOW, Action.RETRY_SCHEDULED}
CONTACT_ACTIONS = {
    Action.REPROMPT,
    Action.NUDGE_FIX_INSTRUMENT,
    Action.OFFER_ALTERNATE_METHOD,
}


@dataclass(frozen=True)
class Limits:
    max_charge_attempts: int = 3
    max_contacts: int = 3
    min_days_between_charges: int = 1
    quiet_hours_start: int = 21
    quiet_hours_end: int = 9
    max_recovery_window_days: int = 21
    # DND registration covers calls and SMS. Email is not in scope of DND,
    # so it stays available — a real distinction, not a loophole.
    dnd_blocked_channels: frozenset = frozenset({Channel.SMS, Channel.VOICE, Channel.WHATSAPP})


@dataclass
class AttemptState:
    """What has already happened to this transaction."""

    charges_used: int = 0
    contacts_used: int = 0
    last_charge_day: int | None = None
    days_elapsed: int = 0
    amount_paise_snapshot: int = 0


@dataclass
class PlannedAction:
    action: Action
    day: int
    """Days since the original failure."""
    hour: int = 10
    channel: Channel | None = None
    amount_paise: int = 0
    rationale: str = ""


@dataclass
class Verdict:
    approved: bool
    rule: str = ""
    reason: str = ""


@dataclass
class PolicyEngine:
    limits: Limits = field(default_factory=Limits)

    def check(
        self,
        plan: PlannedAction,
        payment: FailedPayment,
        customer: Customer,
        state: AttemptState,
    ) -> Verdict:
        """Approve or deny one proposed action. Order matters: the cheapest
        and most absolute checks run first."""

        is_charge = plan.action in CHARGE_ACTIONS
        is_contact = plan.action in CONTACT_ACTIONS

        # --- absolute prohibitions ---------------------------------------

        if is_charge and not payment.mandate_valid:
            return Verdict(
                False,
                "MANDATE_INVALID",
                "The customer's payment permission has expired or been revoked. "
                "No charge may be attempted at all.",
            )

        if is_charge and plan.amount_paise != state.amount_paise_snapshot:
            return Verdict(
                False,
                "AMOUNT_TAMPERED",
                f"Attempted to charge {plan.amount_paise} against a snapshot of "
                f"{state.amount_paise_snapshot}. The amount is fixed at failure.",
            )

        if plan.day > self.limits.max_recovery_window_days:
            return Verdict(
                False,
                "WINDOW_EXPIRED",
                f"Day {plan.day} is past the {self.limits.max_recovery_window_days}-day "
                "recovery window. Continuing to chase costs more than it returns.",
            )

        # --- counting limits ---------------------------------------------

        if is_charge and state.charges_used >= self.limits.max_charge_attempts:
            return Verdict(
                False,
                "CHARGE_CAP",
                f"Already used {state.charges_used} of "
                f"{self.limits.max_charge_attempts} permitted charge attempts.",
            )

        if is_contact and state.contacts_used >= self.limits.max_contacts:
            return Verdict(
                False,
                "CONTACT_CAP",
                f"Already sent {state.contacts_used} of {self.limits.max_contacts} "
                "permitted messages.",
            )

        if (
            is_charge
            and state.last_charge_day is not None
            and plan.day - state.last_charge_day < self.limits.min_days_between_charges
        ):
            return Verdict(
                False,
                "COOLDOWN",
                f"Last charge was on day {state.last_charge_day}. Minimum gap is "
                f"{self.limits.min_days_between_charges} day(s).",
            )

        # --- contact rules ------------------------------------------------

        if is_contact:
            if customer.dnd and plan.channel in self.limits.dnd_blocked_channels:
                return Verdict(
                    False,
                    "DND",
                    f"Customer is DND-registered; {plan.channel} is not permitted. "
                    "Email remains available.",
                )

            if plan.hour >= self.limits.quiet_hours_start or plan.hour < self.limits.quiet_hours_end:
                return Verdict(
                    False,
                    "QUIET_HOURS",
                    f"Hour {plan.hour:02d}:00 falls inside quiet hours "
                    f"({self.limits.quiet_hours_start}:00–{self.limits.quiet_hours_end}:00).",
                )

        return Verdict(True)
