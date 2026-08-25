"""Offline gateway: deterministic ids, and deliberately flaky.

It fails a small, reproducible fraction of calls with a transient error, so
the idempotency-and-re-presentation path is exercised on every single run
rather than only in a test somebody remembers to write.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from backend.executor.gateway_base import GatewayError, GatewayResult

DEFAULT_FAILURE_RATE = 0.02


@dataclass
class FakeGateway:
    failure_rate: float = DEFAULT_FAILURE_RATE
    calls: int = 0
    transient_failures: int = 0

    def create_and_attempt(self, *, idempotency_key: str, amount_paise: int,
                           txn_id: str, notes: dict) -> GatewayResult:
        self.calls += 1
        digest = hashlib.sha256(idempotency_key.encode()).hexdigest()

        # Failure is derived from the key, so the same attempt always fails
        # the same way across runs and across strategies.
        if int(digest[:8], 16) / 0xFFFFFFFF < self.failure_rate:
            self.transient_failures += 1
            raise GatewayError("simulated network timeout contacting gateway")

        return GatewayResult(
            order_id=f"order_TEST{digest[:14].upper()}",
            payment_ref=f"pay_TEST{digest[14:28].upper()}",
            accepted=True,
            raw={"mode": "offline", "amount": amount_paise},
        )
