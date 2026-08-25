"""Work waiting for a future day. A drawer, not a scheduler daemon."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from backend.policy.plan import PlannedAction


@dataclass
class Job:
    txn_id: str
    plan: PlannedAction


@dataclass
class JobQueue:
    _by_day: dict[int, list[Job]] = field(
        default_factory=lambda: defaultdict(list)
    )

    def schedule(self, day: int, job: Job) -> None:
        self._by_day[day].append(job)

    def due(self, day: int) -> list[Job]:
        return self._by_day.pop(day, [])

    def pending(self) -> int:
        return sum(len(jobs) for jobs in self._by_day.values())
