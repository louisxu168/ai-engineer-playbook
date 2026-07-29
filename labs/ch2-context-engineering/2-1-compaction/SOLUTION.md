# Lab 2-1 — Answers

**English** · [简体中文](SOLUTION.zh-CN.md)

> Read after you've run it and predicted wrong at least once.
> **You don't have to run anything** — everything below is real measured output.

Measured with `LAB_BACKEND=claude`. Task: *"Look up the height of these 5
buildings in order: Burj Khalifa, Shanghai Tower, Ping An Finance Centre,
Merdeka 118, The Clock Towers. Then tell me how much taller the first is than
the last."*

Correct answer: **829.8 − 601 = 228.8 m** (227 m if you use the 828 m roof
height — both defensible, depending on which figure you take).

---

## 1. All four modes in one table

| Mode | Peak prompt | Tool calls | Compactions | Answer |
|---|---|---|---|---|
| `full` | **11,649 chars** | fewer | 0 | ✅ 228.8 m |
| `truncate` | 3,677 chars | **29** ← the cost | 0 | ✅ but it re-fetched everything |
| `compact` | 7,546 → squeezed to 2,412 | fewer | 2 | ✅ 228.8 m |
| `compact_tiny` | 4,261 → 282 chars | fewer | 2 | ✅ 227 m |

**Reading it in one line**: `full` has the largest context; `truncate` has the
smallest context **but the most tool calls**; `compact` is extreme in neither.
That's the whole trade-off.

---

## 2. `full`: do nothing, watch it grow

```
  prompt 140 chars
  prompt 3834 chars  ████████████ +3694
  prompt 7548 chars  █████████████████████████ +3714
  prompt 8536 chars  ████████████████████████████ +988
  prompt 9750 chars  ████████████████████████████████ +811
  prompt 11337 chars █████████████████████████████████████ +1148
  prompt 11649 chars ██████████████████████████████████████ +312
```

140 → 11,649: **83×**. The answer is right, but every round you pay again for
every earlier round. Make the task longer and this line hits the window limit.
**That's why compaction exists.**

---

## 3. `compact`: the core of this lab

```
  prompt 7546 chars  █████████████████████████ +3712
  ~ compacted: 7406 chars -> 1392 chars (81% saved)
  prompt 2412 chars  ████████ -5134        <- it dropped
```

**The bar visibly shrinks.** That is the difference between compacting and
truncating, in one image.

What it actually produced (the model wrote this, quoted verbatim):

```
  +- the summary it produced -------------
  | TASK: look up the heights of 5 buildings (Burj Khalifa, Shanghai Tower,
  | Ping An Finance Centre, Merdeka 118, The Clock Towers).
  |
  | Confirmed height data:
  | - Burj Khalifa (Dubai): total 829.8 m; roof height 828 m
  | - Shanghai Tower (Lujiazui, Shanghai): 632 m, 128 storeys
  | - Ping An Finance Centre (Shenzhen): 599.1 m, 115 storeys
  | - Merdeka 118 (Kuala Lumpur): 678.9 m, 118 storeys
  | - The Clock Towers (Mecca): **the article body gives no height figure**
  |
  | Still to do:
  | 1. Get the exact height of The Clock Towers (the only missing height)
  | 2. Aggregate all five and produce the final result
  +--------------------------------------
```

**Three things to notice:**

1. **Every figure survived** — 829.8, 632, 599.1, 678.9, none lost
2. **It flagged what is still missing** — that's how the next round knows what to do
3. **The process was thrown away** — how many searches, which articles: gone.
   That is the point of compaction: **keep conclusions, drop the process.**

None of that is automatic. The four requirements in `compact_prompt` force it:

```
1. Do not lose a single figure, name or unit - it needs those later
2. Write finished work as conclusions, not as a replay of the process
3. State explicitly what has NOT been done yet
4. Add nothing that wasn\'t in the original
```

> **Compaction quality is almost entirely that prompt.** Delete requirement 1
> and re-run (exercise 2): the summary reads *better* while the figures vanish —
> and then the task collapses.

---

## 4. `truncate`: cheap context, expensive redo

Its peak really is the lowest (3,677 chars). But look at round 5:

```
  (3 steps discarded, 1 most recent kept)
  [thinking] The body gives no height figure, and **the first 3 steps' results
             are gone**, so I am **re-fetching** all four towers and the Clock
             Tower height at once rather than writing figures from memory.
  [tool 1/5] read({'title': 'Burj Khalifa'})     <- re-fetch
  [tool 2/5] read({'title': 'Shanghai Tower'})   <- re-fetch
  ...
```

**It re-fetched everything it had already looked up.** Final tool-call count:
**29**, well above `full` and `compact`.

> **Truncation isn't free.** You save context per round and pay by redoing
> finished work — which costs time and tokens too.

**Good news**: it did **not** invent figures; it honestly re-fetched. That's
because of one line in the system prompt:

```
Never guess a figure. If the data isn't in your context, look it up again
rather than recalling it.
```

Delete that (exercise 3) and you'll most likely see it report a figure from
memory instead — **the genuinely dangerous failure: it looks right, but the
number was never looked up.**

---

## 5. `compact_tiny`: over-compaction

Summary capped at one sentence; compression hits **93%** (4,261 → 282 chars):

```
  ~ compacted: 4261 chars -> 282 chars (93% saved)
  | Confirmed: Shanghai Tower 632 m, Ping An Finance Centre 599 m; Burj Khalifa,
  | Merdeka 118 and The Clock Towers have snippets only, no precise heights;
  | read calls for those returned HTTP 429, retry then finish the ranking.
```

**It got away with it this time**, because one sentence happened to hold the two
figures that existed. But note `599.1` became `599` — **precision is already
being lost.** Its final answer used 828 rather than 829.8, giving 227 m.

A few more figures and one sentence won't hold them — **at which point
compaction has degraded into truncation, only slower.**

> **The compression ratio is a dial, not a "higher is better" setting.**

---

## 6. ⚠️ A real problem we hit: HTTP 429

Notice this inside that `compact_tiny` summary:

```
read calls for those returned HTTP 429 Too Many Requests
```

That was me running a dozen experiments back to back and tripping Wikipedia's
rate limit.

The code now backs off and retries (2s / 4s / 6s), so normal use won't hit it.
But the incident is worth keeping:

> **Tools fail, in ways you didn't plan for.** And worse — if you don't retry
> and simply hand the 429 to the model as an error, it concludes "this article
> can't be found" and **makes a number up**.
>
> Tool-layer robustness directly determines whether your agent hallucinates.

---

## 7. Exercise answers

**1. Raise `KEEP_RECENT`** — more kept means less re-fetching and a bigger
context. It's a continuous dial: `KEEP_RECENT = ∞` is `full`, `= 0` is the most
aggressive truncation. **There is no optimum, only a trade-off.**

**2. Weaken the compaction prompt** — the summary gets more readable, more
human, and the figures start disappearing. Then the task breaks: the model finds
the data gone and either re-fetches (slower) or invents (wrong).
**This proves compaction quality ≈ compaction-prompt quality.**

**3. Delete "never guess a figure", run truncate** — it most likely stops
re-fetching and reports from memory. **The most dangerous failure mode**: the
answer looks right, it wasn't looked up, and you can't tell.

**4. Count the difference** — 29 tool calls vs noticeably fewer. Multiply by your
API rate; that's the real price of truncation.

**5. Double the task** — `full` keeps climbing; `compact` settles into a
sawtooth (grow-compact-grow-compact) around some level. **That sawtooth is what
a production agent actually looks like.**

---

## 8. In one line

| | Context size | Extra cost | Information kept |
|---|---|---|---|
| `full` | grows forever, eventually overflows | none | all of it |
| `truncate` | smallest | **redoing finished work** | dropped is gone |
| `compact` | sawtooth, bounded | **a model call per compaction** | depends on the prompt |

**No free lunch — you only choose where to pay.**

And the part most people miss: **compaction quality is decided almost entirely by
the compaction prompt.** The code is a dozen lines; four sentences of prose do
the work. Same conclusion as lab 1-1: **you steer an agent by editing text, not
by editing Python.**
