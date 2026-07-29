"""
实验 4-2：工具太多怎么办 —— 一个没能复现的传说，和一笔真实的账

实验 4-1 讲的是**一个**工具怎么写。这个实验问：**四十个工具摆在面前，它选得对吗？**

我本来是打算复现那个流行说法的：「工具超过 20 个，模型就选不准了」。
为此我特意准备了 6 个**长得极像**的工具（全都是「把消息发给某人」），
外加会误导人的关键词陷阱。

**结果它一次都没选错。** 实测 15 次全对（详见 SOLUTION）。

所以这个实验最后教的不是「工具多了会选错」，而是两件更有用的事：

    1. 这个传说在当前的模型上**没有复现** —— 别照着过时的经验做架构决策
    2. 工具多了确实有代价，但代价**不在准确率，在提示词长度**：
       8 个工具 331 字  →  40 个工具 1249 字，**每一次调用都要付**

于是「先检索再给它看」这件事的理由变了：不是因为模型看不过来，
**是因为你在为没用到的 35 个工具付钱。**

    python3 agent.py                 # 打印用法说明
    python3 agent.py few             # 只给 8 个工具（基线）
    python3 agent.py many            # 给 40 个互不相干的工具
    python3 agent.py confusable      # 40 个，其中 6 个长得像 ★
    python3 agent.py retrieved       # 还是那 40 个，但先用 BM25 筛到 8 个 ★★
    python3 agent.py all             # 四种全跑 + 对比表

不需要 API key，也不联网。

★ 判定是机械的：每个任务有唯一正确的工具名，比对字符串即可。

详细讲解见 README.zh-CN.md（中文）/ README.md（英文）。
"""

import math
import re
import sys
import time

from llm import complete, detect_backend, parse_json_reply


# --------------------------------------------------------------------------
#  可以改的开关（Settings）
# --------------------------------------------------------------------------

LANG = "zh"          # "zh" | "en" —— 同时切换输出和发给模型的提示词

RETRIEVE_K = 8       # retrieved 模式先筛到几个工具

SHOW_PROMPT = False  # 改成 True 会打印真正发给模型的完整文本


MODES = [
    "few",         # 只给 8 个工具（正确的那个 + 7 个不相干的）
    "many",        # 40 个互不相干的工具
    "confusable",  # 40 个，其中 6 个是「发消息」类的近义工具 ★
    "retrieved",   # 还是 confusable 那 40 个，但先用 BM25 筛到 8 个 ★★
]


# ==========================================================================
#  第 1 部分：工具目录（Part 1）
# ==========================================================================
#
# 40 个工具，只有名字和一句话描述 —— 这个实验不真的执行它们，
# 只看**模型选哪个**。
#
# 注意最后 6 个（标了「★ 近义组」）：它们全都是「把消息发给某人」，
# 差别只在**发给谁、走哪个渠道**。这一组是本实验的关键。


TOOL_CATALOG = {
    "zh": [
        # --- 订单与商品 ---
        ("get_order", "按订单号查订单详情"),
        ("list_orders", "列出某个客户的历史订单"),
        ("cancel_order", "取消一个尚未发货的订单"),
        ("update_shipping_address", "修改订单的收货地址"),
        ("track_shipment", "查询包裹物流状态"),
        ("get_product", "查询商品详情和库存"),
        ("search_products", "按关键词搜索商品"),
        ("update_inventory", "调整某个商品的库存数量"),
        ("list_categories", "列出所有商品品类"),
        ("get_price_history", "查询某商品的历史价格"),
        # --- 支付与退款 ---
        ("issue_refund", "对一笔订单发起退款"),
        ("get_payment", "查询一笔支付的状态"),
        ("retry_payment", "对失败的支付重新扣款"),
        ("apply_coupon", "给订单应用一张优惠券"),
        ("get_invoice", "获取订单的发票"),
        ("split_payment", "把一笔支付拆成多笔"),
        # --- 客户 ---
        ("get_customer", "按邮箱或 ID 查客户资料"),
        ("update_customer", "修改客户资料"),
        ("get_loyalty_points", "查询客户的积分余额"),
        ("add_loyalty_points", "给客户加积分"),
        ("block_customer", "封禁一个客户账号"),
        ("merge_customers", "合并两个重复的客户账号"),
        # --- 工单 ---
        ("create_ticket", "新建一张客服工单"),
        ("close_ticket", "关闭一张工单"),
        ("assign_ticket", "把工单指派给某个客服"),
        ("escalate_ticket", "把工单升级给主管"),
        ("get_ticket_history", "查询一张工单的处理历史"),
        # --- 报表与内部 ---
        ("get_daily_sales", "查询某天的销售汇总"),
        ("export_report", "导出一份报表文件"),
        ("get_refund_rate", "查询某段时间的退款率"),
        ("list_agents", "列出所有客服人员"),
        ("get_agent_workload", "查询某个客服的工作量"),
        ("schedule_meeting", "在日历上安排一场会议"),
        ("create_task", "在内部任务系统里建一个任务"),
        # --- ★ 近义组：全都是「把消息发出去」，差别在收件人和渠道 ---
        ("email_customer", "给客户发一封邮件"),
        ("send_internal_email", "给公司内部同事发一封邮件"),
        ("send_sms", "给客户发一条手机短信"),
        ("push_notification", "给客户的手机 App 推送一条通知"),
        ("send_slack_message", "在公司 Slack 里发一条消息"),
        ("add_ticket_comment", "在工单里追加一条备注（客户看不到）"),
    ],
    "en": [
        ("get_order", "Look up an order by its ID"),
        ("list_orders", "List a customer's past orders"),
        ("cancel_order", "Cancel an order that hasn't shipped"),
        ("update_shipping_address", "Change the delivery address on an order"),
        ("track_shipment", "Check the delivery status of a parcel"),
        ("get_product", "Look up product details and stock"),
        ("search_products", "Search products by keyword"),
        ("update_inventory", "Adjust the stock level of a product"),
        ("list_categories", "List all product categories"),
        ("get_price_history", "Look up a product's price history"),
        ("issue_refund", "Issue a refund against an order"),
        ("get_payment", "Check the status of a payment"),
        ("retry_payment", "Retry a failed payment"),
        ("apply_coupon", "Apply a coupon to an order"),
        ("get_invoice", "Fetch an order's invoice"),
        ("split_payment", "Split one payment into several"),
        ("get_customer", "Look up a customer by email or ID"),
        ("update_customer", "Edit a customer's profile"),
        ("get_loyalty_points", "Check a customer's points balance"),
        ("add_loyalty_points", "Credit points to a customer"),
        ("block_customer", "Ban a customer account"),
        ("merge_customers", "Merge two duplicate customer accounts"),
        ("create_ticket", "Open a new support ticket"),
        ("close_ticket", "Close a ticket"),
        ("assign_ticket", "Assign a ticket to an agent"),
        ("escalate_ticket", "Escalate a ticket to a supervisor"),
        ("get_ticket_history", "Look up a ticket's handling history"),
        ("get_daily_sales", "Get the sales summary for a day"),
        ("export_report", "Export a report file"),
        ("get_refund_rate", "Get the refund rate over a period"),
        ("list_agents", "List all support agents"),
        ("get_agent_workload", "Check an agent's workload"),
        ("schedule_meeting", "Book a meeting on the calendar"),
        ("create_task", "Create a task in the internal tracker"),
        ("email_customer", "Send an email to a customer"),
        ("send_internal_email", "Send an email to a colleague inside the company"),
        ("send_sms", "Send a text message to a customer's phone"),
        ("push_notification", "Push a notification to a customer's mobile app"),
        ("send_slack_message", "Post a message in the company Slack"),
        ("add_ticket_comment", "Append an internal note to a ticket (not customer-visible)"),
    ],
}

# 近义组在目录里的位置（最后 6 个）。few 模式要把它们排除掉。
CONFUSABLE_NAMES = ["email_customer", "send_internal_email", "send_sms",
                    "push_notification", "send_slack_message", "add_ticket_comment"]

# few 模式里除了正确答案之外，再放这 7 个不相干的
FEW_FILLER = ["get_order", "track_shipment", "get_product", "create_ticket",
              "get_customer", "issue_refund", "get_daily_sales"]


# ==========================================================================
#  第 2 部分：任务和标准答案（Part 2）
# ==========================================================================
#
# 每个任务都只有一个正确工具。之所以能机械判分，是因为标准答案是我们定的。
#
# ★ 六个任务全都落在那个「近义组」里 —— 这是故意的：
#   要看模型能不能在 6 个「都是发消息」的工具里挑对那一个。
#
#   例 1~3 是普通题：请求里直接点明了渠道（「发个邮件」「推个提醒」）。
#   例 4~6 是**陷阱题**：我故意在请求里塞了会误导的关键词。
#     - 例 4 里同时出现「邮件」和「短信」，但正确答案是「工单备注」
#     - 例 5 不点明渠道，要靠排除法推理（没手机号、没装 App → 只能发邮件）
#     - 例 6 里出现「客户的短信」，但收件人其实是内部同事
#
#   实测这 6 道题模型全对。你可以试着设计第 7 道把它骗倒 —— 见 README 练习 1。

TASKS = {
    "zh": [
        {"text": "客户 alice@example.com 的退款已经打回她的银行卡了，"
                 "给她发个邮件通知一下。",
         "correct": "email_customer"},
        {"text": "这张工单我处理不完了，在工单里留个备注说明进度，"
                 "别让客户看到。",
         "correct": "add_ticket_comment"},
        {"text": "促销明天开始，给所有装了 App 的客户推个提醒。",
         "correct": "push_notification"},
        # --- 以下三道是陷阱题：关键词故意误导 ---
        {"text": "客户在邮件里投诉说收不到我们的短信。"
                 "把处理进度记录下来，只给内部看。",
         "correct": "add_ticket_comment"},
        {"text": "客户 alice 没留手机号，也没装我们的 App。"
                 "退款到账了，通知她一下。",
         "correct": "email_customer"},
        {"text": "这个客户的短信一直发不出去。老王不看 Slack，"
                 "你把这件事发邮件同步给他。",
         "correct": "send_internal_email"},
    ],
    "en": [
        {"text": "The refund for alice@example.com has landed back on her card - "
                 "send her an email letting her know.",
         "correct": "email_customer"},
        {"text": "I can't finish this ticket today. Leave a note on it explaining "
                 "where things stand - the customer must not see it.",
         "correct": "add_ticket_comment"},
        {"text": "The sale starts tomorrow. Send a reminder to every customer who "
                 "has the mobile app.",
         "correct": "push_notification"},
        # --- the next three are traps: deliberately misleading keywords ---
        {"text": "A customer emailed to complain that our text messages never "
                 "arrive. Record where we've got to - internal eyes only.",
         "correct": "add_ticket_comment"},
        {"text": "Customer alice left no phone number and doesn't have our app. "
                 "Her refund has landed - let her know.",
         "correct": "email_customer"},
        {"text": "This customer's texts keep failing to send. Wang doesn't read "
                 "Slack, so email him about it.",
         "correct": "send_internal_email"},
    ],
}


# --------------------------------------------------------------------------
#  所有对用户可见的文字，按语言分开放（包含发给模型的提示词）
# --------------------------------------------------------------------------

TEXT = {
    "zh": {
        "sys_role": "你是一个电商客服 agent。根据下面的请求，从工具列表里选出**唯一**该用的那个工具。",
        "sys_tools_head": "可用的工具：",
        "sys_protocol": """只输出一个 JSON 对象，不要有别的内容：
  {"reasoning": "<一句话说明为什么选它>", "tool": "<工具名>"}""",
        "ask_task": "请输入一个请求（直接回车看例子）：\n> ",
        "examples_title": "六个例子（都要在 6 个「发消息」类工具里挑对一个；4~6 是陷阱题）：",
        "picked": "  ✓ 已选第 {n} 个：{task}",
        "number_out_of_range": "  （只有 {n} 个例子，就按你输的内容当请求了）",
        "custom_no_answer": "  ⚠️ 你输的是自定义请求，程序没有标准答案，所以只显示它选了什么，不判对错。",
        "need_task": "没有请求就没法跑。把请求写在模式后面，或者不带请求运行进入交互输入。",
        "no_tty": "检测到非交互环境（比如管道/脚本里跑），请把请求直接写在命令行：\n    python3 agent.py {mode} \"你的请求\"",
        "interrupted": "\n  已中断（Ctrl+C）。想换个请求重跑就再执行一次。",
        "rerun_hint": "想用同一个请求跑别的模式做对比，复制这行改模式名即可：",
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
        "task_label": "请求：",
        "correct_label": "标准答案：",
        "mode_line": "  模式：{mode}",
        "mode_desc": "  {desc}",
        "desc_few": "只给 8 个工具，近义组只留正确的那一个",
        "desc_many": "给 40 个工具里的 34 个 —— 全都互不相干，近义组整组去掉",
        "desc_confusable": "给全部 40 个 —— 含 6 个「都是发消息」的近义工具",
        "desc_retrieved": "还是那 40 个，但先用 BM25 按请求筛到 {k} 个再给模型",
        "n_tools": "  工具数量：{n}      提示词长度：{chars} 字",
        "retrieved_head": "  ┌─ BM25 筛出来的 {n} 个工具（模型只看得到这些）───",
        "retrieved_line": "  │ {mark} {name} —— {desc}",
        "retrieved_foot": "  └────────────────────────────────────────────",
        "retrieved_missing": "  ☠ 正确答案 {name} **没被筛进来** —— 后面选什么都不可能对了",
        "asking": "  正在问模型…",
        "took": " 用了 {sec} 秒",
        "thinking": "  [理由] ",
        "chose": "  [选择] {tool}",
        "verdict_head": "  ─── 选对了吗 ───",
        "verdict_ok": "  ✓ 选对了",
        "verdict_bad": "  ✗ 选错了：应该是 {correct}",
        "verdict_unknown": "  （自定义请求，无标准答案）",
        "summary_title": "对比结果",
        "summary_mode": "模式：{mode}",
        "summary_tools": "  工具数：{n}      提示词：{chars} 字",
        "summary_result": "  结果：{r}",
        "summary_ok": "✓ 选对",
        "summary_bad": "✗ 选错（选了 {got}，应为 {want}）",
        "summary_verify": """
一张表怎么读：

  先看「结果」那一列 —— 大概率四个全对，包括塞了 6 个近义工具的 confusable。
  **「工具一多模型就选不准」这个说法，在这个规模上没有复现。**

  所以真正要看的是「提示词」那一列：
    few         ~331 字
    confusable  ~1249 字     ← 多出来的 900 字，**每一次调用都要重付一遍**
    retrieved   ~355 字      ← 准确率没掉，长度回到和 few 一个量级

★ 结论要反过来说：
  给工具做检索，理由**不是**「模型看不过来」，而是
  **「你在为这次根本用不到的 30 多个工具付钱」**。

  这是一笔成本账，不是一个能力问题 —— 两者的解法优先级完全不同。

⚠️ 但检索不是白拿的：它引入了一个 few/many/confusable 都没有的失败模式 ——
   **万一没检索到那个正确的工具，后面选什么都不可能对。**
   这就是实验 3-5 里的召回率天花板，一模一样。""",
        "unknown_mode": "✗ 不认识的模式：",
        "exp_header": "# 实验 {i}/{total}：{mode}",
        "all_warning": "\n⚠️  all 模式要跑 4 个实验，不联网所以很快，大约 1～3 分钟。",
        "help": """
======================================================================
 实验 4-2：工具太多怎么办 —— 一个没能复现的传说，和一笔真实的账
======================================================================

同一个请求，四种工具列表。本来是想看它会不会选错 ——
实测它**基本不会**，所以真正要看的是**提示词长度**那一列。

用法：
    python3 agent.py <模式> ["你的请求"]

【四种模式】
    few          只给 8 个工具（基线）
    many         给 34 个互不相干的工具
    confusable   给全部 40 个，含 6 个「都是发消息」的近义工具 ★
    retrieved    还是 40 个，但先用 BM25 筛到 8 个 ★★

【对比】
    all          四种全跑，最后打印对比表（约 1~3 分钟，不联网）

程序会告诉你：
    - 工具数量和提示词长度
    - 它选了哪个工具、为什么
    - 选对没有（三个内置例子都有标准答案，机械判定）

★ 重点看两件事：
  1. 四种模式的**准确率**（实测基本都对 —— 这本身就是个结论）
  2. 四种模式的**提示词长度**（331 vs 1249 字，差 3.8 倍，每次调用都付）

  例 4~6 是我专门设计来「骗」模型的陷阱题（关键词故意误导），
  跑跑看你能不能把它骗倒。骗倒了记得当成发现记下来。

把文件开头的 LANG 改成 "en" 可切换成英文输出。
详细讲解见 README.zh-CN.md。
""",
    },
    "en": {
        "sys_role": "You are an e-commerce support agent. Given the request below, pick the ONE tool from the list that should be used.",
        "sys_tools_head": "Available tools:",
        "sys_protocol": """Reply with ONE JSON object and nothing else:
  {"reasoning": "<one sentence on why this tool>", "tool": "<tool name>"}""",
        "ask_task": "Type a request (Enter for examples):\n> ",
        "examples_title": "Six examples (each needs the right one of 6 messaging tools; 4-6 are traps):",
        "picked": "  ok, picked #{n}: {task}",
        "number_out_of_range": "  (only {n} examples, treating your input as the request)",
        "custom_no_answer": "  !  Custom request - the program has no ground truth, so it will show the choice without scoring it.",
        "need_task": "No request, nothing to run. Put it after the mode, or run without one to be prompted.",
        "no_tty": "Non-interactive environment detected. Put the request on the command line:\n    python3 agent.py {mode} \"your request\"",
        "interrupted": "\n  Interrupted (Ctrl+C). Run it again to try another request.",
        "rerun_hint": "To compare another mode on the SAME request, copy this and change the mode name:",
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
        "task_label": "Request: ",
        "correct_label": "Ground truth: ",
        "mode_line": "  Mode: {mode}",
        "mode_desc": "  {desc}",
        "desc_few": "8 tools only; of the confusable group, just the correct one",
        "desc_many": "34 of the 40 - all unrelated to each other, confusable group removed",
        "desc_confusable": "all 40 - including 6 tools that all 'send a message'",
        "desc_retrieved": "the same 40, but BM25 narrows them to {k} before the model sees them",
        "n_tools": "  tools offered: {n}      prompt length: {chars} chars",
        "retrieved_head": "  +- the {n} tools BM25 kept (all the model sees) ---",
        "retrieved_line": "  | {mark} {name} - {desc}",
        "retrieved_foot": "  +--------------------------------------------",
        "retrieved_missing": "  ! the correct tool {name} **was not retrieved** - nothing downstream can be right now",
        "asking": "  asking the model...",
        "took": " took {sec}s",
        "thinking": "  [reason] ",
        "chose": "  [chose] {tool}",
        "verdict_head": "  --- right tool? ---",
        "verdict_ok": "  ok correct",
        "verdict_bad": "  x wrong: should have been {correct}",
        "verdict_unknown": "  (custom request, no ground truth)",
        "summary_title": "COMPARISON",
        "summary_mode": "mode: {mode}",
        "summary_tools": "  tools: {n}      prompt: {chars} chars",
        "summary_result": "  result: {r}",
        "summary_ok": "ok correct",
        "summary_bad": "x wrong (chose {got}, wanted {want})",
        "summary_verify": """
How to read this table:

  Look at the "result" column first - most likely all four are correct, including
  confusable with its 6 lookalike tools.
  **"Models get confused once you pass ~20 tools" did not reproduce at this scale.**

  So the column that actually matters is "prompt":
    few         ~331 chars
    confusable  ~1249 chars    <- those extra 900 chars are re-paid on EVERY call
    retrieved   ~355 chars     <- accuracy unchanged, length back near few

* The conclusion runs backwards from the folklore:
  the reason to retrieve tools is **not** "the model can't cope", it's
  **"you are paying for 30-odd tools this request will never touch"**.

  That's a cost problem, not a capability problem - and the two have very
  different fix priorities.

! But retrieval isn't free: it adds a failure mode that few/many/confusable don't
  have - **if the right tool isn't retrieved, nothing downstream can be correct.**
  Same recall ceiling as lab 3-5.""",
        "unknown_mode": "x unknown mode: ",
        "exp_header": "# Experiment {i}/{total}: {mode}",
        "all_warning": "\n!  'all' runs 4 experiments. No network, so it's quick: 1-3 minutes.",
        "help": """
======================================================================
 Lab 4-2: Too many tools - a folklore that didn't reproduce, and a real bill
======================================================================

One request, four tool lists. This was built to catch the model picking wrong -
**it basically doesn't**, so the column to watch is prompt length.

Usage:
    python3 agent.py <mode> ["your request"]

THE FOUR MODES
    few          8 tools only (baseline)
    many         34 mutually unrelated tools
    confusable   all 40, including 6 tools that all 'send a message'  <-
    retrieved    the same 40, narrowed to 8 by BM25 first  <-<-

COMPARISON
    all          run all four, then print a table (1-3 minutes, no network)

The program reports:
    - tool count and prompt length
    - which tool it chose, and why
    - whether that was right (the three built-in examples have ground truth)

* Two things to watch:
  1. **accuracy** across the four modes (measured: all correct - that IS the finding)
  2. **prompt length** across the four modes (331 vs 1249 chars, 3.8x, every call)

  Examples 4-6 are traps built to fool the model (deliberately misleading
  keywords). See if you can fool it. If you succeed, write it down - that's a
  finding.

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
#  第 3 部分：BM25（和实验 3-5 是同一份代码）
# ==========================================================================
#
# 这里检索的对象从「用户记忆」换成了「工具描述」，算法一个字没改。
#
# ★ 这就是 3-2 那句话的兑现：**检索不是记忆专用的，它是「候选太多」的通用解法。**


def tokenize(text):
    tokens = []
    for word in re.findall(r"[a-zA-Z0-9_]+", text.lower()):
        tokens.append(word)
        # 工具名是 snake_case，拆开之后才能和自然语言对上
        for piece in word.split("_"):
            if piece and piece != word:
                tokens.append(piece)
    for run in re.findall(r"[一-鿿]+", text):
        if len(run) == 1:
            tokens.append(run)
        for i in range(len(run) - 1):
            tokens.append(run[i:i + 2])
    return tokens


def bm25_rank(query, documents):
    """返回文档下标，按 BM25 分数从高到低。"""
    k1 = 1.5
    b = 0.75
    doc_tokens = [tokenize(d) for d in documents]
    n_docs = len(doc_tokens)

    doc_freq = {}
    for tokens in doc_tokens:
        for w in set(tokens):
            doc_freq[w] = doc_freq.get(w, 0) + 1
    avg_len = sum(len(x) for x in doc_tokens) / max(1, n_docs)

    query_tokens = set(tokenize(query))
    scores = []
    for i in range(n_docs):
        tokens = doc_tokens[i]
        score = 0.0
        for w in query_tokens:
            tf = tokens.count(w)
            if tf == 0:
                continue
            df = doc_freq.get(w, 0)
            idf = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
            score = score + idf * tf * (k1 + 1) / (
                tf + k1 * (1 - b + b * len(tokens) / avg_len))
        scores.append(score)

    return sorted(range(n_docs), key=lambda i: scores[i], reverse=True)


# ==========================================================================
#  第 4 部分：四种模式怎么挑工具列表  ★★★ 本实验的核心 ★★★
# ==========================================================================


def pick_tools(mode, task_text, correct_tool):
    """决定这一轮给模型看哪些工具。返回 (工具列表, 是否命中正确工具)。"""
    catalog = TOOL_CATALOG[LANG]
    by_name = {}
    for name, desc in catalog:
        by_name[name] = desc

    if mode == "few":
        # 正确的那个 + 7 个完全不相干的。近义组的其他 5 个不给。
        names = [correct_tool] + [x for x in FEW_FILLER if x != correct_tool]
        names = names[:8]
        return [(n, by_name[n]) for n in names if n in by_name], True

    if mode == "many":
        # 把整个近义组去掉，只留正确的那一个 —— 于是工具很多，但没有长得像的
        names = [n for n, _ in catalog
                 if n not in CONFUSABLE_NAMES or n == correct_tool]
        return [(n, by_name[n]) for n in names], True

    if mode == "confusable":
        # 全部 40 个，近义组一个不少
        return list(catalog), True

    # retrieved：还是那 40 个，但先用 BM25 按请求筛一遍
    documents = [name + " " + desc for name, desc in catalog]
    ranked = bm25_rank(task_text, documents)[:RETRIEVE_K]
    kept = [catalog[i] for i in ranked]
    hit = any(name == correct_tool for name, _ in kept)
    return kept, hit


def build_system_prompt(tools):
    lines = [t("sys_role"), "", t("sys_tools_head")]
    for name, desc in tools:
        lines.append("- " + name + "：" + desc if LANG == "zh"
                     else "- " + name + " - " + desc)
    lines.append("")
    lines.append(t("sys_protocol"))
    return "\n".join(lines)


# ==========================================================================
#  第 5 部分：主流程（Part 5）
# ==========================================================================


def run(task_text, correct_tool, mode="confusable", backend=None, verbose=True):
    tools, retrieval_hit = pick_tools(mode, task_text, correct_tool)
    system_prompt = build_system_prompt(tools)

    desc = {
        "few": t("desc_few"),
        "many": t("desc_many"),
        "confusable": t("desc_confusable"),
        "retrieved": t("desc_retrieved", k=RETRIEVE_K),
    }[mode]

    if verbose:
        print("")
        print("=" * 68)
        print(t("mode_line", mode=mode))
        print(t("mode_desc", desc=desc))
        print("=" * 68)
        print("")
        print(t("n_tools", n=len(tools), chars=len(system_prompt)))

        if mode == "retrieved":
            print("")
            print(t("retrieved_head", n=len(tools)))
            for name, tool_desc in tools:
                mark = "★" if name == correct_tool else " "
                print(t("retrieved_line", mark=mark, name=name, desc=tool_desc))
            print(t("retrieved_foot"))
            if correct_tool and not retrieval_hit:
                print(t("retrieved_missing", name=correct_tool))

    if SHOW_PROMPT:
        print("")
        print("  ┌─── 实际发给模型的系统提示词 " + "-" * 30)
        for one_line in system_prompt.split("\n"):
            print("  │ " + one_line)
        print("  └" + "-" * 60)

    if verbose:
        print("")
        print(t("asking"), end="", flush=True)

    call_start = time.time()
    raw_text = complete(task_text, system_prompt, backend=backend)
    if verbose:
        print(t("took", sec=round(time.time() - call_start, 1)))

    reply = parse_json_reply(raw_text)
    chosen = str(reply.get("tool", "")).strip()

    if verbose:
        if reply.get("reasoning"):
            print(t("thinking") + str(reply["reasoning"]))
        print(t("chose", tool=chosen if chosen else "—"))
        print("")
        print(t("verdict_head"))
        if not correct_tool:
            print(t("verdict_unknown"))
        elif chosen == correct_tool:
            print(t("verdict_ok"))
        else:
            print(t("verdict_bad", correct=correct_tool))
        print("")

    return {"mode": mode, "n_tools": len(tools), "chars": len(system_prompt),
            "chosen": chosen, "ok": (chosen == correct_tool) if correct_tool else None,
            "retrieval_hit": retrieval_hit}


# ==========================================================================
#  第 6 部分：命令行入口（Part 6）
# ==========================================================================


def ask_for_task(mode):
    """让用户输入请求。返回 (请求文本, 标准答案或 None)。"""
    if not sys.stdin.isatty():
        print("")
        print(t("no_tty", mode=mode))
        sys.exit(1)

    answer = input(t("ask_task")).strip()
    if answer:
        return _resolve_choice(answer)

    print("")
    print(t("examples_title"))
    examples = TASKS[LANG]
    for i in range(len(examples)):
        print("  " + str(i + 1) + ". " + examples[i]["text"])
    print("")
    answer = input(t("ask_task")).strip()

    if not answer:
        print("")
        print(t("need_task"))
        sys.exit(1)
    return _resolve_choice(answer)


def _resolve_choice(answer):
    examples = TASKS[LANG]
    if answer.isdigit():
        index = int(answer)
        if 1 <= index <= len(examples):
            chosen = examples[index - 1]
            print(t("picked", n=index, task=chosen["text"]))
            return chosen["text"], chosen["correct"]
        print(t("number_out_of_range", n=len(examples)))
    # 自定义请求：先看看是不是恰好等于某个内置例子
    for one in examples:
        if one["text"] == answer:
            return answer, one["correct"]
    print(t("custom_no_answer"))
    return answer, None


def print_rerun_hint(task_text, mode_arg):
    others = [m for m in MODES if m != mode_arg]
    if len(others) == 0:
        return
    print("")
    print(t("rerun_hint"))
    print('    python3 agent.py ' + others[0] + ' "' + task_text + '"')
    print("")


def print_help():
    print(t("help"))


def print_summary(results, correct_tool):
    print("")
    print("=" * 70)
    print(t("summary_title"))
    print("=" * 70)
    for r in results:
        print("")
        print(t("summary_mode", mode=r["mode"]))
        print(t("summary_tools", n=r["n_tools"], chars=r["chars"]))
        if r["ok"] is None:
            verdict = r["chosen"]
        elif r["ok"]:
            verdict = t("summary_ok")
        else:
            verdict = t("summary_bad", got=r["chosen"] or "—", want=correct_tool)
        print(t("summary_result", r=verdict))
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
        task_text, correct_tool = _resolve_choice(" ".join(sys.argv[2:]))
    else:
        task_text, correct_tool = ask_for_task(mode_arg)

    try:
        backend = detect_backend()
    except RuntimeError:
        print("")
        print(t("no_backend_title"))
        print(t("no_backend_help"))
        sys.exit(1)

    print(t("backend") + backend)
    print(t("task_label") + task_text)
    if correct_tool:
        print(t("correct_label") + correct_tool)

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
            results.append(run(task_text, correct_tool, mode=m, backend=backend))
        print_summary(results, correct_tool)
    else:
        run(task_text, correct_tool, mode=mode_arg, backend=backend)
        print_rerun_hint(task_text, mode_arg)
