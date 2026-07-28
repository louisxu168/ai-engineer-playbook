# Lab 02: Who runs the tool?

**English** · [简体中文](README.zh-CN.md)

> ## 🚀 Run it first (nothing to install)
>
> ```bash
> cd labs/ch1-agent-basics/1-2-who-runs-the-tool
> python3 agent.py hosted        # step 1: the provider does everything
> python3 agent.py diy           # step 2: now you do it, and compare
> ```
>
> **No `pip install`, no API key.** `hosted` uses Claude Code's built-in web
> search; `diy` uses the public Wikipedia API (standard library only).
>
> **Order matters: hosted first, then diy.** Reversed, the contrast falls flat.
>
> After `hosted` (about a minute) you get a polished answer with source links,
> followed by this:
>
> ```
>   Notice what you CANNOT see: which queries did it run? which pages did it
>   open? what did it read? did anything fail and get retried? -- none of it.
>   Just this final block of text.
> ```
>
> **That is the whole argument of this lab.** Now run `diy` and watch the
> opposite happen.
>
> Forgot the commands? Run `python3 agent.py` with no arguments.
>
> *(Output is Chinese by default — set `LANG = "en"` at the top of `agent.py`.)*

**The question:** when an agent uses a tool, who actually *runs* it — you, or
the provider?

---

## 1. Two legitimate paths

In lab 01 the tools were Python functions you wrote, and the loop was yours.
The model only ever **named** what it wanted.

But plenty of modern models ship with tools **built in**. Ask Claude Code a
question and it will search the web, read pages and answer — you wrote no loop
at all.

That's what "**the model IS the agent**" means: the harness lives at the provider.

| | Runs the loop | Runs the tool | Code you write |
|---|---|---|---|
| **hosted** | provider | provider | 0 lines |
| **DIY** | you | you | the whole loop |

Both are valid. They cost different things. This lab makes you **feel** that
cost by answering the same question five ways.

---

## 2. The five modes

| Mode | What it does |
|---|---|
| `hosted` | Send the question to Claude Code as-is, with its built-in WebSearch allowed. You do nothing |
| `diy` | You implement `search` / `read` / `calc` and run the loop. Every step visible |
| `no_search` | You run the loop but give it **no search tool** (baseline: memory only) |
| `diy_titles_only` | `search` returns titles but no snippets |
| `diy_top1` | `search` returns 1 hit instead of 3 |

The last two are **tool degradations**. They change only what `search`
*returns* — not one line of the loop — to prove a point: **what the tool
returns matters more than how the loop is written.**

---

## 3. Doing it

```bash
pip install -r requirements.txt
python3 agent.py                # usage
python3 agent.py hosted         # start here
python3 agent.py diy            # then this, and compare
```

`hosted` needs Claude Code (it uses its built-in WebSearch). The `diy` modes
use Wikipedia's public API — **no key, standard library only**.

### Step 1: run hosted, notice what you *can't* see

```bash
python3 agent.py hosted
```

It answers fast and well, with a pile of source links. Then ask yourself:

> Which queries did it run? Which pages did it open? What did it read? Did
> anything fail and get retried?

**You can't answer any of those.** All you got is the final block of text. The
program prints exactly this reminder at the end.

### Step 2: run diy, notice what you *can* see

```bash
python3 agent.py diy
```

Much slower. But every search, every snippet, every failure is right there.

An actual trace (abridged):

```
Round 1  [thinking] Search for the tallest buildings in Dubai and Shanghai...
         [tool] search({'query': '迪拜最高建筑 哈利法塔 高度'})
               -> {"error": "no results"}                     <- it failed!

Round 2  [thinking] Chinese keywords found nothing; switching to English names.
         [tool] search({'query': 'Burj Khalifa'})
               -> {"results": [{"title": "Burj Khalifa", "snippet": "...megatall
                  skyscraper in Dubai..."}]}                  <- self-corrected

Round 3  [thinking] Shanghai Tower's snippet gives 632 m, but Burj Khalifa's
                    snippet has no figure. Need to read the article.
         [tool] read({'title': 'Burj Khalifa'})
               -> {"extract": "...total height of 829.8 m..."} <- leads, not answers

Round 4  [tool] calc({'expression': '828 - 632'}) -> 196
```

**Three real teaching moments in four rounds**, none of which hosted mode would
have shown you:

1. **Round 1's search failed** — Chinese keywords against English Wikipedia,
   zero results
2. **Round 2 it self-corrected** — retried with English names. That's what real
   agent fault tolerance looks like
3. **Round 3 exposed the search/read split** — Shanghai Tower's snippet happened
   to contain 632 m; Burj Khalifa's had **no number**, so it had to read the
   article

Point 3 is the one this lab most wants you to notice:

> **`search` returns leads, not answers.**

That is exactly the line between "agentic search" and naive RAG. Naive RAG
stuffs the retrieval results into the prompt and calls it done. Agentic search
judges whether a lead is *enough*, and goes and reads more when it isn't.

### Step 3: predict, then run the degraded modes

```bash
python3 agent.py diy_titles_only   # search gives titles only
python3 agent.py diy_top1          # search gives 1 hit
python3 agent.py no_search         # no search at all
```

Predict first: **more rounds or fewer? is the answer still right?**

Hint: across all three, **not one line changes inside `run_diy()`**. The only
difference is what `search` returns from `execute_tool()`.

### Step 4: the comparison

```bash
python3 agent.py all      # roughly 4-10 minutes
```

---

## 4. Reading the code

`agent.py` is in five parts:

| Part | Content | Note |
|---|---|---|
| 1 | Tools: `search` / `read` / `calc` | note that search and read are **two** tools |
| 2 | System prompt | the `no_search` ablation lives here |
| 3 | Context assembly | same as lab 01; no context ablation this time |
| 4 | **The two runners** ★ | `run_hosted()` vs `run_diy()` — the contrast IS the lab |
| 5 | CLI entry point | skippable |

**Put the two functions in Part 4 side by side:**

- `run_hosted()` — a dozen lines, and **no loop**, because the loop isn't ours
- `run_diy()` — a full ReAct loop, the same one as lab 01

That second point is worth saying out loud: **an agent that searches the web
needs no new machinery.** It's the same loop with different tools. Everything
you learned in lab 01 transfers directly.

`llm.py` carries the same contrast:

```python
complete()          # forbid the provider's built-in tools -> the loop is yours
complete_hosted()   # allow WebSearch                      -> the job is theirs
```

The two functions differ by one argument: `--disallowedTools` becomes
`--allowedTools WebSearch`.

---

## 5. So which should you pick?

| | hosted | DIY |
|---|---|---|
| Development cost | near zero | write the loop, the tools, the prompts |
| Answer quality | usually better (real web search) | depends on your tools |
| **Observability** | **near zero** | **complete** |
| Can you debug a failure? | barely | down to the exact step |
| Can you swap the source? | no | yes (intranet, private corpus, …) |
| Can you control cost? | limited | yes (cap rounds, cache, degrade) |
| Does your data leave? | yes | your call |

**There's no single right answer.** Common real-world combinations:

- General Q&A, prototyping → hosted, it's fast
- Private data, audit logs, cost control → DIY
- Many products are **hybrid**: DIY main loop, hosted tools for some subtasks

The judgement this lab wants to build: **when you choose hosted, what you give
up is observability.** On the day it goes wrong, all you have is that final
block of text.

---

## 6. Exercises

1. **Ask something the model's memory cannot possibly know** — last week's news,
   an obscure figure. Then run `no_search` and watch. (See the surprise in
   SOLUTION.md.)
2. **Cap `read` at 100 characters** (`chars=100`) — is that still enough?
3. **Make `search` return stale data** — hardcode a wrong snippet and see
   whether it gets swallowed.
4. **Count the lines**: how long is `run_hosted()` vs `run_diy()`? What does
   that ratio tell you?
5. **Add a cache to diy mode** — same query twice returns the stored result.
   Think about what that saves in a real deployment.

---

Read [SOLUTION.md](SOLUTION.md) after you've tried it.
