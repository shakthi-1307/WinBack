"""Live numbers for the console: money at risk, recovered, in flight."""

from __future__ import annotations

from fastapi import APIRouter

from backend.api.state import STATE
from backend.evaluation.scoring import score

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("")
def metrics() -> dict:
    campaign = STATE.ensure()
    result = score(STATE.strategy_name, STATE.payments, campaign.traces)

    in_flight = sum(
        1 for t in campaign.traces.values()
        if not t.recovered and t.abandoned_on_day is None
    )
    at_risk_remaining = sum(
        p.amount_paise for p in STATE.payments
        if not campaign.traces[p.id].recovered
    ) / 100

    return {
        **result.as_dict(),
        "day": campaign.day,
        "in_flight": in_flight,
        "at_risk_remaining_rupees": at_risk_remaining,
        "gateway_errors": campaign.executor.gateway_errors,
        "duplicates_suppressed": campaign.executor.duplicate_suppressions,
    }


@router.get("/timeseries")
def timeseries() -> dict:
    """Recovered rupees by simulated day — the line the console animates."""
    campaign = STATE.ensure()
    by_day: dict[int, float] = {}
    for payment in STATE.payments:
        trace = campaign.traces[payment.id]
        if trace.recovered and trace.recovered_on_day is not None:
            by_day[trace.recovered_on_day] = (
                by_day.get(trace.recovered_on_day, 0) + payment.amount_rupees
            )

    cumulative, running = [], 0.0
    for day in range(campaign.horizon + 1):
        running += by_day.get(day, 0.0)
        cumulative.append({"day": day, "recovered_rupees": round(running)})
    return {"series": cumulative, "current_day": campaign.day}
