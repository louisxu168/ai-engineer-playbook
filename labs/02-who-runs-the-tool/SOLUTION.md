# Lab 02 — Answers

**English** · [简体中文](SOLUTION.zh-CN.md)

> Read after you've run it and predicted wrong at least once.

Measured with `LAB_BACKEND=claude`. Default question: **"Which is taller, the
tallest building in Dubai or the tallest in Shanghai? By how many metres?"**

Correct answer: Burj Khalifa 828 m (roof) / 829.8 m (with spire), Shanghai
Tower 632 m, difference **196 m**.

---

## Measured results

| Mode | Rounds | Tool calls | What you can see | Answer |
|---|---|---|---|---|
| `hosted` | some number, internally | invisible | **final text only** | ✅ 196 m, 6 sources |
| `diy` | 5 | 7 | **every step** | ✅ 196 m (and flagged the 829.8 discrepancy) |
| `no_search` | 1 | 0 | 1 step | ✅ **196 m — it was right**, see below |

---

## Mode by mode

### `hosted` — fast, good, and you are blind

The answer quality is high: 828 vs 632, difference 196 m, plus an unprompted
note about CTBUH's 829.8 m figure, plus six sources (Guinness, Wikipedia,
Britannica, a Shanghai government site…).

**And you saw none of the process.** We sent one sentence; everything else ran
at the provider. The program prints this reminder at the end:

> Notice what you CANNOT see: which queries did it run? which pages did it
> open? what did it read? did anything fail and get retried? — none of it.
> Just this final block of text.

**That's not a defect, it's a trade.** You exchange observability for
development cost. The problem is that people often make the trade without
noticing they made it.

### `diy` — slow, but every step is there

5 rounds, 7 tool calls. Much slower, but the trace contained three things
hosted mode would never have told you:

**1. Round 1's search failed outright**

```
[tool] search({'query': '迪拜最高建筑 哈利法塔 高度'})
      -> {"error": "no results"}
```

Chinese keywords against English Wikipedia: nothing. **In hosted mode you would
never know this happened.**

**2. Round 2 it corrected itself**

```
[thinking] Chinese keywords found nothing; switching to English names.
[tool] search({'query': 'Burj Khalifa'})   -> hit
```

That's what real agent fault tolerance looks like: tool returns an error → the
error enters the context → the model sees it → it changes strategy. It's also
why tools should `return {"error": ...}` rather than raise.

**3. Round 3 exposed the search/read split** (the most important point here)

```
[thinking] Shanghai Tower's snippet gives 632 m, but Burj Khalifa's snippet
           has no figure. Need to read the article.
[tool] read({'title': 'Burj Khalifa'})
      -> {"extract": "...total height of 829.8 m..."}
```

Both searches hit. Shanghai Tower's snippet *happened* to contain 632 m; Burj
Khalifa's contained **no number at all**. So it had to call `read`.

> **`search` returns leads, not answers.**

This is the line between agentic search and naive RAG. Naive RAG stuffs the
top-k results into the prompt and stops. Agentic search judges whether a lead is
*enough* and goes to read the source when it isn't. **Give it `search` without
`read` and it can only assemble an answer from whatever the snippets happened
to contain.**

**4. Round 4 it also caught the ambiguity**

```
[tool 1/2] calc({'expression': '828 - 632'})   -> 196
[tool 2/2] calc({'expression': '829.8 - 632'}) -> 197.8
```

828 (roof) or 829.8 (with spire)? It computed both and explained the difference
in the answer. Good behaviour, worth noticing.

### `no_search` — it got it right. That's a surprise.

Expected: "no search tool, so it hallucinates or refuses." Measured: **1 round,
0 tool calls, completely correct answer.**

```
[thinking] No internet tools; from memory: Burj Khalifa 828 m, Shanghai Tower
           632 m, so the former is 196 m taller.
[answer] ...Burj Khalifa is taller by about 196 m (828 - 632 = 196 m).
         Note: structural height including spire, given from memory, not verified online.
```

**Why? Because this fact is famous and stable.** "Burj Khalifa is 828 m"
appears countless times in training data, and it hasn't changed in over a
decade. For a question like this, search only adds cost and latency.

Also note it **flagged its own uncertainty** ("given from memory, not verified
online"). That's good behaviour.

**The surprise itself is the lesson:**

> **Not every question needs a tool.** Stable public facts are already in the
> model. What genuinely needs tools is **time-sensitive data, private data, and
> detail too fine-grained for the model to have memorised.**

To watch it actually fail, ask `no_search` something memory cannot cover:

```bash
python3 agent.py no_search "Which AI models were released last week?"
python3 agent.py no_search "What was the 2024 population of some obscure county?"
```

Then run `hosted` on the same question. **That gap is what a search tool is
actually for.**

---

## Exercise answers

**1. Ask a time-sensitive question** — see above. `no_search` starts inventing,
or admits it doesn't know; `hosted` gets it right. **That is the reason search
tools exist.**

**2. Cap `read` at 100 characters** — often not enough. Wikipedia intros
usually open with definition and history; the actual figure may be in the second
or third sentence. Truncate too hard and it can't get it, so it re-reads or
gives up. Lesson: **a tool's return length is a real design parameter**, not an
arbitrary number.

**3. Make `search` return stale data** — in the vast majority of runs it is
**swallowed whole**. Same conclusion as lab 01's "make `get_rate` return 999":
**the model trusts tool output by default.** Data trustworthiness is your job,
inside the tool.

**4. Line counts** — `run_hosted()` is about a dozen lines with **no loop**;
`run_diy()` is a full ReAct loop. That ratio is the whole subject of this lab:
**the code you skip writing is the control you give up.**

**5. Add a cache** — same query hits the cache and returns immediately. This
saves a lot in a real deployment: agents often search near-identical things in
adjacent rounds. You'll also notice that **being able to add a cache at all is a
DIY advantage** — there's nowhere to insert one in hosted mode.

---

## In one line

| | Code you wrote | What you can see |
|---|---|---|
| hosted | 0 lines | the final answer |
| DIY | the whole loop | every search, every snippet, every failure |

**Choosing hosted means giving up observability.** On the day it breaks, all you
have is that final block of text.

One more thing: `run_diy()` and lab 01's `run()` **are the same loop**. An agent
that searches the web needs no new machinery — only different tools.
