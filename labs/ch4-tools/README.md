# Chapter 4: Tools

**English** · [简体中文](README.zh-CN.md)

For three chapters tools were incidental — something the loop happened to call.
This chapter looks at them directly, and the finding is uncomfortable:

> **Most agent failures blamed on the model are actually tool-design failures.**

---

## Labs in this chapter

| Lab | Topic | Takeaway | Status |
|---|---|---|---|
| [4-1 Tool design](4-1-tool-design/) | Descriptions × error messages, as a 2×2 | Error quality is worthless with good docs and decisive with bad ones | ✅ |
| [4-2 Too many tools](4-2-tool-selection/) | Selecting from dozens of tools | The "20 tools" folklore didn't reproduce; the real cost is prompt length | ✅ |

---

## What this chapter is for

**4-1** turns "write good tool docs" into something measurable. Handing a model a
tool means handing it two things — up-front documentation and after-the-fact error
feedback — so the lab makes those independent switches and runs all four
combinations.

The result is an **interaction effect**, which is the actual lesson: error-message
quality measured as *completely irrelevant* in the top row (with good descriptions
the model never errs, so errors never fire) and as *the difference between resolved
and unresolved* in the bottom row.

Then it goes somewhere better than designed. In the both-bad cell the model
refused to retry a failed refund — correctly reasoning that an opaque `"Call
failed."` can't distinguish "rejected, nothing happened" from "executed, then
failed", and that retrying without an idempotency key risks refunding the customer
twice. It escalated to a human with a precise hand-off and recommended the
interface fix.

**The model out-engineered the tool.** Which is the chapter in one sentence: for
tools that change the world, a vague error isn't slow — it's a hard stop, and
halting is correct.

**4-2** was built to reproduce a different piece of received wisdom — "models get
confused past ~20 tools" — and **failed to**: 15/15 correct across 40 tools
including 6 near-identical ones and three purpose-built keyword traps. What the
measurement *did* find is that the cost is prompt length (331 → 1249 chars,
re-paid every turn), and that retrieving tools to cut it introduces a failure mode
"paste everything" doesn't have. That failure fires in the lab: BM25 ranks the
correct tool 9th with a cutoff of 8, so the retrieval mode fails a task the
all-40 mode solves.

---

## Running them

Each lab is a **self-contained folder**:

```bash
cd 4-1-tool-design
python3 agent.py            # prints usage
```

No API key needed.

---

## Relation to the source book

This parallels chapter 4 of *AI Agents in Depth* (perception / execution /
collaboration tools, active tool discovery and selection, async agents).
**The code is an independent rewrite**, and the selection is deliberate:

| This repo | **Book's number** | Book's project | Notes |
|---|---|---|---|
| 4-1 Tool design | **2-4** (in chapter 2) | prompt-engineering | That project quantifies how **tool descriptions** and similar factors affect task completion - much closer to this lab than chapter 4's execution-tools (I previously mislabelled it; corrected). Here it's a 2×2 ablation with a mechanical verdict |
| 4-2 Too many tools | **4-6** | active-tool-discovery | The book contrasts injecting 120+ tool schemas against on-demand retrieval; this lab adds cost quantification and measures retrieval's recall failure |

**Deliberately not attempted (yet)**: `agent-with-event-trigger` and `async-agent`
need a running service and a scheduler, which sits awkwardly with this repo's
"clone one folder and run it" premise. Read the book directly for those.

← [back to the index](../../README.md)
