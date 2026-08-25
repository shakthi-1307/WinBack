"""Sensitivity analysis — the answer to "you wrote the world your agent wins in".

The frozen simulator encodes beliefs about how recovery works. The most
load-bearing belief is that timing matters for money problems. Winback
exploits that; the baselines cannot, because they never read the reason code.

So the fair question is: if that belief is wrong, does Winback still win?

This sweeps the payday multiplier from 1.0 — payday makes NO difference at
all, the strongest possible case against the design — up to 4.0. A result
that only holds at the frozen value is a result about the simulator. A result
that holds across the sweep is a result about the strategy.

    python -m backend.evaluation.sensitivity
"""

from __future__ import annotations

import copy

from backend.data.generator import generate
from backend.evaluation.runner import run_campaign
from backend.evaluation.scoring import score
from backend.strategies.registry import all_strategies
from simulation.loader import _load_frozen, set_assumptions_override

SWEEP = [1.0, 1.5, 2.0, 2.5, 3.0, 3.6, 4.0]
FROZEN_VALUE = 3.6


def main() -> None:
    customers_list, payments = generate()
    customers = {c.id: c for c in customers_list}
    contenders = all_strategies()[1:]

    print("=" * 78)
    print("SENSITIVITY — how much does the result depend on the payday assumption?")
    print("=" * 78)
    print()
    print("payday multiplier 1.0 means payday timing makes no difference whatsoever.")
    print(f"The frozen assumption is {FROZEN_VALUE}.")
    print()

    header = f"{'multiplier':<12}" + "".join(f"{s.name:>22}" for s in contenders)
    print(header)
    print("-" * len(header))

    rankings = []
    for multiplier in SWEEP:
        assumptions = copy.deepcopy(_load_frozen())
        assumptions["classes"]["timing"]["modifiers"]["payday_aligned"] = multiplier
        set_assumptions_override(assumptions)

        row = []
        for strategy in contenders:
            traces, _ = run_campaign(strategy, payments, customers)
            row.append(score(strategy.name, payments, traces))

        marker = "  <- frozen" if multiplier == FROZEN_VALUE else ""
        cells = "".join(
            f"{r.recovered_count:>15} ({r.recovery_rate * 100:4.1f}%)"[-22:] for r in row
        )
        print(f"{multiplier:<12.1f}{cells}{marker}")
        rankings.append((multiplier, max(row, key=lambda r: r.net_paise).strategy))

    set_assumptions_override(None)

    print()
    print("winner at each point:")
    for multiplier, winner in rankings:
        print(f"  payday x{multiplier:<5.1f}  {winner}")

    winners = {w for _, w in rankings}
    print()
    if len(winners) == 1:
        print(f"VERDICT: {winners.pop()} wins across the entire sweep, including the\n"
              "case where payday timing is assumed to make no difference at all. The\n"
              "result is a property of the strategy, not of the assumption.")
    else:
        print("VERDICT: the ranking changes across the sweep. The result depends on\n"
              "the payday assumption and must be reported with that caveat.")


if __name__ == "__main__":
    main()
