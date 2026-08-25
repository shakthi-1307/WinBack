"""
Recovery strategies: three baselines and the rule tier of the real agent.

A strategy answers one question, repeatedly:

    Given everything that has happened to this transaction so far,
    what should we do next — and when?

Returning None means "stop". Stopping is a decision, and the strategies that
can't make it are exactly the ones we expect to lose money.
"""

from __future__ import annotations

from typing import Protocol

from core.domain.models import Channel, Customer, FailedPayment, Trace
from core.domain.playbook import Action, next_payday, play_for
from core.domain.reason_codes import FailureClass, classify
from core.policy.engine import PlannedAction


class Strategy(Protocol):
    name: str

    def plan(
        self, payment: FailedPayment, customer: Customer, trace: Trace, day: int
    ) -> PlannedAction | None: ...


def _charges_so_far(trace: Trace) -> int:
    return sum(1 for a in trace.attempts if a.is_charge)


def _contacts_so_far(trace: Trace) -> int:
    return sum(1 for a in trace.attempts if a.contacted_customer)


# --------------------------------------------------------------------------
# Baseline 1 — do nothing.
#
# The floor. Everything else has to be worth more than this, and it is not a
# joke: the merchant loses nothing to fees, annoys nobody, and damages no
# issuer relationships. A recovery strategy that barely beats this one is
# not obviously worth running.
# --------------------------------------------------------------------------
class DoNothing:
    name = "do_nothing"

    def plan(self, payment, customer, trace, day):
        return None


# --------------------------------------------------------------------------
# Baseline 2 — retry three times, immediately.
#
# The most common real-world behaviour. Ignores the reason code entirely and
# assumes that trying harder and sooner is trying better.
# --------------------------------------------------------------------------
class RetryThriceImmediate:
    name = "retry_x3_immediate"
    SCHEDULE = [0, 1, 2]

    def plan(self, payment, customer, trace, day):
        n = _charges_so_far(trace)
        if n >= len(self.SCHEDULE):
            return None
        return PlannedAction(
            action=Action.RETRY_NOW if n == 0 else Action.RETRY_SCHEDULED,
            day=self.SCHEDULE[n],
            amount_paise=payment.amount_paise,
            rationale="Fixed aggressive retry schedule; reason code ignored.",
        )


# --------------------------------------------------------------------------
# Baseline 3 — fixed schedule, days 1 / 3 / 5.
#
# The "sophisticated" version most dunning tools ship. Spacing attempts out
# is a genuine improvement over hammering, but it still applies one schedule
# to every kind of failure.
# --------------------------------------------------------------------------
class FixedSchedule:
    name = "fixed_d1_d3_d5"
    SCHEDULE = [1, 3, 5]

    def plan(self, payment, customer, trace, day):
        n = _charges_so_far(trace)
        if n >= len(self.SCHEDULE):
            return None
        return PlannedAction(
            action=Action.RETRY_SCHEDULED,
            day=self.SCHEDULE[n],
            amount_paise=payment.amount_paise,
            rationale="Fixed spaced retry schedule; reason code ignored.",
        )


# --------------------------------------------------------------------------
# Winback, rule tier.
#
# Reads the reason code, looks up the playbook, and picks both the action
# and the timing. This is the deterministic two-thirds of the real agent —
# no model is involved. The LLM tiers add robustness on triage and judgement
# on the ambiguous class; they do not replace this.
# --------------------------------------------------------------------------
class WinbackRules:
    name = "winback_rules"

    def plan(self, payment, customer, trace, day):
        rc = classify(payment.reason_code)
        play = play_for(rc.failure_class)

        # Some failures are worth nothing at all. Say so explicitly rather
        # than quietly running out of attempts.
        if play.action == Action.ABANDON:
            return None

        # A dead mandate means no charge is possible, ever. Fall back to
        # asking the customer to re-authorise rather than burning attempts
        # against a closed door.
        if not payment.mandate_valid:
            if _contacts_so_far(trace) >= 1:
                return None
            return PlannedAction(
                action=Action.NUDGE_FIX_INSTRUMENT,
                day=0,
                hour=11,
                channel=self._channel_for(customer),
                amount_paise=payment.amount_paise,
                rationale="Mandate is dead. Only re-authorisation can fix this.",
            )

        used = (
            _charges_so_far(trace)
            if play.action in {Action.RETRY_NOW, Action.RETRY_SCHEDULED}
            else _contacts_so_far(trace)
        )
        if used >= play.max_attempts:
            return None

        action = play.action
        target_day = self._timing(payment, customer, play, used)
        if target_day is None:
            return None

        # Escalate: if the playbook's first move has already been tried and
        # failed, switching rail beats repeating yourself.
        if used >= 1 and rc.failure_class in {
            FailureClass.PRESENT_FRICTION,
            FailureClass.AMBIGUOUS,
        }:
            action = Action.OFFER_ALTERNATE_METHOD

        contacts = action in {
            Action.REPROMPT,
            Action.NUDGE_FIX_INSTRUMENT,
            Action.OFFER_ALTERNATE_METHOD,
        }

        return PlannedAction(
            action=action,
            day=target_day,
            hour=11,
            channel=self._channel_for(customer) if contacts else None,
            amount_paise=payment.amount_paise,
            rationale=play.rationale,
        )

    # -- timing ---------------------------------------------------------

    def _timing(self, payment, customer, play, used: int) -> int | None:
        """Where the money is actually made.

        For timing failures the target is the customer's payday, not a fixed
        offset. For everything else, a widening gap between attempts.
        """
        if play.align_to_payday:
            days_to_pay = next_payday(payment.failed_on_day, customer.payday)
            # Land just after the salary clears, not on the day itself.
            target = days_to_pay + 1 + (used * 7)
            return target if target <= 21 else None

        base = play.delay_days
        target = base + used * (2 if base == 0 else 3)
        return target if target <= 21 else None

    def _channel_for(self, customer: Customer) -> Channel:
        # DND-registered customers can still be emailed. Choosing email for
        # them here means the policy engine approves rather than blocks —
        # a strategy that anticipates the rules instead of colliding with them.
        if customer.dnd:
            return Channel.EMAIL
        return customer.preferred_channel


# --------------------------------------------------------------------------
# Winback, full agent.
#
# Identical to the rule tier everywhere the reason code is unambiguous —
# which is most of the batch. Where the bank declined without saying why, it
# calls the investigator instead of falling back to a conservative guess.
#
# The model therefore touches roughly a fifth of transactions, and on those
# it may choose one of exactly three actions. Everything else — amounts,
# caps, hours, cooldowns — remains beyond its reach.
# --------------------------------------------------------------------------
class WinbackAgent(WinbackRules):
    name = "winback_agent"

    def __init__(self, client=None) -> None:
        from core.agents.llm import default_client

        self.client = client or default_client()
        self._triage_cache: dict[str, object] = {}
        self.telemetry = {
            "table_decisions": 0,
            "model_decisions": 0,
            "hostile_notes_seen": 0,
            "output_rejections": 0,
            "investigations": 0,
        }

    def _triage(self, payment: FailedPayment, customer: Customer):
        from core.agents.triage import triage

        if payment.id not in self._triage_cache:
            result = triage(payment, customer, self.client)
            self._triage_cache[payment.id] = result
            self.telemetry[
                "model_decisions" if result.authority == "model" else "table_decisions"
            ] += 1
            if result.hostile_note:
                self.telemetry["hostile_notes_seen"] += 1
            if result.output_rejected:
                self.telemetry["output_rejections"] += 1
        return self._triage_cache[payment.id]

    def plan(self, payment: FailedPayment, customer: Customer, trace: Trace, day: int):
        from core.agents.investigator import investigate

        t = self._triage(payment, customer)

        # Anything the table settled is handled exactly as before. No model,
        # no cost, no attack surface.
        if t.failure_class is not FailureClass.AMBIGUOUS:
            return super().plan(payment, customer, trace, day)

        if not payment.mandate_valid:
            return super().plan(payment, customer, trace, day)

        attempts = len(trace.attempts)
        if attempts >= 2:
            return None

        j = investigate(payment, customer, self.client, attempt_number=attempts + 1)
        self.telemetry["investigations"] += 1
        if j.output_rejected:
            self.telemetry["output_rejections"] += 1

        if j.action == Action.ABANDON.value:
            return None

        action = Action(j.action)
        target = day + j.delay_days if attempts else j.delay_days
        if target > 21:
            return None

        contacts = action is Action.OFFER_ALTERNATE_METHOD
        return PlannedAction(
            action=action,
            day=target,
            hour=11,
            channel=self._channel_for(customer) if contacts else None,
            amount_paise=payment.amount_paise,  # never model-controlled
            rationale=f"[investigator] {j.rationale}",
        )


ALL_STRATEGIES: list[Strategy] = [
    DoNothing(),
    RetryThriceImmediate(),
    FixedSchedule(),
    WinbackRules(),
    WinbackAgent(),
]
