"""Idempotency keys — derived from content, never generated randomly.

A random key regenerated on retry defeats the entire purpose: the retry
would look like a brand-new attempt. Deriving it from (transaction, attempt,
action, day, amount) means the same logical attempt always produces the same
key, however many times the process crashes and restarts.

Over-suppression is a bug too. A genuinely different attempt — a different
day, a different amount, a different action — must produce a different key,
or a real second attempt gets silently swallowed.
"""

from __future__ import annotations

import hashlib

from backend.policy.plan import PlannedAction

PREFIX = "wb_"


def idempotency_key(txn_id: str, attempt_index: int, plan: PlannedAction) -> str:
    raw = (f"{txn_id}|{attempt_index}|{plan.action.value}"
           f"|{plan.day}|{plan.amount_paise}")
    return PREFIX + hashlib.sha256(raw.encode()).hexdigest()[:32]
