"""Turning domain objects into JSON the console can render. No logic."""

from __future__ import annotations

from backend.domain.classification import classify
from backend.domain.models import Customer, FailedPayment, Trace


def transaction_row(payment: FailedPayment, customer: Customer,
                    trace: Trace) -> dict:
    last = trace.attempts[-1] if trace.attempts else None
    if trace.recovered:
        status = "recovered"
    elif trace.blocks:
        status = "blocked"
    elif trace.abandoned_on_day is not None:
        status = "abandoned"
    elif trace.attempts:
        status = "in_flight"
    else:
        status = "pending"

    return {
        "id": payment.id,
        "customer_id": payment.customer_id,
        "amount_rupees": payment.amount_rupees,
        "reason_code": payment.reason_code,
        "failure_class": classify(payment.reason_code).failure_class.value,
        "mandate_valid": payment.mandate_valid,
        "dnd": customer.dnd,
        "payday": customer.payday,
        "status": status,
        "attempts": len(trace.attempts),
        "charges": sum(1 for a in trace.attempts if a.is_charge),
        "contacts": sum(1 for a in trace.attempts if a.contacted_customer),
        "last_action": last.action if last else None,
        "recovered_on_day": trace.recovered_on_day,
        "abandon_reason": trace.abandon_reason,
    }


def timeline_event(event: dict) -> dict:
    from backend.ledger.replay import describe

    return {
        "seq": event["seq"],
        "day": event["day"],
        "type": event["type"],
        "text": describe(event),
    }
