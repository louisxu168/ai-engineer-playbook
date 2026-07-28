# Lab 01 — Answers

**English** · [简体中文](SOLUTION.zh-CN.md)

> Read this after you've run it and predicted wrong at least once.

The numbers below were measured with `LAB_BACKEND=claude` (Claude Code headless).
**Yours will probably differ** — see the last section, which is itself a lesson.

---

## Measured results

| Mode | Rounds | Tool calls | Answer |
|---|---|---|---|
| `full` | 3 | 4 | ✅ 597 USD / 4322.28 CNY |
| `no_history` | 5 | 4 | ✅ 4322.28 CNY — **it didn't break!** see below |
| `no_tool_calls` | 3 | 2 (both failed) | ❌ invented "about $100 each, rate ~7.1, ~2130 CNY" |
| `no_tool_results` | 4 | 5 | ❌ re-called the same tools repeatedly, then gave up |

Correct answer: Keychron Q1 Pro at 199 USD × 3 = 597 USD, × 7.24 = **4322.28 CNY**.

> **Note that "rounds" and "tool calls" have decoupled.** With parallel tool
> calls, one round can invoke several tools. So `full` finishes 4 tool calls in
> only 3 rounds: round 1 calls `search_products` + `get_rate` together (they're
> independent), round 2 runs two `calc`s together.
>
> Before parallel calls were added, this task took 5 rounds. **What you save is
> round trips, not tool calls** — each round trip waits 6–13 seconds on the
> model, a local function takes microseconds.
>
> It also makes sense that `no_history` did *not* improve (still 5 rounds): it
> only ever sees the most recent step, so it can't tell which tools are mutually
> independent, and doesn't dare parallelise.

---

## Mode by mode

### `full` — the baseline

3 rounds, 4 tool calls. Every step builds on the previous return value. That's
ReAct working as intended.

### `no_tool_results` — the cleanest failure

Textbook. Tools still get called, but every return value is replaced with
`[result hidden]`, so the model starts doing arithmetic on placeholders:

```
[tool] calc({'expression': '<the real unit price of the keyboard> * 3'})
       -> {'error': 'invalid syntax'}
```

And the "answer" it eventually produces reads like this:

> The unit price, USD total and CNY conversion for 3 mechanical keyboards have
> been computed in steps 4, 5 and 6 respectively; the final CNY figure is the
> result of step 6.

**Not one actual number**, delivered with total confidence. That is exactly what
a broken tool integration looks like in production: no error, just quiet nonsense.

### `no_tool_calls` — there's a trap here, and I fell in it

**On the first run this produced a refusal, not a hallucination.** It said, quite
correctly, "I can't look up the real unit price and I shouldn't invent it."

Why? Because the sentence **"Never guess a number you could look up with a tool"**
was *still in the system prompt* in `no_tool_calls` mode. The model obeyed it. So
what I was observing was **rule-following, not tool-lessness** — the ablation had
a confounding variable in it.

After fixing it (removing that line too — see `sys_no_guessing` in `agent.py`),
the expected hallucination appeared:

> Mainstream mechanical keyboards run about $100 each... 3 × $100 = $300; at a
> rate of roughly 7.1, that's about 2130 CNY

Truth: 199 / 7.24 / 4322.28. **Every number invented, and all of them plausible.**

**This is the single most valuable thing in this lab.** When you design an
ablation, you think you removed one variable — you often removed one and a half.
Always ask: does anything *else* in the system prompt still speak for the thing I
just deleted?

### `no_history` — it didn't break. Why?

Expected: "repeats tools it already called". Observed: **zero repeats**, correct
answer in 5 rounds.

Look at the round numbers and prompt sizes:

```
Round 3 | prompt 207 chars   <- can only see step 2
[tool] get_rate(USD, CNY)
Round 4 | prompt 264 chars   <- can only see step 3 (the get_rate result)
[tool] calc({'expression': '597 * 7.24'})   <- where did 597 come from??
```

Round 4's context contains **no 597 anywhere** — that was step 2's result, long
truncated. So how did it know?

Answer: **the model smuggled state into its own `reasoning` field.** Every step's
assistant reply is rendered back in full, reasoning included. It learned to write
"total is 597 USD, now I need the rate" into the reasoning, so that number
survived alongside the most recent step.

**It invented itself a memory channel.** Not a bug — this is real agent behaviour
(scratchpad persistence).

So how do you actually break it? **Cut history AND reasoning at the same time**,
closing the smuggling channel. That one's for you:

> Add a `no_history_no_reasoning` mode (both conditions active in
> `render_context`), predict the result, then run it.

---

## Exercise answers

**1. Delete the "never guess" line** — it starts quoting prices from memory
instead of calling `search_products`. Same phenomenon as the `no_tool_calls`
trap above: **that sentence carries more weight than you'd think.**

**2. Change a tool description to `"a tool"`** — wrong-tool rate goes up
noticeably, especially between `search_products` and `get_rate`. Because **the
description text is the model's only basis for choosing**; argument names in the
schema don't help much. Lesson: tool descriptions are not comments, they're prompt.

**3. Make `get_rate` return 999** — in the vast majority of runs it **swallows
it**, computes an absurd figure and reports it confidently. Occasionally it
mutters that the rate looks off. Lesson: **the model trusts tool output by
default.** Validation is your job, inside the tool.

**4. `max_iterations = 2`** — hits the cap branch and returns `answer: None`.
This is why every production agent needs the safety valve: without it, a
`no_history`-style loop bills you forever.

**5. Adding a fourth tool needs three changes:**
1. Write the function itself (`def apply_discount(price, percent)`)
2. Add an `elif` branch in `execute_tool()` mapping the name to the function
3. Add it to the `sys_tools` text — **miss this and the model never knows it exists**

Number 3 is the one beginners forget. Function written, wired up, never called —
because the model literally cannot see it.

---

## Why your numbers differ from mine

Three sources, all worth knowing:

1. **The model is stochastic.** The same mode run twice can differ by 1–2 rounds.
   That `no_history` result above **did repeat its tool calls** on a different run
   (steps 1–2 and 3–4 were identical conversions). **Ablation studies need
   multiple runs and trend-reading, not one run and a conclusion.**
2. **Different backends, different conclusions.** `LAB_BACKEND=claude` / `codex` /
   `api` are different models with different levels of instruction-following.
3. **Going through a CLI has a side effect**: you'll sometimes see it try to call
   `WebSearch` or `ToolSearch` — tools **not in our catalog at all**. That's
   Claude Code's own tool namespace leaking through the harness. Doesn't happen
   with `LAB_BACKEND=api`.

---

## In one line

All five ablations are **one or two lines of text** inside `pick_visible_steps()`,
`render_context()` and `build_system_prompt()`. No change to the model, the loop,
or any tool implementation.

**Context engineering is editing a string.** That's the only thing this lab wants
you to remember.
