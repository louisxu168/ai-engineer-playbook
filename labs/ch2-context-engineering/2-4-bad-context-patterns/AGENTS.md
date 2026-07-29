# TA notes — Lab 2-4

Read the repo-root `AGENTS.md` first.

## What this lab actually teaches

> **The five anti-patterns split into two categories with completely different costs:**
> breaking the **cache** costs money and latency but keeps answers correct; breaking
> **capability** hands you a wrong answer silently. **Sliding windows do both** — which is
> why they're the most expensive, and they're also the most popular.

Measured, reproduced twice:
`good` 148.9 → **7.9 ms** (19× cache speedup) · `dynamic_prompt` 181.2 → **176.1 ms**
(never hits) · `sliding_window` answers **21 instead of 37**.

## The design decision worth explaining

The history is **hard-coded, not model-generated**, so all five strategies see identical
input. And the question asks for **retrieval, not arithmetic** — my first version asked for
a sum and the 0.6B listed all five numbers correctly then added them wrong, measuring its
arithmetic rather than the context strategy. If a learner proposes a "harder" question,
that's the trap to point at: **don't let a second variable in.**

## Section 3 of SOLUTION is the most valuable part

This lab **solved lab 2-0's failure**. In 2-0 I alternated between two prompts, so Ollama
cached both and I concluded the effect wasn't reproducible. Here the timestamp is
microsecond-precision, so every prefix is novel and the effect is immediate.

Draw out: **"couldn't reproduce" should make you suspect the method first.** And the
counterweight: the **start-vs-end position effect is still unreproduced**, so don't let a
learner swing to "the books are all wrong" either.

## Be upfront about the two non-reproductions

- `flattened` did **not** break capability — the task doesn't need role boundaries.
  Exercise 4 designs one that does (prompt injection, tying back to lab 2-2).
- `shuffled_tools` shows a weak effect because the tool block is 5 lines. The book assumes
  hundreds of tokens per tool. **Read conclusions with their preconditions.**

## Exercise 3 is the bridge to lab 2-1

Summarising dropped messages into a stable front-of-window entry recovers **both** the
answer and the cache. That's compaction's motivation, derived by the learner rather than
asserted. If they only do one exercise, this one.

## Setup

Same Ollama environment as lab 2-0. A local model is **required** because cloud APIs don't
report prefill time.

## Language

Chinese learners: `README.zh-CN.md` / `SOLUTION.zh-CN.md`.
For English program output: `LANG = "en"` at the top of `agent.py`.
