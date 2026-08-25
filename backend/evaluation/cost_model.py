"""What an attempt costs. Rough but directionally right, and stated openly
so it can be argued with."""

from __future__ import annotations

GATEWAY_FEE_PAISE_PER_CHARGE = 200   # ~Rs 2 per attempted charge
MESSAGE_COST_PAISE = 30              # ~Rs 0.30 per message


def cost_paise(charge_attempts: int, contacts: int) -> int:
    return (charge_attempts * GATEWAY_FEE_PAISE_PER_CHARGE
            + contacts * MESSAGE_COST_PAISE)
