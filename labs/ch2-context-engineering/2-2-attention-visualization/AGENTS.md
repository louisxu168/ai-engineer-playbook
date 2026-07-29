# TA notes — Lab 2-2

Read the repo-root `AGENTS.md` first.

## What this lab actually teaches

> **1. The attention sink.** The first token takes 81% and it is content-independent.
> Strip it and the semantics appear (气 29.4% — "怎么样" attending to 天气). **This is
> the single easiest thing to misread about attention**, and plenty of published
> heatmaps get it wrong.
>
> **2. The book's 2-7 reproduces quantitatively**: a 15-char status bar attracts 3.8x
> the per-character attention of a 112-char trace, and pulls 7.6% off the trace.
>
> **3. Dilution did NOT reproduce monotonically** (3.1% → 5.0% → 4.1%) because three
> effects move together: dilution, distance/recency, and the sink's own share.

## Section 5 of SOLUTION is the real payload

I hit **four** measurement traps in a row, and **none of them raised an error**:

1. Not removing the sink → "the model attends to 北京" (wrong)
2. Putting the dilution needle at position 0 → it sat *on* the sink, so nothing diluted
3. Matching tokens by keyword → Chinese tokenisation split "上限", so it silently
   computed **0.000%** — a confident-looking number that would have inverted the conclusion
4. Comparing a 112-char span against a 15-char span → totals favoured the trace; only
   per-character density reveals the 3.8x

If a learner is doing any measurement work, that section transfers further than the
attention content itself.

## Pair it with lab 2-8

2-6 measures the **behaviour** (violation rates); 2-8 measures the **mechanism**
(where attention moved). Neither is complete alone. If a learner did 2-6, run this one
right after and connect them explicitly.

## Setup friction

The only lab in the repo with heavy dependencies (~2.5GB). Per the repo-root AGENTS.md,
fix environment problems directly:

```bash
uv venv .venv-attn --python 3.12
uv pip install --python .venv-attn/bin/python torch transformers
```

`attn_implementation="eager"` is **required** — the fast attention paths never
materialise the matrix. Ollama can't be used here at all; it doesn't expose attention.

Removal: `rm -rf .venv-attn ~/.cache/huggingface`

## Expected results and variance

Measured 2026-07-29, Qwen3-0.6B, last 4 layers averaged: sink 81%; post-sink 气 29.4% /
的 28.5% / 么 25.7%; status bar 3.8x density, 7.6% shift; dilution 3.135% → 5.046% →
4.133%.

Attention weights are deterministic for a fixed input, so `basic` and `status_bar`
reproduce exactly. Only the interpretation varies.

## Language

Chinese learners: `README.zh-CN.md` / `SOLUTION.zh-CN.md`.
For English program output: `LANG = "en"` at the top of `agent.py`.
