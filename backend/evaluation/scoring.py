"""Turning traces into a Result. Counting only, no formatting."""

from __future__ import annotations

from backend.domain.models import FailedPayment, Trace
from backend.evaluation.result import Result


def score(strategy_name: str, payments: list[FailedPayment],
          traces: dict[str, Trace]) -> Result:
    result = Result(strategy=strategy_name)
    contacted: set[str] = set()

    for payment in payments:
        trace = traces[payment.id]
        result.n += 1
        result.at_risk_paise += payment.amount_paise

        if trace.recovered:
            result.recovered_count += 1
            result.recovered_paise += payment.amount_paise
            if trace.recovered_on_day is not None:
                result.days_to_recovery.append(trace.recovered_on_day)
        if trace.abandoned_on_day is not None:
            result.abandoned += 1

        for attempt in trace.attempts:
            if attempt.is_charge:
                result.charge_attempts += 1
                if attempt.probability == 0.0:
                    result.impossible_charges += 1
                if attempt.damaged_issuer_trust:
                    result.issuer_trust_damage += 1
            if attempt.contacted_customer:
                result.contacts += 1
                contacted.add(payment.customer_id)
                if not trace.recovered:
                    result.wasted_contacts += 1

        for block in trace.blocks:
            rule = block.split(":", 1)[0]
            result.blocks[rule] = result.blocks.get(rule, 0) + 1

    result.customers_contacted = len(contacted)
    return result
