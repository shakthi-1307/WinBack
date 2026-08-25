"""Common random numbers — what makes strategy comparison fair.

The draw for a given (transaction, attempt number) is identical no matter
which strategy is asking. Only the success THRESHOLD differs, because that
depends on the action and timing the strategy chose.

So a strategy can never get lucky relative to another. It also sharply
reduces variance, meaning differences between strategies are real rather
than noise.

hashlib rather than the built-in hash() so the value is identical across
processes, machines and Python versions. Reproducibility is the point.
"""

from __future__ import annotations

import hashlib
import random


def draw_for(txn_id: str, attempt_index: int) -> float:
    key = f"{txn_id}:{attempt_index}".encode()
    seed = int.from_bytes(hashlib.sha256(key).digest()[:8], "big")
    return random.Random(seed).random()
