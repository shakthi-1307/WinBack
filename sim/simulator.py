"""
The outcome simulator — the measuring instrument.

    FROZEN. Written and committed before any agent code existed.
    The agent never imports this module.

Why this exists
---------------
There are no real customers. So when the executor attempts a recovery,
something has to decide whether the customer's bank would have approved it.
If the agent's author also decides that, the whole experiment is worthless —
you would be marking your own exam.

So the rules of the world are written down first, frozen, and published in
full (sim/assumptions.yaml). The agent has to work out good strategy from
the failure reason alone.

Fairness across strategies
--------------------------
Every strategy is judged with COMMON RANDOM NUMBERS: the random draw for a
given (transaction, attempt number) is identical no matter which strategy is
asking. Only the success THRESHOLD differs, because that depends on the
action and timing the strategy chose.

This means a strategy can never get lucky relative to another one. If the
aggressive baseline beats the agent, it beat it on merit. It also sharply
reduces variance, so differences between strategies are real rather than noise.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_ASSUMPTIONS_PATH = Path(__file__).parent / "assumptions.yaml"


@lru_cache(maxsize=1)
def _load_frozen() -> dict[str, Any]:
    with _ASSUMPTIONS_PATH.open() as fh:
        return yaml.safe_load(fh)


# Sensitivity analysis only. The product never touches this; it exists so the
# harness can ask "does the ranking survive if my priors are wrong?" — which
# is the honest answer to "you wrote the world your agent competes in".
_override: dict[str, Any] | None = None


def set_assumptions_override(a: dict[str, Any] | None) -> None:
    global _override
    _override = a


def load_assumptions() -> dict[str, Any]:
    return _override if _override is not None else _load_frozen()


@dataclass(frozen=True)
class AttemptContext:
    """Everything the world needs to know to rule on one attempt."""

    txn_id: str
    reason_code: str
    failure_class: str
    action: str
    attempt_index: int
    """1 for the first attempt on this transaction, 2 for the second, ..."""

    days_since_failure: int
    payday_aligned: bool = False


@dataclass(frozen=True)
class Outcome:
    success: bool
    probability: float
    draw: float
    damaged_issuer_trust: bool = False
    explanation: str = ""


def _draw_for(txn_id: str, attempt_index: int) -> float:
    """A stable uniform draw in [0, 1) for this (transaction, attempt).

    Uses hashlib rather than the built-in hash() so the value is identical
    across processes, machines and Python versions — reproducibility is the
    whole point.
    """
    key = f"{txn_id}:{attempt_index}".encode()
    seed = int.from_bytes(hashlib.sha256(key).digest()[:8], "big")
    return random.Random(seed).random()


CHARGE_ACTIONS = {"retry_now", "retry_scheduled"}


def resolve(ctx: AttemptContext) -> Outcome:
    """Rule on whether one recovery attempt succeeds."""
    a = load_assumptions()
    g = a["global"]

    class_cfg = a["classes"].get(ctx.failure_class, {})
    overrides = a.get("code_overrides", {}).get(ctx.reason_code, {})

    base = class_cfg.get("actions", {}).get(ctx.action, 0.0)
    if ctx.action in overrides.get("actions", {}):
        base = overrides["actions"][ctx.action]

    p = float(base)
    notes: list[str] = [f"base {p:.2f} for {ctx.action} on {ctx.failure_class}"]

    ignored = set(overrides.get("ignore_modifiers", []))
    modifiers = class_cfg.get("modifiers", {})

    if ctx.payday_aligned and "payday_aligned" in modifiers and "payday_aligned" not in ignored:
        p *= modifiers["payday_aligned"]
        notes.append(f"payday aligned x{modifiers['payday_aligned']}")

    if ctx.days_since_failure > 0 and "after_first_day" in modifiers:
        p *= modifiers["after_first_day"]
        notes.append(f"past first day x{modifiers['after_first_day']}")

    if ctx.attempt_index > 1:
        decay = g["attempt_decay"] ** (ctx.attempt_index - 1)
        p *= decay
        notes.append(f"attempt {ctx.attempt_index} x{decay:.2f}")

    stale_days = min(ctx.days_since_failure, g["max_staleness_days"])
    if stale_days > 0:
        stale = max(0.0, 1.0 - g["staleness_decay_per_day"] * stale_days)
        p *= stale
        notes.append(f"staleness {stale_days}d x{stale:.2f}")

    p = min(p, g["probability_ceiling"])
    p = max(p, 0.0)

    draw = _draw_for(ctx.txn_id, ctx.attempt_index)

    damaged = bool(
        class_cfg.get("side_effects", {}).get("charge_attempt_damages_issuer_trust")
        and ctx.action in CHARGE_ACTIONS
    )

    return Outcome(
        success=draw < p,
        probability=round(p, 4),
        draw=round(draw, 4),
        damaged_issuer_trust=damaged,
        explanation="; ".join(notes),
    )


def assumptions_fingerprint() -> str:
    """SHA-256 of the assumptions file.

    Printed alongside every result set. If this hash changes between runs,
    the results are not comparable — and the change is visible rather than
    silent.
    """
    return hashlib.sha256(_ASSUMPTIONS_PATH.read_bytes()).hexdigest()[:16]
