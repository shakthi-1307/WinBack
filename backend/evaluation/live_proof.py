"""Proof that the Razorpay integration is real.

    python -m backend.evaluation.live_proof
    python -m backend.evaluation.live_proof --count 10

Takes a handful of failed payments from the batch and runs them through the
executor with the REAL Razorpay test-mode gateway. Prints the order IDs it
got back, which can be opened in the Razorpay dashboard.

This is deliberately separate from the measurement run. Fifty real calls
prove the integration works exactly as well as two thousand do, and the
strategy comparison has nothing to do with transport. Keeping them apart
makes both faster and both honest.
"""

from __future__ import annotations

import sys
import time

from backend.config.mode import CredentialsMissing, require_razorpay
from backend.data.generator import generate
from backend.domain.actions import Action
from backend.domain.classification import classify
from backend.executor.executor import Executor
from backend.executor.gateway_base import GatewayError
from backend.executor.razorpay_gateway import RazorpayGateway
from backend.policy.engine import PolicyEngine
from backend.policy.limits import AttemptState
from backend.policy.plan import PlannedAction

DEFAULT_COUNT = 5


def main() -> int:
    require_razorpay()

    count = DEFAULT_COUNT
    if "--count" in sys.argv:
        count = int(sys.argv[sys.argv.index("--count") + 1])

    customers_list, payments = generate()
    customers = {c.id: c for c in customers_list}

    # Only transactions the policy engine would actually allow a charge on.
    chargeable = [
        p for p in payments
        if p.mandate_valid
        and classify(p.reason_code).failure_class.value in {"timing", "transient_system"}
    ][:count]

    executor = Executor(gateway=RazorpayGateway())
    policy = PolicyEngine()

    print("=" * 74)
    print("LIVE RAZORPAY TEST-MODE PROOF")
    print("=" * 74)
    print()
    print(f"Attempting {len(chargeable)} real order creations against")
    print("https://api.razorpay.com/v1/orders — these IDs are real and can")
    print("be opened in the Razorpay dashboard under Test Mode.")
    print()

    succeeded = 0
    mismatches = 0
    started = time.perf_counter()

    for payment in chargeable:
        customer = customers[payment.customer_id]
        plan = PlannedAction(Action.RETRY_SCHEDULED, day=1,
                             amount_paise=payment.amount_paise)
        state = AttemptState(amount_paise_snapshot=payment.amount_paise)

        verdict = policy.check(plan, payment, customer, state)
        if not verdict.approved:
            print(f"  {payment.id}  refused by policy: {verdict.rule}")
            continue

        try:
            result = executor.execute(
                plan=plan, payment=payment, customer=customer,
                attempt_index=1,
                failure_class=classify(payment.reason_code).failure_class.value,
                payday_aligned=False,
            )
        except GatewayError as error:
            print(f"  {payment.id}  GATEWAY ERROR  {error}")
            continue

        if result.error:
            print(f"  {payment.id}  transport failed: {result.error}")
            continue

        gateway = result.gateway

        # Creating an order proves we sent something. Reading it back proves
        # Razorpay agrees what we sent. A wrong-units bug — rupees where paise
        # belong — survives creation happily and dies right here.
        try:
            fetched = executor.gateway.fetch_order(gateway.order_id)
            checks = {
                "amount": fetched.get("amount") == payment.amount_paise,
                "currency": fetched.get("currency") == "INR",
                "receipt": fetched.get("receipt") == payment.id[:40],
            }
            if all(checks.values()):
                verified = "verified"
            else:
                failed = ", ".join(k for k, ok in checks.items() if not ok)
                verified = f"MISMATCH on {failed} (got amount={fetched.get('amount')})"
                mismatches += 1
        except GatewayError as error:
            verified = f"fetch failed: {error}"
            mismatches += 1

        print(f"  {payment.id}  Rs {payment.amount_rupees:>7,.0f}  "
              f"{gateway.order_id}  {verified}")
        succeeded += 1

    elapsed = time.perf_counter() - started
    print()
    print(f"  {succeeded} of {len(chargeable)} real orders created in {elapsed:.1f}s")
    print(f"  read back and verified: {succeeded - mismatches} of {succeeded} "
          "(amount in paise, currency, receipt)")
    if mismatches:
        print("  MISMATCHES FOUND — the order Razorpay stored is not the one we meant")
    print()
    print("Note: creating the order is server-side and fully real. AUTHORISING")
    print("the payment needs either a client-side checkout or a saved token on")
    print("a registered mandate, which depends on how the sandbox account is")
    print("provisioned. Where that is unavailable it is recorded as unavailable")
    print("rather than faked.")
    return 0 if succeeded and not mismatches else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except CredentialsMissing as error:
        print(error)
        sys.exit(1)
