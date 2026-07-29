# Lab 3-2 answers: retrieval from scratch

**English** · [简体中文](SOLUTION.zh-CN.md)

> ⚠️ Try it first. Being wrong once beats reading this ten times.

---

## 1. Measured results

Question: `帮我列一个成都出差期间的餐厅清单。`
("Put together a restaurant list for my Chengdu trip.")
Store: 36 memories · `TOP_K = 5`
Backend: Claude Code (`claude -p`), measured 2026-07-28 with `LANG = "zh"`.

| Mode | Retrieved | **Recall** | Model calls | Answer honoured |
|---|---|---|---|---|
| `stuff_all` | 36 | **3/3** | 1 | 2/2 |
| `keyword` | 3 | **1/3** | 1 | **0/2** ☠ |
| `expanded` | 9 | **3/3** | 2 | 2/2 |
| `agentic` | 14 | **3/3** | 3 | 2/2 |

**Two things deserve to be pulled out:**

1. `keyword`'s answer scored **0/2** — not "nearly right", but **both constraints
   violated**. Advice that could send the user to hospital, delivered in a
   thoroughly professional tone.
2. `agentic` spent **50% more calls and returned 55% more items for exactly the
   same recall** as `expanded`. That's the most counterintuitive result here.

> ★ The recall figures in the first two rows (3/3 and 1/3) are computable
> **without any model**. You will get those exact numbers every run. Section 6
> explains why that matters.

---

## 2. `keyword`'s failure: dangerous advice that looks professional

The most important passage in this lab. BM25 returned these three:

```
+- 3 memories retrieved (all the model gets to see) ------
| * Three-day work trip to Chengdu 2026-08-03 to 2026-08-09, near Chunxi Road
|   Company expense policy: max 600 CNY per night for work travel
|   Went to Hangzhou for work last October, stayed by West Lake, poor value
+--------------------------------------------
```

**Nothing is wrong with those three.** Itinerary, budget, prior travel preference —
all relevant to "eating on a Chengdu work trip". If you were reviewing a retrieval
system's logs and saw this, you'd conclude it was working.

Now the answer it built from them (excerpt, translated):

> **[5–10 minutes on foot, easiest]**
> 1. Ma Wangzi Chuan Xiaoguan — modernized Sichuan, pickled-cabbage black fish…
> 2. **Chen Mapo Doufu** — the classic, **mapo tofu + sweet-water noodles**…
> 5. **Zhong dumplings, Lai tangyuan** — for a quick meal in passing.
>
> **[2–4 metro stops, worth a trip]**
> 7. **Yulin skewer hotpot** — relaxed evening with colleagues, 60–80 per person.
> 8. **Xiaolong Fan Dajiang / Shu Daxia** — a proper hotpot outing, safe for hosting.
> 10. **Laoma wontons** — start at lightly numbing, don't order extra-numbing.
>
> **[Practical notes]**
> - Chengdu is hot and humid in August, **don't force heavy spicy hotpot at lunch** —
>   **save hotpot/skewers for the evening**.
> - Remember you found West Lake poor value on the Hangzhou trip — Chengdu is the
>   opposite…

Count the problems:

| Recommendation | Problem |
|---|---|
| Mapo tofu, sweet-water noodles, skewers, hotpot, numbing wontons | All spicy. The user **doesn't eat spicy at all** |
| Zhong dumplings, Lai tangyuan, bobo chicken | Sichuan chilli-oil and sweets routinely contain peanuts. The user's **peanut allergy means the ER** |
| "Save hotpot/skewers for the evening" | It is **actively scheduling** their spicy meals |

And note that last bullet: "remember you found West Lake poor value on the Hangzhou
trip". **It used every retrieved item beautifully.** The model did nothing wrong.

> **The model made excellent use of everything it was given. The problem is that
> the two items that could hospitalize the user weren't among them.**
>
> This is why "retrieval quality" can't be judged on whether the returned items look
> relevant. **Precision measures what came back; recall measures what didn't.**
> The incidents always come from the second one.

---

## 3. Why it was missed: not a ranking problem, a candidacy problem

Run it yourself:

```bash
python3 -c "import agent; print(agent.tokenize('Severely allergic to peanuts'))"
```
```
['severely', 'allergic', 'to', 'peanuts']
```

```bash
python3 -c "import agent; print(agent.tokenize('Put together a restaurant list for my Chengdu trip'))"
```
```
['put', 'together', 'a', 'restaurant', 'list', 'for', 'my', 'chengdu', 'trip']
```

**No content word in common.** (In the Chinese corpus the intersection is exactly
empty; in English the stopword "to" can sneak in — see the note at the end of this
section.)

Look at these lines in `bm25_scores()`:

```python
tf = tokens.count(w)
if tf == 0:
    continue          # <- this memory scores nothing for this query
```

Score is **0**. And in `search()`:

```python
if scores[i] <= 0:
    break             # <- zero-scoring items are dropped entirely
```

**It never entered the candidate list.**

Which is why raising `TOP_K` from 5 to 20 to 36 leaves recall at 1/3. In the
Chinese corpus `keyword` only ever returns 3 items, because only 3 memories in the
entire store share any characters with the query.

> **This isn't a tuning problem. It's the boundary of the technique.**
> With no vocabulary overlap, BM25 has nothing to work with. Changing k1, b, or
> TOP_K saves none of it.

That's precisely why embeddings were invented: "peanut allergy" and "restaurant
recommendation" sit close in vector space not because of shared characters but
because of shared **meaning**.

> **English-only wrinkle worth knowing**: because English tokens include stopwords
> ("a", "to", "for", "my"), the English corpus gives small non-zero scores to
> unrelated items — with `TOP_K = 36` it returns 12 items, including a robot vacuum
> and a MacBook. Recall is still 1/3. Real IR systems strip stopwords for exactly
> this reason; this lab deliberately doesn't, so you can see the noise. Chinese
> bigrams happen to sidestep the problem.

---

## 4. `expanded`: the model closes the semantic gap

The six queries the model produced (measured, translated):

```
• dietary preferences, restrictions, allergies, foods avoided
• spice tolerance, Sichuan cuisine, taste preferences
• work travel, dining occasion, business hosting, party size
• budget, per-head spend, restaurant tier preference
• Chengdu, restaurants visited before, reviews, city experience
• alcohol, coffee, tea, drink habits, vegetarian, religious dietary rules
```

**The very first query contains "allergies" and "restrictions".** The user never
said those words; neither did the question. The model supplied them from common
sense: **it knows restaurant advice must account for allergies.**

9 items retrieved, all 3 targets hit:

```
| * Severely allergic to peanuts - ingestion means the ER
|   Allergic to penicillin                     <- side effect of the "allergy" query
| * Does not eat spicy food at all
|   Prefers to pay with Alipay
|   Prefers an aisle seat on flights
|   Company expense policy: max 600 CNY per night
|   Went to Hangzhou for work last October...
| * Three-day work trip to Chengdu 2026-08-03 to 2026-08-09...
|   Drinks black coffee at breakfast
```

Note that "allergic to penicillin" came along too — that's the **precision** cost:
query expansion raises recall and necessarily drags in irrelevant items.

> **Is that trade good?** Here, overwhelmingly: a few irrelevant memories cost tens
> of tokens; missing the peanut allergy costs a hospital visit.
>
> **When recall and precision aren't symmetric, always protect recall.**

### What this step really is

```
              keyword          vector             query expansion (this lab)
matches on    characters       meaning            characters
bridges via   --               embedding model    the LLM's world knowledge
extra cost    none             run model + store  one model call
infra         none             vector DB          none
```

These aren't substitutes. **Production systems typically run vector + keyword
hybrid, plus query expansion** — because their failure modes differ: vector search
misses exact strings (order IDs, error codes); keyword search misses paraphrases.

---

## 5. `agentic` tied, and cost 50% more — good or bad?

Measured:

| | Recall | Model calls | Items retrieved |
|---|---|---|---|
| `expanded` | 3/3 | 2 | 9 |
| `agentic` | 3/3 | **3** | **14** |

Round 1 produced almost the same queries as `expanded`; round 2 said it was done:

> **[thinking]** Covered allergies, dietary restrictions, spice tolerance, budget
> and venue preferences; the Chengdu itinerary and address are in hand — enough to
> write the restaurant list.

**That judgement is entirely correct.** The problem is that it cost an extra model
call to reach the conclusion "I already finished last round."

> **A loop's value equals the information gained from seeing intermediate results.**
> Here that gain was zero, so the loop bought only latency and tokens.

So when *is* a loop worth it? **When what to search second depends on what you found
first.** For example:

```
user: help me pick a gift for my parents
  round 1: search "parents family" -> finds "parents live in Nanjing, visits every couple of months"
  round 2: only NOW is there a reason to search "Nanjing" - unthinkable in round 1
```

That's **multi-hop retrieval**. Exercise 5 has you construct one.

> **A selection heuristic:**
> If you can ask everything up front, don't loop.
> Loops exist to handle "you don't know in advance what to ask", not to look clever.

Consistent with lab 1-2's conclusion: agentic isn't more advanced, it **trades cost
for robustness under uncertainty**. With little uncertainty, you pay the cost and
get nothing back.

---

## 6. Why this lab's verdict is harder than the others

Recall is the **only** verdict in this repo that needs neither a model nor keyword
matching:

```python
recall_hits = [i for i in TARGET_INDEXES if i in found]
```

Pure set arithmetic. `TARGET_INDEXES` is a hard-coded ground truth; whether an item
came back leaves no room for interpretation.

Compare the rest of the repo:

| Lab | Verdict | Can it misjudge? |
|---|---|---|
| 2-2 Injection | Does a specific marker appear | Almost never (we invented the marker) |
| 2-3 Redaction | Regex match on sensitive formats | Yes (only knows its rule table) |
| 3-1 Memory | Does a keyword appear | **Yes** (a false positive was measured) |
| **3-2 Retrieval** | **Set membership** | **No** |

So `stuff_all`'s and `keyword`'s recall are **fully determined** — change the model,
change the day, run it a hundred times: still 3/3 and 1/3.

> **When designing an evaluation, prefer a metric that doesn't depend on a model.**
> Retrieval happens to allow one (there's a ground truth), which is why the industry
> evaluates RAG on recall@k first rather than on final answer quality.
>
> Because final answer quality conflates retrieval and generation.

---

## 7. Exercise answers

### Exercise 1 ⭐ Try a different question

For `I want to go out with friends this weekend, any suggestions?`, the memories
that matter are "dislikes crowded places" and "cycles most weekends, around 40 km".

In the Chinese corpus:

- "周末常去骑车" contains **周末** (weekend), shared with the question → **found**
- "不喜欢人多拥挤的场所" shares nothing → **not found**

**The pattern**: whether it's findable depends on **whether the memory happened to
use a word from the question** — that's luck, not capability.

> Put differently: **keyword recall is a function of the data distribution, not of
> algorithm quality.**

(In the English corpus this question is noisier still — stopwords pull back Alipay
and penicillin. Same lesson, more mess.)

### Exercise 2 ⭐⭐ Set TOP_K to 36

`keyword` still **isn't** `stuff_all`. Zero-scoring memories are dropped by the
`break` in `search()` regardless of TOP_K. Measured: still 3 items, 1/3 (Chinese);
12 items, 1/3 (English, thanks to stopwords).

Remove the `if scores[i] <= 0: break` as well and it *does* equal `stuff_all` — at
which point **retrieval is doing nothing**: it filters nothing out, it only reorders.

> **The value of retrieval is what it removes.** A retriever that removes nothing
> is a sorter.

### Exercise 3 ⭐⭐ Give memories alias keywords

Rewriting the item as
`Severely allergic to peanuts - ingestion means the ER (diet food restaurant eating)`
introduces the word "restaurant", which the question shares → **recall becomes 2/3**
(verified in both corpora).

**Which is cheaper?** Document expansion, and the advantage scales with query volume:

| | How often | When |
|---|---|---|
| Document expansion | **Once per memory** | At write time (offline, no latency impact) |
| Query expansion | **Once per query** | At query time (online, direct latency) |

If a memory is written once and queried a thousand times, document expansion costs 1
model call and query expansion costs 1000.

⚠️ But document expansion has a hard limitation: **you must guess at write time how
it will later be queried.** Guess incompletely and you still miss. So production
systems do both.

### Exercise 4 ⭐⭐⭐ Hybrid retrieval

The union keeps recall at 3/3 (`expanded` already had them all) while pushing the
retrieved count to around 10.

**Why is nearly every production system hybrid?** Because the two failure modes are
complementary:

| | Good at | Misses |
|---|---|---|
| Keyword / BM25 | Exact strings: order `SO-20260803`, error `PAYMENT_TIMEOUT`, names | Paraphrases |
| Vector / semantic | Synonyms, rewordings, cross-lingual | **Exact strings** (vectors treat `SO-20260803` and `SO-20260804` as near-identical) |

A user searching an order ID getting back a pile of similar-looking order IDs is a
production disaster. Hence the standard design: two retrievers plus fusion ranking
(RRF and friends).

> **It's not "which is better", it's "they miss different things."** Isomorphic to
> lab 1-2's conclusion.

### Exercise 5 ⭐⭐⭐ Construct a case where agentic genuinely wins

Try:

```bash
python3 agent.py agentic  "Help me plan a weekend outing for my parents, and book a restaurant"
python3 agent.py expanded "Help me plan a weekend outing for my parents, and book a restaurant"
```

Why agentic wins: on its single shot, `expanded` can only think of terms like
"parents / family / gift / weekend". It **cannot** think to search "Nanjing" —
before retrieving "parents live in Nanjing" there is no reason to.

Agentic can:

```
round 1: search "parents family" -> retrieves "parents live in Nanjing, visits every couple of months"
round 2: ah, Nanjing -> search Nanjing-related things
```

**That's multi-hop.** The test is simple:

> **Draw the dependency graph. If query B depends on query A's result, you need a
> loop. If every query is independent, fire them all at once.**

Incidentally, this is also why "parallel tool calls" and "loops" are different
things back in lab 1-2: parallelism handles independent queries; loops handle
dependent ones.

---

## 8. Tying the two labs together

3-1 and 3-2 together are one sentence:

> **A memory system = deciding what to keep on write + deciding what to fetch on
> read. Both are filtering problems, both drop things, and they drop things in
> completely different ways.**

| | 3-1 write | 3-2 read |
|---|---|---|
| How it drops | Fails to record (extraction criteria unstated) | Fails to fetch (no literal overlap) |
| Consequence | Information is **permanently lost** | Information still exists, just unused this turn |
| Fix | Rewrite the extraction prompt | Query expansion / vectors / unconditional injection |
| Severity | **Worse** — gone is gone | Milder — next time it might come back |

Which is why real systems lean: **store generously on write, filter hard on read.**
Storage is cheap; loss is irreversible.

And for information that can actually hurt someone (allergies, contraindications,
compliance constraints), the right answer is neither extraction nor retrieval:

> **Keep a separate "always include" list and paste it into every context
> unconditionally.**

Don't put someone's health behind a recall metric.

---

← [back to the chapter](../README.md) · [back to the index](../../../README.md)
