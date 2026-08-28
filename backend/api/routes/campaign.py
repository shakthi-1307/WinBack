"""Campaign control: reset, advance a day, run to completion, kill switch."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.api.state import STATE
from backend.strategies.registry import all_strategies

router = APIRouter(prefix="/api/campaign", tags=["campaign"])


class ResetRequest(BaseModel):
    strategy: str | None = None
    size: int | None = None
    live_sample: int | None = None
    """0 = no network. n = the first n charges hit the real Razorpay API.
    -1 = every charge does, slowly."""


def _snapshot() -> dict:
    campaign = STATE.ensure()
    return {
        "day": campaign.day,
        "horizon": campaign.horizon,
        "finished": campaign.clock.finished or STATE.killed,
        "killed": STATE.killed,
        "strategy": STATE.strategy_name,
        "size": STATE.size,
        "pending_jobs": campaign.queue.pending(),
        # What is ACTUALLY in use, measured from the executor — never what is
        # merely configured. The console header shows this verbatim.
        "gateway_in_use": STATE.gateway_in_use(),
        "live_sample": STATE.live_sample,
        "live_gateway_calls": campaign.executor.live_gateway_calls,
        "doubled_gateway_calls": campaign.executor.substituted_gateway_calls,
    }


@router.get("/status")
def status() -> dict:
    return _snapshot()


@router.get("/strategies")
def strategies() -> dict:
    return {"strategies": [s.name for s in all_strategies()]}


@router.post("/reset")
def reset(request: ResetRequest) -> dict:
    from backend.config.mode import CredentialsMissing

    try:
        STATE.reset(strategy_name=request.strategy, size=request.size,
                    live_sample=request.live_sample)
    except CredentialsMissing as error:
        # A missing credential is a configuration problem with a clear fix, not
        # an internal error. Say so, with the instructions attached.
        raise HTTPException(status_code=503, detail=str(error)) from error
    return _snapshot()


@router.post("/tick")
def tick() -> dict:
    campaign = STATE.ensure()
    fired = 0
    if not campaign.clock.finished and not STATE.killed:
        fired = campaign.tick()
        if campaign.ledger:
            campaign.ledger.commit()
    return {**_snapshot(), "jobs_fired": fired}


@router.post("/run")
def run() -> dict:
    """Run the remaining days. A 21-day campaign over 400 transactions
    completes in well under a second, which is what makes the console
    watchable rather than a progress bar."""
    campaign = STATE.ensure()
    while not campaign.clock.finished and not STATE.killed:
        campaign.tick()
    campaign.run()
    return _snapshot()


@router.post("/kill")
def kill() -> dict:
    """The stop button. An autonomous system that spends money and contacts
    people needs one an operator can reach without a deploy."""
    STATE.killed = True
    return _snapshot()
