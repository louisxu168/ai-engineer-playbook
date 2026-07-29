# TA notes — Lab 2-9

Read the repo-root `AGENTS.md` first. This file is specific to this lab.

## What this lab actually teaches

Not "compaction is better than truncation". This:

> **All three options cost something. You only choose where to pay.**

And the one learners consistently miss:

> **Compaction quality is almost entirely the compaction PROMPT.** The code is a
> dozen lines. The four requirements inside `compact_prompt` do the work.

If they finish thinking "compact is the right answer", push back: ask what
compaction costs (an extra model call every time) and when truncation is the
better call (short tasks, cheap re-fetching, no cross-step dependencies).

## The visual is the point — make them watch it

The bar in each round header is the whole teaching device:

```
prompt 7546 chars  █████████████████████████ +3712
~ compacted: 7406 chars -> 1392 chars (81% saved)
prompt 2412 chars  ████████ -5134
```

If a learner is reading output without noticing the bar shrink, stop and point
at it. Nothing else in the lab lands as hard.

## Order matters

`full` first — they need the peak number as a baseline. Then `compact` (the
satisfying one), then `truncate` (the one with the hidden cost), then
`compact_tiny`. Running truncate before full leaves them with nothing to compare.

## The two exercises that matter

Exercises 2 and 3 are the lab. Push learners toward them:

- **Ex 2** (delete "don't lose a figure" from the compaction prompt) proves
  compaction quality ≈ prompt quality.
- **Ex 3** (delete "never guess" from the system prompt, run truncate) produces
  the genuinely dangerous failure: the agent recalls a figure instead of
  re-fetching. Ask the killer question: *"if the recalled number happened to be
  right, how would you ever know?"*

## Expected results and their variance

Measured once: `full` peaked at ~11,600 chars; `truncate` peaked at ~3,700 but
used **29 tool calls**; `compact` compacted twice, 81% and 49%. Numbers will
vary run to run — the *pattern* is what matters, not the digits.

If compaction never fires, the agent finished too fast. Lower `COMPACT_AFTER` or
pick a longer task. That's a config issue, fix it directly.

## Things you can just fix

- `HTTP 429` from Wikipedia (the code already backs off; just wait)
- Backend detection, dependencies, Python version
- Compaction not triggering (see above)

## Language

Chinese learners: `README.zh-CN.md` / `SOLUTION.zh-CN.md`, reply in Chinese.
For English program output: `LANG = "en"` at the top of `agent.py`.
