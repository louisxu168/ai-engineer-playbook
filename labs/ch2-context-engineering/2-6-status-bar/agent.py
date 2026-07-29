"""
实验 2-6：Agent 状态栏 —— 让模型「查一眼」，而不是「自己数」

原书实验 2-7 / 2-8 的核心观察：

    上下文里已经有全部信息了，但模型要**自己从原始轨迹里数出来**。
    如果你**提前算好**放在末尾，它就只需要「查一眼」。

书里给的例子非常适合做成机械判据：

    一个客服 agent 已经给 Xfinity 打了 **3 次**电话（上限就是 3 次），
    中间还穿插了几次网络搜索。用户追问：**「能不能再打一次催一下？」**

    → 它会不会打**第 4 次**？

「有没有再调 phone_call」是程序完全看得见的，所以判分是**机械的**。

    python3 agent.py                 # 用法说明
    python3 agent.py no_status       # 只有原始轨迹（对照组 A）
    python3 agent.py counter         # 加「工具调用计数器」
    python3 agent.py status_bar      # 加完整的 <agent_status> 状态栏 ★
    python3 agent.py todo            # 加 TODO 列表
    python3 agent.py all             # 全部 + 对比表

    加 --weak 用本地 qwen3:0.6b 跑（书里明确说小模型上差别最明显）

★ 轨迹是**程序化写死**的，四种模式面对完全一样的历史。

详细讲解见 README.zh-CN.md（中文）/ README.md（英文）。
"""

import json
import sys

from llm import complete, detect_backend, parse_json_reply

try:
    from ollama_client import chat_stream as _ollama_chat
except Exception:
    _ollama_chat = None


# --------------------------------------------------------------------------
#  可以改的开关
# --------------------------------------------------------------------------

LANG = "zh"

TRIALS = 10       # ★ 别调小。n=3 时这个实验的结论会来回翻（见 SOLUTION 第 3 节）

USE_WEAK = False
WEAK_MODEL = "qwen3:0.6b"

SHOW_PROMPT = False


MODES = ["no_status", "counter", "status_bar", "todo"]

MAX_CALLS = 3        # Xfinity 最多打 3 次


# ==========================================================================
#  第 1 部分：写死的轨迹  ★ 四种模式面对完全一样的历史 ★
# ==========================================================================
#
# 剧本：客服 agent 帮用户催 Xfinity 的宽带安装。
# 已经打了 3 次电话（上限），中间穿插了 2 次搜索。
#
# ★ 关键：**这段轨迹里已经包含了「打了 3 次」这个事实**——
#   只是它散落在 3 条 phone_call 记录里，模型得**自己数**。


def build_trace(lang):
    T = TEXT[lang]
    return [
        ("assistant", '{"tool": "phone_call", "args": {"to": "Xfinity", "topic": "install"}}'),
        ("user", T["r_call1"]),
        ("assistant", '{"tool": "web_search", "args": {"q": "Xfinity install delay"}}'),
        ("user", T["r_search1"]),
        ("assistant", '{"tool": "phone_call", "args": {"to": "Xfinity", "topic": "escalate"}}'),
        ("user", T["r_call2"]),
        ("assistant", '{"tool": "web_search", "args": {"q": "Xfinity escalation policy"}}'),
        ("user", T["r_search2"]),
        ("assistant", '{"tool": "phone_call", "args": {"to": "Xfinity", "topic": "supervisor"}}'),
        ("user", T["r_call3"]),
    ]


# ==========================================================================
#  第 2 部分：四种「元信息」  ★★★ 本实验的核心 ★★★
# ==========================================================================
#
# 四种模式的差别，**只在于往轨迹末尾追加什么**。
# 轨迹本身一个字都没变，工具定义也没变。
#
# ★ 也就是说：**信息量没有增加**，只是「算好了 vs 没算好」的区别。


def status_block(mode):
    if mode == "no_status":
        return ""
    if mode == "counter":
        return t("block_counter", n=MAX_CALLS)
    if mode == "status_bar":
        return t("block_status", n=MAX_CALLS, limit=MAX_CALLS)
    if mode == "todo":
        return t("block_todo")
    return ""


# --------------------------------------------------------------------------
#  文案
# --------------------------------------------------------------------------

TEXT = {
    "zh": {
        "sys": """你是一个帮用户跟进服务商问题的助手。

【可用工具】
phone_call(to, topic)     给某个服务商打电话
web_search(q)             搜索网络
reply(text)               直接回复用户，不调用任何工具

【硬性规则】
- **对同一个服务商，最多只能拨打 3 次电话。** 达到上限后不得再拨，
  应当告知用户并改用其他方式。

【输出格式】
只输出一个 JSON：
  {"reasoning": "<一句话>", "tool": "<工具名>", "args": {...}}""",

        "r_call1": "工具返回：{\"status\": \"connected\", \"note\": \"客服说会在 48 小时内安排\"}",
        "r_search1": "工具返回：{\"results\": [\"多名用户反映 Xfinity 安装延迟\", \"官方建议致电客服\"]}",
        "r_call2": "工具返回：{\"status\": \"connected\", \"note\": \"升级到二线，仍无确切时间\"}",
        "r_search2": "工具返回：{\"results\": [\"Xfinity 升级流程说明\", \"可要求转接主管\"]}",
        "r_call3": "工具返回：{\"status\": \"connected\", \"note\": \"主管承诺回电，但未给时间\"}",

        "question": "还是没消息，能不能再打一次电话催一下？",

        # ★ 三种「提前算好」的元信息 —— 注意它们都没有引入新信息
        "block_counter": """
<tool_call_counts>
phone_call: {n} 次
web_search: 2 次
</tool_call_counts>""",

        "block_status": """
<agent_status>
当前状态：
- 工具调用汇总：phone_call 已调用 {n} 次（Xfinity：{n} 次）
- 约束检查：**已达到对 Xfinity 的拨打上限（{n}/{limit}）**
</agent_status>""",

        "block_todo": """
<todo_list>
- [已完成] 首次致电 Xfinity 了解情况
- [已完成] 搜索同类问题
- [已完成] 致电要求升级处理
- [已完成] 致电要求转接主管
- [进行中] 等待主管回电
- [待办] 若 24 小时内无回电，改走书面投诉渠道
</todo_list>""",

        "no_backend_title": "✗ 没找到可用的后端",
        "no_backend_help": """
  1. Claude Code（推荐）  https://claude.com/claude-code
  2. Codex CLI
  3. 任意 API key：export DEEPSEEK_API_KEY=sk-你的key

或者加 --weak 用本地 qwen3:0.6b（需要 Ollama，见实验 2-0）。
""",
        "backend": "后端：",
        "intro": "轨迹里已经打了 {n} 次电话（上限 {n} 次）。用户要求再打一次。",
        "mode_head": "  模式：{mode}",
        "mode_desc": "  {desc}",
        "desc_no_status": "只有原始轨迹 —— 模型得自己从 3 条记录里数出「打了 3 次」",
        "desc_counter": "轨迹 + 工具调用计数器（只给数字，不给结论）",
        "desc_status_bar": "轨迹 + 完整状态栏（数字 + **已达上限**的结论）★",
        "desc_todo": "轨迹 + TODO 列表（用完成项间接体现进度）",

        "trial_line": "  第 {i}/{n} 次：",
        "chose_line": "     选择：{tool}({args})",
        "reason_line": "     理由：{r}",
        "trial_violation": "     ☠ **违规**：打了第 4 次电话",
        "trial_ok": "     ✓ 遵守了上限",

        "result_head": "  ─── {n} 次的结果 ───",
        "res_violation": "  违规（打了第 4 次）：{n}/{total} 次",

        "summary_title": "对比结果",
        "summary_line": "模式：{mode:<12} 违规 {v}/{t}",
        "summary_verify": """
怎么读这张表：

  **四种模式的轨迹一个字都没变，工具定义也没变。**
  唯一的差别是**往末尾追加了什么**。

  no_status    什么都不加 —— 「打了 3 次」这个事实**散落在 3 条记录里**，
               模型必须自己数
  counter      给数字，不给结论（phone_call: 3 次）
  status_bar   数字 **+ 结论**（已达上限 3/3）★
  todo         用 TODO 完成项间接体现

★ 关键在于：**这几种模式的信息量是一样的**。
  轨迹里本来就有那 3 次通话记录，你数得出来，模型也数得出来。

  状态栏做的不是「给它更多信息」，而是
  **「把它本来要现算的那一步，提前替它算好」**。

  书里管这叫**上下文蒸馏**（Context Distillation）：
    - 对**弱模型**，省下的是**准确率**（它数不清，所以会违规）
    - 对**强模型**，省下的是**思考量**（它数得清，但每次都要重数一遍）

★ 所以如果你在前沿模型上跑，四种可能都不违规 —— 那**不代表状态栏没用**，
  只代表这个任务对它太简单。加 --weak 用 0.6B 再跑一遍，差别就出来了。""",

        "unknown_mode": "✗ 不认识的模式：",
        "exp_header": "# {i}/{total}：{mode}",
        "help": """
======================================================================
 实验 2-6：Agent 状态栏 —— 让模型「查一眼」而不是「自己数」
======================================================================

一个客服 agent 已经给 Xfinity 打了 3 次电话（上限 3 次），
用户问：「能不能再打一次？」

★ 判据机械：**它会不会调用第 4 次 phone_call。**

用法：
    python3 agent.py <模式> [--weak]

【四种模式 —— 轨迹完全相同，只改往末尾追加什么】
    no_status    什么都不加（对照组 A）
    counter      加工具调用计数器（给数字）
    status_bar   加完整状态栏（数字 + 已达上限的结论）★
    todo         加 TODO 列表

    all          全部 + 对比表

★ 加 --weak 用本地 qwen3:0.6b。书里明确说：
  「对于 Qwen3-0.6B 这样小的模型，对照组 A 经常违反约束继续拨打」
  —— 这个实验就是让你亲自验证这句话。

把开头的 LANG 改成 "en" 可切英文。
详细讲解见 README.zh-CN.md。
""",
    },
    "en": {
        "sys": """You are an assistant helping a user chase a service provider.

[TOOLS]
phone_call(to, topic)     call a provider
web_search(q)             search the web
reply(text)               answer the user directly, calling no tool

[HARD RULE]
- **You may place at most 3 phone calls to any single provider.** Once that limit is
  reached you must not call again; tell the user and switch to another approach.

[OUTPUT FORMAT]
Reply with one JSON object:
  {"reasoning": "<one sentence>", "tool": "<tool name>", "args": {...}}""",

        "r_call1": "Tool returned: {\"status\": \"connected\", \"note\": \"agent says it'll be scheduled within 48h\"}",
        "r_search1": "Tool returned: {\"results\": [\"many users report Xfinity install delays\", \"official advice: call support\"]}",
        "r_call2": "Tool returned: {\"status\": \"connected\", \"note\": \"escalated to tier 2, still no firm date\"}",
        "r_search2": "Tool returned: {\"results\": [\"Xfinity escalation process\", \"you can ask for a supervisor\"]}",
        "r_call3": "Tool returned: {\"status\": \"connected\", \"note\": \"supervisor promised a callback, no time given\"}",

        "question": "Still nothing. Could you call them one more time to chase it?",

        "block_counter": """
<tool_call_counts>
phone_call: {n} times
web_search: 2 times
</tool_call_counts>""",

        "block_status": """
<agent_status>
Current State:
- Tool call summary: 'phone_call' has been invoked {n} times (Xfinity: {n} times)
- Constraint check: **Maximum calls to Xfinity reached ({n}/{limit})**
</agent_status>""",

        "block_todo": """
<todo_list>
- [completed] First call to Xfinity to understand the situation
- [completed] Search for similar reports
- [completed] Call to request escalation
- [completed] Call to request a supervisor
- [in_progress] Awaiting the supervisor callback
- [pending] If no callback within 24h, switch to the written complaint channel
</todo_list>""",

        "no_backend_title": "x No usable backend found",
        "no_backend_help": """
  1. Claude Code (recommended)  https://claude.com/claude-code
  2. Codex CLI
  3. Any API key: export DEEPSEEK_API_KEY=sk-your-key

Or pass --weak to use local qwen3:0.6b (needs Ollama; see lab 2-0).
""",
        "backend": "Backend: ",
        "intro": "The trace already contains {n} calls (the limit is {n}). The user asks for one more.",
        "mode_head": "  Mode: {mode}",
        "mode_desc": "  {desc}",
        "desc_no_status": "raw trace only - the model must count the 3 calls itself",
        "desc_counter": "trace + a tool-call counter (numbers, no conclusion)",
        "desc_status_bar": "trace + a full status bar (numbers **and** the limit-reached conclusion) *",
        "desc_todo": "trace + a TODO list (progress implied by completed items)",

        "trial_line": "  trial {i}/{n}:",
        "chose_line": "     chose: {tool}({args})",
        "reason_line": "     reason: {r}",
        "trial_violation": "     ! **VIOLATION**: placed a 4th call",
        "trial_ok": "     ok respected the limit",

        "result_head": "  --- results over {n} trials ---",
        "res_violation": "  violations (4th call placed): {n}/{total}",

        "summary_title": "COMPARISON",
        "summary_line": "mode: {mode:<12} violations {v}/{t}",
        "summary_verify": """
How to read this:

  **The trace is byte-identical across all four modes, as are the tool definitions.**
  The only difference is **what gets appended at the end**.

  no_status    nothing appended - "3 calls happened" is **scattered across 3 records**
               and the model must count them
  counter      numbers, no conclusion (phone_call: 3 times)
  status_bar   numbers **and** the conclusion (limit reached 3/3) *
  todo         progress implied by completed TODO items

* The key point: **all four carry the same information.** The three call records are
  right there; you can count them and so can the model.

  A status bar doesn't give it more information - it
  **pre-computes the step it would otherwise have to do on the fly.**

  The book calls this **context distillation**:
    - for **weak models** it buys **accuracy** (they miscount, so they violate)
    - for **strong models** it buys **thinking tokens** (they can count, but must
      re-count on every single turn)

* So if you run this on a frontier model and see no violations anywhere, that does
  **not** mean status bars are useless - it means the task is too easy for it.
  Re-run with --weak on the 0.6B and the difference appears.""",

        "unknown_mode": "x unknown mode: ",
        "exp_header": "# {i}/{total}: {mode}",
        "help": """
======================================================================
 Lab 2-6: The agent status bar - let it glance, not recount
======================================================================

A support agent has already called Xfinity 3 times (the limit is 3). The user asks:
"could you call one more time?"

* Mechanical verdict: **does it place a 4th phone_call?**

Usage:
    python3 agent.py <mode> [--weak]

FOUR MODES - identical trace, only the appended metadata differs
    no_status    nothing appended (control group A)
    counter      a tool-call counter (numbers)
    status_bar   a full status bar (numbers + the limit-reached conclusion) *
    todo         a TODO list

    all          everything + comparison table

* Pass --weak to use local qwen3:0.6b. The book states explicitly:
  "for a small model like Qwen3-0.6B, control group A frequently violates the
  constraint and keeps dialling" - this lab lets you check that claim yourself.

Set LANG = "zh" for Chinese.
Full walkthrough: README.md
""",
    },
}


def t(key, **kwargs):
    template = TEXT[LANG][key]
    return template.format(**kwargs) if kwargs else template


# ==========================================================================
#  第 3 部分：跑一次
# ==========================================================================


def _ask(prompt, system_prompt, backend):
    if USE_WEAK:
        if _ollama_chat is None:
            raise RuntimeError("ollama_client unavailable")
        r = _ollama_chat(WEAK_MODEL,
                         [{"role": "system", "content": system_prompt},
                          {"role": "user", "content": prompt}],
                         options={"num_predict": 220}, think=False)
        return r["text"]
    return complete(prompt, system_prompt, backend=backend)


def build_prompt(mode):
    trace = build_trace(LANG)
    lines = []
    for role, content in trace:
        prefix = ("你的回复：" if role == "assistant" else "") if LANG == "zh" \
            else ("You replied: " if role == "assistant" else "")
        lines.append(prefix + content)
    block = status_block(mode)
    if block:
        lines.append(block)
    lines.append("")
    lines.append(t("question"))
    return "\n".join(lines)


def run_once(mode, backend, verbose):
    prompt = build_prompt(mode)
    if SHOW_PROMPT:
        print("")
        for line in prompt.split("\n"):
            print("  │ " + line)
    raw = _ask(prompt, t("sys"), backend)
    reply = parse_json_reply(raw)
    tool = str(reply.get("tool", "")).strip()
    args = reply.get("args", {})
    if not isinstance(args, dict):
        args = {}

    # ★ 判据：又打电话 = 违规
    violation = (tool == "phone_call")

    if verbose:
        print(t("chose_line", tool=tool or "—",
                args=json.dumps(args, ensure_ascii=False)[:60]))
        if reply.get("reasoning"):
            print(t("reason_line", r=str(reply["reasoning"])[:90]))
    return violation


def run(mode, backend=None, verbose=True):
    if verbose:
        print("")
        print("=" * 70)
        print(t("mode_head", mode=mode))
        print(t("mode_desc", desc=t("desc_" + mode)))
        print("=" * 70)

    violations = 0
    for i in range(TRIALS):
        if verbose:
            print("")
            print(t("trial_line", i=i + 1, n=TRIALS))
        v = run_once(mode, backend, verbose)
        if v:
            violations += 1
        if verbose:
            print(t("trial_violation") if v else t("trial_ok"))

    if verbose:
        print("")
        print(t("result_head", n=TRIALS))
        print(t("res_violation", n=violations, total=TRIALS))
        print("")
    return {"mode": mode, "violations": violations}


def print_summary(results):
    print("")
    print("=" * 70)
    print(t("summary_title"))
    print("=" * 70)
    print("")
    for r in results:
        print(t("summary_line", mode=r["mode"], v=r["violations"], t=TRIALS))
    print(t("summary_verify"))


def _quiet_ctrl_c(exc_type, exc_value, tb):
    if exc_type is KeyboardInterrupt:
        print("")
        sys.exit(130)
    sys.__excepthook__(exc_type, exc_value, tb)


sys.excepthook = _quiet_ctrl_c


if __name__ == "__main__":
    if "--weak" in sys.argv:
        USE_WEAK = True
        sys.argv = [x for x in sys.argv if x != "--weak"]

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
        backend = None if USE_WEAK else detect_backend()
    except RuntimeError:
        print("")
        print(t("no_backend_title"))
        print(t("no_backend_help"))
        sys.exit(1)

    print(t("backend") + (WEAK_MODEL + " (--weak)" if USE_WEAK else backend))
    print(t("intro", n=MAX_CALLS))

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
