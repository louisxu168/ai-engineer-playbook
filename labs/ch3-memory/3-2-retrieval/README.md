# Lab 3-2: Retrieval from scratch — why keywords miss what matters

**English** · [简体中文](README.zh-CN.md)

> **What you'll learn**
>
> 1. Write a **BM25** retriever from scratch (under 40 lines, zero dependencies)
>    and understand exactly what it ranks on
> 2. The **structural boundary** of keyword retrieval: when the query and the
>    answer share no keywords, it *cannot* find it
> 3. How to cross that boundary without embeddings: **have the model build the bridge**
> 4. When agentic retrieval is worth it and when it's just burning money (measured)
>
> **How you'll learn it**: the core metric (**recall**) needs **no model at all** —
> it's pure set arithmetic. That part of the result is identical every single run.
>
> **Time**: 25 minutes (no network).

---

## The problem

Lab 3-1 ended on a question: **once memory reaches hundreds of items, it no longer
fits in the context.**

So you need retrieval: pull only the few items **this turn actually needs**.

This lab holds 36 memories (the same person from 3-1, six months on). The user asks:

```
Put together a restaurant list for my Chengdu trip.
```

Three memories must come back:

```
* Severely allergic to peanuts - ingestion means the ER
* Does not eat spicy food at all, not even mildly
* Three-day work trip to Chengdu 2026-08-03 to 2026-08-09, near Chunxi Road
```

**Now stare at the first one and the question for ten seconds.**

```
question: Put together a restaurant list for my Chengdu trip
memory:   Severely allergic to peanuts - ingestion means the ER
```

**Not one shared content word.**

What does keyword retrieval match on? Literal overlap. So — it can't find it.

> That's the wall this lab makes you walk into.

⚠️ 36 items would still fit in a context, and that's **deliberate**: because it
fits, `stuff_all` works as a ceiling, so you can see exactly what the other modes
missed. Real systems hold thousands, and then the `stuff_all` column doesn't exist.

---

## Step 0: establish the ceiling (3 min)

```bash
cd labs/ch3-memory/3-2-retrieval
python3 agent.py stuff_all
```

Press Enter for examples, then type `1`.

### 👀 What you'll see

```
  recall: 3/3  ████████████████████████
  ok honoured: peanut allergy
  ok honoured: no spicy food
```

### 💡 What you learn

**Given the information, it answers correctly.** The point of this step is to rule
out "the model isn't good enough" as a variable — so any later failure can only be
**retrieval's** fault.

> Measuring the ceiling first is a good habit in comparative experiments.
> Otherwise you can't tell "never found it" from "found it and used it badly".

---

## Step 1: run BM25 and see what it drops (6 min) ★ the core

```bash
python3 agent.py keyword "(paste the same question)"
```

### 🤔 Predict

- Of the 3 that must come back, how many will? ___
- The ones that don't — is it because they ranked **6th**, or because they were
  **never candidates at all**? ___

### 👀 What to watch

**What came back, then what was missed, then the answer. All three together.**

### 💡 What you learn

Slow down here. The three items BM25 returned look **entirely reasonable**:

```
* Three-day work trip to Chengdu 2026-08-03 to 2026-08-09, near Chunxi Road
  Company expense policy: max 600 CNY per night for work travel
  Went to Hangzhou for work last October, stayed by West Lake, poor value
```

Itinerary, budget, prior work-travel experience — **every one is relevant to
"Chengdu work trip restaurants"**. The retrieval **looks successful**.

Now read what the answer recommends. (Hint: mapo tofu, sweet-water noodles, hotpot,
skewers, extra-numbing wontons…)

> **The most dangerous retrieval failure isn't returning garbage — it's returning
> a set of plausible-looking hits with the one that matters missing.**

Now answer this: **why was "allergic to peanuts" dropped?**

Verify it yourself:

```bash
python3 -c "import agent; print(agent.tokenize('Severely allergic to peanuts'))"
python3 -c "import agent; print(agent.tokenize('Put together a restaurant list for my Chengdu trip'))"
```

**Do those two lists intersect?**

No intersection → BM25 score is 0 → **it never even became a candidate.**
It wasn't ranked low; it wasn't on the list. No amount of tuning fixes that.

---

## Step 2: understand what BM25 is actually computing (5 min)

Open `agent.py`. Part 2 is under 40 lines and it's the complete algorithm.

Three intuitions, that's all:

| Intuition | In the code |
|---|---|
| The more the query word appears in a doc → higher score | `tf = tokens.count(w)` |
| But a word that's everywhere (like "the") → worth little | `idf = math.log(...)` |
| Longer docs naturally contain more → normalize | `doc_len / avg_len` |

### 🔧 Change one number

Set `TOP_K` from 5 to 20 and re-run `keyword`.

**Predict**: does recall become 3/3?

> The result teaches something important: **this was never a "retrieved too few"
> problem.**

### 💡 Bonus: how Chinese gets tokenized

Chinese has no spaces. The proper approach is a segmenter (jieba etc.), but this
lab uses something simpler:

```
花生过敏  ->  花生, 生过, 过敏
```

**Every adjacent pair of characters becomes a token** (a bigram). Needs no
dictionary, and works surprisingly well for search — real search engines use it as
a fallback for exactly this reason.

---

## Step 3: have the model build the bridge (6 min)

If the problem is that the question doesn't contain the word "allergy", then
**produce that word first**.

```bash
python3 agent.py expanded "(the same question)"
```

### 👀 What to watch

The "queries the model came up with" lines. **This is the most worthwhile output
in the lab.**

### 💡 What you learn

Look at the `sys_expand` prompt in `agent.py`. The load-bearing sentence:

```
The key point: **don't just repeat words from the question.** The word you
actually need usually doesn't appear in the question at all. Asked to
"recommend a restaurant", what you really need is "allergy", "dietary",
"taste" - none of which are in the question.
```

> **The semantic gap is closed by the model, not by the index.**
>
> Vector retrieval (embeddings) solves the same problem by putting "restaurant" and
> "allergy" near each other in vector space. There are no embeddings here, so we use
> the model's **world knowledge** instead: it knows restaurant advice has to account
> for allergies, so it invents the query term itself.
>
> **The two paths cost differently**: vector search needs one call but requires
> running an embedding model and storing vectors; query expansion costs one extra
> model call but needs zero infrastructure.

---

## Step 4: let the agent search, then do the arithmetic (5 min)

```bash
python3 agent.py agentic "(the same question)"
python3 agent.py all     "(the same question)"
```

The difference: `expanded` decides all queries **up front**; `agentic` gets to
**see what came back** before deciding the next move — the loop from lab 1-2.

### 🤔 Predict

Agentic is smarter, so recall should be higher. Right?

### 👀 What to watch

These three rows of the comparison table, together:

```
  recall: ___
  ___ memories retrieved
  model calls: ___
```

### 💡 What you learn

**The answer may surprise you** — the measured numbers are in SOLUTION.

Work out this question first: **when is "being able to see intermediate results"
actually worth something?**

> Hint: if you could have thought of everything in one shot, the loop buys you
> nothing — it only buys latency and tokens.

---

## Step 5: change it yourself (exercises)

### Exercise 1 ⭐ Try a different question

```bash
python3 agent.py keyword "I want to go out with friends this weekend, any suggestions?"
```

**Predict**: does BM25 do better or worse this time? Why?

> Hint: the two that matter here are "dislikes crowded places" and "cycles most
> weekends". Which of them shares a keyword with the question?

### Exercise 2 ⭐⭐ Set TOP_K to 36

That retrieves everything — so is `keyword` now identical to `stuff_all`?

**Think it through**: if it is, what was retrieval buying you in the first place?

### Exercise 3 ⭐⭐ Give memories alias keywords

Manually append keywords to the peanut item, e.g.
`Severely allergic to peanuts - ingestion means the ER (diet food restaurant eating)`,
and re-run `keyword`.

**Predict**: what does recall become?

> This is **document expansion**, the twin of query expansion: one adds terms at
> write time, the other at read time.
> **Which is cheaper?** (Hint: a memory is written once and queried many times.)

### Exercise 4 ⭐⭐⭐ Hybrid retrieval

Take the **union** of `keyword`'s and `expanded`'s results. Look at recall and at
how many items came back.

**Think it through**: why is nearly every production system hybrid rather than
picking one?

### Exercise 5 ⭐⭐⭐ Construct a case where agentic genuinely wins

Right now `agentic` ties `expanded`. Design a question where **agentic is clearly
better**.

**Hint**: think about when you only learn what to search for *second* after
searching *first*. E.g. "help me pick a gift for my parents" — you have to retrieve
"parents live in Nanjing" before you know to search anything about Nanjing.

---

## Check your answers

After you've tried → **[SOLUTION.md](SOLUTION.md)**

Measured output for all four modes, the full text of `keyword`'s
"looks-successful" failure, a cost breakdown, and answers to every exercise.

---

## Appendix: concepts

### The four strategies

| Strategy | Recall | Model calls | Items returned | When |
|---|---|---|---|---|
| `stuff_all` | 100% (necessarily) | 1 | all | Memory small enough to paste (tens of items) |
| `keyword` | **luck of the draw** | 1 | few | Query and documents use the same words (code search, log search, exact match) |
| `expanded` | high | 2 | medium | **Default to this** — one call buys back recall |
| `agentic` | high | 3+ | many | You need **multi-hop**: find A before you know to search for B |

### Keyword vs vector, in one line

> **Keyword retrieval matches *characters*. Vector retrieval matches *meaning*.**
>
> "Peanut allergy" and "restaurant recommendation" share no characters and share
> plenty of meaning. Hence one fails and the other doesn't.

This lab has no vector retrieval (that needs downloadable model weights), so it
gives you a third route: **have the model translate *meaning* back into
*characters***, then hand it to keyword search.

### One engineering principle

> **The most dangerous form of retrieval failure is returning a set of
> plausible-looking results.**
>
> An empty result puts you on alert. A reasonable result that's missing the one
> critical item does not.

Which is why production systems need a **recall backstop**: critical information
(allergies, contraindications, compliance constraints) should never depend on a
retriever hitting it — **paste it into the context unconditionally.**

---

## Stuck?

| What you see | What to do |
|---|---|
| `x No usable backend found` | Install any one of the three options on screen |
| My `keyword` recall is 1/3, same as the docs | **Correct.** That part needs no model and is deterministic |
| My `expanded`/`agentic` numbers differ | **Expected** — the queries are model-generated and vary |
| Want the exact text the model received | Set `SHOW_PROMPT = True` |
| Forgot the commands | Run `python3 agent.py` with no arguments |
