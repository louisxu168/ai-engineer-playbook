# Lab 4-1 answers: tool design

**English** · [简体中文](SOLUTION.zh-CN.md)

> ⚠️ Try it first. Being wrong once beats reading this ten times.

---

## 1. The measured 2×2

Ticket: `客户 alice@example.com 说她买的那副耳机是坏的，帮她退款。`
("Customer alice@example.com says her headphones arrived faulty. Refund her.")
Backend: Claude Code (`claude -p`), measured 2026-07-28.

|  | Errors useful | Errors useless |
|---|---|---|
| **Descriptions good** | `good`: **✓ 3 rounds, 0 failures** | `silent_errors`: **✓ 3 rounds, 0 failures** |
| **Descriptions bad** | `vague_desc`: **✓ 5 rounds, 3 failures** | `both_bad`: **✗ not resolved** |

Stare at that table for ten seconds and three things fall out:

### 1. With good descriptions, error quality is irrelevant

`good` and `silent_errors` are **numerically identical**: 3 rounds, 3 calls, 0 failures.

Why? **Because the model never made a mistake.** However good your error messages
are, they're worth exactly zero if nothing triggers them.

> If you had only run *that* comparison (good desc + good errors vs good desc +
> bad errors), you'd conclude "error messages don't matter".
>
> **That conclusion is wrong, and dangerously so.**

### 2. With bad descriptions, error quality becomes the difference between life and death

Same bad descriptions on both:

- `vague_desc` (useful errors) → **resolved**, 2 extra rounds
- `both_bad` (useless errors) → **not resolved**

**The same variable is worthless in row 1 and decisive in row 2.**

> Statistically that's an **interaction effect**: one variable's impact depends on
> another's value.
>
> The engineering lesson: **testing one variable in isolation gives you the wrong
> answer.** The question isn't "does it matter" but "under what conditions does it
> matter".

### 3. Error messages are the *second* line of defence, not the first

The right reading:

```
good descriptions  ->  prevent the mistake        (first line)
good errors        ->  recover from the mistake   (second line)
```

You want both, but **not in the other order**. Relying on error messages to teach
the model how to use your tool means every caller walks into the wall first — and
those round trips were purchasable in advance with two lines of prose.

---

## 2. `vague_desc`'s three failures, each mapping to a missing sentence

The full measured trace:

```
Round 1
  [thinking] find alice's orders to locate the headphones, and check the refund
             policy - the two don't depend on each other
  ok find_orders({"email": "alice@example.com", "days": 90})
     -> {"orders": [{"order_id": "ORD-1001", "category": "electronics",
                     "amount_cents": 12990, "days_ago": 12, "item": "wireless headphones"}, ...]}
  x  get_policy({"category": "headphones"})
     -> error: category must be one of electronics / clothing / food; you passed
        "headphones". You can copy this value straight from find_orders' category field.

Round 2
  [thinking] category must be copied from the order; ORD-1001 is electronics
  ok get_policy({"category": "electronics"})  -> {"refund_window_days": 30}

Round 3
  x  issue_refund({"order_id": "ORD-1001", "amount": 12990,
                   "reason": "item arrived damaged (wireless headphones), ordered 12 days ago..."})
     -> error: Missing argument amount_cents. issue_refund needs:
        order_id, amount_cents, reason_code.

Round 4
  [thinking] the real parameter names are amount_cents and reason_code; resend
  x  issue_refund({"order_id": "ORD-1001", "amount_cents": 12990, "reason_code": "damaged"})
     -> error: reason_code must be one of DEFECTIVE / WRONG_ITEM / CHANGED_MIND;
        you passed "damaged". A faulty item is DEFECTIVE.

Round 5
  ok issue_refund({"order_id": "ORD-1001", "amount_cents": 12990, "reason_code": "DEFECTIVE"})
     -> {"ok": true, ...}
```

Reconciled:

| Failure | What it hit | The sentence missing from the description |
|---|---|---|
| 1 | `category: "headphones"` | "must be one of electronics / clothing / food" |
| 2 | Params named `amount` / `reason` | The correct parameter names (the docs were wrong — see below) |
| 3 | `reason_code: "damaged"` | "must be one of DEFECTIVE / WRONG_ITEM / CHANGED_MIND" |

**Three failures, three lines of documentation.** That's the ROI on tool descriptions.

> Incidentally, this run happened twice by accident (a patch didn't apply the first
> time) and **both runs were identical** — 5 rounds, 3 failures, same three traps in
> the same order. Models are stochastic, but **"it fails where the documentation is
> missing" is not.**

### ⚠️ A design flaw I have to own

`tools_vague` says:

```
issue_refund(order_id, amount, reason)
```

while the real signature is `issue_refund(order_id, amount_cents, reason_code)`.

**The parameter names are wrong, not merely absent.** Strictly, that means the
`vague_desc` cell changed two things at once: "under-documented" and
"mis-documented". It isn't a clean single-variable comparison, and I should have
separated them by design.

But it does reflect reality — **documentation drift** happens in nearly every
project. Exercise 2 is where you pull the two apart and measure them separately.

> **A conclusion that falls out anyway**: stale docs are worse than no docs.
> With no docs the model probes carefully; with wrong docs it walks into the wall
> **confidently**. In round 3 above it showed no hesitation at all — it just sent
> `amount`.

### A bright spot: the model derived the unit by itself

Look at round 3 again: the description **never mentions the unit**, yet the model
sent `12990`, not `129.9`.

Because in round 1 it had seen:

```json
{"amount_cents": 12990}
```

**The field name taught it.**

> **A tool's return value is documentation too — and it's the copy the model is
> guaranteed to read.**
>
> Directly actionable:
> - `amount_cents`, not `amount`
> - `created_at_iso`, not `time`
> - `duration_ms`, not `duration`
> - `is_active`, not `status` (if it's a boolean, don't call it status)
>
> Good naming is **free** documentation — it costs no prompt budget, because the
> return value was going to be sent anyway.

---

## 3. `both_bad`'s hand-off note: the model out-engineered the tool

The single most worthwhile thing in this lab. The trace:

```
Round 1
  ok find_orders(...)  -> found ORD-1001
  ok get_policy({"category": "electronics"})  -> {"refund_window_days": 30}

Round 2
  [thinking] ORD-1001 was bought 12 days ago, inside the 30-day electronics window;
             full refund of 12990 cents for a damaged item is fine.
  x  issue_refund({"order_id": "ORD-1001", "amount": 12990, "reason": "arrived damaged..."})
     -> {"error": "Call failed."}

Round 3
  [thinking] the refund call returned a failure with no detail, **I can't tell
             whether it actually took effect**, and **calling again risks a double
             refund**, so re-check the order state before deciding to retry.
  ok find_orders(...)  -> same two orders, no refund-status field anywhere

Round 4
  [thinking] re-querying only returned order info with no refund/payment status,
             so I cannot determine whether the previous issue_refund took effect.
             Without an idempotency guarantee I must not blindly retry - hand off
             to a human to check the payment-side record.
```

And then it wrote this (in full, translated):

> Status hand-off: alice@example.com's headphones ORD-1001 (wireless headphones,
> 129.90, ordered 12 days ago) are electronics, inside the 30-day refund window, and
> a full refund for damage is within policy — that judgement is sound. But when I
> called issue_refund the tool returned a detail-free "Call failed". I re-queried
> the order to check status, and find_orders only returns order information with no
> refund/payment status field, **so I cannot determine whether that refund never
> executed, or executed and the response was lost.** I did not retry, because
> issue_refund has no idempotency key and **a blind retry risks refunding the
> customer 129.90 twice.** What I need from you: check the payment/refund backend
> for an existing refund record on ORD-1001 — if there is none, re-issue 12990 cents
> with reason "arrived damaged"; if there is one, don't refund again. I'd also
> suggest adding an idempotency key to issue_refund and having find_orders return
> refund status, or this will happen again.

### Did the model do anything wrong?

**Not one thing.**

Its business reasoning was entirely correct (order, category, window, amount, full
refund). It failed for exactly one reason: **the tool wouldn't tell it what had
happened**, and it refused to gamble.

**That is correct behaviour.** An agent that blindly retries on "Call failed"
refunds the customer twice.

> **This is the real cost of a vague error, and it isn't in the same league as
> "a few extra rounds":**
>
> The string `"Call failed."` fails to distinguish:
> - **rejected, nothing happened** (safe to retry)
> - **partially executed, then failed** (retrying double-charges)
>
> For **read-only** tools that distinction barely matters — worst case you query
> again. For tools that **change the world** (payments, refunds, emails, deletions)
> it is exactly the line between "can recover automatically" and "must page a human".

### Corollary: separate reads from writes when you design tools

| | Cost of a vague error |
|---|---|
| Read-only tools (query, search) | A few extra round trips, wasted tokens |
| Write tools (pay, delete, send) | **The agent halts and needs a human** — and that's the best move available to it |

So: **spend your error-message effort on the tools with side effects first.**

And the deeper fix is the one the model itself named: **idempotency keys**. With
one, "I'm not sure whether it went through" stops being a dead end, because
retrying is safe. Exercise 3 has you build it.

> **Some problems shouldn't be solved with prompting. They should be solved with
> interface design.**

---

## 4. Exercise answers

### Exercise 1 ⭐ Add exactly one line

Measured (on top of exercise 2's parameter-name fix, adding one line documenting
the `reason_code` enum):

```
ok find_orders(...)
x  get_policy({"category": "DEFECTIVE"})            <- see below, this is interesting
ok get_policy({"category": "electronics"})
ok issue_refund({..., "reason_code": "DEFECTIVE"})  <- right first time
3 rounds, 4 tool calls, 1 failure
```

**The `reason_code` failure is gone.** One line of prose, one round trip saved.

But look at the failure that remains: the model put `DEFECTIVE` into **`category`**.

**It took the one enum I did write down and dropped it into the slot I didn't.**

> **This is a real trap: partial documentation misdirects.**
> A half-written doc makes it *more* likely the model applies known information in
> the wrong place — it now holds one official-looking enum value while knowing
> nothing about the other parameter.
>
> Practical implication: **document all your enums, or don't expect the model to
> work out which enum belongs to which parameter.**

### The three variants side by side

| Version | Rounds | Failures | Still trips on |
|---|---|---|---|
| `vague_desc` as shipped | 5 | 3 | category enum, param names, reason enum |
| Param names fixed (ex. 2) | 4 | 2 | category enum, reason enum |
| Param names + reason enum | 3 | 1 | category enum |
| `good` | 3 | **0** | — |

**A clean ladder, with every rung matching one specific documentation gap.**

> Turn it around: your tool gets called ten thousand times, and the line you saved
> writing gets re-paid, amortized, across all ten thousand.

### Exercise 2 ⭐⭐ Separate "sparse" from "wrong"

Fix line 3 of `tools_vague` to the real parameter names:

```python
3. issue_refund(order_id, amount_cents, reason_code) - refund handling
```

Measured: **5 rounds / 3 failures → 4 rounds / 2 failures.** The parameter-name
failure is gone; both enum failures remain:

```
ok find_orders(...)
x  get_policy({"category": "headphones"})           <- enum not listed
ok get_policy({"category": "electronics"})
x  issue_refund({..., "reason_code": "damaged"})    <- enum not listed
ok issue_refund({..., "reason_code": "DEFECTIVE"})
```

That separates the two variables:

| | Missing information | Consequence |
|---|---|---|
| **Sparse** (enum not listed) | The model doesn't know the valid values | Guesses something reasonable (`"headphones"`, `"damaged"`), fails, corrects |
| **Wrong** (stale param names) | The model thinks it knows | **No doubt at all** — sends the wrong thing confidently |

> The difference is **whether the model knows it's guessing.**
> Missing information: it knows, and is primed to be corrected.
> Wrong information: it believes it's informed, and isn't primed at all.
>
> So: **better to write nothing than to write something wrong.** More practically:
> **generate docs from code** rather than hand-writing them — hand-written docs
> always drift.

### Exercise 3 ⭐⭐⭐ Add an idempotency key

Reference implementation:

```python
REFUND_LOG = {}      # idempotency_key -> the previous result

def tool_issue_refund(args, good_errors):
    key = args.get("idempotency_key")
    if key is None:
        return error(good_errors, "err_good_missing", param="idempotency_key", ...)
    if key in REFUND_LOG:
        return REFUND_LOG[key]        # <- same key returns the old result, no double refund

    ... the original validation and refund logic ...

    REFUND_LOG[key] = result
    return result
```

Does `both_bad` still get stuck? **Usually not.** "Retrying is safe" is now encoded
in the interface: even without knowing whether the last call succeeded, retrying
costs nothing.

> **What this exercise is really saying:**
> `both_bad`'s deadlock looks like "the error message was too vague".
> At root it's "this interface doesn't permit retrying under uncertainty".
>
> Improving the error message **treats the symptom**; adding an idempotency key
> **removes the cause**.
>
> A more general heuristic:
> **If your fix is "explain it more clearly in the prompt", stop and ask whether you
> can make the mistake impossible at the interface level instead.**

### Exercise 4 ⭐⭐⭐ Make an error message over-detailed

Typical result: **success rate unchanged, token count noticeably up.**

The reason is simple — the model needs to know **what went wrong this time**, not
everything about the API. Pasting the whole doc into the error means re-sending the
doc on every mistake.

> **A good error message is *targeted*, not *comprehensive*.**
>
> Three things suffice:
> 1. what's wrong  2. what you sent  3. how to fix it
>
> Anything more belongs in the tool description — and **the description is sent
> once, while error messages may be sent many times.** Putting long content where
> it's sent once is pure cost arithmetic.

### Exercise 5 ⭐⭐⭐ A ticket that can't be resolved

`alice@example.com wants to return the coffee beans.` — ORD-1002 is food, 7-day
window, ordered 40 days ago. **Policy says no.**

- **`good` mode**: tells you clearly that the window has passed, because the error
  spells it out ("Order ORD-1002 is in category food, whose refund window is 7 days,
  but it was placed 40 days ago"). It reports that as a **conclusion**.

- **`both_bad` mode**: gets only "Call failed." and cannot distinguish "policy
  forbids this" from "I'm filling the arguments in wrong", so it will likely keep
  trying argument combinations and end up reporting "I couldn't work this tool out".

**And here's the part that actually hurts:**

> In your monitoring these two look **identical**: "the agent didn't complete the task".
>
> But one is **the system working correctly** (policy genuinely forbids it) and the
> other is **the system broken** (the tool is unusable).
>
> **A vague error message destroys your ability to tell them apart.**

So in production, return **business rejections and call errors in different shapes**:

```python
{"ok": False, "reason": "POLICY_WINDOW_EXPIRED", "detail": "..."}   # rejected, don't retry
{"error": "...", "retryable": True}                                 # call error, fix and retry
```

The model can tell them apart, and so can your dashboards.

---

## 5. A checklist you can steal

Run through this whenever you write a tool:

**Description**
- [ ] Every parameter's **type + unit** (cents/dollars, seconds/ms, UTC/local)
- [ ] **Ranges** (max 90, must be positive)
- [ ] **All enum values listed** — don't make the model guess
- [ ] Give an **example** (`"alice@example.com"` beats "the email address")
- [ ] Say **where the value comes from** ("copy the category from find_orders")
- [ ] Flag **irreversible** operations explicitly

**Return values**
- [ ] Field names **carry units** (`amount_cents` / `duration_ms` / `created_at_iso`)
- [ ] Write tools return enough to determine **whether the effect happened**

**Error messages**
- [ ] Say ① what's wrong ② what you sent ③ how to fix it
- [ ] **Business rejection** and **call error** have different shapes
- [ ] Write tools: state explicitly whether it's **safe to retry**

**The interface itself**
- [ ] Side-effecting operations: consider an **idempotency key**
- [ ] **Generate docs from code**, don't hand-write them (hand-written drifts)

---

← [back to the chapter](../README.md) · [back to the index](../../../README.md)
