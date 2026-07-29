# TA notes — Lab 2-3

Read the repo-root `AGENTS.md` first.

## What this lab actually teaches

> **The five anti-patterns split into two categories with completely different costs:**
> breaking the **cache** costs money and latency but keeps answers correct; breaking
> **capability** hands you a wrong answer silently.

Measured (interleaved, 32 rounds): `good` slow in **2/32** (cold start only) ·
`dynamic_prompt` slow in **32/32** (~190 ms vs ~10 ms) · `dynamic_profile` slow in
**22/32**, bimodal ·
`sliding_window` answers **21 instead of 37**.

## ⚠️ Point learners at `agent.py cache`, not `agent.py all`

`all` runs modes **sequentially**, which confounds "which mode" with "which position in the
sequence" — the local backend's state drifts, and the same config measured 180 ms on one
pass and 11 ms on another. `cache` interleaves (one request per mode per round) and is the
only valid instrument here. **This is the lab's real methodology payload.**

## The design decision worth explaining

The history is **hard-coded, not model-generated**, so all five strategies see identical
input. And the question asks for **retrieval, not arithmetic** — my first version asked for
a sum and the 0.6B listed all five numbers correctly then added them wrong, measuring its
arithmetic rather than the context strategy. If a learner proposes a "harder" question,
that's the trap to point at: **don't let a second variable in.**

## Section 3 of SOLUTION is the most valuable part

This lab **solved lab 2-1's failure**. In 2-0 I alternated between two prompts, so Ollama
cached both and I concluded the effect wasn't reproducible. Here the timestamp is
microsecond-precision, so every prefix is novel and the effect is immediate.

Draw out: **"couldn't reproduce" should make you suspect the method first.** Don't let a
learner swing to "the books are all wrong" either.

The postscript also closes 2-0's other open question: with interleaved measurement, the
**start-vs-end position effect does reproduce** — a change at token 0 is slow in 32/32
rounds, a change at ~token 200 in only 22/32 and more cheaply. **Position matters more than
the size of the change.**

## Be upfront about the non-reproductions and the one wrong prediction

- **`dynamic_profile` is where I predicted wrong** (SOLUTION section 2.5). I expected "one
  character at the end of the system prompt = same disaster as a timestamp at the start."
  Measured: free in 10 of 32 rounds, and only ~⅔ the cost when not free — llama.cpp reuses
  the suffix after a *short* divergence. **Cloud prompt caches do not**, so the book's
  advice still holds for APIs. Make sure learners take that distinction, not "the book is
  wrong."
- `sliding_window`'s cache damage is **not measurable here** — both requests use the same
  window position, so the prefix is identical and the cache hits. The book's claim is about
  the window advancing over turns. Exercise 5 supplies that half.
- `flattened` did **not** break capability — the task doesn't need role boundaries.
  Exercise 4 designs one that does (prompt injection, tying back to lab 2-5).
- `shuffled_tools` shows an unstable effect (order-dependent, same confound as above). The
  book also assumes hundreds of tokens per tool, which this lab's 5-line block doesn't meet.
  **Read conclusions with their preconditions.**

## Exercise 3 is the bridge to lab 2-9

Summarising dropped messages into a stable front-of-window entry recovers **both** the
answer and the cache. That's compaction's motivation, derived by the learner rather than
asserted. If they only do one exercise, this one.

## Correspondence to the book

The book's 实验 2-3 (`kv-cache` project) lists **five** anti-patterns plus the correct
baseline: dynamic system prompt, **dynamic user profile**, dynamic tool ordering, sliding
window, text formatting. This lab originally implemented only four — `dynamic_profile` was
missing and was added later. If a learner compares against the book, all six now line up.

The book runs on Kimi K2.6 via the Moonshot API and reads `cached_tokens` (a real cache-hit
counter). This lab runs locally and can only read prefill *timing*, which is noisier — hence
the interleaving requirement.

## Setup

Same Ollama environment as lab 2-1. A local model is **required** because cloud APIs don't
report prefill time.

## Language

Chinese learners: `README.zh-CN.md` / `SOLUTION.zh-CN.md`.
For English program output: `LANG = "en"` at the top of `agent.py`.
