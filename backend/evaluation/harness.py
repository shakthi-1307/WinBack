"""The evaluation harness.

Runs every strategy over the identical batch as a day-by-day campaign and
scores them side by side. Because the simulator uses common random numbers,
differences between strategies are differences in decision quality, not luck.

    python -m backend.evaluation.harness
    python -m backend.evaluation.harness --replay
"""

from __future__ import annotations

import sys

from backend.data.generator import generate
from backend.data.summary import summarise
from backend.evaluation.provenance import report as provenance_report
from backend.evaluation.reporting import comparison_table, detail, intelligence_budget
from backend.evaluation.runner import run_campaign
from backend.evaluation.scoring import score
from backend.ledger import event_types as ev
from backend.ledger.replay import render
from backend.ledger.store import Ledger
from backend.strategies.registry import all_strategies
from simulation.loader import assumptions_fingerprint

SAMPLE_EVENT_TYPES = (ev.RECOVERED, ev.BLOCKED, ev.GATEWAY_ERROR, ev.ABANDONED)


def _live_sample_from_argv() -> int:
    """--live 0 (default) | --live N | --live all"""
    if "--live" not in sys.argv:
        return 0
    value = sys.argv[sys.argv.index("--live") + 1]
    return -1 if value == "all" else int(value)


def main() -> None:
    show_replay = "--replay" in sys.argv
    live_sample = _live_sample_from_argv()
    customers_list, payments = generate()
    customers = {c.id: c for c in customers_list}
    strategies = all_strategies()

    print("=" * 78)
    print("WINBACK — batch evaluation")
    print("=" * 78)
    print()
    print(summarise(customers_list, payments))
    print()
    print(f"assumptions fingerprint  {assumptions_fingerprint()}")
    print("(if this hash changes, results from different runs are not comparable)")
    print()

    results, campaigns, ledgers = [], {}, {}
    for strategy in strategies:
        ledger = Ledger(run_id=f"run_{strategy.name}", strategy=strategy.name)
        traces, campaign = run_campaign(strategy, payments, customers, ledger,
                                        live_sample=live_sample)
        results.append(score(strategy.name, payments, traces))
        campaigns[strategy.name] = campaign
        ledgers[strategy.name] = ledger

    print("=" * 78)
    print(comparison_table(results))
    print("=" * 78)
    print()

    for result in results:
        print(result.strategy)
        print(detail(result))
        print()

    for strategy in strategies:
        budget = intelligence_budget(strategy)
        if budget:
            print(budget)
            print()

    last = strategies[-1].name
    campaign = campaigns[last]
    gateway = campaign.executor.gateway
    print(f"execution integrity ({last})")
    print(f"  gateway calls            {getattr(gateway, 'calls', 0):>4}")
    print(f"  transient gateway errors {campaign.executor.gateway_errors:>4}"
          "   (same idempotency key re-presented, no duplicate charge)")
    print(f"  duplicates suppressed    {campaign.executor.duplicate_suppressions:>4}")
    print(f"  distinct idempotency keys{len(campaign.executor.seen):>5}")
    print()
    print(provenance_report(campaign.executor))
    print()

    ledger = ledgers[last]
    print(f"ledger ({last}): {ledger.total()} events, append-only")
    for kind, count in ledger.counts_by_type().items():
        print(f"  {kind:<24}{count:>6}")
    print()

    if show_replay:
        print("=" * 78)
        print("SAMPLE TRANSACTION STORIES — reconstructed from the ledger alone")
        print("=" * 78)
        print()
        picked = []
        for kind in SAMPLE_EVENT_TYPES:
            ids = ledger.transactions_with(kind)
            if ids:
                picked.append(ids[0])
        for txn_id in dict.fromkeys(picked):
            print(render(ledger, txn_id))
            print()

    best = max(results, key=lambda r: r.net_paise)
    print(f"highest net return: {best.strategy}  (Rs {best.net_paise / 100:,.0f})")


if __name__ == "__main__":
    import sys

    from backend.config.mode import CredentialsMissing

    try:
        main()
    except CredentialsMissing as error:
        print(error)
        sys.exit(1)
