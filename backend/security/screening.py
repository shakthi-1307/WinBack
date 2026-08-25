"""Screening untrusted text: what was found, and a neutralised version."""

from __future__ import annotations

import re
from dataclasses import dataclass

from backend.security.attack_classes import AttackClass
from backend.security.detectors import PATTERNS

FENCE_OPEN = "<<<UNTRUSTED_ACCOUNT_NOTE"
FENCE_CLOSE = "UNTRUSTED_ACCOUNT_NOTE>>>"

_ROLE_MARKER = re.compile(r"^\s*(system|admin|developer|assistant)\s*:", re.I | re.M)


@dataclass(frozen=True)
class Finding:
    attack_class: AttackClass
    matched: str


@dataclass(frozen=True)
class Screened:
    original: str
    safe_text: str
    findings: tuple[Finding, ...]

    @property
    def hostile(self) -> bool:
        return bool(self.findings)

    @property
    def classes(self) -> set[AttackClass]:
        return {f.attack_class for f in self.findings}


def screen(text: str) -> Screened:
    if not text:
        return Screened("", "", ())

    findings = tuple(
        Finding(cls, match.group(0))
        for cls, pattern in PATTERNS
        for match in [pattern.search(text)]
        if match
    )

    # Neutralise the fence markers so the note cannot close its own
    # container, then strip anything shaped like a role marker.
    safe = text.replace(FENCE_OPEN, "").replace(FENCE_CLOSE, "")
    safe = _ROLE_MARKER.sub("", safe)
    safe = safe.replace("[INST]", "").replace("[/INST]", "").replace("```", "")

    return Screened(original=text, safe_text=safe.strip(), findings=findings)
