# Lab 2-6: Progressive disclosure with Agent Skills

**English** · [简体中文](README.zh-CN.md)

> **What you'll learn**
>
> 1. What **progressive disclosure** is: Skills come in three layers, only the first
>    permanently in context
> 2. Measured: on-demand loading **answers correctly on 55% of the context**
> 3. It's the **same shape** as labs 3-2 and 4-2's retrieval — with one key difference
> 4. That difference **repairs the retrieval failure measured in lab 4-2**
>
> **How you'll learn it**: mechanical verdict — does the answer contain the exact format
> string, and how many tokens did it cost?
>
> **Time**: 15 minutes.

---

## What progressive disclosure is

Agent Skills split each Skill into three layers:

```
layer 1  metadata   one line          <- **always** in context
layer 2  SKILL.md   core procedure    <- loaded when needed
layer 3  detail     fine parameters   <- loaded only when a detail is actually needed
```

The model sees "pptx — generate and edit PowerPoint decks" in the list, decides this
task needs it, and **then goes and loads** the documentation.

---

## The design

12 Skills. The task asks:

> "I need a 16:9 presentation. What exactly should `slide_size` be? Give the **exact
> string**."

**The correct answer `13.333x7.5@96` exists only in pptx's layer-3 detail doc.**
Not in layers 1 or 2 — verify it yourself:

```bash
python3 -c "
import skills
for n,meta,md,d in skills.SKILLS:
    if skills.CORRECT_FORMAT in meta: print('in metadata:', n)
    if skills.CORRECT_FORMAT in md:   print('in skill_md:', n)
    if skills.CORRECT_FORMAT in d:    print('in detail:', n)"
```

### Three modes

| Mode | What's in the context |
|---|---|
| `all_loaded` | **all three layers** of all 12 Skills, preloaded |
| `metadata_only` | the one-line list, **and no loading tool** |
| `progressive` | the one-line list + a `load_skill(name, level)` tool ★ |

---

## Step 0: run it (5 min)

```bash
cd labs/ch2-context-engineering/2-6-agent-skills
python3 agent.py all
```

### 🤔 Predict

- How will `metadata_only` answer?
- How many documents will `progressive` load before it can answer?

### 💡 What you learn

**`metadata_only` can't answer, and it says why honestly:**

> "I can only see pptx's one-line description, and there is no tool to load its detailed
> documentation. So I don't know whether slide_size takes "16:9", "widescreen",
> "13.333x7.5in" or something else — **any guess could make your call fail outright.**"

**That proves the information genuinely isn't in the context** — the model isn't
incapable, it simply can't see it.

And `progressive` goes **straight to `pptx / detail`** in one shot, skipping the md
layer and never touching the other 11 Skills.

---

## Step 1: compare it with retrieval (5 min) ★

This lab is the **same shape** as the previous two:

| Lab | Too many candidates | Who filters |
|---|---|---|
| 3-2 Retrieval | 36 memories | **BM25** (your code) |
| 4-2 Tools | 40 tools | **BM25** (your code) |
| **2-7 (this)** | 12 Skills | **the model itself** |

**The last column is the whole difference.**

### Why it matters

Recall [lab 4-2](../../ch4-tools/4-2-tool-selection/README.md)'s failure:

> BM25 ranked the correct tool **9th** with a cutoff of **8**. The model **never got to
> see it**, and could only say "no suitable tool exists".

**Progressive disclosure doesn't have that failure mode**, because the filtering is done
by the model — **it won't filter away something it knows it needs.**

> **The cost is one extra round trip.**
>
> BM25 is "you decide for it" — fast and cheap, but **it can decide wrong**.
> Progressive disclosure is "it decides for itself" — one more call, but **it won't miss
> what it knows it's looking for.**
>
> ⚠️ Note the qualifier: **"what it knows it's looking for."** If the model can't tell
> that this task needs pptx, no amount of listing helps — and the bottleneck moves back
> to how well that one metadata line is written.

---

## Step 2: change it yourself (exercises)

### Exercise 1 ⭐ Write the metadata badly

Change pptx's metadata from "generate and edit PowerPoint decks" to a vague
"document-related processing", then re-run `progressive`.

**Predict**: does it still find pptx?

> This is progressive disclosure's **real bottleneck**. Of the three layers, only layer 1
> is permanently in context — **and only it determines whether the model thinks to load
> anything at all.**
>
> Directly echoes [lab 4-1](../../ch4-tools/4-1-tool-design/README.md): **bad descriptions
> undermine everything downstream.**

### Exercise 2 ⭐⭐ More and bigger Skills

Copy the 12 Skills up to 100 and expand each detail doc to a few thousand words.

**Predict**: how far do `all_loaded` and `progressive` diverge?

> This lab is small (12 Skills, ~1900 chars total), so the gap is only about 1.8×.
> **Real Skill libraries run to dozens or hundreds, each thousands of tokens** — at which
> point `all_loaded` isn't an option at all.

### Exercise 3 ⭐⭐ A task needing two Skills

"Turn this Excel data into a 16:9 deck" needs xlsx **and** pptx.

**Predict**: how many does it load? Does it miss one?

> Multi-hop loading is where progressive disclosure breaks most easily — the same
> difficulty as [lab 3-2's exercise 5](../../ch3-memory/3-2-retrieval/README.md).

### Exercise 4 ⭐⭐⭐ Hybrid: coarse retrieval, then self-loading

Use BM25 to narrow 100 Skills' metadata to the top 30, then let the model load on demand
within those 30.

**Think it through**: is lab 4-2's "ranked 9th, cut at 8" risk back?

> It is — but on metadata rather than full documents. **And the cost is far lower**: a
> metadata line is one line, so you can afford a loose cutoff (top-30, not top-8).
>
> **That's what real systems do: coarse-filter at the cheap layer, and let the model
> decide at the expensive one.**

---

## Check your answers

After you've tried → **[SOLUTION.md](SOLUTION.md)**

---

## Appendix

### Three answers to "too many candidates"

| Approach | Who filters | Failure mode | Cost |
|---|---|---|---|
| Send everything | nobody | none (but may not fit) | tokens |
| Retrieval (3-2 / 4-2) | **your code** | **filters it away unseen** | recall risk |
| Progressive disclosure | **the model** | it doesn't think to load | **an extra round trip** |

### One engineering principle

> **If the model can make the filtering decision, don't make it for them — unless there
> are so many candidates that even the list doesn't fit.**
>
> When you filter wrongly, it can't know. When it filters, it at least knows what it's
> looking for.

---

## Stuck?

| What you see | What to do |
|---|---|
| `progressive` loaded several docs | **Fine** — it may read md before detail. Judge the final answer |
| `metadata_only` guessed correctly | Then this format is common in training data — **pick a more obscure fact** |
| Want to see the actual prompt | Set `SHOW_PROMPT = True` |
