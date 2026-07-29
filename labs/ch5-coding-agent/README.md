# Chapter 5: Coding agents

**English** · [简体中文](README.zh-CN.md)

Code is the tool that makes other tools. This chapter is about the agent that
writes it — and it starts somewhere unglamorous, because that's where coding
agents actually succeed or fail.

---

## Labs in this chapter

| Lab | Topic | Takeaway | Status |
|---|---|---|---|
| [5-1 Edit formats](5-1-edit-formats/) | whole file / search-replace / line range | Cost scales with different things per format; make errors impossible to hide | ✅ |
| 5-2 Code as reasoning | Letting the agent compute instead of guess | 📋 Planned |

---

## What this chapter is for

**5-1** asks the question every coding agent has to answer before anything else:
**what format does the model use to say "change this"?**

It measures three answers on the same bug, and the result is arithmetic rather than
opinion: `whole_file`'s cost tracks *file* size, while `search_replace` and
`line_range` track *edit* size. Grow the edit 8× and `whole_file` grows 1.07% —
which is why every real product defaults to a diff format for everyday edits and
reserves whole-file output for rewrites.

The safety half matters more. `line_range` is the only format whose failure can be
**silent**: an off-by-one line number still applies cleanly, just in the wrong
place. That makes the ordering *cost ≠ preference* — the cheapest format is the one
you should trust least.

This lab also carries the repo's **hardest verdict**: it runs `unittest` for real.
Every earlier lab checks what output *looks* like; this one checks what the code
*does*.

---

## Running them

Each lab is a **self-contained folder**:

```bash
cd 5-1-edit-formats
python3 agent.py            # prints usage
```

No API key needed.

⚠️ This chapter **executes code**. Labs run on a throwaway copy and block edits to
the graders, but **they are not sandboxes** — use a container for real work.

---

## Relation to the source book

This parallels chapter 5 of *AI Agents in Depth* (12 companion projects, from
code-for-math to a production coding agent with 17 tools).
**The code is an independent rewrite**, and the selection is deliberate:

| This repo | **Book's number** | Book's project | Notes |
|---|---|---|---|
| 5-1 Edit formats | **5-12** | coding-agent | The book builds a full agent with 17 tools; this lab isolates the single decision underneath it and measures it, with a real test suite as the verdict |

**Deliberately not attempted**: `paper-to-ppt`, `paper-to-video`, `video-edit`,
`conversational-ui` — they need Slidev, ffmpeg, TTS, or a React toolchain, which
conflicts with this repo's "clone one folder and run it" premise. Read the book
directly for those.

← [back to the index](../../README.md)
