"""The catalogue of Razorpay failure reason codes.

Data only. Every code and its source come from Razorpay's published card
error documentation. The `failure_class` on each is our own judgement and is
the central claim of this project.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.domain.failure_classes import FailureClass, Source


@dataclass(frozen=True)
class ReasonCode:
    code: str
    source: Source
    failure_class: FailureClass
    plain_english: str
    razorpay_says_retryable: bool
    """What Razorpay's own docs say. Kept so the places where this system
    deliberately disagrees are visible rather than implied."""


_CATALOGUE = [
    ReasonCode("gateway_technical_error", Source.RAZORPAY, FailureClass.TRANSIENT_SYSTEM,
               "Partner bank or routing failure on Razorpay's side.", True),
    ReasonCode("bank_technical_error", Source.ISSUER, FailureClass.TRANSIENT_SYSTEM,
               "The customer's own bank was down.", True),
    ReasonCode("insufficient_funds", Source.ISSUER, FailureClass.TIMING,
               "Not enough money in the account at that moment.", True),
    ReasonCode("transaction_limit_exceeded", Source.ISSUER, FailureClass.TIMING,
               "The card's daily transaction cap was already reached.", True),
    ReasonCode("card_expired", Source.ISSUER, FailureClass.CUSTOMER_ACTION_REQUIRED,
               "The card is past its expiry date.", False),
    ReasonCode("card_not_enrolled", Source.ISSUER, FailureClass.CUSTOMER_ACTION_REQUIRED,
               "Card is not activated for online transactions.", True),
    ReasonCode("debit_instrument_inactive", Source.ISSUER, FailureClass.CUSTOMER_ACTION_REQUIRED,
               "Card is not enabled for online use.", True),
    ReasonCode("card_disabled_for_online_payments", Source.ISSUER,
               FailureClass.CUSTOMER_ACTION_REQUIRED,
               "Online transactions are switched off for this card.", True),
    ReasonCode("debit_instrument_blocked", Source.ISSUER, FailureClass.CUSTOMER_ACTION_REQUIRED,
               "The card is blocked by the bank or the customer.", True),
    ReasonCode("payment_timed_out", Source.RAZORPAY, FailureClass.PRESENT_FRICTION,
               "The customer exceeded the ~10 minute payment window.", True),
    ReasonCode("authentication_failed", Source.ISSUER, FailureClass.PRESENT_FRICTION,
               "Wrong OTP, or the browser was closed during verification.", True),
    ReasonCode("incorrect_cvv", Source.CUSTOMER, FailureClass.PRESENT_FRICTION,
               "The customer mistyped the CVV.", True),
    ReasonCode("payment_cancelled", Source.CUSTOMER, FailureClass.INTENT_NEGATIVE,
               "The customer deliberately cancelled or pressed back.", True),
    ReasonCode("payment_risk_check_failed", Source.ISSUER, FailureClass.RISK_BLOCKED,
               "The issuing bank flagged the transaction as risky.", True),
    ReasonCode("card_declined", Source.ISSUER, FailureClass.AMBIGUOUS,
               "Declined by the bank, with no reason given.", True),
    ReasonCode("payment_failed", Source.ISSUER, FailureClass.AMBIGUOUS,
               "Declined by the bank, with no reason given.", True),
]

REASON_CODES: dict[str, ReasonCode] = {rc.code: rc for rc in _CATALOGUE}
