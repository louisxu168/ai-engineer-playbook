# TA notes — Lab 2-3

Read the repo-root `AGENTS.md` first. This file is specific to this lab.

## What this lab actually teaches

Not "don't put PII in prompts". This:

> **Redaction strips identity; it must not strip sameness.** Measured:
> `redacted` achieved zero leakage and made the task *impossible* — the model
> correctly refused, saying "any conclusion would be fabricated". `tokenized`
> achieved zero leakage **and** full task success.

And the transferable principle:

> **"Zero leakage" is not the goal. "Zero leakage AND the task still works" is.**
> A safe design that breaks the job gets routed around in practice.

## The pivot is Step 1, and it depends on prediction

Almost everyone predicts `redacted` will be fine. Make them commit to an answer
**out loud** before running it — "can the task still be done? yes or no" — then
run it. The gap between their answer and the output is the whole lab.

Do not pre-explain why it fails.

## Do not let them skip `raw`

It's tempting to treat `raw` as a throwaway baseline. It isn't: the model's own
answer in `raw` mode spontaneously says *"rotate that API key immediately"*.
Point at that sentence and ask: **"how does it know the key is there?"**

That's the most persuasive single moment in chapter 2 for anyone who thinks
this is theoretical.

## The 2-2 contradiction is a feature — make them notice it

If a learner doesn't raise it, raise it yourself: *"in 2-2 I told you regex
filtering is not a defence. Here I'm telling you regex redaction works. Which
one of us is wrong?"*

Let them find it: **there's no adversary here, and the patterns are formats
rather than intent.** Both READMEs have the table, but discovering it beats
reading it.

## Exercise 2 is verified and it's the sharpest one

Loosening the phone rule to `\d{3}-\d{4}` and moving it above `CARD` produces
`card=4PHONE_2-1PHONE_2` — a shredded card number — **and `count_leaks()` still
reports zero.** The second half is the point: they built the redactor and the
verifier from the same rule table, so the verifier is blind to exactly the
failures the redactor causes. Make sure they see the `leaks: []` line, not just
the mangled card.

## Exercise 4 is the one that changes how they build things

Blocklist → allowlist. If a learner only does one exercise, push them to this
one. The measured result is that four sensitive fields disappear without a
single rule written for them.

## Safety framing

All data is fabricated: `example.com` (RFC 2606 reserved), 555 phone numbers
(reserved for fiction), API keys that literally say `FAKE`. If a learner wants to
run it against their real logs, that's fine and it's the point — but tell them to
check `count_leaks()` covers their formats first, and remind them of exercise 2:
their verifier is only as good as its rules.

## Expected results and variance

Measured 2026-07-28 on Claude Code: `raw` → 5 leak categories, task done;
`redacted` → zero leaks, task refused; `tokenized` → zero leaks, task done.

**Unlike most labs in this repo, this one is not stochastic** — the information
is either present or deleted. If `redacted` *does* name a user, the model
hallucinated, and that's a better lesson than the intended one: say so and dig
into it.

## Language

Chinese learners: `README.zh-CN.md` / `SOLUTION.zh-CN.md`, reply in Chinese.
For English program output: `LANG = "en"` at the top of `agent.py`.
