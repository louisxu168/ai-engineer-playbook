# TA notes — Lab 4-1

Read the repo-root `AGENTS.md` first. This file is specific to this lab.

## What this lab actually teaches

Not "write good docstrings". Two things:

> **1. Interaction effect.** Error-message quality is worth *nothing* when
> descriptions are good (measured: `good` and `silent_errors` are numerically
> identical — 3 rounds, 0 failures) and is the *difference between success and
> failure* when descriptions are bad (`vague_desc` resolved, `both_bad` did not).
>
> **2. For write tools, a vague error isn't slow — it's a hard stop.** And halting
> is the *correct* behaviour.

## The 2×2 is the pedagogy — don't let them run only one cell

If a learner runs `good` and `silent_errors` and concludes "error messages don't
matter", that's the designed trap. Let them say it, then have them run the bottom
row. The point isn't the answer, it's the method: **"does X matter?" is the wrong
question; "under what conditions does X matter?" is the right one.**

## The thing to make them read is `both_bad`'s hand-off note

They'll see "✗ not resolved" and move on. Stop them. Have them read the final
`[hand-off]` paragraph in full, then ask: **"did the model do anything wrong?"**

It didn't. It reasoned correctly that `"Call failed."` doesn't distinguish
"rejected, nothing happened" from "executed then failed", that `issue_refund` has
no idempotency key, and that a blind retry risks double-refunding a customer. It
then escalated with a precise hand-off and recommended the interface fix.

**The model out-engineered the tool.** That reframing — a vague error destroys the
agent's ability to know whether a side effect occurred — is the lab's real payload.

## Own the design flaw when it comes up

`tools_vague` documents `issue_refund(order_id, amount, reason)` while the code
takes `amount_cents`/`reason_code`. That means the "bad descriptions" cell varies
*two* things: sparse AND stale. It's not a clean single-variable comparison.

Don't hide this. Exercise 2 exists to separate them, and the measured ladder is:

| Version | Rounds | Failures |
|---|---|---|
| `vague_desc` as shipped | 5 | 3 |
| param names fixed | 4 | 2 |
| param names + reason enum documented | 3 | 1 |
| `good` | 3 | 0 |

## The best surprise is in exercise 1

Documenting *one* enum (`reason_code`) and not the other made the model call
`get_policy({"category": "DEFECTIVE"})` — it took the only documented enum and put
it in the undocumented slot. **Partial documentation misdirects.** If a learner
hits this, it's the most memorable moment in the lab; don't pre-empt it.

## Another moment worth catching

In `vague_desc` the model gets `amount_cents` numerically right despite the unit
never being documented — because it saw the field name in `find_orders`' *response*.
Ask them where it learned that. **Return-value field names are free documentation.**

## Expected results and variance

Measured 2026-07-28 on Claude Code: `good` 3/0 ✓ · `vague_desc` 5 rounds/3 failures ✓ ·
`silent_errors` 3/0 ✓ · `both_bad` ✗.

`vague_desc` was run twice by accident and reproduced exactly — same three traps in
the same order. The specific rounds vary between models, but **"it fails where the
documentation is missing" is stable**. If a learner's `both_bad` happens to succeed,
have them read its reasoning: did it get lucky on parameter names, or did it verify
anything?

## Language

Chinese learners: `README.zh-CN.md` / `SOLUTION.zh-CN.md`, reply in Chinese.
For English program output: `LANG = "en"` at the top of `agent.py`.
