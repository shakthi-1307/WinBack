"""Winback, full agent — the rule tier plus a model for the gray zone.

Identical to the rule tier everywhere the reason code is unambiguous, which
is most of the batch. Where the bank declined without saying why, it calls
the investigator instead of falling back to a conservative guess.

The model therefore touches roughly a fifth of transactions, and on those it
may choose one of exactly three actions. Amounts, caps, hours and cooldowns
remain beyond its reach.
"""

from __future__ import annotations

from backend.agents.investigator_agent import investigate
from backend.agents.triage_agent import TriageResult, triage
from backend.domain.actions import Action
from backend.domain.failure_classes import FailureClass
from backend.domain.models import Customer, FailedPayment, Trace
from backend.llm.base import LLMClient
from backend.llm.factory import default_client
from backend.policy.plan import PlannedAction
from backend.strategies.winback_rules import CONTACT_HOUR, MAX_DAY, WinbackRules

MAX_INVESTIGATIONS_PER_TXN = 2


class WinbackAgent(WinbackRules):
    name = "winback_agent"

    def __init__(self, client: LLMClient | None = None) -> None:
        self.client = client or default_client()
        self._triage_cache: dict[str, TriageResult] = {}
        self.telemetry = {
            "table_decisions": 0,
            "model_decisions": 0,
            "hostile_notes_seen": 0,
            "output_rejections": 0,
            "investigations": 0,
        }

    def triage_for(self, payment: FailedPayment, customer: Customer) -> TriageResult:
        """Cached: a transaction is triaged once, however many times it is
        replanned. Re-asking would multiply cost for no new information."""
        if payment.id not in self._triage_cache:
            result = triage(payment, customer, self.client)
            self._triage_cache[payment.id] = result
            key = "model_decisions" if result.authority == "model" else "table_decisions"
            self.telemetry[key] += 1
            if result.hostile_note:
                self.telemetry["hostile_notes_seen"] += 1
            if result.output_rejected:
                self.telemetry["output_rejections"] += 1
        return self._triage_cache[payment.id]

    def plan(self, payment: FailedPayment, customer: Customer,
             trace: Trace, day: int) -> PlannedAction | None:
        result = self.triage_for(payment, customer)

        # Anything the table settled is handled exactly as the rule tier
        # would. No model, no cost, no attack surface.
        if result.failure_class is not FailureClass.AMBIGUOUS:
            return super().plan(payment, customer, trace, day)

        if not payment.mandate_valid:
            return super().plan(payment, customer, trace, day)

        attempts = len(trace.attempts)
        if attempts >= MAX_INVESTIGATIONS_PER_TXN:
            return None

        judgement = investigate(payment, customer, self.client,
                                attempt_number=attempts + 1)
        self.telemetry["investigations"] += 1
        if judgement.output_rejected:
            self.telemetry["output_rejections"] += 1

        if judgement.action == Action.ABANDON.value:
            return None

        action = Action(judgement.action)
        target = day + judgement.delay_days if attempts else judgement.delay_days
        if target > MAX_DAY:
            return None

        contacts = action is Action.OFFER_ALTERNATE_METHOD
        return PlannedAction(
            action=action,
            day=target,
            hour=CONTACT_HOUR,
            channel=self.channel_for(customer) if contacts else None,
            amount_paise=payment.amount_paise,  # never model-controlled
            rationale=f"[investigator] {judgement.rationale}",
        )
