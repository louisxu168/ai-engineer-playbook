# Chapter 6: Evaluation

**English** · [简体中文](README.zh-CN.md)

Five chapters of building. This one asks the question that decides whether any of
that building was progress:

> **How do you know it got better?**

---

## Labs in this chapter

| Lab | Topic | Takeaway | Status |
|---|---|---|---|
| [6-1 LLM-as-judge](6-1-llm-as-judge/) | keyword / score / rubric / pairwise | Verbosity bias is real and measurable; a rubric plus an evidence quote fixes it | ✅ |
| 6-2 Building a regression suite | Turning incidents into tests | 📋 Planned |

---

## What this chapter is for

**6-1** treats the evaluator as the thing under test. Four answers form a 2×2 of
length × correctness, and because the answers are authored rather than sampled,
"which one contains peanuts" is a **fact** — which is what makes it possible to
evaluate the evaluator at all.

The headline measurement: two answers that are **equally correct** and differ only
in length scored **1.3 points apart**. That's verbosity bias, isolated. The fix —
an explicit rubric plus a mandatory verbatim quote — took the judge from 3/4 to
4/4 with zero variance across 12 judgements.

The most portable part is smaller and more practical: **two bias checks that need
no labelled data at all.** Position bias (run every pair in both orders, count
flips) and self-consistency (repeat a judgement, look at the variance) cost nothing
but compute, which means most teams could run them tomorrow and don't.

This chapter also audits the rest of the repo. Every earlier lab has a verdict, and
they rank by one principle: **the closer a verdict sits to the real consequence,
the more reliable it is.** Keywords judge what text looks like; lab 5-1's unit
tests judge what code does.

---

## Running them

```bash
cd 6-1-llm-as-judge
python3 agent.py            # prints usage
```

No API key needed. The `keyword` mode needs no model at all.

---

## Relation to the source book

This parallels chapter 6 of *AI Agents in Depth*.
**The code is an independent rewrite**, and the selection is deliberate:

| This repo | Book's version | Notes |
|---|---|---|
| 6-1 LLM-as-judge | agent evaluation | Built around measuring the *judge's* biases rather than an agent's score, with authored ground truth so bias is isolatable |

← [back to the index](../../README.md)
