# Lab 2-1: A local small model — seeing what's under the API

**English** · [简体中文](README.zh-CN.md)

> **What you'll learn**
>
> 1. **A 0.6B model calls tools reliably** — and emits two parallel calls at once (measured)
> 2. Real **TTFT / tokens-per-second / prefill** numbers, measured on your own machine
> 3. A counterintuitive finding: **local deployment washes the "raw" output too** —
>    the thing doing the washing just moves from a cloud vendor to a process on your laptop
> 4. **A textbook claim I could not reproduce** — and the solid number that failure produced
>
> **How you'll learn it**: entirely on your own machine. No network, no cost, no API key.
>
> **Time**: 25 minutes including setup.
>
> ⚠️ This is the **only** lab here that needs an extra install (Ollama + a 500MB model).

---

## Why this lab is different

Every other lab asks a **large model that belongs to someone else**, through Claude
Code / Codex / an API. Those interfaces are helpful — they **wash** the model's raw
output before handing it to you: thinking tags stripped, special tokens removed,
tool calls parsed into structured fields.

This lab tries to get that layer back, by **running the model on your own machine**.

And it's a **0.6B (600-million-parameter)** model — roughly **hundreds to a thousand
times smaller** than what you normally use.

---

## Step 0: setup (5 minutes, once)

```bash
# 1. Install Ollama
brew install ollama                 # macOS; others: https://ollama.com/download

# 2. Start it (leave this running in another terminal)
ollama serve

# 3. Pull the model (~500MB, one time)
ollama pull qwen3:0.6b
```

**No discrete GPU, no CUDA.** On Apple silicon Ollama uses Metal (the GPU inside
the chip); measured **113–131 tokens/s** on an M3.

There are **no Python dependencies** — standard library only. That's deliberate:
an official SDK would wrap up the streaming and timing that this lab exists to show.

```bash
cd labs/ch2-context-engineering/2-1-local-llm-serving
python3 agent.py                    # usage
```

> Don't want to install it? The other three labs in this chapter (2-1 / 2-2 / 2-3)
> don't need it.

---

## Step 1: look at the "raw" output (5 min) ★

```bash
python3 agent.py raw
```

### 👀 What you'll see

```
  +- raw text emitted by the model ------

  | [thinking] The user is asking two things, the time in Vancouver and the
  | weather... so I should call get_time and get_weather, then give the result.
  |
  | [content] TOOL: {"name": "get_time", "args": {"city": "Vancouver"}}
  | TOOL: {"name": "get_weather", "args": {"city": "Vancouver"}}
  +--------------------------------------

  TTFT 197 ms   ·   205 tokens generated   ·   131.1 tok/s   ·   110 input tokens
```

### 💡 What you learn

**Two things.**

**① A 0.6B really does call tools — and it emitted two at once.** It worked out
that "time" and "weather" are independent, so it issued both calls in a single
turn. That's the precondition for parallel execution.

**② But look at those `[thinking]` / `[content]` labels — that line wasn't drawn by
the model.**

The model generates **one continuous span** wrapped in `<think>…</think>`.
**Ollama strips the tags server-side and splits it into two JSON fields** before you
ever see it.

> **This is the first counterintuitive thing here:**
> I set out to show you "the raw token stream the API hides", and discovered that
> **local deployment washes it too** — the washer just moved onto your own machine.
>
> I tried to bypass the template layer (`raw:true` on `/api/generate`) to get the
> literal `<think>` characters. **It didn't work** — SOLUTION section 3 has the
> full attempt.

**"Raw" is layered. Whatever you think the bottom is, there's another layer below.**

---

## Step 2: look at the parsing (3 min)

```bash
python3 agent.py parsed
```

The same output, split three ways: thinking / reply / tool calls.

### 💡 What you learn

Open `agent.py` and read `split_output()` — **I cut those three segments with a
regex.** The model didn't hand you three fields.

Cloud APIs give you structured fields by doing exactly this, just server-side.

> **Note the order: think → speak → call tools.**
>
> It's fixed, and it's why a streaming UI can show "thinking…": switch state when
> thinking arrives, and **start executing the moment the first tool call parses** —
> **without waiting for the model to finish.** That's a real latency win.

---

## Step 3: the full ReAct loop (4 min)

```bash
python3 agent.py react
```

### 👀 What you'll see

```
  -- round 1 --
  * it emitted 2 tool calls at once - the two are independent, so they can run in parallel
  [call] get_time({"city": "Vancouver"})     -> {"time": "2026-07-29 09:56"}
  [call] get_weather({"city": "Vancouver"})  -> {"weather": "小雨", "celsius": 14}

  -- round 2 --
  [final answer] It's 09:56 on 2026-07-29 in Vancouver, with light rain at 14°C.
```

### 💡 What you learn

**This is lab 1-1's loop**, unchanged:

```
llm(messages) -> tool calls -> your code runs them -> paste results back -> repeat
```

The only difference is that the model is now a 0.6B on your laptop. **The loop
itself has nothing to do with model size.**

> It also **combined both tool results into one sentence**, which requires
> understanding what each result was. Six hundred million parameters did that.

---

## Step 4: measure latency, and a claim that didn't reproduce (8 min) ★★

```bash
python3 agent.py cache
```

This mode uses a **~2000-token** system prompt and measures **prefill time**
(`prompt_eval_duration` — the time spent processing the **input**) in three groups:

| Group | What it does |
|---|---|
| **A** | Completely fixed system prompt, 3 runs |
| **B** | A never-seen session ID injected at the **start** each time |
| **C** | A never-seen session ID injected at the **end** each time |

### 🤔 Predict

The book — and nearly every article on KV caching — says **changing the start
invalidates the prefix cache**.

So **B should be clearly slower than C**. Agree?

### 👀 What to watch

**The prefill times, especially B versus C.**

### 💡 What you learn

**I could not reproduce that claim.** B and C show **no stable difference** — both
are "slow the first time, fast afterwards", regardless of where the ID sits.

But the failed attempt measured something **very solid**:

```
first call after the model is cold-loaded   ~1000 ms
every call after that                       ~10-40 ms
```

**Two orders of magnitude, reproducible every time.**

> ⚠️ My first version used a 110-token prompt where prefill was ~10 ms — **entirely
> buried in noise**. Three runs produced three contradictory conclusions.
>
> **That's a lesson in itself: before measuring an effect, confirm it's large enough
> to be measurable.** Full numbers in SOLUTION section 4.

And this is the **real case for context engineering**:

> **A 2050-token input costs ~1 second of prefill when cold.** Longer input, bigger
> number — and you re-pay it on every request that misses the cache.
>
> **That is why lab 2-9 (context compaction) exists.**

---

## Step 5: change it yourself (exercises)

### Exercise 1 ⭐ Try a bigger model

Change `MODEL` at the top of `agent.py`:

```bash
ollama pull qwen3:1.7b     # ~1.4GB
```

**Predict**: how much does tok/s drop? Are the tool calls more accurate? Is the
thinking longer?

> This builds **first-hand** intuition about size ↔ speed ↔ quality, instead of
> reading it off someone else's benchmark.

### Exercise 2 ⭐⭐ Give it a task with a real dependency

Time and weather are independent, hence parallel. Try something **necessarily
sequential**:

> "What time is it in Vancouver? If it's past 8pm there, tell me the weather in Beijing."

**Predict**: will it still fire both tools at once, or call one and wait?

> This tests lab 1-1's conclusion — **dependencies are handled at the prompt layer,
> not validated in code** — now on a 0.6B.

### Exercise 3 ⭐⭐ Turn thinking off

Pass `think=False` to `chat_stream` and re-run `raw`.

**Predict**: how much faster? Are the tool calls still right?

> Thinking **costs tokens**. See what those tokens bought on this task.

### Exercise 4 ⭐⭐⭐ Dig the KV-cache effect out

I couldn't reproduce start-vs-end. **You try.** Directions:

- Grow the system prompt to 8k or 16k tokens (the effect should scale with length)
- Use a **genuinely fresh, never-repeated** prefix each time (avoid hitting a
  previously cached copy)
- Try vLLM — its prefix caching is implemented very differently from llama.cpp's
- Ignore `prompt_eval_duration` and measure **end-to-end TTFT distribution** instead

**If you reproduce it, that's a real finding — write it down.**

> And a more valuable question: **why does nearly every article describe this
> effect, while I can't measure it on a real local stack?**
> A good reminder that **technical folklore spreads much faster than it gets verified.**

### Exercise 5 ⭐⭐⭐ Use Ollama's native tools parameter

This lab deliberately uses a **text protocol** (`TOOL: {...}`) so you can *see* what
a tool call looks like. Switch to Ollama's native `tools` parameter.

**Predict**: can you still see that line in the output?

> The answer restates this lab's theme: **every layer of abstraction you add is one
> more thing you stop being able to see.**

---

## Check your answers

After you've tried → **[SOLUTION.md](SOLUTION.md)**

All measured numbers, the full account of how I tried and failed to get the literal
`<think>` tags, and the KV-cache experiment's journey from "fake success" to
"honest failure".

---

## Appendix: concepts

### Where the latency actually goes

Generation has two phases with completely different cost models:

| Phase | What it does | Scales with | Measured here |
|---|---|---|---|
| **Prefill** | Process the **input**, compute its KV | **input length** | 2050 tokens cold ≈ 1000 ms |
| **Decode** | Emit **output** tokens one by one | **output length** | ≈ 131 tok/s |

> **Context engineering optimizes the first phase.** Every extra 1000 tokens of
> history is prefill you pay for on every request.

### "Raw output" is layered

```
the token sequence the model actually generates
   |  inference engine (llama.cpp) applies the template
<think>...</think> + body + <tool_call>...
   |  the Ollama server parses it
{"thinking": "...", "content": "...", "tool_calls": [...]}
   |  the SDK wraps it again
response.message.content
```

**Wherever you sit, you only see what the layers below have packaged for you.**
This lab takes you down two layers — **but not to the bottom.**

---

## Stuck?

| What you see | What to do |
|---|---|
| `x Can't reach Ollama` | Is `ollama serve` running? It has to stay running |
| `x doesn't have this model` | `ollama pull qwen3:0.6b` |
| The first call is very slow | **Normal** — the model is loading into memory. The second is fast |
| My tok/s is much lower | Depends on your chip. Intel Macs and older machines are much slower |
| I *did* see a B-vs-C difference | **That's a finding!** Write it down — your conditions differ from mine |
| Reclaim the disk space | `ollama rm qwen3:0.6b` + `brew uninstall ollama` |
