# Lab 2-6 answers: the agent status bar

**English** · [简体中文](SOLUTION.zh-CN.md)

> ⚠️ Try it first.

---

## 1. Measured data

Local qwen3:0.6b (`--weak`), two passes of n=20, 2026-07-29:

| Mode | Pass 1 | Pass 2 | **Combined (n=40)** |
|---|---|---|---|
| `no_status` | 10/20 | 10/20 | **20/40 = 50%** |
| `counter` (numbers only) | 8/20 | 6/20 | 14/40 = 35% |
| `status_bar` (numbers + conclusion) | 8/20 | 5/20 | 13/40 = 32.5% |
| `todo` (with an alternative action) | 3/20 | 4/20 | **7/40 = 17.5%** ★ |

Frontier model (Claude Code, n=3): **0/3 violations in all four modes.**

---

## 2. The book's core claim: reproduced ✅

The book states:

> "For a small model like Qwen3-0.6B, control group A frequently violates the
> constraint and keeps dialling."

**Measured: `no_status` violates 50% of the time, at exactly 10/20 on both passes.**

And **every** form of aggregated metadata brings it down (17.5% – 35%).

> This is one of the few experiments in this repo that **fully reproduces** a book claim.
>
> And the mechanism is clear: **the information didn't change** — the three call records
> were always in the trace. What changed is whether the model has to count them.
>
> The book's term, **context distillation**, is accurate: do the inference **ahead of
> time** instead of making the model redo it every turn.

Zero violations on the frontier model doesn't contradict this — **the task is simply
trivial for it.** As the book says: strong models save thinking tokens, weak models save
accuracy.

---

## 3. My first conclusion (n=3) was wrong ★★

Worth more than the result itself.

First run (`TRIALS=3`):

```
no_status  2/3      counter  1/3      status_bar  0/3      todo  2/3
                                                 ^ a perfect monotonic gradient
```

**Textbook.** My reading at the time: "numbers help, numbers+conclusion is best, TODO is useless."

Then I ran it again (n=5):

```
no_status  2/5      counter  0/5      status_bar  2/5      todo  1/5
                                                 ^ from best to joint-worst
```

**The ordering inverted.**

Only at n=20 × 2 did the truth settle — and **it contradicts my first reading entirely**:
`todo` is the best; `status_bar` is mid-table.

> **The second time this repo has hit this trap** (first: [lab 2-0](../2-0-local-llm/SOLUTION.md)):
>
> **A controlled experiment run three times proves nothing. And the more textbook-perfect
> it looks, the more you should suspect it** — clean monotonic gradients are rare in noisy
> measurements.
>
> Hence `TRIALS` defaults to 10, with a "don't lower this" note in the code.

---

## 4. A finding the book doesn't mention: why TODO wins ★★★

`todo` (17.5%) violates markedly less than `status_bar` (32.5%).

Counterintuitive, because `status_bar` says outright:

```
- Constraint check: **Maximum calls to Xfinity reached (3/3)**
```

while `todo` **never mentions a limit.**

### My hypothesis

The last line of `block_todo`:

```
- [pending] If no callback within 24h, switch to the written complaint channel
```

**It gives the agent something else to do.**

`status_bar` only says "you can't call" — **it never says what to do instead.**

### I ran an ablation

Delete that pending item, change nothing else, 20 runs each:

| TODO version | Violations |
|---|---|
| **With** the alternative action | **8/20** |
| **Without** it | **13/20** |

**A 25-point gap, in the predicted direction.**

⚠️ Being honest: the with-alternative condition measured **3/20, 4/20 and 8/20** across
three passes — **high variance.** So this ablation is **directional** evidence, not a
precise effect size. Exercise 1 asks you to reproduce it.

> **Transferable conclusion (if it holds):**
>
> **Telling a model what to do beats telling it what it can't do.**
>
> True of humans too: a policy listing only prohibitions and one saying "in this case,
> use process X" get different compliance rates.
>
> It also explains why `counter` (35%) barely improves on `no_status` (50%): **it gives
> a number, but neither a conclusion nor a way out.**

**Exercise 2 tests this directly**: add a "suggested next step" to `status_bar` and see
whether it catches `todo`. If it does, the difference isn't the form (status bar vs TODO)
but **the content (was a next step supplied)**.

---

## 5. Exercise answers

### Exercise 1 ⭐ Run the ablation

Numbers in section 4. **Use n≥20** — at n=3 the difference is invisible.

### Exercise 2 ⭐⭐ Give `status_bar` an alternative action

I expect it to catch up with `todo`. **I did not test this**, so it's genuinely open.

> If you measure it, you upgrade section 4's hypothesis from directional evidence to a
> causal result. **The most worthwhile exercise here.**

### Exercise 3 ⭐⭐ Remove the rule, keep only the status bar

This tests something different: can a status bar **replace** a rule, or only **remind**
of one?

My expectation is "only remind" — a status bar states a **fact** (three calls happened),
while "the limit is three" is a **norm**. Facts don't imply norms.

> But that's only an expectation. **Go measure it.**

### Exercise 4 ⭐⭐⭐ Make the trace longer

The book says explicitly:

> Without a status bar, per-query thinking **grows continuously** with context length;
> with one it becomes **roughly constant**.

Going from 5 to 30 trace entries should make `no_status` worse — counting costs more and
errs more as length grows, while a status bar is constant cost.

> The direction that best demonstrates context distillation, and the closest approach to
> the book's quantified result (80–90% fewer thinking tokens).

---

## 6. Back to the chapter

```
2-0  longer input -> pricier prefill
2-4  broken prefix -> the cache never hits
2-1  compaction: make the context shorter
2-6  status bar: make what's in it MORE USABLE   <- this lab
```

**2-1 and 2-6 optimise in different directions and are easy to conflate:**

| | 2-1 Compaction | 2-6 Status bar |
|---|---|---|
| Does what | shortens the long | **pre-computes** the scattered |
| Information | **reduced** (lossy) | **unchanged** |
| Solves | doesn't fit | fits, but is **hard to use** |
| Use when | over budget | the model re-derives the same thing every turn |

> **They compose, and often should be used together.** Compaction controls length; the
> status bar keeps what remains from needing to be chewed over repeatedly.

---

← [back to the chapter](../README.md) · [back to the index](../../../README.md)
