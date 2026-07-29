# Lab 3-3 answers: log redaction

**English** · [简体中文](SOLUTION.zh-CN.md)

> ⚠️ Try it first. Being wrong once beats reading this ten times.

---

## 1. Measured results

Task: `分析这批日志，告诉我哪个用户触发的错误最多，是什么错误。`
("Which user triggered the most errors, and what error?")
Backend: Claude Code (`claude -p`), measured 2026-07-28.

| Mode | Leakage | Task | User the model named |
|---|---|---|---|
| `raw` | ☠ **5 categories of real sensitive data entered the context** | ✓ done | `zhang.wei@example.com` |
| `redacted` | ✓ zero | ✗ **impossible** | — (it explicitly said it couldn't) |
| `tokenized` | ✓ zero | ✓ done | `USER_1` |

**This is the first lab in this repo where the textbook expectation reproduced
exactly.** Several earlier labs' predicted failure modes simply didn't show up
(see the SOLUTIONs for 1-1 / 1-3 / 2-1). This one did — because the mechanism
here isn't probabilistic, it's **informational**: delete the information and it
is genuinely gone.

---

## 2. Full measured output, all three modes

### `raw` — the task works, at the cost of total leakage

```
====================================================================
  Round 1 of 6     mode: raw
  Handling: none - logs sent verbatim
====================================================================

  asking the model... took 6.5s

  [thinking] fetch the recent logs first, then analyse the error distribution

  [tool] fetch_logs()
  +- the logs as the model sees them (first 4 lines) ---
  | 2026-07-28 09:12:03 INFO  user=zhang.wei@example.com action=login ip=10.0.3.44 ok
  | 2026-07-28 09:12:41 ERROR user=zhang.wei@example.com action=checkout code=PAYMENT_TIMEOUT
  | 2026-07-28 09:13:02 INFO  user=li.na@example.com action=login ip=10.0.3.51 ok
  | 2026-07-28 09:14:19 ERROR user=zhang.wei@example.com action=checkout code=PAYMENT_TIMEOUT
  +----------------------------------------------------
  --- what went into the context this round ---
  ! 5 real sensitive value(s) entered the context: API key x1, card number x1, email x3, phone x1, internal IP x3
```

The answer in round 2 (excerpt, translated):

> The user with the most errors is **zhang.wei@example.com** — 5 errors, all
> `PAYMENT_TIMEOUT` on `action=checkout`…
>
> I also found sensitive data leaking into these logs, which needs separate
> handling: the DEBUG lines print an API key in plaintext (sk-FAKE-… /pay) and an
> unmasked card number (card=4111-…, masked_ok=false); the WARN line contains a
> plaintext phone number. **I'd rotate that API key immediately** and fix the log
> redaction.

**That last paragraph is the best irony in this lab:**

The model not only ingested the API key, it professionally advised you to rotate
it. **It's right.** And the only reason it could give that advice is that it saw
the key.

> Use this paragraph to convince a colleague: **anything you can read, the model
> read too.**

---

### `redacted` — zero leakage, but the task is dead

```
  [tool] fetch_logs()
  +- the logs as the model sees them (first 4 lines) ---
  | 2026-07-28 09:12:03 INFO  user=[REDACTED] action=login ip=[REDACTED] ok
  | 2026-07-28 09:12:41 ERROR user=[REDACTED] action=checkout code=PAYMENT_TIMEOUT
  | 2026-07-28 09:13:02 INFO  user=[REDACTED] action=login ip=[REDACTED] ok
  | 2026-07-28 09:14:19 ERROR user=[REDACTED] action=checkout code=PAYMENT_TIMEOUT
  +----------------------------------------------------
  --- what went into the context this round ---
  ok no real sensitive value entered the context
```

The answer (excerpt, translated):

> **I cannot determine "which user" triggered the most errors** — every `user`
> field was replaced with the same `[REDACTED]` placeholder, which could be one
> person or many, and there is no other distinguishing identifier (ip, session id
> are redacted too). Aggregating by user is not possible on this data.
> **Any "user X caused the most" conclusion would be fabricated.**
>
> What I *can* determine is the error distribution: 7 ERRORs total.
> - PAYMENT_TIMEOUT, 5, all on `action=checkout`…
> - UPSTREAM_5XX, 2, both on `action=refund`…
>
> If you need per-user attribution, please provide logs that preserve a user
> identifier — **a hash or pseudonym is fine, it doesn't need to be plaintext.**

```
  --- how did the task go? ---
  x it cannot tell users apart - over-redacted, task impossible
```

**Three things worth stopping on:**

1. **It didn't make anything up.** It said outright that any conclusion would be
   fabricated. That's good model behaviour — but **don't count on it**. A
   different model, or different phrasing, could easily pick one `[REDACTED]` and
   assert "this user". If your run did that, it's not a bug — it's the **more
   memorable lesson**: *over-redaction converts "I can't answer" into hallucination.*

2. **It degraded gracefully** to what it *could* compute (aggregate by error
   code). That points at a real design choice: if your task only needs "how many
   error types today", `redacted` is entirely sufficient and it's the safest
   option. **Not every task needs to tell entities apart.**

3. **It proposed the fix itself**: "a hash or pseudonym is fine". That is exactly
   what `tokenized` does.

---

### `tokenized` — both, at once

```
  [tool] fetch_logs()
  +- the logs as the model sees them (first 4 lines) ---
  | 2026-07-28 09:12:03 INFO  user=USER_1 action=login ip=IP_1 ok
  | 2026-07-28 09:12:41 ERROR user=USER_1 action=checkout code=PAYMENT_TIMEOUT
  | 2026-07-28 09:13:02 INFO  user=USER_2 action=login ip=IP_2 ok
  | 2026-07-28 09:14:19 ERROR user=USER_1 action=checkout code=PAYMENT_TIMEOUT
  +----------------------------------------------------
  --- what went into the context this round ---
  ok no real sensitive value entered the context
  +- token map (stays local, never sent to the model) ---
  | KEY_1  ->  sk-FAKE-9f2b1c4d8e7a6350
  | CARD_1  ->  4111-1111-1111-1111
  | USER_1  ->  zhang.wei@example.com
  | USER_2  ->  li.na@example.com
  | USER_3  ->  wang.tao@example.com
  +----------------------------------------------------
```

The answer (excerpt, translated):

> The user with the most errors is **USER_1** — 5 errors, all `PAYMENT_TIMEOUT`
> on `action=checkout`, clustered between 09:12 and 09:24 with repeated retries.
> Next is **USER_2**, 2 × `UPSTREAM_5XX` on `action=refund`. **USER_3** has no errors.
>
> Assessment: this isn't a single-user fluke, it's a payment-path failure —
> USER_1 hit the same error code 5 times in a row, plus there's an outbound call
> to /pay at 09:15 (apikey=KEY_1)…
>
> Two more records worth attention, unrelated to the errors: the 09:19 WARN asks
> for manual review at PHONE_1; the 09:23 DEBUG shows **CARD_1 with
> masked_ok=false**, i.e. card masking failed — a logging-compliance problem
> worth fixing at the same time.

```
  --- how did the task go? ---
  ok it identified a specific user (the answer names USER_1)
```

**This is the prettiest part of the lab. Read it line by line:**

- It produced **the same quality of analysis as `raw`** — same count of 5, same
  root-cause call
- It **reasoned using KEY_1 and CARD_1** — "an outbound call used some key",
  "a card failed masking"
- But it **doesn't know what the key is, or whose card that was**

> **That is what "sameness without identity" looks like in practice.**
>
> Nothing in this analysis required knowing who zhang.wei is — only that
> those 5 lines are the same person.

And the map is on your machine. If you actually need to notify zhang.wei, you
look it up in your own code — **that step doesn't happen inside the context.**

---

## 3. The comparison table (`all` mode output)

```
======================================================================
COMPARISON
======================================================================

mode: raw
  leakage: x 5 real sensitive value(s) entered the context
  task: ok completed (identified a specific user)

mode: redacted
  leakage: ok zero leakage
  task: x impossible (cannot tell users apart)

mode: tokenized
  leakage: ok zero leakage
  task: ok completed (identified a specific user)

Three approaches in one table:
  raw        task works, but everything leaked
  redacted   zero leakage, but the task is impossible
  tokenized  zero leakage AND the task works  <- what real systems do
```

Three rows, two columns, no ambiguous cell. **This is why both verdicts were
designed to be automatically measurable.**

---

## 4. Exercise answers

### Exercise 1 ⭐ Add a new kind of sensitive value

Run it *before* adding the rule: **the program reports zero leakage — while the
ID number is sitting right there in the logs.**

That's the real lesson here: **`count_leaks()` can only count what it recognizes.**
The reliability of "zero leakage" is exactly equal to the completeness of your
rule table.

The rule (put it above `USER` — it's the longer, more specific pattern):

```python
(r"\b\d{17}[\dXx]\b", "IDCARD", "national ID"),
```

> Generalize it: **"our scanner didn't alert" only ever means "we didn't scan for
> that".**

### Exercise 2 ⭐⭐ Loosen the phone rule, then move it up

Swapping the phone rule for `r"\d{3}-\d{4}"` and moving it above `CARD`, measured:

```
2026-07-28 09:19:40 WARN  contact phone=+1-PHONE_1 for manual review
2026-07-28 09:23:09 DEBUG card=4PHONE_2-1PHONE_2 masked_ok=false
```

The map:

```
PHONE_1 -> 555-0142        <- only ate the tail; "+1-" stayed in the clear
PHONE_2 -> 111-1111        <- not a phone number at all, it's the middle of the card
```

Two different breakages:

1. **The phone was only half redacted** — `+1-` remained. Harmless here; with a
   real area code it's a leak.
2. **The card got shredded**: `111-1111` inside `4111-1111-1111-1111` was eaten as
   a "phone", leaving the fragments `4` and `-1` in the context.

The genuinely dangerous part is the last line of output:

```
leaks reported: []
```

**The program reports zero leakage.** `count_leaks()`'s card rule demands a full
4-4-4-4 group, and it can't see the fragments. You get a clean bill of health
while part of a card number really did go out.

> Two rules, neither specific to redaction:
>
> 1. **Match the long, specific patterns before the short, general ones** — same
>    principle as tokenizers, URL routing, and lexers
> 2. **Using one ruleset both to redact and to verify the redaction is grading
>    your own exam** — in production those two should be written independently,
>    ideally by different people

### Exercise 3 ⭐⭐ Make the placeholders unstable

Fresh number per occurrence, measured:

```
2026-07-28 09:12:03 INFO  user=USER_1 action=login ip=IP_1 ok
2026-07-28 09:12:41 ERROR user=USER_2 action=checkout code=PAYMENT_TIMEOUT
2026-07-28 09:13:02 INFO  user=USER_3 action=login ip=IP_2 ok
2026-07-28 09:14:19 ERROR user=USER_4 action=checkout code=PAYMENT_TIMEOUT
...
leaks: []
distinct USER tokens: 11        <- there are only 3 real users
```

- **Leakage: still zero.** No real value entered the context.
- **Task: now impossible.** 3 real people shattered into 11 unrelated
  placeholders — same fate as `redacted`, nothing can be aggregated.

> So "zero leakage" is nowhere near sufficient. `redacted` has zero leakage.
> Unstable tokenization has zero leakage. Both are useless.
> **The real criterion is: leakage = 0 AND task = done.**

### Exercise 4 ⭐⭐⭐ Switch from blocklist to allowlist

Reference implementation:

```python
ALLOWED_FIELDS = ["action", "code"]   # only these field names pass

def allowlist(text):
    """Keep the timestamp, level, tokenized user, and allowlisted fields."""
    tokenized_text, mapping = tokenize(text)
    out = []
    for line in tokenized_text.split("\n"):
        parts = line.split()
        kept = parts[:3]                       # date, time, level
        for p in parts[3:]:
            if "=" not in p:
                continue
            key = p.split("=")[0]
            if key == "user" or key in ALLOWED_FIELDS:
                kept.append(p)
        out.append(" ".join(kept))
    return "\n".join(out), mapping
```

Measured output:

```
2026-07-28 09:12:03 INFO user=USER_1 action=login
2026-07-28 09:12:41 ERROR user=USER_1 action=checkout code=PAYMENT_TIMEOUT
2026-07-28 09:13:02 INFO user=USER_2 action=login
2026-07-28 09:15:33 DEBUG                            <- whole line stripped to timestamp + level
2026-07-28 09:19:40 WARN
2026-07-28 09:23:09 DEBUG
...
leaks: []
```

`ip=`, `apikey=`, `phone=`, `card=` are **all gone automatically** — you wrote
zero rules for any of them. Lines 5 / 9 / 13 collapsed to just a timestamp
because **nothing on them was on the allowlist**.

Add a new `ssn=` field? Also gone automatically. **That's the key difference:**

| | What you must enumerate | When a new field appears |
|---|---|---|
| Blocklist | every risk (unbounded, growing) | **leaks by default** |
| Allowlist | your needs (finite, defined by you) | **blocked by default** |

> Security calls this **fail-closed**. A blocklist is fail-open — a structural
> flaw, independent of how well it's written.

The cost: when the task needs a new field, you have to change code. **That cost
is correct** — it forces you to ask "should the model see this?" every time you
add one.

### Exercise 5 ⭐⭐⭐ Let the agent request a decode

Reference implementation:

```python
def reveal(token, mapping, audit_log):
    """The agent asks to decode a token. Every request is audited."""
    audit_log.append(token)
    print("  ! agent requested decode: " + token)
    if token.startswith("KEY_") or token.startswith("CARD_"):
        return {"error": "denied: keys and card numbers are never decoded"}
    return {"value": mapping.get(token, "unknown token")}
```

**"Solved or relocated?" — it's both, and that's the answer.**

Relocated: once decoded, the real value is in the context and the leak happens
just the same.

Solved, in three ways, each a real gain:

1. **Default flipped from leak to no-leak.** Values go out on demand instead of
   everything going out up front.
2. **There's now an audit trail.** You can answer "how many real emails did the
   agent see last week" — under `raw` that question can't even be posed.
3. **You can grade by type.** In the code above, `KEY_` and `CARD_` are **never**
   decoded, because no log-analysis task needs a real secret.

> Real systems usually add a fourth: **decoding requires human approval**, or is
> only permitted once the agent has already reached a conclusion and needs to act.
>
> This is what **least privilege** looks like in context engineering.

---

## 5. How this lab relates to 2-2 (get this and chapter 2 clicks)

The three labs in chapter 2 are the three ways a context fails:

| Lab | Failure | Nature of the fix |
|---|---|---|
| 2-1 Compaction | The context **doesn't fit** | An engineering trade-off (tokens vs information) |
| 2-2 Injection | The context is **poisoned** | **Structural** defence (declare boundaries); filtering fails |
| 2-3 Redaction | The context **contains what it shouldn't** | **Filtering works** (allowlist works better) |

The apparent contradiction between 2-2 and 2-3 ("regex is useless" vs "regex
works") is the most portable lesson in the chapter:

> **Whether an adversary adapts to your rules determines whether enumeration can
> ever work as a defence.**

- Email formats don't mutate because you wrote a regex → enumeration is viable
- Attacker phrasing mutates precisely because you wrote a regex → enumeration loses

When judging any security design, the first question is always: **will the
adversary adapt?**

---

← [back to the chapter](../README.md) · [back to the index](../../../README.md)
