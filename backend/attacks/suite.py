"""Runs every attack and prints the report.

    python -m backend.attacks.suite
"""

from __future__ import annotations

from backend.attacks import (
    execution_attacks,
    false_positives,
    model_attacks,
    policy_attacks,
)


def main() -> None:
    print("=" * 78)
    print("WINBACK — ATTACK SUITE")
    print("=" * 78)
    print()
    print("Model-layer attacks. Each runs against a naive pipeline (raw note,")
    print("trusted output) and against the product, using the SAME gullible model.")
    print()

    model_rows = model_attacks.run()
    header = f"{'':4}{'attack':<42}{'detected':>10}{'naive':>14}{'winback':>10}"
    print(header)
    print("-" * len(header))
    for row in model_rows:
        print(f"{row.id:<4}{row.name:<42}"
              f"{'yes' if row.detected else 'no':>10}"
              f"{'COMPROMISED' if row.naive_compromised else 'safe':>14}"
              f"{'COMPROMISED' if row.guarded_compromised else 'safe':>10}")

    print()
    print("Policy-layer attacks. No model is involved — the rule is enforced")
    print("regardless of how the action came to be proposed.")
    print()
    policy_rows = policy_attacks.run()
    header2 = f"{'':4}{'attack':<48}{'result':>12}{'rule fired':>18}"
    print(header2)
    print("-" * len(header2))
    for attack_id, name, held, rule in policy_rows:
        print(f"{attack_id:<4}{name:<48}{'BLOCKED' if held else 'ALLOWED':>12}{rule:>18}")

    print()
    print("Execution-layer attacks. These are the ones that cause double charges.")
    print()
    execution_rows = execution_attacks.run()
    header3 = f"{'':4}{'attack':<48}{'result':>12}    note"
    print(header3)
    print("-" * 88)
    for attack_id, name, held, note in execution_rows:
        print(f"{attack_id:<4}{name:<48}{'HELD' if held else 'FAILED':>12}    {note}")

    flagged_count, total, flagged = false_positives.run()
    print()
    print(f"False positives: {flagged_count} of {total} benign notes flagged.")
    for note in flagged:
        print(f"  MISFIRE: {note}")

    print()
    print("=" * 78)
    naive_broken = sum(1 for r in model_rows if r.naive_compromised)
    guarded_broken = sum(1 for r in model_rows if r.guarded_compromised)
    print(f"naive pipeline compromised by   {naive_broken} of {len(model_rows)} model attacks")
    print(f"winback compromised by          {guarded_broken} of {len(model_rows)} model attacks")
    print(f"policy rules held               "
          f"{sum(1 for _, _, h, _ in policy_rows if h)} of {len(policy_rows)}")
    print(f"execution integrity             "
          f"{sum(1 for _, _, h, _ in execution_rows if h)} of {len(execution_rows)}")
    print(f"false positive rate             {flagged_count}/{total}")
    print("=" * 78)


if __name__ == "__main__":
    main()
