"""
Sensitivity analysis — the answer to "you wrote the world your agent wins in".

The frozen simulator encodes beliefs about how recovery works. The single
most load-bearing belief is that timing matters for money problems: that a
retry landing just after payday works far better than one landing the next
morning. Winback exploits that; the baselines cannot, because they never
look at the reason code.

So the fair question is: if that belief is wrong, does Winback still win?

This sweeps the payday multiplier from 1.0 (payday makes NO difference at
all — the strongest possible case against our design) up to 4.0, and prints
the ranking at each point. A result that only holds at the frozen value is a
result about the simulator. A result that holds across the sweep is a result
about the strategy.

    python -m eval.sensitivity
"""

from __future__ import annotations

import copy

from data.generator import generate
from eval import metrics
from eval.harness import run_campaign
from eval.strategies import ALL_STRATEGIES
from sim.simulator import _load_frozen, set_assumptions_override

SWEEP = [1.0, 1.5, 2.0, 2.5, 3.0, 3.6, 4.0]
FROZEN_VALUE = 3.6


def main() -> None:
    customers_list, payments = generate(400)
    customers = {c.id: c for c in customers_list}

    print("=" * 78)
    print("SENSITIVITY — how much does the result depend on the payday assumption?")
    print("=" * 78)
    print()
    print("payday multiplier 1.0 means payday timing makes no difference whatsoever.")
    print(f"The frozen assumption is {FROZEN_VALUE}.")
    print()

    header = f"{'multiplier':<12}" + "".join(f"{s.name:>22}" for s in ALL_STRATEGIES[1:])
    print(header)
    print("-" * len(header))

    rankings = []
    for mult in SWEEP:
        a = copy.deepcopy(_load_frozen())
        a["classes"]["timing"]["modifiers"]["payday_aligned"] = mult
        set_assumptions_override(a)

        row_results = []
        for strategy in ALL_STRATEGIES[1:]:
            traces, _ = run_campaign(strategy, payments, customers)
            row_results.append(metrics.score(strategy.name, payments, traces))

        marker = "  <- frozen" if mult == FROZEN_VALUE else ""
        cells = "".join(f"{r.recovered_count:>15} ({r.recovery_rate*100:4.1f}%)"[-22:] for r in row_results)
        print(f"{mult:<12.1f}{cells}{marker}")

        winner = max(row_results, key=lambda r: r.net_paise)
        rankings.append((mult, winner.strategy))

    set_assumptions_override(None)

    print()
    print("winner at each point:")
    for mult, winner in rankings:
        print(f"  payday x{mult:<5.1f}  {winner}")

    winners = {w for _, w in rankings}
    print()
    if len(winners) == 1:
        print(
            f"VERDICT: {winners.pop()} wins across the entire sweep, including the case\n"
            "where payday timing is assumed to make no difference at all. The result\n"
            "is a property of the strategy, not of the assumption."
        )
    else:
        print(
            "VERDICT: the ranking changes across the sweep. The result depends on the\n"
            "payday assumption and must be reported with that caveat, prominently."
        )


if __name__ == "__main__":
    main()
