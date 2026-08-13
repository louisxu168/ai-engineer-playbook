# Lab 1-1: Context Ablation

**English** · [简体中文](README.zh-CN.md)

> **What you'll learn**
>
> 1. An agent is not mysterious — it's `LLM + context + tools` in a while loop
> 2. "Context" isn't magic either: **it's a string you assembled yourself**
> 3. Delete different parts of it and the agent breaks in **four distinct ways** — and those four are the four incidents you'll hit in production
>
> **How to work through it**: every step is *predict → run → compare → find the
> line in the code*. **Being wrong is where the learning is**, so resist opening
> SOLUTION.md early.
>
> **Time**: about 40 minutes done properly. 3 minutes if you just want to see it run.

---

## Step 0: Get it running (3 min)

```bash
cd labs/ch1-agent-basics/1-1-context
python3 agent.py full
```

**That's it — two lines.** No `pip install`, no API key, no config file. If you
have Claude Code or Codex installed, it finds them automatically.

It will ask what task you want the agent to do. Press Enter for examples and
copy one, e.g.:

```
I want to buy 3 mechanical keyboards. Look up the unit price, compute the total, and convert it to CNY.
```

> Output is Chinese by default. Set `LANG = "en"` at the top of `agent.py` to
> switch both the console output and the prompts sent to the model.

### 👀 You should see

```
============================================
  Round 1 of 8     mode: full
  no history in context yet     prompt 141 chars
============================================
  asking the model... took 7.2s
  [thinking] Look up the price and the rate in parallel; they're independent.
  [tool 1/2] search_products({'keyword': 'mechanical keyboard'})
        -> {'name': 'Keychron Q1 Pro', 'usd': 199.0}
  ...
  [answer] ...about 4322.28 CNY.
```

**An `[answer]` line means it worked.** If not, see "Stuck?" at the bottom.

### ✅ Write these three numbers down

Every later step compares against them:

| | Your baseline |
|---|---|
| How many rounds? | ___ |
| How many tool calls? | ___ |
| Was the answer right? | ___ |

---

## Step 1: See what "context" actually is (5 min)

### 🔧 Do this

Open `agent.py` and flip this line at the top:

```python
SHOW_PROMPT = True
```

Run `python3 agent.py full` again.

### 👀 You'll see

Every round it prints **the exact text sent to the model**:

```
  +--- exact text sent to the model --------
  | TASK: I want to buy 3 mechanical keyboards...
  |
  | --- step 1 ---
  | You replied: {"reasoning": "look up price...", "calls": [...]}
  | Tool search_products returned: {"name": "Keychron Q1 Pro", "usd": 199.0}
  |
  | Now give your next JSON reply.
  +----------------------------------------
```

### 💡 What you learned

**The LLM endpoint is stateless.** The server stores nothing. Every single call,
you resend **everything that has happened so far**.

So "context" is that string in the box. **Everything the agent knows on round 5
is whatever that text says. There is nothing else.**

Also watch the `prompt NNN chars` number grow each round — that's context
accumulating.

---

## Step 2: Predict, then delete the history (8 min)

### 🤔 Predict first (don't skip)

We're about to delete **all history except the most recent step**. Guess:

- More rounds or fewer? ___
- How many tool calls? ___
- Will the answer still be right? ___

### 🔧 Do this

```bash
python3 agent.py no_history "(paste the SAME task you used in step 0)"
```

> ⚠️ **The task must be identical**, or it isn't a comparison. The program
> prints a ready-made command after each run — copy it and change the mode.

### 👀 What to watch

The middle line of each round header:

```
Round 3 | context holds step 2 only | prompt 204 chars
```

In `full` mode it said `context holds steps 1-2` and the character count climbed
past 700. Here it's always one step, and the count stays flat around 200.

### 💡 What you learned

`no_history` is the real-world incident **"your context window got truncated"**.
Conversation too long, compacted, pruned — and the agent starts redoing work it
already finished.

> **If it didn't break** (still got the right answer), you've hit something
> interesting. Don't look it up yet — think about it: round 4's context contains
> no intermediate result at all. So where did it get that number?

---

## Step 3: Run the other three ablations (15 min)

**Predict before each one.** Fill the table before reading on:

| Mode | What's deleted | Predicted rounds | Predicted: still right? | Actual |
|---|---|---|---|---|
| `no_reasoning` | the model's own thinking | | | |
| `no_tool_calls` | tools aren't offered at all | | | |
| `no_tool_results` | tools run, results hidden | | | |

```bash
python3 agent.py no_reasoning "(same task)"
python3 agent.py no_tool_calls "(same task)"
python3 agent.py no_tool_results "(same task)"
```

Then `python3 agent.py all` for the comparison table (3–8 minutes — **set
`SHOW_PROMPT` back to `False` first** or it'll scroll away).

### 💡 What you learned

Each failure mode maps onto a real production incident:

| Mode | Real-world failure |
|---|---|
| `no_history` | context window truncated |
| `no_reasoning` | you dropped thinking blocks to save tokens |
| `no_tool_calls` | misconfigured permissions, tool never registered |
| `no_tool_results` | broken tool integration |

**This lab is a field guide to agent failures.**

---

## Step 4: Go find the line (10 min)

### 🔧 Do this

For every result that didn't match your prediction, find **the line that caused
it** in `agent.py`.

Hint — all four ablations live in two places:

- `pick_visible_steps()` and `render_context()` — Part 3
- `build_system_prompt()` — Part 2

### 💡 What you learned

Count the lines you found: **under ten in total.**

**Not one of them touches the model. Not one touches the loop.**

> The one thing to remember from this lab:
> **context engineering is editing a string.**

---

## Step 5: Change it yourself (exercises)

**Predict the outcome of each before you run it.**

### Exercise 1 ⭐ Delete the "never guess" line

Find `sys_no_guessing` in `agent.py` and take it out of the system prompt.

**Predict**: will it still call `search_products`?

### Exercise 2 ⭐⭐ Ruin a tool description

Change the `search_products` line in `sys_tools` to just `a tool`.

**Predict**: can it still pick the right one?

> The point: **the description text is the model's only basis for choosing.**
> Tool descriptions aren't comments — they're part of your prompt.

### Exercise 3 ⭐⭐ Make a tool return bad data

Make `get_rate` always return `{"rate": 999}`.

**Predict**: will it notice, or swallow it and report an absurd figure?

### Exercise 4 ⭐ Cut the agent off

Change `max_iterations` in `run()` to `2`.

**Predict**: what does a truncated agent produce?

### Exercise 5 ⭐⭐⭐ Add a fourth tool

Add `apply_discount(price, percent)` so the agent can compute discounts.

**Work out how many places you need to change before you start.** (It's three —
miss one and you get "the function is written, it's wired up, and it's never
called".)

### Exercise 6 ⭐⭐⭐ Combined ablation (challenge)

If you hit "`no_history` didn't break" in step 2, add a
`no_history_no_reasoning` mode where both conditions apply.

**Predict**: will it break this time? Why?

---

## Check your answers

Only after doing the above → **[SOLUTION.md](SOLUTION.md)**

It has the measured results, explanations for two surprising findings, and all
the exercise answers.

---

## Appendix: concept reference

Look things up here while reading the code.

### The agent loop

```
loop:
    reply = llm(messages)              # the model says what it wants
    if no tool calls: DONE             # it answered -> exit
    for each tool call:
        result = your_code_runs_it(...)   # the model can't; you can
        messages.append(result)           # paste it back
```

**The model is a planner that speaks JSON. You are its hands.**

### The full version: how many exits does a loop have?

Those six lines leave out something fatal — **checking only `tool_calls` is an infinite
loop.** Nothing stops the model from naming a tool every round and never answering.

A real loop needs at least this:

```python
trajectory = [ {role: "user", content: task} ]

for round in 1 .. MAX_ROUNDS:                 # <- EXIT 3: hard round cap

    prompt = STATIC_PREFIX + trajectory       # system prompt + tool defs, then
                                              # the whole trajectory, resent every time

    if length(prompt) > CONTEXT_LIMIT:        # <- EXIT 4: doesn't fit any more
        trajectory = compact(trajectory)      #    note: compact and CONTINUE,
                                              #    this is not a stop

    reply = call_model(prompt)                # stateless: the server keeps nothing

    if reply failed to parse:                 # <- EXIT 5: no JSON could be extracted
        if retries_left: continue             #    retry - do NOT silently
        else: raise ParseError                #    treat this as "finished"

    trajectory.append(reply)                  # record what it said, immediately

    if reply has "answer":                    # <- EXIT 1: it declared it's done
        return reply.answer

    if reply.tool_calls is empty:             # <- EXIT 2: it stopped asking for tools
        return reply.content                  #    (equivalent to being done)

    for call in reply.tool_calls:             # YOU execute; the model only named them
        result = TOOLS[call.name](**call.args)
        trajectory.append( {role: "tool", content: result} )

return FAILED                                 # ran out of rounds without an answer
                                              # <- this is a FAILURE, not a completion
```

**The exits, grouped:**

| | Exit | Meaning |
|---|---|---|
| **Normal completion** | `answer` field present | it says it's done |
| | `tool_calls` empty | it stopped asking for tools |
| **Resource exhaustion** | round cap reached | ☠ **failure**, not completion |
| | context won't fit | → compact, then **continue** |
| | token / cost budget | any real system needs this |
| **Anomaly** | parse failure | see the trap below |
| | repeated / failing tool calls | loop detection |
| | user interrupt, timeout | |

**This lab implements exits 1, 2 and 3.** Exit 4 is
[lab 2-9](../../ch2-context-engineering/2-9-context-compression/)'s subject; exit 5 is
**deliberately absent here** — see why below.

### ⚠️ A trap: parse failure and "completion" look identical

`agent.py` does this:

```python
reply = parse_json_reply(raw_text)          # returns {} when nothing parses

has_answer   = "answer" in reply            # {} -> False
wanted_calls = extract_tool_calls(reply)    # {} -> []

if has_answer or len(wanted_calls) == 0:    # <- {} lands HERE
    answer = reply.get("answer") or raw_text.strip()
```

**An empty dict satisfies both "no answer" and "no tool_calls" at once**, so a parse
failure gets reclassified as *completion* and the raw text is returned as the answer.

That is **deliberate** in this lab — in `no_tool_calls` mode the model often replies in
plain prose with no JSON to extract, and there the raw text really is the answer.

The price: **a genuine parse failure (truncated output, drifted format) is silently
treated as a completion.** The loop exits cleanly and returns plausible-looking garbage,
**raising no error**.

> This is the same shape as
> [lab 6-1](../../ch6-evaluation/6-1-llm-as-judge/)'s JSON parse failure being recorded as
> "the model is bad at this". Production systems must separate the two cases.

### Why are there two "normal completion" exits?

Exit 1 (`answer` field) and exit 2 (empty `tool_calls`) are redundant — **and exit 1 is a
debt owed by the string-concatenation approach:**

- **Structured tool-use APIs** need only exit 2: `stop_reason != "tool_use"` **is** the
  stop signal. The model never declares an `answer` field.
- **String-concatenation implementations** need exit 1, because there is no `stop_reason`
  to read — the model has to announce "I'm finished" inside its own JSON.

**Letting the model announce its own termination means it can forget to** — which is
exactly why exit 3 (the round cap) has to exist as a backstop.

### The five parts of context

| Part | Role | Written by |
|---|---|---|
| System prompt | who the agent is, the rules | you |
| Tool catalog | what it can call, with what arguments | you |
| User message | the task | the user |
| Assistant messages | its reasoning and its tool requests | the model |
| Tool messages | what your code returned | your code |

### "Round" vs "step"

- **Round N** — the program's view: the loop's Nth iteration, happening *now*
- **Step N** — the model's view: round N's result, already in history

So round N sends steps 1 through N-1.

### One round can call several tools

A single reply can name several tools, provided they're **independent**:

| Call | Depends on | Parallel? |
|---|---|---|
| `search_products("keyboard")` → 199 | nothing | ✅ |
| `get_rate("USD","CNY")` → 7.24 | nothing | ✅ goes with the above |
| `calc("199 * 3")` → 597 | the first one | ❌ needs 199 first |

**What you save is round trips, not tool calls** — a round trip waits 6–13
seconds; a local function takes microseconds.

What enforces the dependencies? **Only two sentences in the system prompt —
there is no validation in the code.** The underlying mechanism: tool arguments
are **literals, not references**, so you physically cannot write a value you
don't have yet.

---

## Stuck?

| What you see | What to do |
|---|---|
| `x No usable backend found` | Install any one of the three options it prints (Claude Code is easiest) |
| Nothing happens for tens of seconds | **Normal** — each model call takes 5–15s |
| Forgot the commands | Run `python3 agent.py` with no arguments |
| Results don't match the docs | **Normal** — models are stochastic. Ablation studies need multiple runs and trend-reading |
