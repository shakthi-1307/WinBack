"""The policy engine — runs the rules and returns a verdict. Nothing else.

It contains no model, no prompt and no judgement. It is a checklist, and it
cannot be reasoned with. That is the entire point: the triage and policy
agents are language models, and anything that can be persuaded is not a limit.

Every denial happens BEFORE the executor runs, so a denied action costs zero
API calls and zero rupees. The engine has no network client and no side
effects — a denial cannot already have cost the merchant a gateway fee.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.domain.models import Customer, FailedPayment
from backend.policy.limits import AttemptState, Limits
from backend.policy.plan import PlannedAction, Verdict
from backend.policy.rules import ALL_RULES, Rule


@dataclass
class PolicyEngine:
    limits: Limits = field(default_factory=Limits)
    rules: list[Rule] = field(default_factory=lambda: list(ALL_RULES))

    def check(self, plan: PlannedAction, payment: FailedPayment,
              customer: Customer, state: AttemptState) -> Verdict:
        for rule in self.rules:
            verdict = rule(plan, payment, customer, state, self.limits)
            if verdict is not None:
                return verdict
        return Verdict(True)
