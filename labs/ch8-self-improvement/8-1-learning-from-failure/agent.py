"""
实验 8-1：从失败中学习 —— agent 能不能不在同一个地方栽两次

实验 3-1 学的是**事实**（用户对花生过敏）。这个实验学的是**教训**：

    「amount 的单位是分，不是元」

区别在哪？事实是关于**世界**的，教训是关于**怎么做事**的。
后者更值钱，因为它能迁移到新任务上。

场景：一个退款 agent，要连着处理 3 个工单。工具里埋了 3 条**没写在文档里**的规则，
它只能靠**撞上错误**才能发现：

    1. amount_cents 的单位是分（129.90 元 = 12990）
    2. reason_code 必须从枚举里选
    3. 超过 500 元的退款需要 approved_by  ← 只有第 3 个工单会撞上

要看的就一件事：

    **第 2、3 个工单，它还会犯第 1 个工单犯过的错吗？**

    python3 agent.py                 # 打印用法说明
    python3 agent.py no_memory       # 每单从零开始（基线）
    python3 agent.py raw_log         # 把失败记录原样带到下一单
    python3 agent.py lesson          # 让模型把失败**总结成教训**再带走 ★
    python3 agent.py all             # 三种全跑 + 对比表

不需要 API key，也不联网。

★ 判据是机械的：数每个工单失败了几次工具调用。会不会学习，看的是**曲线降不降**。

详细讲解见 README.zh-CN.md（中文）/ README.md（英文）。
"""

import json
import sys
import time

from llm import complete, detect_backend, parse_json_reply


# --------------------------------------------------------------------------
#  可以改的开关（Settings）
# --------------------------------------------------------------------------

LANG = "zh"          # "zh" | "en" —— 同时切换输出和发给模型的提示词

MAX_ROUNDS = 6       # 每个工单最多几轮

SHOW_PROMPT = False  # 改成 True 会打印真正发给模型的完整文本


MODES = [
    "no_memory",   # 每个工单都从零开始
    "raw_log",     # 把上一单的失败记录原样带过来
    "lesson",      # 让模型把失败总结成一条教训带走 ★
]


# ==========================================================================
#  第 1 部分：环境 —— 三条没写在文档里的规则  ★★★ 本实验的核心 ★★★
# ==========================================================================
#
# 工具的**文档是残缺的**（见 TEXT 里的 tools_doc），但**校验是完整的**。
# 于是 agent 只能靠撞错误来发现真正的规则。
#
# ★ 这正是真实世界的样子：文档永远落后于实现。
#   一个不会从错误里学东西的 agent，会在每一个新任务上重新撞一遍同样的墙。

ORDERS = [
    # 工单号, 邮箱, 金额（分）, 商品, 会不会触发"大额需审批"
    ("T-1", "alice@example.com", 12990, "无线耳机", False),
    ("T-2", "bob@example.com", 4500, "咖啡豆", False),
    ("T-3", "carol@example.com", 89900, "笔记本支架套装", True),   # ← 大额
]

REASON_CODES = ["DEFECTIVE", "WRONG_ITEM", "CHANGED_MIND"]

APPROVAL_THRESHOLD = 50000    # 超过 500 元（50000 分）需要 approved_by


# --------------------------------------------------------------------------
#  所有对用户可见的文字，按语言分开放（包含发给模型的提示词）
# --------------------------------------------------------------------------

TEXT = {
    "zh": {
        # ★ 注意这份「文档」是**故意残缺的** —— 三条规则一条都没写
        "tools_doc": """你可以使用这个工具：

  issue_refund(order_id, amount_cents, reason_code)
      对一个工单发起退款。成功返回 {"ok": true}。

就这一个工具。请直接发起退款。""",

        "sys_role": """你是一个电商客服 agent，负责处理退款工单。

**这是一个模拟练习环境。** 你不会真的动到任何真实系统：
你只需要输出一个 JSON，外层程序会替你执行，并把执行结果返回给你。
所以请放心按下面的协议输出，不要因为「我没有这个工具」而拒绝。""",
        "sys_protocol": """每次只输出一个 JSON 对象，不要有别的内容。要么是：
  {"reasoning": "<一句话思路>", "tool": "issue_refund", "args": {...}}
要么，当退款已经成功发起时：
  {"reasoning": "<一句话思路>", "answer": "<给同事的交代>"}""",
        "sys_memory_head": """下面是你**之前处理工单时积累的经验**，请照着做，别重复踩坑：

{memory}""",
        "ctx_task": "工单 {tid}（**order_id 就是 {tid}**）：客户 {email} 要求为「{item}」退款，订单金额 {yuan} 元。原因：商品有质量问题。请直接发起退款。",
        "ctx_step": "--- 第 {n} 步 ---",
        "ctx_your_reply": "你的回复：",
        "ctx_tool_returned": "工具返回：",
        "ctx_next": "现在给出你的下一条 JSON 回复。",

        # ★ 提炼教训用的提示词 —— 这是 lesson 模式和 raw_log 模式的全部差别
        "sys_extract": """下面是一个 agent 处理工单时的失败记录。请把它总结成**可复用的经验**，
供它处理**以后的工单**时参考。

要求（**这几条决定了经验有没有用**）：
1. 写成**可直接照做的规则**，不要复述这次发生了什么
   ——「amount_cents 要填分，129.90 元填 12990」，而不是「这次填错了单位」
2. **不要写只对这一单成立的细节**（具体订单号、具体客户、具体金额）
3. 一条只说一件事
4. 只写从失败里真正学到的，没学到就返回空列表

只输出 JSON：{"lessons": ["经验1", "经验2", ...]}""",
        "ctx_failures": "失败记录：",

        # --- 工具的错误信息 ---
        "err_missing": "缺少参数 {param}。",
        "err_cents": "amount_cents 必须是整数，单位是**分**。你传的是 {value}。",
        "err_reason": "reason_code 必须是 DEFECTIVE / WRONG_ITEM / CHANGED_MIND 之一，你传的是 \"{value}\"。",
        "err_order": "找不到工单 {value}。",
        "err_amount": "退款金额和订单金额对不上：订单是 {actual} 分，你要退 {given} 分。",
        "err_approval": "金额超过 {limit} 分的退款需要额外提供 approved_by 参数（填审批人的邮箱）。",

        # --- 屏幕输出 ---
        "no_backend_title": "✗ 没找到可用的后端（agent 需要一个大模型才能跑）",
        "no_backend_help": """
下面三个任选其一即可，装好后回到这个目录重新运行：

  1. Claude Code（推荐，装了就能用，不用配置也不用花钱）
     安装： https://claude.com/claude-code
     检查： claude --version

  2. Codex CLI
     检查： codex --version

  3. 任意一个 API key（最快最省，但要花钱）
     export DEEPSEEK_API_KEY=sk-你的key
""",
        "backend": "后端：",
        "intro": "连续处理 {n} 个工单。工具文档是残缺的，3 条真规则只能靠撞错误发现。",
        "mode_line": "  模式：{mode}",
        "mode_desc": "  {desc}",
        "desc_no_memory": "每个工单从零开始，什么都不带",
        "desc_raw_log": "把上一单的失败记录**原样**带到下一单",
        "desc_lesson": "让模型把失败**总结成教训**再带到下一单",
        "ticket_head": "  ┌─ 工单 {tid}（第 {i}/{n} 单）",
        "memory_head": "  │ 带着的经验：",
        "memory_line": "  │   - {line}",
        "memory_none": "  │ 带着的经验：（无）",
        "asking": "  正在问模型…",
        "took": " {sec} 秒",
        "thinking": "  [思路] ",
        "call_ok": "  ✓ issue_refund({args})",
        "call_err": "  ✗ issue_refund({args})",
        "err_line": "     → {text}",
        "ticket_done": "  └─ 工单 {tid} 完成：{rounds} 轮，失败 {fails} 次",
        "ticket_fail": "  └─ 工单 {tid} **没做成**：跑满 {rounds} 轮，失败 {fails} 次",
        "extracting": "  正在总结教训…",
        "learned": "  💡 学到：{line}",
        "curve_head": "  ─── 失败次数的变化（这才是重点）───",
        "curve_line": "  工单 {tid}：失败 {n} 次  {bar}",
        "curve_total": "  三单合计失败 {n} 次",
        "learned_head": "  ─── 最终积累下来的经验 ───",
        "learned_line": "  - {line}",
        "learned_none": "  （没有积累任何经验）",

        # --- 对比表 ---
        "summary_title": "对比结果",
        "summary_mode": "模式：{mode}",
        "summary_curve": "  失败次数：{curve}      合计 {total}",
        "summary_done": "  做成：{n}/{k} 单",
        "summary_calls": "  模型调用：{n} 次",
        "summary_verify": """
一张表怎么读：

  **只看合计没意义，要看那条曲线降不降。**

  no_memory   每单都是新的开始 —— 曲线应该**是平的**，
              因为它每次都要重新发现同样的规则
  raw_log     带着上一单的原始失败记录 —— 信息是全的，但**没有被提炼**
  lesson      带着提炼过的教训 —— 曲线应该**往下走**

★ 注意 T-3 那一单：它触发了一条**前两单没出现过的**规则（大额需审批）。
  这条规则**谁都学不到**，因为前面没撞上过。

  所以正确的读法是：
    T-1 → T-2 降下来了 = **学到了**
    T-3 又冒出来 1 次   = **正常**，那是新规则，不是没学会

  **能学的和不能学的，要分开看。** 这是评估「自我进化」时最容易搞错的地方。""",
        "unknown_mode": "✗ 不认识的模式：",
        "exp_header": "# 实验 {i}/{total}：{mode}",
        "all_warning": "\n⚠️  all 模式要跑 3 种策略 × 3 个工单，大约 3～6 分钟。",
        "help": """
======================================================================
 实验 8-1：从失败中学习 —— agent 能不能不在同一个地方栽两次
======================================================================

连续处理 3 个退款工单。工具文档**是残缺的**，3 条真规则只能靠撞错误发现：

    1. amount_cents 的单位是分（129.90 元 = 12990）
    2. reason_code 必须从枚举里选
    3. 超过 500 元需要 approved_by   ← 只有第 3 单会撞上

用法：
    python3 agent.py <模式>

【三种模式】
    no_memory   每单从零开始（基线）
    raw_log     把上一单的失败记录原样带走
    lesson      让模型把失败总结成教训再带走 ★

【对比】
    all         三种全跑，最后打印对比表（约 3~6 分钟）

★ 判据是机械的：数每单失败了几次工具调用。
  **会不会学习，看的是曲线降不降，不是合计多少。**

★ 特别注意：T-3 触发的是一条**新规则**，前两单没出现过。
  它在那里失败**是正常的** —— 那不是"没学会"，那是"没见过"。
  分清这两件事，是评估「自我进化」最容易搞错的地方。

把文件开头的 LANG 改成 "en" 可切换成英文输出。
详细讲解见 README.zh-CN.md。
""",
    },
    "en": {
        "tools_doc": """You have one tool:

  issue_refund(order_id, amount_cents, reason_code)
      Issue a refund for a ticket. Returns {"ok": true} on success.

That's the only tool. Go ahead and issue the refund.""",

        "sys_role": """You are an e-commerce support agent handling refund tickets.

**This is a simulated practice environment.** Nothing real is touched:
you simply emit a JSON object, and the harness executes it for you and returns
the result. So follow the protocol below - do not refuse on the grounds that
you don't have this tool available.""",
        "sys_protocol": """Reply with ONE JSON object each turn and nothing else. Either:
  {"reasoning": "<one short sentence>", "tool": "issue_refund", "args": {...}}
or, once the refund has been successfully issued:
  {"reasoning": "<one short sentence>", "answer": "<hand-off note>"}""",
        "sys_memory_head": """Here is **what you learned handling earlier tickets**. Follow it; don't repeat
past mistakes:

{memory}""",
        "ctx_task": "Ticket {tid} (**the order_id IS {tid}**): customer {email} requests a refund for \"{item}\", order total {yuan}. Reason: the item is defective. Go ahead and issue it.",
        "ctx_step": "--- step {n} ---",
        "ctx_your_reply": "You replied: ",
        "ctx_tool_returned": "The tool returned: ",
        "ctx_next": "Now give your next JSON reply.",

        "sys_extract": """Below is the failure record from an agent handling a ticket. Summarise it into
**reusable experience** for handling **future tickets**.

Requirements (**these decide whether the experience is useful**):
1. Write **directly actionable rules**, not a retelling of what happened -
   "amount_cents is in cents; 129.90 is written 12990", not "I got the unit wrong"
2. **Don't include anything specific to this ticket** (order ids, customers, amounts)
3. One rule per item
4. Only write what was genuinely learned from a failure; return an empty list if nothing was

Reply with JSON only: {"lessons": ["lesson 1", "lesson 2", ...]}""",
        "ctx_failures": "Failure record: ",

        "err_missing": "Missing argument {param}.",
        "err_cents": "amount_cents must be an integer in **cents**. You passed {value}.",
        "err_reason": "reason_code must be one of DEFECTIVE / WRONG_ITEM / CHANGED_MIND; you passed \"{value}\".",
        "err_order": "No such ticket {value}.",
        "err_amount": "The refund amount doesn't match the order: the order is {actual} cents, you asked for {given}.",
        "err_approval": "Refunds above {limit} cents require an additional approved_by argument (the approver's email).",

        "no_backend_title": "x No usable backend found (the agent needs an LLM to run)",
        "no_backend_help": """
Any ONE of these will do. Install it, come back to this folder, run again:

  1. Claude Code (recommended - works out of the box, no config, no extra cost)
     Install: https://claude.com/claude-code
     Check:   claude --version

  2. Codex CLI
     Check:   codex --version

  3. Any API key (fastest and cheapest, but costs money)
     export DEEPSEEK_API_KEY=sk-your-key
""",
        "backend": "Backend: ",
        "intro": "Handling {n} tickets in a row. The tool docs are incomplete; 3 real rules can only be discovered by hitting errors.",
        "mode_line": "  Mode: {mode}",
        "mode_desc": "  {desc}",
        "desc_no_memory": "every ticket starts from zero, carrying nothing",
        "desc_raw_log": "carry the previous ticket's failure record **verbatim**",
        "desc_lesson": "have the model **distil the failures into lessons** and carry those",
        "ticket_head": "  +- ticket {tid} ({i}/{n})",
        "memory_head": "  | carrying:",
        "memory_line": "  |   - {line}",
        "memory_none": "  | carrying: (nothing)",
        "asking": "  asking the model...",
        "took": " {sec}s",
        "thinking": "  [plan] ",
        "call_ok": "  ok issue_refund({args})",
        "call_err": "  x  issue_refund({args})",
        "err_line": "     -> {text}",
        "ticket_done": "  +- ticket {tid} done: {rounds} rounds, {fails} failures",
        "ticket_fail": "  +- ticket {tid} **NOT COMPLETED**: {rounds} rounds, {fails} failures",
        "extracting": "  distilling lessons...",
        "learned": "  * learned: {line}",
        "curve_head": "  --- how the failure count moved (this is the point) ---",
        "curve_line": "  ticket {tid}: {n} failures  {bar}",
        "curve_total": "  {n} failures across all three",
        "learned_head": "  --- experience accumulated ---",
        "learned_line": "  - {line}",
        "learned_none": "  (nothing was accumulated)",

        "summary_title": "COMPARISON",
        "summary_mode": "mode: {mode}",
        "summary_curve": "  failures: {curve}      total {total}",
        "summary_done": "  completed: {n}/{k} tickets",
        "summary_calls": "  model calls: {n}",
        "summary_verify": """
How to read this table:

  **The total is meaningless on its own. Watch whether the curve descends.**

  no_memory   every ticket is a fresh start - the curve should be **flat**,
              because it rediscovers the same rules every time
  raw_log     carries the previous raw failure record - complete information, but
              **undigested**
  lesson      carries distilled rules - the curve should **descend**

* Watch ticket T-3: it triggers a rule **the first two never hit** (large refunds
  need approval). **Nobody can have learned that rule** - it was never encountered.

  So the correct reading is:
    T-1 -> T-2 descends  = **it learned**
    T-3 rises again      = **expected**, that's a new rule, not a failure to learn

  **Separate what could be learned from what couldn't.** That distinction is the
  most commonly botched part of evaluating "self-improvement".""",
        "unknown_mode": "x unknown mode: ",
        "exp_header": "# Experiment {i}/{total}: {mode}",
        "all_warning": "\n!  'all' runs 3 strategies x 3 tickets, roughly 3-6 minutes.",
        "help": """
======================================================================
 Lab 8-1: Learning from failure - can an agent avoid the same trap twice?
======================================================================

Handle 3 refund tickets in a row. The tool docs are **incomplete**; 3 real rules
can only be found by hitting errors:

    1. amount_cents is in cents (129.90 -> 12990)
    2. reason_code must come from an enum
    3. refunds above 50000 cents need approved_by   <- only ticket 3 hits this

Usage:
    python3 agent.py <mode>

THE THREE MODES
    no_memory   every ticket starts from zero (baseline)
    raw_log     carry the previous failure record verbatim
    lesson      distil failures into lessons and carry those  <-

COMPARISON
    all         run all three, then print a table (3-6 minutes)

* The verdict is mechanical: count failed tool calls per ticket.
  **Learning shows up as a descending curve, not as a smaller total.**

* Note especially: T-3 triggers a NEW rule the first two never hit. Failing there
  is **correct behaviour** - that's "never seen", not "didn't learn". Separating
  those two is the most commonly botched part of evaluating self-improvement.

Set LANG = "zh" at the top of this file for Chinese output.
Full walkthrough: README.md
""",
    },
}


def t(key, **kwargs):
    """按当前语言取一段文字，并把 {占位符} 填上。"""
    template = TEXT[LANG][key]
    if kwargs:
        return template.format(**kwargs)
    return template


# ==========================================================================
#  第 2 部分：工具（校验完整，文档残缺）
# ==========================================================================


def issue_refund(args, order):
    """发起退款。返回 (结果字典, 是不是失败了)。

    ★ 这里的校验比 tools_doc 里写的**多三条**，全靠 agent 撞出来。
    """
    order_id, _email, cents, _item, _big = order

    if args.get("order_id") is None:
        return {"error": t("err_missing", param="order_id")}, True
    if str(args.get("order_id")) != order_id:
        return {"error": t("err_order", value=str(args.get("order_id")))}, True

    amount = args.get("amount_cents")
    if amount is None:
        return {"error": t("err_missing", param="amount_cents")}, True

    # 规则 1：单位是分，必须是整数
    if isinstance(amount, bool) or not isinstance(amount, int):
        if isinstance(amount, float) and amount.is_integer():
            amount = int(amount)
        else:
            return {"error": t("err_cents", value=json.dumps(amount))}, True

    reason = args.get("reason_code")
    if reason is None:
        return {"error": t("err_missing", param="reason_code")}, True
    # 规则 2：枚举
    if reason not in REASON_CODES:
        return {"error": t("err_reason", value=str(reason))}, True

    if amount != cents:
        return {"error": t("err_amount", actual=cents, given=amount)}, True

    # 规则 3：大额需审批（只有 T-3 会撞上）
    if amount > APPROVAL_THRESHOLD and not args.get("approved_by"):
        return {"error": t("err_approval", limit=APPROVAL_THRESHOLD)}, True

    return {"ok": True, "order_id": order_id, "refunded_cents": amount}, False


# ==========================================================================
#  第 3 部分：三种「带什么去下一单」  ★★★ 本实验的核心 ★★★
# ==========================================================================
#
# 三种模式的差别，只在这一件事上：**一单结束后，往记忆里存什么。**
#
#   no_memory   什么都不存
#   raw_log     把失败的原始记录整段存下来
#   lesson      让模型把失败**提炼成可复用的规则**再存
#
# ★ 和实验 3-1 是同一个结构（存什么 vs 怎么存），但学的东西不同：
#   3-1 学的是**事实**（用户对花生过敏），这里学的是**教训**（单位是分）。
#   教训更值钱，因为它能迁移到**新的任务**上，而事实只对特定对象有效。


def distil_lessons(failure_log, backend, verbose):
    """让模型把这一单的失败提炼成可复用的经验。"""
    if len(failure_log) == 0:
        return []

    if verbose:
        print(t("extracting"), end="", flush=True)
    call_start = time.time()
    raw = complete(t("ctx_failures") + "\n" + "\n".join(failure_log),
                   t("sys_extract"), backend=backend)
    if verbose:
        print(t("took", sec=round(time.time() - call_start, 1)))

    lessons = parse_json_reply(raw).get("lessons", [])
    if not isinstance(lessons, list):
        return []
    return [str(x) for x in lessons if str(x).strip()]


# ==========================================================================
#  第 4 部分：处理一个工单（Part 4）
# ==========================================================================


def build_system_prompt(memory):
    parts = [t("sys_role"), t("tools_doc")]
    if memory:
        parts.append(t("sys_memory_head",
                       memory="\n".join("- " + x for x in memory)))
    parts.append(t("sys_protocol"))
    return "\n\n".join(parts)


def handle_ticket(order, memory, backend, verbose):
    """处理一个工单。返回 (失败次数, 用了几轮, 做成了没有, 失败记录, 模型调用数)。"""
    order_id, email, cents, item, _big = order
    task = t("ctx_task", tid=order_id, email=email, item=item,
             yuan=("%.2f" % (cents / 100.0)))

    system_prompt = build_system_prompt(memory)
    steps = []
    failures = 0
    failure_log = []
    calls = 0
    done = False

    for round_number in range(1, MAX_ROUNDS + 1):
        lines = [task, ""]
        for step in steps:
            lines.append(t("ctx_step", n=step["n"]))
            lines.append(t("ctx_your_reply")
                         + json.dumps(step["assistant"], ensure_ascii=False))
            lines.append(t("ctx_tool_returned")
                         + json.dumps(step["result"], ensure_ascii=False))
            lines.append("")
        lines.append(t("ctx_next"))
        prompt = "\n".join(lines)

        if SHOW_PROMPT:
            print("")
            print("  ┌─── 实际发给模型的内容 " + "-" * 38)
            for one_line in (system_prompt + "\n\n" + prompt).split("\n"):
                print("  │ " + one_line)
            print("  └" + "-" * 60)

        if verbose:
            print("  " + t("asking"), end="", flush=True)
        call_start = time.time()
        raw = complete(prompt, system_prompt, backend=backend)
        calls = calls + 1
        if verbose:
            print(t("took", sec=round(time.time() - call_start, 1)))

        reply = parse_json_reply(raw)
        if verbose and reply.get("reasoning"):
            print(t("thinking") + str(reply["reasoning"]))

        if "answer" in reply and not reply.get("tool"):
            break

        call_args = reply.get("args", {})
        if not isinstance(call_args, dict):
            call_args = {}

        result, failed = issue_refund(call_args, order)
        shown = json.dumps(call_args, ensure_ascii=False)
        if len(shown) > 90:
            shown = shown[:87] + "..."

        if verbose:
            print(t("call_err" if failed else "call_ok", args=shown))
            if failed:
                print(t("err_line", text=str(result.get("error", ""))[:90]))

        if failed:
            failures = failures + 1
            failure_log.append("调用 issue_refund(" + shown + ") -> "
                               + str(result.get("error", ""))
                               if LANG == "zh" else
                               "called issue_refund(" + shown + ") -> "
                               + str(result.get("error", "")))
        else:
            done = True

        steps.append({"n": round_number, "assistant": reply, "result": result})
        if done:
            break

    return failures, len(steps), done, failure_log, calls


# ==========================================================================
#  第 5 部分：跑完三单（Part 5）
# ==========================================================================


def run(mode="lesson", backend=None, verbose=True):
    desc = {"no_memory": t("desc_no_memory"), "raw_log": t("desc_raw_log"),
            "lesson": t("desc_lesson")}[mode]

    if verbose:
        print("")
        print("=" * 70)
        print(t("mode_line", mode=mode))
        print(t("mode_desc", desc=desc))
        print("=" * 70)

    memory = []
    curve = []
    completed = 0
    total_calls = 0

    for i in range(len(ORDERS)):
        order = ORDERS[i]
        if verbose:
            print("")
            print(t("ticket_head", tid=order[0], i=i + 1, n=len(ORDERS)))
            if memory:
                print(t("memory_head"))
                for one in memory:
                    print(t("memory_line", line=one[:88]))
            else:
                print(t("memory_none"))

        failures, rounds, done, failure_log, calls = handle_ticket(
            order, memory, backend, verbose)
        total_calls = total_calls + calls
        curve.append(failures)
        if done:
            completed = completed + 1

        if verbose:
            key = "ticket_done" if done else "ticket_fail"
            print(t(key, tid=order[0], rounds=rounds, fails=failures))

        # ---- 一单结束：往记忆里存什么？三种模式的全部差别就在这里 ----
        if mode == "no_memory":
            memory = []
        elif mode == "raw_log":
            memory = memory + failure_log
        else:
            new_lessons = distil_lessons(failure_log, backend, verbose)
            if new_lessons:
                total_calls = total_calls + 1
                if verbose:
                    for one in new_lessons:
                        print(t("learned", line=one[:88]))
            elif failure_log:
                total_calls = total_calls + 1
            for one in new_lessons:
                if one not in memory:
                    memory.append(one)

    if verbose:
        print("")
        print(t("curve_head"))
        for i in range(len(ORDERS)):
            print(t("curve_line", tid=ORDERS[i][0], n=curve[i],
                    bar="█" * (curve[i] * 6)))
        print(t("curve_total", n=sum(curve)))
        print("")
        print(t("learned_head"))
        if memory:
            for one in memory:
                print(t("learned_line", line=one[:88]))
        else:
            print(t("learned_none"))
        print("")

    return {"mode": mode, "curve": curve, "total": sum(curve),
            "completed": completed, "calls": total_calls}


# ==========================================================================
#  第 6 部分：命令行入口（Part 6）
# ==========================================================================


def print_help():
    print(t("help"))


def print_summary(results):
    print("")
    print("=" * 70)
    print(t("summary_title"))
    print("=" * 70)
    for r in results:
        print("")
        print(t("summary_mode", mode=r["mode"]))
        print(t("summary_curve",
                curve=" → ".join(str(x) for x in r["curve"]),
                total=r["total"]))
        print(t("summary_done", n=r["completed"], k=len(ORDERS)))
        print(t("summary_calls", n=r["calls"]))
    print(t("summary_verify"))


def _quiet_ctrl_c(exc_type, exc_value, tb):
    if exc_type is KeyboardInterrupt:
        print("")
        sys.exit(130)
    sys.__excepthook__(exc_type, exc_value, tb)


sys.excepthook = _quiet_ctrl_c


if __name__ == "__main__":

    if len(sys.argv) == 1:
        print_help()
        sys.exit(0)

    mode_arg = sys.argv[1]
    if mode_arg in ("-h", "--help", "help"):
        print_help()
        sys.exit(0)

    if mode_arg not in MODES and mode_arg != "all":
        print("")
        print(t("unknown_mode") + mode_arg)
        print_help()
        sys.exit(1)

    try:
        backend = detect_backend()
    except RuntimeError:
        print("")
        print(t("no_backend_title"))
        print(t("no_backend_help"))
        sys.exit(1)

    print(t("backend") + backend)
    print(t("intro", n=len(ORDERS)))

    if mode_arg == "all":
        print(t("all_warning"))
        results = []
        for mode_index in range(len(MODES)):
            m = MODES[mode_index]
            print("")
            print("#" * 70)
            print(t("exp_header", i=mode_index + 1, total=len(MODES), mode=m))
            print("#" * 70)
            results.append(run(mode=m, backend=backend))
        print_summary(results)
    else:
        run(mode=mode_arg, backend=backend)
