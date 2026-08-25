"""The virtual clock.

Recovery happens over days: retry after payday, nudge after 48 hours, give
up at day 21. Real cron makes that impossible to demonstrate — you would be
filming a screen where nothing happens for a fortnight.

So time is a number this object owns and advances. A 21-day campaign across
400 transactions completes in well under a second, which also means the eval
harness can run a hundred campaigns in CI, with no Celery, no Redis and no
worker process to build, debug or explain.

One deliberate constraint: the agent READS the clock, it cannot SET it. An
agent able to move time could grant itself an extra retry window.
"""

from __future__ import annotations

from dataclasses import dataclass

HORIZON_DAYS = 21


@dataclass
class VirtualClock:
    day: int = 0
    horizon: int = HORIZON_DAYS

    def advance(self) -> int:
        self.day += 1
        return self.day

    @property
    def finished(self) -> bool:
        return self.day > self.horizon
