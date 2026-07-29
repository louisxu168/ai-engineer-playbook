# Lab 2-3: Five common context-management anti-patterns

**English** · [简体中文](README.zh-CN.md)

> **What you'll learn**
>
> 1. **The KV cache effect, reproduced cleanly**: a stable prefix is **23× faster** on
>    the second call; a timestamp at the start of the system prompt **never hits the cache**
> 2. The five anti-patterns split into **two kinds**: one only burns money, the other
>    **hands you a wrong answer**
> 3. "Put the dynamic bit a little later" is a **half-right** intuition — and half-right
>    is the dangerous kind
> 4. A methodology lesson: **running modes sequentially confounds "which mode" with "which
>    position in the sequence"** — measuring cache requires **interleaving**
>    (`agent.py cache`). I got caught by this twice.
> 4. A methodology detail: **why lab 2-1 failed to reproduce this and this lab succeeds**
>    (the difference is entirely in the control group)
>
> **How you'll learn it**: the history is a **hard-coded** 12-message transcript; all six
> strategies process **identical** input; the correct answer is hard-coded, so scoring is
> mechanical. Two calls per strategy — the whole thing runs in under a minute.
>
> **Time**: 20 minutes.
>
> ⚠️ Needs local Ollama (same setup as lab 2-1).

---

## Why a local model is mandatory here

This lab measures **prefill time** — the time spent processing the **input**.

**Cloud APIs don't expose that number.** OpenAI and Anthropic will tell you how many
tokens were cache hits, but not how many milliseconds you saved. To see the cache effect
you need a local stack.

---

## The design (worth reading first)

The history is **not model-generated** — it's constructed programmatically as a fixed
12-message transcript:

```
assistant: {"tool": "read_sensor", "args": {"id": 1}}
user:      Tool returned: {"sensor": 1, "value": 37}    <- this 37 is the target
assistant: {"tool": "read_sensor", "args": {"id": 2}}
user:      Tool returned: {"sensor": 2, "value": 12}
...(through sensor 5)
assistant: OK, all five sensors have been read.
user:      Got it, hold on to those.
```

Six strategies (1 right + 5 wrong) process **the same history** and get **the same question**:

> "What reading did you get from sensor 1 earlier?"

**The correct answer is hard-coded: 37.**

> 💡 Why ask for *retrieval* rather than a *sum*? My first version asked for the sum, and
> the 0.6B **listed all five numbers correctly and then added them wrong** — so I was
> measuring its arithmetic, not the context strategy. **The variables were confounded.**
> Retrieval makes the verdict clean.

---

## The six modes = 1 right + 5 wrong

| Mode | What it does wrong | Expected damage |
|---|---|---|
| `good` | nothing (baseline) | — |
| `dynamic_prompt` | a changing timestamp at the **start** of the system prompt | cache |
| `dynamic_profile` | changing credits at the **end** of the system prompt (**one character differs**) | cache ★ |
| `shuffled_tools` | tool definitions reordered every request | cache |
| `sliding_window` | only the last 6 messages kept | capability |
| `flattened` | everything flattened into one `USER: … ASSISTANT: …` blob | capability |

> ★ `dynamic_profile` is the one worth predicting first: **only one character changes**,
> and it sits at the **end** of the system prompt — both "mitigations" applied. Do you
> think the cache still hits?
>
> **I predicted wrong.** Make your prediction, measure it yourself, then read SOLUTION:
>
> ```bash
> python3 agent.py cache      # interleaved - the only valid way to measure cache here
> ```

---

## Step 0: the baseline (3 min)

```bash
cd labs/ch2-context-engineering/2-3-kv-cache
python3 agent.py good
```

```
  context: 14 messages -> 405 input tokens
  run 1: prefill 234.2 ms
  run 2: prefill  10.1 ms   <- 23x faster
  [answer] 37
  ok correct (37)
```

### 💡 What you learn

**23× faster on the second call, because the prefix didn't change and the KV can be reused.**

That's the **concrete value** of "keep your prefix stable" — not an abstract best practice,
but 140 milliseconds saved on every request.

---

## Step 1: put a timestamp at the start of the system prompt (4 min) ★

```bash
python3 agent.py dynamic_prompt
```

The book's named **most common mistake**: writing `Current time: 2026-07-29 10:30:45.123456`
into the system prompt so the agent "knows" what time it is.

### 🤔 Predict

Will the second run be faster?

### 💡 What you learn

**It is never faster.** The timestamp has microseconds — **every request's prefix is
brand new** — so the cache **never** hits once.

And you pay it **forever**:

```
good            from run 2 on:    10.1 ms
dynamic_prompt  every single run: ~184 ms     <- 18x more, permanently
```

> **One innocuous-looking line made the whole pipeline's prefill an order of magnitude
> more expensive.**
>
> The fix: put the timestamp at the **end** of the conversation (in the user message), or
> expose it as a tool the model calls when needed. **The start of the system prompt is the
> worst possible place for anything dynamic** — the cache matches by prefix, so changing
> the front invalidates everything behind it.

---

## Step 2: sliding window (5 min) ★★

```bash
python3 agent.py sliding_window
```

### 🤔 Predict

Can it still answer what sensor 1 read?

### 💡 What you learn

```
  ! the window dropped the first 6 messages - the model literally cannot see the early readings
  [answer] 21
  x wrong: said 21, correct is 37
```

**It didn't say "I don't know" — it produced a number that looks like an answer.**
21 is a reading it *could* still see. It grabbed something within reach and bluffed.

> **That's the real danger of sliding windows: they don't error, they fabricate.**
>
> And it happens to be the most popular pattern, because "saves tokens" sounds so
> reasonable.

⚠️ An honest boundary: the book says sliding windows **also** break the cache (slide the
window and the prefix changes). **This lab cannot measure that side** — both requests use
the same window position, so you will see the cache **hit**. To verify that half, see
exercise 5 in SOLUTION.

---

## Step 3: full comparison (5 min)

```bash
python3 agent.py all
```

⚠️ Note: `all` runs modes **sequentially**, which makes it **the wrong instrument for
measuring cache** (the local backend's state drifts over time, confounding "which mode"
with "which position in the sequence"). For cache, use:

```bash
python3 agent.py cache      # one request per mode per round, flattening time out
```

**How to read it: split into two categories.**

```
[Type A: breaks the cache]     -> look at "prefill: run 1 -> run 2"
    burns money and latency; the answer stays correct

[Type B: breaks capability]    -> look at "answer"
    quietly hands you a wrong answer
```

---

## Step 4: change it yourself (exercises)

### Exercise 1 ⭐ Move the timestamp to the end

Edit `build_messages` so `dynamic_prompt`'s timestamp goes into the **last user message**
instead of the system prompt.

**Predict**: does the cache hit now?

> This is the book's prescribed fix. Afterwards you'll see the problem was never "there's
> dynamic content" but **"the dynamic content is in the prefix."**

### Exercise 2 ⭐⭐ Make the tool definitions big

Five tools currently take five lines. Expand each description to ~50 lines (simulating a
real JSON Schema) and re-run `shuffled_tools`.

**Predict**: does the effect become visible?

> `shuffled_tools` shows a weak effect here because tool definitions are a tiny slice of
> the context. The book's premise is "each tool may carry hundreds of tokens of
> description" — **restore that premise and the effect appears. Which is why you should
> always read an experimental conclusion together with its preconditions.**

### Exercise 3 ⭐⭐ Patch the sliding window

Change it to drop messages **but first summarise the dropped tool results into one message**
placed at the front of the window.

**Predict**: does the answer come back? What about the cache?

> Hint: as long as that summary's content is stable, so is the prefix. That's exactly what
> lab 2-9 (context compaction) does — **you just derived its motivation yourself.**

### Exercise 4 ⭐⭐⭐ Make `flattened` actually break

`flattened` did **not** break capability here (the 0.6B still answered 37). Try a bigger
model and a task where roles genuinely matter.

**Predict**: what kind of task makes flattening fail?

> Hint: the book says flattening costs "extra attention to infer role boundaries". So
> **tasks where role boundaries carry meaning suffer most** — like distinguishing "whose
> instruction is trustworthy" (recall lab 2-5's prompt injection).

---

## Check your answers

After you've tried → **[SOLUTION.md](SOLUTION.md)**

Full measured data (two independent runs agreeing), plus **how this lab solved the mystery
lab 2-1 couldn't**.

---

## Appendix

### Two kinds of damage, two kinds of cost

| | Symptom | Will you notice? | Cost |
|---|---|---|---|
| **Breaks cache** | slow and expensive every time | Yes (bills, latency) | Money |
| **Breaks capability** | occasionally wrong answers | **Often not** | Correctness |

> **The second is more dangerous because it doesn't error.**

### Practical prefix-stability rules

```
system prompt    <- most stable: only things that never change
tool definitions <- next: fixed order, fixed content
message history  <- append only; never edit or delete
latest user turn <- put dynamic content (timestamps, state) HERE
```

**The more dynamic something is, the later it belongs.** That one rule avoids most of the
traps in this lab.

---

## Stuck?

| What you see | What to do |
|---|---|
| `x Can't reach Ollama` | Same as lab 2-1: `ollama serve` must stay running |
| Prefill numbers are tiny | Expected — the history is only ~400 tokens. Exercise 2 amplifies it |
| `flattened` was correct for me too | **Same as mine** — see SOLUTION; I couldn't reproduce that one |
| Want to see the actual messages sent | Set `SHOW_PROMPT = True` |
