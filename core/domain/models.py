"""Shared types. Deliberately plain — no ORM, no framework coupling."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Channel(str, Enum):
    SMS = "sms"
    WHATSAPP = "whatsapp"
    EMAIL = "email"
    VOICE = "voice"


@dataclass
class Customer:
    id: str
    payday: int
    """Day of month the customer's salary lands. A calendar fact, not a
    prediction — most Indian salaried customers are paid on a fixed date."""

    dnd: bool
    """Registered do-not-disturb. Contacting them is not a judgement call."""

    preferred_channel: Channel
    tenure_months: int
    prior_failures: int
    """How many payments this customer has already failed historically.
    A signal the investigator uses on ambiguous declines."""


@dataclass
class FailedPayment:
    id: str
    customer_id: str
    amount_paise: int
    reason_code: str
    failed_on_day: int
    """Day of month the original charge failed."""

    mandate_valid: bool
    """False if the e-mandate has expired or been revoked. No charge may be
    attempted at all in that case."""

    support_note: str = ""
    """Free text attached to the account. UNTRUSTED — this is one of the two
    injection surfaces the attack suite targets."""

    @property
    def amount_rupees(self) -> float:
        return self.amount_paise / 100


@dataclass
class Attempt:
    txn_id: str
    attempt_index: int
    day: int
    action: str
    success: bool
    probability: float
    is_charge: bool
    contacted_customer: bool
    damaged_issuer_trust: bool = False
    reason: str = ""


@dataclass
class Trace:
    """Everything that happened to one transaction, in order."""

    txn_id: str
    attempts: list[Attempt] = field(default_factory=list)
    recovered: bool = False
    recovered_on_day: int | None = None
    abandoned_on_day: int | None = None
    abandon_reason: str = ""
    blocks: list[str] = field(default_factory=list)
