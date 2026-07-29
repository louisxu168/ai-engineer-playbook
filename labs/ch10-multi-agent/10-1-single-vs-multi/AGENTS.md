# TA notes — Lab 10-1

Read the repo-root `AGENTS.md` first. This file is specific to this lab.

## What this lab actually teaches

Not "multi-agent is bad". This:

> **Multi-agent buys headroom, and you must confirm the headroom exists.**
> Measured: single scored 8/8 with 0 false positives in 1 call. Nothing beat it.
> chunked matched it at 4x cost; specialists matched it with +2 false positives at
> 4x cost; critic **lost a true finding** at 2x cost.

Plus each pattern's characteristic failure — which is the transferable part:

| Pattern | Assumes | Fails by |
|---|---|---|
| chunked | problems are local | cross-item problems become structurally invisible |
| specialists | every category is present | over-reporting |
| critic | stage one's recall sufficed | over-deleting; can only remove, never add |

## Step 0 is the whole lesson — don't let them skip it

Measuring the single-agent ceiling *first* is the habit this lab exists to build.
In real projects people ship multi-agent, see it work, and credit the architecture
without ever checking whether one agent would have sufficed.

If a learner's `single` run doesn't score 8/8, that's *better* — they have headroom
and multi-agent finally has a chance. Say so.

## The two moments worth stopping on

**1. The specialist breakdown.** Three specialists were flawless (2/2 each); all
over-reporting came from `INPUT` — the one category you can't define in a sentence.
Have them read the four per-agent lines. The rule that falls out: **if you can't
state in one sentence what counts, don't assign a dedicated specialist to it.**

**2. The critic's verdict on S14.** Its stated reason says `normpath` doesn't
validate, `../` can still escape, "but categorically this IS a real problem" — and
it set `decision: drop`. Right reasoning, inverted conclusion. Make them read it
verbatim before you explain anything.

## Section 5 of SOLUTION is the most important part of this lab

My original S13 used `os.path.join` + `startswith`, which **is** exploitable
(`/export/../etc/passwd` starts with `/export`). I had labelled it safe; the agents
reported it; the program called it a false positive. **The models were right and my
ground truth was wrong.**

Two things to draw out:
- **When your evaluation disagrees with the subject, suspect the evaluation first.**
- **Several independent agents reporting the same "false positive" is strong
  evidence it isn't one** — here two non-communicating agents flagged S13.

And: it was only catchable because the verdict is mechanical and itemised. An
overall LLM score would have smoothed it away.

If a learner says "I think snippet X is mislabelled", take it seriously and check
with them. That's the best possible outcome of this lab.

## Expected results and variance

Measured 2026-07-28 on Claude Code, after the S13 correction:
single 8/8, 0 FP, 1 call · chunked 8/8, 0 FP, 4 calls · specialists 8/8, 2 FP,
4 calls · critic 7/8, 0 FP, 2 calls.

Stochastic. The stable parts are the cost ratios and the *kinds* of failure. Which
specific snippet a critic drops, or which false positives appear, will move.

## Language

Chinese learners: `README.zh-CN.md` / `SOLUTION.zh-CN.md`, reply in Chinese.
For English program output: `LANG = "en"` at the top of `agent.py`.
