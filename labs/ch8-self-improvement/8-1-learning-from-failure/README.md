# Lab 8-1: Learning from failure — can an agent avoid the same trap twice?

**English** · [简体中文](README.zh-CN.md)

> **What you'll learn**
>
> 1. **Remembering lessons is not remembering facts** — lab 3-1's recipe **fails here**
> 2. A counterintuitive measured result: **the raw log beat the distilled lessons**,
>    and the reason is worth chewing on
> 3. The commonest mistake when distilling a lesson: **abstracting away the very
>    value that mattered**
> 4. The most commonly botched part of evaluating self-improvement: **confusing
>    "didn't learn" with "never encountered"**
>
> **How you'll learn it**: mechanical verdict — count failed tool calls per ticket.
> **Learning shows up as a descending curve, not as a smaller total.**
>
> **Time**: 25 minutes.

---

## The problem

Lab 3-1 taught an agent **facts** (this user is allergic to peanuts). This lab
teaches it **lessons**:

```
fact:    "alice is allergic to peanuts"   -> useful only for alice
lesson:  "amount_cents is in cents"       -> useful on every ticket
```

**Lessons are worth more** because they transfer to **new tasks**. That's the
minimal form of what people call "self-improvement".

### The environment: the docs are incomplete

A refund agent handles 3 tickets in a row. The tool documentation it gets is one line:

```
issue_refund(order_id, amount_cents, reason_code)
    Issue a refund for a ticket. Returns {"ok": true} on success.
```

But **three real validation rules exist and none are documented**:

| Rule | When it bites |
|---|---|
| 1. `amount_cents` is in cents | Any ticket (though the parameter name hints at it) |
| 2. `reason_code` must come from an enum | Any ticket |
| 3. **Refunds over 50000 cents need `approved_by`** | **Only T-3** ← remember this |

> **This is what the real world looks like: documentation always lags implementation.**
> An agent that can't learn from errors re-walks into the same wall on **every new task**.

---

## Step 0: see what not learning looks like (5 min)

```bash
cd labs/ch8-self-improvement/8-1-learning-from-failure
python3 agent.py no_memory
```

### 🤔 Predict

Across three tickets, what shape does the failure count take — falling, flat, or rising?

### 👀 What to watch

**Watch the curve, not the total.**

### 💡 What you learn

**The curve doesn't fall.** It re-commits T-1's mistake on T-2 — because to it,
every ticket is the first ticket.

> That's the default state of an agent with no cross-task memory:
> **it never gets worse, but it never gets better either.**

---

## Step 1: carry the raw failure log (5 min)

```bash
python3 agent.py raw_log
```

After each ticket, carry the **raw record** of what was called and what error came
back into the next ticket.

### 🤔 Predict

Will the curve fall?

### 💡 What you learn

**It does.** And this is the cheapest possible approach — **zero extra model
calls**, pure string concatenation.

The cost is one you can already guess (recall lab 3-1): **it only ever grows.**
Fine for 3 tickets. What about 300?

---

## Step 2: have the model distil lessons (6 min) ★ the core

```bash
python3 agent.py lesson
```

After each ticket, have the model turn the failures into **reusable rules**. The
distillation prompt (`sys_extract`) is carefully written:

```
1. Write directly actionable rules, not a retelling of what happened
2. Don't include anything specific to this ticket (order ids, customers, amounts)
3. One rule per item
4. Only what was genuinely learned
```

### 🤔 Predict

Surely better than `raw_log`? — that's what lab 3-1 taught (a good extraction
prompt beats storing everything).

### 👀 What to watch

**Three things together:**

1. The curve (versus `raw_log`)
2. The **verbatim lessons** it learned (the `* learned:` lines)
3. **How many tickets it completed**

### 💡 What you learn

**The result is the opposite of lab 3-1's.** Numbers in SOLUTION.

Before you look, read its lessons and ask yourself:

> **Did the lesson abstract away the one piece of information that would have
> helped?**
>
> Hint: rule 2 is "`reason_code` must be DEFECTIVE / WRONG_ITEM / CHANGED_MIND".
> **Do those three words appear anywhere in what it learned?**

---

## Step 3: full comparison, and a distinction you must make (5 min)

```bash
python3 agent.py all
```

### ⚠️ Before reading the table

**T-3 triggers a rule the first two tickets never hit** (large refunds need approval).

So:

```
T-1 -> T-2 falls    =  it learned ✓
T-3 fails again     =  expected ✓  -- that's "never seen", not "didn't learn"
```

> **"Didn't learn" and "never encountered" are different things, and they look
> identical in the metric.**
>
> This is the **most commonly botched part** of evaluating self-improvement: you
> see failures not reaching zero and conclude the learning mechanism doesn't work,
> when it may simply have met something new.
>
> To judge whether learning happened, **you must know which failures are repeats
> and which are novel.** This lab can say so only because **I planted the rules and
> know which one is new.** In your own system, you have to arrange that yourself.

---

## Step 4: change it yourself (exercises)

### Exercise 1 ⭐⭐ Fix the distillation prompt

If `lesson` underperforms, the culprit is probably criterion 2:

```
2. Don't include anything specific to this ticket (order ids, customers, amounts)
```

**That sentence is ambiguous.** Try:

```
2. Don't include anything specific to this ticket (order ids, customers, amounts).
   BUT: an interface's valid values, thresholds, units and format requirements are
   general knowledge and **must be written down verbatim.**
```

**Predict**: does the curve change?

> The real lesson: **there's a hair's breadth between "abstracting" and "losing
> information"**, and you have to draw that line in the prompt yourself.

### Exercise 2 ⭐⭐ Add a 4th ticket that repeats a rule

Add another **large-value** ticket (T-4, say 700).

**Predict**: does it still fail on `approved_by`?

> This is the correct way to test whether rule 3 was learned: **make the same rule
> appear twice.** A rule that appears once can't distinguish "learned it" from
> "got lucky".

### Exercise 3 ⭐⭐ Persist the lessons to a file

Memory currently lives inside one run. Write it to `lessons.json` and reuse it.

**Predict**: on the second run, does ticket 1 still fail?

> That's cross-session experience — lab 3-1 does this with facts, this does it with
> lessons. **Same mechanism, different content.**

### Exercise 4 ⭐⭐⭐ Make lessons expire

Add a rule: drop a lesson if it hasn't been used for N tickets.

**Think it through first**: how do you tell that a lesson *was* used?

> Hint: much harder than it sounds. **You can't directly observe "it avoided the
> mistake because it remembered this."** That's the genuine difficulty in every
> experience-store system — **accumulating is easy, pruning is hard.** And a store
> that never prunes eventually degenerates into `raw_log`.

### Exercise 5 ⭐⭐⭐ Hybrid: lessons + the most recent raw error

Carry both.

**Predict**: can you get `raw_log`'s fidelity and `lesson`'s compactness together?

> Then look at the cost column: were the extra calls worth it?

---

## Check your answers

After you've tried → **[SOLUTION.md](SOLUTION.md)**

Full curves, a line-by-line reading of what `lesson` actually learned, **why it
contradicts lab 3-1**, and the two traps I hit building this — one of which was the
model **correctly refusing my instructions.**

---

## Appendix: concepts

### Facts vs lessons

| | Lab 3-1 (facts) | This lab (lessons) |
|---|---|---|
| Content | "alice is allergic to peanuts" | "amounts are in cents" |
| Scope | Only that person | **Every** task of this kind |
| What distillation should do | **Generalize** (one-off event → durable preference) | **Preserve concrete values** (enums, thresholds, formats) |
| Over-abstraction produces | Lost detail, but you still know who they are | **Correct but useless advice** |

> **The same "distil" action has opposite correct behaviour in the two settings.**

### One engineering principle

> **The most valuable part of a lesson is usually the very value that looks "too
> specific to keep".**
>
> "Confirm the enum's valid values" — correct, useless.
> "The enum is DEFECTIVE / WRONG_ITEM / CHANGED_MIND" — **that's the lesson.**

---

## Stuck?

| What you see | What to do |
|---|---|
| `x No usable backend found` | Install any one of the three options on screen |
| The agent refuses to call the tool | Should be fixed (the prompt states it's a simulation). If it recurs, see SOLUTION section 7 |
| My curve differs from the docs | **Expected** — models are stochastic. Watch the **shape**: does it fall, and where |
| T-3 always fails | **By design** — it triggers a rule the earlier tickets never hit |
| Want the exact text the model received | Set `SHOW_PROMPT = True` |
| Forgot the commands | Run `python3 agent.py` with no arguments |
