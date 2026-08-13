# Lab 1-2: Tools — who runs them, and what they return

**English** · [简体中文](README.zh-CN.md)

> **This lab makes two independent arguments. Don't read them as one.**
>
> **Argument 1 (steps 0–1): who owns the while loop.**
> Modern models ship with tools built in, so you can build a web-searching agent
> **without writing a single loop**. What you pay is **observability** — when it
> breaks you can't even tell which step it broke at. Along the way you'll see that
> `search` returns **leads, not answers**, which is the line between agentic search
> and naive RAG.
>
> **Argument 2 (step 2): what the tool returns matters more than how the loop is
> written.** Without changing a line of the loop, degrade the tools (no search /
> titles only / one result) and the agent's capability collapses.
>
> Both arguments share the same code, which is why they're one lab — but they answer
> **two different questions**, and step 2 will remind you when the switch happens.
>
> **How to work through it**: answer one question five ways — the first two compare
> *who owns the harness* (argument 1), the last three compare *how good the tools are*
> (argument 2). **Order matters — hosted first, then diy.** Reversed, the contrast
> falls flat.
>
> **Time**: 15 minutes for the core, about 40 for everything.
>
> Do [lab 1-1](../1-1-context/) first if you haven't — this one reuses that loop.

---

## Step 0: Let the provider do the work (5 min)

### 🔧 Do this

```bash
cd labs/ch1-agent-basics/1-2-who-runs-the-tool
python3 agent.py hosted
```

It asks what you want researched. Press Enter for examples, e.g.:

```
Which is taller, the tallest building in Dubai or the tallest in Shanghai? By how many metres?
```

**No `pip install`, no API key.** Hosted mode uses Claude Code's built-in web search.

### 👀 You'll see

First this:

```
  All we did: send the question as-is, and allow its built-in WebSearch.
  No loop, no tool definitions, no context assembly -- all of that runs on
  the provider's side.
```

Then, about a minute later, a polished answer with source links, and:

```
  the provider took 4 internal turns (about the only thing it tells us)
```

### 🤔 Now ask yourself four questions

The answer quality is high. So:

1. **Which queries** did it run?
2. **Which pages** did it open?
3. **What did it read**?
4. Did anything **fail and get retried**?

### 💡 What you learned

**You can't answer any of the four.** All you have is that final block of text.

That's not a defect, it's a **trade**: observability for development cost. The
problem is how often people make that trade without noticing they made it.

---

## Step 1: Now run it yourself (8 min)

### 🤔 Predict first

Same question, but this time we implement the loop and the search tool. Guess:

- Faster or slower than hosted? ___
- Better or worse answer? ___
- How much of the process will you see? ___

### 🔧 Do this

```bash
python3 agent.py diy "(paste the SAME question)"
```

> ⚠️ **Identical question or it isn't a comparison.** The program prints a
> ready-made command after each run.

### 👀 What to watch

Much slower — but every search, snippet and failure is in front of you.
**Three things in particular:**

```
Round 1  [tool] search({'query': '迪拜最高建筑 哈利法塔 高度'})
               -> {"error": "no results"}                 <- (1) a search FAILED

Round 2  [thinking] Chinese keywords found nothing; switching to English.
         [tool] search({'query': 'Burj Khalifa'})  -> hit  <- (2) it self-corrected

Round 3  [thinking] Shanghai Tower's snippet gives 632 m, but Burj Khalifa's
                    has no figure. Need to read the article.
         [tool] read({'title': 'Burj Khalifa'})            <- (3) leads, not answers
```

(Your output won't match exactly — models are stochastic. But these three
phenomena usually show up.)

### 💡 What you learned

**(1) and (2)** are what real agent fault tolerance looks like: tool returns an
error → the error enters the context → the model sees it → it changes strategy.
That's why every tool in the code does `return {"error": ...}` rather than raising.

**(3) is the important one**: both searches hit, but Shanghai Tower's snippet
*happened* to contain 632 m while Burj Khalifa's contained **no number**, so it
had to call `read`.

> **`search` returns leads, not answers.**
>
> This is the line between agentic search and naive RAG. Naive RAG stuffs the
> top-k results into the prompt and stops. Agentic search judges whether a lead
> is *enough*, and goes to read the source when it isn't.

**Hosted mode would have told you none of this.**

---

## Step 2: Break the tool (10 min)

> ### ⚠️ The argument changes here
>
> Steps 0–1 asked **who** runs the loop — the provider, or you.
> From here on **you always run the loop**, and the question becomes a different one:
>
> **Same loop — how much does the quality of the tools you feed it matter?**
>
> The three modes below (`no_search` / `diy_titles_only` / `diy_top1`) have **nothing
> to do with who owns the harness**. They're all diy; the tools just get progressively
> worse.

Now prove something: **what the tool returns matters more than how the loop is written.**

### 🤔 Predict first

| Mode | What changed | Predicted round count | Predicted: still right? |
|---|---|---|---|
| `diy_titles_only` | `search` returns titles, no snippets | | |
| `diy_top1` | `search` returns 1 hit, not 3 | | |
| `no_search` | no search tool at all | | |

### 🔧 Do this

```bash
python3 agent.py diy_titles_only "(same question)"
python3 agent.py diy_top1 "(same question)"
python3 agent.py no_search "(same question)"
```

### 💡 What you learned

Open `execute_tool()` in `agent.py` — these three modes change **only what
`search` returns**. Not one line inside `run_diy()` differs.

> If `no_search` got it right, don't call it a bug yet. Ask: is this fact simply
> too famous? Check SOLUTION.md if you can't work it out.

---

## Step 3: Read the code, compare two functions (5 min)

### 🔧 Do this

Open Part 4 of `agent.py` and put these side by side:

- `run_hosted()`
- `run_diy()`

### 👀 What to notice

Count the lines in each. Then notice: **`run_hosted()` has no loop.**

Because the loop isn't ours to run.

The same contrast is in `llm.py`, where the two functions differ by one argument:

```python
complete()          # --disallowedTools        -> the loop is yours
complete_hosted()   # --allowedTools WebSearch -> the job is theirs
```

### 💡 What you learned

Two things:

1. **The code you skip writing is the control you give up.**
2. `run_diy()` and lab 1-1's `run()` **are the same loop**. An agent that
   searches the web needs no new machinery — only different tools.

---

## Step 4: So which do you pick?

| | hosted | DIY |
|---|---|---|
| Development cost | near zero | write the loop, the tools, the prompts |
| Answer quality | usually better (real web search) | depends on your tools |
| **Observability** | **near zero** | **complete** |
| Can you debug a failure? | barely | down to the exact step |
| Can you swap the source? | no | yes (intranet, private corpus, …) |
| Can you control cost? | limited | yes (cap rounds, cache, degrade) |
| Does your data leave? | yes | your call |

**No single right answer.** Common combinations:

- General Q&A, prototyping → hosted, it's fast
- Private data, audit logs, cost control → DIY
- Many products are **hybrid**: DIY main loop, hosted tools for some subtasks

**The judgement this lab is for**: when you choose hosted, what you give up is
observability. On the day it goes wrong, all you have is that final block of text.

---

## Step 5: Change it yourself (exercises)

**Predict each outcome before running.**

### Exercise 1 ⭐ Ask something memory can't cover

```bash
python3 agent.py no_search "Which AI models were released last week?"
python3 agent.py hosted "Which AI models were released last week?"
```

**Predict**: how big is the gap?

> This answers "what problem does a search tool actually solve".

### Exercise 2 ⭐⭐ Cut `read` down to 100 characters

Change `chars=700` to `chars=100` in `read()`.

**Predict**: still enough? How does it cope?

### Exercise 3 ⭐⭐ Make `search` return stale data

Hardcode a wrong snippet (say, a height of 1000 m).

**Predict**: will it spot the contradiction, or swallow it?

### Exercise 4 ⭐ Count the lines

How long is `run_hosted()`? How long is `run_diy()`?

**What does that ratio tell you?**

### Exercise 5 ⭐⭐⭐ Add a cache to diy

Same query twice returns the stored result.

**Then think**: how much would that save in a real deployment? And — **could you
add a cache to hosted mode at all?**

---

## Check your answers

Only after doing the above → **[SOLUTION.md](SOLUTION.md)**

---

## Appendix: concept reference

### What the three tools are for

| Tool | Returns | Why it exists |
|---|---|---|
| `search(query)` | titles + snippets (**leads**) | find where the answer might be |
| `read(title)` | article intro (**content**) | snippets often lack the exact figure |
| `calc(expression)` | arithmetic result | models are unreliable at mental math |

**Give it `search` without `read`** and it can only assemble an answer from
whatever the snippets happened to contain.

### Three approaches, in ascending order

| Approach | What guarantees the dependency | Cost |
|---|---|---|
| Sequential (one tool per round) | the loop structure | more round trips, slow |
| **Parallel (what this lab does)** | **model judgement + literal-only arguments** | wrong judgement → wrong result |
| Model writes code that calls tools | variable references, language-level | needs a sandbox |

The third is Programmatic Tool Calling — the model writes real code, so
dependencies are variables:

```python
p = search_products("keyboard")
r = get_rate("USD", "CNY")
total = p["usd"] * 3 * r["rate"]      # a real dependency
```

**We sit in the middle tier — that's the mainstream approach, not a simplification.**

---

## Stuck?

| What you see | What to do |
|---|---|
| `x hosted mode did not finish` | Run it again — that failure is non-deterministic |
| Hosted mode says it needs Claude Code | Use the `diy` modes; they don't depend on it |
| Nothing happens for tens of seconds | **Normal** — live web search is slow |
| Forgot the commands | Run `python3 agent.py` with no arguments |
