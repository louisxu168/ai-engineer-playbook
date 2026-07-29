"""
实验 1-3：让 agent 写代码来「想」

实验 1-1 问「上下文是什么」，1-2 问「工具由谁来跑」。这一个问：

    当 agent 需要**分析**数据（而不只是取回数据）时，它该怎么办？

先说一个我们实测得到、但和直觉相反的结论：

    **现代模型的心算能力比你想的强得多。** 实测让它心算 20 个三位小数的
    中位数和总体标准差，它给出 518.65 和 93.94（真值 518.65 / 93.9437），
    全对。所以「模型算不对」**不是**给它代码工具的理由。

真正的理由是另外三个：

    1. **你验不了。** 它给你一段散文说「平均是 668.16」，你想确认只能
       自己从头再算一遍。而一段代码你可以直接复制出来跑。
    2. **改假设很贵。** 哈利法塔算 829.8（含天线）还是 828（屋顶）？
       有代码就是改一个数重跑；没代码就得整个重算。实测中有代码的那次
       **主动把两种口径都算了**，没代码的那次没有。
    3. **规模一大就崩。** 20 个数它能心算，2 万行日志不能。

所以这个实验真正在讲的不是「算得对不对」，而是
**「这个结论可不可查、可不可复现」** —— 这才是工程上要的东西。

这就是所谓 Deep Research 循环：

    搜索 → 读正文 → **写代码分析** → 发现还缺数据 → 再搜索 → …

    python3 agent.py                 # 打印用法说明
    python3 agent.py deep            # 完整循环（基线）
    python3 agent.py no_code         # 拿掉代码工具，只能心算 ★核心对比
    python3 agent.py all             # 四种全跑 + 对比表

不需要 API key。搜索用维基百科公开 API，代码在本地子进程里跑。

详细讲解见 README.zh-CN.md（中文）/ README.md（英文）。
"""

import json
import subprocess
import sys
import time
import urllib.parse
import urllib.request

from llm import (complete, complete_hosted, detect_backend, parse_json_reply,
                 HostedNotAvailable, HostedInterrupted)


# --------------------------------------------------------------------------
#  可以改的开关（Settings）
# --------------------------------------------------------------------------

LANG = "zh"          # "zh" | "en" —— 同时切换输出和发给模型的提示词

SHOW_PROMPT = False  # 改成 True 会打印每轮真正发给模型的完整文本

CODE_TIMEOUT = 15    # 模型写的代码最多跑多久（秒）


MODES = [
    "deep",        # search + read + run_python，完整深度研究循环（基线）
    "no_code",     # 拿掉 run_python，只能心算 ★本实验的核心对比
    "no_read",     # 拿掉 read，只有搜索摘要 —— 数据不全就开始算
    "hosted",      # 整件事交给 Claude Code 自带工具（对照实验 1-2）
]

DIY_MODES = ["deep", "no_code", "no_read"]


# --------------------------------------------------------------------------
#  所有对用户可见的文字，按语言分开放（包含发给模型的提示词）
# --------------------------------------------------------------------------

TEXT = {
    "zh": {
        # --- 发给模型的文字 ---
        "sys_role": "你是一个先查资料、再做定量分析的研究助手。",
        "sys_tools_head": "你可以使用这些工具：\n- search(query)   搜维基百科，返回若干条标题和摘要\n- read(title)     读词条正文开头，拿到具体数据\n",
        "sys_tool_code": "- run_python(code) 运行一段 Python 代码做计算/分析，用 print() 输出结果\n",
        "sys_tools_tail": """
注意 search 返回的是**线索**，摘要里常常没有你要的精确数字，那就用 read 读正文。
""",
        "sys_code_advice": """
凡是涉及算术、平均值、百分比、排序、比较的地方，**一律写代码算，不要心算**。
不是因为你算不对，而是因为写成代码之后，看你答案的人可以复制去重跑、
可以改一个数重算 —— 一段散文推导做不到这些。
run_python 里可以用标准库（math、statistics 等），但**没有网络** ——
数据要先用 search / read 拿到，再写进代码里。
""",
        "sys_no_code_advice": """
你没有运行代码的工具，所有计算只能自己心算。
请把每一步算式都完整写进答案里，方便别人核对。
""",
        "sys_protocol": """只输出一个 JSON 对象，不要有别的内容。要么是：
  {"reasoning": "<一句话思路>", "calls": [{"tool": "<工具名>", "args": {...}}]}
要么，当你已经得出完整答案时：
  {"reasoning": "<一句话思路>", "answer": "<答案，要写出用到的每个数字和最终结果>"}

calls 是数组，互不依赖的工具可以一次全放进去。""",
        "sys_no_guessing": "绝对不要猜数字。查不到就说查不到。",
        "hosted_prompt_suffix": "\n\n请联网搜索并做必要的计算后回答，答案里要给出用到的每个数字、计算过程和最终结果。",
        "ctx_task": "研究问题：",
        "ctx_step": "--- 第 {n} 步 ---",
        "ctx_your_reply": "你的回复：",
        "ctx_tool_returned": "工具 {tool} 返回：",
        "ctx_next": "现在给出你的下一条 JSON 回复。",
        # --- 交互输入 ---
        "ask_task": "请输入你想让 agent 研究的问题（直接回车看例子）：\n> ",
        "examples_title": "几个可以直接复制的例子（都需要「先查数据、再算」）：",
        "task_examples": [
            "世界最高的 5 座建筑，平均高度是多少米？最高的那座比平均值高出百分之多少？",
            "中国最长的 3 条河流总长多少公里？平均每条多长？",
            "太阳系里最大的 4 颗行星，直径的平均值和中位数各是多少？",
        ],
        "picked": "  ✓ 已选第 {n} 个：{task}",
        "number_out_of_range": "  （只有 {n} 个例子，就按你输的内容当问题了）",
        "need_task": "没有问题就没法研究。把问题写在模式后面，或者不带问题运行进入交互输入。",
        "no_tty": "检测到非交互环境（比如管道/脚本里跑），请把问题直接写在命令行：\n    python3 agent.py {mode} \"你的问题\"",
        "interrupted": "\n  已中断（Ctrl+C）。想换个问题重跑就再执行一次。",
        "rerun_hint": "想用同一个问题跑别的模式做对比，复制这行改模式名即可：",
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
        "task_label": "研究问题：",
        "no_history_yet": "上下文里还没有历史",
        "only_step": "上下文只含第 {n} 步",
        "steps_range": "上下文含第 {a}~{b} 步",
        "round_line1": "  第 {n} 轮 / 共 {total} 轮     模式：{mode}",
        "round_line2": "  {ctx}     提示词 {chars} 字符",
        "box_top": "  ┌─── 实际发给模型的内容 ",
        "asking": "  正在问模型…",
        "took": " 用了 {sec} 秒",
        "thinking": "  [思考] ",
        "tool": "[工具]",
        "tool_n": "[工具 {i}/{total}]",
        "code_header": "  ┌─ 它写的代码 ─────────────────────────",
        "code_footer": "  └──────────────────────────────────────",
        "answer": "  [答案] ",
        "hit_cap": "  [上限] 跑满 {n} 轮仍未给出答案",
        "no_such_tool": "没有这个工具：",
        "code_disabled": "本模式没有运行代码的工具，请自己心算",
        "read_disabled": "本模式没有 read 工具，只能用搜索摘要里的信息",
        "no_hits": "没搜到结果",
        "read_failed": "读不到这个词条：",
        "code_timeout": "代码跑了超过 {sec} 秒还没结束，已强制终止",
        "code_no_output": "代码跑完了但没有任何输出 —— 记得用 print() 把结果打出来",
        # --- hosted 模式 ---
        "hosted_title": "  ── hosted 模式：整件事都交给厂商 ──",
        "hosted_note": """  我们只做了一件事：把问题原样发出去，并允许它使用自带的工具。
  搜索、读网页、算数 —— 全在厂商那边跑，我们一行循环都没写。""",
        "hosted_waiting": "  正在等厂商跑完整个流程…",
        "waited": "已等 {sec} 秒…（深度研究通常 60~150 秒）",
        "retrying": "  [第 {n}/{total} 次尝试]",
        "hosted_turns": "  厂商内部跑了 {n} 轮",
        "hosted_blind": """  和实验 1-2 一样：它算得对不对，你没法验算 ——
  因为你根本不知道它用了哪几个数、怎么算的。""",
        "hosted_unavailable": "  ⚠️  {msg}",
        "hosted_interrupted": "  ✗ hosted 模式没跑完：{msg}",
        "hosted_interrupted_lesson": "\n  （再跑一次通常就好，这个失败是不确定的。）",
        # --- 对比表 + 用法说明 ---
        "summary_title": "对比结果",
        "summary_mode": "模式：",
        "summary_stats": "  轮数：{r}   工具调用：{t} 次   写了 {c} 段代码",
        "summary_result": "  结果：",
        "summary_capped": "跑满上限，没给出答案",
        "summary_failed": "（本次未能运行）",
        "summary_hosted": "  （厂商跑的，看不到中间过程）",
        "summary_verify": "\n提示：数字很可能都一样。真正要比的是 —— 哪个结论你能**复制出来重跑一遍**？",
        "unknown_mode": "✗ 不认识的模式：",
        "exp_header": "# 实验 {i}/{total}：{mode}",
        "all_warning": "\n⚠️  all 模式要跑 4 个实验，含联网搜索，大约需要 5～12 分钟。",
        "help": """
======================================================================
 实验 1-3：让 agent 写代码来「想」
======================================================================

同一个研究问题，四种跑法。看的是「需要分析时，agent 靠什么算」。

用法：
    python3 agent.py <模式> ["自定义问题"]

【核心两种】
    deep       search + read + run_python，完整深度研究循环（先跑这个）
    no_code    拿掉 run_python，只能心算 ★和 deep 对比，看它算不算得对

【另外两种】
    no_read    拿掉 read，只有搜索摘要 —— 数据不全就开始算
    hosted     整件事交给 Claude Code 自带工具（对照实验 1-2）

【对比】
    all        四种全跑，最后打印对比表（约 5~12 分钟）

关于「问题」这个参数：
    模式后面可以不写问题，这时会交互提示你输入（也可以输编号选例子）。
    也可以写自己的问题，用引号整个包起来。

举例：
    python3 agent.py deep
        ↳ 跑基线，会问你想研究什么

    python3 agent.py no_code "（和上面完全相同的问题）"
        ↳ 问题必须一样才能对比

建议顺序：
    1. 先跑 deep，把它算出的数字记下来
    2. 再跑 no_code（同一个问题），对比两个数字
    3. 自己动手验算一遍 —— 谁对？

把文件开头的 LANG 改成 "en" 可切换成英文输出。
详细讲解见 README.zh-CN.md。
""",
    },
    "en": {
        # --- text sent to the model ---
        "sys_role": "You are a research assistant: look things up first, then analyse quantitatively.",
        "sys_tools_head": "You have these tools:\n- search(query)   search Wikipedia, returns titles with snippets\n- read(title)     read an article's opening, for actual figures\n",
        "sys_tool_code": "- run_python(code) run Python to compute/analyse; use print() for output\n",
        "sys_tools_tail": """
Note that search returns LEADS. Snippets often lack the exact figure you need —
use read to get the article.
""",
        "sys_code_advice": """
For ANY arithmetic, average, percentage, sorting or comparison, WRITE CODE.
Do not do it in your head. You are a language model; multi-digit decimal
arithmetic is where you make mistakes, and code does not.
run_python has the standard library (math, statistics, ...) but NO NETWORK —
fetch the data with search / read first, then put it in the code.
""",
        "sys_no_code_advice": """
You have no way to run code. All arithmetic must be done in your head, so be
as careful as you can.
""",
        "sys_protocol": """Reply with ONE JSON object and nothing else. Either:
  {"reasoning": "<one short sentence>", "calls": [{"tool": "<name>", "args": {...}}]}
or, when you have the complete answer:
  {"reasoning": "<one short sentence>", "answer": "<answer, listing every figure you used and the result>"}

`calls` is an array — independent tools can go in one reply.""",
        "sys_no_guessing": "Never guess a figure. If you cannot find it, say so.",
        "hosted_prompt_suffix": "\n\nSearch the web, do the arithmetic, and answer with every figure you used, the calculation, and the result.",
        "ctx_task": "RESEARCH QUESTION: ",
        "ctx_step": "--- step {n} ---",
        "ctx_your_reply": "You replied: ",
        "ctx_tool_returned": "Tool {tool} returned: ",
        "ctx_next": "Now give your next JSON reply.",
        # --- interactive input ---
        "ask_task": "Type the question you want researched (Enter for examples):\n> ",
        "examples_title": "Some you can copy (all need 'look it up, then compute'):",
        "task_examples": [
            "What is the average height of the world's 5 tallest buildings? By what percentage does the tallest exceed that average?",
            "What is the combined length of China's 3 longest rivers, and the average per river?",
            "For the 4 largest planets in the solar system, what are the mean and median diameters?",
        ],
        "picked": "  ok, picked #{n}: {task}",
        "number_out_of_range": "  (only {n} examples, treating your input as the question)",
        "need_task": "No question, nothing to research. Put it after the mode, or run without one to be prompted.",
        "no_tty": "Non-interactive environment detected (piped or scripted). Put the question on the command line:\n    python3 agent.py {mode} \"your question\"",
        "interrupted": "\n  Interrupted (Ctrl+C). Run it again to try another question.",
        "rerun_hint": "To compare another mode on the SAME question, copy this and change the mode name:",
        # --- console output ---
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
        "task_label": "Research question: ",
        "no_history_yet": "no history in context yet",
        "only_step": "context holds step {n} only",
        "steps_range": "context holds steps {a}-{b}",
        "round_line1": "  Round {n} of {total}     mode: {mode}",
        "round_line2": "  {ctx}     prompt {chars} chars",
        "box_top": "  +--- exact text sent to the model ",
        "asking": "  asking the model...",
        "took": " took {sec}s",
        "thinking": "  [thinking] ",
        "tool": "[tool]",
        "tool_n": "[tool {i}/{total}]",
        "code_header": "  +- the code it wrote --------------------",
        "code_footer": "  +---------------------------------------",
        "answer": "  [answer] ",
        "hit_cap": "  [cap] hit {n} rounds without answering",
        "no_such_tool": "no such tool: ",
        "code_disabled": "this mode has no code tool; do the arithmetic yourself",
        "read_disabled": "this mode has no read tool; use what the search snippets gave you",
        "no_hits": "no results",
        "read_failed": "cannot read that article: ",
        "code_timeout": "the code ran longer than {sec}s and was killed",
        "code_no_output": "the code finished but printed nothing - remember to print() your result",
        # --- hosted mode ---
        "hosted_title": "  -- hosted mode: the whole job goes to the provider --",
        "hosted_note": """  All we did: send the question as-is and allow its built-in tools.
  Search, page reading, arithmetic -- all on the provider's side. We wrote
  no loop at all.""",
        "hosted_waiting": "  waiting for the provider to run the whole thing...",
        "waited": "waited {sec}s... (deep research usually takes 60-150s)",
        "retrying": "  [attempt {n}/{total}]",
        "hosted_turns": "  the provider took {n} internal turns",
        "hosted_blind": """  Same as lab 1-2: you cannot check its arithmetic, because you have no idea
  which figures it used or how it combined them.""",
        "hosted_unavailable": "  !  {msg}",
        "hosted_interrupted": "  x hosted mode did not finish: {msg}",
        "hosted_interrupted_lesson": "\n  (Run it again - this failure is non-deterministic.)",
        # --- summary + help ---
        "summary_title": "COMPARISON",
        "summary_mode": "mode: ",
        "summary_stats": "  rounds: {r}   tool calls: {t}   code blocks written: {c}",
        "summary_result": "  result: ",
        "summary_capped": "hit the cap without answering",
        "summary_failed": "(did not run)",
        "summary_hosted": "  (ran at the provider; no visible steps)",
        "summary_verify": "\nThe numbers are probably identical. The real question: which result can you COPY OUT AND RE-RUN?",
        "unknown_mode": "x unknown mode: ",
        "exp_header": "# Experiment {i}/{total}: {mode}",
        "all_warning": "\n!  'all' runs 4 experiments with live search: roughly 5-12 minutes.",
        "help": """
======================================================================
 Lab 1-3: Letting the agent write code to think
======================================================================

One research question, four ways. The subject: when an agent has to ANALYSE,
what does it compute with?

Usage:
    python3 agent.py <mode> ["your own question"]

THE CORE TWO
    deep       search + read + run_python, the full loop (start here)
    no_code    take run_python away; it must do arithmetic in its head
               ^ compare against deep and check whether it gets it right

TWO MORE
    no_read    take read away; only search snippets -- analysing partial data
    hosted     hand it all to Claude Code's built-in tools (cf. lab 1-2)

COMPARISON
    all        run all four, then print a table (roughly 5-12 minutes)

About the "question" argument:
    Optional. Leave it out and you'll be prompted (you can type an example's
    number). Supply your own in quotes after the mode.

Examples:
    python3 agent.py deep
        -> the baseline; it asks what you want researched

    python3 agent.py no_code "(exactly the same question)"
        -> the question must match, or it isn't a comparison

Suggested order:
    1. Run deep first. Write down the number it produced.
    2. Run no_code on the SAME question. Compare the two numbers.
    3. Check the arithmetic yourself. Which one is right?

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
#  第 1 部分：工具（Part 1: Tools）
# ==========================================================================
# 这个实验的工具比前两个多一件东西：**能跑代码**。
#
# search 和 read 负责「取回数据」，run_python 负责「分析数据」。
# 这两件事是分开的 —— 而这正是本实验要你注意的分工。

WIKI_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "ai-engineer-playbook/0.1 (educational lab)"


def _wiki_get(params):
    """向维基百科 API 发一次 GET，返回解析好的 JSON。"""
    url = WIKI_API + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def search(query, limit=3):
    """工具 1：搜维基百科，返回线索（标题 + 摘要）。"""
    try:
        data = _wiki_get({
            "action": "query", "list": "search", "srsearch": str(query),
            "srlimit": limit, "format": "json",
        })
    except Exception as error:
        return {"error": str(error)}

    hits = data.get("query", {}).get("search", [])
    if len(hits) == 0:
        return {"error": t("no_hits")}

    results = []
    for hit in hits:
        snippet = hit.get("snippet", "")
        snippet = snippet.replace('<span class="searchmatch">', "")
        snippet = snippet.replace("</span>", "")
        snippet = snippet.replace("&quot;", '"').replace("&amp;", "&")
        results.append({"title": hit["title"], "snippet": snippet})

    return {"results": results}


def read(title, chars=1400):
    """工具 2：读词条正文开头。真实数字都在这里。

    这里比实验 1-2 读得更长（1400 字符）。深度研究常常要翻过定义和历史
    才碰得到具体数字 —— 读太短它就得反复 read，白白多跑好几轮。
    **工具返回多少内容，是个真实的设计参数。**
    """
    try:
        data = _wiki_get({
            "action": "query", "prop": "extracts", "titles": str(title),
            "exintro": 1, "explaintext": 1, "exchars": chars,
            "redirects": 1, "format": "json",
        })
    except Exception as error:
        return {"error": str(error)}

    pages = data.get("query", {}).get("pages", {})
    if len(pages) == 0:
        return {"error": t("read_failed") + str(title)}

    page = list(pages.values())[0]
    extract = page.get("extract", "")
    if not extract:
        return {"error": t("read_failed") + str(title)}

    return {"title": page.get("title", title), "extract": extract}


def run_python(code):
    """工具 3：跑一段 Python，把 print() 出来的东西还给模型。

    ⚠️ 安全提醒（这一段请认真读一遍）

    这里执行的是**模型生成的代码**。我们用独立子进程 + 超时来限制它，
    但那远远不算沙箱 —— 这段代码仍然能读写你的文件。

    本实验里模型写的都是「对已取回的数字做算术」，风险很低。
    但**真实项目绝对不能这样跑模型生成的代码**，必须放进容器
    （Docker / gVisor / Firecracker 之类）里，并切断网络和文件系统。

    原书那个实验用的是 OpenAI 托管的 code_interpreter —— 沙箱在厂商那边。
    我们没有厂商托管的沙箱，所以这里是个教学用的简化版。
    """
    source = str(code)
    try:
        proc = subprocess.run(
            [sys.executable, "-c", source],
            capture_output=True, text=True, timeout=CODE_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return {"error": t("code_timeout", sec=CODE_TIMEOUT)}
    except Exception as error:
        return {"error": str(error)}

    stdout = proc.stdout.strip()
    stderr = proc.stderr.strip()

    if proc.returncode != 0:
        # 代码报错也返回字典，让模型看到 traceback 自己改 ——
        # 这跟工具出错返回 {"error": ...} 是同一个道理。
        return {"error": stderr[-600:] or "代码执行失败"}

    if not stdout:
        return {"error": t("code_no_output")}

    return {"stdout": stdout[:1500]}


def execute_tool(tool_name, tool_args, mode):
    """执行模型点名的工具。mode 决定哪些工具可用。

    ★ 两个消融点都在这里，而且都只是「把某个工具拿掉」。
    """

    if tool_name == "search":
        return search(tool_args.get("query"))

    elif tool_name == "read":
        if mode == "no_read":
            # ★ 消融点 no_read：只能用搜索摘要，读不了正文。
            return {"error": t("read_disabled")}
        return read(tool_args.get("title"))

    elif tool_name == "run_python":
        if mode == "no_code":
            # ★ 消融点 no_code：不能跑代码，只能心算。
            return {"error": t("code_disabled")}
        return run_python(tool_args.get("code"))

    else:
        return {"error": t("no_such_tool") + str(tool_name)}


# ==========================================================================
#  第 2 部分：系统提示词（Part 2）
# ==========================================================================


def build_system_prompt(mode):
    """拼系统提示词。

    ★ 消融点：no_code 模式下，工具清单里没有 run_python，
      而且「一律写代码算」那段建议会换成「只能心算」。
    """
    parts = []
    parts.append(t("sys_role"))

    tools_text = t("sys_tools_head")
    if mode != "no_code":
        tools_text = tools_text + t("sys_tool_code")
    tools_text = tools_text + t("sys_tools_tail")

    if mode == "no_code":
        tools_text = tools_text + t("sys_no_code_advice")
    else:
        tools_text = tools_text + t("sys_code_advice")

    parts.append(tools_text)
    parts.append(t("sys_protocol") + "\n" + t("sys_no_guessing"))

    return "\n\n".join(parts)


# ==========================================================================
#  第 3 部分：拼上下文（和前两个实验结构一样）
# ==========================================================================


def describe_visible_steps(steps):
    if len(steps) == 0:
        return t("no_history_yet")
    first = steps[0]["number"]
    last = steps[-1]["number"]
    if first == last:
        return t("only_step", n=first)
    return t("steps_range", a=first, b=last)


def render_context(task, steps):
    """把走过的每一步渲染成这一轮的提示词。本实验不消融上下文。"""
    lines = []
    lines.append(t("ctx_task") + task)
    lines.append("")

    for step in steps:
        lines.append(t("ctx_step", n=step["number"]))
        lines.append(t("ctx_your_reply")
                     + json.dumps(step["assistant"], ensure_ascii=False))
        for one_result in step["results"]:
            lines.append(t("ctx_tool_returned", tool=str(one_result["tool"]))
                         + json.dumps(one_result["result"], ensure_ascii=False))
        lines.append("")

    lines.append(t("ctx_next"))
    return "\n".join(lines)


def extract_tool_calls(reply):
    """归一成「要调的工具」列表。和前两个实验是同一个辅助函数。"""
    calls = reply.get("calls")
    if isinstance(calls, list) and len(calls) > 0:
        return calls
    if reply.get("tool"):
        return [{"tool": reply["tool"], "args": reply.get("args", {})}]
    return []


# ==========================================================================
#  第 4 部分：两个 runner（Part 4）
# ==========================================================================


def run_hosted(task, verbose=True):
    """把整件事交给厂商 —— 和实验 1-2 的 hosted 一样，这里没有循环。"""
    if verbose:
        print("")
        print("=" * 68)
        print(t("hosted_title"))
        print("=" * 68)
        print(t("hosted_note"))
        print("")
        print(t("hosted_waiting"))

    start_time = time.time()
    try:
        def show_progress(waited, attempt, total):
            suffix = ""
            if total > 1 and attempt > 1:
                suffix = t("retrying", n=attempt, total=total)
            print("\r  " + t("waited", sec=waited) + suffix + "   ",
                  end="", flush=True)

        answer, turns = complete_hosted(task + t("hosted_prompt_suffix"),
                                        on_progress=show_progress)
        print("")
    except HostedNotAvailable as error:
        if verbose:
            print("")
            print(t("hosted_unavailable", msg=str(error)))
        return {"mode": "hosted", "answer": None, "iterations": 0,
                "tool_calls": 0, "code_blocks": 0, "unavailable": True,
                "hit_cap": False}
    except HostedInterrupted as error:
        if verbose:
            print("")
            print(t("hosted_interrupted", msg=str(error)))
            print(t("hosted_interrupted_lesson"))
        return {"mode": "hosted", "answer": None, "iterations": 0,
                "tool_calls": 0, "code_blocks": 0, "unavailable": True,
                "hit_cap": False}
    elapsed = time.time() - start_time

    if verbose:
        print(t("took", sec=round(elapsed, 1)))
        if turns is not None:
            print(t("hosted_turns", n=turns))
        print("")
        print(t("answer") + str(answer))
        print("")
        print(t("hosted_blind"))
        print("")

    return {"mode": "hosted", "answer": answer, "iterations": turns or 0,
            "tool_calls": 0, "code_blocks": 0, "unavailable": False,
            "hit_cap": False}


def run_diy(task, mode="deep", max_iterations=16, backend=None, verbose=True):
    """循环我们自己跑。和实验 1-1、1-2 是同一个循环，只是工具不同。"""
    steps = []
    tool_call_count = 0
    code_block_count = 0
    system_prompt = build_system_prompt(mode)

    for round_number in range(1, max_iterations + 1):

        prompt = render_context(task, steps)

        if verbose:
            print("")
            print("=" * 68)
            print(t("round_line1", n=round_number,
                    total=max_iterations, mode=mode))
            print(t("round_line2", ctx=describe_visible_steps(steps),
                    chars=len(prompt)))
            print("=" * 68)

        if SHOW_PROMPT:
            print("")
            print(t("box_top") + "-" * 38)
            for one_line in prompt.split("\n"):
                print("  | " + one_line)
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
            if verbose:
                print("")
                print(t("answer") + str(answer))
                print("")
            return {"mode": mode, "answer": answer, "iterations": round_number,
                    "tool_calls": tool_call_count,
                    "code_blocks": code_block_count,
                    "hit_cap": False, "unavailable": False}

        results_this_round = []
        if verbose:
            print("")

        for call_index in range(len(wanted_calls)):
            one_call = wanted_calls[call_index]
            tool_name = one_call.get("tool")
            tool_args = one_call.get("args", {})

            result = execute_tool(tool_name, tool_args, mode)
            tool_call_count = tool_call_count + 1

            if verbose:
                if len(wanted_calls) > 1:
                    label = t("tool_n", i=call_index + 1,
                              total=len(wanted_calls))
                else:
                    label = t("tool")

                # 代码单独排版打印出来 —— 这是本实验最值得看的东西：
                # 你能亲眼看到模型「想」的过程被写成了一段可验算的程序。
                if tool_name == "run_python" and tool_args.get("code"):
                    code_block_count = code_block_count + 1
                    print("  " + label + " run_python")
                    print(t("code_header"))
                    for code_line in str(tool_args["code"]).split("\n"):
                        print("  │ " + code_line)
                    print(t("code_footer"))
                    print("        -> " + str(result)[:400])
                else:
                    print("  " + label + " " + str(tool_name)
                          + "(" + str(tool_args) + ")")
                    shown = json.dumps(result, ensure_ascii=False)
                    if len(shown) > 300:
                        shown = shown[:300] + " …"
                    print("        -> " + shown)

            results_this_round.append({"tool": tool_name, "result": result})

        steps.append({
            "number": round_number,
            "assistant": reply,
            "results": results_this_round,
        })

    if verbose:
        print("")
        print(t("hit_cap", n=max_iterations))
        print("")

    return {"mode": mode, "answer": None, "iterations": max_iterations,
            "tool_calls": tool_call_count, "code_blocks": code_block_count,
            "hit_cap": True, "unavailable": False}


def run(task, mode="deep", backend=None, verbose=True):
    """分发。注意 hosted 压根不走那个循环。"""
    if mode == "hosted":
        return run_hosted(task, verbose=verbose)
    return run_diy(task, mode=mode, backend=backend, verbose=verbose)


# ==========================================================================
#  第 5 部分：命令行入口（Part 5）
# ==========================================================================


def ask_for_task(mode):
    """让用户输入研究问题。**故意不设默认值。**"""
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
    """如果用户输的是个编号（比如 "3"），就取对应的例子。"""
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
    """跑完之后，打印用同一个问题换模式跑的完整命令。"""
    others = []
    for m in MODES:
        if m != mode_arg:
            others.append(m)
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
        if r["mode"] == "hosted":
            print(t("summary_hosted"))
        else:
            print(t("summary_stats", r=r["iterations"],
                    t=r["tool_calls"], c=r["code_blocks"]))

        if r.get("unavailable"):
            ending = t("summary_failed")
        elif r.get("hit_cap"):
            ending = t("summary_capped")
        else:
            ending = str(r["answer"]).replace("\n", " ")[:70]
        print(t("summary_result") + ending)

    print(t("summary_verify"))


def _quiet_ctrl_c(exc_type, exc_value, tb):
    """Ctrl+C 是正常操作，不是崩溃 —— 不要甩一屏 traceback 吓人。"""
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
