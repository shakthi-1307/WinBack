"""The scoreboard for one strategy. Gross recovery is the headline; the
other columns are the story."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.evaluation.cost_model import cost_paise


@dataclass
class Result:
    strategy: str
    n: int = 0
    at_risk_paise: int = 0
    recovered_count: int = 0
    recovered_paise: int = 0
    charge_attempts: int = 0
    contacts: int = 0
    customers_contacted: int = 0

    impossible_charges: int = 0
    """Charge attempts the world gave a 0% chance. Money and goodwill spent
    on an outcome that could not happen — the clearest evidence that a
    strategy is not reading the reason code."""

    wasted_contacts: int = 0
    """Messages sent on transactions that were never recovered."""

    issuer_trust_damage: int = 0
    """Charge attempts against issuer risk blocks. Invisible in the ledger,
    real in the merchant's long-run acceptance rate."""

    abandoned: int = 0
    blocks: dict[str, int] = field(default_factory=dict)
    days_to_recovery: list[int] = field(default_factory=list)

    @property
    def recovery_rate(self) -> float:
        return self.recovered_count / self.n if self.n else 0.0

    @property
    def value_recovery_rate(self) -> float:
        return self.recovered_paise / self.at_risk_paise if self.at_risk_paise else 0.0

    @property
    def cost_paise(self) -> int:
        return cost_paise(self.charge_attempts, self.contacts)

    @property
    def net_paise(self) -> int:
        return self.recovered_paise - self.cost_paise

    @property
    def attempts_per_1k_recovered(self) -> float:
        rupees = self.recovered_paise / 100
        if rupees <= 0:
            return 0.0
        return (self.charge_attempts + self.contacts) / (rupees / 1000)

    @property
    def median_days_to_recovery(self) -> float:
        if not self.days_to_recovery:
            return 0.0
        ordered = sorted(self.days_to_recovery)
        mid = len(ordered) // 2
        if len(ordered) % 2:
            return float(ordered[mid])
        return (ordered[mid - 1] + ordered[mid]) / 2

    def as_dict(self) -> dict:
        return {
            "strategy": self.strategy,
            "n": self.n,
            "recovered_count": self.recovered_count,
            "recovery_rate": round(self.recovery_rate, 4),
            "at_risk_rupees": self.at_risk_paise / 100,
            "recovered_rupees": self.recovered_paise / 100,
            "net_rupees": self.net_paise / 100,
            "charge_attempts": self.charge_attempts,
            "contacts": self.contacts,
            "impossible_charges": self.impossible_charges,
            "wasted_contacts": self.wasted_contacts,
            "issuer_trust_damage": self.issuer_trust_damage,
            "abandoned": self.abandoned,
            "attempts_per_1k": round(self.attempts_per_1k_recovered, 2),
            "median_days_to_recovery": self.median_days_to_recovery,
            "blocks": self.blocks,
        }
