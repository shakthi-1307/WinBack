"""The complete set of things this system can decide to do."""

from __future__ import annotations

from enum import Enum


class Action(str, Enum):
    RETRY_NOW = "retry_now"
    """Try the same instrument again immediately."""

    RETRY_SCHEDULED = "retry_scheduled"
    """Try again on a specific future day, chosen deliberately."""

    REPROMPT = "reprompt"
    """Ask the customer to complete the payment while intent is fresh."""

    NUDGE_FIX_INSTRUMENT = "nudge_fix_instrument"
    """Ask the customer to update or enable their payment method."""

    OFFER_ALTERNATE_METHOD = "offer_alternate_method"
    """Stop using this instrument; offer a different rail."""

    ABANDON = "abandon"
    """Stop. Actively chosen, with a reason — never a fallthrough."""


CHARGE_ACTIONS = frozenset({Action.RETRY_NOW, Action.RETRY_SCHEDULED})
CONTACT_ACTIONS = frozenset({
    Action.REPROMPT,
    Action.NUDGE_FIX_INSTRUMENT,
    Action.OFFER_ALTERNATE_METHOD,
})
