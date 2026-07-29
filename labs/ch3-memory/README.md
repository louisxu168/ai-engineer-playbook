# Chapter 3: Memory & Knowledge

**English** · [简体中文](README.zh-CN.md)

Chapters 1 and 2 stayed **inside one session**. This chapter starts the moment a
session ends:

> **The context is cleared. He comes back next week — how do you still know him?**

> **On numbering**: this chapter's folder names and numbers are taken **directly from
> the source book** ([*AI Agents in Depth*, chapter
> 3](https://bojieli.github.io/ai-agent-book/chapter3/)). `3-5-sparse-embedding` *is* the
> book's 3-5 `sparse-embedding` — one-to-one, no lookup table needed.

---

## One-to-one with the book: 13 projects, 4 built

The book's chapter 3 has **13 companion projects**. **4 are built so far.** The table
below is the book's own table, annotated with this repo's status row by row:

| Book's number | Book's project | This repo | Status |
|---|---|---|---|
| **3-1**, **3-2** | `user-memory` | [3-1-user-memory](3-1-user-memory/) | ✅ |
| **3-1** | `user-memory-evaluation` | — | ⬜ not built |
| **3-2** | `mem0` · `memobase` | — | ⬜ not built |
| **3-3** | `log-sanitization` | [3-3-log-sanitization](3-3-log-sanitization/) | ✅ |
| **3-4** | `dense-embedding` | [3-4-dense-embedding](3-4-dense-embedding/) | ✅ |
| **3-5** | `sparse-embedding` | [3-5-sparse-embedding](3-5-sparse-embedding/) | ✅ |
| **3-6** | `retrieval-pipeline` | — | ⬜ not built |
| **3-7** | `multimodal-agent` | — | ⬜ not built |
| **3-8** | `structured-index` | — | ⬜ not built |
| **3-9** | `agentic-rag` | — | ⬜ not built |
| **3-10** | `agentic-rag-for-user-memory` | — | ⬜ not built |
| **3-11** | `contextual-retrieval` | — | ⬜ not built |
| **3-12** | `contextual-retrieval-for-user-memory` | — | ⬜ not built |
| **3-13** | `structured-knowledge-extraction` | — | ⬜ not built |

> Numbers 3-1 and 3-2 each map to several projects — **that's how the book is**:
> `user-memory` occupies both 3-1 and 3-2, `user-memory-evaluation` is also 3-1, and
> `mem0 · memobase` are 3-2's reference implementations.

### ⚠️ Retracting a reason I got wrong

This section used to claim those RAG projects "need an embedding model (local weights or a
**paid embedding API**), which conflicts with this repo's zero-API-key premise."

**That reason was wrong.** Measured:

```bash
ollama pull nomic-embed-text          # 274MB
curl http://127.0.0.1:11434/api/embed \
  -d '{"model":"nomic-embed-text","input":"the user does not eat spicy food"}'
# -> a 768-dim vector, zero API key, same Ollama setup chapter 2 already uses
```

So `retrieval-pipeline` (3-6) and `contextual-retrieval` (3-11) have **no technical
barrier**. The real reason they're absent is one sentence: **I haven't built them yet.**

`dense-embedding` (3-4) has since been built down exactly that path — it uses the very
`nomic-embed-text` above, zero API key. **So that "technical barrier" doesn't exist at all;
it wasn't merely worked around.**

> This is the same mistake I made in chapter 2: inventing a technical reason for "not done"
> and never verifying it. All three of chapter 2's were later built.

`mem0 · memobase` (3-2) is the only one with a genuine trade-off: it requires those two
third-party frameworks, whereas this repo's 3-1 deliberately uses the standard library only
— precisely so you can see what a framework is doing for you.

---

## The four that exist

| Lab | Topic | Takeaway |
|---|---|---|
| [3-1 User memory](3-1-user-memory/) | none / all / extracted | A memory system's quality is decided by what it refuses to remember |
| [3-3 Log sanitization](3-3-log-sanitization/) | What should never enter the context | Redaction must strip identity without stripping sameness |
| [3-4 Dense retrieval](3-4-dense-embedding/) | Is "just use embeddings" true? | Dense isn't an upgrade over sparse, it's a **different way of missing**; the most dangerous memory is missed by all six configurations |
| [3-5 Retrieval from scratch](3-5-sparse-embedding/) | When memory outgrows the context | Keyword search cannot find what shares no keywords with the query |

**The code is an independent rewrite**:

| Number | How it differs from the book |
|---|---|
| 3-1 | No frameworks, standard library only; each strategy writes a readable JSON memory file you can diff; adds automatic measurement of size / junk / stale facts |
| 3-3 | Adds the three-way raw / redacted / tokenized contrast, so you see over-redaction destroy the task |
| 3-4 | The book uses the ANNOY and HNSW libraries; here both indexes are written **from scratch** (numpy only - `annoy`'s wheel is broken on this machine, see SOLUTION). Adds a half the book doesn't have: **a sparse/dense contrast on the same corpus and question as 3-5** |
| 3-5 | That book project is itself "BM25 sparse retrieval from scratch"; this lab adds a model-free recall verdict |

---

## What this chapter is for

**3-1** takes the word "memory" apart. It turns out to be two verbs:

```
write: session ends   -> decide what to keep -> store
read:  session starts -> fetch               -> paste into the context
```

Four strategies, differing **only in the write**, produce wildly different
results — and the difference between the two extraction modes is literally one
prompt. Same law as lab 2-9: *compaction quality ≈ compaction-prompt quality;
memory quality ≈ extraction-prompt quality.*

Then it walks into the wall that no prompt fixes: **what do you do when a fact
changes?** Measured, none of the strategies handle it, for a reason that's
visible in a single line of code. That's the setup for how real memory frameworks
(mem0, Memobase) are built — which is exactly what the book's 3-2 contrast covers.

**3-5** picks up where 3-1 stops: memory outgrew the context, so now you have to
*choose* what to load. You write BM25 from scratch, then watch it fail in the way
that matters — the memory it drops shares not a single word with the question, so
it was never even a candidate. The answer built on that retrieval violated both of
the user's safety constraints while looking completely professional.

> **Where 3-5 fails is exactly why embeddings exist** — hence **3-4**.
>
> But 3-4's measured conclusion is *not* "embeddings solved it": the "ingestion means the ER"
> memory is missed by **all six configurations** — 2 methods × 2 models × 2 languages. Dense
> retrieval lifted "no spicy" from #4 to #1 (real capability) while leaving the peanut allergy
> at #21/36 (unreachable).
>
> **Do 3-5 first, then 3-4.** The other order wastes the cliffhanger 3-5 ends on.

Together they give you the shape of the whole problem: **write-side filtering
loses information permanently; read-side filtering loses it for one turn. Both
lose things, in different ways.**

**3-3** is a separate thread: not "can it remember" but "**should it**". Read alongside
chapter 2's 2-5 (prompt injection) it produces a contradiction worth sitting with — see the
[chapter 2 index](../ch2-context-engineering/README.md).

---

## Running them

Each lab is a **self-contained folder**:

```bash
cd 3-1-user-memory
python3 agent.py            # prints usage
```

No API key needed.

← [back to the index](../../README.md)
