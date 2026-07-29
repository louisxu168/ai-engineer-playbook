# Lab 3-1: User memory — remembering a person across sessions

**English** · [简体中文](README.zh-CN.md)

> **What you'll learn**
>
> 1. A memory system does exactly two things: **write** (what to keep) and
>    **read** (paste it into the context) — all four modes differ 100% in the write
> 2. Why "just keep everything" fails: size grows linearly with sessions, and the
>    junk and the stale facts come along for the ride
> 3. **The extraction prompt determines memory quality** — measured, the careless
>    extractor produced memory *larger than not extracting at all*
> 4. The problem no prompt can fix: **what happens when a fact changes** (the real
>    hard part of memory systems)
>
> **How you'll learn it**: the program writes each mode's memory to its own JSON
> file you can open and diff. It also measures size, how many key facts survived,
> how much junk leaked in, and whether a superseded fact is still in there.
>
> **Time**: 20 minutes (no network).

---

## The problem

Everything in chapter 2 was about the context **inside one session**. Real
products aren't one session:

```
Monday  user: I'm allergic to peanuts, it sends me to the ER.
        ...session ends, context cleared...

Friday  user: recommend me some restaurants
        agent: Sure! How about kung pao chicken...
```

> **Context is per-session. People are not.**

The instinct is "store the whole transcript and paste it back next time". That
works — until you hit chapter 2's wall: **after 200 sessions, does it still fit?**

So the real question isn't how to store it. It's: **what do you select, before
storing?**

---

## The script this lab runs

Six sessions are hard-coded (so all four modes face identical input — otherwise
the comparison means nothing):

| # | What the user says | What it is |
|---|---|---|
| 1 | I'm allergic to peanuts… I don't eat spicy at all | ✅ **keep long-term** |
| 2 | I work in **Beijing**, Guomao, backend developer | ⚠️ lastingly true — but wait |
| 3 | Rained today, forgot my umbrella, got a cold, early night | ❌ **expires same day** |
| 4 | Went to Universal Studios, queued forever, can't stand crowds | 🤔 event is useless, but a preference hides inside |
| 5 | Update: transferring, based in **Shanghai** Pudong from now on | 💣 **row 2 is now void** |
| 6 | Three-day work trip to Chengdu next week, near Chunxi Road | ⏳ true, but **will expire** |

Then in session 7, you ask something (e.g. "put together a restaurant list for my
Chengdu trip").

**Those six lines cover every hard part of a memory system** — especially row 5.
Memory has to do more than *add*; it has to *revise*.

---

## Step 0: feel what no memory is like (3 min)

```bash
cd labs/ch3-memory/3-1-user-memory
python3 agent.py no_memory
```

Press Enter for examples, then type `1`.

### 👀 What you'll see

The model **can't answer**. It asks you four questions back, one of which is:

```
3. **Do you eat spicy food?** Back-to-back hotpot on a work trip is
   a real question for your stomach.
```

### 💡 What you learn

**The user already said "I don't eat spicy at all" — in session 1.**

That's the cost of no memory: not a wrong answer, but **making the user
re-introduce themselves**. Every "this AI doesn't know me at all" experience
reduces to exactly this.

> Also notice: the program scores it "✓ honoured: no spicy food". **That's a false
> positive** — the model just happened to say "mix spicy and non-spicy 2:1" and the
> keyword matched. Automatic scoring has limits; SOLUTION digs into this.

---

## Step 1: store the whole transcript (4 min)

```bash
python3 agent.py full_log "(paste the same question)"
```

### 🤔 Predict

- How many key facts survive? ___
- How much junk ends up in the memory? ___

### 👀 What to watch

These four lines:

```
  memory size: ___ chars  ██████
  key facts: ___/2 remembered
  junk: ___ item(s) leaked in
  stale facts: ___
```

### 💡 What you learn

It does remember everything — **and keeps all the garbage too**.

And look carefully: `full_log`'s size is the sum of all session lengths.
**6 sessions is 199 characters; 600 sessions is 20,000.** That line is straight
and it does not bend.

> Open `memory_full_log.json`. That file *is* the agent's memory.

---

## Step 2: let the model extract (6 min) ★ the core

Different approach: **when a session ends, have the model pick out what's worth
keeping.**

Run it twice. The only difference is one extraction prompt:

```bash
python3 agent.py naive_extract "(the same question)"
python3 agent.py extracted     "(the same question)"
```

### 🤔 Predict (almost everyone gets this wrong)

`naive_extract`'s prompt is one sentence: "extract memory items from this
conversation".

- Will its memory be **bigger** or **smaller** than `full_log`? ___

### 🔧 Then do this (the most important step in the lab)

```bash
# macOS / Linux
diff memory_naive_extract.json memory_extracted.json
```

Or just open both files side by side in your editor.

### 👀 What to watch

Compare them item by item. Especially:

1. Session 3's rain / cold / early-night — **is it in both files?**
2. Session 4's theme park — what did each side extract from it?
3. Session 6's "next week" trip — how differently is it written?

### 💡 What you learn

Open `agent.py` and look at `update_memory()`. `naive_extract` and `extracted`
go through **the same function and the same model call**. The only fork is:

```python
if mode == "naive_extract":
    extract_prompt = t("extract_naive")
else:
    extract_prompt = t("extract_good")
```

`extract_good` spells out five criteria, and the load-bearing one is #2:
**explicitly say what to throw away**.

> Same law as lab 2-1:
> **compaction quality ≈ compaction-prompt quality; memory quality ≈
> extraction-prompt quality.**
>
> Any criterion you leave unstated, the model picks one for you.

---

## Step 3: full comparison, and the line you might skip (5 min)

```bash
python3 agent.py all "(the same question)"
```

The table has a row called **"stale facts"**.

In session 5 the user said they're transferring to Shanghai and no longer going
in to Beijing. So "works in Beijing, Guomao" **is void**.

### 🤔 Predict

Of the four modes, how many cleared the Beijing entry?

### 💡 What you learn

The answer is in SOLUTION, but ask yourself a better question first:

> **During extraction, can the model see the memories that are already stored?**

Go find out in `update_memory()`. This line is the whole answer:

```python
raw_text = complete(t("extract_input") + session_text, extract_prompt, ...)
```

What gets sent is **only this one session's text**. It has no idea what was
stored two months ago.

**So this isn't a prompt problem, it's an architecture problem.** Exercise 3 has
you fix it.

---

## Step 4: change it yourself (exercises)

### Exercise 1 ⭐ Add a session to the script

Add a line to `TEXT["en"]["sessions"]`, e.g. "I'm cutting weight lately, no carbs
at dinner".

**Predict**: how will each of the four modes handle it? Run and check.

### Exercise 2 ⭐⭐ Break `extract_good` on purpose

Delete criterion #2 ("explicitly drop present state") and re-run `extracted`.

**Predict**: junk goes from 0 to how many?

> This tells you which of those five lines is actually doing the work.

### Exercise 3 ⭐⭐⭐ Make memory revisable, not just appendable

Change `update_memory()` so that before extracting, it **also sends the existing
memory**, and asks the model for the *updated complete list* rather than a list of
additions.

Roughly:

```
Here is what you already remember: {existing memory}
Here is the newest session: {this session}
Output the **updated complete memory list**. If the new session contradicts an
old memory, delete the old one.
```

**Predict**: does the Beijing entry disappear? Run it.

> This is what mem0, Memobase and friends actually do: not append, but
> **add / update / delete**.

### Exercise 4 ⭐⭐⭐ What happens when memory gets big

Suppose memory grows to 500 items. Can you still paste it all in?

**Think it through**: at that point do you need compaction (chapter 2), or
**retrieval** (the next lab)?

> The dividing line: **can you know in advance which few items this turn needs?**

### Exercise 5 ⭐⭐ Give memories an expiry

Session 6's Chengdu trip should become void once the trip is over.

Add an `expires` field to memory items and filter on read.

**Think it through**: who decides it's expired — the write path, or the read path?

---

## Check your answers

After you've tried → **[SOLUTION.md](SOLUTION.md)**

All four memory files in full, the measured comparison, **one genuinely
surprising result**, and answers to every exercise.

---

## Appendix: concepts

### A memory system has two verbs

```
write: session ends -> decide what to keep -> store to file/DB
read:  session starts -> fetch -> paste into context
```

This lab uses the simplest possible read: **fetch everything**. Once memory grows
past what fits, the read becomes a retrieval problem — that's the next lab.

### The four strategies

| Strategy | Size vs sessions | Junk | Can revise? | When |
|---|---|---|---|---|
| Nothing | 0 | none | — | One-shot tools, no personalization |
| Full log | **linear growth** | all of it | ✗ | Few sessions, zero information loss required |
| Careless extraction | grows (possibly faster than the log) | all of it | ✗ | Don't |
| Good extraction | grows slowly | little | ✗ | **Default to this** |
| Extract + revise (ex. 3) | plateaus | little | ✓ | Real products |

### One engineering principle

> **A memory system's quality is decided by what it refuses to remember.**
>
> A system that keeps everything and a system that keeps nothing perform
> identically at "surfacing the useful bit".

---

## Stuck?

| What you see | What to do |
|---|---|
| `x No usable backend found` | Install any one of the three options on screen |
| My numbers differ from the docs | **Expected** — extraction is done by a model, so it varies. Watch the trend, not the digits |
| `memory_*.json` keeps growing across runs | It doesn't — the program deletes the old file before each run |
| Want the exact text the model received | Set `SHOW_PROMPT = True` |
| Forgot the commands | Run `python3 agent.py` with no arguments |
