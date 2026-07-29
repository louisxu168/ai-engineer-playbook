# Lab 3-4 answers: dense vector retrieval

**English** · [简体中文](SOLUTION.zh-CN.md)

> ⚠️ Try it first. The most valuable part of this lab is predicting how many memories dense
> retrieval rescues — be wrong once before you read on.

---

## 1. Six configurations, one memory, missed by all of them ★★★

Question: `Put together a restaurant list for my Chengdu work trip.`
Corpus: 36 memories · `TOP_K = 5` · measured 2026-07-29 (Apple M3 / Ollama 0.32.5)

Rank of each gold memory out of 36:

| Configuration | peanut allergy ☠ | no spicy | Chengdu trip | recall@5 |
|---|---|---|---|---|
| Chinese · BM25 (sparse) | **#36** | #4 | #1 | 2/3 |
| Chinese · nomic-embed-text | **#21** | **#1** | #2 | 2/3 |
| Chinese · bge-m3 | **#15** | #6 | #1 | 1/3 |
| English · BM25 (sparse) | **#21** | #34 | #1 | 1/3 |
| English · nomic-embed-text | **#34** | #23 | #1 | 1/3 |
| English · bge-m3 | **#19** | #35 | #1 | 1/3 |

**Six configurations: two retrieval methods × two embedding models × two languages.**

> ## ☠ The "ingestion means the ER" memory reaches top-5 in none of them.
>
> The best showing is Chinese bge-m3 at **#15/36** — still 10 places short.

---

## 2. But dense retrieval genuinely works — don't misread this

That table alone invites the conclusion "embeddings are useless". **That's wrong too.**

Look at the "no spicy" column in the Chinese rows:

```
BM25              #4
nomic-embed-text  #1     <- first place
```

"Does not eat spicy food at all" and "restaurant list for my Chengdu work trip" share **not
one keyword**. BM25 only reaches #4 by accidentally matching common characters. Dense
retrieval puts it at **#1** — it really did connect "Chengdu + restaurants" to "spicy".

**That value is real.**

So the correct conclusion is neither "dense wins" nor "dense is useless":

> ### Dense retrieval is not an upgrade over sparse retrieval; it is a **different way of missing**.
>
> | | Misses |
> |---|---|
> | Sparse (BM25) | what doesn't **share wording** |
> | Dense (embeddings) | what isn't **near in semantic space** |
>
> And "restaurant list" and "peanut allergy" simply aren't near enough for an embedding
> model — even though to a **human** it's the first thing to think of when listing
> restaurants.

---

## 3. It misses respectably, which is the dangerous part

The Chinese dense top-5 looks like this:

```
★ 0.7150  does not eat spicy food at all
★ 0.7035  three-day Chengdu work trip 2026-08-03 to 08-09, staying near Chunxi Road
  0.6930  prefers an aisle seat on flights
  0.6650  has a five-year-old ginger cat called Doudou
  0.6601  dislikes subscriptions - buys outright where possible
```

**"Aisle seat", "ginger cat" and "dislikes subscriptions" all score higher than the peanut
allergy (0.5691).**

> If you were reviewing this retrieval system's logs, what would you conclude? Two precise
> hits, three plausible travel-adjacent items — **it looks entirely healthy.**
>
> This is the **same shape** as BM25's failure in lab 3-5: nothing wrong with what came
> back, and no way to know what didn't.
>
> **Retrieval failures do not look like failures.**

Note also that the Chinese similarities are all squeezed into **0.57–0.72**. The most
relevant and the least relevant differ by 0.15 — **you cannot set a threshold at that
resolution.** A rule like "drop anything below 0.6" throws away the peanut allergy and the
cat together, or keeps both.

---

## 4. The ANN half: one table, one variable

`N = 2000` · 768 dimensions · top-10 · averaged over 50 queries

| Method | Build | Per query | Recall | Vectors seen |
|---|---|---|---|---|
| exact (brute force) | 0 ms | 0.120 ms | **1.000** | 2000 / 2000 |
| tree 1 × leaf=32 | 31 ms | **0.019 ms** | 0.204 | **31** / 2000 |
| tree 5 × leaf=32 | 14 ms | 0.077 ms | 0.556 | 141 / 2000 |
| tree 20 × leaf=32 | 67 ms | 0.295 ms | 0.924 | 455 / 2000 |
| tree 5 × leaf=8 | 36 ms | 0.047 ms | 0.358 | 33 / 2000 |
| graph deg=16 ef=10 | 171 ms | 0.227 ms | 0.980 | 171 / 2000 |
| graph deg=16 ef=50 | 171 ms | 0.927 ms | 1.000 | 461 / 2000 |
| graph deg=16 ef=200 | 171 ms | 4.542 ms | 1.000 | 1142 / 2000 |

**Put "vectors seen" next to "recall" and the whole table reduces to one sentence:**

```
see   31 (1.5%)  -> recall 0.204
see  141 (7%)    -> recall 0.556
see  455 (23%)   -> recall 0.924
see  461 (23%)   -> recall 1.000     <- graph
see 2000 (100%)  -> recall 1.000     <- exact
```

> **ANN isn't "smarter retrieval", it's "look at fewer".** Every parameter — number of
> trees, leaf size, ef, degree — is tuning the same thing: **how many you look at.**
>
> Note that at **the same ~460 vectors seen**, the graph gets 1.000 and the tree only 0.924.
> The graph's candidate set is higher quality — at the cost of 2.5× the build time (171 ms
> vs 67 ms), and it needs the **full similarity matrix** (O(N²)), which is itself a problem
> at hundreds of thousands. Real HNSW avoids that with incremental insertion.

### The counter-intuitive row: `leaf=8` is worse than `leaf=32`

```
5 trees leaf=32  ->  saw 141  recall 0.556
5 trees leaf=8   ->  saw  33  recall 0.358
```

Smaller leaves mean a deeper tree and fewer points in the leaf you land in — **a smaller
candidate set**. So "partitioning more finely" doesn't mean "finding more accurately", it
just means "looking at less".

---

## 5. trap: a bug that needs two conditions at once ★★★

**This is the section most worth reading.**

Each cell measured from 20 different entry points:

| Corpus (median nn similarity) | Graph | Stuck | Short of 1.000 | min | median |
|---|---|---|---|---|---|
| evenly spread (0.8646) | out-edges only | 0/20 | 0/20 | 1.000 | 1.000 |
| evenly spread (0.8646) | plus reverse | 0/20 | 0/20 | 1.000 | 1.000 |
| **many near-duplicates (0.9043)** | **out-edges only** | **2/20** | **20/20** | **0.080** | 0.960 |
| many near-duplicates (0.9043) | plus reverse | 0/20 | 0/20 | 1.000 | 1.000 |

**Only one of the four cells collapses, and it needs both conditions.**

- "Stuck" = raising ef from 10 to 200 moves recall **not at all, and it's still below 1.000**
- Those 2 stuck entry points sit at recall **0.080** — 0.8 correct out of 10

### Why it gets stuck

Connecting only to "my nearest neighbours" gives a **directed** graph. The search starts
somewhere and follows out-edges. If the entry point sits inside a clump of near-duplicates,
all 16 of its out-edges **point at other copies inside that clump** — the search can get in
and cannot get out.

Raising `ef` only makes it visit more points *within that clump*. **It genuinely visits more
vectors, all inside the same pocket.** So ef doing nothing isn't "not turned far enough", it
is **cannot get there**.

> **A kNN graph is not the same thing as a navigable graph.**
>
> Add reverse edges (I'm your neighbour, so you link back to me) and the clump now has edges
> leading out. `20/20 short` → `0/20`. **One line of code.**
>
> Those seemingly redundant parts of the HNSW paper — bidirectional links, multiple entry
> points across layers — are solving exactly this. Turning off `undirected` in `ann.py` is
> removing it by hand.

### But the thing to take away is the two "evenly spread" rows

**On an evenly spread corpus the bug does not appear at all.** Both graphs: 0/20, min 1.000.

Which kind is a real memory store? **The near-duplicate kind.** The same preference recorded
again and again across sessions, worded slightly differently — **exactly what lab 3-1's
`remember_all` produces.**

> ☠ So this is a bug that **passes your tests and then breaks in production** — not because
> it's subtle, but because the test data you generated was too clean.
>
> And it raises no error: you get a retrieval system that runs, returns results, and has
> apparently been tuned, with recall 0.080 from some entry points.

---

## 6. Four traps I hit building this lab ★★★

Possibly more useful than everything above. **Each would have produced a wrong conclusion,
and none of them raised an error.**

### Trap 1: the `annoy` library is broken on this machine

I started with the `annoy` and `hnswlib` libraries. First run:

```
ANNOY t=5   recall 0.004
ANNOY t=20  recall 0.004
ANNOY t=50  recall 0.004
```

**I nearly wrote down "ANNOY's recall is catastrophically bad".**

One check later: `get_nns_by_vector(q, 10)` **always returns exactly 1 result** — same with
random vectors, same with euclidean, same on Python 3.11 + numpy 1.x. **The wheel is broken,
not the algorithm.**

> **The symptom was a constant bad number.** Three different tree counts producing an
> identical 0.004 — a parameter having no effect should trigger suspicion immediately.
>
> Incidentally this is why both indexes are now **written from scratch**. The lab depends on
> numpy alone, and the code is in front of you, so when it breaks you can see it.

### Trap 2: the first version of trap didn't reproduce

The first `trap` only contrasted directed vs undirected, on the **evenly spread** synthetic
corpus. Both groups: **1.000**.

I nearly deleted the section on the grounds that "this trap isn't realistic". The real reason
was that **I hadn't supplied the trigger** — it needs a near-duplicate corpus. (My prototype
script generated the corpus by cycling fields modulo, which happened to be degenerate; when
I wrote the lab I switched to random combination and lost the trigger.)

> **The first suspect for "couldn't reproduce" is always the method.** That sentence has
> already come up twice in this repo, in
> [2-1](../../ch2-context-engineering/2-1-local-llm-serving/SOLUTION.md) and
> [2-3](../../ch2-context-engineering/2-3-kv-cache/SOLUTION.md). This is the third time.

### Trap 3: the "ef useless" metric was itself wrong ★

Having fixed trap 2, I counted entry points where recall didn't change from ef=10 to ef=200:

```
spread   · plus reverse edges    ef useless 13/20      <- the fully-correct cell
duplicates · out-edges only      ef useless  2/20      <- the collapsed cell
```

**The metric labelled the best cell as the worst.**

Because "ef does nothing" has two **opposite** causes:
① recall is already 1.000, so of course ef does nothing (**good**)
② the search is trapped in the entry point's clump (**bad**)

The fix is one extra condition: `ef does nothing **and** recall < 0.99`.

> **A metric can be mathematically correct and semantically inverted at the same time.**
> The worst part is that its numbers **look like a conclusion** — 13/20 is bigger than 2/20,
> and a quick glance writes down "reverse edges make it worse".

### Trap 4: the cache key omitted the language, silently loading the wrong vectors ★

Embeddings are cached in `.cache/`. The first version named files `tag-model-count.npy`.

The Chinese and English corpora both have **36 entries**. So when I set `LANG = "en"` and ran
`compare`, it **silently loaded the Chinese vectors** and compared them against an English
query.

The numbers that came out were `Chengdu #6`, `recall 0/3`. Entirely plausible — I was about
to write "dense retrieval fails completely in English".

Fixed, the real English result is `Chengdu #1`, `recall 1/3`. **A completely different
conclusion.**

> **A cache key missing one dimension is a silent wrong-answer generator.** It doesn't error,
> crash, or slow down; it just hands you numbers belonging to a different experiment.
>
> Catching it was luck: I re-checked the English result with a separate script and it
> disagreed with the lab. **Two independent paths giving different answers is the only thing
> that saved me.**

---

## 7. One methodological rule

The four traps are four shapes of the same thing:

> **A failure of the measuring instrument gets recorded as a property of the subject.**

- A broken library → "ANNOY's recall is catastrophic"
- A lost trigger condition → "this trap isn't realistic"
- A semantically inverted metric → "reverse edges make it worse"
- A cache key missing a dimension → "dense retrieval fails completely in English"

**None of the four errored. All four produced a perfectly normal-looking number.**

> This is now the Nth time in this repo —
> [6-1](../../ch6-evaluation/6-1-llm-as-judge/SOLUTION.md)'s JSON parse failure,
> [10-1](../../ch10-multi-agent/10-1-single-vs-multi/SOLUTION.md)'s wrong ground truth,
> [2-8](../../ch2-context-engineering/2-8-system-hint/SOLUTION.md)'s n=3 noise,
> [2-2](../../ch2-context-engineering/2-2-attention-visualization/SOLUTION.md)'s attention
> sink, [2-3](../../ch2-context-engineering/2-3-kv-cache/SOLUTION.md)'s sequential
> measurement.
>
> **The pattern is stable: a number that a parameter doesn't move, or that stays constant, is
> nine times out of ten a bug rather than a finding.**

---

## 8. Exercise answers

### Exercise 1 ⭐ Swap model, swap language
See the table in section 1: **six configurations, the peanut allergy reaches top-5 zero
times.** Note also that bge-m3 lifts the peanut to #15 in Chinese (best of the six) while
dropping "no spicy" from #1 to #6 — **changing model changes what you miss, it doesn't
reduce it.**

### Exercise 2 ⭐⭐ Rescue that memory
Change the **question**, not the model or the algorithm. For example expand the query to:

```
Chengdu restaurant recommendations + dietary restrictions allergies spice level
```

Once "allergies" is in the query, the peanut allergy comes straight up.

> **That is lab 3-5's `expanded` mode**, and it reveals something: **the ceiling on retrieval
> quality is set by the query, not the index.** The law you learned in 3-5 — *compaction
> quality ≈ compaction-prompt quality* — reappears here as **retrieval quality ≈ query
> construction quality.**

### Exercise 3 ⭐⭐ Hybrid retrieval
Normalise each score set, add, take top-5. In the Chinese example, "no spicy" (dense #1) and
"Chengdu" (sparse #1) both make it, while the peanut allergy (sparse #36 + dense #21)
**still doesn't** — something ranked low by both is still low after adding.

> **Hybrid retrieval fixes "strong on one side, weak on the other"; it cannot fix "weak on
> both".** That's precisely why the book has 3-11 `contextual-retrieval` after 3-6: that
> approach **rewrites the indexed text itself** (prefixing each chunk with a context summary)
> rather than changing how you retrieve.

### Exercise 4 ⭐⭐⭐ Multi-branch exploration
`forest_query` currently descends to one leaf per tree. Real ANNOY uses a priority queue,
deciding from the distance to the splitting plane whether the other side is still worth
visiting. Effect: markedly higher recall at the same number of trees, because **the candidate
set is no longer capped by leaf size**.

### Exercise 5 ⭐⭐ Fix the trap a different way
`CORPUS_N = 500`: the trap usually weakens or disappears — the duplicate clumps are smaller,
so out-edges within a clump more easily point outside it.

Adding entry points without reverse edges: **it mitigates, but doesn't fix cleanly.** With 20
random entry points, one landing near the target is enough; but you cannot guarantee that for
every query. **This is why HNSW does both: multiple entry layers and bidirectional links.**

---

## 9. Back to the whole picture

Chapter 3 now has a complete causal chain:

```
3-1  memories get written, but pile up into hundreds (with many near-duplicates)
       | too many to fit, so you must choose
3-5  BM25 chooses wrong - it cannot find what doesn't share wording
       | "just use embeddings"
3-4  dense rescues part of it, but misses the most dangerous memory in all six configs
     and once there are many vectors, exact search is slow too -> ANN, paid for in recall
       | are the two failure modes complementary?
3-6  hybrid retrieval (exercise 3 is its opening move)
       | but what about what's weak on both sides?
3-11 rewrite the indexed text itself
```

**The shape of this chapter: each layer fixes the previous layer's leak and introduces its
own.**

← [back to the chapter](../README.md) · [back to the index](../../../README.md)
