# Chapter 1: Agent Basics

**English** · [简体中文](README.zh-CN.md)

This chapter answers the two most basic questions: **what actually is an agent,
and who runs the tools?**

If you've never written an agent before, start at 1-1 and go in order.

---

## Labs in this chapter

| Lab | Topic | Takeaway | Status |
|---|---|---|---|
| [1-1 Context Ablation](1-1-context/) | Agent = LLM + context + tools | Context engineering is editing a string | ✅ |
| [1-2 Who runs the tool?](1-2-who-runs-the-tool/) | Provider-hosted vs your own harness | Choosing hosted means giving up observability | ✅ |
| [1-3 Code as a tool](1-3-code-as-a-tool/) | Deep research loop; code tools | You give it code for reproducibility, not accuracy | ✅ |

---

## What this chapter is for

**1-1** strips the mystique off the word "agent". You'll find it's just:

```
loop:
    reply = llm(messages)              # the model says what it wants
    if no tool calls: DONE
    for each tool call:
        result = your_code_runs_it(...)   # the model can't; you can
        messages.append(result)           # paste it back
```

Then, by **deliberately deleting one part of the context**, you watch it break.
The four failure modes map onto four real production incidents: truncated
context, broken tool integration, misconfigured permissions, and dropping
thinking blocks to save tokens.

**1-2** asks it from the other side: models ship with tools built in (Claude
Code searches the web by itself) — so why write a loop at all?

The answer isn't "which is better", it's **what you're trading**. Running the
same question five ways, you'll see hosted mode answer fast and well while
being completely opaque, and DIY mode run much slower while every failed search
and self-correction happens in front of you.

Together they should let you answer: **when this breaks, which one can I debug?**

---

## Running them

Each lab is a **self-contained folder** with all its code and dependencies:

```bash
cd 1-1-context
pip install -r requirements.txt
python3 agent.py            # prints usage
```

No API key — it uses the Claude Code or Codex you already have.

---

## Relation to the source book

This chapter parallels chapter 1 of *AI Agents in Depth* (深入理解 AI Agent).
**The code is an independent rewrite** — same themes, different implementation
and angle:

| This repo | **Book's number** | Book's project | Main differences |
|---|---|---|---|
| 1-1 Context ablation | **1-1** | context | Different task and toolset; zero API key; adds parallel tool calls |
| 1-2 Who runs the tool | **1-2** | web-search-agent | Claude Code's built-in WebSearch as the hosted arm, the Wikipedia API as the DIY arm; adds three tool-degradation modes |
| 1-3 Code as a tool | **1-3** | search-codegen | A local `run_python` sandbox plus Wikipedia; reframed from accuracy to reproducibility |

(Chapter 1 is the **only** chapter whose numbering happens to match the book's.)

← [back to the index](../../README.md)
