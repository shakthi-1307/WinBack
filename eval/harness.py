"""
The evaluation harness.

Runs every strategy over the identical batch as a day-by-day campaign, and
scores them side by side. Because the simulator uses common random numbers,
differences between strategies are differences in decision quality, not luck.

    python -m eval.harness
    python -m eval.harness --replay        # show sample transaction stories
"""

from __future__ import annotations

import sys

from core.executor.executor import Executor
from core.executor.gateway import FakeGateway, default_gateway
from core.ledger import events as ev
from core.ledger.events import Ledger
from core.ledger.replay import render
from core.policy.engine import PolicyEngine
from core.scheduler.campaign import Campaign
from data.generator import generate, summarise
from eval import metrics
from eval.strategies import ALL_STRATEGIES
from sim.simulator import assumptions_fingerprint


def run_campaign(strategy, payments, customers, ledger=None):
    campaign = Campaign(
        strategy=strategy,
        payments=payments,
        customers=customers,
        policy=PolicyEngine(),
        executor=Executor(gateway=default_gateway()),
        ledger=ledger,
    )
    traces = campaign.run()
    return traces, campaign


def main() -> None:
    show_replay = "--replay" in sys.argv

    customers_list, payments = generate(400)
    customers = {c.id: c for c in customers_list}

    print("=" * 78)
    print("WINBACK — batch evaluation")
    print("=" * 78)
    print()
    print(summarise(customers_list, payments))
    print()
    print(f"assumptions fingerprint  {assumptions_fingerprint()}")
    print("(if this hash changes, results from different runs are not comparable)")
    print()

    results = []
    campaigns = {}
    ledgers = {}

    for strategy in ALL_STRATEGIES:
        ledger = Ledger(run_id=f"run_{strategy.name}", strategy=strategy.name)
        traces, campaign = run_campaign(strategy, payments, customers, ledger)
        results.append(metrics.score(strategy.name, payments, traces))
        campaigns[strategy.name] = campaign
        ledgers[strategy.name] = ledger

    print("=" * 78)
    print(metrics.table(results))
    print("=" * 78)
    print()

    for r in results:
        print(r.strategy)
        print(metrics.detail(r))
        print()

    # Where the intelligence went, and what it cost.
    for strategy in ALL_STRATEGIES:
        tel = getattr(strategy, "telemetry", None)
        if not tel:
            continue
        total = tel["table_decisions"] + tel["model_decisions"]
        usage = strategy.client.usage
        print(f"{strategy.name} — intelligence budget")
        print(f"  decided by lookup table  {tel['table_decisions']:>4} "
              f"({tel['table_decisions'] / total * 100:.0f}% of transactions, zero model cost)")
        print(f"  escalated to the model   {tel['model_decisions']:>4} "
              f"({tel['model_decisions'] / total * 100:.0f}%)")
        print(f"  gray-zone investigations {tel['investigations']:>4}")
        print(f"  hostile notes seen       {tel['hostile_notes_seen']:>4}")
        print(f"  model outputs rejected   {tel['output_rejections']:>4}")
        print()

    # Execution integrity.
    agent = campaigns[ALL_STRATEGIES[-1].name]
    gw = agent.executor.gateway
    print("execution integrity (winback_agent)")
    print(f"  gateway calls            {getattr(gw, 'calls', 0):>4}")
    print(f"  transient gateway errors {agent.executor.gateway_errors:>4}"
          "   (same idempotency key re-presented, no duplicate charge)")
    print(f"  duplicates suppressed    {agent.executor.duplicate_suppressions:>4}")
    print(f"  distinct idempotency keys{len(agent.executor.seen):>5}")
    print()

    led = ledgers[ALL_STRATEGIES[-1].name]
    print(f"ledger (winback_agent): {led.total()} events, append-only")
    for t, c in led.counts_by_type().items():
        print(f"  {t:<24}{c:>6}")
    print()

    if show_replay:
        print("=" * 78)
        print("SAMPLE TRANSACTION STORIES — reconstructed from the ledger alone")
        print("=" * 78)
        print()
        picked = []
        for t in (ev.RECOVERED, ev.BLOCKED, ev.GATEWAY_ERROR, ev.ABANDONED):
            ids = led.transactions_with(t)
            if ids:
                picked.append(ids[0])
        for txn_id in dict.fromkeys(picked):
            print(render(led, txn_id))
            print()

    best = max(results, key=lambda r: r.net_paise)
    print(f"highest net return: {best.strategy}  (Rs {best.net_paise / 100:,.0f})")


if __name__ == "__main__":
    main()
