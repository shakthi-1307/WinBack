"""The one live campaign the console is watching.

A single in-process object, deliberately. This is an operator console for one
merchant's recovery run, not a multi-tenant service — adding a session store
would be complexity with nothing behind it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.data.generator import generate
from backend.domain.models import Customer, FailedPayment
from backend.executor.executor import Executor
from backend.executor.gateway_factory import default_gateway
from backend.ledger.store import Ledger
from backend.policy.engine import PolicyEngine
from backend.scheduler.campaign import Campaign
from backend.strategies.registry import all_strategies

DEFAULT_BATCH_SIZE = 400


@dataclass
class ConsoleState:
    size: int = DEFAULT_BATCH_SIZE
    strategy_name: str = "winback_agent"
    campaign: Campaign | None = None
    ledger: Ledger | None = None
    payments: list[FailedPayment] = field(default_factory=list)
    customers: dict[str, Customer] = field(default_factory=dict)
    killed: bool = False

    def reset(self, strategy_name: str | None = None, size: int | None = None) -> None:
        self.size = size or self.size
        self.strategy_name = strategy_name or self.strategy_name
        self.killed = False

        customer_list, payments = generate(self.size)
        self.payments = payments
        self.customers = {c.id: c for c in customer_list}

        strategy = next(
            s for s in all_strategies() if s.name == self.strategy_name
        )
        self.ledger = Ledger(run_id="console", strategy=self.strategy_name)
        self.campaign = Campaign(
            strategy=strategy,
            payments=payments,
            customers=self.customers,
            policy=PolicyEngine(),
            executor=Executor(gateway=default_gateway()),
            ledger=self.ledger,
        )

    def ensure(self) -> Campaign:
        if self.campaign is None:
            self.reset()
        return self.campaign  # type: ignore[return-value]


STATE = ConsoleState()
