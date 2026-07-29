# TA notes — Lab 8-1

Read the repo-root `AGENTS.md` first. This file is specific to this lab.

## What this lab actually teaches

Not "agents can learn". This:

> **Distilling lessons and distilling facts require opposite behaviour.** Lab 3-1
> measured good extraction beating the raw log. Here the **raw log beat the
> distilled lessons** on the failure curve (1→0→1 vs 1→1→1) — because the raw error
> text contained the three valid enum values and the "lessons" abstracted them away.

Plus the evaluation point:

> **"Didn't learn" and "never encountered" look identical in the metric.** T-3
> triggers a rule the earlier tickets never hit; failing there is correct.

## Make them read the lessons verbatim, not just the curve

The four lessons distilled after T-1 are all *correct software-engineering advice*
("confirm the enum's valid values", "keep the casing") and contain **zero
occurrences** of DEFECTIVE / WRONG_ITEM / CHANGED_MIND. Then T-2 invented
`DAMAGED_OR_DEFECTIVE` — a correctly-cased invented identifier, obeying its own
lessons perfectly.

Ask: *"which sentence in `sys_extract` caused that?"* Answer: criterion 2, "don't
include anything specific to this ticket". I wrote it; the model's reading was
defensible. That's exercise 1.

## Don't let them conclude "raw_log is better"

`raw_log` wins at 3 tickets and only at 3 tickets — it never dedupes and only grows,
which is lab 3-1's wall. `lesson` was also **the only mode to complete all three
tickets**. The honest summary is that each mode wins a different column and the
lab is too short to reach the crossover. Exercises 2 and 3 are where they find it.

## Section 7 of SOLUTION: I was wrong twice, the model was right twice

1. The model refused to call `issue_refund` because, driven through `claude -p`, it
   knows its real tool list and wouldn't fake an **irreversible refund** through a
   nonexistent tool. Correct behaviour, and exactly the caution we want.
2. It refused to treat a ticket number as an order id rather than invent one.

Both were my task description, not the model. This is the third time in this repo
that the experiment design was the bug (see also labs 6-1 and 10-1). If a learner
sees the agent refuse, that's the lesson, not a crash.

## Expected results and variance

Measured 2026-07-28 on Claude Code:
no_memory 1→1→2, 2/3 completed, 7 calls · raw_log 1→0→1, 2/3, 5 calls ·
lesson 1→1→1, **3/3**, 9 calls.

Stochastic. Stable parts: no_memory's curve doesn't descend; T-3 costs everyone at
least one failure. Whether `lesson` over-abstracts on a given run varies — if a
learner's run keeps the enum values, their curve will descend and that's a
legitimately different (and better) outcome worth discussing.

## Language

Chinese learners: `README.zh-CN.md` / `SOLUTION.zh-CN.md`, reply in Chinese.
For English program output: `LANG = "en"` at the top of `agent.py`.
