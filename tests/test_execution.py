"""
Execution-layer tests: exactly-once, the two-layer split, and the ledger.

These cover the failure modes that cost real merchants real money — double
charges, lost attempts, and audit trails that cannot be trusted.
"""

from __future__ import annotations

import pytest

from core.domain.models import Channel, Customer, FailedPayment
from core.domain.playbook import Action
from core.executor.executor import Executor, idempotency_key
from core.executor.gateway import FakeGateway, GatewayError
from core.ledger import events as ev
from core.ledger.events import Ledger
from core.ledger.replay import render
from core.policy.engine import PlannedAction

SNAPSHOT = 149900


@pytest.fixture
def customer():
    return Customer("c1", payday=1, dnd=False, preferred_channel=Channel.SMS,
                    tenure_months=12, prior_failures=0)


@pytest.fixture
def payment():
    return FailedPayment("t1", "c1", SNAPSHOT, "insufficient_funds", 28, True)


def plan(day=3, amount=SNAPSHOT, action=Action.RETRY_SCHEDULED):
    return PlannedAction(action, day=day, amount_paise=amount)


def kw(payment, customer):
    return dict(payment=payment, customer=customer, attempt_index=1,
                failure_class="timing", payday_aligned=False)


# --- exactly once ---------------------------------------------------------


def test_firing_the_same_job_twice_charges_once(payment, customer):
    ex = Executor(gateway=FakeGateway(failure_rate=0.0))
    first = ex.execute(plan=plan(), **kw(payment, customer))
    second = ex.execute(plan=plan(), **kw(payment, customer))

    assert first.executed and not first.replayed
    assert second.replayed and not second.executed
    assert ex.gateway.calls == 1, "the gateway must be called exactly once"


def test_idempotency_key_is_derived_not_random(payment, customer):
    """A key regenerated on retry defeats the entire purpose — the retry
    would look like a brand-new attempt."""
    assert idempotency_key("t1", 1, plan()) == idempotency_key("t1", 1, plan())


@pytest.mark.parametrize(
    "other",
    [plan(day=7), plan(amount=99900), plan(action=Action.RETRY_NOW)],
)
def test_genuinely_different_attempts_get_different_keys(other):
    """Over-suppression is a bug too: a real second attempt must not be
    silently swallowed."""
    assert idempotency_key("t1", 1, plan()) != idempotency_key("t1", 1, other)


def test_a_replayed_result_returns_the_original_outcome(payment, customer):
    ex = Executor(gateway=FakeGateway(failure_rate=0.0))
    first = ex.execute(plan=plan(), **kw(payment, customer))
    second = ex.execute(plan=plan(), **kw(payment, customer))
    assert second.outcome == first.outcome
    assert second.gateway == first.gateway


# --- transport failure ----------------------------------------------------


def test_gateway_error_records_no_attempt(payment, customer):
    """When transport fails we do not know whether the charge landed, so no
    attempt is recorded and nothing is cached — the same key gets presented
    again rather than a new attempt being invented."""
    ex = Executor(gateway=FakeGateway(failure_rate=1.0))
    result = ex.execute(plan=plan(), **kw(payment, customer))
    assert not result.executed
    assert result.error
    assert result.key not in ex.seen


# --- the two layers must stay separate ------------------------------------


def test_api_success_and_bank_approval_are_recorded_separately(payment, customer):
    """'The integration worked and the customer still would not have paid'
    must remain expressible. Collapsing these into one status field loses
    the distinction the whole results table depends on."""
    ex = Executor(gateway=FakeGateway(failure_rate=0.0))
    r = ex.execute(plan=plan(), **kw(payment, customer))
    assert r.gateway is not None and r.gateway.accepted is True
    assert r.outcome is not None
    assert isinstance(r.outcome.success, bool)
    # Independent: gateway acceptance says nothing about bank approval.
    assert r.gateway.accepted is True


def test_contact_actions_make_no_gateway_call(payment, customer):
    ex = Executor(gateway=FakeGateway(failure_rate=0.0))
    ex.execute(plan=plan(action=Action.NUDGE_FIX_INSTRUMENT), **kw(payment, customer))
    assert ex.gateway.calls == 0, "sending a message must not touch the payment gateway"


# --- the ledger -----------------------------------------------------------


def test_ledger_is_append_only():
    """There is no update and no delete. Not an oversight — the property."""
    led = Ledger()
    assert not hasattr(led, "update")
    assert not hasattr(led, "delete")


def test_a_transaction_story_can_be_rebuilt_from_events_alone():
    led = Ledger()
    led.append(0, "t1", ev.PLANNED, action="retry_scheduled", rationale="payday")
    led.append(3, "t1", ev.EXECUTED, action="retry_scheduled", success=True,
               probability=0.54, order_id="order_TESTX", gateway_accepted=True)
    led.append(3, "t1", ev.RECOVERED, amount_rupees=1499)
    led.commit()

    story = render(led, "t1")
    assert "retry_scheduled" in story
    assert "order_TESTX" in story
    assert "RECOVERED" in story
    assert story.index("plan:") < story.index("RECOVERED"), "events must replay in order"


def test_events_are_scoped_per_run():
    led = Ledger(run_id="a")
    led.append(0, "t1", ev.PLANNED, action="x")
    led.commit()
    other = Ledger(path=":memory:", run_id="b")
    assert other.total() == 0
