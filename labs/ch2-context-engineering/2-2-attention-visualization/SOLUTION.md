# Lab 2-2 answers: attention visualisation

**English** · [简体中文](SOLUTION.zh-CN.md)

> ⚠️ Try it first.

---

## 1. Measured data

Qwen3-0.6B (28 layers × 16 heads), averaged over the last 4 layers and all heads,
2026-07-29

### basic

```
raw:
  ████████████████████████       81.0%  '北京'      <- the sink
  █                               3.0%  '气'
  █                               2.9%  ' 的'

after removing the sink:
  █████████                      29.4%  '气'       <- 天【气】 = weather
  █████████                      28.5%  ' 的'
  ████████                       25.7%  '么'
```

### status_bar

```
[A] no status bar     trace 28.7%   per-char 0.256%
[B] status bar        trace 21.1%   per-char 0.189%
                      status 10.7%  per-char 0.715%   <- only 15 chars

status-bar per-char density = 3.8x the trace's
adding it pulled the trace's attention down by 7.6%
```

### dilution: **did not reproduce cleanly**

```
 67 tokens   needle gets 3.135%
337 tokens   needle gets 5.046%     <- went UP
1309 tokens  needle gets 4.133%
```

---

## 2. The attention sink: the easiest thing to misread ★★

The first token took **81%**.

**That has nothing to do with meaning.** It's a known Transformer artefact, the
**attention sink**: the model needs a default place to put weight when nothing in
particular is relevant, and the first token takes that role. A dustbin.

Strip it and renormalise, and the semantic signal appears:

```
'气'  29.4%      <- "怎么样" attending to 天【气】 (weather) - correct
' 的' 28.5%
'么'  25.7%
```

> **The most practical lesson here: look at raw attention and you will almost
> certainly misread it at first glance.**
>
> Many "attention heatmap" write-ups don't handle the sink, so the first token is
> always the brightest — and the author invents a semantic story for it.
>
> **Exercise 4** has you verify this directly: swap in an irrelevant first word and
> check whether it still takes ~80%.

---

## 3. Status bar: the book's 2-7 reproduces quantitatively ✅

A 15-character status bar attracts **3.8× the per-character attention** of the
112-character trace.

And it **takes attention away from the raw trace**: 28.7% → 21.1%.

The book says:

> Control A: attention highly dispersed; the model is **doing statistics on raw data**
> Control B: attention **highly concentrated on the status bar**

**The measurement supports that**, with a concrete multiple.

> **Pairs with [lab 2-8](../2-8-system-hint/SOLUTION.md):**
>
> | | Measures | Result |
> |---|---|---|
> | 2-6 | **behaviour** | 0.6B violated 50% without, 32.5% with |
> | 2-8 (this) | **mechanism** | 3.8× density difference, 7.6% shifted off the trace |
>
> **Complete only together.** 2-6 says behaviour changed; 2-8 says where the attention
> moved — i.e. **why**.

---

## 4. Dilution: not reproduced, because variables are tangled

```
 67 tokens  3.135%
337 tokens  5.046%     <- went up
1309 tokens 4.133%
```

**Not monotonic.** At least three effects move together:

| Effect | Direction | Note |
|---|---|---|
| **Dilution** | ↓ | more tokens, less each — what I wanted |
| **Distance** | ↓ | the needle drifts further from the question (recency) |
| **Sink** | ? | the first token's share itself varies with length |

**Tangled, so no monotone curve is possible.**

> **But the mechanism is certain** regardless: attention weights must sum to 1
> (softmax), so more tokens means less each on average. That's arithmetic, not
> empirics.
>
> Failing to get a clean curve is **my experimental design failing to control
> variables**, not evidence the mechanism is absent.

**Exercise 3 shows how to untangle it**: fix the needle at a constant distance from the
question and vary only the padding before it.

---

## 5. Four measurement traps I hit in a row ★★★

Possibly more useful than everything above. **Each would have produced a wrong
conclusion, and none of them raised an error.**

### Trap 1: not removing the sink

My first pass concluded "the model attends mostly to 北京".

**Wrong.** That 81% is the sink and is content-independent.

> **Symptom**: the first token is always brightest.
> **If you don't know sinks exist, you'll invent a semantic explanation** — and you'll
> succeed ("well, it's the subject").

### Trap 2: putting the dilution needle at position 0

My first dilution version put the needle at the start, and it held ~78% at every
length — **no dilution measurable at all**.

Because it was **sitting on the sink**. That 78% was never "attention as key
information".

> Fix: move the needle to the middle.
> **A known bias in your measuring tool will disguise itself as your result.**

### Trap 3: matching tokens by keyword

The status_bar version was written as:

```python
for token_text, w in zip(tokens, weights):
    if key in token_text:      # key = "上限"
        total += w
```

**Group B computed 0.000%.**

Chinese tokenisation split "上限" differently, so `"上限" in token_text` was never true —
**no match, silently zero.**

The fix is `return_offsets_mapping=True` to get each token's **character span**, then
select by position rather than text.

> **The scariest symptom of the four**: it produced `0.000%`, a confident-looking number.
> Had I not thought "zero is suspicious", I'd have concluded **the opposite** — that the
> status bar gets no attention at all.

### Trap 4: comparing spans of unequal length

After fixing trap 3: A 85.7% vs B 2.2% — apparently the status bar is irrelevant.

But A measured the **whole trace** (112 chars) and B the **status bar** (15 chars).
**The longer span necessarily wins.**

The right comparison is **per-character density**. Switching to density **reverses** the
conclusion to **3.8×**.

---

## 6. One methodological rule

All four traps are the same thing:

> **Before using a tool to measure, understand the tool's own biases.**

- Attention has a sink bias → misread without removing it
- Tokenisation splits words → text matching fails silently
- Spans differ in length → comparing totals is meaningless

And **none of the four raised an error.** Each returned a perfectly normal-looking number.

> Same lesson as [lab 6-1](../../ch6-evaluation/6-1-llm-as-judge/SOLUTION.md) and
> [lab 10-1](../../ch10-multi-agent/10-1-single-vs-multi/SOLUTION.md):
>
> **A failure of the measuring instrument gets recorded as a property of the subject.**
>
> Fourth time in this repo.

---

## 7. Exercise answers

### Exercise 1 ⭐ A different layer

The usual pattern: **shallow layers track position and syntax** (e.g. strongly attending
to the previous token); **deep layers track semantics.**

Change `LAYERS_FROM_END` to verify. **You can now see this rather than memorise it.**

### Exercise 2 ⭐⭐ A single head

Different heads do very different things — previous-token heads, same-category heads,
heads that mostly stare at the sink.

> **Averaging smears all of it away**, which is why average-only heatmaps invite the
> conclusion that "attention is just a blur".

### Exercise 3 ⭐⭐⭐ Untangle dilution

Hold the needle at a **constant distance from the question**, varying only the padding
before it:

```
[padding x K][needle][fixed-length padding][question]
                      ^ distance to the question is constant
```

Distance is now constant, so what remains is dilution.

> **The most worthwhile exercise here** — it teaches **separating entangled variables**,
> which is exactly what took me three verdict versions to learn in lab 2-4.

### Exercise 4 ⭐⭐ Verify the sink ignores content

Change "北京 的 天气 怎么样" to "香蕉 的 天气 怎么样" (banana's weather). The first
token should **still** take ~80%.

> If so, you've proved that 80% is content-independent — **the first and most important
> lesson in this lab.**

---

← [back to the chapter](../README.md) · [back to the index](../../../README.md)
