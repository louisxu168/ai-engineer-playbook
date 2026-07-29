# TA notes — Lab 6-1

Read the repo-root `AGENTS.md` first. This file is specific to this lab.

## What this lab actually teaches

Not "LLM-as-judge is biased". This:

> **Verbosity bias is measurable, and the clean way to measure it is a pair that
> differs ONLY on length.** Measured: A and C are equally correct; the long one
> scored **1.3 higher** (1.7 in an earlier run — same direction, same magnitude).
>
> And: **an explicit rubric plus a mandatory evidence quote fixed it completely** —
> 3/4 → 4/4, zero length gap, 12 judgements without a single fluctuation.

## Correct the misreading immediately when it appears

Learners will say "so the judge prefers long wrong answers". **It doesn't** — it
scored B (long, wrong) at 1.7, below A (short, correct) at 2.7. It caught B.

The real bias is **penalizing short answers that are entirely correct**. Push them
to state the consequence: use this judge to select or train, and **you get a
verbose agent**, with the penalty showing up in your metrics as "quality improved".

## The A-vs-C comparison is the transferable method

Not the number — the construction. **A pair differing only on the dimension under
test.** If the two samples differ on three axes, the measured gap means nothing.
Learners should leave able to design such a pair for their own system.

## Two measurements need no ground truth — hammer this

Position bias (run both orders, count flips) and self-consistency (repeat N times,
look at variance) require **zero labelled data**. That makes them the only bias
checks most teams can actually run tomorrow.

Position bias measured **0/4 flips** here — it did not reproduce. Don't let that
deflate the point: the method is the deliverable, not the result.

## Be honest about what wasn't tested

`rubric` changes **two** things at once (explicit criteria + evidence requirement).
This lab did not separate them, so no claim about which matters more is supported.
Exercise 1 is where learners do the 2×2. Say this out loud rather than letting the
SOLUTION's enthusiasm for the evidence requirement read as a measured finding.

## Section 6 is worth reading even to non-learners

I hit a real trap building this: a JSON parse failure returned a sentinel `0` that
got averaged in, and B was flagged "self-inconsistent" when actually **my parser had
failed**. A measuring-instrument failure recorded as a subject defect.

If a learner is building any eval, that section is the most directly useful part of
the lab. The diagnostic question: *do your failure rates move together with the
subject's apparent quality?*

## Connect it back to the repo

This lab audits chapters 1-5. The ordering principle: **the closer a verdict sits
to the real consequence, the more reliable it is.** Keywords judge text shape;
unit tests (lab 5-1) judge behaviour; LLM-as-judge sits in between. Learners should
leave with "use tests where you can, judges where you can't, keywords almost
nowhere".

## Expected results and variance

Measured 2026-07-28 on Claude Code, two independent runs.
keyword 3/4 (deterministic) · score 3/4 with a +1.3 length gap and 2/4 unstable ·
rubric 4/4, gap 0.0, fully stable · pairwise 4/4, 0/4 flips.

`keyword` is deterministic and will reproduce exactly. The others vary; the
*direction* of the verbosity gap has reproduced in both runs so far. If a learner
sees no gap, have them raise `REPEATS`.

## Language

Chinese learners: `README.zh-CN.md` / `SOLUTION.zh-CN.md`, reply in Chinese.
For English program output: `LANG = "en"` at the top of `agent.py`.
