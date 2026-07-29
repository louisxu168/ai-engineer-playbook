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
| [2-0 A local small model](2-0-local-llm/) | Run a 0.6B on your own machine, look under the API | "Raw" is layered - local deployment washes the output too | ✅ |
| [2-1 Context compaction](2-1-compaction/) | When it no longer fits: do nothing / truncate / compact | All three cost something; you only choose where to pay. Compaction quality ≈ compaction-prompt quality | ✅ |
| [2-2 Prompt injection](2-2-prompt-injection/) | What happens when a tool result carries instructions | Keyword filtering isn't a defence; a few sentences are | ✅ |
| [2-3 Log redaction](2-3-log-redaction/) | What should never enter the context | Redaction must strip identity without stripping sameness | ✅ |
| [2-4 Bad context patterns](2-4-bad-context-patterns/) | Breaking the cache vs breaking capability | The two kinds of damage cost very differently; sliding windows do both | ✅ |
| [2-5 Prompt ablation](2-5-prompt-ablation/) | Tone / structure / tool descriptions - which does the work | The book's "scrambling costs 30%" didn't reproduce; only the tool-description dimension still holds | ✅ |
| [2-6 Agent status bar](2-6-status-bar/) | Let it glance instead of recounting | The book's claim reproduces; but TODO wins - because it supplies an alternative action | ✅ |
| [2-7 Progressive disclosure](2-7-agent-skills/) | Loading Agent Skills on demand | Same shape as retrieval, but the model does the filtering - which repairs lab 4-2's failure | ✅ |
| [2-8 Attention visualisation](2-8-attention/) | Open the model, read the attention weights directly | The first token takes 81% and it's **content-independent**; a status bar's per-char density is 3.8x the trace's | ✅ |

---

## What this chapter is for

Chapter 1's three labs **take things apart**: remove a piece, see how it breaks.

This chapter starts **building**: given real constraints (finite window,
untrusted external content), what are the engineering options and what does each
one cost?

**2-1** is a good opener because its cost is fully quantifiable — the prompt size
is printed every round, so you literally watch the bar grow and then get squeezed
back down.

**2-2 and 2-3 belong together**, and reading them in order produces an apparent
contradiction worth sitting with: 2-2 measures keyword filtering *failing* to stop
injection, while 2-3 measures regex filtering *succeeding* at stopping PII leakage.
Same technique, opposite verdicts. The difference is whether there's an adversary
who adapts to your rules — which turns out to be the first question worth asking
about any security design.

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

This parallels chapter 2 of *AI Agents in Depth*.

The book's prose has **9 experiment numbers** (2-1 through 2-9), but only **8
companion projects** — **experiments 2-2 and 2-7 share the single
`attention_visualization` project** (2-2 covers the attention mechanism itself;
2-7 uses the same tool to validate the agent status bar). That's why the book's
project table has 8 rows with one of them numbered "2-2, 2-7".

**All 9 numbers are now covered**, plus one the book files under chapter 3
(log-sanitization). **The code is an independent rewrite**:

| This repo | **Book's number** | Book's project | Notes |
|---|---|---|---|
| 2-0 A local small model | **2-1** | local_llm_serving | Ollama + qwen3:0.6b; additionally measures TTFT / prefill, and **honestly reports that I could not reproduce prefix-cache invalidation** |
| 2-1 Context compaction | **2-9** | context-compression | Different task and implementation; adds a quantified size visualisation |
| 2-2 Prompt injection | **2-5** | prompt-injection | Adds an automatic attack-success judge, so defence effectiveness is measured rather than asserted |
| 2-3 Log redaction | **3-3** | log-sanitization | The book numbers it under chapter 3; adds the three-way raw / redacted / tokenized contrast |
| 2-4 Bad context patterns | **2-3** | kv-cache | History is hardcoded; five strategies process the same input, measuring *cache* damage and *capability* damage separately |
| 2-5 Prompt ablation | **2-4** | prompt-engineering | Not τ-bench — a support flow whose call *order* is mechanically checkable; a `--weak` flag runs the same suite on a local 0.6B to locate where the advice applies |
| 2-6 Agent status bar | **2-7, 2-8** | attention_visualization (2-7 uses it for the status-bar contrast), system-hint (2-8) | Uses the book's Xfinity three-phone-call scenario but with a **mechanical verdict** (does it place a 4th call); n=40 on a 0.6B confirms the book's "the small model in group A violates often" |
| 2-7 Progressive disclosure | **2-6** | agent-skills-ppt | Doesn't generate a real .pptx (that needs python-pptx) — it isolates **the disclosure mechanism itself**: verdict = does the answer contain the parameter format that exists only in layer 3, plus context token count |
| 2-8 Attention visualisation | **2-2, 2-7** | attention_visualization | Actually loads Qwen3-0.6B and pulls out the attention matrix (`attn_implementation="eager"`); quantitatively reproduces the book's 2-7 status-bar claim (3.8x per-char density) and **honestly reports that the dilution curve is not monotonic**, with the reason |

**Nothing in this chapter is left unattempted any more.**

This table used to list three: `local_llm_serving` (2-1), `kv-cache` (2-3) and
`attention_visualization` (2-2/2-7), with the reason "they need GPU inference."
**That reason was wrong**, and all three have since been built — they're 2-0, 2-4
and 2-8 above.

The only real barrier was 2-8's, and it isn't a GPU: it's the ~2.5GB `torch` +
`transformers` install. A 0.6B runs fine on CPU.

← [back to the index](../../README.md)
