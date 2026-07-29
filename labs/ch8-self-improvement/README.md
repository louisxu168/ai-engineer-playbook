# Chapter 8: Self-improvement

**English** · [简体中文](README.zh-CN.md)

Chapter 3 taught an agent to remember **facts**. This chapter asks the harder
question: can it remember **lessons** — and stop walking into the same wall?

---

## Labs in this chapter

| Lab | Topic | Takeaway | Status |
|---|---|---|---|
| [8-1 Learning from failure](8-1-learning-from-failure/) | no memory / raw log / distilled lessons | Distilling lessons and distilling facts need opposite behaviour | ✅ |
| 8-2 Self-improving prompts | Rewriting your own instructions | 📋 Planned |

---

## What this chapter is for

**8-1** gives an agent three refund tickets and a tool whose documentation is
missing three of its real validation rules. The only way to find them is to hit
errors — which is exactly what production feels like, because documentation always
lags implementation.

The measured result inverts lab 3-1. There, a good extraction prompt beat storing
the raw log. Here, **the raw log won the failure curve** — because the raw error
text contained the three valid enum values, and the "distilled lessons" abstracted
them away into correct, useless advice ("confirm the enum's valid values"), after
which the agent invented a correctly-cased identifier and failed again.

The principle: **when you store facts, abstraction purifies; when you store
lessons, abstraction can throw away the answer.** The most valuable part of a
lesson is usually the value that looks too specific to keep.

The chapter also carries an evaluation warning worth more than the result:
**"didn't learn" and "never encountered" are indistinguishable in the metric**
unless you know which rules are novel.

---

## Running them

```bash
cd 8-1-learning-from-failure
python3 agent.py            # prints usage
```

No API key needed.

---

## Relation to the source book

This parallels chapter 8 of *AI Agents in Depth*.
**The code is an independent rewrite**, and the angle is deliberate:

| This repo | **Book's number** | Book's project | Notes |
|---|---|---|---|
| 8-1 Learning from failure | **8-2** | gaia-experience | The book generates an experience document from successful / partial / failed trajectories; this lab scores a failure curve across episodes, with one rule deliberately appearing only in the final episode so "didn't learn" can be separated from "never seen". (The book's 8-1 is trajectory-verifier, a different thing) |

← [back to the index](../../README.md)
