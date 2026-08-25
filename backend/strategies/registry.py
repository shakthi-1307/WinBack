"""The list of strategies the harness compares. Assembly only."""

from __future__ import annotations

from backend.strategies.base import Strategy
from backend.strategies.do_nothing import DoNothing
from backend.strategies.fixed_schedule import FixedSchedule
from backend.strategies.retry_thrice import RetryThriceImmediate
from backend.strategies.winback_agent import WinbackAgent
from backend.strategies.winback_rules import WinbackRules


def all_strategies() -> list[Strategy]:
    return [
        DoNothing(),
        RetryThriceImmediate(),
        FixedSchedule(),
        WinbackRules(),
        WinbackAgent(),
    ]
