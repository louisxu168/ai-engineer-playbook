# Lab 2-5: A prompt-engineering ablation — which part does the work?

**English** · [简体中文](README.zh-CN.md)

> **What you'll learn**
>
> 1. A headline finding that **didn't reproduce**, and why that's valuable
> 2. How to run an ablation properly: **identical rule text, only the arrangement changes**
> 3. A hard lesson in verdict design: **a rule the model would follow anyway cannot
>    measure your prompt**
> 4. Running the same ablation on a **strong and a weak model** locates a claim's
>    **range of validity**
>
> **How you'll learn it**: mechanical verdict — did it call `issue_refund` *before*
> verifying identity / getting approval? Call order is fully visible to the program.
>
> **Time**: 25 minutes.

---

## The conclusion first: I couldn't reproduce the book's claim

The book's headline result:

> Keep **all** the rule content but **scramble the organisation and remove the
> heading hierarchy**, and task success drops **by more than 30%**.

I rebuilt the experiment and **couldn't reproduce it on either model**:

| | baseline | shuffled | Difference |
|---|---|---|---|
| Frontier model (Claude Code) | 0/3 violations | 0/3 violations | **none** |
| Local 0.6B | 1/3, but looping | 1/3, but looping | **buried in noise** |

**But the failure has content** — see below.

---

## The design

An airline support agent. The correct order is mandatory:

```
verify_identity  ->  check_policy  ->  escalate_to_supervisor  ->  issue_refund
                                       (only when amount > 40000 cents)
```

The order is 48600 cents, **so the approval step always applies**.

### Five modes with identical rule content

| Mode | What changes |
|---|---|
| `baseline` | nothing — headings, numbering, explicit ordering |
| `shuffled` | **the same 10 sentences**, shuffled, headings and numbering removed ★ |
| `tone_hype` | one added line: "be extremely confident and exaggerated" |
| `tone_casual` | one added line: "keep it casual, use emoji 😊" |
| `no_tool_desc` | tools reduced to bare signatures |

**`shuffled` deletes nothing** — verify it yourself:

```bash
python3 -c "import agent; print(agent.rules_shuffled(0))"
```

### The verdict is mechanical

```
Violation A: issue_refund before verify_identity
Violation B: issue_refund above the threshold without escalation   <- * the real verdict
```

---

## Step 0: run everything (8 min)

```bash
cd labs/ch2-context-engineering/2-5-prompt-ablation
python3 agent.py all
```

### 🤔 Predict

How much worse is `shuffled` than `baseline`?

### 👀 What you'll see

Most likely **all five modes: 0 violations, 3/3 completions.**

### 💡 What you learn

**The book's 2024 finding no longer holds on a 2026 frontier model.**

Not surprising — models improved a lot in two years. What's worth thinking about is
**why**:

> Shuffling **deletes no information**. All the model has to do is re-derive the
> priorities and dependencies from 10 scattered rules — **which is exactly what it's
> now good at.**

---

## Step 1: a hard lesson in verdict design (5 min) ★

I went through **three versions** of the verdict; the first two measured nothing.

### v1: "verify identity before refunding"

**0 violations in all five modes.** Why?

> **Because verifying before refunding matches the model's priors.** It doesn't need
> your rule. Scramble it, or delete it entirely, and it still verifies first.
>
> **A rule the model would follow anyway cannot measure your prompt.**

### v2: added a rule it can't guess

So I added: **refunds above 40000 cents require supervisor approval first.**

That threshold is **arbitrary** — no prior gets you there; it's **only knowable from
the prompt**.

**Still 0 violations.** The frontier model finds it even in the scrambled rules.

### v3: switch to a weak model

`--weak` runs the same ablation on local qwen3:0.6b:

```bash
python3 agent.py all --weak      # needs Ollama, see lab 2-0
```

**Now there are violations (1/3) — but they're useless**, because the 0.6B fails a
different way: it calls `verify_identity` eight times in a row and never gets past step one.

> **The signal is drowned by "the model can't do the task at all."**

### The conclusion

```
frontier model   too strong -> scrambling doesn't hurt   -> no discrimination
0.6B             too weak   -> fails for other reasons   -> signal buried
                     ^
       the book's effect lives in a capability band BETWEEN them,
       and I don't happen to have a model in that band
```

> **That's the real output: a piece of advice has a range of validity, and most
> articles won't tell you where it is.**
>
> You now have a measuring tool — **exercise 3 points it at the model you actually ship.**

---

## Step 2: the one dimension that did reproduce (4 min)

Compare `no_tool_desc`'s tool-error count against the other four:

| | Frontier | 0.6B |
|---|---|---|
| Other four modes | 0 errors | 1 – 19 |
| `no_tool_desc` | **1** | **24** |

**Consistent direction on both models: remove tool descriptions, get more call errors.**

The book reports "+45% error rate" for this dimension. My sample is too small for a
percentage, but **the direction holds on both models.**

> This matches [lab 4-1](../../ch4-tools/4-1-tool-design/README.md) exactly, which
> ablates this dimension in a 2×2: **every line you save in a tool description gets
> re-paid at call time.**
>
> **Of the three dimensions, only "tool descriptions" still holds stably in 2026.**

---

## Step 3: change it yourself (exercises)

### Exercise 1 ⭐ Verify `shuffled` really deletes nothing

```bash
python3 -c "import agent; print(agent.rules_structured())"
python3 -c "import agent; print(agent.rules_shuffled(0))"
```

Count the rules on both sides.

> Basic ablation hygiene: **you must be able to prove you changed one variable.**

### Exercise 2 ⭐⭐ More rules, with dependencies

Ten rules is few. Grow it to 40 and make two of them **conditionally dependent**
("in case A follow procedure X, unless B also holds, then Y").

**Predict**: at what rule count does scrambling start to matter?

> The book's τ-bench scenarios carry far more than 10 rules. **That may be the
> difference.**

### Exercise 3 ⭐⭐⭐ Test the model you actually ship ★

Swap `_ask()` for the model your project really uses and run all five modes.

**Those are the numbers you actually need.**

> Because this lab proved the claim's validity **depends on the model**. My numbers
> are useless to you — **the method isn't.**

### Exercise 4 ⭐⭐ Push tone to the extreme

`tone_hype` currently only *adds a line*. Try rewriting the rules themselves in that
voice.

**Predict**: does tone start to matter?

> The book says tone matters little — **but that's with tone and rules kept separate.**
> What if the tone invades how the rules are stated?

---

## Check your answers

After you've tried → **[SOLUTION.md](SOLUTION.md)**

The full three-version evolution of the verdict, both models' data, and why
"couldn't reproduce" is a **conclusion** here rather than a failure.

---

## Appendix

### Three rules for ablation experiments

1. **Change one variable at a time** — `shuffled` deletes no rule
2. **The verdict must be visible to the program** — call order qualifies; "answer quality" doesn't
3. **The verdict must involve something the model wouldn't do by default** — otherwise
   you're measuring its priors, not your prompt

I needed two failed attempts to learn #3.

### When to run an ablation

> When an agent underperforms, **run an ablation before rewriting the prompt**: switch
> off one component at a time and see which matters.
>
> More reliable than guessing — and **most people's instinct is to adjust the tone,
> which is the dimension that matters least.**

---

## Stuck?

| What you see | What to do |
|---|---|
| All five modes look identical | **Same as mine** — that's the finding; see SOLUTION |
| `--weak` errors out | Needs Ollama; see [lab 2-0](../2-0-local-llm/README.md) |
| My `shuffled` IS clearly worse | **That's a finding!** Your model sits in that band — write it down |
| Want to see the actual prompt | Set `SHOW_PROMPT = True` |
