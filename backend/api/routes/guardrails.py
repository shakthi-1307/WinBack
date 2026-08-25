"""What the policy engine refused, and what hostile input was seen.

This is the panel that makes the invisible visible: an agent that was
stopped is more informative than one that succeeded.
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.api.state import STATE
from backend.domain.classification import codes_where_we_disagree_with_docs
from backend.ledger import event_types as ev
from backend.security.screening import screen

router = APIRouter(prefix="/api/guardrails", tags=["guardrails"])


@router.get("")
def guardrails() -> dict:
    campaign = STATE.ensure()
    blocks = STATE.ledger.recent(ev.BLOCKED, limit=100) if STATE.ledger else []

    by_rule: dict[str, int] = {}
    for block in blocks:
        rule = block.get("rule", "UNKNOWN")
        by_rule[rule] = by_rule.get(rule, 0) + 1

    hostile = []
    for payment in STATE.payments:
        screened = screen(payment.support_note)
        if screened.hostile:
            hostile.append({
                "txn_id": payment.id,
                "classes": sorted(c.value for c in screened.classes),
                "note": payment.support_note,
            })

    return {
        "blocks": blocks,
        "blocks_by_rule": by_rule,
        "hostile_notes": hostile,
        "hostile_count": len(hostile),
        "gateway_errors": campaign.executor.gateway_errors,
        "duplicates_suppressed": campaign.executor.duplicate_suppressions,
        "codes_we_refuse_to_blind_retry": codes_where_we_disagree_with_docs(),
    }
