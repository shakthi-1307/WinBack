"""
Razorpay payment failure reason codes, and what kind of problem each one is.

Every code here comes from Razorpay's published card error documentation.
The `FailureClass` assigned to each is our own judgement — it is the core
claim of this project and is defended in docs/playbook.md.

The distinction that matters:

    Razorpay's docs answer "can this be retried?"  (almost always: yes)
    This module answers    "what KIND of problem is this?"

Those are different questions, and conflating them is why naive retry
schedules waste money.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FailureClass(str, Enum):
    """What kind of problem the failure actually represents."""

    TRANSIENT_SYSTEM = "transient_system"
    """Nobody's fault. A machine was down. Retrying soon usually works."""

    TIMING = "timing"
    """The customer is good for the money, just not at this moment.
    Recovery depends almost entirely on WHEN you try again."""

    CUSTOMER_ACTION_REQUIRED = "customer_action_required"
    """The instrument cannot work until the customer does something.
    Retrying is guaranteed to fail. Only a nudge can change the outcome."""

    PRESENT_FRICTION = "present_friction"
    """The customer was actively trying to pay and something got in the way.
    Intent is high and fresh. Re-prompting quickly is the strongest move."""

    INTENT_NEGATIVE = "intent_negative"
    """The customer deliberately backed out. Pressure here is
    counterproductive and damages the relationship."""

    RISK_BLOCKED = "risk_blocked"
    """The issuer flagged the transaction. Repeated attempts degrade issuer
    trust for the merchant's ENTIRE account, harming unrelated customers."""

    AMBIGUOUS = "ambiguous"
    """The bank declined and told us nothing useful. Requires investigation
    against customer history rather than a lookup."""


class Source(str, Enum):
    ISSUER = "issuer"
    RAZORPAY = "razorpay"
    CUSTOMER = "customer"


@dataclass(frozen=True)
class ReasonCode:
    code: str
    source: Source
    failure_class: FailureClass
    plain_english: str
    razorpay_says_retryable: bool
    """What Razorpay's own docs say. Kept so we can show, explicitly, where
    our system disagrees with a naive reading of the documentation."""


# --------------------------------------------------------------------------
# The catalogue. Source: Razorpay card error documentation.
# --------------------------------------------------------------------------

REASON_CODES: dict[str, ReasonCode] = {
    rc.code: rc
    for rc in [
        ReasonCode(
            "gateway_technical_error",
            Source.RAZORPAY,
            FailureClass.TRANSIENT_SYSTEM,
            "Partner bank or routing failure on Razorpay's side.",
            razorpay_says_retryable=True,
        ),
        ReasonCode(
            "bank_technical_error",
            Source.ISSUER,
            FailureClass.TRANSIENT_SYSTEM,
            "The customer's own bank was down.",
            razorpay_says_retryable=True,
        ),
        ReasonCode(
            "insufficient_funds",
            Source.ISSUER,
            FailureClass.TIMING,
            "Not enough money in the account at that moment.",
            razorpay_says_retryable=True,
        ),
        ReasonCode(
            "transaction_limit_exceeded",
            Source.ISSUER,
            FailureClass.TIMING,
            "The card's daily transaction cap was already reached.",
            razorpay_says_retryable=True,
        ),
        ReasonCode(
            "card_expired",
            Source.ISSUER,
            FailureClass.CUSTOMER_ACTION_REQUIRED,
            "The card is past its expiry date.",
            razorpay_says_retryable=False,
        ),
        ReasonCode(
            "card_not_enrolled",
            Source.ISSUER,
            FailureClass.CUSTOMER_ACTION_REQUIRED,
            "Card is not activated for online transactions.",
            razorpay_says_retryable=True,
        ),
        ReasonCode(
            "debit_instrument_inactive",
            Source.ISSUER,
            FailureClass.CUSTOMER_ACTION_REQUIRED,
            "Card is not enabled for online use.",
            razorpay_says_retryable=True,
        ),
        ReasonCode(
            "card_disabled_for_online_payments",
            Source.ISSUER,
            FailureClass.CUSTOMER_ACTION_REQUIRED,
            "Online transactions are switched off for this card.",
            razorpay_says_retryable=True,
        ),
        ReasonCode(
            "debit_instrument_blocked",
            Source.ISSUER,
            FailureClass.CUSTOMER_ACTION_REQUIRED,
            "The card is blocked by the bank or the customer.",
            razorpay_says_retryable=True,
        ),
        ReasonCode(
            "payment_timed_out",
            Source.RAZORPAY,
            FailureClass.PRESENT_FRICTION,
            "The customer exceeded the ~10 minute payment window.",
            razorpay_says_retryable=True,
        ),
        ReasonCode(
            "authentication_failed",
            Source.ISSUER,
            FailureClass.PRESENT_FRICTION,
            "Wrong OTP, or the browser was closed during verification.",
            razorpay_says_retryable=True,
        ),
        ReasonCode(
            "incorrect_cvv",
            Source.CUSTOMER,
            FailureClass.PRESENT_FRICTION,
            "The customer mistyped the CVV.",
            razorpay_says_retryable=True,
        ),
        ReasonCode(
            "payment_cancelled",
            Source.CUSTOMER,
            FailureClass.INTENT_NEGATIVE,
            "The customer deliberately cancelled or pressed back.",
            razorpay_says_retryable=True,
        ),
        ReasonCode(
            "payment_risk_check_failed",
            Source.ISSUER,
            FailureClass.RISK_BLOCKED,
            "The issuing bank flagged the transaction as risky.",
            razorpay_says_retryable=True,
        ),
        ReasonCode(
            "card_declined",
            Source.ISSUER,
            FailureClass.AMBIGUOUS,
            "Declined by the bank, with no reason given.",
            razorpay_says_retryable=True,
        ),
        ReasonCode(
            "payment_failed",
            Source.ISSUER,
            FailureClass.AMBIGUOUS,
            "Declined by the bank, with no reason given.",
            razorpay_says_retryable=True,
        ),
    ]
}


def classify(code: str) -> ReasonCode:
    """Look up a reason code. Unknown codes are treated as ambiguous rather
    than crashing — an unrecognised code is exactly the case that should be
    investigated, not dropped."""
    return REASON_CODES.get(
        code,
        ReasonCode(
            code,
            Source.ISSUER,
            FailureClass.AMBIGUOUS,
            "Unrecognised reason code.",
            razorpay_says_retryable=True,
        ),
    )


def codes_where_we_disagree_with_docs() -> list[str]:
    """Codes Razorpay marks retryable that we refuse to blind-retry.

    This list IS the thesis of the project. Used in the README and the
    pitch video.
    """
    never_blind_retry = {
        FailureClass.CUSTOMER_ACTION_REQUIRED,
        FailureClass.RISK_BLOCKED,
        FailureClass.INTENT_NEGATIVE,
    }
    return sorted(
        rc.code
        for rc in REASON_CODES.values()
        if rc.razorpay_says_retryable and rc.failure_class in never_blind_retry
    )
