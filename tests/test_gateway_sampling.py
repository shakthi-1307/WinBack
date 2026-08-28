"""Sampling: real calls where they prove something, doubles where they don't.

The property under test is not "it goes fast". It is that the split is
*always accurately reported* — a run must never be able to imply more real
integration than it actually performed.
"""

from __future__ import annotations

import pytest

from backend.executor.fake_gateway import FakeGateway
from backend.executor.gateway_base import GatewayError, GatewayResult
from backend.executor.sampling_gateway import SamplingGateway


class StubLive:
    """Stands in for RazorpayGateway, marking results as live."""

    def __init__(self, fail_times: int = 0):
        self.calls = 0
        self.fail_times = fail_times

    def create_and_attempt(self, *, idempotency_key, amount_paise, txn_id, notes):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise GatewayError("simulated transport failure")
        return GatewayResult(order_id=f"order_LIVE{self.calls}",
                             payment_ref="pay_LIVE", accepted=True,
                             live=True, raw={})


def call(gateway, n: int = 1):
    for i in range(n):
        try:
            gateway.create_and_attempt(idempotency_key=f"k{i}", amount_paise=100,
                                       txn_id=f"t{i}", notes={})
        except GatewayError:
            pass


def test_the_first_n_calls_are_real_and_the_rest_are_not():
    live = StubLive()
    gateway = SamplingGateway(live=live, sample_size=3)
    call(gateway, 10)

    assert live.calls == 3, "the sample must be respected exactly"
    assert gateway.live_calls == 3
    assert gateway.doubled_calls == 7
    assert gateway.calls == 10


def test_sample_size_zero_never_touches_the_network():
    live = StubLive()
    call(SamplingGateway(live=live, sample_size=0), 5)
    assert live.calls == 0


def test_negative_sample_size_means_every_call_is_real():
    live = StubLive()
    gateway = SamplingGateway(live=live, sample_size=-1)
    call(gateway, 6)
    assert live.calls == 6
    assert gateway.doubled_calls == 0


def test_results_are_tagged_with_their_provenance():
    gateway = SamplingGateway(live=StubLive(), sample_size=1)
    first = gateway.create_and_attempt(idempotency_key="a", amount_paise=1,
                                       txn_id="t", notes={})
    second = gateway.create_and_attempt(idempotency_key="b", amount_paise=1,
                                        txn_id="t", notes={})
    assert first.live is True
    assert second.live is False, "a doubled call must never claim to be live"


def test_a_transport_failure_does_not_consume_the_sample():
    """Nothing was proven by a call that never landed, so it should not
    eat one of the real slots."""
    live = StubLive(fail_times=2)
    gateway = SamplingGateway(live=live, sample_size=2)
    call(gateway, 4)

    assert gateway.live_errors == 2
    assert gateway.live_calls == 2, "two real successes still required"
    assert live.calls == 4


@pytest.mark.parametrize("sample", [0, 1, 5, -1])
def test_the_reported_total_always_matches_the_calls_made(sample):
    gateway = SamplingGateway(live=StubLive(), sample_size=sample)
    call(gateway, 8)
    assert gateway.calls == gateway.live_calls + gateway.doubled_calls == 8
