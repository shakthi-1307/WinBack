"""How often each failure reason occurs.

An informed estimate for an Indian D2C subscription merchant, not a
measurement. Two properties matter more than the exact weights:

  * insufficient funds and generic declines dominate, as they do in reality
  * the "impossible to retry" codes are a small but non-trivial slice — and
    that slice is exactly where naive schedules burn money for zero return
"""

from __future__ import annotations

REASON_MIX: dict[str, float] = {
    "insufficient_funds": 22.0,
    "authentication_failed": 15.0,
    "payment_failed": 11.0,
    "card_declined": 7.0,
    "payment_timed_out": 9.0,
    "bank_technical_error": 7.0,
    "gateway_technical_error": 6.0,
    "card_expired": 6.0,
    "payment_cancelled": 6.0,
    "incorrect_cvv": 3.0,
    "transaction_limit_exceeded": 2.5,
    "payment_risk_check_failed": 2.0,
    "card_not_enrolled": 1.2,
    "debit_instrument_inactive": 1.0,
    "card_disabled_for_online_payments": 0.8,
    "debit_instrument_blocked": 0.5,
}
