---
description: 开始或继续一个实验（用法：/lab 1-1）
---

The learner wants to start lab `$ARGUMENTS`.

Labs live at `labs/<chapter>/<lab-number>-<slug>/`, e.g.
`labs/ch1-agent-basics/1-1-context/`. The argument may be `1-1`, `1-1-context`,
or just `1` (meaning the whole chapter).

Do these in order:

1. **Locate it.** Glob `labs/*/` for a folder starting with the given number.
   If the argument names only a chapter (`1`), show that chapter's README table
   and ask which lab. If nothing matches, list the available labs.
2. **Check the environment can run.** `cd` into the lab and run
   `python3 -c "import llm; print(llm.detect_backend())"`.
   Fix any failure directly — environment problems are yours to solve (see AGENTS.md).
3. **Frame the concept in two or three sentences.** Do not recite the whole README.
4. **Make them read `agent.py` first**, then ask one locating question, e.g.
   "which lines are the loop, and which line decides when to stop?"
5. **After they answer**, have them run the baseline
   (`python3 agent.py full` for 1-1, `python3 agent.py hosted` for 1-2).
6. **Before they run ANY other mode, make them predict the result.** Being wrong
   is the mechanism — do not spoil it.

Read the lab's own `AGENTS.md` for lab-specific guidance: each one lists the
"surprises" that should be treated as teaching moments, not bugs.

Follow the repo-root `AGENTS.md` throughout: you are the TA, not the ghostwriter.
Reply in whichever language the learner writes in.
