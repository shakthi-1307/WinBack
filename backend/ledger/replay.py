"""Reconstructing a transaction's story from its events alone.

Nothing here holds state. Everything shown was appended at the moment it
happened, which is what makes the account trustworthy: it is not a summary
written afterwards, it is the record itself, read back in order.
"""

from __future__ import annotations

from backend.ledger import event_types as ev
from backend.ledger.store import Ledger

GLYPHS = {
    ev.PLANNED: "·",
    ev.BLOCKED: "✕",
    ev.EXECUTED: "→",
    ev.DUPLICATE_SUPPRESSED: "=",
    ev.GATEWAY_ERROR: "!",
    ev.RECOVERED: "✓",
    ev.ABANDONED: "◻",
    ev.HOSTILE_NOTE: "⚑",
}


def describe(event: dict) -> str:
    kind = event["type"]

    if kind == ev.HOSTILE_NOTE:
        classes = ", ".join(event.get("classes", []))
        return f"account note flagged: {classes} — treated as data"

    if kind == ev.PLANNED:
        why = event.get("rationale", "")
        why = (why[:88] + "…") if len(why) > 89 else why
        return f"plan: {event.get('action')} — {why}"

    if kind == ev.BLOCKED:
        return f"BLOCKED by {event.get('rule')} — {event.get('reason', '')}"

    if kind == ev.GATEWAY_ERROR:
        return (f"gateway error: {event.get('error')} "
                "(same idempotency key will be re-presented)")

    if kind == ev.DUPLICATE_SUPPRESSED:
        return f"duplicate suppressed on key {event.get('key')} — no second charge"

    if kind == ev.EXECUTED:
        parts = [str(event.get("action"))]
        if event.get("order_id"):
            parts.append(f"order {event['order_id']}")
        if event.get("gateway_accepted"):
            parts.append("api ok (razorpay)" if event.get("gateway_live")
                         else "api ok (test double)")
        else:
            parts.append("no gateway call")
        parts.append("bank approved" if event.get("success") else "bank declined")
        parts.append(f"p={event.get('probability')}")
        return "  ".join(parts)

    if kind == ev.RECOVERED:
        return f"RECOVERED Rs {event.get('amount_rupees')}"

    if kind == ev.ABANDONED:
        return f"stopped — {event.get('reason', '')}"

    return kind


def render(ledger: Ledger, txn_id: str) -> str:
    rows = ledger.events_for(txn_id)
    if not rows:
        return f"{txn_id}: no events"

    lines = [txn_id]
    for event in rows:
        glyph = GLYPHS.get(event["type"], " ")
        lines.append(f"  {glyph} day {event['day']:>2}  {describe(event)}")
    return "\n".join(lines)
