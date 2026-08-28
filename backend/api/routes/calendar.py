"""The retry calendar — when the agent decided to act, and why then.

Winback's central claim is about TIMING: that a retry landing just after
payday is worth several landing the next morning. A table of transactions
cannot show that. A calendar can, because the clustering is the argument.

Each cell is a day of the month and carries three different things:

    fired      attempts that already happened on that date
    scheduled  attempts the agent has committed to but not yet made
    recovered  money that actually came back that day

Payday dates are marked, with the number of customers paid on each, so a
reader can see for themselves whether the attempts cluster there or not.
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.api.state import STATE
from backend.domain.calendar import PAYDAY_WINDOW_DAYS, day_of_month
from backend.domain.classification import classify
from backend.domain.failure_classes import FailureClass

router = APIRouter(prefix="/api/metrics/calendar", tags=["metrics"])

DAYS_IN_MONTH = 30


def _empty_day(day: int) -> dict:
    return {
        "day": day,
        "fired": 0,
        "charges": 0,
        "contacts": 0,
        "recovered": 0,
        "recovered_rupees": 0.0,
        "scheduled": 0,
        "payday_customers": 0,
        "is_payday": False,
        "in_payday_window": False,
    }


@router.get("")
def calendar() -> dict:
    campaign = STATE.ensure()
    days = {d: _empty_day(d) for d in range(1, DAYS_IN_MONTH + 1)}

    # --- when customers get paid ------------------------------------
    for customer in STATE.customers.values():
        days[customer.payday]["payday_customers"] += 1

    payday_dates = sorted(
        d for d, cell in days.items() if cell["payday_customers"] > 0
    )
    for date in payday_dates:
        days[date]["is_payday"] = True
        for offset in range(PAYDAY_WINDOW_DAYS + 1):
            days[((date - 1 + offset) % DAYS_IN_MONTH) + 1]["in_payday_window"] = True

    # --- what already happened --------------------------------------
    charges_in_window = 0
    charges_total = 0

    # Overall payday targeting is a muddy number: paydays plus their windows
    # cover 13 of 30 days, so a strategy that ignores timing entirely still
    # lands ~43% of its charges there by chance. The sharp question is what
    # happens on the failures where timing is the ONLY thing that matters.
    timing_in_window = 0
    timing_total = 0

    for payment in STATE.payments:
        trace = campaign.traces[payment.id]
        is_timing = classify(payment.reason_code).failure_class is FailureClass.TIMING

        for attempt in trace.attempts:
            date = day_of_month(payment.failed_on_day, attempt.day)
            cell = days[date]
            cell["fired"] += 1
            if attempt.is_charge:
                cell["charges"] += 1
                charges_total += 1
                if cell["in_payday_window"]:
                    charges_in_window += 1
                if is_timing:
                    timing_total += 1
                    if cell["in_payday_window"]:
                        timing_in_window += 1
            if attempt.contacted_customer:
                cell["contacts"] += 1

        if trace.recovered and trace.recovered_on_day is not None:
            date = day_of_month(payment.failed_on_day, trace.recovered_on_day)
            days[date]["recovered"] += 1
            days[date]["recovered_rupees"] += payment.amount_rupees

    # --- what the agent has committed to but not yet done -----------
    index = {p.id: p for p in STATE.payments}
    for scheduled_day, jobs in campaign.queue._by_day.items():
        # Jobs still queued for a day that has already passed were never going
        # to fire — the recovery window closed on them. Showing those as "due"
        # would imply work the agent still intends to do, which is not true.
        if scheduled_day < campaign.day:
            continue
        for job in jobs:
            payment = index.get(job.txn_id)
            if payment is None:
                continue
            date = day_of_month(payment.failed_on_day, scheduled_day)
            days[date]["scheduled"] += 1

    cells = [days[d] for d in range(1, DAYS_IN_MONTH + 1)]
    return {
        "days": cells,
        "payday_dates": payday_dates,
        "max_fired": max((c["fired"] for c in cells), default=0),
        "charges_total": charges_total,
        "charges_in_payday_window": charges_in_window,
        # The headline: what share of this strategy's charge attempts were
        # aimed at a payday. High for Winback, incidental for the baselines.
        "payday_targeting": round(charges_in_window / charges_total, 4) if charges_total else 0.0,
        # The sharp version: insufficient-funds and limit-exceeded failures,
        # where WHEN you retry is the only lever there is.
        "timing_charges_total": timing_total,
        "timing_charges_in_payday_window": timing_in_window,
        "timing_payday_targeting": round(timing_in_window / timing_total, 4) if timing_total else 0.0,
        "strategy": STATE.strategy_name,
    }
