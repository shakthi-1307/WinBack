"""API tests: the console must show the same numbers the harness reports."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        test_client.post("/api/campaign/reset", json={"strategy": "winback_agent"})
        yield test_client


def test_health_reports_which_mode_is_active(client):
    body = client.get("/api/health").json()
    assert body["ok"] is True
    assert "model" in body and "gateway_configured" in body


def test_a_finished_campaign_matches_the_harness(client):
    client.post("/api/campaign/reset", json={"strategy": "winback_agent"})
    client.post("/api/campaign/run")
    metrics = client.get("/api/metrics").json()

    # The console is a view over the same engine, not a second implementation.
    assert metrics["recovered_count"] == 187
    assert metrics["impossible_charges"] == 0
    assert metrics["n"] == 400


def test_stepping_one_day_advances_the_clock(client):
    client.post("/api/campaign/reset", json={"strategy": "winback_rules"})
    before = client.get("/api/campaign/status").json()["day"]
    client.post("/api/campaign/tick")
    after = client.get("/api/campaign/status").json()["day"]
    assert after == before + 1


def test_kill_switch_stops_the_campaign(client):
    client.post("/api/campaign/reset", json={"strategy": "winback_agent"})
    client.post("/api/campaign/kill")
    status = client.get("/api/campaign/status").json()
    assert status["killed"] is True
    assert status["finished"] is True


def test_a_transaction_can_be_replayed_from_the_ledger(client):
    client.post("/api/campaign/reset", json={"strategy": "winback_agent"})
    client.post("/api/campaign/run")
    recovered = client.get("/api/transactions?status=recovered").json()
    assert recovered["total"] > 0

    txn_id = recovered["transactions"][0]["id"]
    replay = client.get(f"/api/transactions/{txn_id}").json()
    kinds = [event["type"] for event in replay["timeline"]]
    assert "planned" in kinds
    assert "recovered" in kinds
    assert kinds.index("planned") < kinds.index("recovered")


def test_unknown_transaction_is_a_404(client):
    assert client.get("/api/transactions/txn_nope").status_code == 404


def test_guardrail_panel_surfaces_hostile_notes(client):
    body = client.get("/api/guardrails").json()
    assert body["hostile_count"] == 19
    assert body["codes_we_refuse_to_blind_retry"]


def test_timeseries_is_monotonic(client):
    """Cumulative recovery can never go down."""
    series = client.get("/api/metrics/timeseries").json()["series"]
    values = [point["recovered_rupees"] for point in series]
    assert values == sorted(values)


def test_the_console_is_served(client):
    assert client.get("/").status_code == 200
    assert client.get("/styles/tokens.css").status_code == 200
    assert client.get("/scripts/main.js").status_code == 200


def test_the_console_reports_the_gateway_it_actually_used(client):
    """The header must describe measured reality, not configuration.

    A console that says "live razorpay" while its attempts went to a transport
    double is exactly the overstatement this project claims is impossible.
    """
    client.post("/api/campaign/reset", json={"strategy": "winback_agent",
                                             "live_sample": 0})
    client.post("/api/campaign/run")
    status = client.get("/api/campaign/status").json()

    assert status["live_gateway_calls"] == 0
    assert status["doubled_gateway_calls"] > 0
    assert status["gateway_in_use"] == "transport double"


def test_health_reports_configuration_not_usage(client):
    """/api/health says what is CONFIGURED. Only campaign status says what was
    used — the two must not be confusable."""
    body = client.get("/api/health").json()
    assert "gateway_configured" in body
    assert "gateway" not in body, "the ambiguous key must be gone"


def test_the_calendar_shows_when_the_agent_acted(client):
    client.post("/api/campaign/reset", json={"strategy": "winback_agent"})
    client.post("/api/campaign/run")
    body = client.get("/api/metrics/calendar").json()

    assert len(body["days"]) == 30
    assert body["payday_dates"], "customers must have paydays"
    assert all(body["days"][d - 1]["is_payday"] for d in body["payday_dates"])
    assert sum(c["charges"] for c in body["days"]) == body["charges_total"]


def test_winback_aims_at_paydays_and_the_baseline_does_not(client):
    """The timing thesis, as a number.

    On insufficient-funds failures WHEN you retry is the only lever there is.
    Paydays plus their windows cover 13 of 30 days, so a strategy that ignores
    timing lands about 43% of its retries there by chance. Winback should be
    far above that; retry-x3 should be at chance.
    """
    client.post("/api/campaign/reset", json={"strategy": "retry_x3_immediate"})
    client.post("/api/campaign/run")
    baseline = client.get("/api/metrics/calendar").json()["timing_payday_targeting"]

    client.post("/api/campaign/reset", json={"strategy": "winback_agent"})
    client.post("/api/campaign/run")
    winback = client.get("/api/metrics/calendar").json()["timing_payday_targeting"]

    assert baseline < 0.55, "the baseline should be near chance"
    assert winback > 0.75, "winback should deliberately aim at paydays"
    assert winback - baseline > 0.25
