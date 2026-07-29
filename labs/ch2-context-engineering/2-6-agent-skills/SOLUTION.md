# Lab 2-6 answers: progressive disclosure

**English** · [简体中文](SOLUTION.zh-CN.md)

> ⚠️ Try it first.

---

## 1. Measured data

Claude Code (`claude -p`), 2026-07-29

| Mode | Peak context | Docs loaded | Answer |
|---|---|---|---|
| `all_loaded` | 1920 chars (~1200 tokens) | 0 | ✓ correct |
| `metadata_only` | 452 chars (~282 tokens) | 0 | **✗ wrong** |
| `progressive` | **1053 chars (~658 tokens)** | **1** | ✓ correct |

**`progressive` got the same correct answer on 55% of the context.**

---

## 2. `metadata_only`'s refusal proves the experiment is sound

It didn't guess. It said:

> "I can only see pptx's one-line description ('generate and edit PowerPoint decks'), and
> **there is no tool to load its detailed documentation or parameter spec**. So I don't
> know whether slide_size takes "16:9", "widescreen", "13.333x7.5in" or something else —
> **any guess could make your call fail outright.**"

This matters because it **proves the information genuinely isn't in the context** — the
model isn't incapable, it just can't see it.

> Which makes `progressive`'s success meaningful: it didn't "already know", **it went and
> fetched the document.**

---

## 3. `progressive` went straight to the target

```
[loaded] pptx / detail   (336 chars)
[answer] slide_size should be "13.333x7.5@96" ...
```

**Two correct judgements:**

1. From twelve one-line descriptions, it identified **pptx**
2. It recognised that "the exact parameter format" lives in the **detail** layer, so it
   **skipped the md layer** and loaded detail directly

It touched none of the other 11 Skills.

---

## 4. Same shape as retrieval, one key difference ★★

Three times now this repo has hit "too many candidates, filter before sending":

| Lab | Candidates | Who filters |
|---|---|---|
| [3-2](../../ch3-memory/3-5-sparse-embedding/README.md) | 36 memories | BM25 (your code) |
| [4-2](../../ch4-tools/4-2-tool-selection/README.md) | 40 tools | BM25 (your code) |
| **2-7 (this)** | 12 Skills | **the model itself** |

### This repairs lab 4-2's failure

What lab 4-2 measured:

> BM25 ranked the correct tool **9th**, cutoff at **8**. The model never saw it and
> (correctly) reported no suitable tool.

**Progressive disclosure has no such failure mode** — the model does the filtering, and
**won't filter away what it needs.**

The cost: **one extra model call.**

```
BM25 retrieval        you decide  ->  fast, cheap, can decide wrong, and it can't tell
progressive disclosure it decides ->  one more round trip, won't miss what it seeks
```

⚠️ Note the qualifier: **"what it knows it's looking for."**

> If the model can't tell that this task needs pptx, no list helps — the bottleneck moves
> to **how well that one metadata line is written** (exercise 1).
>
> In other words: **progressive disclosure converts a "retrieval quality" problem into a
> "description quality" problem.** And description quality is exactly what
> [lab 4-1](../../ch4-tools/4-1-tool-design/README.md) shows has the highest return.

---

## 5. Honest disclosure: this lab is small

`all_loaded` totals only 1920 chars (~1200 tokens), so the gap is about **1.8×**.

```
this lab       12 Skills, ~1200 tokens total   ->  all_loaded is perfectly viable
reality        dozens-hundreds, thousands each ->  all_loaded isn't an option
```

> **The ratio here is compressed by scale. Read the trend, not the multiple.**
>
> Exercise 2 scales it to 100 Skills, where `all_loaded` goes from "expensive" to
> "impossible".

Which is why the mechanism exists at all: not to save 40% of tokens, but to make
**"the Skill library can grow without bound"** possible.

---

## 6. Exercise answers

### Exercise 1 ⭐ Bad metadata

With pptx's metadata vagued to "document-related processing", the model likely won't
think to load it.

> **This is progressive disclosure's true bottleneck.** Only layer 1 is permanently in
> context, **and only it determines whether the model thinks to load anything.**
>
> Echoes lab 4-1 — except the failure here is more insidious: not a wrong argument, but
> **never making the call at all.**

### Exercise 2 ⭐⭐ More and bigger Skills

At 100 Skills × thousands of words:

- `all_loaded` blows the context (or the budget)
- `progressive` is **basically unchanged** — it still loads 1–2 docs

> **That's the real value: context cost doesn't grow with library size.**
> `all_loaded` is O(total Skills); `progressive` is O(Skills actually used).

### Exercise 3 ⭐⭐ A two-Skill task

"Excel data into a 16:9 deck" needs xlsx **and** pptx — and the failure mode is loading
only one and answering too early.

> Same difficulty as lab 3-5's multi-hop retrieval: **what to load second depends on what
> the first load revealed.**

### Exercise 4 ⭐⭐⭐ Hybrid

BM25 down to top-30 metadata, then let the model load within those.

**Is lab 4-2's "9th place, cut at 8" risk back?** Yes — but on metadata, not documents.

> **And the cost is far lower**: metadata is one line each, so a loose cutoff (top-30) is
> affordable. **The looser the coarse filter, the lower the miss probability, at the price
> of a few dozen extra lines.**
>
> **That's the production pattern: coarse-filter where it's cheap, let the model decide
> where it's expensive.**

---

## 7. Back to the chapter

Chapter 2 now has a full taxonomy of context management:

```
2-0  the problem: longer input, pricier prefill
2-4  the trap:    broken prefix, cache never hits
      | so how do you make the context smaller?
2-1  compaction     -- shorten what's long (lossy)
2-7  load on demand -- never put it in (lossless)   <- this lab
      | and how do you make what IS there more usable?
2-6  status bar     -- pre-compute the scattered (information unchanged)
```

**2-1 vs 2-7 is worth stating clearly:**

| | 2-1 Compaction | 2-7 Progressive disclosure |
|---|---|---|
| When | content **is already in**, compress after | content **never entered** |
| Loss | **lossy** (a summary drops detail) | **lossless** (fetched verbatim on demand) |
| Fits | conversation history (already happened) | docs / tools / skills (static, fetchable) |

> **Where progressive disclosure applies, prefer it over compaction** — it's lossless.
> Compaction is for history you had no choice about.

---

← [back to the chapter](../README.md) · [back to the index](../../../README.md)
