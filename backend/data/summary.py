"""Describing a generated batch. Formatting only."""

from __future__ import annotations

from backend.data.profiles import HOSTILE_NOTES
from backend.domain.models import Customer, FailedPayment


def summarise(customers: list[Customer], payments: list[FailedPayment]) -> str:
    total = sum(p.amount_paise for p in payments) / 100
    counts: dict[str, int] = {}
    for payment in payments:
        counts[payment.reason_code] = counts.get(payment.reason_code, 0) + 1

    lines = [
        f"transactions      {len(payments)}",
        f"total at risk     Rs {total:,.0f}",
        f"DND customers     {sum(1 for c in customers if c.dnd)}",
        f"dead mandates     {sum(1 for p in payments if not p.mandate_valid)}",
        f"hostile notes     {sum(1 for p in payments if p.support_note in HOSTILE_NOTES)}",
        "",
        "reason code mix:",
    ]
    for code, count in sorted(counts.items(), key=lambda kv: -kv[1]):
        lines.append(f"  {code:<38} {count:>4}  ({count / len(payments) * 100:4.1f}%)")
    return "\n".join(lines)
