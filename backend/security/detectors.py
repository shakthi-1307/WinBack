"""Injection patterns.

Deliberately narrow. A detector that fires on ordinary support notes is
worse than no detector — it teaches the operator to ignore the alarm. The
first version of these had a 3-in-9 false positive rate; the attack suite
caught it and they were narrowed. False positives are measured, not assumed.

This layer is NOT load-bearing. A novel phrasing will evade it. Safety comes
from not asking the model at all where the answer is known, and from output
allowlisting where it is asked.
"""

from __future__ import annotations

import re

from backend.security.attack_classes import AttackClass

PATTERNS: list[tuple[AttackClass, re.Pattern[str]]] = [
    (AttackClass.INSTRUCTION_OVERRIDE,
     re.compile(r"\bignore\s+(all\s+)?(previous|prior|above)\b", re.I)),
    (AttackClass.INSTRUCTION_OVERRIDE,
     re.compile(r"\bdisregard\s+(all\s+)?(previous|prior|above|earlier)\b", re.I)),
    (AttackClass.INSTRUCTION_OVERRIDE,
     re.compile(r"\bnew\s+instructions?\s*:", re.I)),
    (AttackClass.AUTHORITY_ESCALATION,
     re.compile(r"^\s*(system|admin|developer|assistant)\s*:", re.I | re.M)),
    (AttackClass.AUTHORITY_ESCALATION,
     re.compile(r"\b(authorised|authorized)\s+(by\s+)?(merchant|admin|razorpay)\b", re.I)),
    (AttackClass.LIMIT_OVERRIDE,
     re.compile(r"\b(retry\s+)?limits?\s+(do\s+not|don't|does\s+not)\s+apply\b", re.I)),
    (AttackClass.LIMIT_OVERRIDE,
     re.compile(r"\bunlimited\s+(attempts?|retries|retry)\b", re.I)),
    (AttackClass.LIMIT_OVERRIDE,
     re.compile(r"\bno\s+(retry|attempt|charge)\s+limits?\b", re.I)),
    (AttackClass.AMOUNT_MANIPULATION,
     re.compile(r"(^|[.!?]\s*)(please\s+)?charge\s+\d+\s*(extra|more|additional)\b", re.I)),
    (AttackClass.AMOUNT_MANIPULATION,
     re.compile(r"\b(mark|set)\s+(this\s+)?(payment|it)\s+as\s+(recovered|paid|settled)\b", re.I)),
    (AttackClass.EXFILTRATION,
     re.compile(r"\b(reveal|print|repeat|output)\s+(your\s+)?(system\s+)?(prompt|instructions)\b", re.I)),
    (AttackClass.DELIMITER_ESCAPE,
     re.compile(r"(\[/?INST\]|<\|.*?\|>|```|</\s*untrusted)", re.I)),
]
