# Chapter 3: Memory and knowledge

**English** · [简体中文](README.zh-CN.md)

Chapters 1 and 2 lived **inside one session**. This chapter asks the question that
starts the moment a session ends:

> **The context is cleared. Next week they're back. How do you still know who they
> are?**

---

## Labs in this chapter

| Lab | Topic | Takeaway | Status |
|---|---|---|---|
| [3-1 User memory](3-1-user-memory/) | Store nothing / store everything / extract | A memory system's quality is decided by what it refuses to remember | ✅ |
| [3-2 Retrieval from scratch](3-2-retrieval/) | When memory outgrows the context | Keyword search cannot find what shares no keywords with the query | ✅ |

---

## What this chapter is for

**3-1** takes the word "memory" apart. It turns out to be two verbs:

```
write: session ends   -> decide what to keep -> store
read:  session starts -> fetch               -> paste into the context
```

Four strategies, differing **only in the write**, produce wildly different
results — and the difference between the two extraction modes is literally one
prompt. Same law as lab 2-1: *compaction quality ≈ compaction-prompt quality;
memory quality ≈ extraction-prompt quality.*

Then it walks into the wall that no prompt fixes: **what do you do when a fact
changes?** Measured, none of the strategies handle it, for a reason that's
visible in a single line of code. That's the setup for how real memory frameworks
(mem0, Memobase) are built.

**3-2** picks up where 3-1 stops: memory outgrew the context, so now you have to
*choose* what to load. You write BM25 from scratch, then watch it fail in the way
that matters — the memory it drops shares not a single word with the question, so
it was never even a candidate. The answer built on that retrieval violated both of
the user's safety constraints while looking completely professional.

Together they give you the shape of the whole problem: **write-side filtering
loses information permanently; read-side filtering loses it for one turn. Both
drop things, in different ways.**

---

## Running them

Each lab is a **self-contained folder**:

```bash
cd 3-1-user-memory
python3 agent.py            # prints usage
```

No API key needed.

---

## Relation to the source book

This parallels chapter 3 of *AI Agents in Depth* (13 companion projects there).
**The code is an independent rewrite**, and the selection is deliberate:

| This repo | **Book's number** | Book's project | Notes |
|---|---|---|---|
| 3-1 User memory | **3-1, 3-2** | user-memory, mem0, memobase | Framework-free, stdlib only. Writes a readable JSON memory file per strategy so you can diff them; adds automatic measurement of size / junk / stale facts |
| 3-2 Retrieval from scratch | **3-5** | sparse-embedding | That book project is itself "BM25 sparse retrieval from scratch" - the closest match (I previously mislabelled this as retrieval-pipeline / agentic-rag; corrected). This lab adds a model-free recall verdict |

**Deliberately not attempted**: `dense-embedding`, `retrieval-pipeline`,
`contextual-retrieval` and the other RAG projects — they need embedding models
(local weights or a paid embedding API), which conflicts with this repo's
"no API key, clone and run" premise. 3-2 covers the *idea* of retrieval with a
from-scratch BM25 index instead, and shows you exactly where keyword retrieval
stops working — which is the reason embeddings exist. For production RAG, read the
book directly.

← [back to the index](../../README.md)
