# TA notes — Lab 3-5

Read the repo-root `AGENTS.md` first. This file is specific to this lab.

## What this lab actually teaches

Not "here is BM25". This:

> **Keyword retrieval cannot find what shares no keywords with the query.** Not
> "ranks it low" — it never becomes a candidate. Measured: recall 1/3, and the
> answer built on it violated both of the user's safety constraints (0/2).

And the principle underneath:

> **Precision measures what came back; recall measures what didn't. The incidents
> come from the second one.**

## The moment to slow down is `keyword`'s output, not its recall number

Learners see "recall 1/3" and think they've got it. They haven't. Make them read
the three retrieved items and say out loud whether they look reasonable — they
do. Then make them read the recommendations: mapo tofu, hotpot, skewers, sweet
water noodles, Zhong dumplings.

Ask: *"if you were reviewing this retrieval system's logs, would you have flagged
anything?"*

The lesson is that **a plausible-looking result set is more dangerous than an
empty one**, and no amount of eyeballing the retrieved items catches it.

## Make them prove the "never a candidate" claim

Don't explain it. Have them run both `tokenize()` calls and check the
intersection themselves, then find these two lines:

```python
if tf == 0: continue          # in bm25_scores
if scores[i] <= 0: break      # in search
```

Then have them set `TOP_K = 36` and watch recall stay at 1/3. That experiment is
what converts "it ranked badly" into "it was never on the list".

## The deterministic-metric point is worth making explicitly

Recall here is pure set arithmetic — no model, no keyword matching. It's the only
verdict in this repo that cannot misjudge. If a learner has done 3-1, contrast it
with that lab's measured false positive.

Generalize it for them: **when designing an eval, prefer metrics that don't
depend on a model.** That's why RAG is evaluated on recall@k before answer quality
— answer quality conflates retrieval with generation.

## Don't let them conclude "agentic is better"

Measured, `agentic` tied `expanded` at 3/3 while spending 50% more calls and
pulling back 55% more items. That's the designed finding, not a bad run.

Push to the general rule: **a loop's value equals the information gained from
seeing intermediate results.** Here that gain was zero. Exercise 5 is where they
build a case where it isn't (multi-hop: you must retrieve "parents live in
Nanjing" before you can know to search Nanjing).

## Language wrinkle worth knowing

The Chinese corpus uses character bigrams, which happen to avoid stopwords, so the
query/memory intersection is exactly empty and the numbers are clean. The English
corpus has stopwords ("a", "to", "for", "my"), so unrelated items get small
non-zero scores — `TOP_K = 36` returns 12 items including a robot vacuum. Recall
is still 1/3 and the lesson is unchanged; if an English learner asks about the
noise, that's a real IR topic (stopword removal), deliberately omitted so the
noise is visible.

## Expected results and variance

Measured 2026-07-28, `LANG = "zh"`: recall 3/3 · 1/3 · 3/3 · 3/3; calls 1 · 1 · 2 · 3;
`keyword` answer 0/2.

**`stuff_all` and `keyword` are fully deterministic** — if a learner's numbers
differ there, something is genuinely modified. `expanded` and `agentic` vary,
since their queries are model-generated.

## Language

Chinese learners: `README.zh-CN.md` / `SOLUTION.zh-CN.md`, reply in Chinese.
For English program output: `LANG = "en"` at the top of `agent.py`.
