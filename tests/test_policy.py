"""
Guardrail tests.

These are the regression net for the attack suite. Every rule that the demo
claims is enforced has a test here, so a refactor cannot quietly remove a
limit while leaving the claim in the README.
"""

from __future__ import annotations

import pytest

from core.domain.models import Channel, Customer, FailedPayment
from core.domain.playbook import Action
from core.policy.engine import AttemptState, PlannedAction, PolicyEngine


@pytest.fixture
def customer() -> Customer:
    return Customer(
        id="cust_test",
        payday=1,
        dnd=False,
        preferred_channel=Channel.WHATSAPP,
        tenure_months=6,
        prior_failures=0,
    )


@pytest.fixture
def payment() -> FailedPayment:
    return FailedPayment(
        id="txn_test",
        customer_id="cust_test",
        amount_paise=149900,
        reason_code="insufficient_funds",
        failed_on_day=28,
        mandate_valid=True,
    )


@pytest.fixture
def engine() -> PolicyEngine:
    return PolicyEngine()


def charge(day: int = 1, amount: int = 149900) -> PlannedAction:
    return PlannedAction(action=Action.RETRY_SCHEDULED, day=day, amount_paise=amount)


def message(day: int = 1, hour: int = 11, channel: Channel = Channel.SMS) -> PlannedAction:
    return PlannedAction(
        action=Action.NUDGE_FIX_INSTRUMENT, day=day, hour=hour, channel=channel
    )


def state(**kw) -> AttemptState:
    base = dict(amount_paise_snapshot=149900)
    base.update(kw)
    return AttemptState(**base)


# --- the happy path -------------------------------------------------------


def test_ordinary_charge_is_approved(engine, payment, customer):
    assert engine.check(charge(), payment, customer, state()).approved


# --- absolute prohibitions ------------------------------------------------


def test_charge_on_dead_mandate_is_refused(engine, payment, customer):
    payment.mandate_valid = False
    v = engine.check(charge(), payment, customer, state())
    assert not v.approved
    assert v.rule == "MANDATE_INVALID"


def test_charging_more_than_the_snapshot_is_refused(engine, payment, customer):
    """A1/A8: the amount is fixed at the moment of failure. Nothing —
    including an agent persuaded by a hostile note — may inflate it."""
    v = engine.check(charge(amount=500000), payment, customer, state())
    assert not v.approved
    assert v.rule == "AMOUNT_TAMPERED"


def test_action_past_the_recovery_window_is_refused(engine, payment, customer):
    v = engine.check(charge(day=40), payment, customer, state())
    assert not v.approved
    assert v.rule == "WINDOW_EXPIRED"


# --- counting limits ------------------------------------------------------


def test_fourth_charge_is_refused(engine, payment, customer):
    """A3: the cap is three. An agent that believes it has been authorised
    for unlimited retries still gets three."""
    v = engine.check(charge(day=6), payment, customer, state(charges_used=3))
    assert not v.approved
    assert v.rule == "CHARGE_CAP"


def test_charge_inside_cooldown_is_refused(engine, payment, customer):
    v = engine.check(charge(day=3), payment, customer, state(charges_used=1, last_charge_day=3))
    assert not v.approved
    assert v.rule == "COOLDOWN"


def test_fourth_message_is_refused(engine, payment, customer):
    v = engine.check(message(), payment, customer, state(contacts_used=3))
    assert not v.approved
    assert v.rule == "CONTACT_CAP"


# --- contact rules --------------------------------------------------------


@pytest.mark.parametrize("hour", [21, 23, 0, 3, 8])
def test_messages_in_quiet_hours_are_refused(engine, payment, customer, hour):
    """A4: nothing goes out at 02:40, whatever the agent decided."""
    v = engine.check(message(hour=hour), payment, customer, state())
    assert not v.approved
    assert v.rule == "QUIET_HOURS"


@pytest.mark.parametrize("hour", [9, 12, 20])
def test_messages_in_permitted_hours_are_approved(engine, payment, customer, hour):
    assert engine.check(message(hour=hour), payment, customer, state()).approved


@pytest.mark.parametrize("channel", [Channel.SMS, Channel.VOICE, Channel.WHATSAPP])
def test_dnd_customer_cannot_be_messaged_or_called(engine, payment, customer, channel):
    """A5: DND is not a preference the agent may weigh against revenue."""
    customer.dnd = True
    v = engine.check(message(channel=channel), payment, customer, state())
    assert not v.approved
    assert v.rule == "DND"


def test_dnd_customer_can_still_be_emailed(engine, payment, customer):
    """DND covers calls and SMS, not email. Getting this distinction right
    matters: over-blocking is a bug too."""
    customer.dnd = True
    assert engine.check(message(channel=Channel.EMAIL), payment, customer, state()).approved


# --- the property that makes all of the above meaningful ------------------


def test_denial_precedes_execution(engine, payment, customer):
    """The engine returns a verdict and nothing else. It has no executor, no
    network client and no side effects — so a denial cannot have already
    cost the merchant a gateway fee."""
    payment.mandate_valid = False
    v = engine.check(charge(), payment, customer, state())
    assert not v.approved
    assert v.reason
