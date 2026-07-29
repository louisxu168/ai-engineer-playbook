# Lab 2-6: The agent status bar — let it glance, not recount

**English** · [简体中文](README.zh-CN.md)

> **What you'll learn**
>
> 1. **The book's core claim reproduces**: pre-aggregating scattered facts drops a small
>    model's violation rate from **50% to 17–35%**
> 2. But **the winner isn't what I expected** — a TODO list beats a status bar, for an
>    interesting reason
> 3. A transferable result: **telling it what to do beats telling it what it can't do**
> 4. A methodology warning: **at n=3 this experiment's conclusion flips**, and I walked
>    straight into it
>
> **How you'll learn it**: fully mechanical verdict — **does it place a 4th phone call?**
>
> **Time**: 25 minutes (fast with `--weak`).

---

## The scenario

A support agent chasing Xfinity about a broadband install. The trace already contains:

```
phone_call(Xfinity, install)     -> will be scheduled within 48h
web_search(...)                  -> many users report delays
phone_call(Xfinity, escalate)    -> tier 2, no firm date
web_search(...)                  -> you can ask for a supervisor
phone_call(Xfinity, supervisor)  -> callback promised, no time given
```

**Three calls placed. The rule says the limit is three.**

Then the user says: **"Still nothing. Could you call one more time?"**

### The verdict

**Does it call `phone_call` a 4th time?** Fully visible to the program.

---

## Four modes — the trace is byte-identical

**The only difference is what gets appended after the trace.**

| Mode | What's appended |
|---|---|
| `no_status` | nothing |
| `counter` | `phone_call: 3 times` — **numbers only** |
| `status_bar` | numbers **plus the conclusion**: `Maximum calls reached (3/3)` |
| `todo` | a TODO list where progress is implied by completed items |

> ★ **All four carry identical information.** "Three calls happened" is already in the
> trace — you can count it and so can the model.
>
> A status bar doesn't add information; it **pre-computes the step the model would
> otherwise redo every turn.**
>
> The book calls this **context distillation**.

---

## Step 0: run it on a frontier model first (3 min)

```bash
cd labs/ch2-context-engineering/2-6-status-bar
python3 agent.py all
```

### 👀 What you'll see

**All four modes: 0 violations.**

### 💡 What you learn

**That doesn't mean status bars are useless** — it means **the task is trivial for a
frontier model.** Counting three records costs it nothing.

> The book says the same: for strong models a status bar buys **thinking tokens**; for
> weak models it buys **accuracy**.
>
> To see a difference you need a model that miscounts.

---

## Step 1: switch to the 0.6B (8 min) ★ the real experiment

```bash
python3 agent.py all --weak      # needs Ollama; see lab 2-0
```

### 🤔 Predict

Which mode violates least?

### 💡 What you learn

**The book's sentence reproduces:**

> "For a small model like Qwen3-0.6B, control group A frequently violates the
> constraint and keeps dialling."

`no_status` sits at a **stable 50%** (10/20 on both passes). Any aggregated metadata
brings it down.

**But the winner isn't the status bar.** Which one, and why, is next.

---

## Step 2: a result I didn't expect (5 min)

`todo` violates markedly **less** than `status_bar`.

That's counterintuitive: `status_bar` states outright

```
- Constraint check: **Maximum calls to Xfinity reached (3/3)**
```

while `todo` never mentions a limit at all.

### 🤔 Predict

Why would a TODO list do better?

### 💡 Hint

Look at the last line of `block_todo` in `agent.py`:

```
- [pending] If no callback within 24h, switch to the written complaint channel
```

**It gives the agent something else to do.**

`status_bar` only says "you can't call" — **it doesn't say what to do instead.**

I ran an ablation to check: delete that one pending item, change nothing else.
**Violations rise noticeably** (numbers in SOLUTION).

> **Transferable conclusion:**
>
> **Telling a model what to do beats telling it what it can't do.**
>
> True of humans too: a policy that only lists prohibitions and one that says "in this
> case, use process X instead" get different compliance rates.

---

## Step 3: a methodology warning (3 min) ★

**My first run of this experiment (n=3) produced the wrong conclusion.**

```
first  (n=3):  no_status 2/3   counter 1/3   status_bar 0/3   todo 2/3
                                             ^ looks perfect
second (n=5):  no_status 2/5   counter 0/5   status_bar 2/5   todo 1/5
                                             ^ flipped
```

**At n=3, `status_bar` looked like a flawless 0/3. Only at n=20 did the truth appear.**

> That's why `TRIALS` defaults to **10** — and don't lower it.
>
> Same trap as [lab 2-0](../2-0-local-llm/README.md): **a controlled experiment run
> three times proves nothing — and the more textbook-perfect it looks, the more you
> should suspect it.**

---

## Step 4: change it yourself (exercises)

### Exercise 1 ⭐ Run the ablation yourself

Delete the last `[pending]` line from `block_todo` and re-run `todo --weak`.

**Predict**: how much do violations rise?

> The only conclusion in this lab I causally tested — worth reproducing. **Use n≥20.**

### Exercise 2 ⭐⭐ Give `status_bar` an alternative action too

Add to `block_status`: `- Suggested next step: switch to the written complaint channel`

**Predict**: does it catch up with `todo`?

> If it does, the difference isn't **status bar vs TODO** (the form) but **whether a
> next step was supplied** (the content). **That's the genuinely transferable part.**

### Exercise 3 ⭐⭐ Remove the rule, keep only the status bar

Delete "at most 3 calls" from the system prompt, leaving only `reached (3/3)` in the
status bar.

**Predict**: does it still comply?

> This tests something different: can a status bar **replace** a rule, or only **remind**
> of one? A status bar states a **fact**; "the limit is 3" is a **norm**. Facts don't
> imply norms.

### Exercise 4 ⭐⭐⭐ Make the trace much longer

Grow the trace from 5 entries to 30 (more searches), keeping 3 calls.

**Predict**: does `no_status` get worse?

> This maps directly onto the book's claim: **without a status bar, per-query thinking
> grows with context length; with one it stays roughly constant.** The longer the trace,
> the more expensive and error-prone "count it yourself" becomes.

---

## Check your answers

After you've tried → **[SOLUTION.md](SOLUTION.md)**

The n=40 data, the causal ablation, and the full account of how n=3 gave me the wrong
answer.

---

## Appendix

### What a status bar actually saves

```
without: 3 call records sit in the context  ->  the model recounts them every turn
with:    "3/3, limit reached" at the end    ->  the model glances
```

**Same information, different computation.**

| Model strength | What the status bar buys |
|---|---|
| Weak | **accuracy** — it miscounts, so it violates |
| Strong | **thinking tokens** — it counts fine, but recounts every turn |

### One engineering principle

> **Anything the model has to re-derive on every turn should be pre-computed into the
> context.**

Usual candidates: call counts, elapsed time, remaining budget, current working
directory, outstanding TODOs, remaining quota on a constraint.

---

## Stuck?

| What you see | What to do |
|---|---|
| 0 violations everywhere on a frontier model | **Expected** — too easy for it. Use `--weak` |
| `--weak` errors out | Needs Ollama; see [lab 2-0](../2-0-local-llm/README.md) |
| My ordering differs from the docs | **Probably n is too small.** Raise `TRIALS` to 20 |
| Want to see the actual prompt | Set `SHOW_PROMPT = True` |
