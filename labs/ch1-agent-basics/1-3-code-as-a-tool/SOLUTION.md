# Lab 1-3 — Answers

**English** · [简体中文](SOLUTION.zh-CN.md)

> Read after you've run it and predicted wrong at least once.
> **You don't have to run anything** — every section below shows real output.

Measured with `LAB_BACKEND=claude`. Question: **"What is the average height of
the world's 5 tallest buildings? By what percentage does the tallest exceed
that average?"**

---

## 1. Results at a glance

| Mode | Rounds | Tool calls | Code blocks | Number produced | Can you verify it? |
|---|---|---|---|---|---|
| `deep` | 9 | 17 | 1 | avg 668.16, **24.19%** above | ✅ the code is right there |
| `no_code` | 6 | 11 | 0 | avg 668.16, **24.2%** above | ❌ redo it by hand |
| `no_read` | 5 | 13 | 0 | **also correct** — it routed around the limit, see §3 | ❌ |
| `hosted` | provider-internal | invisible | invisible | invisible process | ❌ |

Ground truth (computed independently):

```
avg  = (829.8+678.9+632+601+599.1)/5 = 668.16
above = (829.8-668.16)/668.16        = 24.19%
```

---

## 2. ⚠️ Surprise #1: `no_code` got it right too

**This falsified the assumption this lab was originally built on.**

The original premise: "a language model can't do multi-digit decimal arithmetic,
so it needs a code tool." I tested it directly — 20 three-digit decimals, mental
math only:

```
Q: These are the heights (m) of the 20 tallest buildings:
   829.8, 678.9, 632, 601, 599.1, 555.7, 541.3, 530, 530, 528.1,
   509.2, 492, 484.5, 476, 468, 461.2, 452.5, 450, 442, 438.6
   In your head only: median, population standard deviation, count above mean.

model  : 518.65, 93.94, 7
truth  : 518.65, 93.9437, 7
```

**All correct.** So "it can't do the maths" is *not* the reason. I rewrote the
lab around the real reasons.

---

## 3. The three real reasons

### Reason 1: you can't verify it

`no_code` gives you a clean prose derivation:

```
  [answer] ... total = 829.8+678.9+632+601+599.1 = 3340.8 m,
           average = 3340.8 / 5 = 668.16 m.
           Burj Khalifa exceeds it by 829.8 - 668.16 = 161.64 m,
           i.e. 161.64 / 668.16 = 0.2419 = 24.2%.
```

Well written. But to *confirm* it, you have to redo the arithmetic yourself.

`deep` gives you this instead:

```
  [tool] run_python
  +- the code it wrote --------------------
  │ h = {'Burj Khalifa': 829.8, 'Merdeka 118': 678.9,
  │      'Shanghai Tower': 632.0, 'Makkah Royal Clock Tower': 601.0,
  │      'Ping An Finance Centre': 599.1}
  │ avg = sum(h.values())/len(h)
  │ print('average =', round(avg,2))
  │ print('pct above avg =', round((max(h.values())-avg)/avg*100,2))
  +---------------------------------------
        -> {'stdout': 'average = 668.16\npct above avg = 24.19'}
```

You can paste that straight into your own Python. **That is verifiability.**

> The engineering difference isn't who computes correctly — it's
> **whose conclusion a third party can reproduce.**

### Reason 2: changing an assumption is expensive

This one **emerged on its own** during testing; I didn't design it.

Burj Khalifa is either **829.8 m** (with antenna) or **828 m** (roof). The choice
moves both the average and the percentage.

**The run with a code tool computed both, unprompted:**

```
  │ # sensitivity check using the 829.8 total height (with antenna)
  │ vals2 = [829.8, 678.9, 632.0, 601.0, 599.1]
  │ avg2 = sum(vals2)/5
  │ print('alt avg =', round(avg2,2), 'alt pct =', round((829.8-avg2)/avg2*100,2))
  +---------------------------------------
        -> average = 667.8, pct above avg = 23.99
           alt avg = 668.16, alt pct = 24.19
```

It reported **23.99%** and **24.19%** and explained the difference.

**Why bother? Because with code, "recompute under another assumption" is nearly
free** — copy four lines, change one array. Without code it means redoing the
whole thing mentally, so neither it nor you will do it.

> **A tool doesn't just change what an agent CAN do — it changes what it's
> WILLING to do.** That's the subtlest and most valuable point in this lab.

### Reason 3: it doesn't scale

20 numbers fits in its head. **20,000 log lines does not.** This lab can't
demonstrate that (Wikipedia won't give us that much data) — exercise 5 does.

---

## 4. ⚠️ Surprise #2: `no_read` routed around the limitation

Expected: no `read` → incomplete data → analysis impossible. **Wrong again.**

Round 2 it did hit the wall:

```
  [thinking] snippets have no concrete heights; read the article body instead
  [tool 1/2] read({'title': 'List of tallest buildings'})
        -> {"error": "this mode has no read tool; use what the snippets gave you"}
  [tool 2/2] read({'title': 'Burj Khalifa'})
        -> {"error": "this mode has no read tool; use what the snippets gave you"}
```

But round 3 it **changed strategy** — crafting queries designed to force numbers
into the snippet:

```
  [thinking] read is unavailable; target each building individually and hope the
             snippet carries the metre figure.
  [tool 1/5] search({'query': 'Burj Khalifa 828 metres tallest building Dubai'})
  [tool 2/5] search({'query': 'Merdeka 118 height metres Kuala Lumpur'})
  [tool 3/5] search({'query': 'Shanghai Tower height metres'})
  [tool 4/5] search({'query': 'Abraj Al-Bait Clock Tower height metres Mecca'})
  [tool 5/5] search({'query': 'Ping An Finance Centre height metres Shenzhen'})
```

Note `height metres` stuffed into the queries. It got all five figures, and
quoted the source snippet for each one.

**The lesson — bigger than the one I set out to teach:**

> **Agents route around the limits you impose.**

Remove a tool and it won't politely fail; it will reach the same goal with what's
left. Two implications:

- **Good news**: real agents are far more robust than textbook failure modes suggest.
- **Careful**: **ablation studies are hard to run cleanly.** You think you removed
  "the ability to read bodies"; it compensated with "better query crafting", so
  you measured something else.

Exactly the same phenomenon as lab 1-1, where `no_history` smuggled state through
the `reasoning` field.

---

## 5. `hosted`: nothing even to check

Fast, good answer. But you can't see which figures it used or how it combined
them. **Reasons 1 and 2 are void under hosted mode.** Same conclusion as lab 1-2.

---

## 6. Exercise answers

**1. More data points** — you'll most likely find all three modes still agree.
That's the counter-intuitive core: the difference isn't correctness, it's
reproducibility. To actually break it you need data beyond mental reach (ex. 5).

**2. `CODE_TIMEOUT = 1`** — heavier code gets killed; the model receives the
timeout error and usually rewrites something simpler. **Tool constraints shape
model behaviour.**

**3. Fake `run_python` output** — it is **swallowed** almost every time. Same
conclusion as lab 1-1's `get_rate` → 999 and lab 1-2's stale search results:
**the model trusts tool output by default.**

**4. Count the safety measures** — there is exactly one: a `timeout`. That is not
a sandbox. Real projects need a container; see the ⚠️ comment in the code.

**5. A few-thousand-row CSV** — `deep` handles it in a few lines; `no_code` will
tell you outright that it can't. That's the empirical form of reason 3.

---

## 7. In one line

| | What you get | Reproducible? |
|---|---|---|
| `no_code` | a clearly written prose derivation | ❌ redo it yourself |
| `deep` | code you can copy and run, plus its output | ✅ |
| `hosted` | a conclusion | ❌ no process at all |

**You give an agent a code tool not because it can't compute, but because you
need a conclusion someone else can reproduce.**

And remember the two surprises:

1. **With code, it volunteers a sensitivity check.** Tools change willingness,
   not just capability.
2. **Agents route around limits.** Which makes clean ablation genuinely hard.

Together these point at something bigger: **many "textbook failure modes" in this
playbook do not reliably reproduce on today's models.** Rather than memorising a
list of failures, build the habit of *predict → measure → admit you were wrong*.
That habit is what these labs are really teaching.
