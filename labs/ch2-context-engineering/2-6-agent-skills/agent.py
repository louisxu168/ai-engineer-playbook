"""
实验 2-6：Agent Skills 的渐进式披露 —— 按需加载，而不是全都塞进去

原书实验 2-6 演示了 Agent Skills 的**渐进式披露**（progressive disclosure）：

    第 1 层  上下文末尾只有一份 **Skill 元数据清单**（每个一行）
    第 2 层  模型判断需要某个 Skill → 用工具加载它的 SKILL.md
    第 3 层  还需要更细的东西 → 再加载 detail 文档

这个实验把它做成一个**可量化**的对照：12 个 Skill，任务需要用到
**只写在第 3 层里**的一个具体参数格式。

三种做法：

    all_loaded    12 个 Skill 的全部三层，一次性全塞进去（最贵）
    metadata_only 只给第 1 层清单，没有加载工具（**做不到**）
    progressive   第 1 层 + load_skill 工具，按需加载 ★

判据是机械的：**答案里有没有那个正确的参数格式**，以及**用了多少 token**。

    python3 agent.py                  # 用法说明
    python3 agent.py all_loaded
    python3 agent.py metadata_only
    python3 agent.py progressive      # ★
    python3 agent.py all              # 全部 + 对比表

不需要 API key（用你已装的 Claude Code / Codex），不联网。

详细讲解见 README.zh-CN.md（中文）/ README.md（英文）。
"""

import json
import sys

from llm import complete, detect_backend, parse_json_reply
from skills import (SKILLS, TARGET_SKILL, CORRECT_FORMAT,
                    metadata_list, get_skill_md, get_detail, everything)


# --------------------------------------------------------------------------
#  可以改的开关
# --------------------------------------------------------------------------

LANG = "zh"

MAX_ROUNDS = 6

SHOW_PROMPT = False


MODES = ["all_loaded", "metadata_only", "progressive"]


# --------------------------------------------------------------------------
#  文案
# --------------------------------------------------------------------------

TEXT = {
    "zh": {
        "role": "你是一个能使用各种 Skill 的助手。",

        "sys_all": """【已加载的全部 Skill 文档】

{blob}

【输出格式】
只输出一个 JSON：{{"reasoning": "<一句话>", "answer": "<你的回答>"}}""",

        "sys_meta": """【可用的 Skill 清单】

{meta}

⚠️ 你现在只能看到每个 Skill 的一句话说明，**没有工具可以加载它们的详细文档**。

【输出格式】
只输出一个 JSON：{{"reasoning": "<一句话>", "answer": "<你的回答>"}}""",

        "sys_prog": """【可用的 Skill 清单】

{meta}

【加载工具】
你可以用下面这个工具**按需加载**某个 Skill 的详细文档：

  load_skill(name, level)
      name  —— Skill 名字，从上面清单里选
      level —— "md" 加载核心流程文档；"detail" 加载更细的参数文档

  一次只加载一个。需要什么加什么，不需要的别加。

【输出格式】
每次只输出一个 JSON。要加载文档时：
  {{"reasoning": "<一句话>", "tool": "load_skill", "args": {{"name": "...", "level": "..."}}}}
已经知道答案时：
  {{"reasoning": "<一句话>", "answer": "<你的回答>"}}""",

        "task": "我要生成一份 16:9 的演示文稿。slide_size 这个参数应该怎么填？"
                "请给出**确切的字符串**。",

        "loaded": "  [加载] {name} / {level}   （{n} 字）",
        "load_err": "  [加载失败] {why}",
        "err_no_skill": "没有叫 {name} 的 Skill。",
        "err_bad_level": "level 只能是 \"md\" 或 \"detail\"。",

        "no_backend_title": "✗ 没找到可用的后端",
        "no_backend_help": """
  1. Claude Code（推荐）  https://claude.com/claude-code
  2. Codex CLI
  3. 任意 API key：export DEEPSEEK_API_KEY=sk-你的key
""",
        "backend": "后端：",
        "intro": "{n} 个 Skill。任务需要的那个参数格式**只写在 pptx 的 detail 文档里**。",
        "mode_head": "  模式：{mode}",
        "mode_desc": "  {desc}",
        "desc_all_loaded": "12 个 Skill 的全部三层，一次性全塞进上下文",
        "desc_metadata_only": "只给一句话清单，**没有**加载工具",
        "desc_progressive": "一句话清单 + load_skill 工具，按需加载 ★",

        "ctx_line": "  上下文：{chars} 字（约 {tok} token）",
        "round_line": "  ── 第 {n} 轮 ──",
        "answer_line": "  [回答] {text}",
        "verdict_ok": "  ✓ 答对了：找到了 {fmt}",
        "verdict_bad": "  ✗ 答错了：没给出正确的 {fmt}",

        "summary_title": "对比结果",
        "summary_mode": "模式：{mode}",
        "summary_ctx": "  最大上下文：{chars} 字（约 {tok} token）",
        "summary_loads": "  加载了 {n} 份文档",
        "summary_ok": "  答案：{r}",
        "yes": "✓ 对",
        "no": "✗ 错",
        "summary_verify": """
一张表怎么读：

  all_loaded     能答对，但**把 12 个 Skill 的所有细节都塞进去了** ——
                 而这次任务只用到其中 1 个的 1 段
  metadata_only  **答不出来** —— 那个参数格式根本不在上下文里
  progressive    能答对，而且上下文只有 all_loaded 的一小部分 ★

★ 这三种模式画出了一条清楚的取舍曲线：

    信息全在上下文里  →  能用，但每次请求都为用不到的东西付钱
    信息全不在        →  省钱，但做不了事
    **按需加载**      →  两头兼顾，代价是**多花一轮模型调用**

  书里管这叫**渐进式披露**。它和实验 3-2 的检索、实验 4-2 的工具检索
  是**同一个形状** —— 都是「候选太多，先筛再给」。

  区别在于：**这次是模型自己决定筛什么**（它调 load_skill），
  而不是你用 BM25 替它筛。**决定权在模型手里，所以它不会漏掉自己需要的东西。**

★ 而这正好补上了实验 4-2 的那个失败：那里 BM25 把正确的工具排在第 9、
  切线在第 8，模型**根本没机会看见它**。
  渐进式披露没有这个问题 —— 因为筛选是模型自己做的。""",

        "unknown_mode": "✗ 不认识的模式：",
        "exp_header": "# {i}/{total}：{mode}",
        "help": """
======================================================================
 实验 2-6：Agent Skills 的渐进式披露
======================================================================

12 个 Skill。任务问的那个参数格式，**只写在其中一个 Skill 的
第 3 层细节文档里** —— 第 1、2 层都没有。

用法：
    python3 agent.py <模式>

【三种模式】
    all_loaded     12 个 Skill 的全部三层一次性全塞进去（最贵）
    metadata_only  只给一句话清单，没有加载工具（做不到）
    progressive    清单 + load_skill 工具，按需加载 ★

    all            全部 + 对比表

★ 判据机械：答案里有没有那个正确的参数格式，以及用了多少 token。

不需要 API key，用你已装的 Claude Code / Codex。

把开头的 LANG 改成 "en" 可切英文。
详细讲解见 README.zh-CN.md。
""",
    },
    "en": {
        "role": "You are an assistant that can use various Skills.",

        "sys_all": """[ALL SKILL DOCUMENTATION, PRELOADED]

{blob}

[OUTPUT FORMAT]
Reply with one JSON object: {{"reasoning": "<one sentence>", "answer": "<your answer>"}}""",

        "sys_meta": """[AVAILABLE SKILLS]

{meta}

⚠️ You can only see a one-line description of each Skill. **There is no tool to load
their detailed documentation.**

[OUTPUT FORMAT]
Reply with one JSON object: {{"reasoning": "<one sentence>", "answer": "<your answer>"}}""",

        "sys_prog": """[AVAILABLE SKILLS]

{meta}

[LOADING TOOL]
You can load a Skill's documentation **on demand**:

  load_skill(name, level)
      name  - a Skill name from the list above
      level - "md" loads the core procedure doc; "detail" loads the finer parameter doc

  One at a time. Load what you need and nothing else.

[OUTPUT FORMAT]
One JSON object per turn. To load a document:
  {{"reasoning": "<one sentence>", "tool": "load_skill", "args": {{"name": "...", "level": "..."}}}}
Once you know the answer:
  {{"reasoning": "<one sentence>", "answer": "<your answer>"}}""",

        "task": "I need to produce a 16:9 presentation. What exactly should the "
                "slide_size parameter be? Give the **exact string**.",

        "loaded": "  [loaded] {name} / {level}   ({n} chars)",
        "load_err": "  [load failed] {why}",
        "err_no_skill": "No Skill named {name}.",
        "err_bad_level": "level must be \"md\" or \"detail\".",

        "no_backend_title": "x No usable backend found",
        "no_backend_help": """
  1. Claude Code (recommended)  https://claude.com/claude-code
  2. Codex CLI
  3. Any API key: export DEEPSEEK_API_KEY=sk-your-key
""",
        "backend": "Backend: ",
        "intro": "{n} Skills. The parameter format the task needs is **only in pptx's detail doc**.",
        "mode_head": "  Mode: {mode}",
        "mode_desc": "  {desc}",
        "desc_all_loaded": "all three layers of all 12 Skills, preloaded into the context",
        "desc_metadata_only": "one-line list only, **no** loading tool",
        "desc_progressive": "one-line list + a load_skill tool, loaded on demand *",

        "ctx_line": "  context: {chars} chars (~{tok} tokens)",
        "round_line": "  -- round {n} --",
        "answer_line": "  [answer] {text}",
        "verdict_ok": "  ok correct: found {fmt}",
        "verdict_bad": "  x wrong: did not produce the correct {fmt}",

        "summary_title": "COMPARISON",
        "summary_mode": "mode: {mode}",
        "summary_ctx": "  peak context: {chars} chars (~{tok} tokens)",
        "summary_loads": "  documents loaded: {n}",
        "summary_ok": "  answer: {r}",
        "yes": "ok correct",
        "no": "x wrong",
        "summary_verify": """
How to read this:

  all_loaded     correct, but it shipped **every detail of all 12 Skills** - while the
                 task used one paragraph of one of them
  metadata_only  **can't answer** - the format simply isn't in the context
  progressive    correct, on a fraction of all_loaded's context *

* The three modes trace a clear trade-off curve:

    everything in context -> works, but you pay for the unused on every request
    nothing in context    -> cheap, but can't do the job
    **load on demand**    -> both, at the cost of **an extra model call**

  The book calls this **progressive disclosure**. It's the **same shape** as lab 3-2's
  retrieval and lab 4-2's tool retrieval - "too many candidates, filter before you send".

  The difference: **the model decides what to filter** (it calls load_skill), rather
  than BM25 deciding for it. **The choice stays with the model, so it can't be denied
  something it knows it needs.**

* Which repairs lab 4-2's failure exactly: there, BM25 ranked the correct tool 9th with
  a cutoff of 8, and the model **never got to see it**. Progressive disclosure doesn't
  have that failure mode, because the filtering is done by the model itself.""",

        "unknown_mode": "x unknown mode: ",
        "exp_header": "# {i}/{total}: {mode}",
        "help": """
======================================================================
 Lab 2-6: Progressive disclosure with Agent Skills
======================================================================

12 Skills. The parameter format the task asks about lives **only in one Skill's
third-layer detail doc** - not in layers 1 or 2.

Usage:
    python3 agent.py <mode>

THREE MODES
    all_loaded     all three layers of all 12 Skills, preloaded (most expensive)
    metadata_only  one-line list only, no loading tool (can't do it)
    progressive    list + a load_skill tool, on demand  <-

    all            everything + comparison table

* Mechanical verdict: does the answer contain the correct format string, and how many
  tokens did it cost?

No API key needed - uses the Claude Code / Codex you already have.

Set LANG = "zh" for Chinese.
Full walkthrough: README.md
""",
    },
}


def t(key, **kwargs):
    template = TEXT[LANG][key]
    return template.format(**kwargs) if kwargs else template


# ==========================================================================
#  第 1 部分：三种模式怎么装配上下文  ★★★ 本实验的核心 ★★★
# ==========================================================================


def build_system(mode):
    if mode == "all_loaded":
        return t("role") + "\n\n" + t("sys_all", blob=everything())
    if mode == "metadata_only":
        return t("role") + "\n\n" + t("sys_meta", meta=metadata_list())
    return t("role") + "\n\n" + t("sys_prog", meta=metadata_list())


def load_skill(args):
    """★ progressive 模式的那个工具。模型自己决定加载什么。"""
    name = str(args.get("name", "")).strip()
    level = str(args.get("level", "")).strip().lower()
    if level not in ("md", "detail"):
        return None, t("err_bad_level")
    doc = get_skill_md(name) if level == "md" else get_detail(name)
    if doc is None:
        return None, t("err_no_skill", name=name)
    return doc, None


# ==========================================================================
#  第 2 部分：跑一次
# ==========================================================================


def run(mode, backend=None, verbose=True):
    if verbose:
        print("")
        print("=" * 70)
        print(t("mode_head", mode=mode))
        print(t("mode_desc", desc=t("desc_" + mode)))
        print("=" * 70)

    system = build_system(mode)
    loaded = []          # progressive 模式加载过的文档
    peak_chars = 0
    answer = ""

    for round_number in range(1, MAX_ROUNDS + 1):
        parts = [t("task")]
        for one in loaded:
            parts.append("")
            parts.append("===== " + one["name"] + " / " + one["level"] + " =====")
            parts.append(one["doc"])
        prompt = "\n".join(parts)

        peak_chars = max(peak_chars, len(system) + len(prompt))

        if SHOW_PROMPT and round_number == 1:
            print("")
            print("  │ (system " + str(len(system)) + " 字)")

        if verbose and round_number == 1:
            print("")
            print(t("ctx_line", chars=len(system) + len(prompt),
                    tok=int((len(system) + len(prompt)) / 1.6)))

        raw = complete(prompt, system, backend=backend)
        reply = parse_json_reply(raw)

        if reply.get("tool") == "load_skill" and mode == "progressive":
            doc, err = load_skill(reply.get("args", {}) or {})
            if err:
                if verbose:
                    print(t("load_err", why=err))
                loaded.append({"name": "?", "level": "?", "doc": err})
                continue
            args = reply.get("args", {})
            if verbose:
                print(t("loaded", name=args.get("name"),
                        level=args.get("level"), n=len(doc)))
            loaded.append({"name": str(args.get("name")),
                           "level": str(args.get("level")), "doc": doc})
            continue

        answer = str(reply.get("answer", raw)).strip()
        break

    ok = CORRECT_FORMAT in answer

    if verbose:
        print("")
        print(t("answer_line", text=answer[:200].replace("\n", " ")))
        print(t("verdict_ok", fmt=CORRECT_FORMAT) if ok
              else t("verdict_bad", fmt=CORRECT_FORMAT))
        print("")

    return {"mode": mode, "ok": ok, "chars": peak_chars,
            "loads": len([x for x in loaded if x["name"] != "?"])}


def print_summary(results):
    print("")
    print("=" * 70)
    print(t("summary_title"))
    print("=" * 70)
    for r in results:
        print("")
        print(t("summary_mode", mode=r["mode"]))
        print(t("summary_ctx", chars=r["chars"], tok=int(r["chars"] / 1.6)))
        print(t("summary_loads", n=r["loads"]))
        print(t("summary_ok", r=t("yes") if r["ok"] else t("no")))
    print(t("summary_verify"))


def _quiet_ctrl_c(exc_type, exc_value, tb):
    if exc_type is KeyboardInterrupt:
        print("")
        sys.exit(130)
    sys.__excepthook__(exc_type, exc_value, tb)


sys.excepthook = _quiet_ctrl_c


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print(t("help"))
        sys.exit(0)
    mode_arg = sys.argv[1]
    if mode_arg in ("-h", "--help", "help"):
        print(t("help"))
        sys.exit(0)
    if mode_arg not in MODES and mode_arg != "all":
        print("")
        print(t("unknown_mode") + mode_arg)
        print(t("help"))
        sys.exit(1)

    try:
        backend = detect_backend()
    except RuntimeError:
        print("")
        print(t("no_backend_title"))
        print(t("no_backend_help"))
        sys.exit(1)

    print(t("backend") + backend)
    print(t("intro", n=len(SKILLS)))

    todo = MODES if mode_arg == "all" else [mode_arg]
    results = []
    for i in range(len(todo)):
        if len(todo) > 1:
            print("")
            print("#" * 70)
            print(t("exp_header", i=i + 1, total=len(todo), mode=todo[i]))
            print("#" * 70)
        results.append(run(todo[i], backend=backend))
    if mode_arg == "all":
        print_summary(results)
