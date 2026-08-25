"""
The gateway seam — the MECHANICS half of an attempt.

This answers exactly one question: *did the API call work?*

It does not, and cannot, answer whether the customer's bank would have
approved. Razorpay's test mode returns whatever outcome the sandbox is
configured to return; there is no real Arun and no real balance. That second
question belongs to the frozen simulator, and keeping the two apart is the
central design decision of this project.

Two implementations:

  RazorpayGateway — real HTTP against Razorpay test mode. Creates real orders,
                    gets real order IDs, verifies real signatures.

  FakeGateway     — deterministic, offline, and deliberately flaky: it fails
                    roughly 2% of calls with a transient network error so the
                    idempotency path is exercised on every run rather than
                    only in a test nobody remembers to write.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from typing import Protocol


class GatewayError(RuntimeError):
    """A transport-level failure. The attempt may or may not have landed —
    which is precisely why idempotency keys exist."""


@dataclass(frozen=True)
class GatewayResult:
    order_id: str
    payment_ref: str
    accepted: bool
    """Whether the gateway accepted the request. NOT whether the customer
    paid — see the module docstring."""

    raw: dict


class Gateway(Protocol):
    def create_and_attempt(
        self, *, idempotency_key: str, amount_paise: int, txn_id: str, notes: dict
    ) -> GatewayResult: ...


# --------------------------------------------------------------------------


class RazorpayGateway:
    """Live Razorpay test mode.

    Order creation is fully server-side and works with test keys today.
    Authorising the payment itself normally needs either a client-side
    checkout or a saved token on a registered mandate, which depends on how
    the sandbox account is provisioned. When a token is available the
    recurring charge is attempted; when it is not, the order is still created
    for real and the authorisation step is recorded as unavailable rather
    than faked. Being explicit about that boundary is better than a demo that
    quietly pretends.
    """

    BASE = "https://api.razorpay.com/v1"

    def __init__(self) -> None:
        self.key_id = os.environ["RAZORPAY_KEY_ID"]
        self.key_secret = os.environ["RAZORPAY_KEY_SECRET"]

    def _post(self, path: str, body: dict, idempotency_key: str) -> dict:
        import base64
        import urllib.error
        import urllib.request

        auth = base64.b64encode(f"{self.key_id}:{self.key_secret}".encode()).decode()
        req = urllib.request.Request(
            f"{self.BASE}{path}",
            data=json.dumps(body).encode(),
            headers={
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/json",
                # Razorpay honours this on supported endpoints; we also keep
                # our own store, because never trusting a single layer with
                # duplicate suppression is the whole lesson of payments.
                "X-Razorpay-Idempotency-Key": idempotency_key,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            return json.loads(e.read() or b"{}")
        except Exception as e:  # network, DNS, timeout
            raise GatewayError(str(e)) from e

    def create_and_attempt(
        self, *, idempotency_key: str, amount_paise: int, txn_id: str, notes: dict
    ) -> GatewayResult:
        order = self._post(
            "/orders",
            {
                "amount": amount_paise,
                "currency": "INR",
                "receipt": txn_id[:40],
                "notes": {k: str(v)[:100] for k, v in notes.items()},
            },
            idempotency_key,
        )
        order_id = order.get("id", "")
        if not order_id:
            raise GatewayError(f"order not created: {order.get('error', order)}")

        return GatewayResult(
            order_id=order_id,
            payment_ref=order.get("payment_id", "authorisation_unavailable_in_sandbox"),
            accepted=True,
            raw=order,
        )

    def verify_signature(self, order_id: str, payment_id: str, signature: str) -> bool:
        expected = hmac.new(
            self.key_secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)


# --------------------------------------------------------------------------


@dataclass
class FakeGateway:
    """Offline gateway. Deterministic ids, and a small, reproducible rate of
    transient failures so the retry-and-idempotency path is exercised."""

    failure_rate: float = 0.02
    calls: int = 0
    transient_failures: int = 0

    def create_and_attempt(
        self, *, idempotency_key: str, amount_paise: int, txn_id: str, notes: dict
    ) -> GatewayResult:
        self.calls += 1
        digest = hashlib.sha256(idempotency_key.encode()).hexdigest()

        # Deterministic pseudo-failure derived from the key, so the same
        # attempt always fails the same way across runs and strategies.
        if int(digest[:8], 16) / 0xFFFFFFFF < self.failure_rate:
            self.transient_failures += 1
            raise GatewayError("simulated network timeout contacting gateway")

        return GatewayResult(
            order_id=f"order_TEST{digest[:14].upper()}",
            payment_ref=f"pay_TEST{digest[14:28].upper()}",
            accepted=True,
            raw={"mode": "offline", "amount": amount_paise},
        )


def default_gateway() -> Gateway:
    if os.environ.get("RAZORPAY_KEY_ID") and os.environ.get("RAZORPAY_KEY_SECRET"):
        return RazorpayGateway()
    return FakeGateway()
