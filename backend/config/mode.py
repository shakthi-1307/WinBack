"""Run mode. Strict by default.

There is exactly one thing in this system that may be substituted for the
real Razorpay API: a fake gateway used by the test suite. It is NOT a
fallback and it is never silently selected. If credentials are missing, the
system refuses to run rather than quietly producing numbers that look real
and are not.

A payments system that silently degrades to a pretend mode is worse than one
that stops, because the output is indistinguishable either way.
"""

from __future__ import annotations

import os

from backend.config.env import ensure_loaded

ALLOW_FAKE_VAR = "WINBACK_ALLOW_FAKE_GATEWAY"


class CredentialsMissing(RuntimeError):
    """Raised instead of falling back to something invented."""


def fake_gateway_permitted() -> bool:
    """Only ever true when explicitly requested — by the test suite, or by
    someone who has read the warning and typed the variable themselves."""
    ensure_loaded()
    return os.environ.get(ALLOW_FAKE_VAR) == "1"


def razorpay_configured() -> bool:
    ensure_loaded()
    return bool(os.environ.get("RAZORPAY_KEY_ID")
                and os.environ.get("RAZORPAY_KEY_SECRET"))


def require_razorpay() -> None:
    if razorpay_configured():
        return
    if fake_gateway_permitted():
        return
    raise CredentialsMissing(
        "\n"
        "  Razorpay test credentials are not configured, so this run was refused.\n"
        "\n"
        "  Every gateway call in a Winback run is a real call to Razorpay test\n"
        "  mode. There is no pretend mode that produces results anyway.\n"
        "\n"
        "  To fix:\n"
        "    1. Razorpay Dashboard -> Account & Settings -> API Keys\n"
        "       (mode switch on TEST)\n"
        "    2. cp .env.example .env\n"
        "    3. Put RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in .env\n"
        "    4. python -m backend.config     # confirm it reads LIVE\n"
        "\n"
        f"  The test suite sets {ALLOW_FAKE_VAR}=1 deliberately, so that unit\n"
        "  tests do not depend on network access. Nothing else should.\n"
    )
