"""What KIND of problem a payment failure represents.

Razorpay's docs answer "can this be retried?" — almost always yes.
This answers "what is actually wrong?", which is a different question and
the one that determines whether retrying is worth anything.
"""

from __future__ import annotations

from enum import Enum


class FailureClass(str, Enum):
    TRANSIENT_SYSTEM = "transient_system"
    """Nobody's fault. A machine was down. A prompt retry usually works."""

    TIMING = "timing"
    """The customer is good for the money, just not at this moment.
    Recovery depends almost entirely on WHEN you try again."""

    CUSTOMER_ACTION_REQUIRED = "customer_action_required"
    """The instrument cannot work until the customer does something.
    Retrying is guaranteed to fail. Only a nudge can change the outcome."""

    PRESENT_FRICTION = "present_friction"
    """The customer was actively trying to pay and something got in the way.
    Intent is high and fresh, and decays within hours."""

    INTENT_NEGATIVE = "intent_negative"
    """The customer deliberately backed out. Pressure converts a soft no
    into a permanent one."""

    RISK_BLOCKED = "risk_blocked"
    """The issuer flagged it. Repeated attempts degrade issuer trust for the
    merchant's ENTIRE account, harming unrelated customers."""

    AMBIGUOUS = "ambiguous"
    """The bank declined and said nothing useful. Needs investigation against
    customer history rather than a lookup."""


class Source(str, Enum):
    ISSUER = "issuer"
    RAZORPAY = "razorpay"
    CUSTOMER = "customer"
