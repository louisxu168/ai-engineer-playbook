# Lab 5-1: How a coding agent edits code — three edit formats

**English** · [简体中文](README.zh-CN.md)

> **What you'll learn**
>
> 1. The core engineering decision in any coding agent: **what format the model
>    uses to say "change this"**
> 2. The three mainstream formats differ in cost by **2.1× to 7.8×** — and by how
>    much depends on what fraction of the file you're changing
> 3. `whole_file`'s cost barely moves with edit size; it tracks *file* size. The
>    other two are the opposite
> 4. "Diff formats are fragile and mismatch" **did not reproduce** here (two tasks,
>    three formats, zero failures)
>
> **How you'll learn it**: the verdict is a **real unittest run** — the hardest
> verdict in this repo, with no room for interpretation.
>
> **Time**: 25 minutes (no network).
>
> ⚠️ This lab **executes code** (it runs the tests). It runs a copy of
> `workspace/`, and the model cannot modify the test file. But **it is not a
> sandbox** — use a container for real work.

---

## The problem

You're building an agent that edits code. The model has read the file and wants to
change line 24.

**How does it tell your program that?**

This is not a detail — it's **the single design choice that most affects whether a
coding agent works**. Three mainstream answers:

```
whole_file      "here is the complete file after my change: <all 130 lines>"
search_replace  "replace `return ordered[middle]` with `<three new lines>`"
line_range      "lines 24 to 24 become `<three new lines>`"
```

All three work; real products each picked one. This lab has **the same model fix
the same bug**, changing only this, and measures three numbers:

| What | Why it matters |
|---|---|
| Do the tests pass | **Objective verdict** — unittest actually runs |
| How many chars the model emitted | The **cost** difference between formats |
| How many edits failed to apply | The **reliability** difference between formats |

---

## The material

`workspace/` holds two files you can open right now:

- **`stats.py`** — a 130-line statistics module with **one bug in it**
- **`test_stats.py`** — 20 unit tests, 3 of which catch that bug

⚠️ **The agent may not modify the test file.** The program blocks it in two places
(stated in the prompt, *and* checked in code).

> Why bother? Because "edit the test to expect the wrong answer" is the cheapest
> way to make tests pass, and AI writing code **really does do this**.
>
> Which is lab 4-1's conclusion again: **a constraint you can enforce at the
> interface shouldn't live only in the prompt.**

### Two tasks, different difficulty

```bash
python3 agent.py <mode>            # the fix task by default
python3 agent.py <mode> refactor   # the hard one
```

| Task | Sites to change | What's hard |
|---|---|---|
| `fix` | **1 site, 2 lines** | Not hard. The **best case** for all three formats |
| `refactor` | **8 sites** | 7 of them have **near-identical context**, differing only in a function name inside a string ★ |

Those 7 sites look like this — glance at it and guess which format struggles most:

```python
    if len(numbers) == 0:
        raise ValueError("mean() 需要至少一个数")      # <- 6 more just like it
```

---

## Step 0: find the bug yourself first (3 min)

```bash
cd labs/ch5-coding-agent/5-1-edit-formats
cd workspace && python3 -m unittest 2>&1 | tail -20 && cd ..
```

### 👀 What you'll see

3 failures, all pointing at `median`.

### 💡 What you learn

**Confirm the verdict works by hand before letting an agent near it.**

> This is basic hygiene for agent evaluation: **if you can't verify "correct" by
> hand, you can't score it automatically either.** This lab has the hardest
> verdict in the repo — "the tests pass" admits no second interpretation.

---

## Step 1: run the easy task, look at cost (6 min)

```bash
python3 agent.py all
```

### 🤔 Predict

What ratio of emitted characters between the three formats? ___ : ___ : ___

### 👀 What to watch

The **"model output"** column of the comparison table.

### 💡 What you learn

The gap is far larger than most people guess (numbers in SOLUTION).

The reason is simple but worth spelling out:

```
whole_file      cost ~ how big the FILE is      <- independent of how much you changed
search_replace  cost ~ how big the EDIT is      <- independent of file size
line_range      cost ~ how big the EDIT is (cheaper still - no original text repeated)
```

> **This isn't "saving a few tokens".**
> Changing 2 lines in a 2000-line file means `whole_file` emits 2000 lines. And an
> agent loop may go a dozen rounds.

---

## Step 2: run the hard task, watch how cost moves (6 min) ★

```bash
python3 agent.py all refactor
```

### 🤔 Predict (this is the key question)

The edit goes from 1 site to 8. **By what factor does each format's cost grow?**

- `whole_file` grows ___×
- `search_replace` grows ___×

### 👀 What to watch

Put the two `all` runs' "model output" numbers side by side.

### 💡 What you learn

**`whole_file` barely moved.** The other two roughly quadrupled.

Which nails the rule down:

> **`whole_file`'s cost is set by file size; `search_replace` / `line_range`'s cost
> is set by edit size.**

Corollary — **there is a crossover point**:

| Situation | Which wins |
|---|---|
| Big file + small edit (**the everyday case**) | Diff formats, by an order of magnitude |
| Small file + big rewrite (new files, rewrites) | `whole_file` — cheaper *and* safer |

**So real products keep both** and switch based on the situation.

---

## Step 3: find their failure modes (5 min)

**How each format can break** matters more than how many tokens it saves:

| Format | How it fails | Do you **know** it failed? |
|---|---|---|
| `whole_file` | Barely can — it *is* the final result | — |
| `search_replace` | One wrong space in `old` → not found; or `old` isn't unique | **Yes, it errors loudly** |
| `line_range` | Off-by-one on the line number | **☠ Not necessarily** |

**That last row is the point.** Open `agent.py` and look at `apply_line_range()`:

```python
lines[start - 1:end] = new.split("\n")
```

Off by one line and that statement still "succeeds" — it just edits the wrong
place. `whole_file` and `search_replace` fail loudly; **`line_range` corrupts
quietly.**

> `line_range` has a second hidden hazard: **when you make several edits at once,
> earlier edits shift every later line number.** See the "iterate backwards"
> comment in `apply_line_range()` — that's not an optimization, it's **mandatory**.

### ⚠️ But be honest: nothing failed in the measured runs

Two tasks × three formats: **zero failed edit applications.**

The widely repeated claim that diff formats mismatch **did not reproduce at this
scale.**

**That doesn't mean it isn't real** — it's likelier with bigger files, more edit
sites, weaker models, or genuinely duplicated code.

But at minimum: **don't treat it as a law you can apply without checking.**
Exercise 1 sends you looking for its boundary.

---

## Step 4: change it yourself (exercises)

### Exercise 1 ⭐⭐ Push it until something fails

I couldn't make any format fail. **Your turn.** Directions:

- Copy-paste `stats.py` up to 500 lines (lots of near-duplicate functions) → is
  `search_replace`'s `old` still unique?
- Remove the "the file is shown with line numbers" sentence from the
  `fmt_line_range` prompt → can it still count?
- Switch line numbering from 1-based to 0-based → does it drift?

**If you succeed, write it down** — that's a real finding.

### Exercise 2 ⭐ Let it cheat

Comment out the block in `check_path()` and re-run `refactor`.

**Predict**: will it modify the test file?

> Whatever happens, settle this question:
> **does your coding agent have any path to "edit the grader so I pass"?**
> In production that's reward hacking, and it's often unintentional.

### Exercise 3 ⭐⭐ Add a fourth format: unified diff

Have the model emit standard `diff -u` output and apply it with `patch` or your own
parser.

**Predict**: where does it land on cost and reliability relative to the other three?

> Hint: a unified diff contains **both** line numbers **and** the original context.
> Think about what that buys — it's trading redundancy for error detection.

### Exercise 4 ⭐⭐⭐ Let the model choose the format

Offer it two formats and let it decide per edit.

**Predict**: how will it choose? Will it switch to `whole_file` for big rewrites?

> This is what real products do. Then ask: **how would you verify it chose well?**

### Exercise 5 ⭐⭐⭐ Turn the tests from verdict into tool

Right now the program runs the tests and feeds the model the result. Instead, give
it a **`run_tests()` tool** and let it decide when to run them.

**Predict**: how often will it run them? After every single edit?

> That's another core coding-agent design question: **who triggers the feedback.**
> Look back at lab 1-2 — it's the same question wearing a different hat.

---

## Check your answers

After you've tried → **[SOLUTION.md](SOLUTION.md)**

Full measured data for both tasks × three formats, the cost-growth analysis, each
format's failure modes in detail, and answers to every exercise.

---

## Appendix: concepts

### Choosing a format

| | Cost scales with | On error | Good for |
|---|---|---|---|
| `whole_file` | **file size** | basically never errs | New files, small files, big rewrites |
| `search_replace` | **edit size** | errors loudly | **Everyday edits (default to this)** |
| `line_range` | **edit size** (cheapest) | **may corrupt silently** | Use with caution; always pair with review |

### One engineering principle

> **Make it impossible for errors to happen quietly.**
>
> `search_replace` beats `line_range` not because it's cheaper or more accurate,
> but because **when it's wrong, it always tells you.**

The same principle appeared in lab 4-1 (a vague error left the agent unable to tell
"rejected" from "half-executed"). **Observability isn't a luxury; it's a
precondition for correctness.**

### Why this lab's verdict is the hardest in the repo

| Lab | Verdict | Can it misjudge? |
|---|---|---|
| 3-1 Memory | keywords | Yes (measured) |
| 3-5 Retrieval | set membership | No |
| 4-1 Tools | compare against the one correct call | No |
| **5-1 Editing** | **a real unittest run** | **No — and it checks *behaviour*, not shape** |

> The earlier verdicts check "what the output looks like". This one checks "what
> the code does". **That's the only trustworthy way to evaluate a coding agent** —
> and why benchmarks like SWE-bench run tests.

---

## Stuck?

| What you see | What to do |
|---|---|
| `x No usable backend found` | Install any one of the three options on screen |
| Did it break my `workspace/`? | No — each run copies to `.run_*/`; the originals are read-only in practice |
| Want to see the edited code | Look in `.run_<mode>_<task>/stats.py` |
| My numbers differ from the docs | **Expected** — models are stochastic. Watch the trend, especially the cost column |
| Want the exact text the model received | Set `SHOW_PROMPT = True` |
| Forgot the commands | Run `python3 agent.py` with no arguments |
