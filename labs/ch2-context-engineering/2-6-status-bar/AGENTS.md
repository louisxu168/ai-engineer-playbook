# TA notes — Lab 2-6

Read the repo-root `AGENTS.md` first.

## What this lab actually teaches

> **The book's claim reproduces cleanly on a weak model**: `no_status` violates 50%
> (10/20 on both passes, n=40); every form of aggregated metadata reduces it to 17-35%.
> The information is identical in all modes - only "who does the counting" changes.

Plus two things the book doesn't say:

> **1. TODO beat the status bar** (17.5% vs 32.5%), and an ablation supports why: the
> TODO carried an *alternative action*. Removing that one line took it from 8/20 to
> 13/20. **Telling a model what to do beats telling it what it can't do.**
>
> **2. `counter` (numbers only) barely helps** - a number without a conclusion or a way
> out is nearly as bad as nothing.

## Insist on `--weak`

On a frontier model all four modes score 0 violations. Learners will conclude status bars
don't matter. They must re-run with `--weak`; counting three records is trivial for a
frontier model, which is exactly the book's point (strong models save thinking tokens,
weak models save accuracy).

## Section 3 is the methodology payload

My first run at n=3 produced a **perfect monotonic gradient** (2/3, 1/3, 0/3, 2/3) and the
**wrong** conclusion. n=5 inverted it. Only n=20×2 settled it, and the truth contradicted
my first reading.

If a learner reports a different ordering, the first question is **"what was your n?"**
`TRIALS` defaults to 10 with a don't-lower-this comment for this reason.

## Exercise 2 is the open question

Adding a "suggested next step" to `status_bar` should let it catch `todo` if the
form/content hypothesis is right. **I didn't test it.** A learner who does upgrades
section 4 from directional evidence to a causal result - tell them that plainly.

## Be honest about variance

`todo`-with-alternative measured 3/20, 4/20 and 8/20 across three passes. The 25-point
ablation gap is directional, not a precise effect size. Don't let a learner quote it as
a hard number.

## Language

Chinese learners: `README.zh-CN.md` / `SOLUTION.zh-CN.md`.
For English program output: `LANG = "en"` at the top of `agent.py`.
