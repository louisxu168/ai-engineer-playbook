# Lab 2-3: Log redaction — what should never enter the context

**English** · [简体中文](README.zh-CN.md)

> **What you'll learn**
>
> 1. The third context risk: not "too big" (2-1), not "poisoned" (2-2), but
>    **it contains things it shouldn't**
> 2. Why "redact everything" **destroys the task itself** — safety and usefulness
>    genuinely pull against each other
> 3. **Reversible tokenization**: zero leakage *and* the task still works. This is
>    what real systems do
> 4. Why regex works here but didn't in 2-2 — **the threat model is different**
>
> **How you'll learn it**: the program automatically counts how many real
> sensitive values entered the context, *and* automatically judges whether the
> task succeeded. Both are objectively measurable, so the trade-off is visible.
>
> **Time**: 15 minutes (no network, runs fast).
>
> ⚠️ Every sensitive value in the logs is **fabricated**: emails use
> `example.com` (an RFC-reserved domain), phones use the 555 range (reserved for
> fiction), API keys literally say `FAKE`.

---

## The problem

You're on-call. Something broke. You paste the logs into an agent. They look
like this:

```
2026-07-28 09:12:03 INFO  user=zhang.wei@example.com action=login ip=10.0.3.44 ok
2026-07-28 09:12:41 ERROR user=zhang.wei@example.com action=checkout code=PAYMENT_TIMEOUT
2026-07-28 09:15:33 DEBUG outbound call apikey=sk-FAKE-9f2b1c4d8e7a6350 endpoint=/pay
2026-07-28 09:23:09 DEBUG card=4111-1111-1111-1111 masked_ok=false
```

**You have just done something irreversible.** User emails, internal IPs, an API
key, a card number — all sent to a model provider. Possibly logged, retained,
seen.

> That line from lab 1-1 becomes a security property here:
> **whatever the tool returns goes into the context verbatim.** Not filtering
> means sending everything.

The obvious fix is "redact it". Below you'll find that redaction has a real
dilemma in it.

---

## Step 0: measure the leak (3 min)

```bash
cd labs/ch2-context-engineering/2-3-log-redaction
python3 agent.py raw
```

Press Enter for examples, then type `1` ("which user triggered the most errors").

### 👀 What you'll see

```
  +- the logs as the model sees them (first 4 lines) ---
  | 2026-07-28 09:12:03 INFO  user=zhang.wei@example.com action=login ip=10.0.3.44 ok
  +----------------------------------------------------
  --- what went into the context this round ---
  ! 5 real sensitive value(s) entered the context: API key x1, card number x1, email x3, phone x1, internal IP x3

  --- how did the task go? ---
  ok it identified a specific user
```

### 💡 What you learn

**The task worked. The cost was total leakage.** This is where almost everyone
starts — not out of carelessness, but because **nothing about the step tells you
it happened**.

> Notice the model's own answer: it spontaneously points out that the logs
> contain a plaintext API key and an unmasked card number.
> **It can see them — which is exactly the proof they entered the context.**

---

## Step 1: predict, then run "redact everything" (5 min)

### 🤔 Predict first (this is the pivot of the whole lab)

`redacted` mode replaces every sensitive value with `[REDACTED]`. Predict:

- How many leaks remain? ___
- **Can the task still be done?** ___

Give the second one a genuine 10 seconds before reading on.

### 🔧 Do this

```bash
python3 agent.py redacted "(paste the same task)"
```

(After the `raw` run the program prints this exact line for you — just copy it.)

### 👀 What to watch

The last two verdicts, **read together**: how much leaked, and did the task work.

### 💡 What you learn

Open `agent.py` and look at `redact_all()`. It's three lines:

```python
for pattern, _prefix, _desc in REDACTION_RULES:
    result = re.sub(pattern, placeholder, result)
```

Nothing is wrong with the code. The problem is **informational**: three distinct
users all became `[REDACTED]`, so "which user has the most errors" **no longer
has an answer in this data**.

> **More redaction is not strictly better. Past a point, the task stops existing.**

This is the most-ignored half of security engineering: a perfectly safe design
that makes the job impossible gets routed around in practice — the engineer
quietly switches back to `raw`.

---

## Step 2: the path that gets both (5 min)

```bash
python3 agent.py tokenized "(the same task)"
```

### 👀 What to watch

Three things:

1. What the logs look like to the model now
2. The **token map** — note it's printed separately, marked "never sent to the model"
3. The last two verdicts

### 💡 What you learn

The core of `tokenize()`:

```python
counters[prefix] = counters.get(prefix, 0) + 1
token = prefix + "_" + str(counters[prefix])
mapping[token] = match
result = re.sub(re.escape(match), token, result)
```

**The whole trick is the word "stable"**: the same real value always maps to the
same placeholder.

| | Real identity | Sameness |
|---|---|---|
| `raw` | kept ✗ | kept ✓ |
| `redacted` | discarded ✓ | **discarded ✗ ← the task dies here** |
| `tokenized` | discarded ✓ | **kept ✓** |

The model can count "USER_1 hit 5 errors" without knowing who USER_1 is.
**Reasoning needs sameness, not identity.** Those two are separable — that's all
of it.

The map stays on your machine. When you genuinely need the real value (file a
ticket, notify the user) you decode it — but that happens **in your process**,
not in the context.

> This is **reversible tokenization**. Log scrubbing, database masking, privacy
> engineering, and PCI card handling all use the same move.

---

## Step 3: full comparison (2 min)

```bash
python3 agent.py all "(the same task)"
```

Three runs, then a table. **That table is the entire conclusion of this lab.**

---

## ⚠️ Hold on — doesn't this contradict lab 2-2?

In 2-2 I said "keyword filtering is not a defence". Here I say "regex redaction
works".

**Both are true, because the threat models differ.**

| | Lab 2-2 injection defence | Lab 2-3 log redaction |
|---|---|---|
| Adversary | Yes, and they **adapt to your rules** | None. You defined the log format |
| What you must match | "all natural language that expresses a command" — **infinite** | "the shape of an email / card / key" — **finite and known** |
| Cost of missing one | The whole defence fails | You miss one; the rest still hold |

> **Regex is good at matching *formats*. It is bad at matching *intent*.**
>
> An email has a shape. Malice has ten thousand phrasings.

Internalizing this is worth more than any specific technique in either lab.

⚠️ Don't over-rotate either: **no adversary ≠ no misses**. Add a new field to
your logs (`ssn=`, `token=`) and your rules won't recognize it — straight into
the context it goes. Real systems use an **allowlist**: pass through only the
fields you explicitly recognize, drop everything else. Exercise 4 has you build
that.

---

## Step 4: change it yourself (exercises)

### Exercise 1 ⭐ Add a new kind of sensitive value

Add a log line containing a national-ID number to `RAW_LOGS`, then add a matching
rule to `REDACTION_RULES`.

**Predict**: if you run `tokenized` *before* adding the rule, how many leaks does
the program report?

### Exercise 2 ⭐⭐ Loosen the phone rule, then move it up

The phone rule today is `r"\+?\d{1,3}-\d{3}-\d{4}"`. Replace it with the version
most people write without thinking:

```python
(r"\d{3}-\d{4}", "PHONE", "phone number"),   # and move this ABOVE the CARD rule
```

Run `tokenized` and **watch the card line**.

**Predict**:
- What does the card number turn into?
- How many leaks does the program report at the end?

> This is the two most common redaction bugs at once: a regex that's too loose,
> plus the wrong order. **Match the long, specific patterns before the short,
> general ones.**

### Exercise 3 ⭐⭐ Make the placeholders unstable

Change `tokenize()` so every *occurrence* gets a fresh number (`USER_1`,
`USER_2`, … even for the same person).

**Predict**: does leakage increase? Does the task still work?

> Do this one and you'll understand exactly why "stable" is the load-bearing word.

### Exercise 4 ⭐⭐⭐ Switch from blocklist to allowlist

Right now you enumerate what's sensitive and delete it. Invert it: **keep only
fields you recognize** (`action`, `code`, timestamp, tokenized user) and drop
everything else.

**Predict**: when a new field suddenly appears in the logs, which approach is safer?

> This is what real systems do. A blocklist asks you to enumerate every risk; an
> allowlist asks you to enumerate your needs — **and needs are finite.**

### Exercise 5 ⭐⭐⭐ Let the agent request a decode

Add a `reveal(token)` tool the agent can call when it genuinely needs a real
value. Your code writes an audit line, then decides whether to answer.

**Think it through first**: does this solve the problem, or relocate it?

---

## Check your answers

After you've tried → **[SOLUTION.md](SOLUTION.md)**

Full measured output for all three modes, the comparison table, and answers to
every exercise.

---

## Appendix: concepts

### The three-way trade-off

| Approach | Leakage | Task | When to use it |
|---|---|---|---|
| `raw` | ✗ everything | ✓ works | The data genuinely isn't sensitive (public docs, OSS code) |
| `redacted` | ✓ none | ✗ impossible | The task doesn't need to tell entities apart ("how many ERRORs today") |
| `tokenized` | ✓ none | ✓ works | **Default to this** |

### One engineering principle

> **Redaction should strip *identity*, not *sameness*.**
>
> Reasoning runs on "these two are the same person", not on "this person is named X".

### What most often slips into a context by accident

Ranked by how often it actually happens:

1. **Logs** — the most common, because "just paste it in and see" is so cheap
2. **Query results** — `SELECT *` drags along the columns you forgot about
3. **Stack traces** — connection strings, tokens, and request bodies live in there
4. **Support tickets / email bodies** — users type their own ID and card numbers
5. **Config files** — "have the agent check why my .env isn't loading"

The pattern: **all of it is data you grabbed for a different purpose, not input
you deliberately prepared.**

---

## Stuck?

| What you see | What to do |
|---|---|
| `x No usable backend found` | Install any one of the three options on screen |
| `redacted` somehow named a user | Check whether it made that up — **that's a finding in itself**, see SOLUTION |
| Want the exact text the model received | Set `SHOW_PROMPT = True` |
| Forgot the commands | Run `python3 agent.py` with no arguments |
