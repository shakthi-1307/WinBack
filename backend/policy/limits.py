"""The hard limits, as data. Changing behaviour means changing this file."""

from __future__ import annotations

from dataclasses import dataclass

from backend.domain.models import Channel


@dataclass(frozen=True)
class Limits:
    max_charge_attempts: int = 3
    max_contacts: int = 3
    min_days_between_charges: int = 1
    quiet_hours_start: int = 21
    quiet_hours_end: int = 9
    max_recovery_window_days: int = 21

    dnd_blocked_channels: frozenset = frozenset(
        {Channel.SMS, Channel.VOICE, Channel.WHATSAPP}
    )
    """DND registration covers calls and SMS. Email is not in its scope, so
    it stays available — a real distinction, not a loophole."""


@dataclass
class AttemptState:
    """What has already happened to one transaction."""

    charges_used: int = 0
    contacts_used: int = 0
    last_charge_day: int | None = None
    days_elapsed: int = 0
    amount_paise_snapshot: int = 0
