"""Printing results. Formatting only — no counting happens here."""

from __future__ import annotations

from backend.evaluation.result import Result


def comparison_table(results: list[Result]) -> str:
    header = (f"{'strategy':<22}{'recov':>7}{'rate':>8}{'Rs recovered':>15}"
              f"{'charges':>9}{'msgs':>7}{'impossible':>12}{'net Rs':>14}")
    lines = [header, "-" * len(header)]
    for r in results:
        lines.append(
            f"{r.strategy:<22}{r.recovered_count:>7}{r.recovery_rate * 100:>7.1f}%"
            f"{r.recovered_paise / 100:>15,.0f}{r.charge_attempts:>9}"
            f"{r.contacts:>7}{r.impossible_charges:>12}{r.net_paise / 100:>14,.0f}"
        )
    return "\n".join(lines)


def detail(result: Result) -> str:
    lines = [
        f"  value recovered          {result.value_recovery_rate * 100:.1f}% of rupees at risk",
        f"  attempts per Rs 1,000    {result.attempts_per_1k_recovered:.2f}",
        f"  median days to recovery  {result.median_days_to_recovery:.0f}",
        f"  wasted messages          {result.wasted_contacts}",
        f"  issuer trust damage      {result.issuer_trust_damage}",
        f"  actively abandoned       {result.abandoned}",
    ]
    if result.blocks:
        blocked = ", ".join(f"{k}={v}" for k, v in sorted(result.blocks.items()))
        lines.append(f"  policy blocks            {blocked}")
    else:
        lines.append("  policy blocks            none")
    return "\n".join(lines)


def intelligence_budget(strategy) -> str:
    telemetry = getattr(strategy, "telemetry", None)
    if not telemetry:
        return ""
    total = telemetry["table_decisions"] + telemetry["model_decisions"]
    if not total:
        return ""
    usage = strategy.client.usage
    lines = [
        f"{strategy.name} — intelligence budget",
        f"  decided by lookup table  {telemetry['table_decisions']:>4} "
        f"({telemetry['table_decisions'] / total * 100:.0f}% of transactions, zero model cost)",
        f"  escalated to the model   {telemetry['model_decisions']:>4} "
        f"({telemetry['model_decisions'] / total * 100:.0f}%)",
        f"  gray-zone investigations {telemetry['investigations']:>4}",
        f"  hostile notes seen       {telemetry['hostile_notes_seen']:>4}",
        f"  model outputs rejected   {telemetry['output_rejections']:>4}",
        f"  model calls              {usage.calls:>4}",
    ]
    if usage.calls:
        lines.append(f"  cost per transaction     Rs {usage.cost_paise / 100 / total:.4f}")

    if getattr(usage, "failures", 0):
        lines.append(f"  MODEL FAILURES           {usage.failures:>4}"
                     "   (these decisions fell back to the rule tier)")
        if getattr(usage, "circuit_open", False):
            lines.append("  circuit                  OPEN — model calls stopped for this run")
        lines.append(f"  last error               {usage.last_error}")
    return "\n".join(lines)
