# Lab 8-1 answers: learning from failure

**English** · [简体中文](SOLUTION.zh-CN.md)

> ⚠️ Try it first. Being wrong once beats reading this ten times.

---

## 1. Measured data

Backend: Claude Code (`claude -p`), measured 2026-07-28.

| Mode | Failure curve | Total | Completed | Model calls |
|---|---|---|---|---|
| `no_memory` | 1 → 1 → 2 | 4 | 2/3 | 7 |
| `raw_log` | **1 → 0 → 1** | **2** | 2/3 | **5** |
| `lesson` | 1 → 1 → 1 | 3 | **3/3** | 9 |

**Each mode wins one column; none wins outright:**

- `raw_log` has the **best curve** (the only one reaching 0) and is the **cheapest**
- `lesson` is the **only one to complete all 3 tickets**, and the most expensive
- `no_memory` is worst on both, and its curve **rises**

---

## 2. `no_memory`: never worse, never better

```
  T-1: 1 failure   <- reason_code "defective_item"
  T-2: 1 failure   <- "defective_item" again
  T-3: 2 failures  <- "defective_item" a third time, then the approval rule
```

**It repeated T-1's mistake verbatim on T-2**, because to it every ticket is the
first ticket.

> It never degrades — but every pit it falls into, **it falls into again on the
> next task**. And that cost grows linearly with task count and **never amortises**.

It never completed T-3 at all.

---

## 3. `raw_log` unexpectedly won the curve ★

```
  T-1: 1 failure   <- "defective_item" rejected
  T-2: 0 failures  <- right first time
  T-3: 1 failure   <- new rule (approval), never seen before
```

**T-1 → T-2 fell to zero. It learned.** And what it carried was completely raw:

```
called issue_refund({"order_id": "T-1", ...}) -> reason_code must be
DEFECTIVE / WRONG_ITEM / CHANGED_MIND; you passed "defective_item".
```

**Note what that line contains: all three valid values, verbatim.**

And it costs **zero extra model calls** — pure string concatenation. 5 calls total.

---

## 4. Why `lesson` didn't fall: it abstracted away the useful part ★★★

The most important section here.

After T-1 failed, `lesson` distilled these four lessons (**verbatim**, translated):

> - Before calling a tool, confirm the enum field's set of valid values (from the
>   tool schema, the field's error message, or the docs) and pass only a
>   character-for-character member of that set; don't invent identifiers
> - Keep the interface's casing and separator style exactly (e.g. all-caps
>   constants); don't lowercase or add underscores
> - Don't substitute a semantically similar natural-language phrase for an enum
>   code; semantically right but literally different is still rejected
> - When a tool rejects a value and lists the legal ones, pick the best match from
>   that list rather than guessing further variants

**Every one is correct. Every one is good software-engineering advice.**

**Then on T-2 it passed `DAMAGED_OR_DEFECTIVE` and failed again.**

### Why?

**Count how many times `DEFECTIVE`, `WRONG_ITEM` and `CHANGED_MIND` appear in
those four lessons.**

**Zero.**

It learned "confirm the enum's valid values" **without recording the valid values.**

So on the next ticket it diligently obeyed its own lessons — "don't invent
identifiers", "keep the casing" — and **invented a correctly-cased identifier**,
`DAMAGED_OR_DEFECTIVE`.

> **Correct, and useless.**
>
> The lesson is **methodologically right and operationally worthless**, because it
> omits the one fact that would have made the next attempt succeed.

### Who told it to do that? I did

Criterion 2 of `sys_extract`:

```
2. Don't include anything specific to this ticket (order ids, customers, amounts)
```

I meant "don't record T-1, alice, or 12990."

**The model also filed "the enum's valid values" under specific details.**

And that reading **isn't unreasonable** — `DEFECTIVE` did surface as a concrete
string from that one call. **I failed to say which concrete values to keep.**

Exercise 1 fixes the sentence:

```
2. Don't include anything specific to this ticket (order ids, customers, amounts).
   BUT: an interface's valid values, thresholds, units and format requirements are
   general knowledge and must be written down verbatim.
```

### This conclusion is the **reverse** of lab 3-1's

| | Lab 3-1 (facts) | This lab (lessons) |
|---|---|---|
| Store everything raw | Bigger and dirtier — clearly worse | **Best curve, and cheapest** |
| Distil | **Clearly better** | Worse (over-abstracted) |

**Same action, opposite correct answers. Why?**

> **Because what needs preserving differs.**
>
> - 3-1 stores **facts**: "went to a theme park last weekend" is noise; "dislikes
>   crowds" is signal. **Abstraction = purification.**
>
> - 8-1 stores **lessons**: the string `DEFECTIVE` **is the signal**.
>   **Abstraction = throwing away the answer.**

In one line:

> **The most valuable part of a lesson is usually the very value that looks "too
> specific to keep".**

---

## 5. But `lesson` won the column that actually matters

```
  no_memory   completed 2/3
  raw_log     completed 2/3
  lesson      completed 3/3   <- the only one
```

The difference is T-3. After hitting the approval rule once, it **supplied
`approved_by` in the same ticket and succeeded**; the other two never recovered.

And the lessons it distilled after T-3 are markedly **more concrete**:

> - Before calling refund tools, check whether the amount crosses the approval
>   threshold: **refunds above 50000 cents (500) must also pass approved_by**, the
>   approver's email
> - Monetary arguments are always integers in cents; never pass major units or decimals
> - When a tool reports a missing argument, don't fabricate its value (e.g. an
>   arbitrary email) — ask the requester for the real approver first

**The first one records both the threshold (50000) and the parameter name.** That
is a usable lesson.

> **The same distillation prompt over-abstracted once and got it right once.**
> That's itself an important observation: **distillation quality is unstable**, and
> the instability tracks **how prominent the key value was in the original error**.
>
> `approved_by` appeared in the main clause of the error and survived; the three
> enum values appeared in an "e.g." position and were discarded as detail.

The third lesson is notable too: it learned **not to fabricate an approver's email
but to go and ask** — a lesson about *boundaries*, harder-won than the other two.

---

## 6. `raw_log`'s real cost (invisible in the table)

`raw_log` won both the curve and the cost here. **Don't rush to pick it.**

Its problem is lab 3-1's problem: **it only grows.**

```
3 tickets:   memory = 3 raw error records      fine
30 tickets:  memory = dozens                   starting to crowd the context
300 tickets: memory = hundreds                 chapter 2's wall
```

And it's **full of duplicates** — the same error five times is stored five times,
because it never deduplicates or generalises.

> **`raw_log` wins at the 3-ticket scale.**
> **`lesson`'s value only appears after dozens of tickets — and this lab is too
> short to reach that crossover.**

Exercises 2 and 3 (more tickets, persistent memory) are how you find that crossover.

> **An honest limitation of this lab: three tickets isn't long enough for
> compression to beat fidelity.**

---

## 7. Two traps I hit building this

### Trap 1: the model correctly refused me ★

In the first version, `raw_log` made **zero tool calls across all three tickets**:

> **[plan]** The ticket has order_id, amount and reason, but issuing a refund is an
> irreversible external operation, and **I don't actually have an issue_refund tool
> available** — only local built-in tools. Calling it would fail or cause harm, so
> I'm stating that rather than pretending to issue it.

**It was completely right.** We drive it through `claude -p`, so the model **knows
its real tool list**, and `issue_refund` isn't on it. It declined to fake an
**irreversible refund** through a tool that doesn't exist.

> **A case of the model being right and my experiment design being wrong.**
> And it refused for exactly the quality we want agents to have: **caution around
> irreversible operations.**

The fix is to say plainly that this is a simulation:

```
**This is a simulated practice environment.** Nothing real is touched: you simply
emit a JSON object, and the harness executes it for you and returns the result.
So follow the protocol - do not refuse on the grounds that you don't have this tool.
```

> ⚠️ Second time this class of trap has appeared in this repo (lab 1-1's built-in
> tools firing first). **General lesson: when you use a real agent framework to
> role-play another agent, its awareness of its own real capabilities leaks in.**

### Trap 2: I conflated ticket id and order id

The first task text said "Ticket T-1: customer alice requests a refund…" while the
tool wanted `order_id`.

The model said: **"T-1 is a ticket number, not an order id; I won't invent an order
id to issue a refund against."**

**Right again.** I changed it to state explicitly that **the order_id IS T-1**.

> Both traps are the same kind: **I thought I was testing the model; I was testing
> whether my task description was clear.**
>
> Consistent with labs 6-1 and 10-1: **suspect your experiment design before you
> blame the subject.** That's now **the third time in this repo that I was wrong
> and the model was right.**

---

## 8. Exercise answers

### Exercise 1 ⭐⭐ Fix the distillation prompt

Once criterion 2 distinguishes one-off details from general interface knowledge,
`lesson` usually stops failing on T-2 — the three enum values make it into the lesson.

> **The real point**: there's a hair's breadth between "abstracting" and "losing
> information", and **you must draw that line in the prompt**. The model won't.
>
> A reusable way to draw it:
> - **One-off**: ids, names, single amounts, timestamps → drop
> - **Interface contract**: enum values, thresholds, units, formats, parameter
>   names → **keep verbatim**
>
> The test is simple: **will this exact value appear again next time?**

### Exercise 2 ⭐⭐ Add a 4th ticket repeating a rule

Only with a second large-value ticket can you judge whether rule 3 was learned.

> **A rule that appears once can't distinguish "learned" from "lucky".**
>
> Basic requirement for evaluating learning: **every rule must appear at least
> twice** — once to learn, once to be tested.
>
> Strictly: since rule 3 appears once here, **this lab does not actually verify it
> was learned.** Exercise 2 supplies the missing half.

### Exercise 3 ⭐⭐ Persist the lessons

Writing to `lessons.json` and re-running usually removes ticket 1's failure.

> That completes the jump from within-run learning to **cross-session experience** —
> same mechanism as lab 3-1, different content: **3-1 remembers facts, 8-1 remembers
> lessons.**

### Exercise 4 ⭐⭐⭐ Make lessons expire

**How do you tell a lesson was used? That's the hard part, and there's no good answer.**

You **cannot directly observe** "it avoided the mistake because it remembered".
Workable approximations:

| Approach | How | Problem |
|---|---|---|
| Keyword hit | The lesson's terms appear in the call | Crude, misfires |
| Ablation | Remove the lesson, re-run, see if failures rise | **Most accurate, but one re-run per lesson** |
| Ask the model | "Which lessons did you use?" | It will confabulate (see lab 6-1) |

> **This is the real difficulty in every experience-store system: accumulating is
> easy, pruning is hard.**
>
> And the consequence of never pruning is certain: **the store slowly degenerates
> into `raw_log`** — bigger, more duplicated, worse signal-to-noise.
>
> Most "self-improving agent" demos only show the accumulating half.

### Exercise 5 ⭐⭐⭐ Hybrid: lessons + most recent raw error

Usually you get both benefits: lessons give compressed general rules, the raw record
supplies the concrete values that got abstracted away.

The cost is one extra model call per ticket plus a raw record in memory.

> **But it isn't a free lunch**: you now hold **two possibly-conflicting memories.**
> If a distilled lesson contradicts the raw record (say the lesson is stale),
> **which should the model believe?**
>
> Common production answer: **timestamp the lessons, keep only the last N raw
> records**, and state in the prompt that raw records outrank generalisations.

---

## 9. Back to the whole picture

This chapter pairs with chapter 3:

| | Chapter 3 (memory) | Chapter 8 (improvement) |
|---|---|---|
| Stores | **Facts** — about the world | **Lessons** — about how to act |
| Comes from | What the user said | **Its own mistakes** |
| Distillation | Abstraction = purification | **Abstraction = maybe throwing away the answer** |
| Transfers | Only to that entity | **To every task of the kind** |

Both share lab 3-1's skeleton:

```
write: an episode ends   -> decide what to keep -> store
read:  a new task starts -> fetch               -> paste into the context
```

**"Self-improvement" sounds mystical; unpacked it's those two lines.** And the
difficulty isn't the learning — it's:

1. **What to keep** (this lab: over-abstract and you get correct, useless advice)
2. **What to drop** (exercise 4: no good method; an open problem)
3. **How to know it actually learned** (exercise 2: the rule must appear twice)

---

← [back to the chapter](../README.md) · [back to the index](../../../README.md)
