# TA notes — Lab 02

Read the repo-root `AGENTS.md` first. This file covers what's specific here.

## What this lab is actually teaching

Not "hosted tools exist". This:

> **When you choose hosted, what you give up is observability.**

And a second, quieter one:

> **`run_diy()` is the same loop as lab 01.** An agent that searches the web
> needs no new machinery — only different tools.

If the learner walks away thinking "hosted is better because the answer was
nicer", the lab failed. Push them to the question: *when this breaks in
production at 3am, which one can you debug?*

## Order matters here

Make them run `hosted` **first**, then `diy`. In that order the contrast lands:
hosted is impressively good and completely opaque; diy is slower and totally
transparent. Reversed, the impact is much weaker.

After `hosted`, ask them directly: *"which search queries did it run?"* Let them
discover they can't answer.

## The three moments in the diy trace

The `diy` run usually surfaces all three. Make sure they notice each — ask, don't
tell:

1. **A search failed** (Chinese keywords against English Wikipedia return
   nothing) — *"what happened in round 1?"*
2. **It self-corrected** (retried in English) — *"how did it recover, and where
   did it learn that the first attempt failed?"* Leads to: errors go back into
   the context, which is why tools return `{"error": ...}` instead of raising.
3. **`search` wasn't enough, it had to `read`** — *"the Shanghai snippet had the
   number but the Dubai one didn't. Why does `read` exist?"* This is the
   agentic-search-vs-naive-RAG point and the single most valuable idea in the lab.

Traces vary between runs. If one of the three didn't show up, that's fine — do
not fake it. Work with what their run actually produced.

## The surprise: `no_search` usually gets it RIGHT

Expected failure is hallucination; what actually happens on the default question
is a correct answer from memory, in one round, with an honest "not verified
online" caveat.

**Do not treat this as a broken lab.** It's the lesson: *not every question
needs a tool.* Guide them to ask why — the fact is famous and hasn't changed in
a decade.

Then get them to break it themselves: have them run `no_search` on something
time-sensitive (recent news, an obscure statistic) and compare against `hosted`.
**That gap is what search tools are for.**

## Degraded modes

`diy_titles_only` and `diy_top1` change **only what `search` returns** — not one
line of `run_diy()`. Make them verify that claim by reading `execute_tool()`
themselves. The takeaway: **a tool's return shape matters more than the loop.**

## Things you can just fix

- `hosted` mode unavailable because the backend isn't Claude Code — explain and
  point them to the other four modes
- Wikipedia API timeouts / network issues
- Dependencies, Python version, backend detection

## Language

Chinese learners: `README.zh-CN.md` and `SOLUTION.zh-CN.md`; reply in Chinese.
For English program output, set `LANG = "en"` at the top of `agent.py` — that
switches the prompts too, so the model reasons and answers in English.
