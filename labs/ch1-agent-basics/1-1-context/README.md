# Lab 01: Context Ablation

**English** · [简体中文](README.zh-CN.md)

> ## 🚀 Run it first (nothing to install)
>
> ```bash
> cd labs/ch1-agent-basics/1-1-context
> python3 agent.py full
> ```
>
> **That's it — two lines.** No `pip install`, no API key, no config file. If you
> have Claude Code or Codex installed, it finds them automatically.
>
> **Takes about 30 seconds.** You should see something like:
>
> ```
> Backend: claude
> Task: I want to buy 3 mechanical keyboards...
>
> ============================================
>   Round 1 of 8     mode: full
> ============================================
>   asking the model... took 7.2s
>   [thinking] Look up the price and the rate in parallel; they're independent.
>   [tool 1/2] search_products({'keyword': 'mechanical keyboard'})
>         -> {'name': 'Keychron Q1 Pro', 'usd': 199.0}
>   ...
>   [answer] ...about 4322.28 CNY.
> ```
>
> If you got an `[answer]` line, it worked. **Read on for the other four modes.**
>
> Forgot the commands? Run `python3 agent.py` with no arguments for usage.
>
> *(Output is Chinese by default — set `LANG = "en"` at the top of `agent.py`.)*

**The question:** what exactly *is* an agent's "context", and how does it break
when you delete a piece of it?

---

## 1. The one idea

> **Agent = LLM + context + tools, wrapped in a while loop.**

An LLM is a pure function: text in, text out. It has no memory, and it
**cannot execute anything**.

The only thing it can do is emit some JSON saying *"I'd like to call
`search_products('keyboard')`"*. The thing that actually runs that function is
**your Python**. You paste the return value back into the text and ask again.
Loop until it stops asking for tools and gives an answer instead.

```
loop:
    reply = llm(messages)              # model decides what to do next
    if reply has no tool calls: DONE   # it answered -> exit
    for each tool call:
        result = your_code_runs_it(...)   # the model can't; you can
        messages.append(result)           # paste the result back
```

That's the whole ReAct loop. In `agent.py` it's `run()` — about 30 lines.

**The thing to internalise:** the model is a planner that speaks JSON. You are
its hands.

### One round can call several tools (parallel tool calls)

Note that `for each tool call` is plural — **one model reply can name several
tools at once**. In real APIs (Anthropic, OpenAI) a single assistant message
can carry multiple `tool_use` blocks; you run them all and return every result
**in one message**.

Whether calls can be parallel comes down to **data dependency**:

| Call | Depends on | Parallel? |
|---|---|---|
| `search_products("keyboard")` → 199 | nothing | ✅ independent of the next one |
| `get_rate("USD","CNY")` → 7.24 | nothing | ✅ can go together |
| `calc("199 * 3")` → 597 | the first one | ❌ needs 199 first |
| `calc("597 * 7.24")` | the two above | ❌ needs 597 and 7.24 |

So the optimum for this task is **3 rounds** (1+2 together → 3 → 4), not 4.

**What you save is round trips, not tool calls.** Each round trip waits
6–13 seconds on the model; a local function takes microseconds. Round trips are
the entire cost. That's why real agents care about parallelism.

> Worth remembering: in real APIs, multiple `tool_result` blocks **must go back
> in a single message**. Split them across messages and the model gradually
> learns "I'd better do these one at a time" — you train the parallelism out of it.

### So who enforces the dependencies?

Key question, and the answer may surprise you: **the judgement happens in the
prompt, the enforcement happens in the loop, and nothing validates either.**

| | Who does it | Which layer |
|---|---|---|
| **Deciding** what can be parallel | the model, on its own | Prompt — literally two sentences in `sys_protocol` |
| **Enforcing** the ordering | the loop structure | Code — to use a result you must wait a round |

The entire "dependency management" in `agent.py` is these two lines of prose:

```
- If the tools are INDEPENDENT, put them all in one reply.
- If a later tool needs an earlier one's return value, request only the
  earlier one now.
```

**Not one line of code checks whether it got that right.** No dependency graph,
no topological sort, no validation. The model says parallel, `run()` runs them.

So what happens when it judges wrong? Both cases show up in practice:

**Case 1 — it routes around the dependency:**

```python
[tool] calc({'expression': '199.0 * 3'})           -> 597.0
[tool] calc({'expression': '199.0 * 3 * 7.24'})    -> 4322.28
```

The second call *conceptually* depends on the first, but instead of writing
`597 * 7.24` it **inlined `199.0 * 3`** — it already had 199 and 7.24 from the
previous round, so it could substitute the values and the dependency vanished.

**Case 2 — it can't route around it, and breaks** (seen in `no_tool_results`):

```python
[tool] calc({'expression': '<the USD total from step 5> * <the rate>'})
       -> {'error': "invalid syntax"}
```

It tried to reference a value it didn't have, could only write a placeholder,
and `eval` failed.

**The underlying mechanism:** tool arguments are **literals, not references**.
You cannot write "the previous tool's return value" into an argument. So
dependencies aren't enforced by anyone — they're **physically unwritable**. If
you don't have the number, you can't type it.

### Three approaches, in ascending order

| Approach | What guarantees the dependency | Cost |
|---|---|---|
| Sequential (one per round) | the loop structure | more round trips, slow |
| **Parallel (what this lab does)** | **model judgement + literal-only arguments** | wrong judgement → wrong result |
| Model writes code that calls tools | variable references, language-level | needs a sandbox |

The third is Anthropic's Programmatic Tool Calling — the model writes actual
code and calls tools from inside it, so dependencies are expressed as variables:

```python
p = search_products("keyboard")
r = get_rate("USD", "CNY")
total = p["usd"] * 3 * r["rate"]      # a real dependency
```

Intermediate results never enter the context either, which saves tokens. The
price is a sandbox to run it in.

**We sit in the middle tier — that's the mainstream approach, not a
simplification.** The mainstream answer really is "accept that the model may
judge wrong, and let tool errors flow back so it can correct itself." That's
also why every tool in `agent.py` does `return {"error": ...}` instead of
raising: the error text goes back into the context where the model can see and
fix it. Fault tolerance is part of the design.

---

## 2. What "context" actually means

Every time you call the LLM you resend **the entire conversation**. The server
stores nothing. That array is the context, and it has five parts:

| Part | Role | Written by |
|---|---|---|
| System prompt | who the agent is, what the rules are | you |
| Tool catalog | what it can call, with what arguments | you |
| User message | the task | the user |
| Assistant messages | its reasoning and its tool requests | the model |
| Tool messages | what your code returned | your code |

Everything the agent knows on round 7 is what's in that array. **There is
nothing else.**

### "Round" vs "step"

Two views of the same counter, which trips people up:

- **Round N** — the program's view: the loop's Nth iteration, happening *now*
- **Step N** — the model's view: the result of round N, already in history

So round N sends steps 1 through N-1:

```
Round 1  ->  history is empty
Round 2  ->  history has step 1
Round 3  ->  history has steps 1, 2
Round 4  ->  history has steps 1, 2, 3
```

In one line: **"round" is what's happening, "step" is what already happened.**
The progress output prints this for you (`context holds steps 1-3`).

---

## 3. What the experiment does

An **ablation study**: run the same task five times, deleting one part of the
context each time, and observe how it breaks. The method is borrowed from ML
research — to prove a component matters, remove it and measure the damage.

| Mode | What's deleted | Expected failure |
|---|---|---|
| `full` | nothing (baseline) | completes normally |
| `no_history` | everything but the latest step | repeats tools it already called, loops to the cap |
| `no_reasoning` | the model's own thinking | still works, but takes more rounds — it re-derives its plan every time |
| `no_tool_calls` | tools aren't offered at all | confidently makes up an answer |
| `no_tool_results` | results replaced with `[result hidden]` | calls tools, sees nothing, invents numbers |

**Read those failure modes again.** Every one is a bug you will hit for real:

- `no_history` = your context window got truncated
- `no_tool_results` = your tool integration is broken
- `no_tool_calls` = misconfigured permissions, tool never registered
- `no_reasoning` = you dropped thinking blocks to save tokens

This lab is a **field guide to agent failures**.

---

## 4. Doing it

### 0. Setup

```bash
pip install -r requirements.txt
python3 -c "import llm; print(llm.detect_backend())"
```

If that prints `claude` or `codex`, you're set — no API key needed.
Want it faster: `export LAB_BACKEND=api DEEPSEEK_API_KEY=sk-...`

For English output, set `LANG = "en"` at the top of `agent.py`. That switches
both the console output and the prompts sent to the model.

### 1. Read the code first

`agent.py` is written **in reading order**, in six labelled parts:

| Part | Content | Difficulty |
|---|---|---|
| 1 | Tools — three plain Python functions | easy |
| 2 | System prompt — what tools exist, what format to reply in | easy |
| 3 | **Assembling the context** ★ all five ablations live here | core |
| 4 | Running the tools — an if/elif chain | easy |
| 5 | The loop — the heart of the agent | core |
| 6 | CLI entry point — irrelevant to how agents work | skip |

`llm.py` next door is the backend adapter. **Skip it entirely on a first read** —
all you need to know is that it gives you `complete(prompt, system)`.

Read with these three questions in mind:

1. Which function is the loop? Which line decides when to stop?
2. Which line does each ablation change?
3. Where does a tool the model named actually get executed?

### 2. See the context with your own eyes

At the top of `agent.py`:

```python
SHOW_PROMPT = True
```

Leave it on and run `python3 agent.py full`. It prints the exact text sent to
the model each round:

```
  +--- exact text sent to the model ------------
  | TASK: I want to buy 3 mechanical keyboards...
  |
  | Now give your next JSON reply.
  +---------------------------------------------
```

After that one look, the mystique is gone: **"context" is a string you built.**

Keep it on and run `python3 agent.py no_history`, then compare the two dumps.
Which sections are missing? That beats reading the docs ten times.

### 3. Run the baseline

```bash
python3 agent.py full
```

Watch the `[tool]` lines. Count the rounds and the tool calls.

### 4. The important bit: predict, *then* run

Run the other four modes one at a time — but **write down your prediction
first**. More rounds or fewer? How many tool calls? Is the answer still right?

```bash
python3 agent.py no_history
python3 agent.py no_reasoning
python3 agent.py no_tool_calls
python3 agent.py no_tool_results
```

Once you've done all four and predicted each, run the comparison:

```bash
python3 agent.py all
```

> ⚠️ **`all` is not a sixth mode** — it runs the five above back to back. So
> you'll see five blocks of output, each restarting from "Round 1". That looks
> like an infinite loop but isn't. Up to 40 model calls, roughly **3–8 minutes**
> on the CLI backends. **Turn `SHOW_PROMPT` back to `False` first**, or the
> comparison table will scroll away.

**Being wrong is where the learning is.** If you predicted right you already
knew it. Don't read `SOLUTION.md` yet.

### 5. Trace it back to the code

For every result that didn't match your prediction, go find **the line that
caused it**.

Hint: all five ablations are in `pick_visible_steps()`, `render_context()` and
`build_system_prompt()` — one or two lines each. That's the point of the lab:
**context engineering is editing a string.**

---

## 5. Exercises: break it on purpose

Edit `agent.py`, predict, verify:

1. **Delete the "never guess" line** (`sys_no_guessing`) — does it still look
   things up?
2. **Change a tool description to just `"a tool"`** — does it still pick the
   right one? (Point: **tool descriptions are part of your prompt.**)
3. **Make `get_rate` return a wrong rate** (say 999) — does it notice, or
   swallow it?
4. **Set `max_iterations` to 2** — what does a truncated agent produce?
5. **Add a fourth tool** (e.g. `apply_discount(price, percent)`) — you need to
   change **three** places. Find them.

2 and 3 are the ones worth doing. They make the same point: **the system prompt
and the tool descriptions are your program.** What you're really learning is how
to write and debug code in English.

---

## 6. Odds and ends

- **`temperature`** — randomness. Agents want it low (0–0.3) so tool arguments
  stay deterministic.
- **`max_iterations`** — the safety valve. Without it, `no_history` mode bills
  you forever. **Every production agent needs one.**
- **Why tool calls are JSON text, not structured `tool_use`** — because we go
  through the Claude Code / Codex CLI, whose harness owns that channel. Use
  `LAB_BACKEND=api` to see real structured tool calling.

---

Read [SOLUTION.md](SOLUTION.md) after you've tried it.
