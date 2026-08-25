"""Turning a reason code into a failure class. Lookup only, no side effects."""

from __future__ import annotations

from backend.domain.failure_classes import FailureClass, Source
from backend.domain.reason_codes import REASON_CODES, ReasonCode

NEVER_BLIND_RETRY = {
    FailureClass.CUSTOMER_ACTION_REQUIRED,
    FailureClass.RISK_BLOCKED,
    FailureClass.INTENT_NEGATIVE,
}


def classify(code: str) -> ReasonCode:
    """An unrecognised code is treated as ambiguous rather than crashing —
    an unknown code is exactly the case that should be investigated."""
    return REASON_CODES.get(
        code,
        ReasonCode(code, Source.ISSUER, FailureClass.AMBIGUOUS,
                   "Unrecognised reason code.", True),
    )


def is_ambiguous(code: str) -> bool:
    return classify(code).failure_class is FailureClass.AMBIGUOUS


def is_known(code: str) -> bool:
    return code in REASON_CODES


def codes_where_we_disagree_with_docs() -> list[str]:
    """Codes Razorpay marks retryable that this system refuses to blind-retry.

    This list is the thesis, in one function.
    """
    return sorted(
        rc.code for rc in REASON_CODES.values()
        if rc.razorpay_says_retryable and rc.failure_class in NEVER_BLIND_RETRY
    )
