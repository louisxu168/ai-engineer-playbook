# Lab 3-1 answers: user memory

**English** · [简体中文](SOLUTION.zh-CN.md)

> ⚠️ Try it first. Being wrong once beats reading this ten times.

---

## 1. Measured results

Question: `帮我列一个成都出差期间的餐厅清单。`
("Put together a restaurant list for my Chengdu trip.")
Backend: Claude Code (`claude -p`), measured 2026-07-28.

| Mode | Memory size | Key facts | Junk | Stale fact | Answer honoured |
|---|---|---|---|---|---|
| `no_memory` | 0 chars | 0/2 | 0 | n/a | 1/2 ⚠️ false positive |
| `full_log` | 199 chars | 2/2 | **5 items** | ✗ still there | 2/2 |
| `naive_extract` | **268 chars** | 2/2 | **5 items** | ✗ still there | 2/2 |
| `extracted` | 195 chars | 2/2 | **0 items** | ✗ still there | 2/2 |

**Two results deserve to be pulled out:**

1. **`naive_extract` came out bigger than `full_log`** (268 > 199). When I designed
   this lab I expected "smaller but dirty". It measured **bigger *and* dirty**.
2. **None of the four modes passed the "stale fact" test** — not even the
   best-written extraction prompt. That's not the prompt's fault, it's the
   architecture's. Section 4 unpacks it.

---

## 2. All four memory files

Read this section alongside the files your own run produced.

### `memory_full_log.json` — stored verbatim

```json
[
  "我对花生过敏，吃到会直接送医院，这个千万记住。另外我完全不吃辣，一点都不行。",
  "我在北京国贸上班，做后端开发，平时中午就在公司楼下吃。",
  "今天下雨我忘带伞，淋了一路，现在有点感冒，晚上打算早点睡。",
  "上周末去了趟环球影城，人太多了，排队排到怀疑人生，我是真受不了人挤人的地方。",
  "更新一下：我下个月调岗，以后常驻上海浦东了，北京这边不去了。",
  "我下周要去成都出差三天，住在春熙路附近。"
]
```

Zero thought, zero information loss. Exactly one problem: **this list only ever
gets longer.**

### `memory_naive_extract.json` — careless extraction (10 items, 268 chars)

```json
[
  "用户对花生严重过敏，误食会导致需要送医院的严重反应，任何饮食相关建议必须严格排除花生",
  "用户完全不吃辣，不能接受任何辣度",
  "用户在北京国贸上班",
  "用户从事后端开发工作",
  "用户平时中午在公司楼下吃午饭",
  "用户今天（2026-07-28）下雨忘带伞被淋湿，之后有点感冒，打算晚上早点睡",   <- junk
  "用户不喜欢人多拥挤的地方，讨厌排长队",
  "用户上周末（约2026年7月中下旬）去了环球影城，因人多排队体验很差",         <- junk
  "用户下个月调岗，之后常驻上海浦东，不再去北京",
  "用户下周（相对 2026-07-28）要去成都出差三天，住在春熙路附近"
]
```

### `memory_extracted.json` — good extraction (9 items, 195 chars)

```json
[
  "对花生过敏，误食会送医院（严重过敏）",
  "完全不吃辣，一点辣都不能接受",
  "在北京国贸上班",
  "职业：后端开发",
  "工作日中午通常在公司楼下吃午饭",
  "不喜欢人多拥挤的场所",
  "常驻工作地为上海浦东（2026年8月起调岗生效）",
  "不再在北京工作",
  "2026-08-03 至 2026-08-09 期间（表述为「下周」）赴成都出差三天，住在春熙路附近（此条为临时行程，出差结束后失效）"
]
```

---

## 3. Item by item: what the good prompt actually bought

Side by side, there are four differences, each mapping to one criterion in
`extract_good`.

### Difference 1: an entire noise session — one kept it, one dropped it

Session 3 (rain / forgot umbrella / cold / early night):

| | Result |
|---|---|
| `naive_extract` | Recorded it: "user got soaked today (2026-07-28), now has a cold, plans an early night" |
| `extracted` | **Nothing at all** |

That's criterion #2: "**explicitly drop present state**: today's weather, current
mood, temporary ailments".

> **If you don't say it, it doesn't know you don't want it.** "Extract the
> information" is a neutral instruction — weather is information; a cold is
> information.

### Difference 2: the theme park — same paragraph, different extraction

Session 4 contains two things: a **one-off event** (went to Universal Studios) and
a **durable preference** hiding inside it (can't stand crowds).

| | What it extracted |
|---|---|
| `naive_extract` | **Both**: the preference AND the event |
| `extracted` | **Only the preference**: "dislikes crowded places" |

This is the prettiest moment in the lab. **Good extraction isn't transcription —
it's pulling a reusable conclusion out of a specific event.** Nobody cares whether
this person goes to a theme park next month; "hates queues" is still useful a year
from now.

> Side note: `full_log`'s final answer contained the line "you don't like crowds
> and queuing, so I picked places that take bookings or are easy off-peak".
> **Junk isn't just dead weight — it gets read and it shapes output.** This time
> the effect was positive. You can't count on that.

### Difference 3: time bounds

Session 6, "three-day trip to Chengdu next week":

| | How it was written |
|---|---|
| `naive_extract` | "next week (relative to 2026-07-28) …" |
| `extracted` | "**2026-08-03 to 2026-08-09** … (**temporary itinerary, void after the trip**)" |

Criterion #3. "Next week" is wrong a month later; a date range is always right,
and the expiry note means the read path can filter it.

### Difference 4: size — why careless extraction came out *bigger*

The counterintuitive one:

```
full_log        199 chars   6 items  (= the 6 raw sessions)
naive_extract   268 chars   10 items  <- 35% MORE than the raw text
extracted       195 chars   9 items
```

Because every `naive_extract` item adds boilerplate:

```
original: 我在北京国贸上班，做后端开发          (13 chars)
naive:    用户在北京国贸上班
          用户从事后端开发工作                  (18 chars, 2 items)
```

The prefix "用户" ("the user") repeats on every line, and splitting one sentence
into two items multiplies that overhead.

> **Extraction ≠ shrinking.** The value of extraction is **dropping what shouldn't
> be kept**, not compressing characters. An extractor with no selection criteria is
> a pure negative: you paid for a model call and got a *larger*, equally dirty
> memory.
>
> I got this wrong when designing the lab — see section 7.

---

## 4. The test all four modes failed: a fact that changed

In session 5 the user said: "transferring, based in Shanghai Pudong from now on,
no longer going in to Beijing."

So "works in Beijing, Guomao" should be **deleted**. Measured:

| Mode | Beijing still in memory? |
|---|---|
| `full_log` | ✗ yes (session 2 verbatim) |
| `naive_extract` | ✗ yes ("用户在北京国贸上班") |
| `extracted` | ✗ yes ("在北京国贸上班") |

**Even the best extraction prompt failed.** Why?

Look at what actually gets sent in `update_memory()`:

```python
raw_text = complete(t("extract_input") + session_text, extract_prompt, backend=backend)
```

`session_text` is **this one session's text** and nothing else. While processing
session 5, the model **cannot see** the memory item that session 2 wrote.

> **It didn't fail to delete — it didn't know there was anything to delete.**

Worth noting: `extracted` did the best it could, writing both

```
"常驻工作地为上海浦东（2026年8月起调岗生效）",
"不再在北京工作"
```

So **the contradiction is resolvable** — a model reading all three lines can work
out the truth. But that's luck, not design: memory now holds A and not-A
simultaneously and delegates reconciliation downstream. As item count grows, these
self-contradictions accumulate.

### The correct architecture

Memory update shouldn't be append. It should be **read-modify-write**:

```
load existing memory -> send it WITH the new session -> model emits add / update / delete
```

That's the core loop in mem0, Memobase and similar frameworks. Exercise 3 has you
build it.

**The cost**: every update now sends the existing memory, so token cost grows with
memory size. Real systems therefore add a layer that only pulls **possibly
relevant** memories into the update — which is a retrieval problem again.

> That's the real shape of a memory system: **the write is a retrieval problem and
> so is the read.**

---

## 5. That `1/2` for `no_memory` is a false positive

The program scored `no_memory`'s answer as "✓ honoured: no spicy food". The
actual text:

> 3. **Do you eat spicy food?** Back-to-back hotpot on a work trip is a real
>    question for your stomach. I usually suggest a 2:1 mix of **spicy and
>    non-spicy**.

The characters for "non-spicy" are genuinely there — but the model was **asking
the user whether they eat spice**, then offering generic advice. That is nothing
like "knew you avoid spice, so I avoided it."

**Keyword scoring does this.** Every automatic verdict in this repo has the
problem, to differing degrees:

| Lab | Verdict | Reliability |
|---|---|---|
| 2-2 Injection | Does a specific marker appear | **High** — we invented the marker; it never occurs naturally |
| 2-3 Redaction | Regex match on sensitive formats | **Medium** — only recognizes formats in the rule table |
| 3-1 Memory | Does a keyword appear | **Low** — "non-spicy" can show up many ways |

> Fine for a teaching lab, because **you also read the full output**. But if you're
> building a real evaluation: **don't use keywords — use LLM-as-judge, and spot-check
> the judge itself by hand.**

The source book's `user-memory-evaluation` project is entirely about this and is
worth reading.

Also worth saying: `no_memory` actually behaved **well** here — it didn't invent
anything, it asked four honest clarifying questions. That's correct model
behaviour. The only cost is that **the user has to repeat what they already said.**

---

## 6. Exercise answers

### Exercise 1 ⭐ Add a session to the script

After adding "I'm cutting weight lately, no carbs at dinner":

- `full_log`: one more verbatim line
- `naive_extract`: likely split into two items ("cutting weight" + "no carbs at dinner")
- `extracted`: one item, possibly annotated as a phase that may change

**Watch whether it registers that "cutting weight" is temporary**, not whether it
recorded it. Criterion #3 (time-bounded facts carry their bound) is awkward here
because there's no explicit end date. Real systems handle this class with
**confidence decay**.

### Exercise 2 ⭐⭐ Break `extract_good` on purpose

Delete criterion #2 and re-run: junk goes from 0 to somewhere between 2 and 5
(it varies), and size grows.

**Conclusion: of those five lines, #2 does most of the work.**

Exactly matching lab 2-1's finding: in a compaction/extraction prompt, **"what to
drop" is worth more than "what to keep"** — because the model can guess what you
want, and cannot guess what you don't.

### Exercise 3 ⭐⭐⭐ Make memory revisable

Reference implementation (replacing the extraction branch of `update_memory()`):

```python
existing = load_memory(mode)
prompt = (
    "Here is what you already remember about the user:\n"
    + json.dumps(existing, ensure_ascii=False, indent=2)
    + "\n\nHere is the newest session:\n" + session_text
    + "\n\nOutput the UPDATED COMPLETE memory list. Rules:\n"
      "1. If the new session contradicts an old memory, delete the old one\n"
      "2. If it adds detail, rewrite that item - don't add a second one\n"
      "3. Memories not mentioned stay as they are\n"
)
raw_text = complete(prompt, t("extract_good"), backend=backend)
memories = parse_json_reply(raw_text).get("memories", [])
save_memory(mode, memories)          # note: overwrite, not extend
```

Only two differences, but both structural:

1. **Extraction can see existing memory** (`existing` is in the prompt)
2. **Saving overwrites instead of appending** (`save_memory`, not `memories.extend`)

Run it and the Beijing entry usually disappears.

**But notice the new risk it introduces**: every update now gives the model a
chance to **wrongly delete** a correct memory. `full_log` can never lose
information. This design can.

> **That's the central trade-off of memory systems:**
> Appending can only get dirty; rewriting gets clean but can get things wrong.
>
> The common production compromise is a **soft delete** — mark it void rather than
> removing it, and filter on read. You keep correctness and you can roll back.

### Exercise 4 ⭐⭐⭐ What happens when memory gets big

500 items pasted into a context hits chapter 2's wall. But **compaction is the
wrong tool here.**

The dividing line: **can you know in advance which few items this turn needs?**

| | Compaction (2-1) | Retrieval (3-2) |
|---|---|---|
| Fits when | Everything is relevant, just too long | Most of it is irrelevant |
| Method | Make all the content shorter | Pull out only the relevant few |
| Cost | Guaranteed information loss | May fail to retrieve what mattered |

The user asks "what should I eat in Chengdu"; of 500 memories maybe 3 matter
(allergy, no spice, itinerary). **Compressing 500 into a summary dilutes those 3
too.** The right move is retrieving those 3.

> Which is why a memory system is inherently a retrieval system. That's the next lab.

### Exercise 5 ⭐⭐ Give memories an expiry

"Who decides it's expired" — **both sides, with different jobs:**

| | Write path | Read path |
|---|---|---|
| Does what | Records an `expires` field (a date) | Compares now against `expires` |
| Why here | Only the write knows the context ("next week" relative to *when*) | Only the read knows what "now" is |

Suggested shape:

```json
{"text": "three-day Chengdu trip, staying near Chunxi Road", "expires": "2026-08-09"}
```

**The write path must convert relative time into absolute time**, or the read path
has nothing to compare — which is exactly what `extract_good` criterion #3 does.

⚠️ A common trap: **don't actually delete** on expiry. The user may later ask
"where did I stay in Chengdu last time?" The right move is to drop it out of
*active* memory while keeping it searchable in history.

> **Expired ≠ useless. Expired just means "no longer pulled into the context by
> default".**

---

## 7. Somewhere I designed this wrong

Worth writing down, because it's the thing this repo is trying to teach.

When I designed the lab I expected:

> `naive_extract`: **small but dirty** (kept the junk)
> `extracted`: **small and clean**

What actually measured:

> `naive_extract`: **big AND dirty** (268 chars, 35% more than the raw text)

What I missed: an extractor with no selection criteria **paraphrases and splits
line by line**, and both paraphrasing and splitting add characters. It isn't
extracting — it's restating the input in more words.

**This is more valuable than the conclusion I designed for:**

> Adding a model call in the middle **does not** imply the result is smaller or
> better. You have to state what that layer optimizes for, or it will just hand the
> input downstream in a different shape.

This shows up everywhere in agent engineering — adding a planner, a reranker, a
summarizer. If the objective isn't explicit, what you added is latency and tokens,
not quality.

**Building the predict → measure → admit-you-were-wrong habit matters more than
any single conclusion here.**

---

← [back to the chapter](../README.md) · [back to the index](../../../README.md)
