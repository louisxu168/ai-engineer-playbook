# Lab 5-1 answers: three edit formats

**English** · [简体中文](SOLUTION.zh-CN.md)

> ⚠️ Try it first. Being wrong once beats reading this ten times.

---

## 1. Measured data

Backend: Claude Code (`claude -p`), measured 2026-07-28.

### `fix` task (1 site, 2 lines)

| Format | Tests | Rounds | Model output | Failed edits |
|---|---|---|---|---|
| `whole_file` | ✓ 20/20 | 1 | **3204 chars** | 0 |
| `search_replace` | ✓ 20/20 | 1 | **411 chars** | 0 |
| `line_range` | ✓ 20/20 | 1 | **265 chars** | 0 |

### `refactor` task (8 sites, 7 with near-identical context)

| Format | Tests | Rounds | Model output | Failed edits |
|---|---|---|---|---|
| `whole_file` | ✓ 29/29 | 1 | **3413 chars** | 0 |
| `search_replace` | ✓ 29/29 | 1 | **1603 chars** | 0 |
| `line_range` | ✓ 29/29 | 1 | **1194 chars** | 0 |

**Six runs, all passing in one round, zero failed edits, and all three formats
produced identical code.**

---

## 2. The most valuable number here: how cost grows

The two tasks side by side:

| Format | fix | refactor | **growth** |
|---|---|---|---|
| `whole_file` | 3204 | 3413 | **1.07×** ← barely moved |
| `search_replace` | 411 | 1603 | **3.9×** |
| `line_range` | 265 | 1194 | **4.5×** |

**The edit got 8× bigger and `whole_file` grew 6.5%.**

Because it emits **the whole file** — changing 2 lines and changing 20 lines produce
almost identical output.

Which gives the rule most worth remembering:

> ```
> whole_file      cost ~ O(file size)     independent of edit size
> search_replace  cost ~ O(edit size)     independent of file size
> line_range      cost ~ O(edit size), smaller constant
> ```

### Corollary: there's a crossover

Look at the two ratios:

```
fix task:       whole_file / search_replace = 7.8x
refactor task:  whole_file / search_replace = 2.1x
```

**The bigger the edit, the smaller the diff formats' advantage.** Push it far enough
— when the edit approaches the whole file — and `whole_file` wins (and is safer).

Pushing the other way is more interesting. The file here is only **130 lines**. Real
source files run to hundreds or thousands.

```
130-line file, 2-line edit    -> whole_file costs 7.8x more
2000-line file, 2-line edit   -> whole_file costs roughly 100x more
```

And it's **re-paid every round** — one bad edit, tests fail, try again, and
`whole_file` re-emits the entire file.

> **Which is why real products default to diff formats** (Aider, Claude Code,
> Cursor), reserving whole-file output for new files and large rewrites.
>
> **Not because diffs are more accurate, but because in the "big file, small edit"
> normal case they're an order of magnitude cheaper.**

---

## 3. Reliability: how each format breaks

None of this **showed up in the measured runs** (zero failures), but you need to know
it, because it determines what happens when things do go wrong.

### `whole_file`: basically can't fail

It supplies the final result and we write it straight out. The only failure is "it
didn't give a content field".

The cost is a different risk: **it may change things you didn't ask about**. It
rewrote the entire file, so every unrelated line passed through its hands. The diff
in this lab shows it didn't — but the risk is structural.

> That's what `show_diff()` is for in this lab — **always look at what it actually
> changed.**

### `search_replace`: can fail, but **always says so**

From `apply_search_replace()`:

```python
count = text.count(old)
if count == 0:
    return None, t("err_old_missing", i=i + 1)              # copied it wrong
if count > 1:
    return None, t("err_old_ambiguous", i=i + 1, n=count)   # not unique
```

Both failures **explicitly reject and tell the model why**, and it corrects on the
next round.

Which is lab 4-1's conclusion applied here: **a good error message is the next
turn's prompt.**

### `line_range`: can fail, and **may not say so** ☠

```python
lines[start - 1:end] = new.split("\n")
```

Off by one and that line still "succeeds" — it just edits the wrong place.

- `whole_file` wrong → loud error
- `search_replace` wrong → loud error
- **`line_range` wrong → silently corrupts the code**

It has one more hazard: **with several edits at once, earlier edits shift every
later line number.** So `apply_line_range()` **must** iterate backwards:

```python
# iterate backwards, or earlier edits shift all the later line numbers
ordered = sorted(range(len(edits)),
                 key=lambda i: edits[i].get("start", 0), reverse=True)
```

**That line isn't an optimization, it's a requirement.** Forget it and multi-site
edits corrupt silently.

> **The principle to take away:**
>
> **Make it impossible for errors to happen quietly.**
>
> `search_replace` beats `line_range` not because it's cheaper or more accurate,
> but because **when it's wrong, it always tells you.**

---

## 4. Honest disclosure: the reliability difference didn't reproduce

I designed the `refactor` task specifically to force `search_replace`'s
"old isn't unique" failure — those 7 sites look like this, differing only in a
function name inside a string:

```python
    if len(numbers) == 0:
        raise ValueError("mean() 需要至少一个数")
```

**The model never tripped.** It included the function name in `old`, which made it
unique automatically.

`line_range` edited 8 sites and never miscounted a line.

**Two tasks × three formats = 6 runs, zero failed edit applications.**

> The widely repeated claim that diff formats mismatch **did not reproduce at this
> scale.**

That doesn't mean it isn't real. It's likelier with:

- **Bigger files** (larger line numbers, easier to miscount)
- **More edit sites** (more chances to drift)
- **Weaker models** (most likely cause — these formats demand instruction-following
  discipline)
- **Genuinely duplicated code** (the 7 sites here aren't *identical*; the function
  names did a lot of work)

**Exercise 1 sends you to find the boundary.** Write down what you find.

> That's the 7th falsified expectation in this repo. From 1-1's `no_history` to
> 4-2's "too many tools", the pattern holds:
> **received wisdom about what models *can't* do expires faster than you'd think.**
>
> Whereas **conclusions about cost are far more stable** — they're set by
> arithmetic, not by model capability. Which is why the cost-growth table is the
> part of this lab worth memorizing, not the reliability section.

---

## 5. A detail worth noticing: it didn't over-replace

`refactor` asks to convert the "empty input" ValueErrors to `EmptyDataError`.

`stats.py` contains **9** `raise ValueError(` statements, but only **7** should
change. The other two are:

```python
    if not (0 <= p <= 100):
        raise ValueError("p 必须在 0 到 100 之间")      # percentile: bad argument range

    if window <= 0:
        raise ValueError("window 必须是正整数")          # moving_average: bad argument
```

**Neither is about empty data, so neither should be touched.**

Measured, all three formats **changed exactly the right 7**:

```
whole_file       EmptyDataError appears 8x (1 class def + 7 raises), ValueError( remaining: 2 ✓
search_replace   same ✓
line_range       same ✓
```

> A script doing string replacement would have changed all 9.
> **The model was matching the semantics of "which errors are about empty data",
> not "which strings look alike".**
>
> That's the actual value of "let a model edit code" over "write a regex" — and
> incidentally it explains why a format like `search_replace`, which demands
> **semantic localization**, isn't hard for a model.

---

## 6. Exercise answers

### Exercise 1 ⭐⭐ Push it until something fails

I didn't succeed, so these are **directions**, not answers:

| Direction | Why it might work |
|---|---|
| Grow the file past 500 lines | Bigger line numbers are easier to miscount; `old` collides more |
| Delete "the file is shown with line numbers" from the prompt | Forces it to count lines itself — `line_range`'s weakest point |
| Create genuinely duplicated blocks (same function names too) | The only way to really force `old` ambiguity |
| Try a smaller model (`LAB_BACKEND` + an API key) | **Most likely to work** — format discipline correlates strongly with model strength |

That last one deserves emphasis. **"Format reliability" findings are really
measuring instruction-following**, so they necessarily move with model strength. When
choosing a format for your own project, test it with **the model you'll actually
ship**, not by copying any article — including this one.

### Exercise 2 ⭐ Let it cheat

With `check_path()`'s block removed, the model **most likely still won't** touch the
test file — because the system prompt still says not to change test expectations.

**And that's exactly the point:**

> You currently have **two lines of defence**: the prompt says it, and the code
> enforces it. Removing one and surviving **doesn't mean that defence was useless** —
> it means you didn't hit the case that needed it this time.
>
> Lab 4-1's conclusion, restated:
> **a constraint you can enforce at the interface shouldn't live only in the prompt.**

To actually see reward hacking, also delete that sentence from the prompt *and*
swap in a bug that's genuinely hard to fix. The temptation only appears once
"edit the test" is much easier than "fix the bug".

⚠️ Which is the real-world lesson too: **when an agent finds that bypassing the
grader is easier than satisfying it, it will bypass it.** So either make the grader
hard to tamper with (read-only, run in another process, run in CI), or don't rely
on it.

### Exercise 3 ⭐⭐ Add a fourth format: unified diff

It lands between `search_replace` and `line_range`, **closer to `search_replace`**:

```
                cost        on error
line_range      lowest      may corrupt silently
unified diff    middle      loud (context mismatch -> patch fails)
search_replace  middle      loud
whole_file      highest     basically never errs
```

The key is that a unified diff carries **both line numbers and original context**:

```diff
@@ -24,1 +24,3 @@
     ordered = sorted(numbers)
-    return ordered[middle]
+    if len(ordered) % 2 == 0:
```

The line number locates quickly; **the context verifies the location is right.** If
the number is off but the context matches, standard `patch` searches nearby (fuzz);
if the context doesn't match, it fails outright.

> **It trades redundancy for error detection.** Which is why it has survived forty
> years of engineering practice.
>
> Generalized: **any addressing mechanism should carry verifiable redundancy**, so
> that a wrong address is detected rather than quietly applied.

### Exercise 4 ⭐⭐⭐ Let the model choose the format

It generally picks: **diff formats for small edits, `whole_file` for new files and
large rewrites** — i.e. real products' strategy.

But the second question matters more: **how would you verify it chose well?**

The difficulty: **choosing the wrong format doesn't cause failure, only expense.**
Tests still pass, monitoring shows nothing unusual, and only the bill slowly grows.

> **This is a particularly hard class of problem: no error, just waste.**
>
> The only defence is to **measure cost as a first-class metric** — exactly what
> this lab does. If your agent system isn't recording "tokens per task", you will
> never notice this kind of regression.

### Exercise 5 ⭐⭐⭐ Turn the tests from verdict into tool

Give the model a `run_tests()` tool and the typical behaviour is: **run after every
single edit.**

Two changes, one good and one bad:

| | Change |
|---|---|
| ✓ | It **discovers its own mistakes** without waiting to be told — especially valuable for multi-step edits |
| ✗ | More rounds, more tokens, and it may **re-run when there's no need** |

> **The real question is: who triggers the feedback?**
>
> - Program-triggered (this lab): controlled, cheap, but you set the rhythm
> - Model-triggered (the exercise): flexible, self-correcting, cost unbounded
>
> Look back at lab 1-2 — hosted vs DIY is **the same question in another form**:
> **however much control you hand over, you hand over exactly that much
> predictability.**

---

## 7. Putting this lab back in context

The `whole_file` vs diff choice looks like a token-saving question. It's actually
the same thing this repo keeps circling:

| Lab | Give less vs give everything |
|---|---|
| 2-1 Compaction | summary vs full text |
| 3-2 Retrieval | top-k vs all memories |
| 4-2 Tools | retrieved tools vs all tools |
| **5-1 Editing** | **diff vs the whole file** |

**Four instances of one shape:**

> **"Give everything" is expensive but reliable. "Filter first" is cheap but
> introduces a new failure mode.**

And the deciding question is the same each time:

> **First ask how bad your cost problem is; then decide whether it's worth buying a
> new failure mode.**

The only difference here is that this new failure mode is especially nasty —
**`line_range` is the only one of the four whose failure may not report itself.**
So it should rank lower than its cost alone would suggest.

---

← [back to the chapter](../README.md) · [back to the index](../../../README.md)
