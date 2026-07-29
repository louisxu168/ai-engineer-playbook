# Chapter 2: Context Engineering

**English** · [简体中文](README.zh-CN.md)

Chapter 1 told you *what* context is. This chapter asks: **how do you manage it?**

Because real agents always hit these: the conversation outgrows the window,
external content smuggles instructions in, logs carry things that should never
reach the model.

---

## Labs in this chapter

| Lab | Topic | Takeaway | Status |
|---|---|---|---|
| [2-1 Context compaction](2-1-compaction/) | When it no longer fits: do nothing / truncate / compact | All three cost something; you only choose where to pay. Compaction quality ≈ compaction-prompt quality | ✅ |
| [2-2 Prompt injection](2-2-prompt-injection/) | What happens when a tool result carries instructions | Keyword filtering isn't a defence; a few sentences are | ✅ |
| 2-3 Log sanitisation | What should never enter the context | 📋 Planned |

---

## What this chapter is for

Chapter 1's three labs **take things apart**: remove a piece, see how it breaks.

This chapter starts **building**: given real constraints (finite window,
untrusted external content), what are the engineering options and what does each
one cost?

**2-1** is a good opener because its cost is fully quantifiable — the prompt size
is printed every round, so you literally watch the bar grow and then get squeezed
back down.

---

## Running them

Each lab is a **self-contained folder**:

```bash
cd 2-1-compaction
python3 agent.py            # prints usage
```

No API key needed.

---

## Relation to the source book

This parallels chapter 2 of *AI Agents in Depth* (9 companion experiments there).
**The code is an independent rewrite**, and the selection is deliberate:

| This repo | Book's version | Notes |
|---|---|---|
| 2-1 Context compaction | context-compression | Different task and implementation; adds a quantified size visualisation |
| 2-2 Prompt injection (planned) | prompt-injection | |
| 2-3 Log sanitisation (planned) | log-sanitization | |

**Deliberately not attempted**: `attention_visualization`, `kv-cache`,
`local_llm_serving` — they need local model weights and GPU inference, which
conflicts head-on with this repo's "no API key, clone and run" premise. Read the
book directly for those.

← [back to the index](../../README.md)
