"""Chooses a gateway. One decision, one file.

`live_sample` controls how many charge attempts go to the real Razorpay API:

    0     none — a pure measurement run, no network
    n     the first n attempts are real, the rest use a transport double
    -1    every attempt is real (slow: thousands of serial round trips)

Whatever is chosen, every attempt records which kind it was and the run
reports the split. Nothing is ever silently substituted.
"""

from __future__ import annotations

from backend.config.mode import razorpay_configured, require_razorpay
from backend.executor.fake_gateway import FakeGateway
from backend.executor.gateway_base import Gateway
from backend.executor.razorpay_gateway import RazorpayGateway
from backend.executor.sampling_gateway import SamplingGateway

DEFAULT_LIVE_SAMPLE = 25


def default_gateway(live_sample: int = 0) -> Gateway:
    if live_sample == 0:
        return FakeGateway()

    require_razorpay()
    if not razorpay_configured():
        # Only reachable when the test suite has explicitly opted out.
        return FakeGateway()

    return SamplingGateway(live=RazorpayGateway(), sample_size=live_sample)
