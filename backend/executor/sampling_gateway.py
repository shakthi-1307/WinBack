"""Real Razorpay calls for a sample, a deterministic stand-in for the rest.

Why this exists
---------------
The harness compares four strategies over 400 transactions. Together they
attempt roughly 2,350 charges. Sending every one to Razorpay means thousands
of serial HTTPS round trips — ten minutes of wall clock, a hammered sandbox,
and no information that the first fifty calls did not already provide.

The two things being asked are different questions:

    INTEGRATION   does the executor really talk to Razorpay correctly?
                  Answered by a sample of real calls. Fifty is as
                  convincing as two thousand.

    MEASUREMENT   which strategy makes better decisions?
                  Has nothing to do with transport. Real HTTP adds latency
                  and flakiness to a comparison it cannot affect.

So the sample is real and the remainder is deterministic — and every single
attempt records which it was, so the split is never a claim you have to take
on trust. `--live 0` and `--live all` are both available.

The stand-in is not pretending to be Razorpay. It is a transport double for
a measurement that does not depend on transport, and it says so in every
line of output it touches.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.executor.fake_gateway import FakeGateway
from backend.executor.gateway_base import Gateway, GatewayError, GatewayResult


@dataclass
class SamplingGateway:
    live: Gateway
    sample_size: int
    """How many charge attempts go to the real API. `-1` means all of them."""

    double: FakeGateway = field(default_factory=lambda: FakeGateway(failure_rate=0.0))
    live_calls: int = 0
    doubled_calls: int = 0
    live_errors: int = 0

    @property
    def calls(self) -> int:
        return self.live_calls + self.doubled_calls

    def _sample_exhausted(self) -> bool:
        return self.sample_size >= 0 and self.live_calls >= self.sample_size

    def create_and_attempt(self, *, idempotency_key: str, amount_paise: int,
                           txn_id: str, notes: dict) -> GatewayResult:
        if self._sample_exhausted():
            self.doubled_calls += 1
            return self.double.create_and_attempt(
                idempotency_key=idempotency_key, amount_paise=amount_paise,
                txn_id=txn_id, notes=notes)

        try:
            result = self.live.create_and_attempt(
                idempotency_key=idempotency_key, amount_paise=amount_paise,
                txn_id=txn_id, notes=notes)
        except GatewayError:
            # A real transport failure is real data — the campaign already
            # knows how to re-present the same idempotency key — but it does
            # not consume the sample, because nothing was proven by it.
            self.live_errors += 1
            raise

        self.live_calls += 1
        return result
