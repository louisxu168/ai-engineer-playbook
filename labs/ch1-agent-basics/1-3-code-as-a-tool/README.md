# Lab 1-3: Letting the agent write code to think

**English** · [简体中文](README.zh-CN.md)

> **What you'll learn**
>
> 1. What a Deep Research loop looks like: `search → read → write code → search again`
> 2. Why you give an agent a code tool — and it is **NOT "because it can't do arithmetic"**. Modern models are far better at mental math than you'd guess.
> 3. The real reason is **verifiability**: code can be copied out and re-run by someone else. A prose derivation cannot.
>
> **How to work through it**: predict → run → compare. This lab has a quirk —
> **your predictions will probably be wrong in the "it's stronger than you
> thought" direction.** That's the point.
>
> **Time**: 15 minutes for the core, about 45 for everything.
>
> Do [1-1](../1-1-context/) and [1-2](../1-2-who-runs-the-tool/) first.

---

## Step 0: Run the full deep-research loop (8 min)

### 🔧 Do this

```bash
cd labs/ch1-agent-basics/1-3-code-as-a-tool
python3 agent.py deep
```

It asks what you want researched. Press Enter for examples, then type a number
(e.g. `1`) to pick one:

```
What is the average height of the world's 5 tallest buildings? By what
percentage does the tallest exceed that average?
```

**No `pip install`, no API key.**

> Output is Chinese by default. Set `LANG = "en"` at the top of `agent.py`.

### 👀 What to watch

This lab has one thing the previous two didn't: **it writes code.**

```
  [tool] run_python
  +- the code it wrote --------------------
  │ h = {'Burj Khalifa': 829.8, 'Merdeka 118': 678.9, ...}
  │ avg = sum(h.values())/len(h)
  │ print('average =', round(avg,2))
  │ print('pct above avg =', round((max(h.values())-avg)/avg*100,2))
  +---------------------------------------
        -> {'stdout': 'average = 668.16\npct above avg = 24.19'}
```

Also watch the *shape* of the loop: it does **not** gather everything and then
compute. It searches, finds a gap, searches again, then computes. That's the
deep-research loop.

### ✅ Write two things down

| | Your baseline |
|---|---|
| What number did it produce? | ___ |
| How many code blocks did it write? | ___ |

---

## Step 1: Predict, then take the code tool away (10 min)

### 🤔 Predict (most people get this wrong)

We're removing `run_python`, so it must do the arithmetic in its head. Guess:

- Will it still get it right? ___
- How likely is an error, do you think? ___

### 🔧 Do this

```bash
python3 agent.py no_code "(paste the SAME question)"
```

### 💡 What you learned

If you predicted "it'll get it wrong" — so did I, and we were both wrong.
**It got it right**, to the decimal.

I also ran a harsher check: 20 three-digit decimals, mental math only, asking
for the median and population standard deviation. It answered
`518.65, 93.94`; the truth is `518.65, 93.9437`. **Correct.**

> **So "the model can't do arithmetic" is not the reason to give it a code tool.**
> This lab was originally designed around that assumption. Testing falsified it,
> so I rewrote the lab.

The real reasons are these three:

| Reason | What it means |
|---|---|
| **You can't verify it** | A prose derivation must be redone by hand; code can be copied and run |
| **Changing assumptions is expensive** | With code, edit one number and re-run; without, redo everything |
| **It doesn't scale** | 20 numbers fits in its head; 20,000 log lines does not |

Reason two **showed up on its own** during testing: is Burj Khalifa 829.8 m
(with antenna) or 828 m (roof)? **The run with a code tool computed both. The
run without it did not.** See SOLUTION.md.

---

## Step 2: Take `read` away and watch it cope (8 min)

### 🤔 Predict

Only `search` (snippets), no `read` (no article bodies). Guess:

- Can it still get the five heights? ___
- If not, what will it do? ___

### 🔧 Do this

```bash
python3 agent.py no_read "(same question)"
```

### 👀 What to watch

**Pay close attention to what happens between round 2 and round 3.**

### 💡 What you learned

Another one most people get wrong. Half a spoiler: it does **not** simply fail.

Run it and see what it does instead — this is the single most worthwhile thing
to watch in this lab. (Section 4 of SOLUTION.md if you can't work it out.)

---

## Step 3: Compare against hosted (5 min)

```bash
python3 agent.py hosted "(same question)"
```

The answer is good again. But ask: **which figures did it use? How did it
combine them?**

Same as lab 1-2 — you can't say. **"You can't verify it" applies in full.**

---

## Step 4: Change it yourself (exercises)

**Predict each before running.**

### Exercise 1 ⭐ Ask for more data points

E.g. the world's 10 tallest buildings.

**Predict**: will the three modes start to disagree?

### Exercise 2 ⭐⭐ Set `CODE_TIMEOUT` to 1 second

**Predict**: what does the model do when it's told its code timed out?

### Exercise 3 ⭐⭐ Make `run_python` return a fake result

Always return `{"stdout": "42"}`.

**Predict**: will it notice?

> Hint: lab 1-1's "make `get_rate` return 999" and lab 1-2's "make search return
> stale data" asked the same question. Remember the answer?

### Exercise 4 ⭐ Count the safety measures

How many lines in `run_python` actually prevent the model from writing something
dangerous?

**That number should make you slightly uncomfortable.** Then read the ⚠️ comment
in the code.

### Exercise 5 ⭐⭐⭐ Build a big dataset

Write a few-thousand-row CSV, add a tool that lets the agent read it, then ask a
question that needs statistics over it.

**This is the empirical test of the "scale" reason** — `no_code` will simply tell
you it can't.

---

## Check your answers

**[SOLUTION.md](SOLUTION.md)** — full transcripts (**readable without running
anything**), both surprising findings explained, and all exercise answers.

---

## ⚠️ Safety: `run_python` is not a sandbox

This lab **executes model-generated Python**. All we add is a timeout — that is
nowhere near a sandbox, and the code can still read and write your files.

Here the model only ever writes arithmetic over figures it already fetched, so
the risk is low. But:

> **Never run model-generated code this way in a real project.**
> Put it in a container (Docker / gVisor / Firecracker) with no network and no
> filesystem access.

The book's version uses OpenAI's hosted `code_interpreter` — the sandbox lives at
the provider. We have no hosted sandbox, so this is a deliberately simplified
teaching version, and the code says so.

---

## Appendix: concept reference

### The deep-research loop

```
search → read → analyse with code → notice a gap → search again → …
```

It is **the same loop** as lab 1-1's ReAct loop, with one more tool. By now you
should be able to confirm: **all three labs run the same machinery; only the
tools changed.**

### What the three tools do

| Tool | Job | Phase |
|---|---|---|
| `search(query)` | find leads | retrieval |
| `read(title)` | get actual figures | retrieval |
| `run_python(code)` | compute, compare, sort, aggregate | **analysis** |

The first two retrieve; the third analyses. **This lab is about the third.**

### The three labs together

| Lab | Question | Conclusion |
|---|---|---|
| 1-1 | What is context? | A string you assembled yourself |
| 1-2 | Who runs the tool? | Choosing hosted costs you observability |
| 1-3 | What does it compute with? | Choosing code buys you reproducibility |

**1-2 and 1-3 are two sides of one thing: you want a process that can be checked.**

---

## Stuck?

| What you see | What to do |
|---|---|
| `x No usable backend found` | Install any one of the three options it prints |
| Hit 16 rounds with no answer | Normal — deep research is slow. Try a question with easier-to-find data |
| `the code ran longer than 15s` | It wrote a loop or something heavy; it usually rewrites and retries |
| Forgot the commands | Run `python3 agent.py` with no arguments |
