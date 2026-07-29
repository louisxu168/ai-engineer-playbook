# Lab 2-1 answers: a local small model

**English** · [简体中文](SOLUTION.zh-CN.md)

> ⚠️ Try it first. Being wrong once beats reading this ten times.

---

## 1. Environment and numbers

Machine: MacBook (Apple **M3**, 16GB)
Stack: Ollama **0.32.5** (Metal / iGPU, 11.8 GiB available), model **qwen3:0.6b** (522MB)
Date: 2026-07-29

| Metric | Measured |
|---|---|
| Generation speed | **113 – 131 tok/s** |
| TTFT (warm) | **120 – 200 ms** |
| Prefill (110 input tokens) | **8 – 35 ms** |
| Prefill (2050 input tokens, cold) | **≈ 1000 ms** |
| Prefill (2050 input tokens, warm) | **10 – 40 ms** |

The book says "over 100 tokens per second on an Apple M2" — **that reproduced**;
an M3 gives 113–131.

---

## 2. A 0.6B's tool calling: better than expected

The complete output from one `raw` run:

```
[thinking] The user asks two things, the current time in Vancouver and the weather.
First I need the current time in Vancouver, which get_time can provide. The weather
likewise needs get_weather. The question has two parts, so I may need to call both
tools... So the correct approach is to call get_time and get_weather, then answer.

[content] TOOL: {"name": "get_time", "args": {"city": "Vancouver"}}
          TOOL: {"name": "get_weather", "args": {"city": "Vancouver"}}
```

**Six hundred million parameters did three things:**

1. Split one question into two sub-questions
2. Determined they are **independent**, and therefore **emitted both tool calls at once**
3. Produced valid JSON first try (no trailing commas, didn't write `arguments` for `args`)

And in `react` mode it did a fourth:

```
[final answer] It's 09:56 on 2026-07-29 in Vancouver, with light rain at 14°C.
```

**It fused two tool results into one fluent sentence** — which requires understanding
what each result was.

> **The book's line — "size matters but isn't the only factor" — holds up.**
>
> But state the **preconditions**: this task has 2 tools, 1 parameter each, and a
> complete format example in the system prompt. Give it lab 4-2's 40 tools, or lab
> 4-1's enum-and-unit traps, and a 0.6B would very likely fail. **"Small models can
> call tools" has a scope.**

---

## 3. I could not get the literal `<think>` tags ★

The first counterintuitive finding, worth telling in full.

### What I set out to do

The book says this experiment lets you "**directly observe the model's raw input and
output token stream**", including details "invisible at the API layer" like `<think>`.

So I thought: **it's local, surely I can see the raw form.**

### What actually happened

**Ollama parses the tags away server-side.** With `/api/chat` + `think:true` the
response looks like this:

```json
{"message": {"role": "assistant",
             "thinking": "The user asks two things...",   <- what was inside the tags
             "content": "It's 12:37 in Vancouver."}}      <- what was outside
```

**The fields are called `thinking` and `content`. The characters `<think>` appear
nowhere.**

### I tried to bypass it, and failed

Getting the true raw stream means bypassing the template layer — Ollama's
`/api/generate` has `raw: true`, where you assemble ChatML yourself. I tried:

| Attempt | Result |
|---|---|
| `<\|im_start\|>user\n...<\|im_end\|>\n<\|im_start\|>assistant\n` | Normal answer, **no `<think>`** |
| Same, with ` /think` appended to the user turn (Qwen3's switch) | **Empty string returned** |
| Same, plus pre-filling `<think>\n` on the assistant turn | **Empty string returned** |

The model's template explains it:

```
{{- if and $.IsThinkSet (eq $i $lastUserIdx) }}
   {{- if $.Think -}}{{- " "}}/think
   {{- else -}}{{- " "}}/no_think
```

Thinking mode is driven by the `IsThinkSet` **template variable** — and `raw:true`
**skips the template**, so the whole mechanism is bypassed.

### So the conclusion is

> **The assumption "local deployment lets you see the raw output" is wrong.**
>
> I expected:
> ```
> cloud API (washed)  ->  local Ollama (raw)
> ```
> The actual stack:
> ```
> the token sequence the model generates
>    | llama.cpp applies the template
> <think>...</think> + body + <tool_call>...
>    | the Ollama server parses it        <- I'm stuck at this layer
> {"thinking": ..., "content": ...}
>    | the SDK wraps it again
> response.message.content
> ```
>
> **"Raw" is layered. Whatever you think the bottom is, there's another layer below.**

This doesn't refute the book — it strengthens it. Local deployment genuinely shows
you one layer more than a cloud API (you see that thinking and content are separate,
you see the literal `TOOL:` line, you get `prompt_eval_duration`). **It just isn't
"raw".** For actual tokens you'd have to go down to llama.cpp.

💡 `agent.py`'s `raw` mode was therefore changed to **label honestly**: it prints
`[thinking]` / `[content]` tags and states plainly that **Ollama drew that line, not
the model.**

---

## 4. The KV cache experiment: from "fake success" to "honest failure" ★★★

The most important section here — an account of nearly publishing a wrong conclusion.

### Version 1: it looked like a perfect reproduction

Using the original **110-token** system prompt, three runs:

```
run 1  first time (cold)                 prefill 18 ms
run 2  identical prompt (should hit)     prefill  8 ms     <- 2.25x faster!
run 3  one char changed at the start     prefill 55 ms     <- back up!
```

**Textbook perfect.** I nearly wrote it up that way.

### But I ran it twice more

```
repeat 1:  27 ms  ->  16 ms  ->   7 ms     <- run 3 was FASTEST, opposite of the prediction
repeat 2:   8 ms  ->   8 ms  ->  10 ms     <- flat; no effect at all
```

**Three runs, three mutually contradictory conclusions.**

The cause is clear: with 110 input tokens, prefill is around **10 ms** — **entirely
buried in measurement noise**. That first "perfect" result was **luck**.

> **Lesson 1: a controlled experiment run once proves nothing.**
> And the more textbook-perfect it looks, **the more you should suspect it** —
> clean results are rare in noisy real measurements.

### Version 2: grow the prompt to 2050 tokens

With prefill at ~1000 ms cold, noise stops dominating. Redesigned into three groups:

```
A. Completely fixed system prompt, 3 runs
B. A never-seen session ID injected at the START each time
C. A never-seen session ID injected at the END each time
```

Measured (2026-07-29, consistent across repeats):

```
A  warm-up (cold)     1031.1 ms
A  run 1                20.7 ms
A  run 2                15.5 ms
A  run 3                10.1 ms

B  run 1               989.2 ms      <- slow
B  run 2                17.6 ms      <- but runs 2 and 3 are fast again
B  run 3                10.1 ms

C  run 1               997.4 ms      <- equally slow
C  run 2                37.8 ms
C  run 3                29.4 ms
```

### Conclusion: **B and C are indistinguishable**

The book — and nearly every article on KV caching — says changing the **start**
invalidates the prefix, so **B should be clearly slower than C**.

**The measurement doesn't support that.** B and C have the **same shape**: ~990 ms
on the first run, then 10–40 ms. Start or end, **no stable difference**.

Stranger still: B's runs 2 and 3 used **brand-new IDs** (REQ-9001, REQ-9002), so the
prefix genuinely differed — yet they were fast.

### ★ I later found the cause (lab 2-3 resolved it)

After writing this section I built [lab 2-3](../2-3-kv-cache/README.md),
which **reproduces the cache effect cleanly**:

```
good (fully stable prefix)          prefill 148.9 ms -> run 2   7.9 ms   <- hit, 19x faster
dynamic_prompt (timestamp at start) prefill 181.2 ms -> run 2 176.1 ms   <- NEVER hits
```

**Two independent runs agreed.**

**So why did the attempt above fail? My methodology was flawed:**

Group B used prefixes differing by only a few digits (REQ-9000, REQ-9001, REQ-9002),
and I **alternated** between the stable and variant prompts. Ollama **caches several
prefixes at once** — so while I thought I was measuring invalidation, each variant was
hitting **its own** cache entry.

Lab 2-3's `dynamic_prompt` uses a **microsecond timestamp**, making every call's prefix
**one that has never been seen**, so it **can never hit** — and the effect appears
immediately and cleanly.

> **Lesson: my failure to reproduce wasn't because the effect isn't real; it was a hole
> in my control group.** "Change the prefix" and "use a brand-new prefix every time" are
> different things, and multi-slot caching quietly rescues the first one.
>
> **Which is why "couldn't reproduce" should make you suspect the method before the
> claim** — the same lesson as labs 6-1 and 10-1.

The candidates I listed at the time are below; candidate 1 turned out to be essentially right:

### The candidates I listed at the time

1. **Ollama / llama.cpp caches several prefixes at once** — so alternating between
   prompts keeps them all cached and hides the invalidation
2. **Whether `prompt_eval_duration` faithfully reflects recomputation** on this
   version, I can't confirm
3. **The effect may require longer contexts, larger models, or a stack like vLLM**

**Candidate 1 was later confirmed by lab 2-3.** But note what 2-4 established: that
**a genuinely novel prefix never hits the cache**. It does **not** answer whether
changing the *start* differs from changing the *end* — **that position question is
still open**, and exercise 4 hands it to you.

### But the failure produced something solid

```
2050-token input, first call after cold load   ~1000 ms
every call after that                          ~10-40 ms
```

**Two orders of magnitude, reproducible every time.**

And *that* number is the real case for context engineering:

> **Longer input means pricier prefill, re-paid on every request that misses cache.**
>
> 2050 tokens costs a second. An agent running 20 rounds with a growing context
> pays that **every round**.
>
> **That is why lab 2-9 (context compaction) exists.**

> **Lesson 2: a failed experiment is not an experiment without output.**
> I failed to reproduce the prefix-position effect, but measured a 100x cold-vs-warm
> gap — which is **more useful** for engineering decisions, because it's larger,
> more stable, and easier to exploit.

---

## 5. Exercise answers

### Exercise 1 ⭐ A bigger model

`qwen3:1.7b` (~1.4GB) typically: tok/s roughly halves, thinking gets longer and
better organised, and tool calls become noticeably more reliable **on complex
scenarios** (both get simple ones right).

> Why run it yourself: **"bigger is better" is a vague claim**, and what you need is
> three concrete numbers — how much bigger, how much better, how much slower — **on
> your task**.

### Exercise 2 ⭐⭐ A task with a real dependency

With "what time is it in Vancouver? If it's past 8pm, tell me Beijing's weather", a
capable model should call **only `get_time` first**, then decide.

A 0.6B **often gets this wrong** — it tends to fire both.

> This confirms lab 1-1's conclusion: **dependencies are handled at the prompt layer,
> not validated by code.** And **judging dependencies correctly is one of the
> clearest gaps between small and large models**, because it requires a conditional
> reasoning step before acting.

### Exercise 3 ⭐⭐ Turn thinking off

`think=False` is noticeably faster (a hundred-odd fewer tokens generated), and on
this simple task the tool calls are **usually still correct**.

> State it precisely: **not "thinking is useless", but "this task is too simple to
> need it".** Thinking's value grows with task complexity. Using a simple task to
> prove thinking is useless is the same error this repo keeps catching (labs 1-3, 4-2).

### Exercise 4 ⭐⭐⭐ Dig out the *position* effect

**Current status** (I built lab 2-3 after writing this):

| Question | Status |
|---|---|
| Does a brand-new prefix hit the cache? | **Resolved**: no. Lab 2-3 reproduces it cleanly (149ms → 7.9ms vs 181ms → 176ms) |
| Does changing the **start** differ from changing the **end**? | **Still open** ← yours to try |

The most promising directions, in order:

| Direction | Why it might work |
|---|---|
| Grow context to 8k–16k | The effect scales with length while noise doesn't → better SNR |
| Use **never-repeated** fresh prefixes | Rules out "several prefixes are all cached" |
| Try vLLM | Its PagedAttention / prefix caching is entirely different from llama.cpp's |
| Measure the **distribution** of end-to-end TTFT (20 runs, take the median) | Sidesteps `prompt_eval_duration`, which I don't fully trust |

**If you reproduce it, that's a real finding.**

> This episode already taught one lesson: **my first "couldn't reproduce" turned out
> to be a hole in my control group** (several prefixes were all cached), not an
> absent effect.
>
> So the order is: **suspect the method before the conclusion.** Had I written
> "this claim doesn't hold in practice" at that point, I would have been **wrong**.
>
> But don't overcorrect either — **both errors are worth guarding against:
> credulity, and premature dismissal.**

> ### ★ Follow-up: the position effect does reproduce, in lab 2-3
>
> When this section was written I had not managed to reproduce "change the start vs
> change the end." [Lab 2-3](../2-3-kv-cache/SOLUTION.md) later did, using
> **interleaved measurement** (one request per prefix variant per round, flattening
> time out as a variable):
>
> ```
> change at token 0        slow in 32/32 rounds, ~190 ms
> change at ~token 200     slow in 22/32, and only ~125 ms when slow
> ```
>
> **The reason it failed here is precisely the missing interleaving**: two prefixes sent
> alternately, each hitting its own cache slot. So this section's "couldn't reproduce"
> was **again a method problem, not an effect problem** — the same flaw, twice, on the
> same backend.
>
> To verify yourself: `cd ../2-3-kv-cache && python3 agent.py cache`

### Exercise 5 ⭐⭐⭐ Ollama's native tools parameter

Switch to native `tools` and the `TOOL: {...}` line **disappears** — it becomes a
`message.tool_calls` array in the response JSON.

The upside is a more reliable format (the server guarantees valid structure); the
cost is that **you see one layer less**.

> Which is this lab's theme demonstrating itself again:
> **every layer of abstraction you add is one more thing you stop being able to see.**
>
> And the trade is usually worth it — **provided you know what you traded away.**
> Making you know is the entire point of this lab.

---

## 6. Where this sits in the repo

This lab is the only one that looks **downward**.

The other 14 ask "**how should I use** this model". This one asks "**what is
underneath** it".

Both matter, but the second is the one people skip — because you can build without
it, right up until you need to optimise latency, debug a strange format error, or
judge whether a piece of technical folklore is actually true.

**And it leads directly into the rest of chapter 2:**

```
2-0 (this lab)    measures: longer input -> pricier prefill    <- the problem
2-1 Compaction    ->  so make the context shorter              <- one answer
2-2 Injection     ->  but shorter isn't safer
2-3 Redaction     ->  and it isn't the same as putting in what belongs
```

---

← [back to the chapter](../README.md) · [back to the index](../../../README.md)
