"""Reporting which half of each attempt was real.

Winback makes two very different kinds of claim, and they must never be
allowed to blur:

    REAL       every gateway call is a live Razorpay test-mode request.
               Real auth, real order IDs, real error handling.

    MODELLED   whether a customer's bank would have approved is decided by
               the frozen simulator, because there are no real customers and
               no sandbox can answer that question.

Printing the split on every run means a reader never has to guess which is
which — and it makes it impossible to quietly overstate the first.
"""

from __future__ import annotations

from backend.executor.executor import Executor


def report(executor: Executor) -> str:
    live = executor.live_gateway_calls
    substituted = executor.substituted_gateway_calls
    total = live + substituted

    lines = ["provenance of this run"]
    if total == 0:
        lines.append("  no gateway calls were made")
    elif substituted == 0:
        lines.append(f"  gateway calls        {live} of {total} REAL "
                     "(live Razorpay test mode)")
    elif live == 0:
        lines.append(f"  gateway calls        {total} via transport double, 0 live")
        lines.append("                       (measurement run — decision quality does")
        lines.append("                       not depend on transport. Prove the")
        lines.append("                       integration with: python -m")
        lines.append("                       backend.evaluation.live_proof)")
    else:
        lines.append(f"  gateway calls        {live} REAL (live Razorpay test mode), "
                     f"{substituted} via transport double")

    lines += [
        "  bank approval        MODELLED by the frozen simulator",
        "                       (no sandbox can say whether a real customer "
        "would have paid)",
    ]
    return "\n".join(lines)
