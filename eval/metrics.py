"""Scoring. Gross recovery is the headline; the other columns are the story."""

from __future__ import annotations

from dataclasses import dataclass, field

from core.domain.models import FailedPayment, Trace

# Cost model. Rough but directionally right, and stated openly so it can be
# argued with.
GATEWAY_FEE_PAISE_PER_CHARGE = 200   # ~Rs 2 per attempted charge
MESSAGE_COST_PAISE = 30              # ~Rs 0.30 per message


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

    # -- derived -------------------------------------------------------

    @property
    def recovery_rate(self) -> float:
        return self.recovered_count / self.n if self.n else 0.0

    @property
    def value_recovery_rate(self) -> float:
        return self.recovered_paise / self.at_risk_paise if self.at_risk_paise else 0.0

    @property
    def cost_paise(self) -> int:
        return (
            self.charge_attempts * GATEWAY_FEE_PAISE_PER_CHARGE
            + self.contacts * MESSAGE_COST_PAISE
        )

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
        s = sorted(self.days_to_recovery)
        mid = len(s) // 2
        return float(s[mid]) if len(s) % 2 else (s[mid - 1] + s[mid]) / 2


def score(strategy_name: str, payments: list[FailedPayment], traces: dict[str, Trace]) -> Result:
    r = Result(strategy=strategy_name)
    contacted: set[str] = set()

    for p in payments:
        t = traces[p.id]
        r.n += 1
        r.at_risk_paise += p.amount_paise

        if t.recovered:
            r.recovered_count += 1
            r.recovered_paise += p.amount_paise
            if t.recovered_on_day is not None:
                r.days_to_recovery.append(t.recovered_on_day)
        if t.abandoned_on_day is not None:
            r.abandoned += 1

        for a in t.attempts:
            if a.is_charge:
                r.charge_attempts += 1
                if a.probability == 0.0:
                    r.impossible_charges += 1
                if a.damaged_issuer_trust:
                    r.issuer_trust_damage += 1
            if a.contacted_customer:
                r.contacts += 1
                contacted.add(p.customer_id)
                if not t.recovered:
                    r.wasted_contacts += 1

        for b in t.blocks:
            rule = b.split(":", 1)[0]
            r.blocks[rule] = r.blocks.get(rule, 0) + 1

    r.customers_contacted = len(contacted)
    return r


def table(results: list[Result]) -> str:
    """The four-strategy comparison — the first thing in the README."""
    head = (
        f"{'strategy':<22}{'recov':>7}{'rate':>8}{'Rs recovered':>15}"
        f"{'charges':>9}{'msgs':>7}{'impossible':>12}{'net Rs':>14}"
    )
    lines = [head, "-" * len(head)]
    for r in results:
        lines.append(
            f"{r.strategy:<22}"
            f"{r.recovered_count:>7}"
            f"{r.recovery_rate * 100:>7.1f}%"
            f"{r.recovered_paise / 100:>15,.0f}"
            f"{r.charge_attempts:>9}"
            f"{r.contacts:>7}"
            f"{r.impossible_charges:>12}"
            f"{r.net_paise / 100:>14,.0f}"
        )
    return "\n".join(lines)


def detail(r: Result) -> str:
    lines = [
        f"  value recovered          {r.value_recovery_rate * 100:.1f}% of rupees at risk",
        f"  attempts per Rs 1,000    {r.attempts_per_1k_recovered:.2f}",
        f"  median days to recovery  {r.median_days_to_recovery:.0f}",
        f"  wasted messages          {r.wasted_contacts}",
        f"  issuer trust damage      {r.issuer_trust_damage}",
        f"  actively abandoned       {r.abandoned}",
    ]
    if r.blocks:
        blocked = ", ".join(f"{k}={v}" for k, v in sorted(r.blocks.items()))
        lines.append(f"  policy blocks            {blocked}")
    else:
        lines.append("  policy blocks            none")
    return "\n".join(lines)
