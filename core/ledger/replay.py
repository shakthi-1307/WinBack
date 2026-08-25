"""
Replay — reconstruct a transaction's whole story from its events.

Nothing here holds state. Everything shown was appended at the moment it
happened, which is what makes the account trustworthy: it is not a summary
written afterwards, it is the record itself, read back in order.

This is the text version. The console renders the same events as a timeline.
"""

from __future__ import annotations

from core.ledger import events as ev
from core.ledger.events import Ledger

_GLYPH = {
    ev.PLANNED: "·",
    ev.BLOCKED: "✕",
    ev.EXECUTED: "→",
    ev.DUPLICATE_SUPPRESSED: "=",
    ev.GATEWAY_ERROR: "!",
    ev.RECOVERED: "✓",
    ev.ABANDONED: "◻",
    ev.HOSTILE_NOTE: "⚑",
}


def render(ledger: Ledger, txn_id: str) -> str:
    rows = ledger.events_for(txn_id)
    if not rows:
        return f"{txn_id}: no events"

    out = [f"{txn_id}"]
    for e in rows:
        glyph = _GLYPH.get(e["type"], " ")
        day = f"day {e['day']:>2}"
        out.append(f"  {glyph} {day}  {_describe(e)}")
    return "\n".join(out)


def _describe(e: dict) -> str:
    t = e["type"]

    if t == ev.HOSTILE_NOTE:
        return f"account note flagged: {', '.join(e.get('classes', []))} — treated as data"

    if t == ev.PLANNED:
        why = e.get("rationale", "")
        why = (why[:88] + "…") if len(why) > 89 else why
        return f"plan: {e.get('action')} — {why}"

    if t == ev.BLOCKED:
        return f"BLOCKED by {e.get('rule')} — {e.get('reason', '')}"

    if t == ev.GATEWAY_ERROR:
        return f"gateway error: {e.get('error')} (same idempotency key will be re-presented)"

    if t == ev.DUPLICATE_SUPPRESSED:
        return f"duplicate suppressed on key {e.get('key')} — no second charge"

    if t == ev.EXECUTED:
        bits = [f"{e.get('action')}"]
        if e.get("order_id"):
            bits.append(f"order {e['order_id']}")
        api = "api ok" if e.get("gateway_accepted") else "no gateway call"
        behaviour = "bank approved" if e.get("success") else "bank declined"
        bits.append(f"{api} / {behaviour}")
        bits.append(f"p={e.get('probability')}")
        return "  ".join(bits)

    if t == ev.RECOVERED:
        return f"RECOVERED Rs {e.get('amount_rupees')}"

    if t == ev.ABANDONED:
        return f"stopped — {e.get('reason', '')}"

    return t
