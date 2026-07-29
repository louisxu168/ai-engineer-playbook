# Chapter 2: Context Engineering

**English** · [简体中文](README.zh-CN.md)

Chapter 1 told you *what* context is. This chapter asks: **how do you manage it?**

Because real agents always hit these: the conversation outgrows the window,
external content smuggles instructions in, logs carry things that should never
reach the model.

> **On numbering**: this chapter's folder names and numbers are taken **directly from
> the source book** ([*AI Agents in Depth*, chapter
> 2](https://bojieli.github.io/ai-agent-book/chapter2/)). `2-3-kv-cache` *is* the book's
> experiment 2-3 `kv-cache` — one-to-one, no lookup table needed. Other chapters still
> use this repo's own numbering.

---

## Labs in this chapter: one-to-one with the book

The book's chapter 2 has **8 companion projects** occupying **9 experiment numbers**
(experiments 2-2 and 2-7 share the single `attention_visualization` project).
**All 8 are built.**

| Book's number | Book's project | This repo's folder | Takeaway |
|---|---|---|---|
| **2-1** | `local_llm_serving` | [2-1-local-llm-serving](2-1-local-llm-serving/) | "Raw" is layered — local deployment washes the output too |
| **2-2**, **2-7** | `attention_visualization` | [2-2-attention-visualization](2-2-attention-visualization/) | The first token takes 81% and it's **content-independent**; a status bar's per-char density is 3.8× the trace's (that part *is* experiment 2-7) |
| **2-3** | `kv-cache` | [2-3-kv-cache](2-3-kv-cache/) | Breaking the cache vs breaking capability cost very differently; **measuring cache requires interleaving** |
| **2-4** | `prompt-engineering` | [2-4-prompt-engineering](2-4-prompt-engineering/) | The book's "scrambling costs 30%" didn't reproduce; only the tool-description dimension holds |
| **2-5** | `prompt-injection` | [2-5-prompt-injection](2-5-prompt-injection/) | Keyword filtering isn't a defence; a few sentences are |
| **2-6** | `agent-skills-ppt` | [2-6-agent-skills](2-6-agent-skills/) | Progressive disclosure has the same shape as retrieval, but the model does the filtering |
| **2-8** | `system-hint` | [2-8-system-hint](2-8-system-hint/) | The book's claim reproduces; but TODO wins — because it supplies an alternative action |
| **2-9** | `context-compression` | [2-9-context-compression](2-9-context-compression/) | All three paths cost something; you only choose where to pay |

**There is no `2-7-` folder because the book has no 2-7 project either.** The book's
experiment 2-7 ("validating the agent status bar through attention visualisation") states
explicitly that it is "based on the `attention_visualization` project" — so in this repo it
*is* `2-2-attention-visualization`'s `status_bar` mode:

```bash
cd 2-2-attention-visualization
python3 agent.py status_bar        # <- this is the book's experiment 2-7
```

> The book's **experiment 3-3 `log-sanitization`** is also built, but the book files it
> under chapter 3, so it lives at
> [../ch3-memory/3-3-log-sanitization](../ch3-memory/3-3-log-sanitization/).

---

## Nothing in this chapter is left unattempted

This section used to list three: `local_llm_serving` (2-1), `kv-cache` (2-3) and
`attention_visualization` (2-2/2-7), with the reason "they need GPU inference."
**That reason was wrong**, and all three have since been built.

The only real barrier was 2-2's, and it isn't a GPU: it's the ~2.5GB `torch` +
`transformers` install. A 0.6B runs fine on CPU.

---

## The code is an independent rewrite: what each lab changed

| Number | How it differs from the book |
|---|---|
| 2-1 | Ollama + qwen3:0.6b; additionally measures TTFT / prefill |
| 2-2 | Actually loads Qwen3-0.6B and pulls out the attention matrix (`attn_implementation="eager"`); quantitatively reproduces experiment 2-7's status-bar claim (3.8× per-char density) and **honestly reports that the dilution curve is not monotonic**, with the reason |
| 2-3 | All six of the book's modes (its 5 anti-patterns including **dynamic user profile**, plus the correct baseline); history is hardcoded. The book reads `cached_tokens` from Kimi; locally only prefill *timing* is available, so an interleaved `cache` mode was added |
| 2-4 | Not τ-bench — a support flow whose call *order* is mechanically checkable; a `--weak` flag runs the same suite on a local 0.6B |
| 2-5 | Adds an automatic attack-success judge, so defence effectiveness is measured rather than asserted |
| 2-6 | Doesn't generate a real .pptx (that needs python-pptx) — it isolates **the disclosure mechanism itself**: verdict = does the answer contain the parameter format that exists only in layer 3, plus context token count |
| 2-8 | Uses the book's Xfinity three-phone-call scenario but with a **mechanical verdict** (does it place a 4th call); n=40 on a 0.6B confirms the book's "the small model in group A violates often" |
| 2-9 | Different task and implementation; adds a quantified size visualisation |

---

## What this chapter is for

Chapter 1's three labs **take things apart**: remove a piece, see how it breaks.

This chapter starts **building**: given real constraints (finite window,
untrusted external content), what are the engineering options and what does each
one cost?

**2-9 (context compression)** is a good opener because its cost is fully quantifiable —
the prompt size is printed every round, so you literally watch the bar grow and then get
squeezed back down.

**2-5 (prompt injection) and 3-3 (log redaction) belong together**, and reading them in
order produces an apparent contradiction worth sitting with: 2-5 measures keyword filtering
*failing* to stop injection, while 3-3 measures regex filtering *succeeding* at stopping PII
leakage. Same technique, opposite verdicts. The difference is whether there's an adversary
who adapts to your rules — which turns out to be the first question worth asking about any
security design.

**2-3 and 2-2 also belong together**: 2-3 measures what context-management strategies
cost, while 2-2 opens the model up to see **where the attention actually lands**. Behaviour,
then mechanism.

---

## Running them

Each lab is a **self-contained folder**:

```bash
cd 2-3-kv-cache
python3 agent.py            # prints usage
```

No API key needed.

← [back to the index](../../README.md)
