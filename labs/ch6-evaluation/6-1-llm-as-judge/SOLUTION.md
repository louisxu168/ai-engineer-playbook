# Lab 6-1 answers: LLM-as-judge

**English** · [简体中文](SOLUTION.zh-CN.md)

> ⚠️ Try it first. Being wrong once beats reading this ten times.

---

## 1. Measured overview

Backend: Claude Code (`claude -p`), measured 2026-07-28, `REPEATS = 3`.
**Everything below held across two independent runs** (numbers moved slightly, the
direction didn't move at all).

| Judge | Correct | Verbosity bias (A vs C, both correct) | Self-consistent | Position bias |
|---|---|---|---|---|
| `keyword` | 3/4 | 0.0 (none) | deterministic | — |
| `score` (no rubric) | 3/4 | **+1.3 ☠** | **2 of 4 unstable** | — |
| `rubric` | **4/4** | 0.0 (none) | **4 of 4 stable** | — |
| `pairwise` | 4/4 | — | — | **0/4 flips** |

---

## 2. `keyword`: can't tell "mentions" from "did"

```
  A short - correct                    score 5   ok correct
  B long - wrong (says allergy, ...)   score 5   x wrong
  C long - correct                     score 5   ok correct
  D short - wrong                      score 1   ok correct
```

**A and B both score a perfect 5.**

What each actually says:

| | Text |
|---|---|
| **A** (correct) | "always say **severe peanut allergy**, ER-level… order no cold dishes at all: Sichuan cold dishes almost all contain crushed **peanut**" |
| **B** (wrong) | "your **peanut allergy** and **no spicy food** — noted" + "**kung pao chicken**… with crisp **peanuts** — the dish out-of-towners take to most easily" |

Both are dense with "peanut", "allergy", "non-spicy". The counter can't separate them.

> **Keywords fail to distinguish three different pairs:**
> - "mentions peanuts" vs "recommends peanut dishes"
> - "acknowledged the constraint" vs "respected the constraint"
> - "said the right thing" vs "did the right thing"

`D` is scored correctly only because it **doesn't bother with the pleasantries** —
it never mentions the allergy at all, so the keywords don't fire. **In other words,
D got graded right for being honestly bad.**

> Same root cause as lab 3-1's false positive, where "non-spicy" matched inside
> "mix spicy and non-spicy 2:1".
>
> **One defect, two labs, two scenarios.** Keyword scoring doesn't fail by
> accident; it fails structurally.

---

## 3. `score`: verbosity bias, measured ★

The most important section here.

```
  A short - correct   scores 2/3/3  avg 2.7   x wrong
  B long  - wrong     scores 1/2/2  avg 1.7   ok correct
  C long  - correct   scores 4/4/4  avg 4.0   ok correct
  D short - wrong     scores 1/1/1  avg 1.0   ok correct

  * clean comparison: A and C are both correct; only length differs
    short A: 2.7     long C: 4.0     gap 1.3
    ! equally correct, yet the long one scored 1.3 higher - that IS verbosity bias
```

### Why this comparison is "clean"

A and C are **equally correct**: both avoid peanuts, avoid spice, and name concrete
restaurants.

So the **1.3-point gap can only come from length**. There is no other variable.

> **That's the general method for measuring bias:**
> **construct a pair that differs only on the dimension you're testing.**
>
> If your two samples differ on three dimensions, the gap you measure **tells you
> nothing.**

The first run measured this gap at **1.7** (A 3.0 / C 4.7); the second at **1.3**.
**Same direction, same order of magnitude — a reproducible systematic bias, not
noise.**

### But state it precisely

A common misreading is "the judge prefers long-and-wrong answers". **Measured, it
does not:**

```
  severe case: long-and-wrong B (1.7) vs short-and-correct A (2.7)
  ok A beat B - not fooled by length
```

**It scored B down.** It saw B's problem.

The real bias runs the other way:

> **It deducts points for being short, even when the answer is fully correct.**

A is a **completely adequate** answer — avoids every hazard, names concrete places,
even supplies the phrasing to use when ordering. Its only "flaw" is being ~110
words. **It scored 2.7 — a bare pass.**

### What this bias costs you

Use this judge to **select** answers, **screen** prompts, or **train** a model and:

> **You get an increasingly verbose agent.**
>
> Not because verbosity is better, but because **brevity is being systematically
> penalized** — and that penalty shows up in your metrics looking like "quality
> improved".

That's what makes evaluation bias so insidious: **it never errors, it just steers
you off course slowly.**

### And it isn't stable with itself

```
  A: 2/3/3  x inconsistent
  B: 1/2/2  x inconsistent
  C: 4/4/4  ok consistent
  D: 1/1/1  ok consistent
```

**Half the answers got different scores from the same judge on three passes.**

Note the pattern: **A and B are the middling cases and they're unstable; C and D
are clearly-good and clearly-bad and they're stable.**

> Which means: **the judge's uncertainty is concentrated exactly where you most
> needed its help.** It's rock solid on the cases you could have called yourself.

---

## 4. `rubric`: fixed in one shot, perfectly stable

```
  A short - correct   scores 5/5/5  avg 5.0   ok
  B long  - wrong     scores 1/1/1  avg 1.0   ok
  C long  - correct   scores 5/5/5  avg 5.0   ok
  D short - wrong     scores 1/1/1  avg 1.0   ok

  1) correct verdicts: 4/4
  2) short A: 5.0     long C: 5.0     gap 0.0   ok no bonus for length
  3) all four stable across 3 repeats
```

**4/4 correct, zero verbosity gap, and 12 judgements without a single fluctuation.**

The only differences between `sys_rubric` and `sys_score` are two things:

### ① Safety as a veto

```
1. Safety (decisive): ... if it recommends peanut-containing or spicy dishes,
   however good it is otherwise, it scores at most 2.
...
Length is not a merit. A correct 50-word answer is far better than a 500-word
one that recommends peanuts.
```

Note that the last sentence **names the bias explicitly**. That isn't a coincidence —
**once you know which way your judge leans, close that road in the rubric.**

### ② A mandatory verbatim quote ★ badly underrated

```
You must quote a short passage from the answer verbatim in `evidence`.
```

Why this one is worth so much:

> Without it, the judge scores **on overall impression** — and impression is
> precisely where length, structure, formatting and tone operate.
>
> With it, the judge must return to the answer and **produce a specific sentence**.
> **Once evidence is required, "looks thorough" stops working** — you cannot quote
> a feeling.

In the measured runs, the evidence the judge cited for B was exactly the kung pao
chicken recommendation. **It was forced to look.**

> ⚠️ But honestly: this lab **did not test those two changes separately**, so I
> can't claim which contributes more. **Exercise 1 is where you take them apart.**
> Don't take my word for it — measure.

---

## 5. `pairwise`: no position bias found, but the method is the point

```
  A vs B: forward winner A, reversed winner A   ok stable
  A vs D: forward winner A, reversed winner A   ok stable
  C vs B: forward winner C, reversed winner C   ok stable
  C vs D: forward winner C, reversed winner C   ok stable

  position bias: 0/4 pairs flipped when the order was swapped
```

**No flips.** Position bias **did not reproduce** on this model with these samples
(the 8th falsified expectation in this repo).

But the value here isn't the result, it's the **method**:

> **This is the only measurement in the lab that needs no ground truth.**
>
> The logic: if A really is better than B, A should win regardless of order. A
> changing winner is a **self-contradiction** — detectable without any external
> standard.

Which means:

> **You can point this at your own eval system today.**
> No labelled data, no annotators, no ground truth. Run every pair in **both
> orders** and count flips.
>
> **Flip rate > 0 means part of your leaderboard is noise.**

The same applies to **self-consistency** (repeat a judgement N times, look at the
variance) — that's how the `2/3/3` above was measured, and it also needs no labels.

> **Two bias checks that cost zero annotation. There is no excuse.**

---

## 6. A trap I fell into while building this (worth its own section)

On the first `score` run, B's three scores came back as **`0/2/2`**.

That `0` wasn't from the model — it was the sentinel my `_clean_score()` returns
when **the JSON fails to parse.**

So what happened was:

- The 0 got averaged in ((0+2+2)/3 = 1.3)
- B was flagged as "self-inconsistent"

**But B wasn't inconsistent — my parser had failed.**

> **A failure of the measuring instrument was recorded as a defect in the subject.**

The fix is in `_ask_with_retry()`: if it doesn't parse, ask again rather than
scoring it 0.

> This deserves calling out because it's **extremely common** in real evaluation:
>
> - API timeout → recorded as "the model couldn't answer"
> - JSON parse failure → recorded as "the model won't follow the format" (sometimes
>   true; sometimes your parser is too strict)
> - No retry on rate limits → recorded as "this batch performed badly"
>
> **A diagnostic**: do your failure rates rise and fall together with the subject's
> apparent quality? If a "worse" model also happens to be slower and time out more,
> you may be measuring your network rather than the model.
>
> **Write tests for your evaluator before you point it at anything else.**

---

## 7. Exercise answers

### Exercise 1 ⭐ Take the rubric apart

This lab didn't split them, so all I can give is an **expectation** and how to judge it:

| Variant | Rough expectation | What to actually watch |
|---|---|---|
| Rubric, no quote | Accuracy probably still decent | Does **stability** drop? (the quote is an anchor) |
| Quote, no rubric | Accuracy likely drops | **Which sentence** does it cite? Without criteria it doesn't know what to look for |

**Don't trust that table — run it.** This is lab 4-1's 2×2 method: **change one
variable at a time.**

If your result contradicts my expectation, **your result is the correct one** —
this repo is up to 8 falsified expectations so far.

### Exercise 2 ⭐⭐ Build an even longer correct answer

Doubling C's length will most likely still score 4–5 under `score`, because 5 is the
ceiling.

**So open up the range**: switch the prompt to 1–10 and measure again. Only then can
you tell whether the bias is **bounded** or roughly **linear**.

> A general evaluation technique: **too narrow a scale hides bias.** On a 1–5 scale
> "very good" and "excellent" are crushed into the same bucket, so you can't see
> whether the judge kept adding points.

### Exercise 3 ⭐⭐ Reason before score

Usually **yes, and it's a free improvement.**

The mechanism is autoregression: **earlier tokens condition later ones.**

```json
{"score": 4, "reason": "..."}     <- score first; the reason is a post-hoc justification
{"reason": "...", "score": 4}     <- reason first; the score is its conclusion
```

In the first, the model picks a number and then writes something to justify it. In
the second, it must lay out the judgement before it's allowed to conclude.

> Same idea as the evidence requirement: **force it to land on specifics before it's
> allowed to conclude.**
>
> ⚠️ Note: this pays off much less on **thinking models**, which already reason
> internally first. **Another instance of advice expiring with model generations.**

### Exercise 4 ⭐⭐⭐ A panel of judges

**Three different judges is clearly the better option.**

The key distinction:

| Approach | Reduces | Does NOT reduce |
|---|---|---|
| One judge, 3 runs, take the median | **Random error** (the 2/3/3 jitter) | **Systematic bias** |
| Three differently-focused rubrics, majority vote | Random error **+ some systematic bias** | Bias the three **share** |

> **Repetition cannot fix systematic bias.** A judge that prefers long answers still
> prefers long answers after a hundred runs — you've just become more confident in
> the wrong answer.
>
> That's elementary statistics, and it's violated constantly in LLM evaluation:
> people use self-consistency to "improve reliability" when it only reduces
> variance, never the offset.

Multiple judges have a ceiling too: if they're all the same base model, **their
biases are correlated.** Real diversity has to come from different models, different
rubrics, and — most expensive and most reliable — **humans**.

### Exercise 5 ⭐⭐⭐ Measure position bias on your own data

Lift `judge_pairwise()`, point it at your evaluation, run every pair both ways.

**This is the one thing in this lab you can use today at zero labelling cost.**

What to do with the flip rate:

| Flip rate | Reading |
|---|---|
| 0% | Position bias isn't significant on these pairs (not proof it's absent) |
| 5–15% | Typical. **Run both orders and require agreement** — double the cost, trustworthy conclusions |
| > 20% | A large part of your leaderboard is coin flips |

---

## 8. Connecting this chapter back

This lab is really an **audit of the previous five chapters.**

Every lab in this repo has a verdict, and their reliability varies enormously:

| Lab | Verdict | Can it misjudge? | Which mode here |
|---|---|---|---|
| 3-1 Memory | keywords | **Yes** (measured) | ← literally `keyword` |
| 2-3 Redaction | regex | Yes (only knows its rules) | |
| 3-2 Retrieval | set membership | No | |
| 4-1 Tools | compare to the one correct call | No | |
| 5-1 Editing | **a real test run** | No, and it checks **behaviour** | ← hardest |

**What orders that list?**

> **The closer the verdict sits to the real consequence, the more reliable it is.**
>
> Keywords judge "what the text looks like" — furthest from consequence.
> Unit tests judge "what the code does" — that *is* the consequence.
>
> LLM-as-judge sits in between: it understands meaning far better than keywords, but
> it still judges **text**, not **outcomes**. **So use tests where you can, judges
> where you can't, and keywords almost nowhere.**

And when a judge is genuinely your only option (open-ended answers, writing,
conversation quality — these really have no unit tests), then:

1. Write an explicit rubric and **name the known bias to close that road**
2. **Require evidence quotes**
3. Measure position bias and self-consistency (**zero labelling cost — no excuse**)

---

← [back to the chapter](../README.md) · [back to the index](../../../README.md)
