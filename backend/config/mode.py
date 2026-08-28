"""Run mode and credential policy.

The rule is not "everything must hit the network". It is **nothing is ever
silently substituted**. A run that uses a transport double says so, on every
attempt and in its summary. A run that asks for real Razorpay calls and has
no credentials is refused rather than quietly downgraded.
"""

from __future__ import annotations

import os

from backend.config.env import ensure_loaded

ALLOW_FAKE_VAR = "WINBACK_ALLOW_FAKE_GATEWAY"


class CredentialsMissing(RuntimeError):
    """Raised instead of pretending a live run happened."""


def fake_gateway_permitted() -> bool:
    ensure_loaded()
    return os.environ.get(ALLOW_FAKE_VAR) == "1"


def razorpay_configured() -> bool:
    ensure_loaded()
    return bool(os.environ.get("RAZORPAY_KEY_ID")
                and os.environ.get("RAZORPAY_KEY_SECRET"))


def require_razorpay() -> None:
    """Called only when live Razorpay calls have actually been requested."""
    if razorpay_configured() or fake_gateway_permitted():
        return
    raise CredentialsMissing(
        "\n"
        "  Live Razorpay calls were requested, but no test credentials are\n"
        "  configured. Refusing rather than substituting.\n"
        "\n"
        "  To fix:\n"
        "    1. Razorpay Dashboard -> Account & Settings -> API Keys\n"
        "       (mode switch on TEST)\n"
        "    2. cp .env.example .env  and fill in the two values\n"
        "    3. python -m backend.config     # confirm it reads LIVE\n"
        "\n"
        "  Or run the measurement without live calls, which is the default:\n"
        "    python -m backend.evaluation.harness            # --live 0\n"
    )
