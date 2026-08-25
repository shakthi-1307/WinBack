"""Live Razorpay test mode.

Order creation is fully server-side and works with test keys today.
Authorising the payment itself normally needs either a client-side checkout
or a saved token on a registered mandate, which depends on how the sandbox
account is provisioned. Where that is unavailable the order is still created
for real and the authorisation step is recorded as unavailable rather than
faked — an explicit boundary beats a demo that quietly pretends.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os

from backend.config.env import ensure_loaded
from backend.executor.gateway_base import GatewayError, GatewayResult

BASE_URL = "https://api.razorpay.com/v1"
TIMEOUT_SECONDS = 20
UNAVAILABLE = "authorisation_unavailable_in_sandbox"


class RazorpayGateway:
    def __init__(self) -> None:
        ensure_loaded()
        self.key_id = os.environ["RAZORPAY_KEY_ID"]
        self.key_secret = os.environ["RAZORPAY_KEY_SECRET"]
        self._refuse_live_keys()

    def _refuse_live_keys(self) -> None:
        """Winback creates orders. With a live key it would create real ones,
        for real customers, from a batch of synthetic test data. Refuse at
        construction rather than discovering it from a bank statement."""
        if self.key_id.startswith("rzp_live_") and not os.environ.get(
            "WINBACK_ALLOW_LIVE_KEYS"
        ):
            raise RuntimeError(
                "RAZORPAY_KEY_ID is a LIVE key (rzp_live_...). Winback creates "
                "orders and runs against synthetic data — this would produce "
                "real orders for real customers. Use a test key (rzp_test_...)."
            )

    def _post(self, path: str, body: dict, idempotency_key: str) -> dict:
        import base64
        import urllib.error
        import urllib.request

        auth = base64.b64encode(f"{self.key_id}:{self.key_secret}".encode()).decode()
        request = urllib.request.Request(
            f"{BASE_URL}{path}",
            data=json.dumps(body).encode(),
            headers={
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/json",
                # Razorpay honours this on supported endpoints. We also keep
                # our own store, because trusting a single layer with
                # duplicate suppression is how double charges happen.
                "X-Razorpay-Idempotency-Key": idempotency_key,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as error:
            return json.loads(error.read() or b"{}")
        except Exception as error:
            raise GatewayError(str(error)) from error

    def create_and_attempt(self, *, idempotency_key: str, amount_paise: int,
                           txn_id: str, notes: dict) -> GatewayResult:
        order = self._post("/orders", {
            "amount": amount_paise,
            "currency": "INR",
            "receipt": txn_id[:40],
            "notes": {k: str(v)[:100] for k, v in notes.items()},
        }, idempotency_key)

        order_id = order.get("id", "")
        if not order_id:
            raise GatewayError(f"order not created: {order.get('error', order)}")

        return GatewayResult(
            order_id=order_id,
            payment_ref=order.get("payment_id", UNAVAILABLE),
            accepted=True,
            live=True,
            raw=order,
        )

    def verify_signature(self, order_id: str, payment_id: str, signature: str) -> bool:
        expected = hmac.new(
            self.key_secret.encode(),
            f"{order_id}|{payment_id}".encode(),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
