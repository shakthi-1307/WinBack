"""Wiring one strategy into a full campaign. Assembly only."""

from __future__ import annotations

from backend.executor.executor import Executor
from backend.executor.gateway_factory import default_gateway
from backend.ledger.store import Ledger
from backend.policy.engine import PolicyEngine
from backend.scheduler.campaign import Campaign


def run_campaign(strategy, payments, customers, ledger: Ledger | None = None,
                 live_sample: int = 0):
    campaign = Campaign(
        strategy=strategy,
        payments=payments,
        customers=customers,
        policy=PolicyEngine(),
        executor=Executor(gateway=default_gateway(live_sample)),
        ledger=ledger,
    )
    return campaign.run(), campaign
