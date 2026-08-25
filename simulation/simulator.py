"""The outcome simulator — the measuring instrument.

    FROZEN. Written and committed before any agent code existed.
    Nothing under backend/ imports this module.

There are no real customers, so something has to decide whether a bank
would have approved an attempt. If the agent's author also decides that,
the experiment is worthless. So the rules of the world were written down
first, frozen, and published in full in assumptions.yaml.
"""

from __future__ import annotations

from dataclasses import dataclass

from simulation.loader import load_assumptions
from simulation.random_draw import draw_for

CHARGE_ACTIONS = {"retry_now", "retry_scheduled"}


@dataclass(frozen=True)
class AttemptContext:
    txn_id: str
    reason_code: str
    failure_class: str
    action: str
    attempt_index: int
    days_since_failure: int
    payday_aligned: bool = False


@dataclass(frozen=True)
class Outcome:
    success: bool
    probability: float
    draw: float
    damaged_issuer_trust: bool = False
    explanation: str = ""


def resolve(ctx: AttemptContext) -> Outcome:
    assumptions = load_assumptions()
    globals_ = assumptions["global"]

    class_cfg = assumptions["classes"].get(ctx.failure_class, {})
    overrides = assumptions.get("code_overrides", {}).get(ctx.reason_code, {})

    probability = float(class_cfg.get("actions", {}).get(ctx.action, 0.0))
    if ctx.action in overrides.get("actions", {}):
        probability = float(overrides["actions"][ctx.action])

    notes = [f"base {probability:.2f} for {ctx.action} on {ctx.failure_class}"]
    ignored = set(overrides.get("ignore_modifiers", []))
    modifiers = class_cfg.get("modifiers", {})

    if (ctx.payday_aligned and "payday_aligned" in modifiers
            and "payday_aligned" not in ignored):
        probability *= modifiers["payday_aligned"]
        notes.append(f"payday aligned x{modifiers['payday_aligned']}")

    if ctx.days_since_failure > 0 and "after_first_day" in modifiers:
        probability *= modifiers["after_first_day"]
        notes.append(f"past first day x{modifiers['after_first_day']}")

    if ctx.attempt_index > 1:
        decay = globals_["attempt_decay"] ** (ctx.attempt_index - 1)
        probability *= decay
        notes.append(f"attempt {ctx.attempt_index} x{decay:.2f}")

    stale_days = min(ctx.days_since_failure, globals_["max_staleness_days"])
    if stale_days > 0:
        staleness = max(0.0, 1.0 - globals_["staleness_decay_per_day"] * stale_days)
        probability *= staleness
        notes.append(f"staleness {stale_days}d x{staleness:.2f}")

    probability = max(0.0, min(probability, globals_["probability_ceiling"]))
    draw = draw_for(ctx.txn_id, ctx.attempt_index)

    damaged = bool(
        class_cfg.get("side_effects", {}).get("charge_attempt_damages_issuer_trust")
        and ctx.action in CHARGE_ACTIONS
    )

    return Outcome(
        success=draw < probability,
        probability=round(probability, 4),
        draw=round(draw, 4),
        damaged_issuer_trust=damaged,
        explanation="; ".join(notes),
    )
