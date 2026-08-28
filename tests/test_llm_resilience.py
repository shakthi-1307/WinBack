"""A model provider outage must not stop a merchant recovering money.

This is the property that matters most about the model tier: it is optional.
The lookup table decides four fifths of every batch, and the rule tier is a
complete strategy on its own — so losing the model should cost a percent or
two of recovery, not the run.
"""

from __future__ import annotations

import json
import urllib.error

import pytest

from backend.agents.investigator_agent import ALLOWED_ACTIONS, investigate
from backend.domain.models import Channel, Customer, FailedPayment
from backend.llm.live_client import CIRCUIT_TRIPS_AFTER, LiveClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("WINBACK_API_KEY", "test-key")
    return LiveClient()


def fail_with(monkeypatch, error):
    def boom(*args, **kwargs):
        raise error
    monkeypatch.setattr("urllib.request.urlopen", boom)


def http_error(code: int, message: str = "model_not_found"):
    body = json.dumps({"error": {"message": message}}).encode()

    class Body:
        def read(self):
            return body

    error = urllib.error.HTTPError("u", code, "reason", {}, None)
    error.read = Body().read
    return error


def test_an_http_error_returns_empty_rather_than_raising(client, monkeypatch):
    """The bug this file exists for: a single 403 used to kill a
    400-transaction campaign."""
    fail_with(monkeypatch, http_error(403))
    assert client.complete_json("s", "u", []) == {}
    assert client.usage.failures == 1


def test_the_provider_message_is_kept(client, monkeypatch):
    fail_with(monkeypatch, http_error(403, "model has been decommissioned"))
    client.complete_json("s", "u", [])
    assert "decommissioned" in client.usage.last_error
    assert "403" in client.usage.last_error


def test_a_timeout_is_also_survivable(client, monkeypatch):
    fail_with(monkeypatch, TimeoutError("timed out"))
    assert client.complete_json("s", "u", []) == {}
    assert client.usage.failures == 1


def test_the_circuit_opens_after_repeated_failures(client, monkeypatch):
    """400 doomed HTTP requests help nobody."""
    fail_with(monkeypatch, http_error(403))
    for _ in range(CIRCUIT_TRIPS_AFTER):
        client.complete_json("s", "u", [])
    assert client.usage.circuit_open

    calls_before = client.usage.calls
    client.complete_json("s", "u", [])
    assert client.usage.calls == calls_before, "no call should be attempted"


def test_a_dead_model_still_produces_a_safe_decision(client, monkeypatch):
    """The whole point: the agent degrades, it does not fail."""
    fail_with(monkeypatch, http_error(403))
    customer = Customer("c1", payday=1, dnd=False,
                        preferred_channel=Channel.SMS,
                        tenure_months=12, prior_failures=0)
    payment = FailedPayment("t1", "c1", 149900, "card_declined", 10, True)

    judgement = investigate(payment, customer, client)
    assert judgement.action in ALLOWED_ACTIONS
    assert 1 <= judgement.delay_days <= 14
    assert judgement.output_rejected is True


def test_usage_reports_health(client, monkeypatch):
    assert client.usage.healthy
    fail_with(monkeypatch, http_error(500))
    client.complete_json("s", "u", [])
    assert not client.usage.healthy
