# Lab 4-1: Tool design — what decides the outcome is your documentation

**English** · [简体中文](README.zh-CN.md)

> **What you'll learn**
>
> 1. Same model, same task — **change only the tool descriptions and error
>    messages** and the result moves from "right first time" to "cannot complete"
> 2. A **2×2** that tells you which of the two is worth more, and *when*
> 3. Error messages aren't logs — **they're part of the next turn's context**, the
>    most timely instruction you can hand a model
> 4. For tools that **change the world** (payments, refunds, deletes), a vague error
>    isn't just slow — it's a **hard stop**
>
> **How you'll learn it**: the verdict is purely mechanical — the program knows the
> one correct call and compares against it. No keywords, no LLM-as-judge.
>
> **Time**: 25 minutes (no network).

---

## The problem

For three chapters, tools have been incidental. Now look at them directly.

Handing a model a tool means handing it **two** things:

```
1. Up-front documentation: what it does, how to fill the arguments   <- tool description
2. After-the-fact feedback: you got it wrong, here's where, here's the fix
                                                                     <- error message
```

Most people put some effort into #1 and **none whatsoever** into #2 (just `raise`
and move on).

This lab makes those two independent switches and runs a 2×2:

|  | Errors useful | Errors useless |
|---|---|---|
| **Descriptions good** | `good` | `silent_errors` |
| **Descriptions bad** | `vague_desc` | `both_bad` |

**Read across** → what error messages are worth
**Read down** → what tool descriptions are worth

---

## The task and its three traps

One refund ticket:

```
Customer alice@example.com says the headphones she bought arrived faulty. Refund her.
```

Three tools: `find_orders` / `get_policy` / `issue_refund`.

Three traps are buried in it, **all of them everyday production hazards**:

| Trap | What it looks like |
|---|---|
| **Units** | `amount_cents` is in *cents*: 129.90 must be written 12990, not 129.9 |
| **Enum** | `reason_code` accepts only `DEFECTIVE` / `WRONG_ITEM` / `CHANGED_MIND` |
| **Business rule** | alice has two orders; one (food, 40 days ago) is past its refund window |

The one correct call:

```python
issue_refund(order_id="ORD-1001", amount_cents=12990, reason_code="DEFECTIVE")
```

⚠️ **The tools validate identically in all four modes.** No mode is "easier to
succeed in" — some modes just make it **easier for the model to work out what it
got wrong**.

---

## Step 0: establish the baseline (4 min)

```bash
cd labs/ch4-tools/4-1-tool-design
python3 agent.py good
```

Press Enter for examples, then type `1`.

### 👀 What you'll see

```
  --- did the ticket get resolved? ---
  ok RESOLVED: the correct refund was issued in round 3
  rounds used: 3
  tool calls: 3, of which 0 failed
```

### 💡 What you learn

**Zero failures.** All three traps avoided.

Open `agent.py` and read `tools_good`. Notice the shape of it —
**every sentence pre-answers a question the model was going to have**:

```
- days:  how many days back to search. Integer, max 90. If unsure, use 90.
                                                        ^ removes the hesitation

- amount_cents: ... 129.90 in currency units is written 12990, not 129.9.
                find_orders already returns amount_cents in cents - use it directly.
                                       ^ gives a counter-example AND says where the data is

- category: must be one of ... (the category value appears in find_orders' output -
            copy it verbatim)
                                       ^ not just the enum, but where to get it
```

> **A good tool description doesn't "explain what the function does". It predicts
> where the caller will get stuck.**

---

## Step 1: make the descriptions bad (6 min) ★ the point

```bash
python3 agent.py vague_desc "(paste the same ticket)"
```

`tools_vague` reads like this — **this isn't a strawman**, it's what
auto-generated-from-signature docs almost always look like:

```
1. find_orders(email, days) - order lookup
2. get_policy(category) - policy lookup
3. issue_refund(order_id, amount, reason) - refund handling
```

### 🤔 Predict

- Can it still finish? ___
- How many failures, and on which traps? ___

### 👀 What to watch

**Read the failures one at a time.** After each one, watch what it changes.

### 💡 What you learn

The failures arrive one at a time, and **each maps to a sentence missing from the
description**.

You'll see something interesting: the model gets `amount_cents` right (12990),
**even though the description never mentions units**.

**Why?** Because it saw the field name in `find_orders`' output:

```json
{"order_id": "ORD-1001", "amount_cents": 12990, ...}
```

> **A tool's return value is documentation too.** One well-named response field is
> worth a paragraph of parameter docs.

Take this straight into your own projects: **return `amount_cents`, not `amount`;
return `created_at_iso`, not `time`.** Naming is teaching.

---

## Step 2: make the errors bad (6 min) ★ the point

```bash
python3 agent.py silent_errors "(the same ticket)"
```

Descriptions are good now, but every error just says "Call failed."

### 🤔 Predict

How much worse than `good`?

### 💡 What you learn

**The result may surprise you.** Answer this before reading SOLUTION:

> **If the model never makes a mistake, does the quality of the error message
> matter at all?**

That's the point of a 2×2 — **some variables only act under specific conditions.**
Test one in isolation and you'll draw the wrong conclusion ("it doesn't matter").

---

## Step 3: both bad (5 min)

```bash
python3 agent.py both_bad "(the same ticket)"
python3 agent.py all      "(the same ticket)"
```

### 👀 What to watch

**Don't just look at resolved/not — read `both_bad`'s final `[hand-off]` note.**

It's the single most worthwhile thing in this lab. After reading it, ask yourself:

> **Did the model do anything wrong?**

(Hint: it didn't. SOLUTION goes into it.)

---

## Step 4: change it yourself (exercises)

### Exercise 1 ⭐ Add exactly one line

Add **one line** to `tools_vague` documenting the `reason_code` enum:

```python
3. issue_refund(order_id, amount_cents, reason_code) - refund handling
   reason_code must be one of DEFECTIVE / WRONG_ITEM / CHANGED_MIND
```

**Predict**: failures drop from 3 to how many?

> The intuition to build: **documentation has an absurd return on investment.**
> One line of prose buys back a round trip.

### Exercise 2 ⭐⭐ Separate "sparse" from "wrong"

Look closely at line 3 of `tools_vague`:

```
issue_refund(order_id, amount, reason)               <- what the docs say
issue_refund(order_id, amount_cents, reason_code)    <- what the code takes
```

**The parameter names are wrong**, not merely missing. That's what documentation
drift looks like.

Fix the names (but still write no explanations) and re-run `vague_desc`.

**Predict**: how many failures does that alone save?

> **Stale docs are worse than no docs** — with no docs the model is careful; with
> wrong docs it confidently walks into the wall.

### Exercise 3 ⭐⭐ Add an idempotency key to `issue_refund`

Run `both_bad` and you'll see the model suggest this itself. Do it: add an
`idempotency_key` parameter so repeat calls with the same key return the same result.

**Think it through**: does `both_bad` still get stuck afterwards?

> The real lesson: **some problems shouldn't be solved with prompting. They should
> be solved with interface design.**

### Exercise 4 ⭐⭐⭐ Make an error message *over*-detailed

Rewrite one error to dump a wall of text (say, the whole API doc) and re-run
`vague_desc`.

**Predict**: is more detail always better?

> Think back to chapter 2: error messages enter the context, and context has a
> budget. **Every error message costs money.**

### Exercise 5 ⭐⭐⭐ A harder ticket

```bash
python3 agent.py good "alice@example.com wants to return the coffee beans she bought."
```

That order is past its window (food: 7 days, bought 40 days ago).

**Predict**: what does `good` do? What does `both_bad` do?

> Note that "cannot complete" is the **correct** answer here. Watch whether it
> distinguishes "policy says no" from "I can't figure out this tool" — in a log,
> those two look almost identical.

---

## Check your answers

After you've tried → **[SOLUTION.md](SOLUTION.md)**

The full measured 2×2, a line-by-line reading of `vague_desc`'s three failures,
the complete text of `both_bad`'s "the model outperformed the tool design"
hand-off, and answers to every exercise.

---

## Appendix: concepts

### A checklist for a good tool description

For each parameter, ask:

- [ ] Is the **type and unit** stated? (cents/dollars, seconds/ms, UTC/local)
- [ ] Is the **range** stated? (max 90, must be positive)
- [ ] Are the **enum values** listed? (don't expect the model to guess your codes)
- [ ] Is there an **example**? One `"alice@example.com"` beats "the email address"
- [ ] **Where does this value come from?** ("copy the category from find_orders")
- [ ] Are **irreversible** operations flagged as such?

For return values:

- [ ] Do the field names **carry their units**? (`amount_cents`, not `amount`)

### The three parts of a good error message

```
1. what's wrong    "reason_code must be one of DEFECTIVE / WRONG_ITEM / CHANGED_MIND"
2. what you sent   "you passed \"damaged\""
3. how to fix it   "A faulty item is DEFECTIVE."
```

#3 is the one most often omitted, and **the most valuable**.

### One engineering principle

> **An error message isn't a log line for your ops team. It's the next turn's
> prompt for the model.**
>
> The 20 characters you saved in `raise ValueError("invalid")` get paid back out
> on every single call.

---

## Stuck?

| What you see | What to do |
|---|---|
| `x No usable backend found` | Install any one of the three options on screen |
| My run differs from the docs | **Expected** — models are stochastic. Read the **shape** of the 2×2, not the digits |
| Even `good` failed | Uncommon but possible. Re-run; if it persists, look at which trap it hit — that's where the description can still improve |
| Want the exact text the model received | Set `SHOW_PROMPT = True` |
| Forgot the commands | Run `python3 agent.py` with no arguments |
