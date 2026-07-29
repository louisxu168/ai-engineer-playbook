# Lab 10-1: One agent vs many — what do the extra agents actually buy?

**English** · [简体中文](README.zh-CN.md)

> **What you'll learn**
>
> 1. Measured: **the single agent wins outright** — 8/8 found, 0 false positives,
>    1 call. No multi-agent pattern beat it
> 2. Each pattern's **characteristic failure**: chunking loses context, specialists
>    over-report, critics over-delete
> 3. The question to ask before adding agents: **has the single agent saturated?**
> 4. A trap I fell into: **the "false positive" the models reported was my ground
>    truth being wrong**
>
> **How you'll learn it**: the verdict is mechanical — ground truth is 8 hard-coded
> ids, and recall and false positives are set arithmetic. Same class of verdict as
> lab 3-2, the most reliable kind in this repo.
>
> **Time**: 25 minutes.

---

## The conclusion first, because it may invert your expectation

"Multi-agent" is the most over-mythologised word of the last two years. This lab
breaks it into four concrete patterns and measures them on **the same task with the
same model**:

| Mode | Found | False positives | Calls |
|---|---|---|---|
| **single** (1 agent) | **8/8** | **0** | **1** |
| chunked (4, split by data) | 8/8 | 0 | 4 |
| specialists (4, split by concern) | 8/8 | **2** | 4 |
| critic (find + verify) | **7/8** | 0 | 2 |

**The single agent is no worse on any column, at 2–4× less cost.**

This doesn't mean multi-agent is useless. It means:

> **Multi-agent buys headroom — the part a single agent can't reach — and you have
> to confirm that headroom exists first.**

The value of this lab is teaching you **how to confirm it.**

---

## The task

Review 24 code snippets and find the insecure ones. **Exactly 8 are flawed:**

| Category | Obvious | Subtle |
|---|---|---|
| SQL injection | S01 string concatenation | S09 f-string interpolation |
| Hardcoded secret | S03 plaintext API key | S11 admin token as a default argument |
| Path traversal | S05 direct concatenation | S14 `normpath` with no prefix check |
| Unvalidated input | S07 bare `int()` | S15 table name from the request body |

**Each category has one obvious and one subtle instance** — anyone finds the
obvious ones, so **multi-agent's value can only show up in the 4 subtle ones.**

---

## Step 0: measure the ceiling (4 min)

```bash
cd labs/ch10-multi-agent/10-1-single-vs-multi
python3 agent.py single
```

### 🤔 Predict

One agent reading all 24 — how many does it find? How many of the 4 subtle ones?

### 👀 What you'll see

```
  ok found: S01, S03, S05, S07, S09, S11, S14, S15
  x  missed: -
  ok no false positives
  recall: 8/8    of which: obvious 4/4, subtle 4/4
  model calls: 1
```

### 💡 What you learn

**Full marks.** And that is the single most important step:

> **Before adding agents, measure whether one agent has already saturated.**
>
> If a single agent already scores 8/8, then no matter how many agents you add or
> how you arrange them, **recall tops out at 8/8** — every cent you spend buys
> nothing.

This step is nearly always skipped in real projects. People ship multi-agent, it
works well, and the architecture gets the credit — **without anyone checking
whether one agent could have done it.**

---

## Step 1: split by DATA — the intuitive kind of multi-agent (5 min)

```bash
python3 agent.py chunked
```

24 snippets split into 4, one agent per 6, results unioned.

### 🤔 Predict

Better than single?

### 💡 What you learn

**Same 8/8, at 4× the cost.**

And notice what it **structurally gave up**: each agent sees only a quarter of the code.

> Fine on this task, because each snippet is **independent**.
> But what if a problem needs **cross-snippet** reasoning — "the key defined in S03
> gets written to the log in S22"?
> **The cut you made through the data severed that discovery.**

That's chunking's characteristic failure: **it assumes problems are local.**

---

## Step 2: split by CONCERN — same cost, different cut (5 min) ★

```bash
python3 agent.py specialists
```

Still 4 agents, still 4 calls — but now each agent **reads all 24 snippets and
hunts one category.**

### 🤔 Predict (the question worth predicting here)

`chunked` and `specialists` cost **exactly the same**. Which does better?

### 👀 What to watch

**Watch the false-positive line.**

### 💡 What you learn

Possibly the opposite of what you expected (see SOLUTION).

The reason is worth chewing on: **tell an agent "you're only responsible for
finding X" and it will go find X.** Even if there is no X in this batch, it's
inclined to hand you something.

> **The specialist pattern's characteristic failure: over-reporting.**
> Give someone a hammer and everything looks like a nail — that applies to agents too.
>
> And the failure is **manufactured by your own prompt**: "this pass, find only path
> traversal" implicitly asserts that path traversal is present.

---

## Step 3: add a verifier (5 min) ★★

```bash
python3 agent.py critic
```

Run single, then have **another agent judge each finding** — real or false positive.

### 🤔 Predict

What can a verifier improve? What might it cost you?

### 👀 What to watch

**Read the verifier's decisions and reasons one by one.** Especially the one it
calls a false positive.

### 💡 What you learn

First, a structural fact:

> **A verifier can only remove, never add.**
> Anything stage one missed, stage two can **never** recover.
> So it buys **precision**, and cannot possibly buy recall.

Then look at the measured result — **it deleted the wrong thing.** And the part
worth reading is its stated reason: what it wrote **argues for keeping the
finding**, and then it labelled it a false positive.

> **Right reasoning, inverted conclusion.** SOLUTION has the verbatim text — it's
> the best moment in this lab.

---

## Step 4: full comparison (3 min)

```bash
python3 agent.py all
```

---

## Step 5: change it yourself (exercises)

### Exercise 1 ⭐⭐ Manufacture some headroom

The single agent already scores full marks, so multi-agent has nowhere to win.
**Make it harder:**

- Grow the corpus from 24 to ~100 snippets (copy the clean ones, rename variables)
- Or add a fifth, subtler category

**Predict**: at what size does `single` start missing things? **That point is where
multi-agent starts being worth anything.**

> That's the real lesson: **multi-agent's benefit has a precondition, and the
> precondition is measurable.**

### Exercise 2 ⭐⭐ Build a problem that needs cross-snippet reasoning

Add two snippets: one defines a hardcoded key, another writes it to the log.
**Individually mild; together an incident.**

**Predict**: with `chunked` splitting them across agents, can it still be found?

> That's chunking's **structural blind spot**, not bad luck.

### Exercise 3 ⭐⭐ Tell specialists that finding nothing is fine

Add to `sys_specialist`: "**If there are none of this category, return an empty
list — that is a perfectly normal result.**"

**Predict**: do the false positives drop?

> If they do, it proves something important: **over-reporting is manufactured by
> the prompt's implicit expectation, not a fixed model defect.**

### Exercise 4 ⭐⭐⭐ Let the verifier downgrade instead of delete

Change `run_critic`: replace keep/drop with high-confidence / low-confidence,
**keeping both**, differing only in ranking.

**Predict**: does recall still drop?

> This is what real systems do: **irreversible deletion goes to a human; the agent
> only ranks.** Think about why — look back at lab 4-1's idempotency key; it's the
> same idea.

### Exercise 5 ⭐⭐⭐ Combine all three

specialists → merge → critic.

**Predict**: what happens to recall and false positives? How many calls?

> When you're done, compare against the `single` row: **you spent 6× as much — what
> did you buy?** If the answer is "nothing", that's this lab's most important lesson.

---

## Check your answers

After you've tried → **[SOLUTION.md](SOLUTION.md)**

Full measured data, the verbatim text of the verifier's right-reasoning /
wrong-conclusion moment, and the complete story of **how I got the ground truth
wrong and the models caught it.**

---

## Appendix: concepts

### Each pattern's characteristic failure

| Pattern | What it assumes | Characteristic failure |
|---|---|---|
| Split by data (chunked) | Problems are **local** | Cross-snippet problems are **structurally** invisible |
| Split by concern (specialists) | Every category **is present** | **Over-reporting** (hammer, nail) |
| Verify (critic) | Stage one's **recall was sufficient** | **Over-deletion**, and it can only remove |

### Three questions before adding agents

1. **Has one agent saturated?** Adding without measuring is buying something that may not exist
2. **Which axis am I splitting on?** Data? Concern? Stage? — wrong axis = pure added cost
3. **Does each agent now see less?** If so, you're trading recall for parallelism

### One engineering principle

> **Multi-agent isn't "stronger", it's "cost traded for headroom".**
> **With no headroom, all you buy is cost.**

Same shape as lab 4-2 (tool retrieval) and 5-1 (edit formats): **measure how bad
your problem actually is before deciding whether new complexity — and its new
failure modes — is worth it.**

---

## Stuck?

| What you see | What to do |
|---|---|
| `x No usable backend found` | Install any one of the three options on screen |
| My `single` didn't score full marks | **Even better** — you have headroom, so multi-agent finally has a chance to win |
| My results differ from the docs | **Expected** — models are stochastic. Watch the **pattern**: who costs more, who over-reports, who deletes wrongly |
| I think a snippet is mislabelled | **Take that seriously** — SOLUTION section 5 is about the time I got one wrong |
| Want the exact text the model received | Set `SHOW_PROMPT = True` |
| Forgot the commands | Run `python3 agent.py` with no arguments |
