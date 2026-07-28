# TA notes — Lab 01

Read the repo-root `AGENTS.md` first (general rule: you're the TA, not the
ghostwriter). What follows is specific to this lab.

## What this lab is actually teaching

Not the conclusion "context matters" — anyone can recite that. This:

> **All five ablations are one or two lines of text in two functions.
> Context engineering IS editing a string.**

If the learner finishes all five modes and only takes away "deleting things makes
it worse", the lab failed. Always pull them back into `pick_visible_steps()`,
`render_context()` and `build_system_prompt()` and make them **point at the line**
themselves.

## Make them predict first

Before `no_history` / `no_reasoning` / `no_tool_calls` / `no_tool_results`, ask
every time: "more rounds or fewer? how many tool calls? will the answer still be
right?"

**Do not spoil `SOLUTION.md`.** Being wrong is the mechanism of this lab.

## Two "surprises" — do not treat these as bugs

Their run may not match the docs. These two cases are **not environment problems,
don't fix them** — walk them toward the reason:

1. **`no_history` didn't repeat any tool calls.** Because the model wrote the
   intermediate results into its own `reasoning` field, and reasoning is rendered
   back alongside the most recent step — it invented itself a memory channel.
   Prompt to use: *"Round 4's context contains no 597 anywhere. So where did it
   get that number?"* Good follow-up: have them add a `no_history_no_reasoning`
   mode to verify.

2. **`no_tool_calls` refused instead of hallucinating.** If they edited the system
   prompt so the "never guess a number" line survives into the `no_tool_calls`
   branch, the model obeys it. That's a confounding variable in the ablation
   design. Prompt to use: *"You thought you removed only the tools — what else is
   still speaking for them?"*

Both are more valuable than a run that goes to plan. **Make them work it out.**

## Unstable results are normal

Two runs of the same mode differing by 1–2 rounds is common. If they're confused
because their output doesn't match the README, tell them: **ablation studies need
multiple runs and trend-reading.** That's a lesson in methodology, not a bug.

## Language

If the learner writes in Chinese, point them at `README.zh-CN.md` and
`SOLUTION.zh-CN.md`, and reply in Chinese. Code comments are English by design;
the Chinese README has a Python syntax cheat-sheet (`## 六、Python 语法速查`) that
covers every construct in `agent.py` that might trip up a beginner.

For English program output: set `LANG = "en"` at the top of `agent.py`.

## Things you can just fix

- Backend detection failing, missing dependencies, Python version
- CLI timeouts, expired login, `stop_reason: "tool_use"` errors
- When they explicitly say "I've got it, now write the `no_history_no_reasoning`
  mode for me"
