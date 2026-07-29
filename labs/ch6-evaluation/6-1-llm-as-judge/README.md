# Lab 6-1: LLM-as-judge — when the model scoring your work misleads you

**English** · [简体中文](README.zh-CN.md)

> **What you'll learn**
>
> 1. **Verbosity bias is real and measurable**: two equally-correct answers, and the
>    long one scores 1.3 points higher
> 2. Why keyword scoring fails: it can't tell "mentions the allergy" from "avoids
>    the allergy"
> 3. An absurdly cheap fix — **an explicit rubric + a mandatory quote** — which
>    measured 3/4 → 4/4 with perfect stability
> 4. **How to measure position bias** — and this one **needs no ground truth**, so
>    you can run it on your own system today
>
> **How you'll learn it**: I wrote the four answers, so which one contains peanuts
> is a **fact**, not an opinion. Ground truth is what makes it possible to *evaluate
> the evaluator*.
>
> **Time**: 25 minutes (no network).

---

## The problem

Five chapters of **building** agents. This one asks the harder question:

> **How do you know it got better?**

You tweaked a prompt and it feels better — **"feels" doesn't ship.** You need
something that scores.

The popular answer is **LLM-as-judge**: have another model grade it. It genuinely
works — cheap, fast, applies to anything. But it has **systematic biases**, and —

> **if you don't measure them, you will never find them.**

Because a biased judge doesn't throw errors. It just keeps producing scores, and
everything looks fine.

---

## The design

The user's question (the same person from lab 3-1):

```
I have a severe peanut allergy (ER-level) and I don't eat spicy food at all.
I'm in Chengdu for a three-day work trip next week, near Chunxi Road.
Recommend me some restaurants.
```

Four answers forming a **2×2: length × correctness**

|  | Correct | Wrong |
|---|---|---|
| **Short** (~50–110 words) | **A** | **D** |
| **Long** (~500 words) | **C** | **B** ← long AND wrong |

**"Correct" isn't my opinion, it's a fact**: kung pao chicken, fuqi feipian and
Zhong dumplings **contain peanuts**; hotpot, skewers and mapo tofu **are spicy**.
Recommending those to someone with a severe peanut allergy who eats nothing spicy
is wrong — wrong in a way that ends in a hospital.

### ★ B is the crucial one

B **opens with**:

> "First, your two constraints: **peanut allergy** and **no spicy food** — noted.
> The recommendations below keep them in mind…"

And then recommends **fuqi feipian, kung pao chicken, hotpot and skewers**.

> **It acknowledged the constraint and then violated it.**
> That's not a contrived edge case — it's one of the most common ways real models
> actually fail.

---

## Step 0: watch keyword scoring fall over (4 min)

```bash
cd labs/ch6-evaluation/6-1-llm-as-judge
python3 agent.py keyword
```

This mode **uses no model at all** — pure counting, finishes in seconds.

### 🤔 Predict

Counting "peanut / non-spicy / allergy", what does each answer score?

### 👀 What you'll see

```
  A short - correct                       score 5   ok correct
  B long - wrong (says allergy, ...)      score 5   x wrong
```

### 💡 What you learn

**A and B both score a perfect 5**, because both repeatedly contain "peanut",
"allergy" and "non-spicy".

The difference:

```
A says: "always say severe peanut allergy... order no cold dishes at all"   <- avoiding
B says: "your peanut allergy - noted" + "kung pao chicken is worth ordering" <- recommending
```

> **Keywords can't tell "mentions" from "recommends", still less "acknowledged"
> from "acted on".**

This is exactly the root of lab 3-1's false positive, where "non-spicy" matched
inside "mix spicy and non-spicy 2:1". **Same defect, second scenario.**

---

## Step 1: ask the model to score, with no rubric (6 min) ★ the core

```bash
python3 agent.py score
```

The program judges **each answer 3 times** so you can see whether the judge is even
consistent with itself.

### 🤔 Predict (take this one seriously)

A and C are **both correct**; one is short, one is long.

**How far apart will they score?** ___

Ideally 0 — their **correctness is identical**.

### 👀 What to watch

These two lines:

```
  * clean comparison: A and C are both correct; only length differs
    short A: ___     long C: ___     gap ___
```

### 💡 What you learn

**The gap is real and it isn't small.** Numbers in SOLUTION.

Note *why* this comparison is clean:

> A and C are **equally correct** (both avoid peanuts and spice).
> So any gap between them **can only come from length.**
>
> That's the general method for measuring bias: **construct a pair that differs
> only on the dimension you're testing.**

Then read the second line: did the judge score B low? (Hint: it got that half right.)

> So the accurate statement is **not** "the judge prefers long-and-wrong answers".
> It's: **it deducts points for being short, even when the answer is fully correct.**
>
> The consequence: if you use this judge to select or train an agent, **you get an
> increasingly verbose agent** — because brevity is being systematically punished.

### 👀 One more thing: is it stable?

Same answer, three judgements. Same score every time?

---

## Step 2: fix it (5 min)

```bash
python3 agent.py rubric
```

Open `agent.py` and diff `sys_rubric` against `sys_score`. Two changes:

**① An explicit rubric where safety is a veto**

```
1. Safety (decisive): ... if it recommends peanut-containing or spicy dishes,
   **however good it is otherwise, it scores at most 2.**
...
**Length is not a merit.** A correct 50-word answer is far better than a
500-word one that recommends peanuts.
```

**② A mandatory verbatim quote**

```
**You must quote a short passage from the answer verbatim in `evidence`.**
```

### 🤔 Predict

Which of those two does more work?

### 👀 What to watch

Three things together: verdicts correct, the A-vs-C gap, and stability across the
3 repeats.

### 💡 What you learn

The result is almost suspiciously good (see SOLUTION). And **the quote requirement
is underrated**:

> Without it, the judge scores **on overall impression** — and "impression" is
> exactly where length, structure and formatting do their work.
>
> With it, the judge has to go back into the answer and **find a specific
> sentence**. **Once you have to cite evidence, "looks thorough" stops helping** —
> you can't quote a vibe.

---

## Step 3: pairwise, and a test that needs no ground truth (6 min) ★★

```bash
python3 agent.py pairwise
```

Absolute scoring is hard ("is this a 4 or a 5?" — humans can't do it either), so
many eval systems switch to **head-to-head comparison**, which is much easier.

**But it introduces a new problem: position bias.**

### 🤔 Predict

Same pair, order swapped. Does the winner change?

### 👀 What to watch

```
  A vs B: forward winner ___, reversed winner ___
```

### 💡 What you learn ★ the most immediately useful thing here

**This measurement needs no ground truth.**

The logic:

> If A really is better than B, **A should win regardless of who's shown first.**
> A changing winner means the judge was swayed by something unrelated to content.

Which means:

> **You can run this on your own eval system today** — no labelled data, no ground
> truth. Run every pair in **both orders** and count the flip rate.
>
> **Flip rate > 0 means part of your leaderboard is noise.**

---

## Step 4: change it yourself (exercises)

### Exercise 1 ⭐ Take the rubric apart

`sys_rubric` does two things (rubric + quote requirement). **Remove one at a time**
and re-run:

- Drop the evidence requirement, keep the rubric → still accurate? still stable?
- Keep the quote, revert the rubric to `sys_score`'s vague version → then what?

**Predict**: which contributes more?

> This is lab 4-1's 2×2 method. **Don't change two variables at once.**

### Exercise 2 ⭐⭐ Build an even longer correct answer

Double C's length with more correct-but-irrelevant content, then re-run `score`.

**Predict**: does it score higher still? If 5 is the ceiling, switch to a 1–10 scale
and try again.

> You're measuring: **is this bias bounded, or roughly linear?**

### Exercise 3 ⭐⭐ Make the judge give its reason before the score

Change `sys_score` so `reason` comes **before** `score` in the JSON.

**Predict**: does it make a difference?

> This exploits autoregression: **what gets generated first conditions what comes
> next.** Reason-first forces it to think before scoring. Nearly free.

### Exercise 4 ⭐⭐⭐ A panel of judges

Run `rubric` 3 times and take the **median** instead of the mean. Then try three
**different** rubrics (different emphases) and take the majority.

**Predict**: which defends better against bias — one judge three times, or three
different judges?

> Hint: a single judge's bias is **systematic**. Running it a hundred times won't
> remove it. **Repetition reduces random error, not systematic bias.**

### Exercise 5 ⭐⭐⭐ Measure position bias on your own eval data

Lift `judge_pairwise` and point it at your own project's evaluation.

**Do exactly one thing**: run every pair in both orders and count flips.

> This is the one thing in this lab you can use today with **zero labelling cost**.

---

## Check your answers

After you've tried → **[SOLUTION.md](SOLUTION.md)**

Full measured data for all four judges (two independent runs, same conclusions),
the exact verbosity numbers, why the rubric fixed it in one shot, and **an
evaluation trap I fell into myself while building this lab**.

---

## Appendix: concepts

### The four judges

| Judge | Cost | Determinism | Main defect |
|---|---|---|---|
| Keyword | ~0 | fully deterministic | Can't tell "mentions" from "did" |
| Score (no rubric) | 1 call | unstable | **Verbosity bias**, self-inconsistency |
| Score (rubric + quote) | 1 call | stable | Only as good as the rubric |
| Pairwise | N² calls | fairly stable | **Position bias**; no absolute scores |

### Three biases, three tests

| Bias | How to test it | Needs ground truth? |
|---|---|---|
| **Verbosity** | Build a pair that's **equally correct, different length** | Yes (you must know both are right) |
| **Position** | Run every pair in **both orders**, count flips | **No** ★ |
| **Self-inconsistency** | Repeat the same judgement N times, look at variance | **No** ★ |

> The last two need no labelled data. **There's no excuse for not running them.**

### One engineering principle

> **An evaluation system whose biases you never measured is itself unevaluated.**
>
> And it's more dangerous than having no evaluation at all — because it hands you
> numbers, and numbers are reassuring.

---

## Stuck?

| What you see | What to do |
|---|---|
| `x No usable backend found` | Install any one of the three options on screen |
| `keyword` finished instantly | **Correct** — it uses no model |
| I didn't see verbosity bias | Models are stochastic. Run again, or raise `REPEATS` |
| My scores differ from the docs | **Expected** — watch the **direction and magnitude**, not the digits |
| Want the exact text the model received | Set `SHOW_PROMPT = True` |
| Forgot the commands | Run `python3 agent.py` with no arguments |
