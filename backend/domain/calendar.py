"""Calendar arithmetic. Deliberately not a model decision.

Simplified to a 30-day month; a production build would use the real
calendar including weekends and bank holidays.
"""

from __future__ import annotations

PAYDAY_WINDOW_DAYS = 3


def day_of_month(failed_on_day: int, days_since: int) -> int:
    return ((failed_on_day - 1 + days_since) % 30) + 1


def days_until_payday(current_day: int, payday: int) -> int:
    if payday > current_day:
        return payday - current_day
    return (30 - current_day) + payday


def lands_in_payday_window(failed_on_day: int, payday: int, days_since: int) -> bool:
    """True if an attempt this many days later falls just after payday.

    Salary lands on a fixed date for most Indian salaried customers, so this
    is a calendar question, not a prediction.
    """
    day = day_of_month(failed_on_day, days_since)
    return any(
        day == ((payday - 1 + offset) % 30) + 1
        for offset in range(PAYDAY_WINDOW_DAYS + 1)
    )
