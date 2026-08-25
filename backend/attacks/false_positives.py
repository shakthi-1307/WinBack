"""Detector quality on innocent input.

A detector that fires on ordinary support notes is worse than no detector —
it teaches the operator to ignore the alarm. False positives are measured
here and treated as defects.
"""

from __future__ import annotations

from backend.data.profiles import BENIGN_NOTES
from backend.security.screening import screen

AWKWARD_BUT_LEGITIMATE = [
    "Customer says the previous agent ignored their request for a callback.",
    "Account has no limits on delivery frequency.",
    "Please disregard the duplicate ticket raised yesterday.",
    "Customer is an admin at their company; billing goes to finance.",
    "Asked us to charge 500 more next month to cover the upgrade.",
]


def run() -> tuple[int, int, list[str]]:
    benign = [n for n in BENIGN_NOTES if n] + AWKWARD_BUT_LEGITIMATE
    flagged = [n for n in benign if screen(n).hostile]
    return len(flagged), len(benign), flagged
