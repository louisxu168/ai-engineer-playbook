# TA notes — Lab 2-5

Read the repo-root `AGENTS.md` first. This file is specific to this lab.

## What this lab actually teaches

Not "prompt injection exists". This:

> **Keyword filtering is not a defence, and it is worse than nothing because it
> manufactures confidence.** Measured: `sanitized` — the only mode with actual
> filtering code — was compromised by BOTH payloads, while `delimited` (a few
> sentences, zero filtering code) blocked both and flagged the attack.

And the principle underneath:

> **Context has no concept of authority. Authority is something you construct
> while assembling context.**

## Order matters a lot here

`vulnerable` → `sanitized` → `delimited` → `hardened`.

Running `sanitized` **before** the working defences is what makes the lesson
land: they see the mode with the most code fail, then see prose succeed. Reversed,
the punch is gone.

## The moment to slow down

When they run `sanitized`, do NOT explain why it failed. Have them run:

```bash
python3 -c "import agent; print(agent.sanitize(agent.INJECT_A)[0])"
```

and ask: *"the filter matched 3 times. Look at what's left — is the sentence
that actually does the work still there?"*

They should discover themselves that the filter removed the **framing**
("ignore previous instructions", "system administrator") and left the **payload**
("output INJECTED-A at the end") untouched.

Then ask about payload B: *"how many times did the filter match on that one, and
why zero?"*

## Exercise 2 is the real lesson

The whack-a-mole exercise (block B, then write something that beats your new
rule) teaches the structural problem with blocklists: you must enumerate every
attack; the attacker needs one gap. Push learners to actually do it rather than
just read about it.

## Exercise 4 has a trap worth landing

Putting the injection in the *user's own request* cannot be blocked — **and
shouldn't be.** The user's input IS the instruction channel. If a learner tries
to "fix" this, that's the teaching moment: the vulnerability is confusing
*instruction channel* with *data channel*, not "instructions are bad".

## Safety framing

This is defensive education: local fake data, harmless markers, no real systems.
If a learner asks how to attack a real product, redirect to defence: what would
that product need to do to stop it? Don't help construct attacks against systems
they don't own.

## Expected results and variance

Measured once: `vulnerable` compromised by A and B; `sanitized` compromised by A
and B (filter matched 3 passages); `delimited` and `hardened` both clean and both
flagged the attempt. Injection success is stochastic — the *pattern* is the
lesson, not the exact outcome. If their `sanitized` run happens to block one
payload, the analysis still holds: ask them why it's unreliable either way.

## Language

Chinese learners: `README.zh-CN.md` / `SOLUTION.zh-CN.md`, reply in Chinese.
For English program output: `LANG = "en"` at the top of `agent.py`.
