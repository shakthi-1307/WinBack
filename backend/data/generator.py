"""Generates the synthetic batch. Seeded, so every run is identical.

There is no public dataset of payment failures with recovery outcomes — that
data is confidential and PCI-regulated everywhere it exists. So the batch is
generated, and its realism comes from STRUCTURE rather than provenance: real
Razorpay reason codes, a plausible mix, real subscription price points, and
the customer attributes that actually drive recovery.
"""

from __future__ import annotations

import random

from backend.data.profiles import (
    ALL_NOTES,
    DEAD_MANDATE_RATE,
    DND_RATE,
    NOTE_WEIGHTS,
    PAYDAYS,
    PLANS,
)
from backend.data.reason_mix import REASON_MIX
from backend.domain.models import Channel, Customer, FailedPayment

SEED = 20260821
DEFAULT_SIZE = 400

CHANNEL_WEIGHTS = [(Channel.WHATSAPP, 52.0), (Channel.SMS, 30.0), (Channel.EMAIL, 18.0)]
TENURES = [(1, 24.0), (3, 26.0), (6, 22.0), (12, 18.0), (24, 10.0)]
PRIOR_FAILURES = [(0, 62.0), (1, 24.0), (2, 10.0), (4, 4.0)]


def _weighted(rng: random.Random, pairs):
    return rng.choices([p[0] for p in pairs], weights=[p[1] for p in pairs], k=1)[0]


def generate(n: int = DEFAULT_SIZE,
             seed: int = SEED) -> tuple[list[Customer], list[FailedPayment]]:
    rng = random.Random(seed)
    reason_pairs = list(REASON_MIX.items())

    customers: list[Customer] = []
    payments: list[FailedPayment] = []

    for i in range(n):
        customer_id = f"cust_{i:04d}"
        customers.append(Customer(
            id=customer_id,
            payday=int(_weighted(rng, PAYDAYS)),
            dnd=rng.random() < DND_RATE,
            preferred_channel=_weighted(rng, CHANNEL_WEIGHTS),
            tenure_months=int(_weighted(rng, TENURES)),
            prior_failures=int(_weighted(rng, PRIOR_FAILURES)),
        ))
        payments.append(FailedPayment(
            id=f"txn_{i:04d}",
            customer_id=customer_id,
            amount_paise=int(_weighted(rng, PLANS)),
            reason_code=str(_weighted(rng, reason_pairs)),
            failed_on_day=rng.randint(1, 28),
            mandate_valid=rng.random() > DEAD_MANDATE_RATE,
            support_note=rng.choices(ALL_NOTES, weights=NOTE_WEIGHTS, k=1)[0],
        ))

    return customers, payments
