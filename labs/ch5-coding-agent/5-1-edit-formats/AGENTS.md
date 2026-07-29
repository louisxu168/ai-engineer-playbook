# TA notes — Lab 5-1

Read the repo-root `AGENTS.md` first. This file is specific to this lab.

## What this lab actually teaches

Not "coding agents edit files". This:

> **The edit format is the highest-leverage design choice in a coding agent, and
> its cost behaviour is arithmetic, not opinion:**
> `whole_file` cost ~ O(file size); `search_replace`/`line_range` cost ~ O(edit size).
>
> Measured: the edit grew 8× and `whole_file`'s output grew **1.07×** while the
> diff formats grew 3.9× and 4.5×.

And the safety principle underneath:

> **Make it impossible for errors to happen quietly.** `search_replace` beats
> `line_range` not on cost or accuracy but because it fails loudly.

## This lab has the repo's hardest verdict — use that

`unittest` actually runs. Point out to learners that every earlier lab's verdict
checks *what the output looks like*; this one checks *what the code does*. That's
why SWE-bench-style benchmarks run tests, and it's the only trustworthy way to
evaluate a coding agent.

Have them run `cd workspace && python3 -m unittest` by hand **before** any agent
run. If they can't verify "correct" manually, they can't score it automatically.

## Make them run BOTH tasks — one task teaches nothing

The whole point is the *pair*. With only `fix`, they'll conclude "diff formats are
7.8× cheaper, done". Running `refactor` too shows the ratio collapse to 2.1× and
exposes the actual rule (cost scales with different things). Have them predict the
growth factors before running.

## Be upfront that the reliability difference did not reproduce

Zero failed edit applications across 6 runs. `refactor` was built specifically to
force `search_replace`'s ambiguity failure (7 sites with near-identical context)
and the model defeated it by including the function name in `old`.

Do not let a learner conclude "so line_range is fine". The correct framing:
**cost conclusions are arithmetic and stable; reliability conclusions measure
instruction-following and move with model strength.** Exercise 1's most promising
direction is trying a weaker model.

## The best detail to point at

In `refactor` there are 9 `raise ValueError(` and only 7 should change — the other
two are argument-range checks, not empty-data checks. All three formats changed
exactly the right 7. Ask: *"what would a regex have done?"*

That's the real argument for model-driven edits over scripted ones, and it also
explains why `search_replace` (which needs semantic localization) isn't hard.

## Exercise 2 is about reward hacking — don't skip it

Removing `check_path()`'s block usually still doesn't produce cheating, because the
prompt still forbids it. The lesson is that surviving with one defence removed
doesn't prove that defence was useless. To actually see it, they must remove the
prompt sentence *and* make the bug genuinely hard.

## Safety

This lab executes code. It runs a fresh copy of `workspace/` in `.run_<mode>_<task>/`
and blocks edits to the test files in two places. **It is not a sandbox** — say so
if a learner wants to point it at their own repo.

## Expected results and variance

Measured 2026-07-28 on Claude Code. fix: 3204 / 411 / 265 chars. refactor:
3413 / 1603 / 1194 chars. All six runs passed in round 1 with 0 failed edits.

The cost ordering is highly stable. Round counts and exact character counts vary.
If a learner gets a failed edit application, that's a genuine finding worth recording.

## Language

Chinese learners: `README.zh-CN.md` / `SOLUTION.zh-CN.md`, reply in Chinese.
For English program output: `LANG = "en"` at the top of `agent.py`.
