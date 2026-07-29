# TA notes — Lab 3-1

Read the repo-root `AGENTS.md` first. This file is specific to this lab.

## What this lab actually teaches

Not "agents can have memory". This:

> **A memory system's quality is decided by what it refuses to remember** — and
> the refusal criteria live entirely in one extraction prompt.

Plus the finding that only shows up when you measure:

> **Extraction ≠ shrinking.** Measured: `naive_extract` produced memory 35%
> *larger* than storing the raw transcript (268 vs 199 chars), and just as dirty.
> A middle layer with no stated objective adds cost, not quality.

## The step people skip, and shouldn't

`diff memory_naive_extract.json memory_extracted.json`.

Learners will read the summary table and move on. Push them to open both files.
The table says "0 junk vs 5 junk"; the files show *which* items and *why*, and
that's where the lesson lives. Specifically make them find the theme-park pair:
one mode kept both the event and the preference, the other kept only the
preference. That single contrast explains what "extraction" means.

## Do not pre-explain the stale-fact result

The "stale facts" row shows ✗ for **all three** memory modes. Learners often
assume they broke something. They didn't — it's the designed finding.

Ask: *"during extraction, does the model see what's already stored?"* and send
them to this line in `update_memory()`:

```python
raw_text = complete(t("extract_input") + session_text, extract_prompt, ...)
```

They should reach "it's an architecture problem, not a prompt problem" themselves.
That realization is the entire setup for exercise 3.

## Exercise 3 is the one that matters

Read-modify-write instead of append. If they only do one exercise, this one.
Two structural changes: existing memory enters the prompt, and `save_memory`
replaces `memories.extend`.

When it works, ask the follow-up: **"what can this design now get wrong that
`full_log` never could?"** (Answer: wrongly deleting a correct memory.) That
trade-off — dirty-but-safe vs clean-but-fallible — is the real content.

## Be honest about the scoring

The `no_memory` run scores 1/2 and **that's a false positive** — the model said
"mix spicy and non-spicy 2:1" while *asking* whether the user eats spice, and the
keyword matched. If a learner notices, congratulate them; if they don't, point it
out. Keyword judges are the weakest verdict in this repo and they should know it.

Do not let them conclude `no_memory` "half worked".

## Expected results and variance

Measured 2026-07-28 on Claude Code: sizes 0 / 199 / 268 / 195; junk 0 / 5 / 5 / 0;
stale fact present in all three memory modes.

**Extraction is model-generated, so numbers vary run to run.** The reproducible
parts are the *ordering* (`extracted` cleanest) and the stale-fact failure
(structural — it cannot pass as written). If a learner's `naive_extract` comes out
smaller than `full_log`, the analysis still holds: ask them to count items and
look at the per-item boilerplate.

## Language

Chinese learners: `README.zh-CN.md` / `SOLUTION.zh-CN.md`, reply in Chinese.
For English program output: `LANG = "en"` at the top of `agent.py`.
