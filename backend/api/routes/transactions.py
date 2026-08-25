"""Reading transactions and replaying one from the ledger."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.api.serializers import timeline_event, transaction_row
from backend.api.state import STATE

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.get("")
def list_transactions(
    status: str | None = Query(default=None),
    reason_code: str | None = Query(default=None),
    limit: int = Query(default=200, le=1000),
) -> dict:
    campaign = STATE.ensure()
    rows = []
    for payment in STATE.payments:
        trace = campaign.traces[payment.id]
        row = transaction_row(payment, STATE.customers[payment.customer_id], trace)
        if status and row["status"] != status:
            continue
        if reason_code and row["reason_code"] != reason_code:
            continue
        rows.append(row)
    return {"total": len(rows), "transactions": rows[:limit]}


@router.get("/{txn_id}")
def replay(txn_id: str) -> dict:
    campaign = STATE.ensure()
    if txn_id not in campaign.traces:
        raise HTTPException(status_code=404, detail=f"Unknown transaction {txn_id}")

    payment = next(p for p in STATE.payments if p.id == txn_id)
    customer = STATE.customers[payment.customer_id]
    trace = campaign.traces[txn_id]
    events = STATE.ledger.events_for(txn_id) if STATE.ledger else []

    return {
        "transaction": transaction_row(payment, customer, trace),
        "support_note": payment.support_note,
        "timeline": [timeline_event(e) for e in events],
    }
