# Lab 4-2: Too many tools — a folklore that didn't reproduce, and a real bill

**English** · [简体中文](README.zh-CN.md)

> **What you'll learn**
>
> 1. "Models get confused past ~20 tools" **did not reproduce** here (15/15 correct)
> 2. What tools-at-scale actually costs isn't accuracy, it's **prompt length**:
>    331 → 1249 chars, re-paid on every call
> 3. So the reason to retrieve tools is **cost**, not "the model can't cope"
> 4. And retrieval **isn't free** — it adds a failure mode that "paste everything"
>    doesn't have, and this lab measures it firing
>
> **How you'll learn it**: the verdict is mechanical — each example has one correct
> tool name, compared as a string.
>
> **Time**: 20 minutes (no network).

---

## Where this lab came from

I built it to reproduce a popular claim:

> "Once you pass 20 tools, models start picking the wrong one."

I set it up properly: 40 tools, 6 of which are **near-identical** — all of them
"send a message to someone", differing only in recipient and channel:

```
email_customer        Send an email to a customer
send_internal_email   Send an email to a colleague inside the company
send_sms              Send a text message to a customer's phone
push_notification     Push a notification to a customer's mobile app
send_slack_message    Post a message in the company Slack
add_ticket_comment    Append an internal note to a ticket (not customer-visible)
```

I also wrote three **trap questions** with deliberately misleading keywords.

**Result: 15 out of 15 correct. It was never fooled once.**

So this lab doesn't teach what I expected. It teaches two more useful things:

1. **The folklore didn't reproduce on a current model** — don't make architecture
   decisions from stale received wisdom
2. **The cost is real, but it isn't accuracy** — it's the 900 extra characters you
   re-pay on every single call

> Which is itself a methodology demo: **predict → measure → admit you were wrong.**
> That's now happened 6 times in this repo (see 1-1, 1-3, 2-1, 3-1).

---

## Step 0: run it and look at the accuracy column (5 min)

```bash
cd labs/ch4-tools/4-2-tool-selection
python3 agent.py all
```

Press Enter for examples, then type `1`.

### 🤔 Predict

`confusable` hands it 40 tools, 6 of which all "send a message". Will it pick wrong?

### 👀 What you'll see

```
mode: few          tools: 8     prompt: 331 chars     result: ok correct
mode: many         tools: 35    prompt: 1077 chars    result: ok correct
mode: confusable   tools: 40    prompt: 1249 chars    result: ok correct
mode: retrieved    tools: 8     prompt: 358 chars     result: ok correct
```

### 💡 What you learn

**All four correct.** So which column actually differs?

**Prompt length. 331 → 1249. 3.8×.**

> Those 900 characters aren't a one-off. **Every turn of the agent loop re-sends
> the entire tool table.** On a 10-round task you paid for those 32 unused tools
> ten times.

---

## Step 1: try to fool it (6 min)

Examples 4–6 are traps I built on purpose:

| # | Request | The bait | Correct |
|---|---|---|---|
| 4 | A customer **emailed** to complain our **text messages** never arrive. Record where we've got to — internal eyes only. | both "email" and "text" appear | `add_ticket_comment` |
| 5 | Customer alice left no **phone number** and doesn't have our **app**. Her refund landed — let her know. | no channel named; needs elimination | `email_customer` |
| 6 | This customer's **texts** keep failing. Wang doesn't read Slack, so **email** him about it. | "customer's texts", "email" | `send_internal_email` |

```bash
python3 agent.py confusable      # then type 5
```

### 👀 What to watch

**Don't just check right/wrong — read the `[reason]` line.**

Example 5 especially: the request **never contains the word "email"**. So how did
it get there?

### 💡 What you learn

By **elimination**: no phone → SMS is out; no app → push is out; the only channel
left that reaches a customer is email.

> **That's pure semantic reasoning, not keyword matching.** Hold onto that — the
> next step depends on it.

---

## Step 2: attack the retrieval (8 min) ★ the most important step

`retrieved` looks like a free win: accuracy unchanged, prompt cut by 72%.

**But it has a failure mode none of the other modes have.**

### 🤔 Predict

BM25 ranks by literal overlap. Example 5's request contains "phone number", "app",
"refund", "know".

**Can `email_customer` be retrieved by that query?**

### 🔧 Do this

```bash
python3 agent.py retrieved   # type 5
python3 agent.py confusable  # type 5, for contrast
```

### 👀 What you'll see

`retrieved` tells you outright:

```
  ! the correct tool email_customer **was not retrieved** - nothing downstream can be right now
```

While `confusable` (all 40 tools) **gets it right**.

### 💡 What you learn

**Retrieval hid the correct answer from the model.**

Exactly lab 3-2's mechanism: the request says "no phone number, no app"; the tool
description says "send an email to a customer" — **not one word in common**. BM25
has nothing to work with.

And the model could have reasoned it out by elimination — **if only it had been
allowed to see the tool.**

> **The lab in one sentence:**
>
> "Paste everything" wastes tokens, but **its recall is always 100%.**
> "Retrieve first" saves tokens, but **its recall is a variable.**
>
> You are trading a **certain cost** for an **uncertain success rate**. Whether
> that's a good trade depends on your tool table and your queries — it isn't a
> decision you can make from a blog post.

---

## Step 3: change it yourself (exercises)

### Exercise 1 ⭐⭐ Write a trap that actually works

I wrote 3 and none of them landed. **Your turn.**

Ideas:
- Make two tools **genuinely** defensible, not merely similar-sounding
- Give constraints that need **multi-hop** reasoning to resolve to one tool
- Or: make the request **self-contradictory** and see how it handles that

**If you succeed, write it down** — that's a real finding, worth far more than
re-reading this page.

> Failing to fool it is also a result: **it means you shouldn't over-engineer your
> architecture around "the model will pick the wrong tool".**

### Exercise 2 ⭐ Raise `RETRIEVE_K`

Set it to 12, 16, 20 and re-run the failing example.

**Predict**: how high do you need to go?

> Then answer the harder question: **how would you have known to raise it?**
> You only knew because you could see the ground truth. Production has none.

### Exercise 3 ⭐⭐ Hybrid: retrieve + always-include

Change `pick_tools()`: take BM25's top 8, **then unconditionally add the 6
lookalike tools**.

**Predict**: how much longer is the prompt? Does the failing example recover?

> This is the principle that keeps recurring (labs 2-3 and 3-2):
> **don't put critical things behind a recall metric — include them unconditionally.**
>
> What makes something "critical" here? **The tools are mutually substitutable and
> picking wrong is expensive.**

### Exercise 4 ⭐⭐⭐ Improve the descriptions, then retrieve

Add synonyms to the 6 lookalike descriptions:

```python
("email_customer", "Send an email to a customer (contact customer, email notification, reach the customer)"),
```

Re-run `retrieved`.

**Predict**: does the failing example recover?

> That's **document expansion** (lab 3-2, exercise 3).
> **Note that it fixes two things at once**: retrieval can now find it, *and* the
> model can distinguish it better. One good description pays off in both places —
> another reason tool descriptions have such a high return.

### Exercise 5 ⭐⭐⭐ Two-stage selection

Restructure it: first have the model pick one of 6 **categories** (orders /
payments / customers / tickets / reports / messaging), then show only that
category's tools.

**Predict**: how much prompt do you save? What new failure mode appears?

> Hint: there are now **two** chances to pick wrong, and getting the first one
> wrong means there is no second chance. Same class of problem as retrieval's
> (**an irreversible early filter**), wearing a different hat.

---

## Check your answers

After you've tried → **[SOLUTION.md](SOLUTION.md)**

The full 15/15 data, the ranking detail on the retrieval failure (off by one
place!), why English and Chinese behave differently, and answers to every exercise.

---

## Appendix: concepts

### The four strategies

| Strategy | Prompt | Accuracy | Recall risk | When |
|---|---|---|---|---|
| Paste everything | **longest** | high | **none** | Tens of tools, and you fear misses more than cost |
| Retrieve first | short | high (**if it retrieves**) | **yes** | Hundreds of tools, and queries use the tools' vocabulary |
| Two-stage | short | medium | **yes, and earlier** | Tools have genuinely clean categories |
| Cut tools | shortest | — | — | First check whether you really don't need them |

### One engineering principle

> **"Paste everything" has 100% recall by construction. Every filter trades that
> away for cost.**
>
> So ask first: **how bad is your cost problem?** Bad enough to introduce a new
> failure mode?

Plenty of people do it backwards — reach for retrieval because "models get
confused with many tools". **This lab shows that premise doesn't hold on a current
model.**

### When to actually worry

Tool selection usually breaks not because of *count* but because:

1. **The descriptions are bad** (lab 4-1 — this is the real cause)
2. **Two tools genuinely overlap** (then merge them; don't retrieve around it)
3. **You have hundreds of tools** (now retrieval is mandatory — but pair it with an
   always-include list)

---

## Stuck?

| What you see | What to do |
|---|---|
| `x No usable backend found` | Install any one of the three options on screen |
| Mine picked wrong | **That's a finding — write it down!** Models are stochastic; I measured 15/15, not 100% |
| `retrieved` didn't fail for me | Check your `LANG`. In Chinese the tool ranks #8 and scrapes in; in English it's #9 and gets cut |
| Want the exact text the model received | Set `SHOW_PROMPT = True` |
| Forgot the commands | Run `python3 agent.py` with no arguments |
