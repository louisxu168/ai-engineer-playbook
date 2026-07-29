# Lab 10-1 answers: one agent vs many

**English** · [简体中文](SOLUTION.zh-CN.md)

> ⚠️ Try it first. Being wrong once beats reading this ten times.

---

## 1. Measured data

Backend: Claude Code (`claude -p`), measured 2026-07-28.

| Mode | Recall | Obvious | Subtle | False pos. | Calls |
|---|---|---|---|---|---|
| **single** | **8/8** | 4/4 | 4/4 | **0** | **1** |
| chunked | 8/8 | 4/4 | 4/4 | 0 | 4 |
| specialists | 8/8 | 4/4 | 4/4 | **2** | 4 |
| critic | **7/8** | 4/4 | **3/4** | 0 | 2 |

**The single agent is no worse on any column, at the lowest cost.**

- `chunked`: identical result, **4× the cost**
- `specialists`: same recall, **2 extra false positives**, still 4× the cost
- `critic`: **lost a real finding**, at 2× the cost

**Not one of the four patterns beat single.**

---

## 2. Why: the single agent had already saturated

This is the key to everything above:

> **single scored 8/8. That's the ceiling.**
>
> No matter how many agents you add or how you arrange them, **recall tops out at
> 8/8**. The only things left that can change are: **more false positives**, or
> **more cost**.
>
> Both happened.

So the teaching point isn't "multi-agent is useless". It's:

> **Before adding agents, measure whether one agent has already saturated.**

That step is nearly always skipped. The usual sequence is: ship multi-agent → it
works well → credit the architecture. **Nobody goes back to check whether one agent
could have done it.**

Exercise 1 is about **raising the ceiling** (grow to ~100 snippets) and finding the
point where single starts missing — **that point is where multi-agent begins to
matter.**

---

## 3. `specialists`' 2 false positives: hammer, meet nail

`specialists` reported **S22** and **S23**:

```python
# S22
def send_report(to):
    body = render_template("report.html", data=fetch())
    mailer.send(to, body)

# S23
def parse_dates(rows):
    return [datetime.strptime(r["d"], "%Y-%m-%d") for r in rows]
```

Neither has any of this lab's four defined problems. So why were they reported?

**Look at what each specialist reported and it becomes obvious:**

```
  [agent 1/4] SQLI     reported 2: S01, S09                                <- perfect
  [agent 2/4] SECRET   reported 2: S03, S11                                <- perfect
  [agent 3/4] PATH     reported 2: S05, S14                                <- perfect
  [agent 4/4] INPUT    reported 8: S01, S05, S07, S09, S14, S15, S22, S23  <- !
```

**Three specialists were flawless. Every false positive came from the fourth.**

And the INPUT specialist didn't merely add 2 false positives — it also reported
S01, S05, S09 and S14 (which belong to the SQLI and PATH categories) **despite the
prompt explicitly saying "report only this category"**. Only S07 and S15 are
genuinely INPUT. It reported 8.

**Why that one?** Because the four categories differ enormously in **crispness**:

| Category | Test for it | Specialist |
|---|---|---|
| SQL injection | Is a variable concatenated into SQL? | precise |
| Hardcoded secret | Is a credential written in the source? | precise |
| Path traversal | Is the path confined to a directory? | precise |
| **Unvalidated input** | **…what counts as "validated"? validated *enough*?** | **4× over-reporting** |

> **The specialist pattern's failure concentrates on whichever specialist has the
> vaguest definition.**
>
> The first three can be settled in one sentence. The fourth can't — strictly,
> **any** external input can be called insufficiently validated. So that specialist
> found what it was told to find, because there is always something to find.

The prompt it received was:

```
You are a code security reviewer, and this pass covers one category only:
**Unvalidated input: an externally supplied value used directly, with no
type/range/allowlist check**
Below are several code snippets... Report only this category.
```

> **That prompt implicitly asserts: there are unvalidated-input problems here.**
>
> So the agent looked, and **found some** — `strptime` really can throw on bad
> format, `render_template` really does handle external data. Not nonsense, just not
> this task's definition of a problem.

The crucial part:

> **This failure is manufactured by the prompt, not a fixed defect of the model.**
> Lock someone in a room and say "today you only hunt path traversal" and they will
> struggle to hand back a blank sheet.
>
> **And it only happens when your category definition is vague** — which you can
> judge in advance: **if you can't state in one sentence what counts, don't assign
> a dedicated specialist to it.**

### By contrast: `chunked` produced no false positives

Same 4 agents, same 4 calls — but each `chunked` agent received the **complete
four-category definition**, just less code. Nothing implied "your category is
definitely present here."

> **Same cost, different cut, completely different failure mode.**
>
> That's multi-agent's real design question: **not "how many" but "along which
> axis"** — and every axis comes with its own characteristic way of breaking.

---

## 4. `critic`'s fatal cut: right reasoning, inverted conclusion ★

The best moment in this lab.

Stage one (single) found all 8. In verification, it marked **S14 a false positive**:

```python
# S14 (a genuine path traversal)
def download(name):
    target = os.path.normpath(os.path.join(BASE, name))
    return send_file(target)
```

The verifier's stated reason, **verbatim** (translated):

> **"normpath only normalizes the path; it does not check the result is still
> within BASE, so `../` can still escape — but categorically this IS a real
> problem"**

**Read that three times.**

It states:
1. `normpath` normalizes but doesn't validate ✓ correct
2. The result isn't checked against BASE ✓ correct
3. `../` can still escape ✓ correct
4. **"but categorically this IS a real problem"** ✓ it says so itself

**And then it set `decision` to `drop`.**

> **Every step of the reasoning right, the conclusion inverted.**

Recall fell from 8/8 to 7/8, subtle from 4/4 to 3/4. **An extra call made the result
worse.**

### Why

The verifier's job definition is asymmetric:

> It was asked to **find the false positives**.
>
> An agent dispatched to find false positives **tends to find false positives** —
> the same mechanism as the over-reporting specialist above, pointed the other way.

And there's a structural property that matters more than this particular bug:

> **A verifier can only remove, never add.**
>
> Anything stage one missed is **permanently** unrecoverable. So its expected gain
> is "fewer false positives" and its expected risk is "deleting a real finding".
>
> **When stage one had no false positives to begin with (exactly this lab), the
> expected gain is 0 and the expected risk is positive.** Pure loss.

### The fix

Exercise 4's direction: **replace deletion with downgrading.**

```python
# not: keep / drop
# instead: high-confidence / low-confidence - keep both, change only the ranking
```

> **Irreversible deletion goes to a human; the agent only ranks.**
>
> Same idea as lab 4-1's idempotency key: **don't let an agent do irreversible
> things**, especially when its judgement carries a systematic lean.

---

## 5. I got the ground truth wrong, and the models caught it ★★

This section matters more than everything above.

**On the first run**, both `chunked` and `specialists` reported **S13**, and my
ground truth said S13 was safe. The program dutifully labelled it "☠ false positive".

S13 looked like this:

```python
def export(path):
    target = os.path.join(EXPORT_DIR, path)
    if not target.startswith(EXPORT_DIR):
        raise ValueError("bad path")
    return open(target, "w")
```

My thinking at the time: "there's a `startswith` check, it's safe."

**I was wrong.** Verified:

```
path                 old check passes   join result                    fixed version passes
report.csv           True               /export/report.csv             True
../etc/passwd        True               /export/../etc/passwd          False   <- there it is
../export_evil/x     True               /export/../export_evil/x       False
```

`os.path.join` **does not normalize paths.** `/export/../etc/passwd` genuinely does
start with `/export`, the check waves it through, and `open()` then resolves it to
`/etc/passwd`.

**That is a real path traversal vulnerability. The models were right and my ground
truth was wrong.**

I rewrote S13 to be genuinely safe:

```python
target = os.path.realpath(os.path.join(EXPORT_DIR, path))
if os.path.commonpath([target, EXPORT_DIR]) != EXPORT_DIR:
    raise ValueError("bad path")
```

The table at the top is from the re-run.

### The lesson

> **When your evaluation disagrees with the thing being evaluated, suspect the
> evaluation first.**

That isn't modesty, it's probability:

- Your ground truth was written by **one person** in **one afternoon**
- The model under test has seen **an enormous amount** of security code and CVEs

**On "who is more likely to misremember `os.path.join`'s semantics", betting on the
model is the better bet.**

And there's a sharper signal:

> **If several independent agents report the same "false positive", it probably
> isn't one.**
>
> Here, `chunked`'s third shard agent and `specialists`' PATH specialist reported
> S13 **independently**. Two non-communicating agents reaching the same conclusion
> is itself strong evidence.

This continues lab 6-1's theme directly:

| Lab | The trap I hit |
|---|---|
| 6-1 | A JSON parse failure recorded as "the model is unstable" — **an instrument failure recorded as a subject defect** |
| **10-1** | **Wrong ground truth recorded as "the model over-reported" — the same error, different shape** |

> **Write tests for your evaluator before you blame the thing it's evaluating.**

⚠️ Also worth noting: this was catchable only because **the verdict is mechanical
and the results are itemised.** Had I used "ask another model for an overall
score", S13 would have been smoothed away and I would never have found it.
**Interpretable verdicts aren't only for human comprehension — they're what lets
errors surface.**

---

## 6. Exercise answers

### Exercise 1 ⭐⭐ Manufacture headroom

Grow to ~100 snippets (copy clean ones, rename things) and single usually starts
missing.

**That point is where multi-agent starts to matter.**

At that point you'll see what this lab couldn't show:

| Mode | Expected once headroom exists |
|---|---|
| `chunked` | Recall should rise — attention no longer diluted across 100 snippets |
| `specialists` | Recall should also rise, and the **subtle** items should gain most |

> But note: **their gains come from different sources.**
> `chunked` addresses "too much to look at";
> `specialists` addresses "can't hold four concerns at once".
>
> **Which bottleneck your task has determines which axis you should split on.**

### Exercise 2 ⭐⭐ Build a cross-snippet problem

Add:

```python
# S25
DEBUG_TOKEN = "dbg-7c2a"                            # alone: a hardcoded secret

# S26
logger.info("auth attempt with %s", DEBUG_TOKEN)    # alone: just logging
```

The real incident is the **combination**: the secret reaches the log, which gets
shipped, indexed and searched.

Split across `chunked` agents, it becomes **structurally invisible**.

> **Not bad luck. The cut through the data severed the possibility of that
> discovery.**
>
> Generalized: **splitting by data implicitly assumes problems are local.** In code
> review, log analysis and compliance checking, that assumption **often doesn't
> hold.**

### Exercise 3 ⭐⭐ Tell specialists that finding nothing is fine

False positives usually drop.

If they do, it confirms section 3's diagnosis:

> **Over-reporting is manufactured by the prompt's implicit expectation, not a
> fixed model defect.**

Generalizes to any classification/detection prompt:

> **Explicitly tell the model that an empty result is valid, normal, and not a
> failure.**
>
> Leave it unsaid and it defaults to "you asked me to look, so there must be
> something."

### Exercise 4 ⭐⭐⭐ Verifier downgrades instead of deleting

With high/low confidence, **recall doesn't drop** (nothing is removed) and you still
gain ranking information — the genuinely suspicious items sort to the top.

The cost: **you haven't reduced how many items a human must read.**

> **That's the trade in its essential form:**
> - Let the agent delete → saves human effort, but deletes wrongly, and **the
>   deletion is silent**
> - Let the agent rank → doesn't reduce the count, but **loses nothing**, and a
>   human sees the priorities immediately
>
> Where **the cost of a miss >> the cost of reading a few extra items** (security,
> medicine, compliance), **always choose ranking over deletion.**

### Exercise 5 ⭐⭐⭐ Combine all three

specialists (4) + critic (1) + merge ≈ 6 calls.

Expected: recall 8/8 (specialists already saturated), some false positives cleaned
by the critic — but **it may also delete a real finding, exactly as it did here.**

**When you're done, compare against the `single` row: you spent 6× as much — what
did you buy?**

> If the answer is "nothing", **congratulations — you just measured this lab's most
> important lesson yourself.**
>
> And it generalizes well beyond multi-agent:
> **any architectural complexity should first prove the problem it solves is real.**

---

## 7. Back to the whole picture

This is the fifth time this repo has produced the same shape:

| Lab | Cheap, "weak" approach | Expensive, "strong" approach | Measured |
|---|---|---|---|
| 2-1 | No compaction | Compaction | Both cost something |
| 3-2 | Paste everything | Retrieve first | Retrieval missed things |
| 4-2 | All tools | Retrieved tools | **Retrieval missed; all-tools didn't** |
| 5-1 | Whole-file rewrite | Diff editing | 8× cost gap, no reliability gap |
| **10-1** | **1 agent** | **4 agents** | **1 agent was better** |

**The pattern is remarkably consistent:**

> **The "more sophisticated" approach always brings new failure modes, and the
> benefit it promises has a precondition — which may not hold.**
>
> So the order should be:
> 1. Use the simplest approach and **measure its ceiling**
> 2. Confirm the ceiling is actually blocking you
> 3. **Then** add complexity, and **measure the new failures it introduces**

Across this repo's five "simple vs complex" comparisons so far, **simple won three
times.**

That doesn't mean the sophisticated approaches are useless — it means **their
preconditions are narrower than advertised**, and **you're capable of measuring
that yourself.**

---

← [back to the chapter](../README.md) · [back to the index](../../../README.md)
