"""Chooses a gateway based on configuration. One decision, one file."""

from __future__ import annotations

import os

from backend.config.env import ensure_loaded
from backend.executor.fake_gateway import FakeGateway
from backend.executor.gateway_base import Gateway
from backend.executor.razorpay_gateway import RazorpayGateway


def default_gateway() -> Gateway:
    ensure_loaded()
    if os.environ.get("RAZORPAY_KEY_ID") and os.environ.get("RAZORPAY_KEY_SECRET"):
        return RazorpayGateway()
    return FakeGateway()
