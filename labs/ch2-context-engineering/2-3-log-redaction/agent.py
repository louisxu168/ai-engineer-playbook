"""
实验 2-3：日志脱敏 —— 什么不该进上下文

前两个实验讲的是「上下文装不下」和「上下文被投毒」。这个讲第三种风险：

    **上下文里装了不该装的东西。**

你把服务器日志丢给 agent 分析，日志里可能有：用户邮箱、手机号、
API key、身份证号、信用卡号。这些一旦进了上下文，就等于发给了模型厂商 ——
可能被记录、被用于训练、被别人看到。

直觉答案是「脱敏就好了」。但这里有个真实的两难：

    **脱得太狠，任务就做不成了。**

本实验的任务需要**区分不同用户**（找出谁触发了最多错误）。
如果把所有邮箱都换成 `[已脱敏]`，agent 就分不清张三和李四了。

所以真实系统用的是第三条路：**可逆令牌化**（tokenization）——
把 `zhang@example.com` 换成稳定的 `USER_1`，agent 能推理"同一个人"，
但不知道他是谁。

⚠️ 和实验 2-2 对照着看：那里我说「关键词过滤不是防御」，这里我说
   「正则脱敏是有效的」。**看起来矛盾，其实不是** —— 差别在威胁模型，
   README 里有详细解释。

    python3 agent.py                 # 打印用法说明
    python3 agent.py raw             # 不脱敏（基线，看泄露了多少）
    python3 agent.py tokenized       # 可逆令牌化 ★核心
    python3 agent.py all             # 三种全跑 + 对比表

不需要 API key，也不联网 —— 日志数据都在这个文件里，且**全是假的**。

详细讲解见 README.zh-CN.md（中文）/ README.md（英文）。
"""

import json
import re
import sys
import time

from llm import complete, detect_backend, parse_json_reply


# --------------------------------------------------------------------------
#  可以改的开关（Settings）
# --------------------------------------------------------------------------

LANG = "zh"          # "zh" | "en" —— 同时切换输出和发给模型的提示词

SHOW_PROMPT = False  # 改成 True 会打印每轮真正发给模型的完整文本


MODES = [
    "raw",         # 日志原样发给模型 —— 敏感信息全进上下文（基线）
    "redacted",    # 全部替换成 [已脱敏] —— 安全了，但任务还做得成吗？
    "tokenized",   # 换成稳定占位符 USER_1 / KEY_1 ★核心：两头兼顾
]


# --------------------------------------------------------------------------
#  假日志数据
# --------------------------------------------------------------------------
#
# ⚠️ 下面所有「敏感信息」都是**编造的**：
#    - 邮箱用 example.com（RFC 2606 保留域名，永远不会属于任何人）
#    - 手机号用 555 开头（北美影视专用号段，不会分配给真人）
#    - API key 明确写了 FAKE
#    - 身份证/卡号是明显的占位数字
#
# 真实场景里这些会来自：应用日志、数据库导出、客服工单、错误上报。
# **这正是最容易被顺手丢给模型的一类数据。**

RAW_LOGS = """
2026-07-28 09:12:03 INFO  user=zhang.wei@example.com action=login ip=10.0.3.44 ok
2026-07-28 09:12:41 ERROR user=zhang.wei@example.com action=checkout code=PAYMENT_TIMEOUT
2026-07-28 09:13:02 INFO  user=li.na@example.com action=login ip=10.0.3.51 ok
2026-07-28 09:14:19 ERROR user=zhang.wei@example.com action=checkout code=PAYMENT_TIMEOUT
2026-07-28 09:15:33 DEBUG outbound call apikey=sk-FAKE-9f2b1c4d8e7a6350 endpoint=/pay
2026-07-28 09:16:07 ERROR user=zhang.wei@example.com action=checkout code=PAYMENT_TIMEOUT
2026-07-28 09:17:55 INFO  user=wang.tao@example.com action=login ip=10.0.3.77 ok
2026-07-28 09:18:21 ERROR user=li.na@example.com action=refund code=UPSTREAM_5XX
2026-07-28 09:19:40 WARN  contact phone=+1-555-0142 for manual review
2026-07-28 09:20:02 ERROR user=zhang.wei@example.com action=checkout code=PAYMENT_TIMEOUT
2026-07-28 09:21:18 INFO  user=wang.tao@example.com action=browse ok
2026-07-28 09:22:47 ERROR user=li.na@example.com action=refund code=UPSTREAM_5XX
2026-07-28 09:23:09 DEBUG card=4111-1111-1111-1111 masked_ok=false
2026-07-28 09:24:31 ERROR user=zhang.wei@example.com action=checkout code=PAYMENT_TIMEOUT
""".strip()


# 脱敏规则。每条 = （正则, 令牌前缀, 人话说明）
#
# ⚠️ 顺序很重要：**先匹配长的、具体的，再匹配短的、宽泛的**。
#    卡号 4111-1111-1111-1111 里藏着一个"像电话号"的片段 111-1111。
#    下面的电话规则要求带区号（\+?\d{1,3}-），所以现在不会误伤；
#    但只要把它写松成 \d{3}-\d{4} 并放到卡号规则前面，卡号就会被从中间切开。
#    README 的练习 2 会让你亲手做一遍 —— 这是写脱敏规则最常见的坑。
REDACTION_RULES = [
    (r"sk-[A-Za-z0-9\-]{8,}", "KEY", "API 密钥"),
    (r"\b\d{4}-\d{4}-\d{4}-\d{4}\b", "CARD", "银行卡号"),
    (r"\b[\w.+-]+@[\w-]+\.[\w.]+\b", "USER", "邮箱地址"),
    (r"\+?\d{1,3}-\d{3}-\d{4}", "PHONE", "电话号码"),
    (r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "IP", "内网 IP"),
]


# --------------------------------------------------------------------------
#  所有对用户可见的文字，按语言分开放（包含发给模型的提示词）
# --------------------------------------------------------------------------

TEXT = {
    "zh": {
        "sys_role": "你是一个分析服务器日志、定位问题的运维助手。",
        "sys_tools": """你可以使用这个工具：
- fetch_logs()   取最近的服务器日志
""",
        "sys_token_note": """
日志里的敏感信息已被替换成稳定的占位符（如 USER_1、KEY_1）。
**同一个占位符始终代表同一个实体** —— 所以你完全可以统计
「USER_1 出现了几次」「哪个 USER 错误最多」。
回答时直接用占位符，不要试图猜测它们背后的真实值。
""",
        "sys_redact_note": """
日志里的敏感信息已被移除，统一替换成 [已脱敏]。
""",
        "sys_protocol": """只输出一个 JSON 对象，不要有别的内容。要么是：
  {"reasoning": "<一句话思路>", "calls": [{"tool": "<工具名>", "args": {...}}]}
要么，当你已经得出完整答案时：
  {"reasoning": "<一句话思路>", "answer": "<你的分析结论>"}""",
        "ctx_task": "运维请求：",
        "ctx_step": "--- 第 {n} 步 ---",
        "ctx_your_reply": "你的回复：",
        "ctx_tool_returned": "工具 {tool} 返回：",
        "ctx_next": "现在给出你的下一条 JSON 回复。",
        # --- 交互输入 ---
        "ask_task": "请输入你想让 agent 分析什么（直接回车看例子）：\n> ",
        "examples_title": "几个可以直接复制的例子（都需要「区分不同用户」）：",
        "task_examples": [
            "分析这批日志，告诉我哪个用户触发的错误最多，是什么错误。",
            "这批日志里有几类错误？各自影响了几个不同的用户？",
            "找出错误最集中的那个用户，并判断问题出在哪个环节。",
        ],
        "picked": "  ✓ 已选第 {n} 个：{task}",
        "number_out_of_range": "  （只有 {n} 个例子，就按你输的内容当任务了）",
        "need_task": "没有任务就没法跑。把任务写在模式后面，或者不带任务运行进入交互输入。",
        "no_tty": "检测到非交互环境（比如管道/脚本里跑），请把任务直接写在命令行：\n    python3 agent.py {mode} \"你的任务\"",
        "interrupted": "\n  已中断（Ctrl+C）。想换个任务重跑就再执行一次。",
        "rerun_hint": "想用同一个任务跑别的模式做对比，复制这行改模式名即可：",
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
        "task_label": "任务：",
        "round_line": "  第 {n} 轮 / 共 {total} 轮     模式：{mode}",
        "mode_desc_line": "  处理方式：{desc}",
        "desc_raw": "不处理，日志原样发给模型",
        "desc_redacted": "全部替换成 [已脱敏]",
        "desc_tokenized": "替换成稳定占位符（USER_1 / KEY_1 …）",
        "box_top": "  ┌─── 实际发给模型的内容 ",
        "asking": "  正在问模型…",
        "took": " 用了 {sec} 秒",
        "thinking": "  [思考] ",
        "tool": "[工具]",
        "leak_head": "  ─── 这一轮往上下文里放了什么 ───",
        "leak_count": "  ☠ 真实敏感信息 {n} 条进入上下文：{detail}",
        "leak_none": "  ✓ 没有任何真实敏感信息进入上下文",
        "token_map_head": "  ┌─ 令牌映射表（只存在你本地，不发给模型）─────",
        "token_map_foot": "  └────────────────────────────────────────────",
        "box_line": "  │ ",
        "sample_head": "  ┌─ 模型看到的日志（前 4 行）─────────────────",
        "sample_foot": "  └────────────────────────────────────────────",
        "answer": "  [答案] ",
        "verdict_head": "  ─── 任务完成得怎么样 ───",
        "verdict_done": "  ✓ 分辨出了具体是哪个用户（答案里出现 {who}）",
        "verdict_vague": "  ✗ 分不清是哪个用户 —— 脱敏脱过头了，任务做不成",
        "hit_cap": "  [上限] 跑满 {n} 轮仍未给出答案",
        "no_such_tool": "没有这个工具：",
        # --- 对比表 + 用法说明 ---
        "summary_title": "对比结果",
        "summary_mode": "模式：",
        "summary_leak": "  泄露：",
        "summary_leak_n": "✗ {n} 条真实敏感信息进入上下文",
        "summary_leak_0": "✓ 零泄露",
        "summary_task": "  任务：",
        "summary_task_ok": "✓ 完成（分辨出了具体用户）",
        "summary_task_fail": "✗ 做不成（分不清用户）",
        "summary_capped": "跑满上限，没给出答案",
        "summary_verify": """
一张表看懂三条路：
  raw        任务能做，但敏感信息全泄露了
  redacted   零泄露，但任务做不成
  tokenized  零泄露 + 任务能做  ← 这才是真实系统的做法""",
        "unknown_mode": "✗ 不认识的模式：",
        "exp_header": "# 实验 {i}/{total}：{mode}",
        "all_warning": "\n⚠️  all 模式要跑 3 个实验，不联网所以很快，大约 1～3 分钟。",
        "help": """
======================================================================
 实验 2-3：日志脱敏 —— 什么不该进上下文
======================================================================

同一个日志分析任务，三种脱敏方式。看的是「安全」和「可用」怎么兼顾。

用法：
    python3 agent.py <模式> ["自定义任务"]

【三种模式】
    raw         不处理，日志原样发给模型（基线，看泄露多少）
    redacted    全部替换成 [已脱敏]（安全了，但任务还做得成吗？）
    tokenized   替换成稳定占位符 USER_1 / KEY_1 ★核心

【对比】
    all         三种全跑，最后打印对比表（约 1~3 分钟，不联网）

程序会在每次跑完后直接告诉你：
    - 有多少条真实敏感信息进入了上下文
    - 任务有没有做成（能不能分辨出具体是哪个用户）

建议顺序：
    1. 先跑 raw，数一下泄露了多少
    2. 再跑 redacted —— 零泄露了，但注意看任务还做不做得成
    3. 最后 tokenized，看它怎么两头兼顾

⚠️ 日志里的敏感信息全是编造的：邮箱用 example.com（保留域名），
   电话用 555 号段，API key 明确写了 FAKE。

把文件开头的 LANG 改成 "en" 可切换成英文输出。
详细讲解见 README.zh-CN.md。
""",
    },
    "en": {
        "sys_role": "You are an ops assistant who analyses server logs to locate problems.",
        "sys_tools": """You have this tool:
- fetch_logs()   get the recent server logs
""",
        "sys_token_note": """
Sensitive values in the logs have been replaced with stable placeholders
(e.g. USER_1, KEY_1). **The same placeholder always means the same entity** —
so you can absolutely count "how many times USER_1 appears" or "which USER has
the most errors". Refer to the placeholders directly in your answer; do not try
to guess the real values behind them.
""",
        "sys_redact_note": """
Sensitive values have been removed from the logs and replaced with [REDACTED].
""",
        "sys_protocol": """Reply with ONE JSON object and nothing else. Either:
  {"reasoning": "<one short sentence>", "calls": [{"tool": "<name>", "args": {...}}]}
or, when you have the complete answer:
  {"reasoning": "<one short sentence>", "answer": "<your analysis>"}""",
        "ctx_task": "OPS REQUEST: ",
        "ctx_step": "--- step {n} ---",
        "ctx_your_reply": "You replied: ",
        "ctx_tool_returned": "Tool {tool} returned: ",
        "ctx_next": "Now give your next JSON reply.",
        "ask_task": "Type what you want analysed (Enter for examples):\n> ",
        "examples_title": "Copy one (all of them require telling users apart):",
        "task_examples": [
            "Analyse these logs: which user triggered the most errors, and what error?",
            "How many kinds of error are in these logs, and how many distinct users did each affect?",
            "Find the user with the most concentrated errors and say which stage is failing.",
        ],
        "picked": "  ok, picked #{n}: {task}",
        "number_out_of_range": "  (only {n} examples, treating your input as the task)",
        "need_task": "No task, nothing to run. Put it after the mode, or run without one to be prompted.",
        "no_tty": "Non-interactive environment detected. Put the task on the command line:\n    python3 agent.py {mode} \"your task\"",
        "interrupted": "\n  Interrupted (Ctrl+C). Run it again to try another task.",
        "rerun_hint": "To compare another mode on the SAME task, copy this and change the mode name:",
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
        "task_label": "Task: ",
        "round_line": "  Round {n} of {total}     mode: {mode}",
        "mode_desc_line": "  Handling: {desc}",
        "desc_raw": "none - logs sent verbatim",
        "desc_redacted": "everything replaced with [REDACTED]",
        "desc_tokenized": "replaced with stable placeholders (USER_1 / KEY_1 ...)",
        "box_top": "  +--- exact text sent to the model ",
        "asking": "  asking the model...",
        "took": " took {sec}s",
        "thinking": "  [thinking] ",
        "tool": "[tool]",
        "leak_head": "  --- what went into the context this round ---",
        "leak_count": "  ! {n} real sensitive value(s) entered the context: {detail}",
        "leak_none": "  ok no real sensitive value entered the context",
        "token_map_head": "  +- token map (stays local, never sent to the model) ---",
        "token_map_foot": "  +----------------------------------------------------",
        "box_line": "  | ",
        "sample_head": "  +- the logs as the model sees them (first 4 lines) ---",
        "sample_foot": "  +----------------------------------------------------",
        "answer": "  [answer] ",
        "verdict_head": "  --- how did the task go? ---",
        "verdict_done": "  ok it identified a specific user (the answer names {who})",
        "verdict_vague": "  x it cannot tell users apart - over-redacted, task impossible",
        "hit_cap": "  [cap] hit {n} rounds without answering",
        "no_such_tool": "no such tool: ",
        "summary_title": "COMPARISON",
        "summary_mode": "mode: ",
        "summary_leak": "  leakage: ",
        "summary_leak_n": "x {n} real sensitive value(s) entered the context",
        "summary_leak_0": "ok zero leakage",
        "summary_task": "  task: ",
        "summary_task_ok": "ok completed (identified a specific user)",
        "summary_task_fail": "x impossible (cannot tell users apart)",
        "summary_capped": "hit the cap without answering",
        "summary_verify": """
Three approaches in one table:
  raw        task works, but everything leaked
  redacted   zero leakage, but the task is impossible
  tokenized  zero leakage AND the task works  <- what real systems do""",
        "unknown_mode": "x unknown mode: ",
        "exp_header": "# Experiment {i}/{total}: {mode}",
        "all_warning": "\n!  'all' runs 3 experiments. No network, so it's quick: 1-3 minutes.",
        "help": """
======================================================================
 Lab 2-3: Log redaction - what should never enter the context
======================================================================

One log-analysis task, three redaction strategies. Subject: how do you get
safety AND usefulness?

Usage:
    python3 agent.py <mode> ["your own task"]

THE THREE MODES
    raw         no handling, logs sent verbatim (baseline - count the leaks)
    redacted    everything replaced with [REDACTED] (safe - but can the task
                still be done?)
    tokenized   replaced with stable placeholders USER_1 / KEY_1  <- the core one

COMPARISON
    all         run all three, then print a table (1-3 minutes, no network)

After each run the program tells you:
    - how many real sensitive values entered the context
    - whether the task succeeded (could it tell users apart?)

Suggested order:
    1. Run raw. Count the leaks.
    2. Run redacted. Zero leakage now - but watch whether the task still works.
    3. Run tokenized and see how it gets both.

⚠️ Every sensitive value in the logs is fabricated: emails use example.com
   (a reserved domain), phones use the 555 range, API keys say FAKE.

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
#  第 1 部分：脱敏  ★★★ 本实验的核心 ★★★
# ==========================================================================
#
# 三种做法的差别，全在这一节。注意它们的**信息保留程度**是递进的：
#
#   raw        保留 100%  → 任务能做，但全泄露
#   redacted   保留 0%    → 零泄露，但同一类实体全都长得一样，分不清
#   tokenized  保留"同一性" → 零泄露，且还分得清谁是谁
#
# 第三种叫 **可逆令牌化**：真实值 → 稳定占位符，映射表留在你本地。
# 这是真实系统（日志脱敏、数据脱敏、隐私计算）普遍采用的做法。


def redact_all(text):
    """把所有敏感信息统一替换成 [已脱敏]。

    安全，但**破坏了同一性** —— 三个不同用户都变成 [已脱敏]，
    agent 再也没法回答「哪个用户错误最多」。
    """
    placeholder = "[已脱敏]" if LANG == "zh" else "[REDACTED]"
    result = text
    for pattern, _prefix, _desc in REDACTION_RULES:
        result = re.sub(pattern, placeholder, result)
    return result


def tokenize(text):
    """把敏感信息换成稳定占位符，并返回映射表。

    ★ 关键在「稳定」两个字：同一个真实值，永远映射到同一个占位符。
      所以 agent 数得出「USER_1 出现了 6 次」，却不知道 USER_1 是谁。

    映射表留在本地，**永远不进上下文** —— 这一点由调用方保证，
    你可以在输出里看到它被单独打印，而不是拼进提示词。

    返回 (令牌化后的文本, {占位符: 真实值})
    """
    mapping = {}
    counters = {}
    result = text

    for pattern, prefix, _desc in REDACTION_RULES:
        # 先找出这一类的所有不同取值，保证同值同令牌
        for match in re.findall(pattern, result):
            if match in mapping.values():
                continue
            counters[prefix] = counters.get(prefix, 0) + 1
            token = prefix + "_" + str(counters[prefix])
            mapping[token] = match
            # 用 re.escape 是因为真实值里可能含正则特殊字符（比如 + . 号）
            result = re.sub(re.escape(match), token, result)

    return result, mapping


def count_leaks(text):
    """数一数这段文本里还有多少条**真实**敏感信息。

    这是本实验能自动判分的原因：泄露与否是客观可测的。
    """
    found = []
    for pattern, _prefix, desc in REDACTION_RULES:
        hits = re.findall(pattern, text)
        # 占位符长得不像真实值，不会被这些正则匹配到 —— 除了 IP 那条，
        # 所以下面再排除掉已经是占位符的情况。
        real_hits = [h for h in hits if not re.match(r"^(USER|KEY|PHONE|CARD|IP)_\d+$", h)]
        if real_hits:
            found.append(desc + " ×" + str(len(set(real_hits))))
    return found


# ==========================================================================
#  第 2 部分：工具（Part 2）
# ==========================================================================


def fetch_logs(mode):
    """工具：取服务器日志。mode 决定发出去之前怎么处理。

    ★ 三种模式的差别就在这个函数里，每种只有一两行。
    """
    if mode == "raw":
        return {"logs": RAW_LOGS}, {}

    if mode == "redacted":
        return {"logs": redact_all(RAW_LOGS)}, {}

    # tokenized
    tokenized_text, mapping = tokenize(RAW_LOGS)
    return {"logs": tokenized_text}, mapping


# ==========================================================================
#  第 3 部分：系统提示词（Part 3）
# ==========================================================================


def build_system_prompt(mode):
    """脱敏之后要**告诉模型你做了什么** —— 否则它会以为日志本来就长这样，
    甚至可能试图去猜占位符背后是什么。"""
    parts = [t("sys_role"), t("sys_tools")]

    if mode == "tokenized":
        parts.append(t("sys_token_note"))
    elif mode == "redacted":
        parts.append(t("sys_redact_note"))

    parts.append(t("sys_protocol"))
    return "\n\n".join(parts)


# ==========================================================================
#  第 4 部分：拼上下文 + 判定（Part 4）
# ==========================================================================


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
    """归一成「要调的工具」列表。和前面几个实验是同一个辅助函数。"""
    calls = reply.get("calls")
    if isinstance(calls, list) and len(calls) > 0:
        return calls
    if reply.get("tool"):
        return [{"tool": reply["tool"], "args": reply.get("args", {})}]
    return []


def judge_task(answer):
    """任务算不算做成了？判据：答案里有没有指名道姓某一个具体用户。

    - raw 模式下应该出现真实邮箱（zhang.wei@example.com）
    - tokenized 模式下应该出现 USER_1 之类的占位符
    - redacted 模式下两者都没有 → 任务做不成
    """
    text = str(answer)
    token_hit = re.search(r"USER_\d+", text)
    if token_hit:
        return True, token_hit.group(0)
    email_hit = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text)
    if email_hit:
        return True, email_hit.group(0)
    return False, ""


# ==========================================================================
#  第 5 部分：主循环（Part 5）
# ==========================================================================


def run(task, mode="raw", max_iterations=6, backend=None, verbose=True):
    steps = []
    system_prompt = build_system_prompt(mode)
    total_leaks = 0

    desc = {"raw": t("desc_raw"), "redacted": t("desc_redacted"),
            "tokenized": t("desc_tokenized")}[mode]

    for round_number in range(1, max_iterations + 1):
        prompt = render_context(task, steps)

        if verbose:
            print("")
            print("=" * 68)
            print(t("round_line", n=round_number,
                    total=max_iterations, mode=mode))
            print(t("mode_desc_line", desc=desc))
            print("=" * 68)

        if SHOW_PROMPT:
            print("")
            print(t("box_top") + "-" * 38)
            for one_line in prompt.split("\n"):
                print(t("box_line") + one_line)
            print("  +" + "-" * 60)

        if verbose:
            print("")
            print(t("asking"), end="", flush=True)

        call_start = time.time()
        raw_text = complete(prompt, system_prompt, backend=backend)
        if verbose:
            print(t("took", sec=round(time.time() - call_start, 1)))

        reply = parse_json_reply(raw_text)

        if verbose and reply.get("reasoning"):
            print("")
            print(t("thinking") + str(reply["reasoning"]))

        has_answer = "answer" in reply
        wanted_calls = extract_tool_calls(reply)

        if has_answer or len(wanted_calls) == 0:
            answer = reply["answer"] if has_answer else raw_text.strip()
            done, who = judge_task(answer)

            if verbose:
                print("")
                print(t("answer") + str(answer))
                print("")
                print(t("verdict_head"))
                if done:
                    print(t("verdict_done", who=who))
                else:
                    print(t("verdict_vague"))
                print("")

            return {"mode": mode, "answer": answer, "leaks": total_leaks,
                    "task_done": done, "iterations": round_number,
                    "hit_cap": False}

        results_this_round = []
        if verbose:
            print("")

        for one_call in wanted_calls:
            tool_name = one_call.get("tool")

            if tool_name == "fetch_logs":
                result, mapping = fetch_logs(mode)
                if verbose:
                    print("  " + t("tool") + " fetch_logs()")
                    # 把模型实际看到的日志前几行打出来 —— 这是本实验最直观的地方
                    print(t("sample_head"))
                    for line in str(result["logs"]).split("\n")[:4]:
                        print(t("box_line") + line)
                    print(t("sample_foot"))
                    # 泄露判定
                    leaks = count_leaks(str(result["logs"]))
                    print(t("leak_head"))
                    if leaks:
                        total_leaks = total_leaks + len(leaks)
                        print(t("leak_count", n=len(leaks),
                                detail="、".join(leaks)))
                    else:
                        print(t("leak_none"))
                    # 映射表只在本地打印，不进上下文
                    if mapping:
                        print(t("token_map_head"))
                        for token in list(mapping)[:5]:
                            print(t("box_line") + token + "  ->  " + mapping[token])
                        print(t("token_map_foot"))
            else:
                result = {"error": t("no_such_tool") + str(tool_name)}
                if verbose:
                    print("  " + t("tool") + " " + str(tool_name))

            results_this_round.append({"tool": tool_name, "result": result})

        steps.append({"number": round_number, "assistant": reply,
                      "results": results_this_round})

    if verbose:
        print("")
        print(t("hit_cap", n=max_iterations))
        print("")
    return {"mode": mode, "answer": None, "leaks": total_leaks,
            "task_done": False, "iterations": max_iterations, "hit_cap": True}


# ==========================================================================
#  第 6 部分：命令行入口（Part 6）
# ==========================================================================


def ask_for_task(mode):
    """让用户输入任务。故意不设默认值。"""
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
        print("")
        print(t("summary_mode") + r["mode"])
        if r["leaks"] > 0:
            print(t("summary_leak") + t("summary_leak_n", n=r["leaks"]))
        else:
            print(t("summary_leak") + t("summary_leak_0"))
        if r["hit_cap"]:
            print(t("summary_task") + t("summary_capped"))
        elif r["task_done"]:
            print(t("summary_task") + t("summary_task_ok"))
        else:
            print(t("summary_task") + t("summary_task_fail"))
    print(t("summary_verify"))


def _quiet_ctrl_c(exc_type, exc_value, tb):
    """Ctrl+C 是正常操作，不是崩溃 —— 不要甩一屏 traceback。"""
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
