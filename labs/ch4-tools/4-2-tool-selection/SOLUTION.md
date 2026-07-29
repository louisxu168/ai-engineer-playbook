# Lab 4-2 answers: too many tools

**English** · [简体中文](SOLUTION.zh-CN.md)

> ⚠️ Try it first. Being wrong once beats reading this ten times.

---

## 1. Accuracy: 15/15 correct — the folklore didn't reproduce

Backend: Claude Code (`claude -p`), measured 2026-07-28.

Three plain examples across all four modes (12 runs) plus three trap examples under
`confusable` (3 runs) = **15 scored decisions, all correct.**

The three plain examples in full:

| Mode | Tools | Prompt | Ex 1 | Ex 2 | Ex 3 |
|---|---|---|---|---|---|
| `few` | 8 | ~331 chars | ✓ | ✓ | ✓ |
| `many` | 35 | ~1077 chars | ✓ | ✓ | ✓ |
| `confusable` | 40 | **1249 chars** | ✓ | ✓ | ✓ |
| `retrieved` | 8 | ~355 chars | ✓ | ✓ | ✓ |

**"Models get confused past 20 tools" did not reproduce at this scale.**

And not narrowly. Here's the reasoning on trap example 5 under `confusable`
(all 40 tools present):

> **[reason]** Alice has no phone for SMS and no mobile app for push
> notifications, so email is the only way to notify her that the refund landed.

The request was: *"Customer alice left no phone number and doesn't have our app.
Her refund has landed — let her know."*

**The word "email" never appears in the request.** It got there by elimination:
no phone → SMS out; no app → push out; the only remaining customer-reaching channel
is email.

The three traps:

| # | The bait | It chose | Right? |
|---|---|---|---|
| 4 | "email" and "text" both present, but an internal note is wanted | `add_ticket_comment` | ✓ |
| 5 | No channel named; requires elimination | `email_customer` | ✓ |
| 6 | "customer's texts" up front, but the recipient is a colleague | `send_internal_email` | ✓ |

> **I failed to fool it.** That's this lab's first finding — and it's a *negative*
> result, precisely the kind that most often goes unrecorded and most deserves to be.

---

## 2. So where's the cost? In prompt length

Accuracy is flat across modes, but:

```
few         8 tools     331 chars
many       35 tools    1077 chars
confusable 40 tools    1249 chars   <- 918 more than few
retrieved   8 tools     355 chars   <- 72% cut, no accuracy loss
```

**The important part is how that bill is paid:**

The tool table lives in the **system prompt**, and **every turn of the agent loop
re-sends the whole context** (lab 1-1: the endpoint is stateless). So:

```
a task that runs 10 rounds
  x 918 characters of unused tool descriptions
  = you paid for 32 irrelevant tools, ten times over
```

> **State the conclusion backwards from the folklore:**
>
> The reason to retrieve tools is **not** "the model can't cope" — it copes fine.
> It's **"you are repeatedly paying for things you never use."**
>
> Those sound similar and imply completely different priorities:
> - A **capability** problem → you must fix it, or the feature is broken
> - A **cost** problem → you do the arithmetic, and you weigh the new risk it adds

That new risk is next.

---

## 3. `retrieved`'s failure: off by one place

The most valuable part of this lab.

Example 5 (English corpus): `Customer alice left no phone number and doesn't have
our app. Her refund has landed - let her know.`

BM25's ranking over all 40 tools:

```
    1. send_sms
    2. push_notification
    3. issue_refund
    4. get_refund_rate
    5. get_product
    6. cancel_order
    7. block_customer
    8. update_customer
  ------------------- RETRIEVE_K = 8 cuts here
    9. email_customer      <- the correct tool, one place short
   10. get_customer
```

**The right answer ranked 9th. The cutoff is 8.**

So:

| Mode | Result |
|---|---|
| `confusable` (all 40) | **✓ correct** — "SMS and push are both unusable, so email" |
| `retrieved` (BM25 top-8) | **✗ wrong** |

And the model's behaviour under `retrieved` is worth quoting verbatim:

> **[reason]** With no phone number and no mobile app, SMS and push are both
> unusable, so the only remaining way to reach alice about her landed refund is via
> her profile contact channel — **but among the listed tools none actually sends an
> email** … therefore no tool fits.
>
> **[chose] none**

**Once again the model did the right thing**: it correctly deduced that email was
needed, found no email tool in its list, and **refused to force a wrong pick**.

> Same shape as `both_bad` in lab 4-1:
> **the model's judgement was sound; what we handed it was not.**

### Why BM25 can't find it

Request words: `phone number`, `app`, `refund`, `let her know`
Tool description: `email_customer - Send an email to a customer`

**Not one content word in common.**

Meanwhile `send_sms`'s description contains `phone` and `push_notification`'s
contains `app` — so **the two tools the request explicitly rules out ranked 1st and
2nd.**

> **This is keyword retrieval's nastiest failure mode:**
> the request mentions something **in order to negate it** ("no phone number"), and
> BM25 only sees that the word "phone" occurred, so it *boosts* `send_sms`.
>
> **BM25 doesn't understand negation.** It has no concept of "not".

Same wall as lab 3-2, hit from a different direction.

### English vs Chinese — the detail that should worry you most

Same task: in the Chinese corpus `email_customer` ranks **8th**, **scrapes in**, and
`retrieved` succeeds.

```
Chinese:  ... 7. block_customer    8. email_customer   <- 8th, made it
English:  ... 8. update_customer   9. email_customer   <- 9th, cut
```

**Same task, same logic, same K — swap the language and success becomes failure.**

> This doesn't mean "Chinese is better". It means:
> **your retrieval pipeline may be standing right at the cliff edge and you can't
> tell.**
>
> There is no meaningful difference between ranking 8th and 9th — it just happened
> to land on one side of the cutoff. A rephrasing, one more tool, one edited
> description could push it over.
>
> **A retrieval pipeline that "passes its tests" and one that "barely didn't fall
> off" look identical in the test report.**

---

## 4. So should you retrieve tools or not?

Both bills side by side:

| | Paste everything | Retrieve first |
|---|---|---|
| Prompt | 1249 chars | 355 chars (**72% saved**) |
| Recall | **always 100%** | **a variable** (measured failing here) |
| What failure looks like | — | the model can only say "no suitable tool" |
| Will you notice? | — | **hard** — production has no ground truth |

> **In one line: you're trading a certain cost for an uncertain success rate.**

When the trade is worth it:

- ✅ You have **hundreds** of tools and everything genuinely doesn't fit — no choice
- ✅ Queries and tool descriptions **share vocabulary** (tools named the way users talk)
- ✅ You can **tolerate occasional failure** (picking wrong is cheap and retryable)

When it isn't:

- ❌ You have tens of tools and they fit — **don't buy a new failure mode to save money**
- ❌ Picking wrong is expensive (payments, deletions, outbound email)
- ❌ Users' vocabulary differs from your tools' (exactly this lab's case)

**And if you must retrieve, pair it with an always-include list** (exercise 3):
unconditionally add the group of tools that are **mutually substitutable and
expensive to confuse**. Same principle as labs 2-3 and 3-2:

> **Don't put critical things behind a recall metric.**

---

## 5. Exercise answers

### Exercise 1 ⭐⭐ Write a trap that actually works

None of my three landed. If yours does, write it down — it's worth more than this page.

Directions I tried that failed, so you don't repeat them:

| Approach | Outcome |
|---|---|
| Pile on misleading keywords (ex. 4, 6) | Failed — it reads **intent**, not keywords |
| Name no channel, force reasoning (ex. 5) | Failed — its elimination is clean |
| Make two tools genuinely both defensible | **This direction works**, but then there's no unique ground truth |

That last row is really a **methodology** problem:

> **Once a question is genuinely ambiguous, "picking wrong" stops being the model's
> problem and becomes your ground truth's problem.**
>
> So "tool selection accuracy" has a built-in ceiling as a metric: **it can only
> measure cases that have a unique right answer.** Large parts of real tool
> selection have several defensible answers — and this method can't evaluate those
> at all.

### Exercise 2 ⭐ Raise `RETRIEVE_K`

For the failing English example the right answer ranks 9th, so **`RETRIEVE_K = 9`
recovers it.**

But answer the second question honestly: **how would you have known to use 9?**

**You knew because you could see the ground truth.** In production there is none —
you'd just see the agent say "no suitable tool" and conclude the model is weak.

> And raising K has a price: at K=20 the prompt grows back and you've handed back
> the savings that motivated retrieval in the first place.
>
> **K is fundamentally a line drawn between "how much you save" and "how much you
> miss". Where that line belongs depends on your data — there is no universally
> good value.**

### Exercise 3 ⭐⭐ Retrieve + always-include

Reference implementation (the retrieved branch of `pick_tools()`):

```python
documents = [name + " " + desc for name, desc in catalog]
ranked = bm25_rank(task_text, documents)[:RETRIEVE_K]
kept = [catalog[i] for i in ranked]

# * always-include: mutually substitutable and expensive to confuse
by_name = dict(catalog)
for name in CONFUSABLE_NAMES:
    if name in by_name and all(n != name for n, _ in kept):
        kept.append((name, by_name[name]))
```

Effect:

- The failing example **recovers** (`email_customer` is present unconditionally)
- The prompt grows from ~355 to roughly 500 chars — **still less than half of 1249**

> **This is what real systems look like: not "retrieve" vs "paste everything", but
> "retrieve for the bulk of the savings, and unconditionally include the few that
> matter".**
>
> How do you pick what to always-include? Two conditions together:
> 1. It is **mutually substitutable** with other tools (so retrieval easily picks wrong)
> 2. **Picking wrong is expensive** (so you can't gamble)

### Exercise 4 ⭐⭐⭐ Improve the descriptions, then retrieve

Measured (English corpus, the failing example):

| Description | rank of `email_customer` | inside K=8? |
|---|---|---|
| As shipped: `Send an email to a customer` | **9** | ✗ |
| Plus synonyms: `(contact customer, email notification, reach the customer)` | **7** | **✓ recovered** |
| Plus `no phone, no app` as well | **1** | ✓ |

**Synonyms alone are enough.** 9 → 7, across the cutoff.

But be wary of that last row: reaching 1st place required me to **already know how
the question would be phrased**.

> **That's document expansion's built-in limitation** (also noted in lab 3-2,
> exercise 3): **you have to guess, at write time, how it will later be queried.**
> Guess right and it's dramatic; guess wrong and you wrote nothing.

Still, this technique has an advantage the others don't:

> **It improves two stages at once** — retrieval can now find it, **and the model
> can distinguish it better.**
>
> A good tool description pays off both in "getting retrieved" and in "getting
> picked". An extension of lab 4-1's conclusion: **tool descriptions have an absurd
> return on investment.**

### Exercise 5 ⭐⭐⭐ Two-stage selection

Savings land in the same ballpark as `retrieved` (send 6 category names first, then
only that category's tools).

**The new failure mode: there are now two chances to pick wrong, and getting the
first wrong leaves no second chance.**

Concretely: if stage one classifies "notify the customer their refund landed" as
*payments* rather than *messaging*, then `email_customer` isn't even on the stage-two
menu. Dead end.

> **Same class as retrieval's failure**: **an early, irreversible filter.**
>
> Classification, retrieval, routing, top-K truncation — different names, same
> shape: **making the least reversible decision at the moment you have the least
> information.**
>
> The general mitigations are few:
> 1. Make the filter **reversible** (let it say "start over")
> 2. **Always-include** the critical items (exercise 3)
> 3. **Keep more** (raise K, pick two categories) — trade cost for tolerance

---

## 6. What this lab is really for

Not "should you retrieve tools", but:

> **A widely repeated rule of thumb ("things break past 20 tools") did not
> reproduce in the scenario I measured.**

That doesn't mean it's never true — it may hold for weaker models, for far more
tools, for worse descriptions. But it is **not a law you can apply to an
architecture decision without checking.**

**And checking it cost me one afternoon.**

> That's now the 6th time an expectation has failed in this repo (1-1's
> `no_history`, 1-3's `no_code` and `no_read`, 2-1's `truncate`, 3-1's
> `naive_extract`, and this one).
>
> **Building the predict → measure → admit-you-were-wrong habit matters more than
> any conclusion on this page.**
>
> Especially in this field: **models turn over every few months, and blog posts
> don't get updated.**

---

← [back to the chapter](../README.md) · [back to the index](../../../README.md)
