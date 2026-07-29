# Lab 2-4 answers: a prompt-engineering ablation

**English** · [简体中文](SOLUTION.zh-CN.md)

> ⚠️ Try it first.

---

## 1. Measured data

Claude Code (`claude -p`), 3 trials per mode, 2026-07-29

| Mode | Violation A (unverified) | Violation B (unapproved) ★ | Compliant | Tool errors |
|---|---|---|---|---|
| `baseline` | 0/3 | **0/3** | 3/3 | 0 |
| `shuffled` | 0/3 | **0/3** | 3/3 | 0 |
| `tone_hype` | 0/3 | **0/3** | 3/3 | 0 |
| `tone_casual` | 0/3 | **0/3** | 3/3 | 0 |
| `no_tool_desc` | 0/3 | **0/3** | 3/3 | **1** |

Local qwen3:0.6b (`--weak`):

| Mode | Violation B | Compliant | Tool errors |
|---|---|---|---|
| `baseline` | 1/3 | 0/3 | 17 |
| `shuffled` | 1/3 | 1/3 | 1 |
| `tone_hype` | 0/3 | 0/3 | 19 |
| `tone_casual` | 1/3 | 1/3 | 9 |
| `no_tool_desc` | 0/3 | 0/3 | **24** |

---

## 2. Conclusion: the book's claim didn't reproduce

The book reports a **>30% drop** when the organisation is scrambled.

**On the frontier model, `baseline` and `shuffled` are identical** — 0 violations, 3/3.

**On the 0.6B there are violations, but they're meaningless** (section 4).

---

## 3. Three versions of the verdict; the first two measured nothing ★★

Worth more than the conclusion itself.

### v1: "verify identity before refunding"

**0 violations everywhere.**

The reason is clear: **verifying before refunding matches the model's priors.** It
doesn't need your rule. Scramble it, delete it — it still verifies first.

> **A rule the model would follow anyway cannot measure your prompt.**
>
> This is the easiest ablation mistake to make: you think you're measuring "was the
> prompt understood" while actually measuring the model's default behaviour.

### v2: added a rule it cannot guess

So: **refunds above 40000 cents require supervisor approval.**

Arbitrary — I invented the threshold, so it's **only knowable from the prompt**. The
order is 48600, so it always triggers.

**Still 0 violations.** The frontier model extracts it even from scrambled rules.

### v3: switch to a weak model

`--weak` runs qwen3:0.6b. **Violations appear — and are still useless**, because the
call order reads:

```
verify_identity -> verify_identity -> verify_identity -> verify_identity
-> verify_identity -> verify_identity -> verify_identity -> verify_identity
```

**It's stuck on step one, calling `verify_identity` eight times.** 9 of 15 runs look
like this.

> **The signal is drowned by "the model can't do the task."** It isn't violating
> because the rules were scrambled; it never got that far.

### So where does the claim live?

```
frontier   too strong -> untangles scrambled rules fine -> no discrimination
0.6B       too weak   -> can't finish the procedure     -> signal buried
                    ^
        the book's effect lives in a capability band between them,
        and I don't have a model in that band
```

> **That's the real output: advice has a range of validity, and most articles don't
> tell you where it is.**
>
> The book used τ-bench and 2024-era models. Two years on, **the lower edge of that
> band has slid down** — meaning **this advice has largely expired for today's
> frontier models, while probably still holding for small ones.**

---

## 4. The one dimension that did reproduce: tool descriptions

| | Frontier | 0.6B |
|---|---|---|
| Other four modes | 0 errors | 1 – 19 |
| `no_tool_desc` | **1** | **24** |

**Same direction on both models: remove tool descriptions, get more call errors.**

The book reports +45% for this dimension. My sample is too small for a percentage, but
**the direction is stable.**

> This matches [lab 4-1](../../ch4-tools/4-1-tool-design/SOLUTION.md), which ablates
> this dimension in a 2×2 and measures a clean ladder: 5 rounds/3 failures →
> 4/2 → 3/1 → 3/0, each rung matching one specific documentation gap.
>
> **Of the three dimensions, only "tool descriptions" still holds stably in 2026.**
> And it's the one **most often skipped**, because writing descriptions is tedious.

---

## 5. Tone: the book was right

`tone_hype` and `tone_casual` are **identical** to `baseline` on the frontier model.

The book's "models adapt to style easily" — **reproduced.**

> The practical implication matters more than it sounds:
>
> **Tone is exactly what most people adjust when tuning prompts.**
> "You are a professional, rigorous, experienced assistant…" — those words have almost
> no effect on **behaviour**, but you pay for them on every request.
>
> **Spend the effort on tool descriptions and procedural structure, not adjectives.**

---

## 6. Exercise answers

### Exercise 1 ⭐ Verify `shuffled` deletes nothing

Both sides have 10 rules, word for word; only order and formatting differ.

> Basic ablation hygiene. Of the three traps I hit in this lab, two were
> **uncontrolled variables** (a badly chosen verdict, and forgetting to give the model
> the order amount — see the comment in `agent.py`).

### Exercise 2 ⭐⭐ 40 rules with dependencies

The most promising route to reproducing the book's effect:

> Ten rules are trivially scannable. Forty, with conditional dependencies, is where
> headings and numbering start to genuinely affect readability — **for humans, and
> probably for models.**
>
> The book's τ-bench scenarios carry far more than ten rules. **That's likely the difference.**

### Exercise 3 ⭐⭐⭐ Test the model you ship

**The only exercise here that's genuinely useful to you.**

The lab already proved the claim's validity **depends on the model**. My numbers are
useless to you — **the method isn't.**

Swap `_ask()` for your real model and you get three numbers: how much scrambling
costs, how much tone costs, how much removing tool descriptions costs.

**Then you know which dimension deserves your effort** — more reliably than any
prompt-engineering article.

### Exercise 4 ⭐⭐ Push tone to the extreme

Currently `tone_hype` only *adds a line*; the rules stay neutrally worded. Rewrite the
rules themselves in that voice and it may start to matter.

> Because then you've changed **two** things: tone *and* the rules' parseability.
>
> Which illustrates why ablations are hard: **many "dimensions" are entangled in practice.**

---

## 7. "Couldn't reproduce" is a conclusion, not a failure

The 11th falsified expectation in this repo. Worth stating the value:

| Had I… | Consequence |
|---|---|
| Run baseline and shuffled once, seen no difference, dropped it | One fewer conclusion |
| Tuned parameters until a difference appeared | **A false conclusion** |
| Reported honestly plus the three verdict versions | **Readers learn where the claim's boundary is** |

> And this "failure" produced three things:
> 1. A **verdict-design principle**: rules the model already follows measure nothing
> 2. The concept of a **range of validity** for a piece of advice
> 3. A **reusable measuring tool** you can point at your own model
>
> **An experiment's most valuable output isn't always the thing it set out to prove.**

---

← [back to the chapter](../README.md) · [back to the index](../../../README.md)
