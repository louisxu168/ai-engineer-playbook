# TA notes — Lab 4-2

Read the repo-root `AGENTS.md` first. This file is specific to this lab.

## What this lab actually teaches

Not "retrieve your tools". This:

> **The folklore ("models get confused past ~20 tools") did not reproduce.**
> Measured 15/15 correct, including three purpose-built keyword traps and a case
> requiring reasoning by elimination.
>
> **What tools-at-scale actually costs is prompt length** — 331 → 1249 chars,
> re-paid on every turn of the loop.
>
> **And retrieval is a trade, not a free win**: measured, BM25 ranked the correct
> tool 9th with `RETRIEVE_K = 8`, so `retrieved` failed a task that `confusable`
> (all 40 tools) solved.

## The lab is a negative result — treat that as the feature

Learners expect `confusable` to break. It doesn't. Let them predict, watch it not
happen, and then redirect their attention to the prompt-length column. The point
is that **a negative result is a result**, and that received wisdom about models
expires.

Don't let them leave thinking "so tool count never matters" either — it matters
for cost, and it may well matter for weaker models or hundreds of tools. The
honest claim is narrow: *it didn't reproduce in this scenario.*

## The moment that carries the lab is Step 2

`retrieved` failing on example 5 while `confusable` succeeds. Make sure they run
both. Two things to draw out:

1. **Why BM25 missed it**: the request says "no phone number, no app" — and BM25
   boosted `send_sms` and `push_notification` to ranks 1 and 2 *because the request
   named them in order to rule them out*. **BM25 has no concept of negation.**

2. **The model's response to the bad candidate list**: it deduced email was needed,
   found no email tool, and refused to force a pick. Same as lab 4-1's `both_bad` —
   the model's judgement was fine; what we handed it wasn't.

## The English/Chinese discrepancy is the sharpest teaching moment

`email_customer` ranks 8th in Chinese (scrapes in, succeeds) and 9th in English
(cut, fails). Same task, same K.

Ask: *"which of those two pipelines is correct?"* Neither — one just landed on the
lucky side of a cutoff. **A pipeline that passes its tests and one that barely
didn't fall off look identical in the report.** If a learner's Chinese run doesn't
fail, that's why; have them set `LANG = "en"`.

## Verified exercise numbers

- Ex 2: correct tool ranks 9th, so `RETRIEVE_K = 9` recovers it. The follow-up
  question ("how would you have known?") is the actual lesson.
- Ex 4 (measured): baseline rank 9 → synonyms only rank **7** (recovers at K=8) →
  adding "no phone, no app" rank **1**. Point out that reaching 1st required
  knowing the question in advance — document expansion's built-in limit.

## Exercise 1 has a trap worth landing

If a learner "succeeds" by making two tools genuinely both defensible, that isn't a
model failure — it's a ground-truth failure. Use it: **tool-selection accuracy can
only measure questions that have a unique right answer**, and much of real tool
selection doesn't.

## Expected results and variance

Measured 2026-07-28 on Claude Code: 15/15 correct; prompts 331 / 1077 / 1249 / 355
chars; `retrieved` fails English example 5.

The **retrieval ranking is fully deterministic** — no model involved — so the rank-9
result reproduces exactly. The model's choices are stochastic; if a learner sees a
wrong pick, that's a genuine finding and they should record it.

## Language

Chinese learners: `README.zh-CN.md` / `SOLUTION.zh-CN.md`, reply in Chinese.
For English program output: `LANG = "en"` at the top of `agent.py`.
