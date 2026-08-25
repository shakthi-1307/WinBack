"""Every kind of thing that can be recorded.

Adding a case here is how the system is extended; there is no other way to
record anything.
"""

from __future__ import annotations

PLANNED = "planned"
BLOCKED = "blocked"
EXECUTED = "executed"
DUPLICATE_SUPPRESSED = "duplicate_suppressed"
GATEWAY_ERROR = "gateway_error"
RECOVERED = "recovered"
ABANDONED = "abandoned"
HOSTILE_NOTE = "hostile_note_seen"

ALL_TYPES = (PLANNED, BLOCKED, EXECUTED, DUPLICATE_SUPPRESSED,
             GATEWAY_ERROR, RECOVERED, ABANDONED, HOSTILE_NOTE)
