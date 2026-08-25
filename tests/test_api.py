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
    assert "model" in body and "gateway" in body


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
