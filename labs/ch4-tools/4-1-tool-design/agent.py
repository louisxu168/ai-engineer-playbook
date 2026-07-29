"""
实验 4-1：工具设计 —— 决定成败的不是模型，是你写的那几行说明

前面三章，工具一直是「顺便有的东西」。这一章正面看它。

一个残酷的事实：

    **同一个模型、同一个任务，只因为工具描述写得不一样，
      有的一次做对，有的怎么都做不对。**

这个实验做一个 2×2 的对照，两个变量各自独立开关：

                  错误信息有用      错误信息没用
    描述写得好       good           silent_errors
    描述写得烂       vague_desc     both_bad

跑完你会知道：**这两件事哪个更重要**，以及它们各自在什么时候救得了你。

    python3 agent.py                 # 打印用法说明
    python3 agent.py good            # 描述好 + 错误信息好（基线）
    python3 agent.py vague_desc      # 描述烂 + 错误信息好
    python3 agent.py silent_errors   # 描述好 + 错误信息烂
    python3 agent.py both_bad        # 两个都烂
    python3 agent.py all             # 四种全跑 + 对比表

不需要 API key，也不联网。

★ 判定完全是机械的：程序知道唯一正确的那次调用长什么样
  （工具名 + 三个参数值），比对即可，不靠关键词也不靠模型判分。

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

SHOW_PROMPT = False  # 改成 True 会打印每轮真正发给模型的完整文本

MAX_ROUNDS = 8       # 最多跑几轮


MODES = [
    "good",           # 描述好 + 错误信息好（基线）
    "vague_desc",     # 描述烂 + 错误信息好
    "silent_errors",  # 描述好 + 错误信息烂
    "both_bad",       # 两个都烂
]

# 上面四种模式，其实是两个开关的四种组合。代码里就是这两个函数：
GOOD_DESC = {"good": True, "vague_desc": False,
             "silent_errors": True, "both_bad": False}
GOOD_ERRORS = {"good": True, "vague_desc": True,
               "silent_errors": False, "both_bad": False}


# ==========================================================================
#  第 1 部分：假数据（Part 1）
# ==========================================================================
#
# 一个电商客服场景。数据写死，保证四种模式面对的世界完全一样。

ORDERS = [
    # order_id, 邮箱, 品类, 金额（分！）, 下单距今天数, 商品名
    ("ORD-1001", "alice@example.com", "electronics", 12990, 12, "无线耳机"),
    ("ORD-1002", "alice@example.com", "food", 4500, 40, "咖啡豆 1kg"),
    ("ORD-1003", "bob@example.com", "clothing", 29900, 5, "冲锋衣"),
]

# 各品类的退款窗口（天）
POLICY = {"electronics": 30, "clothing": 15, "food": 7}

# issue_refund 只接受这三个原因码
REASON_CODES = ["DEFECTIVE", "WRONG_ITEM", "CHANGED_MIND"]


# ★ 唯一正确的那次调用。程序拿它来自动判分。
#
#   为什么只有这一个答案？
#     - alice 名下两笔订单，只有 ORD-1001 是耳机
#     - electronics 窗口 30 天，下单 12 天，在窗口内 ✓
#       （ORD-1002 是食品，窗口 7 天，40 天前买的，早就过期了）
#     - 金额必须是**分**：129.90 元 = 12990 分  ← 这是最容易踩的坑
#     - 原因是「坏了」→ DEFECTIVE
CORRECT_CALL = {"tool": "issue_refund",
                "args": {"order_id": "ORD-1001",
                         "amount_cents": 12990,
                         "reason_code": "DEFECTIVE"}}


# --------------------------------------------------------------------------
#  所有对用户可见的文字，按语言分开放（包含发给模型的提示词）
# --------------------------------------------------------------------------

TEXT = {
    "zh": {
        # ==== 工具描述：好版本 ====
        # 注意这段里的每一句话，都在**预先回答模型会问的一个问题**。
        "tools_good": """你可以使用下面三个工具。

1. find_orders(email, days)
   查一个客户最近的订单。
   - email: 客户邮箱，完整地址，例如 "alice@example.com"
   - days:  往前查多少天，整数，最大 90。不确定就填 90。
   返回订单列表，每条含 order_id、category（品类）、amount_cents（金额，单位：分）、
   days_ago（下单距今天数）、item（商品名）。

2. get_policy(category)
   查某个品类的退款政策。
   - category: 必须是这三个之一："electronics" / "clothing" / "food"
     （品类值在 find_orders 的返回里能直接看到，照抄即可）
   返回 refund_window_days —— 超过这个天数就不能退了。

3. issue_refund(order_id, amount_cents, reason_code)
   实际发起退款。**这一步不可撤销，参数一定要对。**
   - order_id:     订单号，例如 "ORD-1001"
   - amount_cents: 退款金额，**单位是分（cent），必须是整数**。
                   例如 129.90 元要写成 12990，不要写 129.9。
                   find_orders 返回的 amount_cents 已经是分，直接用。
   - reason_code:  必须是这三个之一："DEFECTIVE"（商品有问题）/
                   "WRONG_ITEM"（发错货）/ "CHANGED_MIND"（客户改主意）
   成功返回 {"ok": true, ...}。""",

        # ==== 工具描述：烂版本 ====
        # 这不是我编出来吓唬人的写法 —— 这是自动从函数签名生成的文档最常见的样子：
        # 名字有了，参数名有了，**但凡是需要人解释一句的东西全没有**。
        "tools_vague": """你可以使用下面三个工具。

1. find_orders(email, days) —— 查询订单
2. get_policy(category) —— 查询政策
3. issue_refund(order_id, amount, reason) —— 处理退款""",

        # ==== 系统提示词的其余部分 ====
        "sys_role": "你是一个电商客服 agent，负责处理退款请求。",
        "sys_protocol": """每次只输出一个 JSON 对象，不要有别的内容。要么是：
  {"reasoning": "<一句话思路>", "calls": [{"tool": "<工具名>", "args": {...}}]}
要么，当退款已经成功发起、事情办完时：
  {"reasoning": "<一句话思路>", "answer": "<给同事的交代>"}""",
        "ctx_task": "工单：",
        "ctx_step": "--- 第 {n} 步 ---",
        "ctx_your_reply": "你的回复：",
        "ctx_tool_returned": "工具 {tool} 返回：",
        "ctx_next": "现在给出你的下一条 JSON 回复。",

        # ==== 错误信息：好版本（说清楚哪儿错了、该怎么改）====
        "err_good_unknown_tool": "没有名为 {tool} 的工具。可用的是：find_orders、get_policy、issue_refund。",
        "err_good_missing": "缺少参数 {param}。{tool} 需要这些参数：{needed}。",
        "err_good_days": "days 必须是 1 到 90 之间的整数，你传的是 {value}。不确定就填 90。",
        "err_good_category": "category 必须是 electronics / clothing / food 之一，你传的是 \"{value}\"。这个值可以从 find_orders 返回的 category 字段直接照抄。",
        "err_good_cents_float": "amount_cents 的单位是**分**，必须是整数。你传的是 {value}，看起来是「元」。{value} 元 = {fixed} 分。find_orders 返回的 amount_cents 已经是分，直接用那个数。",
        "err_good_cents_type": "amount_cents 必须是整数（单位：分），你传的是 {value}（{typ}）。",
        "err_good_reason": "reason_code 必须是 DEFECTIVE / WRONG_ITEM / CHANGED_MIND 之一，你传的是 \"{value}\"。商品坏了用 DEFECTIVE。",
        "err_good_order": "找不到订单 {value}。订单号形如 ORD-1001，可以先用 find_orders 查。",
        "err_good_expired": "订单 {order} 属于 {cat} 品类，退款窗口是 {window} 天，但它是 {ago} 天前下的单，已经超期，不能退款。",
        "err_good_amount_mismatch": "退款金额和订单金额对不上：订单 {order} 是 {actual} 分，你要退 {given} 分。",

        # ==== 错误信息：烂版本（只说「不行」，不说为什么）====
        "err_bad": "调用失败。",

        # ==== 交互输入 ====
        "ask_task": "请输入这张工单的内容（直接回车看例子）：\n> ",
        "examples_title": "几个可以直接复制的例子（第 1 个是文档里用的那个）：",
        "task_examples": [
            "客户 alice@example.com 说她买的那副耳机是坏的，帮她退款。",
            "alice@example.com 反馈耳机有质量问题，按流程给她办退款。",
            "处理一下 alice@example.com 的耳机退款，她说收到就是坏的。",
        ],
        "picked": "  ✓ 已选第 {n} 个：{task}",
        "number_out_of_range": "  （只有 {n} 个例子，就按你输的内容当工单了）",
        "need_task": "没有工单就没法跑。把工单写在模式后面，或者不带工单运行进入交互输入。",
        "no_tty": "检测到非交互环境（比如管道/脚本里跑），请把工单直接写在命令行：\n    python3 agent.py {mode} \"工单内容\"",
        "interrupted": "\n  已中断（Ctrl+C）。想换个工单重跑就再执行一次。",
        "rerun_hint": "想用同一个工单跑别的模式做对比，复制这行改模式名即可：",

        # ==== 屏幕输出 ====
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
        "task_label": "工单：",
        "mode_line": "  模式：{mode}",
        "mode_desc": "  工具描述：{d}     错误信息：{e}",
        "desc_ok": "写清楚了 ✓",
        "desc_bad": "只有函数签名 ✗",
        "label_err_ok": "说清哪儿错、怎么改 ✓",
        "label_err_bad": "只说「调用失败」 ✗",
        "round_line": "  第 {n} 轮 / 最多 {total} 轮",
        "asking": "  正在问模型…",
        "took": " 用了 {sec} 秒",
        "thinking": "  [思考] ",
        "call_ok": "  ✓ {tool}({args})",
        "call_err": "  ✗ {tool}({args})",
        "result": "     → {text}",
        "answer": "  [交代] ",
        "verdict_head": "  ─── 这一单办成了吗 ───",
        "verdict_success": "  ✓ 办成了：第 {n} 轮发起了正确的退款",
        "verdict_wrong": "  ✗ 没办成：退款发起了，但参数不对",
        "verdict_never": "  ✗ 没办成：始终没有成功发起退款",
        "stats_rounds": "  用了 {n} 轮",
        "stats_calls": "  工具调用 {total} 次，其中失败 {bad} 次",
        "stats_correct_call": "  正确的调用应该是：issue_refund(order_id=\"ORD-1001\", amount_cents=12990, reason_code=\"DEFECTIVE\")",

        # ==== 对比表 + 用法说明 ====
        "summary_title": "对比结果",
        "summary_mode": "模式：{mode}   （描述 {d} / 错误 {e}）",
        "summary_ok": "  结果：✓ 办成了",
        "summary_fail": "  结果：✗ 没办成",
        "summary_rounds": "  轮数：{n}",
        "summary_calls": "  工具调用：{total} 次（失败 {bad} 次）",
        "summary_verify": """
2×2 怎么读：

                  错误信息有用        错误信息没用
  描述写得好        good              silent_errors
  描述写得烂        vague_desc        both_bad

横着比 → 错误信息值多少钱
竖着比 → 工具描述值多少钱

★ 重点看 vague_desc：描述很烂，但错误信息会告诉它哪儿错了。
  它靠「试错」能不能补回来？补回来花了几轮？
  这几轮的钱，本来只要在工具描述里多写两行就能省掉。""",
        "unknown_mode": "✗ 不认识的模式：",
        "exp_header": "# 实验 {i}/{total}：{mode}",
        "all_warning": "\n⚠️  all 模式要跑 4 个实验，不联网所以很快，大约 2～5 分钟。",
        "help": """
======================================================================
 实验 4-1：工具设计 —— 决定成败的不是模型，是你写的那几行说明
======================================================================

同一个模型、同一个退款任务，只改工具描述和错误信息，看结果差多少。

用法：
    python3 agent.py <模式> ["工单内容"]

【2×2 四种模式】
                      错误信息有用        错误信息没用
    描述写得好          good              silent_errors
    描述写得烂          vague_desc        both_bad

【对比】
    all         四种全跑，最后打印对比表（约 2~5 分钟，不联网）

程序会在每次跑完后直接告诉你：
    - 办成了没有（比对唯一正确的那次调用，机械判定，不靠模型）
    - 用了几轮
    - 工具调用了几次，其中失败几次

任务里埋了三个坑，都是真实项目里最常见的：
    - 金额单位是「分」不是「元」
    - 原因码必须从枚举里选
    - 有两笔订单，其中一笔已过退款窗口

建议顺序：
    1. 先跑 good，确认「写清楚了就一次做对」
    2. 再跑 both_bad，看它能坏成什么样
    3. 然后 vague_desc 和 silent_errors —— **这两个才是重点**，
       它们告诉你「描述」和「错误信息」哪个更值钱

把文件开头的 LANG 改成 "en" 可切换成英文输出。
详细讲解见 README.zh-CN.md。
""",
    },
    "en": {
        "tools_good": """You have these three tools.

1. find_orders(email, days)
   Look up a customer's recent orders.
   - email: the customer's full email address, e.g. "alice@example.com"
   - days:  how many days back to search. Integer, max 90. If unsure, use 90.
   Returns a list of orders, each with order_id, category, amount_cents
   (the amount, in CENTS), days_ago, and item.

2. get_policy(category)
   Look up the refund policy for a category.
   - category: must be one of "electronics" / "clothing" / "food"
     (the category value appears in find_orders' output - copy it verbatim)
   Returns refund_window_days - past that many days, no refund is possible.

3. issue_refund(order_id, amount_cents, reason_code)
   Actually issue the refund. **This is irreversible - get the arguments right.**
   - order_id:     the order number, e.g. "ORD-1001"
   - amount_cents: the refund amount **in CENTS, and it must be an integer**.
                   129.90 in currency units is written 12990, not 129.9.
                   find_orders already returns amount_cents in cents - use it directly.
   - reason_code:  must be one of "DEFECTIVE" (item is faulty) /
                   "WRONG_ITEM" (we shipped the wrong thing) /
                   "CHANGED_MIND" (customer changed their mind)
   Returns {"ok": true, ...} on success.""",
        "tools_vague": """You have these three tools.

1. find_orders(email, days) - order lookup
2. get_policy(category) - policy lookup
3. issue_refund(order_id, amount, reason) - refund handling""",
        "sys_role": "You are an e-commerce support agent handling refund requests.",
        "sys_protocol": """Reply with ONE JSON object each turn and nothing else. Either:
  {"reasoning": "<one short sentence>", "calls": [{"tool": "<name>", "args": {...}}]}
or, once the refund has been successfully issued and the job is done:
  {"reasoning": "<one short sentence>", "answer": "<hand-off note for a colleague>"}""",
        "ctx_task": "TICKET: ",
        "ctx_step": "--- step {n} ---",
        "ctx_your_reply": "You replied: ",
        "ctx_tool_returned": "Tool {tool} returned: ",
        "ctx_next": "Now give your next JSON reply.",
        "err_good_unknown_tool": "There is no tool called {tool}. Available: find_orders, get_policy, issue_refund.",
        "err_good_missing": "Missing argument {param}. {tool} needs: {needed}.",
        "err_good_days": "days must be an integer between 1 and 90; you passed {value}. Use 90 if unsure.",
        "err_good_category": "category must be one of electronics / clothing / food; you passed \"{value}\". You can copy this value straight from find_orders' category field.",
        "err_good_cents_float": "amount_cents is in **cents** and must be an integer. You passed {value}, which looks like a currency amount. {value} in currency units = {fixed} cents. find_orders already returns amount_cents in cents - use that number.",
        "err_good_cents_type": "amount_cents must be an integer (cents); you passed {value} ({typ}).",
        "err_good_reason": "reason_code must be one of DEFECTIVE / WRONG_ITEM / CHANGED_MIND; you passed \"{value}\". A faulty item is DEFECTIVE.",
        "err_good_order": "No order {value}. Order numbers look like ORD-1001; find_orders will list them.",
        "err_good_expired": "Order {order} is in category {cat}, whose refund window is {window} days, but it was placed {ago} days ago. Past the window - no refund possible.",
        "err_good_amount_mismatch": "Refund amount doesn't match the order: order {order} is {actual} cents, you asked to refund {given} cents.",
        "err_bad": "Call failed.",
        "ask_task": "Type the ticket (Enter for examples):\n> ",
        "examples_title": "Copy one (#1 is the one used throughout the docs):",
        "task_examples": [
            "Customer alice@example.com says the headphones she bought arrived faulty. Refund her.",
            "alice@example.com reports a quality problem with her headphones - process the refund.",
            "Handle the headphone refund for alice@example.com; she says it was broken on arrival.",
        ],
        "picked": "  ok, picked #{n}: {task}",
        "number_out_of_range": "  (only {n} examples, treating your input as the ticket)",
        "need_task": "No ticket, nothing to run. Put it after the mode, or run without one to be prompted.",
        "no_tty": "Non-interactive environment detected. Put the ticket on the command line:\n    python3 agent.py {mode} \"ticket text\"",
        "interrupted": "\n  Interrupted (Ctrl+C). Run it again to try another ticket.",
        "rerun_hint": "To compare another mode on the SAME ticket, copy this and change the mode name:",
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
        "task_label": "Ticket: ",
        "mode_line": "  Mode: {mode}",
        "mode_desc": "  Tool descriptions: {d}     Error messages: {e}",
        "desc_ok": "properly written ok",
        "desc_bad": "signatures only x",
        "label_err_ok": "say what's wrong and how to fix it ok",
        "label_err_bad": "just \"Call failed\" x",
        "round_line": "  Round {n} of at most {total}",
        "asking": "  asking the model...",
        "took": " took {sec}s",
        "thinking": "  [thinking] ",
        "call_ok": "  ok {tool}({args})",
        "call_err": "  x  {tool}({args})",
        "result": "     -> {text}",
        "answer": "  [hand-off] ",
        "verdict_head": "  --- did the ticket get resolved? ---",
        "verdict_success": "  ok RESOLVED: the correct refund was issued in round {n}",
        "verdict_wrong": "  x NOT RESOLVED: a refund went out, but with wrong arguments",
        "verdict_never": "  x NOT RESOLVED: no refund was ever successfully issued",
        "stats_rounds": "  rounds used: {n}",
        "stats_calls": "  tool calls: {total}, of which {bad} failed",
        "stats_correct_call": "  the correct call was: issue_refund(order_id=\"ORD-1001\", amount_cents=12990, reason_code=\"DEFECTIVE\")",
        "summary_title": "COMPARISON",
        "summary_mode": "mode: {mode}   (descriptions {d} / errors {e})",
        "summary_ok": "  result: ok resolved",
        "summary_fail": "  result: x not resolved",
        "summary_rounds": "  rounds: {n}",
        "summary_calls": "  tool calls: {total} ({bad} failed)",
        "summary_verify": """
How to read the 2x2:

                     errors useful       errors useless
  descriptions good    good               silent_errors
  descriptions bad     vague_desc         both_bad

Read across -> what error messages are worth
Read down   -> what tool descriptions are worth

* Focus on vague_desc: the descriptions are terrible, but the errors tell it what
  went wrong. Can trial and error recover? How many rounds did it cost?
  Those rounds were purchasable in advance with two more lines of documentation.""",
        "unknown_mode": "x unknown mode: ",
        "exp_header": "# Experiment {i}/{total}: {mode}",
        "all_warning": "\n!  'all' runs 4 experiments. No network, so it's quick: 2-5 minutes.",
        "help": """
======================================================================
 Lab 4-1: Tool design - what decides the outcome is your documentation
======================================================================

Same model, same refund task. Only the tool descriptions and error messages
change. Watch how far apart the results land.

Usage:
    python3 agent.py <mode> ["ticket text"]

THE 2x2
                         errors useful       errors useless
    descriptions good      good               silent_errors
    descriptions bad       vague_desc         both_bad

COMPARISON
    all         run all four, then print a table (2-5 minutes, no network)

After each run the program tells you:
    - whether it was resolved (compared against the one correct call -
      mechanical, no model, no keywords)
    - how many rounds it took
    - how many tool calls, and how many of them failed

Three traps are buried in the task, all of them common in real projects:
    - the amount is in CENTS, not currency units
    - the reason code must come from an enum
    - there are two orders and one of them is past its refund window

Suggested order:
    1. Run good first, to confirm "documented properly, it gets it right"
    2. Run both_bad, to see how bad it gets
    3. Then vague_desc and silent_errors - **these two are the point**,
       they tell you which of the two things is worth more

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
#  第 2 部分：错误信息  ★★★ 本实验的核心之一 ★★★
# ==========================================================================
#
# 每个工具出错的时候，都会走到这个函数。
#
#   good_errors = True  → 返回「哪儿错了 + 该怎么改」
#   good_errors = False → 返回「调用失败。」
#
# 就这一个开关。请留意：**两种情况下，工具的行为是完全一样的**，
# 拒绝的调用还是拒绝，成功的调用还是成功。差别只在**告诉模型多少信息**。
#
# 这一点很重要：错误信息不是「日志」，是**下一轮上下文的一部分**。
# 你写在错误信息里的每一个字，模型下一轮都读得到 ——
# **它是你能给模型的、最及时的一次指导。**


def error(good_errors, key, **kwargs):
    if good_errors:
        return {"error": t(key, **kwargs)}
    return {"error": t("err_bad")}


# ==========================================================================
#  第 3 部分：工具的实现（Part 3）
# ==========================================================================
#
# ⚠️ 注意：**四种模式下，这三个函数的逻辑一模一样。**
#    参数校验一样严，通过条件一样。变的只有出错时说什么话。
#
#    换句话说：本实验没有让任何模式「更容易成功」，
#    只是让某些模式「更容易搞明白自己错在哪」。


def tool_find_orders(args, good_errors):
    email = args.get("email")
    if not email:
        return error(good_errors, "err_good_missing", param="email",
                     tool="find_orders", needed="email, days")

    days = args.get("days")
    if days is None:
        return error(good_errors, "err_good_missing", param="days",
                     tool="find_orders", needed="email, days")
    if not isinstance(days, int) or isinstance(days, bool) or not (1 <= days <= 90):
        return error(good_errors, "err_good_days", value=json.dumps(days))

    found = []
    for order_id, mail, category, cents, ago, item in ORDERS:
        if mail == email and ago <= days:
            found.append({"order_id": order_id, "category": category,
                          "amount_cents": cents, "days_ago": ago, "item": item})
    return {"orders": found}


def tool_get_policy(args, good_errors):
    category = args.get("category")
    if category is None:
        return error(good_errors, "err_good_missing", param="category",
                     tool="get_policy", needed="category")
    if category not in POLICY:
        return error(good_errors, "err_good_category", value=str(category))
    return {"category": category, "refund_window_days": POLICY[category]}


def tool_issue_refund(args, good_errors):
    order_id = args.get("order_id")
    # 参数名也可能被写错 —— 描述烂的时候模型只能猜，这里一并兼容不了，
    # 因为「猜错参数名」正是我们要观察的失败之一。
    if order_id is None:
        return error(good_errors, "err_good_missing", param="order_id",
                     tool="issue_refund",
                     needed="order_id, amount_cents, reason_code")

    row = None
    for candidate in ORDERS:
        if candidate[0] == order_id:
            row = candidate
    if row is None:
        return error(good_errors, "err_good_order", value=str(order_id))

    _oid, _mail, category, cents, ago, _item = row

    amount = args.get("amount_cents")
    if amount is None:
        return error(good_errors, "err_good_missing", param="amount_cents",
                     tool="issue_refund",
                     needed="order_id, amount_cents, reason_code")

    # ★ 最经典的坑：把「元」当成「分」传进来
    if isinstance(amount, float) and not amount.is_integer():
        return error(good_errors, "err_good_cents_float",
                     value=amount, fixed=int(round(amount * 100)))
    if not isinstance(amount, int) or isinstance(amount, bool):
        if isinstance(amount, float):
            amount = int(amount)
        else:
            return error(good_errors, "err_good_cents_type",
                         value=json.dumps(amount), typ=type(amount).__name__)

    reason = args.get("reason_code")
    if reason is None:
        return error(good_errors, "err_good_missing", param="reason_code",
                     tool="issue_refund",
                     needed="order_id, amount_cents, reason_code")
    if reason not in REASON_CODES:
        return error(good_errors, "err_good_reason", value=str(reason))

    # 业务规则：过了退款窗口就不能退
    window = POLICY[category]
    if ago > window:
        return error(good_errors, "err_good_expired", order=order_id,
                     cat=category, window=window, ago=ago)

    if amount != cents:
        return error(good_errors, "err_good_amount_mismatch", order=order_id,
                     actual=cents, given=amount)

    return {"ok": True, "order_id": order_id, "refunded_cents": amount,
            "reason_code": reason}


TOOLS = {"find_orders": tool_find_orders,
         "get_policy": tool_get_policy,
         "issue_refund": tool_issue_refund}


# ==========================================================================
#  第 4 部分：拼上下文（Part 4）
# ==========================================================================


def build_system_prompt(mode):
    tools_text = t("tools_good") if GOOD_DESC[mode] else t("tools_vague")
    return "\n\n".join([t("sys_role"), tools_text, t("sys_protocol")])


def render_context(task, steps):
    lines = [t("ctx_task") + task, ""]
    for step in steps:
        lines.append(t("ctx_step", n=step["number"]))
        lines.append(t("ctx_your_reply")
                     + json.dumps(step["assistant"], ensure_ascii=False))
        for one in step["results"]:
            lines.append(t("ctx_tool_returned", tool=str(one["tool"]))
                         + json.dumps(one["result"], ensure_ascii=False))
        lines.append("")
    lines.append(t("ctx_next"))
    return "\n".join(lines)


def extract_tool_calls(reply):
    calls = reply.get("calls")
    if isinstance(calls, list) and len(calls) > 0:
        return calls
    if reply.get("tool"):
        return [{"tool": reply["tool"], "args": reply.get("args", {})}]
    return []


# ==========================================================================
#  第 5 部分：主循环（Part 5）
# ==========================================================================


def run(task, mode="good", backend=None, verbose=True):
    steps = []
    system_prompt = build_system_prompt(mode)
    good_errors = GOOD_ERRORS[mode]

    total_calls = 0
    bad_calls = 0
    success_round = None      # 第几轮发起了**正确**的退款
    any_refund = False        # 有没有成功发起过退款（哪怕参数不对）

    if verbose:
        print("")
        print("=" * 68)
        print(t("mode_line", mode=mode))
        print(t("mode_desc",
                d=t("desc_ok") if GOOD_DESC[mode] else t("desc_bad"),
                e=t("label_err_ok") if good_errors else t("label_err_bad")))
        print("=" * 68)

    for round_number in range(1, MAX_ROUNDS + 1):
        prompt = render_context(task, steps)

        if verbose:
            print("")
            print(t("round_line", n=round_number, total=MAX_ROUNDS))

        if SHOW_PROMPT:
            print("")
            print("  ┌─── 实际发给模型的内容 " + "-" * 38)
            for one_line in prompt.split("\n"):
                print("  │ " + one_line)
            print("  └" + "-" * 60)

        if verbose:
            print(t("asking"), end="", flush=True)

        call_start = time.time()
        raw_text = complete(prompt, system_prompt, backend=backend)
        if verbose:
            print(t("took", sec=round(time.time() - call_start, 1)))

        reply = parse_json_reply(raw_text)

        if verbose and reply.get("reasoning"):
            print(t("thinking") + str(reply["reasoning"]))

        wanted_calls = extract_tool_calls(reply)

        if "answer" in reply or len(wanted_calls) == 0:
            answer = reply.get("answer", raw_text.strip())
            if verbose:
                print("")
                print(t("answer") + str(answer))
            break

        results_this_round = []
        for one_call in wanted_calls:
            tool_name = one_call.get("tool")
            call_args = one_call.get("args", {})
            if not isinstance(call_args, dict):
                call_args = {}

            total_calls = total_calls + 1

            if tool_name in TOOLS:
                result = TOOLS[tool_name](call_args, good_errors)
            else:
                result = error(good_errors, "err_good_unknown_tool",
                               tool=str(tool_name))

            failed = "error" in result
            if failed:
                bad_calls = bad_calls + 1

            # ★ 判定：这次调用是不是那唯一正确的一次？（纯机械比对）
            if tool_name == "issue_refund" and result.get("ok"):
                any_refund = True
                if (call_args.get("order_id") == CORRECT_CALL["args"]["order_id"]
                        and call_args.get("amount_cents") == CORRECT_CALL["args"]["amount_cents"]
                        and call_args.get("reason_code") == CORRECT_CALL["args"]["reason_code"]
                        and success_round is None):
                    success_round = round_number

            if verbose:
                shown = json.dumps(call_args, ensure_ascii=False)
                if len(shown) > 90:
                    shown = shown[:87] + "..."
                line_key = "call_err" if failed else "call_ok"
                print(t(line_key, tool=str(tool_name), args=shown))
                result_text = json.dumps(result, ensure_ascii=False)
                if len(result_text) > 150:
                    result_text = result_text[:147] + "..."
                print(t("result", text=result_text))

            results_this_round.append({"tool": tool_name, "result": result})

        steps.append({"number": round_number, "assistant": reply,
                      "results": results_this_round})

        if success_round is not None:
            # 办成了就可以停了 —— 再跑下去只是浪费
            break

    if verbose:
        print("")
        print(t("verdict_head"))
        if success_round is not None:
            print(t("verdict_success", n=success_round))
        elif any_refund:
            print(t("verdict_wrong"))
            print(t("stats_correct_call"))
        else:
            print(t("verdict_never"))
            print(t("stats_correct_call"))
        print(t("stats_rounds", n=len(steps)))
        print(t("stats_calls", total=total_calls, bad=bad_calls))
        print("")

    return {"mode": mode, "ok": success_round is not None,
            "rounds": len(steps), "calls": total_calls, "bad": bad_calls}


# ==========================================================================
#  第 6 部分：命令行入口（Part 6）
# ==========================================================================


def ask_for_task(mode):
    if not sys.stdin.isatty():
        print("")
        print(t("no_tty", mode=mode))
        sys.exit(1)

    answer = input(t("ask_task")).strip()
    if answer:
        return _resolve_choice(answer)

    print("")
    print(t("examples_title"))
    examples = t("task_examples")
    for i in range(len(examples)):
        print("  " + str(i + 1) + ". " + examples[i])
    print("")
    answer = input(t("ask_task")).strip()

    if not answer:
        print("")
        print(t("need_task"))
        sys.exit(1)
    return _resolve_choice(answer)


def _resolve_choice(answer):
    if not answer.isdigit():
        return answer
    examples = t("task_examples")
    index = int(answer)
    if 1 <= index <= len(examples):
        chosen = examples[index - 1]
        print(t("picked", n=index, task=chosen))
        return chosen
    print(t("number_out_of_range", n=len(examples)))
    return answer


def print_rerun_hint(task, mode_arg):
    others = [m for m in MODES if m != mode_arg]
    if len(others) == 0:
        return
    print("")
    print(t("rerun_hint"))
    print('    python3 agent.py ' + others[0] + ' "' + task + '"')
    print("")


def print_help():
    print(t("help"))


def print_summary(results):
    print("")
    print("=" * 70)
    print(t("summary_title"))
    print("=" * 70)
    for r in results:
        m = r["mode"]
        print("")
        print(t("summary_mode", mode=m,
                d="✓" if GOOD_DESC[m] else "✗",
                e="✓" if GOOD_ERRORS[m] else "✗"))
        print(t("summary_ok") if r["ok"] else t("summary_fail"))
        print(t("summary_rounds", n=r["rounds"]))
        print(t("summary_calls", total=r["calls"], bad=r["bad"]))
    print(t("summary_verify"))


def _quiet_ctrl_c(exc_type, exc_value, tb):
    if exc_type is KeyboardInterrupt:
        print(t("interrupted"))
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

    if len(sys.argv) > 2:
        task = " ".join(sys.argv[2:])
    else:
        task = ask_for_task(mode_arg)

    try:
        backend = detect_backend()
    except RuntimeError:
        print("")
        print(t("no_backend_title"))
        print(t("no_backend_help"))
        sys.exit(1)

    print(t("backend") + backend)
    print(t("task_label") + task)

    if mode_arg == "all":
        print(t("all_warning"))
        print("")
        results = []
        for mode_index in range(len(MODES)):
            m = MODES[mode_index]
            print("")
            print("#" * 70)
            print(t("exp_header", i=mode_index + 1, total=len(MODES), mode=m))
            print("#" * 70)
            results.append(run(task, mode=m, backend=backend))
        print_summary(results)
    else:
        run(task, mode=mode_arg, backend=backend)
        print_rerun_hint(task, mode_arg)
