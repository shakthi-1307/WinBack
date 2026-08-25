"""Chooses a gateway. Strict: the real one, or a refusal.

The fake gateway is not a fallback. It is a test double, selected only when
something explicitly asks for it. Missing credentials produce an error, never
a quietly substituted pretend run.
"""

from __future__ import annotations

from backend.config.mode import razorpay_configured, require_razorpay
from backend.executor.fake_gateway import FakeGateway
from backend.executor.gateway_base import Gateway
from backend.executor.razorpay_gateway import RazorpayGateway


def default_gateway() -> Gateway:
    require_razorpay()          # raises unless real keys, or an explicit opt-out
    if razorpay_configured():
        return RazorpayGateway()
    return FakeGateway()        # tests only; never reached in a normal run
