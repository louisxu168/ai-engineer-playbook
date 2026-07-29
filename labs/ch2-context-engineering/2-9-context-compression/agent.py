"""
实验 2-9：上下文压缩 —— 对话撑爆窗口时该怎么办

实验 1-1 告诉你：上下文就是一段你自己拼出来的字符串，而且它每轮都在变长。

那问题来了：**变长到装不下怎么办？**

真实 agent 跑长任务时一定会撞上这堵墙。业界只有三条路：

    1. 什么都不做   → 迟早爆掉（而且越到后面越贵、越慢）
    2. 裁剪 truncate → 直接扔掉旧的。便宜，但**丢掉的就真没了**
    3. 压缩 compact  → 让模型把旧历史总结成一段摘要，再把摘要拼回去

这个实验让你**亲眼看到三者的区别**，而且是可量化的：
每轮的提示词字符数会打出来，你能看到它是一路涨、卡在原地、还是被压回去。

关键设计：**这个任务的最后一步，必须用到第一步查到的数据。**
所以「裁剪」会真的丢东西，而「压缩」有机会保住 —— 这正是要你观察的地方。

    python3 agent.py                 # 打印用法说明
    python3 agent.py full            # 不做任何处理（基线）
    python3 agent.py truncate        # 只留最近几步
    python3 agent.py compact         # 压缩成摘要 ★核心
    python3 agent.py all             # 四种全跑 + 对比表

不需要 API key。搜索用维基百科公开 API。

详细讲解见 README.zh-CN.md（中文）/ README.md（英文）。
"""

import json
import sys
import time
import urllib.parse
import urllib.request

from llm import complete, detect_backend, parse_json_reply


# --------------------------------------------------------------------------
#  可以改的开关（Settings）
# --------------------------------------------------------------------------

LANG = "zh"          # "zh" | "en" —— 同时切换输出和发给模型的提示词

SHOW_PROMPT = False  # 改成 True 会打印每轮真正发给模型的完整文本

# 这两个阈值刻意设得很小。真实系统是按 token 数触发压缩的（比如到 15 万
# token 才压），但那种规模在教学实验里跑不出来 —— agent 并行查询很高效，
# 五步就把任务做完了，压缩根本来不及触发。
# 所以这里用「步数」当阈值并调到很小，效果等价于「窗口很小」。
# 想看不压缩会涨到多大，跑 full 模式对比。
KEEP_RECENT = 1      # truncate / compact 模式保留最近几步的原文
COMPACT_AFTER = 2    # 超过几步就触发压缩


MODES = [
    "full",           # 不做任何处理，上下文一路变长（基线）
    "truncate",       # 只留最近 KEEP_RECENT 步，更早的直接扔掉
    "compact",        # 更早的压缩成一段摘要 ★本实验的核心
    "compact_tiny",   # 同上，但摘要只允许一句话 —— 压太狠会怎样
]


# --------------------------------------------------------------------------
#  所有对用户可见的文字，按语言分开放（包含发给模型的提示词）
# --------------------------------------------------------------------------

TEXT = {
    "zh": {
        # --- 发给模型的文字 ---
        "sys_role": "你是一个按顺序完成多步查询任务的 agent。",
        "sys_tools": """你可以使用这些工具：
- search(query)   搜维基百科，返回若干条标题和摘要
- read(title)     读词条正文开头，拿到具体数据
- calc(expression) 算算术表达式，如 "829.8 - 599.1"
""",
        "sys_protocol": """只输出一个 JSON 对象，不要有别的内容。要么是：
  {"reasoning": "<一句话思路>", "calls": [{"tool": "<工具名>", "args": {...}}]}
要么，当你已经得出完整答案时：
  {"reasoning": "<一句话思路>", "answer": "<答案，要写出用到的每个数字>"}

calls 是数组，互不依赖的工具可以一次全放进去。""",
        "sys_no_guessing": "绝对不要猜数字。数据不在上下文里就重新查，不要凭印象写。",
        # 压缩用的提示词（这是本实验最值钱的一段 prompt）
        "compact_sys": "你在为一个 agent 压缩它自己的历史记录。",
        "compact_prompt": """下面是一个 agent 已经走过的若干步。请把它压缩成一段摘要，
供它继续往下做任务时使用。

压缩要求（**这几条决定了压缩的成败**）：
1. **所有具体数字、名称、单位一个都不能丢** —— 这是它后面要用的
2. 已经做完的事写成结论，不要复述过程
3. 明确写出「还没做的事」
4. 不要加任何原文里没有的信息

原始历史：
{history}

只输出摘要正文，不要有别的内容。""",
        "compact_tiny_extra": "\n\n**额外限制：整段摘要不能超过一句话。**",
        "ctx_task": "任务：",
        "ctx_summary_head": "【前面若干步的摘要】",
        "ctx_summary_tail": "【摘要结束，以下是最近几步的原文】",
        "ctx_dropped": "【前面 {n} 步已被丢弃，无法找回】",
        "ctx_step": "--- 第 {n} 步 ---",
        "ctx_your_reply": "你的回复：",
        "ctx_tool_returned": "工具 {tool} 返回：",
        "ctx_next": "现在给出你的下一条 JSON 回复。",
        # --- 交互输入 ---
        "ask_task": "请输入你想让 agent 做的多步任务（直接回车看例子）：\n> ",
        "examples_title": "几个可以直接复制的例子（都特意设计成「最后一步要用到第一步的数据」）：",
        "task_examples": [
            "依次查这 5 座建筑的高度：Burj Khalifa、Shanghai Tower、Ping An Finance Centre、Merdeka 118、The Clock Towers。全部查完后，告诉我第一座比最后一座高多少米。",
            "依次查这 4 条河的长度：Yangtze、Yellow River、Amur、Mekong。查完后告诉我第一条比第四条长多少公里。",
            "依次查这 4 颗行星的直径：Jupiter、Saturn、Uranus、Neptune。查完后告诉我第一颗是第四颗的多少倍。",
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
        "round_line1": "  第 {n} 轮 / 共 {total} 轮     模式：{mode}",
        "round_line2": "  提示词 {chars} 字符  {bar} {delta}",
        "ctx_desc_full": "（完整历史 {n} 步）",
        "ctx_desc_trunc": "（丢弃 {dropped} 步，保留最近 {kept} 步）",
        "ctx_desc_compact": "（{compacted} 步已压缩成摘要 + 最近 {kept} 步原文）",
        "box_top": "  ┌─── 实际发给模型的内容 ",
        "asking": "  正在问模型…",
        "took": " 用了 {sec} 秒",
        "thinking": "  [思考] ",
        "tool": "[工具]",
        "tool_n": "[工具 {i}/{total}]",
        "compacting": "  ⟳ 正在压缩前 {n} 步…",
        "compacted_to": "  ⟳ 压缩完成：{before} 字符 → {after} 字符（省了 {pct}%）",
        "compact_result_head": "  ┌─ 压缩出来的摘要 ─────────────────────",
        "compact_result_foot": "  └──────────────────────────────────────",
        "answer": "  [答案] ",
        "hit_cap": "  [上限] 跑满 {n} 轮仍未给出答案",
        "no_such_tool": "没有这个工具：",
        "no_hits": "没搜到结果",
        "read_failed": "读不到这个词条：",
        # --- 对比表 + 用法说明 ---
        "summary_title": "对比结果",
        "summary_mode": "模式：",
        "summary_stats": "  轮数：{r}   工具调用：{t} 次   压缩了 {c} 次",
        "summary_peak": "  提示词峰值：{peak} 字符   最后一轮：{last} 字符",
        "summary_result": "  结果：",
        "summary_capped": "跑满上限，没给出答案",
        "summary_verify": """
看两件事：
  1. 「提示词峰值」—— full 应该明显最高，这就是不处理的代价
  2. 「结果」—— 谁答对了？裁剪掉的那步数据，它是重查了还是编了？""",
        "unknown_mode": "✗ 不认识的模式：",
        "exp_header": "# 实验 {i}/{total}：{mode}",
        "all_warning": "\n⚠️  all 模式要跑 4 个实验，含联网搜索，大约需要 6～15 分钟。",
        "help": """
======================================================================
 实验 2-9：上下文压缩
======================================================================

同一个多步任务，四种上下文处理方式。看的是「装不下了怎么办」。

用法：
    python3 agent.py <模式> ["自定义任务"]

【四种模式】
    full           什么都不做，上下文一路变长（基线，先跑这个）
    truncate       只留最近 1 步，更早的直接扔掉
    compact        更早的压缩成一段摘要 ★核心
    compact_tiny   同上，但摘要只允许一句话 —— 压太狠会怎样

【对比】
    all            四种全跑，最后打印对比表（约 6~15 分钟）

关于「任务」这个参数：
    模式后面可以不写，会交互提示你输入（也可以输编号选例子）。
    例子都特意设计成「最后一步要用到第一步的数据」——
    这样才能看出裁剪到底丢了什么。

举例：
    python3 agent.py full
    python3 agent.py truncate "（和上面完全相同的任务）"

建议顺序：
    1. 先跑 full，记下「提示词峰值」那个数字
    2. 再跑 truncate，看峰值降了多少 —— 以及答案还对不对
    3. 再跑 compact，看它是怎么两头兼顾的
    4. 最后 compact_tiny，看压过头是什么下场

可调参数（文件开头）：
    KEEP_RECENT    保留最近几步原文（默认 1）
    COMPACT_AFTER  超过几步触发压缩（默认 2）

把文件开头的 LANG 改成 "en" 可切换成英文输出。
详细讲解见 README.zh-CN.md。
""",
    },
    "en": {
        # --- text sent to the model ---
        "sys_role": "You are an agent working through a multi-step lookup task in order.",
        "sys_tools": """You have these tools:
- search(query)    search Wikipedia, returns titles with snippets
- read(title)      read an article's opening, for actual figures
- calc(expression) evaluate arithmetic, e.g. "829.8 - 599.1"
""",
        "sys_protocol": """Reply with ONE JSON object and nothing else. Either:
  {"reasoning": "<one short sentence>", "calls": [{"tool": "<name>", "args": {...}}]}
or, when you have the complete answer:
  {"reasoning": "<one short sentence>", "answer": "<answer, listing every figure you used>"}

`calls` is an array — independent tools can go in one reply.""",
        "sys_no_guessing": "Never guess a figure. If the data isn't in your context, look it up again rather than recalling it.",
        "compact_sys": "You are compacting an agent's own history for it.",
        "compact_prompt": """Below are several steps an agent has already taken. Compact them into a
summary it can use to carry on with the task.

Requirements (**these decide whether the compaction works**):
1. **Do not lose a single figure, name or unit** — it needs those later
2. Write finished work as conclusions, not as a replay of the process
3. State explicitly what has NOT been done yet
4. Add nothing that wasn't in the original

Original history:
{history}

Output only the summary text, nothing else.""",
        "compact_tiny_extra": "\n\n**Extra constraint: the whole summary must fit in ONE sentence.**",
        "ctx_task": "TASK: ",
        "ctx_summary_head": "[SUMMARY OF EARLIER STEPS]",
        "ctx_summary_tail": "[END OF SUMMARY - the most recent steps follow verbatim]",
        "ctx_dropped": "[{n} earlier steps were discarded and cannot be recovered]",
        "ctx_step": "--- step {n} ---",
        "ctx_your_reply": "You replied: ",
        "ctx_tool_returned": "Tool {tool} returned: ",
        "ctx_next": "Now give your next JSON reply.",
        # --- interactive input ---
        "ask_task": "Type the multi-step task you want run (Enter for examples):\n> ",
        "examples_title": "Copy one (all are designed so the LAST step needs the FIRST step's data):",
        "task_examples": [
            "Look up the height of these 5 buildings in order: Burj Khalifa, Shanghai Tower, Ping An Finance Centre, Merdeka 118, The Clock Towers. When all five are done, tell me how much taller the first is than the last.",
            "Look up the length of these 4 rivers in order: Yangtze, Yellow River, Amur, Mekong. Then tell me how much longer the first is than the fourth.",
            "Look up the diameter of these 4 planets in order: Jupiter, Saturn, Uranus, Neptune. Then tell me how many times larger the first is than the fourth.",
        ],
        "picked": "  ok, picked #{n}: {task}",
        "number_out_of_range": "  (only {n} examples, treating your input as the task)",
        "need_task": "No task, nothing to run. Put it after the mode, or run without one to be prompted.",
        "no_tty": "Non-interactive environment detected. Put the task on the command line:\n    python3 agent.py {mode} \"your task\"",
        "interrupted": "\n  Interrupted (Ctrl+C). Run it again to try another task.",
        "rerun_hint": "To compare another mode on the SAME task, copy this and change the mode name:",
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
        "task_label": "Task: ",
        "round_line1": "  Round {n} of {total}     mode: {mode}",
        "round_line2": "  prompt {chars} chars  {bar} {delta}",
        "ctx_desc_full": "(full history, {n} steps)",
        "ctx_desc_trunc": "({dropped} steps discarded, {kept} most recent kept)",
        "ctx_desc_compact": "({compacted} steps compacted into a summary + {kept} verbatim)",
        "box_top": "  +--- exact text sent to the model ",
        "asking": "  asking the model...",
        "took": " took {sec}s",
        "thinking": "  [thinking] ",
        "tool": "[tool]",
        "tool_n": "[tool {i}/{total}]",
        "compacting": "  ~ compacting the first {n} steps...",
        "compacted_to": "  ~ compacted: {before} chars -> {after} chars ({pct}% saved)",
        "compact_result_head": "  +- the summary it produced -------------",
        "compact_result_foot": "  +--------------------------------------",
        "answer": "  [answer] ",
        "hit_cap": "  [cap] hit {n} rounds without answering",
        "no_such_tool": "no such tool: ",
        "no_hits": "no results",
        "read_failed": "cannot read that article: ",
        # --- summary + help ---
        "summary_title": "COMPARISON",
        "summary_mode": "mode: ",
        "summary_stats": "  rounds: {r}   tool calls: {t}   compactions: {c}",
        "summary_peak": "  peak prompt: {peak} chars   final round: {last} chars",
        "summary_result": "  result: ",
        "summary_capped": "hit the cap without answering",
        "summary_verify": """
Look at two things:
  1. "peak prompt" - full should be clearly highest. That's the cost of doing nothing.
  2. "result" - who got it right? For the step that got truncated away, did it
     look the data up again, or did it make something up?""",
        "unknown_mode": "x unknown mode: ",
        "exp_header": "# Experiment {i}/{total}: {mode}",
        "all_warning": "\n!  'all' runs 4 experiments with live search: roughly 6-15 minutes.",
        "help": """
======================================================================
 Lab 2-9: Context compaction
======================================================================

One multi-step task, four ways of handling context. Subject: what do you do
when it no longer fits?

Usage:
    python3 agent.py <mode> ["your own task"]

THE FOUR MODES
    full           do nothing; context grows every round (baseline, start here)
    truncate       keep only the last step, discard the rest
    compact        summarise the older steps into a paragraph  <- the core one
    compact_tiny   same, but the summary may be ONE sentence - over-compaction

COMPARISON
    all            run all four, then print a table (roughly 6-15 minutes)

About the "task" argument:
    Optional - you'll be prompted (you can type an example's number).
    The examples are deliberately built so the LAST step needs the FIRST step's
    data. That's what makes truncation's cost visible.

Examples:
    python3 agent.py full
    python3 agent.py truncate "(exactly the same task)"

Suggested order:
    1. Run full. Note the "peak prompt" figure.
    2. Run truncate. How much did the peak drop - and is the answer still right?
    3. Run compact. See how it gets both.
    4. Run compact_tiny last, to see over-compaction fail.

Tunables (top of this file):
    KEEP_RECENT    how many recent steps to keep verbatim (default 1)
    COMPACT_AFTER  how many steps before compaction kicks in (default 2)

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
# 和实验 1-2 / 1-3 是同一套工具。这个实验消融的不是工具，是**上下文的处理方式**。

WIKI_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "ai-engineer-playbook/0.1 (educational lab)"


def _wiki_get(params, attempts=3):
    """向维基百科 API 发一次 GET。

    带 429 退避重试：短时间内跑很多次实验（尤其 all 模式）会撞上维基百科
    限流，返回 HTTP 429。直接失败的话模型会以为「这个词条查不到」，
    然后去编数字 —— 所以这里退避重试一下，比让错误传下去好。
    """
    url = WIKI_API + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_error = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            last_error = error
            if error.code == 429:
                time.sleep(2 * (attempt + 1))   # 2 秒、4 秒、6 秒
                continue
            raise
    raise last_error


def search(query, limit=3):
    """工具 1：搜维基百科，返回线索。"""
    try:
        data = _wiki_get({"action": "query", "list": "search",
                          "srsearch": str(query), "srlimit": limit,
                          "format": "json"})
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


def read(title, chars=900):
    """工具 2：读词条正文开头。"""
    try:
        data = _wiki_get({"action": "query", "prop": "extracts",
                          "titles": str(title), "exintro": 1, "explaintext": 1,
                          "exchars": chars, "redirects": 1, "format": "json"})
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


def calc(expression):
    """工具 3：算算术表达式。"""
    try:
        return {"result": eval(str(expression), {"__builtins__": {}}, {})}
    except Exception as error:
        return {"error": str(error)}


def execute_tool(tool_name, tool_args):
    """执行模型点名的工具。本实验四种模式的工具是完全一样的 ——
    变的只有上下文怎么拼。"""
    if tool_name == "search":
        return search(tool_args.get("query"))
    elif tool_name == "read":
        return read(tool_args.get("title"))
    elif tool_name == "calc":
        return calc(tool_args.get("expression"))
    else:
        return {"error": t("no_such_tool") + str(tool_name)}


# ==========================================================================
#  第 2 部分：系统提示词（Part 2）
# ==========================================================================


def build_system_prompt():
    """四种模式共用同一个系统提示词 —— 这个实验不消融提示词。"""
    return "\n\n".join([
        t("sys_role"),
        t("sys_tools"),
        t("sys_protocol") + "\n" + t("sys_no_guessing"),
    ])


# ==========================================================================
#  第 3 部分：把历史渲染成文本（Part 3）
# ==========================================================================


def render_steps(steps):
    """把若干步渲染成纯文本。压缩和拼上下文都要用它。"""
    lines = []
    for step in steps:
        lines.append(t("ctx_step", n=step["number"]))
        lines.append(t("ctx_your_reply")
                     + json.dumps(step["assistant"], ensure_ascii=False))
        for one_result in step["results"]:
            lines.append(t("ctx_tool_returned", tool=str(one_result["tool"]))
                         + json.dumps(one_result["result"], ensure_ascii=False))
        lines.append("")
    return "\n".join(lines)


# ==========================================================================
#  第 4 部分：压缩   ★★★ 本实验的核心 ★★★
# ==========================================================================
#
# 压缩和裁剪的区别，一句话：
#
#     裁剪  = 把旧历史**删掉**            → 便宜，但丢掉的找不回来
#     压缩  = 把旧历史**换成一段摘要**    → 要多花一次模型调用，但信息还在
#
# 注意压缩本身**也要调一次模型**。这是它的成本，输出里会明确标出来。


def compact_steps(steps, mode, backend=None, verbose=True):
    """把若干步压缩成一段摘要文本。

    这里最关键的其实不是代码，是 `compact_prompt` 那段提示词 ——
    「所有具体数字一个都不能丢」这句话，决定了压缩之后任务还做不做得下去。
    你可以把那句删掉再跑一次，亲眼看差别（练习 2）。
    """
    history_text = render_steps(steps)

    instruction = t("compact_prompt", history=history_text)
    if mode == "compact_tiny":
        # ★ 消融点：把摘要压到一句话。信息必然丢失。
        instruction = instruction + t("compact_tiny_extra")

    if verbose:
        print(t("compacting", n=len(steps)))

    summary = complete(instruction, t("compact_sys"), backend=backend).strip()

    if verbose:
        before = len(history_text)
        after = len(summary)
        saved = 0
        if before > 0:
            saved = int((before - after) * 100 / before)
        print(t("compacted_to", before=before, after=after, pct=saved))
        print(t("compact_result_head"))
        for line in summary.split("\n"):
            print("  │ " + line)
        print(t("compact_result_foot"))

    return summary


def build_context(task, steps, summary, mode, dropped_count):
    """把任务 + （摘要）+ 最近几步 拼成这一轮的提示词。

    四种模式的差别全在这个函数里，每种只差几行。
    """
    lines = []
    lines.append(t("ctx_task") + task)
    lines.append("")

    if summary:
        # compact / compact_tiny：先放摘要，再放最近几步原文
        lines.append(t("ctx_summary_head"))
        lines.append(summary)
        lines.append(t("ctx_summary_tail"))
        lines.append("")
    elif dropped_count > 0:
        # truncate：明确告诉它「前面的没了」，否则它会以为自己从没做过
        lines.append(t("ctx_dropped", n=dropped_count))
        lines.append("")

    lines.append(render_steps(steps))
    lines.append(t("ctx_next"))
    return "\n".join(lines)


def describe_context(mode, total_steps, kept, dropped, compacted):
    """一句话说明这轮上下文里装了什么，用来打印进度。"""
    if mode == "full":
        return t("ctx_desc_full", n=total_steps)
    if mode == "truncate":
        return t("ctx_desc_trunc", dropped=dropped, kept=kept)
    return t("ctx_desc_compact", compacted=compacted, kept=kept)


def extract_tool_calls(reply):
    """归一成「要调的工具」列表。和前面几个实验是同一个辅助函数。"""
    calls = reply.get("calls")
    if isinstance(calls, list) and len(calls) > 0:
        return calls
    if reply.get("tool"):
        return [{"tool": reply["tool"], "args": reply.get("args", {})}]
    return []


# ==========================================================================
#  第 5 部分：主循环（Part 5）
# ==========================================================================


def run(task, mode="full", max_iterations=14, backend=None, verbose=True):
    """跑一次完整循环。四种模式的差别只在「每轮怎么拼上下文」。"""
    steps = []              # 还保留着原文的步骤
    summary = ""            # 压缩出来的摘要（compact 模式才有）
    dropped_count = 0       # 已经被丢弃的步数（truncate 模式才有）
    compacted_count = 0     # 已经被压进摘要的步数
    tool_call_count = 0
    compaction_count = 0
    peak_chars = 0
    last_chars = 0
    prev_chars = 0

    system_prompt = build_system_prompt()

    for round_number in range(1, max_iterations + 1):

        # ---- 关键：在拼上下文之前，先决定要不要处理历史 ----
        if mode == "truncate" and len(steps) > KEEP_RECENT:
            # 裁剪：直接扔掉旧的，扔掉就没了
            dropped_count = dropped_count + (len(steps) - KEEP_RECENT)
            steps = steps[-KEEP_RECENT:]

        elif mode in ("compact", "compact_tiny") and len(steps) > COMPACT_AFTER:
            # 压缩：把旧的换成摘要。注意这里会多调一次模型。
            to_compact = steps[:-KEEP_RECENT]
            if len(to_compact) > 0:
                if summary:
                    # 已经有摘要了 —— 把旧摘要和新一批一起再压一次。
                    # 真实系统也是这么滚动压缩的。
                    merged = [{"number": "摘要", "assistant": {"summary": summary},
                               "results": []}] + to_compact
                    summary = compact_steps(merged, mode, backend, verbose)
                else:
                    summary = compact_steps(to_compact, mode, backend, verbose)
                compacted_count = compacted_count + len(to_compact)
                compaction_count = compaction_count + 1
                steps = steps[-KEEP_RECENT:]

        prompt = build_context(task, steps, summary, mode, dropped_count)
        chars = len(prompt)
        peak_chars = max(peak_chars, chars)
        last_chars = chars

        if verbose:
            # 画一条正比于字符数的条，让增长/压缩一眼可见。
            # 刻度 300 字符一格：实测 full 模式能涨到 1 万多字符，
            # 刻度太小的话第二轮就顶格了，条就失去意义。
            bar = "█" * min(40, chars // 300)
            delta = ""
            if prev_chars > 0:
                diff = chars - prev_chars
                delta = ("+" if diff >= 0 else "") + str(diff)
            print("")
            print("=" * 68)
            print(t("round_line1", n=round_number,
                    total=max_iterations, mode=mode))
            print(t("round_line2", chars=chars, bar=bar, delta=delta))
            print("  " + describe_context(mode, round_number - 1, len(steps),
                                          dropped_count, compacted_count))
            print("=" * 68)
        prev_chars = chars

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
                    "compactions": compaction_count,
                    "peak_chars": peak_chars, "last_chars": last_chars,
                    "hit_cap": False}

        results_this_round = []
        if verbose:
            print("")

        for call_index in range(len(wanted_calls)):
            one_call = wanted_calls[call_index]
            tool_name = one_call.get("tool")
            tool_args = one_call.get("args", {})
            result = execute_tool(tool_name, tool_args)
            tool_call_count = tool_call_count + 1

            if verbose:
                if len(wanted_calls) > 1:
                    label = t("tool_n", i=call_index + 1,
                              total=len(wanted_calls))
                else:
                    label = t("tool")
                print("  " + label + " " + str(tool_name)
                      + "(" + str(tool_args) + ")")
                shown = json.dumps(result, ensure_ascii=False)
                if len(shown) > 220:
                    shown = shown[:220] + " …"
                print("        -> " + shown)

            results_this_round.append({"tool": tool_name, "result": result})

        steps.append({"number": round_number, "assistant": reply,
                      "results": results_this_round})

    if verbose:
        print("")
        print(t("hit_cap", n=max_iterations))
        print("")

    return {"mode": mode, "answer": None, "iterations": max_iterations,
            "tool_calls": tool_call_count, "compactions": compaction_count,
            "peak_chars": peak_chars, "last_chars": last_chars,
            "hit_cap": True}


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
    """如果用户输的是个编号（比如 "2"），就取对应的例子。"""
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
        print(t("summary_stats", r=r["iterations"], t=r["tool_calls"],
                c=r["compactions"]))
        print(t("summary_peak", peak=r["peak_chars"], last=r["last_chars"]))
        if r["hit_cap"]:
            ending = t("summary_capped")
        else:
            ending = str(r["answer"]).replace("\n", " ")[:70]
        print(t("summary_result") + ending)

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
