# Lab 3-4: Dense vector retrieval — what it rescues, what it still misses

**English** · [简体中文](README.zh-CN.md)

> **What you'll learn**
>
> 1. **"Just use embeddings" turns out to be half true.** Dense retrieval rescues
>    some of it — but **the most dangerous memory is not recovered by any of six
>    configurations**
> 2. Dense retrieval is not an **upgrade** over sparse; it's a **different way of missing**
> 3. An ANN index's entire trick is one thing: **look at fewer vectors**. Projection
>    trees and navigable graphs are just two ways of looking at fewer
> 4. A knob that **does absolutely nothing** — and only on data of a particular shape,
>    so it passes your tests and then breaks in production
> 5. **ANN is a pure loss at 2,000 vectors.** The crossing is near ten thousand
>
> **How you'll learn it**: both indexes are written from scratch in `ann.py` using only
> numpy — no annoy, no hnswlib. Every recall figure is computed **mechanically** (part 1
> against hardcoded gold answers, part 2 against exact search); no model acts as judge.

---

## Starting from the hole lab 3-5 left

[Lab 3-5](../3-5-sparse-embedding/) ended somewhere uncomfortable:

```
user asks:        Put together a restaurant list for my Chengdu work trip
memory needed:    Severely allergic to peanuts - ingestion means the ER

                  Not one shared word -> BM25 scores it zero
```

Almost every tutorial says the same thing next: **"keyword retrieval's limits are what
embeddings are for."**

This lab doesn't repeat that sentence. It **measures it**.

---

## Setup (once, 5 minutes)

Same Ollama setup as chapter 2, plus one **embedding model**:

```bash
ollama serve                      # leave running in another terminal
ollama pull nomic-embed-text      # 274MB
pip3 install numpy                # the only third-party dependency
```

No API key.

> ⚠️ **Generative models cannot embed.** Put `qwen3:0.6b` in and Ollama replies
> `This server does not support embeddings` — these are two different kinds of model.
> This lab detects that and tells you plainly rather than failing obscurely.

---

## Step 1: dense vs sparse (3 minutes) ★★★

```bash
python3 agent.py compare
```

It asks what to retrieve. **There is deliberately no default** — retrieval quality depends
entirely on what you ask. To reproduce the numbers below, enter `1` (the Chengdu restaurant
question, the same one lab 3-5 used).

### Predict first

Same 36 memories, same question: will dense retrieval recover the two that BM25 missed?

- [ ] Both — this is exactly what embeddings were invented for
- [ ] One of them
- [ ] Neither

### 👀 What you'll see

```
  Where each of the three gold memories ranks (out of 36):
    Severely allergic to peanuts       sparse #21   dense #34
    Does not eat spicy food at all     sparse #34   dense #23
    Three-day work trip to Chengdu     sparse #1    dense #1
```

(Those are the **English** corpus numbers. In Chinese: peanut `#36 -> #21`, spicy
`#4 -> #1`, Chengdu `#1 -> #2`.)

### 💡 What you learn

**In Chinese, look at the spicy row: `#4 -> #1`.** Dense retrieval genuinely works — it
promoted to first place a memory that shares **not one keyword** with the question. That
value is real.

**Now the peanut row.** `#36 -> #21` in Chinese, and in English it goes the **wrong way**:
`#21 -> #34`.

Rank 21 of 36 isn't "close". It's **unreachable by this route**. And it happens to be the
memory whose omission sends someone to hospital.

> **Dense retrieval is not an upgrade over sparse retrieval.**
>
> It's a **different way of missing**: sparse misses what doesn't share wording, dense
> misses what isn't nearby in semantic space — and "restaurant list" and "peanut allergy"
> simply aren't near enough for an embedding model.
>
> Worse, **it misses respectably**: dense's top-5 contains "prefers an aisle seat" and "has
> a ginger cat called Doudou", both scoring *higher* than the peanut allergy. Reviewing the
> logs, nothing looks wrong.

### One step further (worth doing)

Set `MODEL` to `bge-m3` (`ollama pull bge-m3`) and run again; then set `LANG = "en"` and run
again. **Four combinations.** Count: in how many does the peanut allergy make top-5?

The answer is in SOLUTION, but **counting it yourself lands very differently.**

---

## Step 2: once there are a lot of vectors (5 minutes)

36 memories don't need an index. Real memory stores hold hundreds of thousands — and then
"compute everything" becomes the bottleneck. That is what the book's version of this
experiment is actually about.

```bash
python3 agent.py ann
```

It generates 2,000 synthetic memories, embeds them (~30s, then cached), and compares three
indexes. Both ANN indexes live in `ann.py`, under 120 lines total.

### Predict first

Projection tree (ANNOY's idea) and navigable graph (HNSW's idea): at 2,000 vectors, which
one beats exact search?

### 👀 What you'll see

```
  method                      build    per query    recall    vectors seen
  exact (brute force)         0 ms    0.120 ms     1.000     2000/2000
  tree  trees=1  leaf=32     31 ms    0.019 ms     0.204       31/2000
  tree  trees=5  leaf=32     14 ms    0.077 ms     0.556      141/2000
  tree  trees=20 leaf=32     67 ms    0.295 ms     0.924      455/2000
  graph deg=16 ef=10        171 ms    0.227 ms     0.980      171/2000
  graph deg=16 ef=50        171 ms    0.927 ms     1.000      461/2000
  graph deg=16 ef=200       171 ms    4.542 ms     1.000     1142/2000
```

### 💡 What you learn

**"Vectors seen" is the column that explains the other three.**

Exact search sees all 2,000, so recall is necessarily 1.000. An ANN index's entire trick is
**seeing fewer**: fewer is faster, and fewer misses more. `trees=1` sees 31 (1.5%), so it's
6× faster, so recall is 0.204.

> **There is no "which is better" in this table, only "where do you want to stop".**
>
> And look at the **absolute** numbers: `tree trees=20` takes 0.295 ms/query, **slower than
> exact search's 0.120 ms**, for recall of only 0.924. At this scale it's a pure loss. Step
> 4 shows when it stops being one.

---

## Step 3: a knob that does absolutely nothing (3 minutes) ★★

```bash
python3 agent.py trap
```

Graph indexes have a parameter `ef`: the candidate-queue size, i.e. how many "best so far"
results you may hold at once. Textbook says higher ef, higher recall.

This step crosses two variables: **whether reverse edges are added** when building the graph
(one line in `ann.py`), and **whether the corpus is evenly spread or packed with
near-duplicates**. Each cell is measured from 20 different entry points.

### Predict first

In which cell does ef stop working?

### 👀 What you'll see

```
  Corpus: evenly spread (median nearest-neighbour similarity 0.8646)
    only "my neighbours"     stuck  0/20   short of 1.000  0/20   min 1.000
    plus reverse edges       stuck  0/20   short of 1.000  0/20   min 1.000

  Corpus: many near-duplicates (median nearest-neighbour similarity 0.9043)
    only "my neighbours"     stuck  2/20   short of 1.000 20/20   min 0.080  !
    plus reverse edges       stuck  0/20   short of 1.000  0/20   min 1.000
```

### 💡 What you learn

**Only one of the four cells collapses**, and it collapses hard: **all 20** entry points
fall short of 1.000, and 2 of them don't move *at all* when ef goes from 10 to 200 —
recall 0.080.

One line of code (reverse edges) turns `20/20 short` into `0/20`.

> **A kNN graph is not the same thing as a navigable graph.** With only outgoing edges the
> search gets trapped in the entry point's pocket — it genuinely visits more vectors, all
> inside the same pocket. Those seemingly redundant parts of the HNSW paper (bidirectional
> links, multiple entry points) are solving exactly this.

**But the thing to take away is the two "evenly spread" rows: the bug doesn't appear at all.**

And a real memory store **is** the near-duplicate one — the same preference recorded again
and again across sessions, worded slightly differently. **That is exactly what lab 3-1's
`remember_all` produces.**

> ! So this bug **passes your tests and then breaks in production** — not because it's
> subtle, but because your test data was too clean. And it raises no error.

---

## Step 4: at what scale does ANN pay off (2 minutes)

```bash
python3 agent.py scale
```

```
    vectors    exact ms/query   tree(20)     winner
      2000       0.169 ms      0.311 ms    exact 1.8x
     10000       1.327 ms      0.508 ms     tree 2.6x
     50000       6.307 ms      1.180 ms     tree 5.3x
    200000      27.322 ms      1.230 ms    tree 22.2x
```

**Exact is O(N), the tree is O(log N) — two lines with different slopes, and they cross.**

The crossing sits somewhere near ten thousand. To its left, ANN is a pure loss: several
hundred more lines of code, an extra index in memory, recall below 1.000 — in exchange for
being **slower**.

> Lab 3-5's 36 memories and the 2,000 here are **both left of the crossing.** Measure which
> side your N is on before reaching for an ANN index.

---

## Try it yourself

### Exercise 1 ⭐ Swap model, swap language
Set `MODEL` to `bge-m3` and `LANG` to `"en"`, and run `compare` for all four combinations.
In how many does the peanut allergy make top-5?

### Exercise 2 ⭐⭐ Rescue that memory
Without changing model or algorithm — only the **question**. How do you have to ask for the
peanut allergy to reach top-5? (Hint: that's what lab 3-5's `expanded` mode does.)

### Exercise 3 ⭐⭐ Hybrid retrieval
Normalise the sparse and dense scores, **add them**, then take top-5. Does recall change?
This is the core idea of the book's 3-6 `retrieval-pipeline`.

### Exercise 4 ⭐⭐⭐ Raise the tree's recall without slowing it down
`ann.py`'s `forest_query` currently descends to **one** leaf per tree. Real ANNOY explores
several branches at once with a priority queue. Add that.

### Exercise 5 ⭐⭐ Reproduce the trap, then fix it a different way
Set `CORPUS_N` to 500 and run `trap`: is the trap still there? Why? Then, without adding
reverse edges, increase only the number of entry points — can that fix it?

---

## Where to go next

- **The book's 3-6 `retrieval-pipeline`**: sparse + dense + reranking. Exercise 3 is its
  opening move.
- [Lab 3-5](../3-5-sparse-embedding/): if you haven't done it, do that one first.
- [Lab 3-1](../3-1-user-memory/): where near-duplicate corpora come from.

Answers and full analysis: [SOLUTION.md](SOLUTION.md) (**after you've tried**)

← [back to the chapter](../README.md) · [back to the index](../../../README.md)
