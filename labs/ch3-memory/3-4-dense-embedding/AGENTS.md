# TA notes — Lab 3-4

Read the repo-root `AGENTS.md` first.

## What this lab actually teaches

> **1. "Just use embeddings" is half true.** Dense retrieval genuinely rescues a memory that
> shares no keywords with the query (Chinese "no spicy": BM25 #4 → dense #1). But the
> life-threatening one (peanut allergy) reaches top-5 in **none of six configurations** —
> 2 methods × 2 models × 2 languages.
>
> **2. Dense is not an upgrade, it's a different way of missing.** Sparse misses what doesn't
> share wording; dense misses what isn't near in semantic space.
>
> **3. ANN's entire trick is "look at fewer vectors."** Every parameter tunes the same thing.
> At N=2000 ANN is a **pure loss** — the crossing is near ten thousand.
>
> **4. `trap` is the payload**: a bug needing two conditions (directed graph AND a
> near-duplicate corpus). One line of code fixes it. On clean test data it's invisible.

## The single most important teaching move

**Do not let a learner walk away with either "embeddings solve it" or "embeddings are
useless".** Both are wrong and both are easy to reach from this lab's data. The finding is
specifically that dense retrieval *moved which memory it missed*. If they only take one
sentence, it's that one.

Get them to predict before `compare` runs. The natural prediction is "both rescued" — being
wrong there is the whole point.

## Section 6 of SOLUTION is the real transferable content

Four traps, none of which raised an error:

1. `annoy` 1.17.3's wheel is broken here (always returns 1 result) — I nearly published
   "ANNOY's recall is catastrophic". Symptom: **a constant number across three parameter
   values.**
2. `trap` v1 didn't reproduce because I lost the trigger (degenerate corpus), and I nearly
   deleted the section as "unrealistic".
3. The "ef useless" metric was **semantically inverted** — it labelled the fully-correct cell
   13/20 and the collapsed cell 2/20, because "ef does nothing" covers both "already perfect"
   and "trapped".
4. The embedding cache key omitted `LANG`; both corpora have 36 entries, so the English run
   **silently loaded Chinese vectors**. It produced plausible numbers (`Chengdu #6`,
   `recall 0/3`) and I was about to write "dense fails completely in English". The real answer
   is `#1`, `1/3`.

Trap 3 and trap 4 are the ones worth walking a learner through — they're the kinds of bug that
produce a *publishable-looking* wrong result.

## Setup friction

Needs Ollama plus an **embedding** model, and numpy:

```bash
ollama pull nomic-embed-text        # 274MB
pip3 install numpy
```

Generative models cannot embed — `qwen3:0.6b` returns "This server does not support
embeddings". The lab detects this and prints a specific message; if a learner hits it, that's
the fix, not a bug.

First `ann`/`trap` run embeds 2000 sentences (~30 s) and caches to `.cache/`. Both `.cache/`
and `.venv/` are gitignored. Deleting `.cache/` is always safe.

No annoy, no hnswlib — both indexes are in `ann.py` (~120 lines, numpy only). If a learner
asks why not use the libraries, the answer is in SOLUTION section 6 trap 1.

## Expected results

Measured 2026-07-29, Apple M3 / Ollama 0.32.5 / nomic-embed-text.

Embedding is deterministic, so `compare` reproduces **exactly**. The ANN recall figures are
also deterministic (fixed seeds). Only the millisecond timings vary — and `scale`'s crossing
point genuinely depends on the machine, so don't treat "near ten thousand" as a constant.

## Pair it with 3-5 and 3-1

- **3-5 first, always.** This lab is the answer to the cliffhanger 3-5 ends on; running it
  first wastes the setup.
- **3-1 explains where the near-duplicate corpus comes from** — `remember_all` produces
  exactly that shape, which is what makes `trap`'s bug realistic rather than contrived.

## Language

Chinese learners: `README.zh-CN.md` / `SOLUTION.zh-CN.md`.
For English program output: `LANG = "en"` at the top of `agent.py`. Note the conclusions
differ by language — that's a finding, documented in SOLUTION section 1, not a bug.
