"""Shared value types. Plain dataclasses — no ORM, no framework coupling."""

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
    """Day of month the salary lands."""
    dnd: bool
    """Registered do-not-disturb. Not a preference to weigh against revenue."""
    preferred_channel: Channel
    tenure_months: int
    prior_failures: int
    """Historical failures. Evidence for the investigator on ambiguous declines."""


@dataclass
class FailedPayment:
    id: str
    customer_id: str
    amount_paise: int
    reason_code: str
    failed_on_day: int
    mandate_valid: bool
    """False if the e-mandate expired or was revoked. No charge is permitted."""
    support_note: str = ""
    """Free text on the account. UNTRUSTED — one of two injection surfaces."""

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
