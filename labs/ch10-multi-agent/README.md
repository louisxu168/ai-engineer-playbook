# Chapter 10: Multi-agent

**English** · [简体中文](README.zh-CN.md)

The most over-mythologised topic in the field. This chapter breaks "multi-agent
collaboration" into concrete patterns and measures them against the obvious
baseline — one agent.

---

## Labs in this chapter

| Lab | Topic | Takeaway | Status |
|---|---|---|---|
| [10-1 One agent vs many](10-1-single-vs-multi/) | single / chunked / specialists / critic | Multi-agent buys headroom; confirm the headroom exists first | ✅ |
| 10-2 Handoffs and shared state | What agents pass to each other | 📋 Planned |

---

## What this chapter is for

**10-1** measures four collaboration patterns on one task with one model, using a
mechanical verdict (8 hard-coded ids, set arithmetic). The measured result is
uncomfortable and useful: **the single agent won outright** — 8/8 found, zero false
positives, one call. Nothing beat it, and two patterns were strictly worse.

The reason is the lesson: the single agent had **already saturated the task**, so
recall had nowhere to go and the only things left to change were cost and false
positives. Both got worse.

What transfers is each pattern's characteristic failure. Splitting by data assumes
problems are local — cross-item findings become structurally invisible. Splitting
by concern over-reports, and measurably **the over-reporting concentrated entirely
in the one category that can't be defined in a sentence**. A verifier can only
remove, never add, so it buys precision and risks recall — and here it deleted a
real finding while its own written reasoning argued for keeping it.

The chapter also contains the repo's sharpest evaluation lesson: **my ground truth
was wrong and the models caught it.** A snippet I'd labelled safe was genuinely
exploitable, reported independently by two agents, and recorded by my program as a
false positive.

---

## Running them

```bash
cd 10-1-single-vs-multi
python3 agent.py            # prints usage
```

No API key needed.

---

## Relation to the source book

This parallels chapter 10 of *AI Agents in Depth*.
**The code is an independent rewrite**, and the angle is deliberate:

| This repo | Book's version | Notes |
|---|---|---|
| 10-1 One agent vs many | multi-agent collaboration | Framed as a measurement rather than a demonstration: every pattern is compared against the single-agent baseline on a mechanically scored task |

← [back to the index](../../README.md)
