# AI Engineer Playbook

**English** · [简体中文](README.zh-CN.md)

> Hands-on labs for understanding how AI agents actually work.
> **No API key required** — if you already have Claude Code or Codex, clone and run.

---

## What problem this solves

Agent tutorials tend to fall into two camps, and neither is much use:

- **Pure theory.** Plenty of ReAct, function calling and context engineering
  concepts — but you close the tab still not knowing what to type first.
- **Code that runs.** Either it leans on a framework (LangChain, LlamaIndex)
  that hides the one loop you most need to see, or it opens by telling you to
  go buy an API key, which loses half the audience on line one.

This playbook's answer: **every lab is a single ~500-line, zero-framework script
you can read start to finish**, and it runs on the Claude Code / Codex
subscription you already have. No spend.

More importantly, the point of each lab is not to get it *working* — it is to
**break it**. You systematically delete one part of the agent and watch which
way it falls over. Because in a real project the question is never "how do I
get it running", it's "why is it being weird again".

---

## 30 seconds to first run

```bash
git clone https://github.com/louisxu168/ai-engineer-playbook.git
cd ai-engineer-playbook/labs/ch1-agent-basics/1-1-context
pip install -r requirements.txt
python3 agent.py          # prints usage
python3 agent.py full     # run the baseline
```

No `.env`, no signup, no billing.

> **Output is in Chinese by default.** Set `LANG = "en"` at the top of
> `agent.py` to switch the console output *and* the prompts sent to the model
> to English.

---

## Two things that are different here

### 1. No API key

Most learners have no paid API key, but many already run Claude Code or Codex.
Both can be driven non-interactively, using **the subscription you're already
logged into**:

```bash
claude -p "hello" --output-format json    # Claude Code headless
codex exec --json "hello"                 # Codex headless
```

Each lab's `llm.py` auto-detects, in the order `claude` → `codex` → API key.
To force one, or to go much faster:

```bash
LAB_BACKEND=codex python3 agent.py full
LAB_BACKEND=api DEEPSEEK_API_KEY=sk-... python3 agent.py full   # fastest, cheapest
```

> **The trade-off, stated up front:** going through a CLI means no structured
> `tool_use` blocks, so tool calls are a JSON text protocol we parse ourselves.
> The loop, the context handling and the ablations are all real — only the
> *transport* for tool calls is simplified. Use `LAB_BACKEND=api` to see genuine
> structured tool calling.

### 2. Your coding agent becomes a teaching assistant, not a ghostwriter

The repo root ships an [`AGENTS.md`](AGENTS.md) (Claude Code reads the same file
via `CLAUDE.md`). It tells your coding agent: **you are the TA here, not the
person doing the homework.**

| You say | It won't | It will |
|---|---|---|
| "How do I do this lab?" | Write the implementation | Ask you to read `agent.py` and say which lines are the loop |
| "I got an error" | Silently fix it | Read the error back to you and ask which step you think broke |
| "Why did that happen?" | Explain it | Ask first: "what did you predict before you ran it?" |

Environment problems (dependencies, backend detection, CLI timeouts) it just
fixes — no point wasting your time on those.

Claude Code users also get a slash command:

```
/lab 1-1
```

It checks your environment, frames the concept, makes you read the code, and
makes you predict the result before running — in teaching order.

> Worth saying out loud: **Claude Code and Codex are themselves agent
> harnesses**, and these labs are about what a harness is made of. You can ask
> yours "how do *you* manage context?" at any point — the toy in your terminal
> and the tool you're asking run on the same principles.

---

## The labs

Labs are grouped by **chapter**, following the structure of *AI Agents in Depth*
so you can read the two side by side. Each lab is still a **self-contained
folder** — download one and it runs.

| Ch | Topic | Labs | Status |
|---|---|---|---|
| [1](labs/ch1-agent-basics/) | Agent basics | [1-1 Context ablation](labs/ch1-agent-basics/1-1-context/) · [1-2 Who runs the tool?](labs/ch1-agent-basics/1-2-who-runs-the-tool/) | ✅ 2 ready |
| 2 | Context engineering | Compaction, prompt injection, system-prompt ablation | 📋 Planned |
| 3 | User memory & knowledge | File-based memory, agentic RAG vs naive RAG | 📋 Planned |
| 4 | Tools | Tool design (schemas / descriptions / error feedback), async tools | 📋 Planned |
| 5 | Coding agents | Code-as-reasoning, a minimal coding agent | 📋 Planned |
| 6 | Evaluation | LLM-as-judge, and when it lies to you | 📋 Planned |
| 7 | Post-training | Distillation, RL, post-training | 📋 Planned |
| 8 | Continuous evolution | Learning from experience, self-improving prompts | 📋 Planned |
| 9 | Multimodal & real-time | Speech, streaming interaction | 📋 Planned |
| 10 | Multi-agent collaboration | Parallel research, subagent coordination | 📋 Planned |

### What lab 1-1 looks like

Running `python3 agent.py full` (with `LANG = "en"`):

```
====================================================================
  Round 1 of 8     mode: full
  no history in context yet     prompt 141 chars
====================================================================

  asking the model... took 8.8s

  [thinking] Look up the keyboard price and the USD->CNY rate in parallel
             since they're independent.

  [tool 1/2] search_products({'keyword': 'mechanical keyboard'})
        -> {'name': 'Keychron Q1 Pro', 'usd': 199.0}
  [tool 2/2] get_rate({'from_currency': 'USD', 'to_currency': 'CNY'})
        -> {'rate': 7.24, 'from': 'USD', 'to': 'CNY'}
  ^ 2 tools called in parallel (model judged them independent)
```

Then flip `SHOW_PROMPT` to `True` and it prints **the exact text sent to the
model each round**. One look at that and the mystique evaporates: "context" is
a string you assembled yourself.

---

## Repo layout

```
ai-engineer-playbook/
├── README.md / README.zh-CN.md   this file, in both languages
├── AGENTS.md                     TA-mode instructions (Claude Code + Codex)
├── CLAUDE.md                     -> imports AGENTS.md
├── .claude/commands/lab.md       the /lab 1-1 slash command
└── labs/
    └── ch1-agent-basics/         grouped by chapter, numbered like the book
        ├── README.md             chapter intro (both languages)
        ├── 1-1-context/          one self-contained folder per lab
        │   ├── README.md         the lab walkthrough (English)
        │   ├── README.zh-CN.md   同上（中文）
        │   ├── agent.py          the agent itself
        │   ├── llm.py            backend adapter (claude / codex / api)
        │   ├── AGENTS.md         TA notes specific to this lab
        │   ├── SOLUTION.md       answers — read after you've tried
        │   └── requirements.txt
        └── 1-2-who-runs-the-tool/
```

**Every lab folder stands alone**, `llm.py` included. The duplication is
deliberate: it's what makes "download one folder and run it" true.

---

## Prerequisites

You need to be able to write Python. That's it. No ML background, no GPU, no
papers.

The code deliberately avoids Python shorthand (ternaries, comprehensions,
`**kwargs` unpacking) in favour of the dumbest readable form — **if you can
write `for` and `if`, you can read it.**

If "an LLM is just a function" is news to you, start at lab 01. That's the
whole point of it.

---

## Contributing

Issues and PRs welcome. Especially these:

- **Your run didn't match the docs.** Open an issue with the output. Models are
  stochastic; many people running it many times beats me running it once.
- **Some code was hard to follow.** That's a bug in the lab, not in you. Tell me
  which line lost you.
- **A new lab.** Open an issue first to discuss what it teaches and how a
  learner would break it.

---

## Credits

Lab topics are inspired by [bojieli/ai-agent-book](https://github.com/bojieli/ai-agent-book).
The code is an independent rewrite, and the approach (zero API key, TA mode)
differs. For systematic theory, read the original book.

## License

[MIT](LICENSE)
