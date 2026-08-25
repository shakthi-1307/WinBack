"""Shared subjects for the attack suite."""

from __future__ import annotations

from backend.domain.models import Channel, Customer, FailedPayment

SNAPSHOT_PAISE = 149900


def customer(dnd: bool = False) -> Customer:
    return Customer(id="cust_attack", payday=1, dnd=dnd,
                    preferred_channel=Channel.SMS, tenure_months=12,
                    prior_failures=0)


def payment(note: str = "", code: str = "card_declined",
            mandate: bool = True) -> FailedPayment:
    return FailedPayment(id="txn_attack", customer_id="cust_attack",
                         amount_paise=SNAPSHOT_PAISE, reason_code=code,
                         failed_on_day=10, mandate_valid=mandate,
                         support_note=note)
