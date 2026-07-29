# TA notes — Lab 2-0

Read the repo-root `AGENTS.md` first. This file is specific to this lab.

## What this lab actually teaches

Three things, in ascending order of value:

> **1.** A 0.6B model calls tools reliably — measured, it emitted **two parallel
> calls** and then fused both results into one sentence. The book's "size isn't the
> only factor" holds. State the preconditions though: 2 tools, 1 arg each, a format
> example in the prompt.
>
> **2. "Raw" is layered, and local deployment washes the output too.** Ollama strips
> `<think>` server-side into a separate `thinking` field. I tried to bypass the
> template (`raw:true`) and **failed** — thinking mode is driven by a template
> variable that `raw:true` skips.
>
> **3.** The prefill/decode split, and the number that motivates the whole chapter:
> **2050 tokens costs ~1000 ms of cold prefill vs ~10-40 ms warm.**

## The KV-cache section is the most important part — teach the process, not the result

I nearly shipped a wrong conclusion. With a 110-token prompt the first run gave a
textbook 18 → 8 → 55 ms. Two repeats gave 27 → 16 → **7** and 8 → 8 → 10. Prefill
at that size is ~10 ms — **pure noise**.

After growing the prompt to 2050 tokens the picture is stable and **does not match
the textbook**: B (ID at the start) and C (ID at the end) are indistinguishable,
both ~990 ms on first use then 10–40 ms.

Points to draw out with a learner:
- **A single run of a controlled experiment proves nothing**, and a textbook-clean
  result should *increase* suspicion.
- **Before measuring an effect, confirm it's larger than your noise floor.**
- **A failed experiment still produces output** — the 100× cold/warm gap is more
  useful for engineering than the effect I was chasing.

If a learner *does* reproduce a start-vs-end difference, that's a genuine finding.
Take it seriously and ask what differs in their setup (context length, model,
whether prefixes repeat, vLLM vs llama.cpp).

## Setup friction is real — handle it directly

This is the only lab needing an install. Per the repo-root AGENTS.md, environment
problems are yours to fix, not the learner's puzzle:

```bash
brew install ollama
ollama serve            # must stay running
ollama pull qwen3:0.6b  # ~500MB
```

No discrete GPU or CUDA. Apple silicon uses Metal. Measured 113–131 tok/s on an M3.
Uninstall: `ollama rm qwen3:0.6b && brew uninstall ollama`.

Python dependencies: **none**, deliberately. If a learner asks why not the `ollama`
pip package, that's the lab's point — the SDK wraps up the streaming and timing this
lab exists to expose.

## Expected results and variance

Measured 2026-07-29, M3/16GB, Ollama 0.32.5, qwen3:0.6b:
113–131 tok/s · TTFT 120–200 ms warm · prefill 2050 tok ≈ 1000 ms cold, 10–40 ms warm.

The 0.6B's tool calling is stochastic — it usually emits both calls in one turn, but
not always. Intel Macs will be far slower. The cold-vs-warm gap is the most stable
thing here.

## Language

Chinese learners: `README.zh-CN.md` / `SOLUTION.zh-CN.md`, reply in Chinese.
For English program output: `LANG = "en"` at the top of `agent.py`.
