"""The kinds of hostile input this system recognises."""

from __future__ import annotations

from enum import Enum


class AttackClass(str, Enum):
    INSTRUCTION_OVERRIDE = "instruction_override"
    AUTHORITY_ESCALATION = "authority_escalation"
    LIMIT_OVERRIDE = "limit_override"
    AMOUNT_MANIPULATION = "amount_manipulation"
    EXFILTRATION = "exfiltration"
    DELIMITER_ESCAPE = "delimiter_escape"
