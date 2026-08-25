"""A proposed action, and the verdict on it."""

from __future__ import annotations

from dataclasses import dataclass

from backend.domain.actions import Action
from backend.domain.models import Channel


@dataclass
class PlannedAction:
    action: Action
    day: int
    """Days since the original failure."""
    hour: int = 10
    channel: Channel | None = None
    amount_paise: int = 0
    rationale: str = ""


@dataclass
class Verdict:
    approved: bool
    rule: str = ""
    reason: str = ""
