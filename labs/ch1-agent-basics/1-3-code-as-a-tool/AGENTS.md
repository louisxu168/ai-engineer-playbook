# TA notes — Lab 1-3

Read the repo-root `AGENTS.md` first. This file is specific to this lab.

## What this lab actually teaches

**Not** "models can't do arithmetic". That premise was tested and **falsified** —
see SOLUTION.md §2. Teaching it would be teaching something false.

The real lesson:

> **You give an agent a code tool for verifiability, not for accuracy.**
> Code can be copied out and re-run by a third party. A prose derivation cannot.

Plus the emergent one, which is the best thing in this lab:

> **With a code tool, the model volunteers a sensitivity check** (it computed
> Burj Khalifa at both 829.8 m and 828 m unprompted). Tools change what a model
> is *willing* to do, not just what it *can* do.

## Two surprises — these are the lab, not bugs

Both will very likely reproduce for the learner. **Do not "fix" them, and do not
spoil them.**

1. **`no_code` gets the right answer.** Ask: *"you predicted it would get this
   wrong. It didn't. So what IS the code tool actually buying you?"* Let them
   arrive at "I can't check the prose version" themselves.

2. **`no_read` doesn't fail either — it routes around the limit** by crafting
   queries with `height metres` in them so the figures land in the snippets.
   Ask: *"look at rounds 2 and 3. What changed, and why?"*

   Follow-up worth making explicit: **this is why ablation studies are hard.**
   You removed one capability and it compensated with another, so you measured
   something other than what you intended. Same phenomenon as lab 1-1's
   `no_history` smuggling state through `reasoning`.

If the learner is frustrated that "nothing broke", that's the moment to make the
meta-point: **predict → measure → admit you were wrong** is the actual skill.

## Safety — raise this proactively

`run_python` executes model-generated code with only a timeout. That is **not** a
sandbox. If a learner starts extending it (exercise 5, adding file access), say
plainly that real projects need container isolation. The code carries a ⚠️
comment; point at it.

Do not help anyone remove the timeout.

## Things you can just fix

- Backend detection, dependencies, Python version
- Runs that hit the 16-round cap (suggest a question with easier-to-find data)
- Wikipedia API timeouts

## Language

Chinese learners: `README.zh-CN.md` / `SOLUTION.zh-CN.md`, reply in Chinese.
For English program output: `LANG = "en"` at the top of `agent.py`.
