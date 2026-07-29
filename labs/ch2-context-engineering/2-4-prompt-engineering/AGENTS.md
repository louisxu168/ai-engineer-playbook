# TA notes — Lab 2-4

Read the repo-root `AGENTS.md` first.

## What this lab actually teaches

The book's headline (scramble the organisation → >30% success drop) **did not
reproduce**, on either a frontier model or a 0.6B. What the lab teaches instead:

> **1. Verdict design.** A rule the model would follow anyway measures nothing. I
> needed two failed versions to learn this — v1 used "verify before refunding", which
> matches the model's priors, so all five modes scored 0 violations.
>
> **2. Range of validity.** Frontier model: too strong, no discrimination. 0.6B: too
> weak, fails by looping on step one. **The effect lives in a band between them.**
>
> **3. The one dimension that survives**: removing tool descriptions raises tool errors
> on both models (frontier 1 vs 0; weak 24 vs 1-19), matching lab 4-1.

## Don't let learners conclude "the book is wrong"

The correct reading is **"this advice has a range of validity and the lower edge moved
between 2024 and 2026"** — not that it was never true. Exercise 2 (40 rules with
dependencies) is the most promising route to reproducing it, and the book's τ-bench
scenarios carry far more rules than this lab's ten.

## Exercise 3 is the one that matters

The lab proves the claim is **model-dependent**, which makes my numbers useless to any
given reader — but the harness isn't. Point them at swapping `_ask()` for the model
they actually ship.

## The `--weak` switch is the lab's best idea

Running the identical ablation on qwen3:0.6b (via Ollama) is what turns "I couldn't
reproduce it" into "here is where the effect lives". If a learner has a mid-tier model
available (7B–30B), that's exactly the band to test.

## Expected results and variance

Frontier: all five modes 0/3 violations, 3/3 compliant; only `no_tool_desc` produced a
tool error. Weak: dominated by `verify_identity` loops (9 of 15 runs).

`claude -p` is fairly deterministic here, so 3 trials often produce identical traces.
Raise `TRIALS` if a learner wants variance.

## Language

Chinese learners: `README.zh-CN.md` / `SOLUTION.zh-CN.md`.
For English program output: `LANG = "en"` at the top of `agent.py`.
