# Lab 2-9: Context compaction

**English** · [简体中文](README.zh-CN.md)

> **What you'll learn**
>
> 1. When context outgrows the window there are only three options: **do nothing / truncate / compact**
> 2. What each one costs — and you can **see it quantified** (prompt size per round)
> 3. Compaction quality depends almost entirely on **the compaction prompt**; the code is a dozen lines
>
> **How to work through it**: predict → run → watch whether the bar grows, stays flat, or drops.
>
> **Time**: 15 minutes for the core, about 45 for everything.
>
> Do [lab 1-1](../../ch1-agent-basics/1-1-context/) first — this is its direct sequel.

---

## The problem, stated clearly

Lab 1-1 showed you: **context is a string you assembled, and it grows every round.**

So: **what happens when it no longer fits?**

Every long-running agent hits this wall. There are only three options:

| Approach | How | Cost |
|---|---|---|
| **Do nothing** | resend the whole history each round | eventually overflows; slower and pricier as it grows |
| **Truncate** | keep the last N steps, discard the rest | cheap, but **what you dropped is gone** |
| **Compact** | have the model summarise older history | costs **one extra model call**, information survives |

This lab runs all three on the same task so you can see the difference.

> **Key design**: the example tasks are built so the **last step needs the first
> step's data**. That's what makes truncation's cost visible.

---

## Step 0: Run the baseline and watch it grow (5 min)

```bash
cd labs/ch2-context-engineering/2-9-context-compression
python3 agent.py full
```

Press Enter for examples, type `1` to pick the first.

> Output is Chinese by default. Set `LANG = "en"` at the top of `agent.py`.

### 👀 What to watch

**The bar.** Each round header shows the prompt size and a proportional bar:

```
  prompt 140 chars
  prompt 3834 chars  ████████████ +3694
  prompt 7548 chars  █████████████████████████ +3714
  ...
  prompt 11649 chars ██████████████████████████████████████ +312
```

### ✅ Note this number

| | Your baseline |
|---|---|
| Peak prompt size? | ___ |
| Total tool calls? | ___ |

### 💡 What you learned

140 → over 11,000. **More than 80×.** The answer is right, but **every round
you pay again for every earlier round.** Make the task longer and this line hits
the wall.

---

## Step 1: Predict, then run compaction (10 min)

### 🤔 Predict

`compact` hands the older steps to the model to summarise, then splices the
summary back into context. Guess:

- How far will the peak drop? ___
- Will the height figures survive the summary? ___
- How many extra model calls? ___

### 🔧 Do this

```bash
python3 agent.py compact "(paste the SAME task from step 0)"
```

### 👀 What to watch

**Two things.**

1. **Does the bar shrink back?**
   ```
   prompt 7546 chars  █████████████████████████ +3712
   ~ compacted: 7406 chars -> 1392 chars (81% saved)
   prompt 2412 chars  ████████ -5134        <- it dropped
   ```

2. **What the summary looks like** (printed in full). Specifically:
   - Did the figures survive?
   - Did it state what's still to do?

### 💡 What you learned

Open `agent.py` and find `compact_prompt`. **The entire secret is those four
requirements:**

```
1. Do not lose a single figure, name or unit - it needs those later
2. Write finished work as conclusions, not as a replay of the process
3. State explicitly what has NOT been done yet
4. Add nothing that wasn't in the original
```

The code is a dozen lines; **the prose does the work.** Same conclusion as lab 1-1.

---

## Step 2: Run truncation and see what it costs (10 min)

### 🤔 Predict

`truncate` keeps only the last step. Guess:

- Will its peak be the lowest of the three? ___
- For the dropped data — will it **look it up again**, or **recall it**? ___

### 🔧 Do this

```bash
python3 agent.py truncate "(same task)"
```

### 👀 What to watch

**Its `[thinking]` lines.** At some round it realises the data is gone — watch
what it says and does.

Also count the **total tool calls** and compare with `full`.

### 💡 What you learned

Context really is smallest. But **tool calls go up noticeably** — it has to
re-fetch what was dropped.

> **Truncation isn't free.** You save context per round and pay by redoing work
> you'd already finished.

Did it invent figures? No — because the system prompt says "**if the data isn't
in your context, look it up again rather than recalling it**". **Delete that
line and re-run** (exercise 3) to see the genuinely dangerous failure.

---

## Step 3: What over-compaction looks like (5 min)

```bash
python3 agent.py compact_tiny "(same task)"
```

The summary is limited to **one sentence**.

### 💡 What you learned

Compression ratio can exceed 90%, but **precision starts to go** (`599.1`
becomes `599`).

A few more figures and one sentence won't hold them — **at that point compaction
has degraded into truncation, and it's slower** (you paid for a model call for
nothing).

> **The compression ratio is a dial, not a "higher is better" setting.**

---

## Step 4: See them all at once

```bash
python3 agent.py all      # roughly 6-15 minutes
```

The table prints **peak prompt / tool calls / compactions / answer** per mode.

---

## Step 5: Change it yourself (exercises)

**Predict each before running.**

### Exercise 1 ⭐ Tune `KEEP_RECENT`

Top of the file, default 1. Set it to 5 and re-run `truncate`.

**Predict**: what happens to context size and tool calls?

> Note: `KEEP_RECENT = ∞` *is* `full`; `= 0` is the most aggressive truncation.
> **It's a continuous dial with no optimum.**

### Exercise 2 ⭐⭐⭐ Weaken the compaction prompt

Delete requirement 1 ("do not lose a single figure") from `compact_prompt` and
re-run `compact`.

**Predict**: does the summary read better or worse? Can the task still finish?

> **This is the most worthwhile exercise in the lab.**

### Exercise 3 ⭐⭐⭐ Delete "never guess a figure"

Remove `sys_no_guessing` from the system prompt and re-run `truncate`.

**Predict**: after the data is dropped, does it re-fetch or recall?

> Then think: if the number it recalled happens to be **correct**, how would you
> ever find out? **This is the most dangerous failure mode.**

### Exercise 4 ⭐ Do the arithmetic

How many more tool calls did `truncate` make than `full`? Multiply by your API
rate — that's truncation's real cost.

### Exercise 5 ⭐⭐ Double the task length

Ask for 10 buildings.

**Predict**: what shape does `full`'s curve take? What about `compact`'s?

---

## Check your answers

**[SOLUTION.md](SOLUTION.md)** — full measured output for all four modes
(**readable without running anything**), the actual summary the model produced,
and all exercise answers.

---

## Appendix

### The three-way trade-off

| | Context size | Extra cost | Information kept |
|---|---|---|---|
| `full` | grows forever, eventually overflows | none | all of it |
| `truncate` | smallest | **redoing finished work** | dropped is gone |
| `compact` | sawtooth, bounded | **one model call per compaction** | depends on the prompt |

**No free lunch — you only choose where to pay.**

### How real systems do it

Production agents (including Claude Code) are usually **hybrid**:

- Triggered by **token count** (e.g. 150k tokens), not step count
- Keep the last N turns **verbatim**, summarise everything older — exactly this lab's `compact`
- Some go **layered**: drop tool results, keep the model's reasoning

This lab's thresholds are deliberately tiny (`COMPACT_AFTER = 2`) — otherwise
the agent finishes in five steps and compaction never fires. **Equivalent to a
very small window.**

### Relation to lab 1-1

Lab 1-1's `no_history` mode *is* this lab's `truncate` at its most aggressive.
The difference:

- 1-1 breaks it **on purpose**, to see how it fails
- 2-1 solves it **seriously**, comparing what real approaches cost

---

## Stuck?

| What you see | What to do |
|---|---|
| `x No usable backend found` | Install any one of the three options it prints |
| `HTTP 429` | Wikipedia rate limit. The code backs off and retries; if you're running lots of experiments, pause a moment |
| Compaction never fired | Task too short. Lower `COMPACT_AFTER`, or use a task with more steps |
| Forgot the commands | Run `python3 agent.py` with no arguments |
