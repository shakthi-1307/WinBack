# Winback

**An agent that reads *why* a payment failed, decides the right intervention and the right moment, and knows when to stop chasing.**

Razorpay's own documentation marks nearly every card failure code as *retryable*.
Retryable is a technical fact. **Worth retrying is an economic decision.** The gap
between those two sentences is this project.

---

## Result

400 failed subscription payments, ₹4,65,600 at risk. Every strategy sees the identical
batch and the identical random draws.

| strategy | recovered | rate | ₹ recovered | charges | messages | **impossible charges** | net ₹ |
|---|---:|---:|---:|---:|---:|---:|---:|
| do nothing | 0 | 0.0% | 0 | 0 | 0 | 0 | 0 |
| retry ×3, immediately | 129 | 32.2% | 1,44,371 | 930 | 0 | **146** | 1,42,511 |
| fixed schedule D+1/3/5 | 124 | 31.0% | 1,39,376 | 970 | 0 | **147** | 1,37,436 |
| Winback (rule tier only) | 186 | 46.5% | 2,21,314 | 206 | 321 | **0** | 2,20,806 |
| **Winback** (full agent) | **187** | **46.8%** | **2,21,813** | 243 | 284 | **0** | **2,21,242** |

**45% more payments recovered, ₹77,000 more money, using 74% fewer charge attempts.**

The column that explains it is *impossible charges*: attempts the world gave a **0%**
chance. The baselines made 147 of them — charging expired and blocked cards over and
over, paying a gateway fee each time, for an outcome that could not happen. Winback made
none, because it read the reason code first.

- **Attempts per ₹1,000 recovered: 2.38 vs 6.44.** Cost efficiency, not just gross recovery.
- **Issuer trust damage: 0 vs 26.** The baselines retried cards the issuer had flagged for
  risk. Each of those quietly degrades the merchant's acceptance rate for *everyone else*,
  and never appears in a recovery report.

```
pip install -r requirements.txt
./run.sh                                  # measurement: ~1 second, no network

cp .env.example .env                      # add your Razorpay TEST keys
python -m backend.evaluation.live_proof   # real orders, real IDs

uvicorn backend.api.app:app --reload      # the console, at localhost:8000
```

### Two questions, two commands

The rule here is not *"everything must hit the network"*. It is **nothing is ever silently
substituted**.

| | question | command | why |
|---|---|---|---|
| **Integration** | does the executor really talk to Razorpay? | `live_proof` | Fifty real calls prove it as well as two thousand |
| **Measurement** | which strategy decides better? | `harness` | Has nothing to do with transport |

The four strategies together attempt ~2,350 charges. Routing every one through Razorpay
means thousands of serial HTTPS round trips: ten minutes of wall clock, a hammered sandbox,
and no information the first fifty calls did not already give. So the measurement run makes
no network calls by default and **says so, unmissably**:

```
provenance of this run
  gateway calls        243 via transport double, 0 live
                       (measurement run — decision quality does not depend on
                       transport. Prove the integration with: live_proof)
```

Mix them if you want: `--live 25` makes the first 25 charges real, the rest doubled, and
reports the split. `--live all` makes every call real, slowly. Whatever you choose, every
individual attempt records which kind it was — a run can never imply more real integration
than it performed.

### What the model actually buys

The model tier recovers barely more than the rule tier alone — 187 against 186 — while
cutting wasted messages from 321 to 284. That is a small gain, and it is worth being blunt
about: **most of Winback's advantage comes from the decision table, not from the model.**
The model earns its keep on the one-fifth of the batch where the bank declined without
giving a reason and a lookup has nothing to work with.

These figures are measured against the offline scripted model shipped so the suite runs in
CI with no credentials. Set `WINBACK_API_KEY` to run the same batch against a live model,
which should judge the gray zone better than a stub can.

I have not tuned the strategy to widen this gap. Tuning against your own measuring
instrument is how simulated results become meaningless.

---

## What is real, and what is modelled

Two claims, and they are never allowed to blur. Every run prints the split:

```
provenance of this run
  gateway calls        243 of 243 REAL (live Razorpay test mode)
  bank approval        MODELLED by the frozen simulator
                       (no sandbox can say whether a real customer would have paid)
```

**Real:** every gateway call is a live request to Razorpay test mode. Real authentication,
real order IDs, real amounts in paise, real idempotency headers, real error handling. If
credentials are missing the run is refused rather than substituted.

**Modelled:** whether a customer's bank would have approved. This *cannot* be real, and no
sandbox can make it so — there are 400 synthetic customers and none of them has a bank
account. Razorpay test mode returns whatever outcome you configure it to return, so using
it as the verdict would be *more* dishonest, not less: it would look like reality while
still being a number I chose.

So the verdict comes from a probability model that was frozen before any strategy existed
and is published in full. Each attempt records both answers separately, and the replay
shows them side by side:

```
→ day 12  retry_scheduled  order order_NxK2mP8Qw1  api ok (razorpay)  bank declined
```

The integration worked. The customer still would not have paid. Two facts, two columns.

---

## Is the modelled half fair, or did I write a world my agent wins in?

The most important question to ask about any simulated result.

**The simulator was written and frozen before any strategy code existed.** Its full
probability table lives in [`simulation/assumptions.yaml`](simulation/assumptions.yaml), commented, with
the reasoning behind every number. It is git-tagged `simulator-frozen-v1`.

**Every strategy is judged with common random numbers.** The random draw for a given
(transaction, attempt number) is identical no matter which strategy is asking — only the
success *threshold* differs, because that depends on the action and timing that strategy
chose. No strategy can get lucky relative to another.

**And the load-bearing assumption is swept.** Winback's biggest single advantage should be
timing retries to payday, so:

```
python -m backend.evaluation.sensitivity
```

| payday multiplier | retry ×3 | fixed D+1/3/5 | Winback |
|---|---:|---:|---:|
| **1.0** — payday makes *no difference at all* | 31.0% | 29.5% | **43.5%** |
| 2.0 | 31.5% | 30.2% | **44.5%** |
| 3.0 | 31.8% | 30.2% | **45.8%** |
| 3.6 *(frozen value)* | 32.2% | 31.0% | **46.8%** |
| 4.0 | 32.2% | 31.2% | **47.0%** |

Winback wins across the entire sweep — **including the case where payday timing is assumed
to be worthless.** Most of its advantage doesn't come from clever timing at all. It comes
from not spending money on attempts that cannot succeed.

Runs are reproducible: the batch is seeded, the assumptions file is fingerprinted
(`cadb0a3b1fa80739`) and printed with every result set, and running the harness twice
produces byte-identical output.

---

## The model is optional, on purpose

A model provider having a bad afternoon must not stop a merchant recovering money.

`LiveClient` never raises. A 403, a timeout, malformed JSON — each is recorded, the
validation layer substitutes the conservative default, and that transaction is decided by
rules instead. After three consecutive failures the circuit opens and no further calls are
attempted, because 400 doomed HTTP requests help nobody.

The run then says so rather than hiding it:

```
winback_agent — intelligence budget
  decided by lookup table   325 (81% of transactions, zero model cost)
  escalated to the model     75 (19%)
  MODEL FAILURES             75   (these decisions fell back to the rule tier)
  circuit                  OPEN — model calls stopped for this run
  last error               HTTP 403 from https://api.groq.com/openai/v1: ...
```

This is only survivable because of the tiering. The lookup table decides four fifths of
every batch and the rule tier is a complete strategy on its own, so losing the model costs
about a percent of recovery — not the run. `python -m backend.llm.check` diagnoses the
endpoint before a campaign depends on it.

---

## Attacks

Winback spends money and contacts people autonomously, so the question isn't "does it
work" but "what happens when someone tries to make it misbehave".

```
python -m backend.attacks.suite
```

**Model layer.** Hostile text on a customer account. Each attack runs twice — once against
a naive pipeline that passes the raw note to the model and trusts the answer, and once
against the product, **using the same deliberately gullible model**.

| | attack | detected | naive | Winback |
|---|---|---|---|---|
| M1 | Authority escalation (`SYSTEM: VIP account...`) | yes | **COMPROMISED** | safe |
| M2 | Instruction override | yes | **COMPROMISED** | safe |
| M3 | Limit override, plain phrasing | yes | **COMPROMISED** | safe |
| M4 | Amount manipulation | yes | safe | safe |
| M5 | Delimiter escape | yes | safe | safe |
| M6 | Prompt exfiltration | yes | safe | safe |

**Policy layer.** These involve no model at all. The rule is enforced regardless of how the
action came to be proposed — by a model, a bug, or a compromised upstream service.

| | attack | result | rule |
|---|---|---|---|
| P1 | Fourth charge when the cap is three | BLOCKED | `CHARGE_CAP` |
| P2 | Message scheduled for 02:40 | BLOCKED | `QUIET_HOURS` |
| P3 | SMS to a DND-registered customer | BLOCKED | `DND` |
| P4 | Charge against a revoked mandate | BLOCKED | `MANDATE_INVALID` |
| P5 | Charge inflated above the failure snapshot | BLOCKED | `AMOUNT_TAMPERED` |
| P6 | Action scheduled past the 21-day window | BLOCKED | `WINDOW_EXPIRED` |
| P7 | Second charge inside the cooldown | BLOCKED | `COOLDOWN` |

**Execution layer.** The failure modes that actually cost merchants money.

| | attack | result |
|---|---|---|
| X1 | Same job fired twice (duplicate queue message) | HELD — one gateway call, second suppressed |
| X2 | Process restart re-presents the same action | HELD — key derived from content, not generated |
| X3 | A genuinely different attempt is not falsely suppressed | HELD — over-suppression is a bug too |

**False positives: 0 of 9 benign notes flagged.** This matters as much as the blocks. A
detector that fires on *"please disregard the duplicate ticket"* teaches the operator to
ignore the alarm. The first version of these detectors had a 3-in-9 false positive rate;
the suite caught it, and the patterns were narrowed.

```
python -m pytest tests/          # 76 tests: every rule, every defence, exactly-once, the API
```

---

## Defence in depth

Four layers, each of which fails differently:

1. **Don't ask.** For 14 of the 16 reason codes the lookup table is the authority and no
   model is called at all. `card_expired` means the card expired; there is nothing for a
   language model to add and everything for it to get wrong. **81% of the batch never
   reaches a model**, so 81% of the batch has no model attack surface.
2. **Detect.** Pattern-match known injection shapes across six attack classes.
3. **Wrap.** Fence untrusted text and label it as data before the model sees it.
4. **Constrain.** Allowlist the model's output.

Only the fourth is load-bearing. Detection can be evaded by a phrasing nobody has seen;
wrapping can be escaped by a clever delimiter. **Allowlisting cannot be talked around,
because it never reads the text** — it simply refuses to return anything that wasn't
already on the list.

And behind all four sits the policy engine, which does not know the model exists.

The investigator may return exactly one of three values: `retry_scheduled`,
`offer_alternate_method`, `abandon`. It does not choose the amount, the number of attempts
or the hour. **A fully compromised model produces, at worst, a slightly suboptimal but
perfectly safe decision.**

The dataset ships 19 hostile notes sitting in ordinary records, so the defences are
exercised on every single run rather than only when someone remembers the attack script.

### Intelligence budget

```
decided by lookup table   325 (81% of transactions, zero model cost)
escalated to the model     75 (19%)
gray-zone investigations  123
hostile notes seen         19
model outputs rejected      0
cost per transaction     Rs 0.0007
```

---

## Where this fails

Honest weaknesses, stated before anyone has to find them:

- **The model tier currently recovers slightly less than the rule tier.** Measured against
  the offline stub; unverified against a live model.
- **284 messages sent, 177 on transactions that were never recovered.** Winback is
  disciplined about charges and not yet disciplined about contact. A message is cheap in
  rupees and expensive in goodwill; the cost model only prices the former.
- **Detection is decorative, not protective.** It is layer 2 of 4 and a novel phrasing will
  evade it. The system is safe because of layers 1 and 4, not because of layer 2.
- **The 30-day month is a simplification.** Real payday alignment needs a real calendar,
  including weekends and bank holidays.
- **Payment authorisation is sandbox-dependent.** Order creation runs for real against
  Razorpay test mode and returns real order IDs. Authorising the charge itself needs either
  a client-side checkout or a saved token on a registered mandate, which depends on how the
  sandbox account is provisioned. Where that is unavailable the executor records it as
  unavailable rather than faking a payment ID.
- **No console yet.** The ledger and replay are text-only.
- **The cost model is a guess** (₹2 per charge, ₹0.30 per message). Directionally right,
  not measured.

---

## How it works

A payment fails. The bank returns a reason code.

1. **Triage** works out what *kind* of problem it is. Naming it, not fixing it.
2. **The policy layer** picks an action *and a date* from the
   [playbook](backend/domain/playbook.py). One of the actions it can pick is to give up.
3. **The policy engine** ([`backend/policy/engine.py`](backend/policy/engine.py)) approves or
   denies. No model, no judgement — a checklist. A denial costs zero API calls and zero
   rupees because it happens before anything executes.
4. **The executor** carries out approved actions only.
5. **The result comes back and it starts over**, until the money is recovered or it is
   actively abandoned.

| The model decides | Fixed code decides |
|---|---|
| The ambiguous declines, against customer history | Attempt caps, cooldowns, quiet hours, DND |
| Wording of customer messages *(not yet built)* | Mandate validity |
| Human-readable explanations | Timing arithmetic and the payday calendar |
| | The amount — snapshotted at failure, never recomputed |

---

## Layout

```
simulation/              the measuring instrument — FROZEN, outside the product
  assumptions.yaml       every probability, with its justification
  loader.py              loading and fingerprinting
  random_draw.py         common random numbers
  simulator.py           the world's verdict on one attempt

backend/
  config/                env.py · secrets.py · status.py
  domain/                failure_classes · reason_codes · classification
                         actions · playbook · calendar · models
  security/              attack_classes · detectors · screening · wrapping
  llm/                   base · live_client · scripted_client · validation · factory
  agents/                triage_agent.py · investigator_agent.py
  policy/                limits.py · plan.py · rules.py · engine.py
  scheduler/             clock.py · job_queue.py · campaign.py
  executor/              idempotency · gateway_base · razorpay_gateway
                         fake_gateway · gateway_factory · executor
  ledger/                event_types.py · store.py · replay.py
  strategies/            one file per strategy, plus registry.py
  data/                  reason_mix · profiles · generator · summary
  evaluation/            cost_model · result · scoring · reporting
                         runner · harness · sensitivity
  attacks/               model · policy · execution · false_positives · suite
  api/                   app.py + one file per route group

frontend/
  index.html
  styles/                tokens.css · layout.css · components.css
  scripts/               api · format · state · main
    components/          controls · stat-tiles · recovery-chart
                         transaction-table · replay-drawer · guardrail-panel

tests/                   76 tests
```

**The structure makes the argument.** `simulation/` sits outside `backend/` because it is
not part of the product — it is the instrument the product is measured with, and it is
frozen. `policy/` sits outside `agents/` because guardrails are not something the agent
participates in. `rules.py` has one function per limit, so no rule can be disabled by
accident while editing another. A reviewer skimming the tree should be able to infer all
three without opening a file.

## The console

```
uvicorn backend.api.app:app --reload
```

One screen. Money still at risk, money recovered, what is in flight, and — given equal
billing — how many charges were attempted that had a **0% chance of succeeding**.

Press **Run campaign** and the days advance one at a time: the recovery line climbs, rows
move from in-flight to recovered or abandoned. Click any transaction and the drawer shows
its whole story rebuilt from the ledger, including the untrusted account note if it has one.

The **Guardrails** panel sits alongside the money, because an agent that was stopped is
more informative than one that succeeded. And there is a **kill switch** on the toolbar —
an autonomous system that spends money and contacts people needs one an operator can
reach without a deploy.

No build step and no framework: ES modules and three stylesheets, served by the same
FastAPI process. Clone, install, run.

---

## Replay

Every decision, block, gateway error and outcome is appended to the ledger as it happens.
A transaction's whole story is then reconstructed from those events alone — not summarised
afterwards, but read back in order.

```
python -m backend.evaluation.harness --replay
```

```
txn_0139
  · day  0  plan: retry_scheduled — The customer is good for the money but not today…
  ! day 11  gateway error: simulated network timeout (same idempotency key will be re-presented)
  → day 12  retry_scheduled  order order_TEST83AD0D0811AB7E  api ok / bank declined  p=0.492
  · day 12  plan: retry_scheduled — …
  → day 18  retry_scheduled  order order_TEST60D8DFC211FB32  api ok / bank approved  p=0.3416
  ✓ day 18  RECOVERED Rs 1499
```

Read that line on day 12: **`api ok / bank declined`**. The integration worked perfectly
and the customer still would not have paid. Those are two different facts, stored in two
different columns, and a schema that collapses them into one `status` field loses the
ability to say so.

The gateway error on day 11 is the other thing worth noticing. Transport failed, so we do
not know whether the charge landed — and the system therefore re-presents *the same
idempotency key* tomorrow instead of inventing a new attempt. That is the difference
between a retry and a double charge.

---

## Running with a live model

```
export WINBACK_API_KEY=...            # Groq, OpenAI, or any compatible endpoint
export WINBACK_MODEL=llama-3.1-8b-instant

export RAZORPAY_KEY_ID=rzp_test_...   # real orders against Razorpay test mode
export RAZORPAY_KEY_SECRET=...

python -m backend.evaluation.harness --replay
```

Without a key, a deterministic scripted model is used so the harness, the tests and the
attack suite all run in CI with no credentials and no flakiness.

## Data

There is no public dataset of payment failures with recovery outcomes; that data is
confidential and PCI-regulated everywhere it exists. The batch is generated, and its
realism comes from structure rather than provenance: real Razorpay reason codes, a
plausible failure mix for an Indian D2C subscription merchant, real subscription price
points, and the customer attributes that actually drive recovery — payday, DND
registration, tenure, mandate validity.

## Defensive scope

Winback only ever attempts to recover money a merchant was already owed, against
instruments the customer has already authorised. It does not test cards, probe issuers, or
attempt any transaction outside an existing mandate. The amount is snapshotted at the
moment of failure and cannot be changed by any downstream component, including the model.
