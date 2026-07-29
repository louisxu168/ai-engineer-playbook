# Lab 2-8: Attention visualisation — opening the model up

**English** · [简体中文](README.zh-CN.md)

> **What you'll learn**
>
> 1. The **attention sink**: the first token absorbs **81%** of attention, and it has
>    **nothing to do with meaning** — the easiest thing to misread about attention
> 2. Remove it and the real semantic distribution appears
> 3. The book's 2-7 claim **reproduces quantitatively**: a status bar's per-character
>    attention density is **3.8× the trace's**
> 4. One that didn't reproduce: attention dilution **isn't monotonic**, because three
>    effects are tangled together
>
> **How you'll learn it**: the only lab here that actually **opens the model**.
>
> **Time**: 25 minutes including setup.
>
> ⚠️ **The only lab here with heavy dependencies** (~2.5GB). Skipping it is fine.

---

## Setup

```bash
# A separate venv keeps your environment clean
uv venv .venv-attn --python 3.12
uv pip install --python .venv-attn/bin/python torch transformers

cd labs/ch2-context-engineering/2-8-attention
.venv-attn/bin/python agent.py all
```

First run downloads Qwen3-0.6B (~1.2GB); torch + transformers ~1.3GB.
**Clean removal**: `rm -rf .venv-attn ~/.cache/huggingface`

> Why not Ollama? **It doesn't expose attention matrices.** To see inside you must
> load with transformers *and* pass `attn_implementation="eager"` — the fast paths
> (sdpa/flash) never materialise the attention matrix at all.

---

## Step 1: look at attention (5 min)

```bash
.venv-attn/bin/python agent.py basic
```

Sentence: "北京 的 天气 怎么样" (what's the weather in Beijing). We look at what the
final token attends back to.

### 🤔 Predict

Which word do you think it attends to most?

### 👀 What you'll see

```
  ████████████████████████       81.0%  '北京'
  █                               3.0%  '气'
```

**The first token takes 81%.**

### 💡 What you learn ★

**Not because it's the most semantically relevant — this is the attention sink.**

In a Transformer the first token systematically absorbs a large share of attention
**almost regardless of content**. Think of it as the model's dustbin: when it doesn't
know where to look, it dumps weight there.

The program strips it and renormalises, and *then* the semantics appear:

```
  Distribution after removing the sink:
  █████████                      29.4%  '气'      <- 天【气】 = weather
  █████████                      28.5%  ' 的'
  ████████                       25.7%  '么'
```

**"怎么样" really is attending to "天气"** — but the sink buried that signal.

> **The most practical lesson here: look at raw attention and you will almost
> certainly misread it at first glance.**
>
> Plenty of "attention heatmap" articles don't handle the sink, so the first token is
> always the brightest — and the author invents a semantic story for it.

---

## Step 2: attention dilution (5 min)

```bash
.venv-attn/bin/python agent.py dilution
```

The same fact ("the code is 7391") placed in 67 / 337 / 1309-token contexts.

### 👀 What you'll see

**The three numbers probably aren't monotonically decreasing.** Mine weren't either.

### 💡 What you learn

**At least three effects move at once here:**

| Effect | Direction |
|---|---|
| Dilution — more tokens, less each | ↓ (what I wanted to measure) |
| Distance — the needle drifts further from the question | ↓ (recency) |
| Sink — the first token's share itself varies with length | ? |

**Tangled together, monotonicity disappears.**

> But **the mechanism is certain** regardless of this measurement: attention weights
> must sum to 1 (softmax), so more tokens means less each on average.
>
> That's **context rot**: the window isn't full, but the key fact is drowning in
> irrelevant content.
>
> **Which is exactly what labs 2-1 (compaction) and 2-7 (on-demand loading) address —
> they don't just cut token count, they cut the denominator.**

---

## Step 3: what a status bar looks like in attention (8 min) ★★

```bash
.venv-attn/bin/python agent.py status_bar
```

The book's experiment 2-7: the same Xfinity trace, with and without a status bar.

### 👀 What you'll see

```
  [Control A] no status bar
     trace gets  28.7%   per-char 0.256%

  [Control B] status bar
     trace gets  21.1%   per-char 0.189%
     status bar  10.7%   per-char 0.715%   <- only 15 chars

  * The status bar's per-character density is 3.8x the trace's;
    and adding it pulled the trace's own attention down by 7.6%.
```

### 💡 What you learn

**The book's sentence reproduces, quantified:**

> Control A: attention is highly dispersed; the model is **doing statistics on raw data**
> Control B: attention is **highly concentrated on the status bar**

A 15-character status bar attracts **3.8× the per-character attention** of a
112-character trace — and it **takes attention away** from the raw trace (28.7% → 21.1%).

> **This pairs with [lab 2-6](../2-6-status-bar/README.md):**
>
> - 2-6 measures **behaviour**: the 0.6B violated 50% without a status bar, 32.5% with
> - 2-8 (this lab) measures **mechanism**: where the attention moved from and to
>
> **Only together are they complete**: 2-6 says the behaviour changed; 2-8 says **why**.

---

## Step 4: change it yourself (exercises)

### Exercise 1 ⭐ Look at a different layer

Change `LAYERS_FROM_END` (currently averaging the last 4). Try layer 1 only, or the middle.

**Predict**: do shallow and deep layers attend the same way?

> The usual rule: **shallow layers track position and syntax; deep layers track
> semantics.** You now have the tool to verify that rather than memorise it.

### Exercise 2 ⭐⭐ Look at a single head

Currently 16 heads are averaged. Look at one.

**Predict**: do different heads attend to different things?

> They do, dramatically. Some heads only look at the previous token; some find
> same-category words. **Averaging smears all that structure away** — which is why
> average-only heatmaps invite over-general conclusions.

### Exercise 3 ⭐⭐⭐ Untangle the dilution experiment

Design a version that measures **only** dilution.

**Hint**: fix the needle at a **constant distance from the question** and vary only the
padding before it. That holds "distance" constant.

> The most worthwhile exercise here — it teaches **how to separate entangled
> variables**, which is exactly the trap I hit three times in lab 2-5.

### Exercise 4 ⭐⭐ Verify the sink ignores content

Replace the first word with something irrelevant ("banana's weather is...") and see
whether the first token still takes ~80%.

**Predict**: does it change?

> If it doesn't, you've just proved that 80% **has nothing to do with meaning** — and
> verified the attention sink with your own hands.

---

## Check your answers

After you've tried → **[SOLUTION.md](SOLUTION.md)**

All measured numbers, plus the **four measurement traps I walked into in a row** —
each of which would have produced a wrong conclusion, and none of which raised an error.

---

## Appendix

### Q / K / V in one box

```
Query   what the current token is looking for
Key     what each candidate token is
Value   each candidate token's content

attention weights = softmax(Q · K)   <- the percentages you see in this lab
output = weighted sum of all Values
```

### Three traps when reading attention directly

| Trap | Consequence |
|---|---|
| **Not removing the sink** | The first token is always brightest, and you invent a story |
| **Matching tokens by keyword** | Tokenisation splits words; a miss silently counts as 0 |
| **Comparing spans of unequal length** | The longer span always wins — compare **density**, not totals |

**I hit all three.** See SOLUTION.

---

## Stuck?

| What you see | What to do |
|---|---|
| `x Missing dependencies` | Install torch + transformers as above |
| Slow download | Weights are ~1.2GB; the first run is slow, then it's cached |
| Dilution numbers aren't monotonic | **Same as mine** — see SOLUTION; I couldn't reproduce it cleanly |
| Want it all gone | `rm -rf .venv-attn ~/.cache/huggingface` |
