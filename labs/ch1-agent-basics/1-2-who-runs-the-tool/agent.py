"""
实验 1-2：工具由谁来跑？

实验 1-1 问的是「上下文是什么」，这一个问的是另一件事：

    当 agent 用工具时，**真正执行工具的是你，还是厂商？**

现在的模型很多自带工具。你直接问 Claude Code 一个问题，它会自己联网搜索、
自己读网页、自己给答案 —— 你一行循环都没写。
这就是所谓「模型即 Agent」：harness 在厂商那边。

另一条路：工具你自己定义，循环你自己跑，模型只负责**说出**它想调什么。
那正是实验 1-1 搭的东西。

两条路都成立，只是代价不同。这个实验让你亲手体会那个代价 ——
同一个问题，五种跑法。

    python3 agent.py                 # 打印用法说明
    python3 agent.py hosted          # 厂商把整件事搞定
    python3 agent.py diy             # 你自己搞定
    python3 agent.py all             # 五种全跑 + 对比表

不需要 API key。hosted 用 Claude Code 自带的 WebSearch，
diy 系列用维基百科公开 API（无需 key，只用 Python 标准库）。

详细讲解见 README.zh-CN.md（中文）/ README.md（英文）。
"""

import json
import sys
import time
import urllib.parse
import urllib.request

from llm import (complete, complete_hosted, detect_backend, parse_json_reply,
                 HostedNotAvailable, HostedInterrupted)


# --------------------------------------------------------------------------
#  可以改的开关（Settings）
# --------------------------------------------------------------------------

LANG = "zh"          # "zh" | "en" — language of the output AND the prompts

SHOW_PROMPT = False  # 改成 True 会打印每轮真正发给模型的完整文本


MODES = [
    "hosted",            # 厂商跑搜索、也跑循环。你几乎什么都看不到。
    "diy",               # 两样都你自己跑。每一步都看得见。
    "no_search",         # 你跑循环，但完全不给它搜索工具。
    "diy_titles_only",   # 你的 search 只返回标题，不返回摘要。
    "diy_top1",          # 你的 search 只返回 1 条结果，而不是 3 条。
]

# 三个 diy_* 模式共用同一个循环，区别只在 search 工具本身。
DIY_MODES = ["diy", "no_search", "diy_titles_only", "diy_top1"]


# --------------------------------------------------------------------------
#  所有对用户可见的文字，按语言分开放（包含发给模型的提示词）。
# --------------------------------------------------------------------------

TEXT = {
    "zh": {
        "sys_role": "你是一个通过搜索来回答问题的 agent。",
        "sys_no_tools": "你没有任何工具，也不能联网。只能凭自己的记忆回答。",
        "sys_tools": """你可以使用这些工具：
- search(query)       搜索维基百科，返回若干条结果的标题和摘要
- read(title)         读取某个词条的开头段落，拿到具体数据
- calc(expression)    算算术表达式，如 "828 - 632"

注意 search 返回的是**线索**（标题+摘要），不是最终答案。
摘要里往往没有你要的精确数字，这时要用 read 去读正文。
""",
        "sys_protocol": """只输出一个 JSON 对象，不要有别的内容。要么是：
  {"reasoning": "<一句话思路>", "calls": [{"tool": "<工具名>", "args": {...}}]}
要么，当你已经得出完整答案时：
  {"reasoning": "<一句话思路>", "answer": "<答案，要写出具体数字和依据>"}

calls 是数组，互不依赖的工具可以一次全放进去。""",
        "sys_no_guessing": "绝对不要猜数字。查不到就说查不到。",
        "hosted_prompt_suffix": "\n\n请联网搜索后回答，答案里要给出具体数字和信息来源。",
        "ctx_task": "问题：",
        "ctx_step": "--- 第 {n} 步 ---",
        "ctx_your_reply": "你的回复：",
        "ctx_tool_returned": "工具 {tool} 返回：",
        "ctx_next": "现在给出你的下一条 JSON 回复。",
        "ask_task": "请输入你想让 agent 查的问题（直接回车看例子）：\n> ",
        "examples_title": "几个可以直接复制的例子（英文维基百科查得到的都行）：",
        "task_examples": [
            "迪拜最高的建筑和上海最高的建筑，哪个更高？高多少米？",
            "珠穆朗玛峰和乔戈里峰差多少米？",
            "长江和黄河哪条更长？长多少公里？",
        ],
        "picked": "  ✓ 已选第 {n} 个：{task}",
        "number_out_of_range": "  （只有 {n} 个例子，就按你输的内容当问题了）",
        "interrupted": "\n  已中断（Ctrl+C）。想换个问题重跑就再执行一次。",
        "need_task": "没有问题就没法查。把问题写在模式后面，或者不带问题运行进入交互输入。",
        "no_tty": "检测到非交互环境（比如管道/脚本里跑），请把问题直接写在命令行：\n    python3 agent.py {mode} \"你的问题\"",
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
        "task_label": "问题：",
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
        "answer": "  [答案] ",
        "hit_cap": "  [上限] 跑满 {n} 轮仍未给出答案",
        "no_such_tool": "没有这个工具：",
        "search_disabled": "本模式没有搜索工具",
        "no_hits": "没搜到结果",
        "read_failed": "读不到这个词条：",
        # --- hosted 模式专用 ---
        "hosted_title": "  ── hosted 模式：整件事都交给厂商 ──",
        "hosted_note": """  我们只做了一件事：把问题原样发出去，并允许它使用自带的 WebSearch。
  没有循环、没有工具定义、没有上下文拼接 —— 那些都在厂商那边跑。""",
        "hosted_waiting": "  正在等厂商跑完整个流程…",
        "waited": "已等 {sec} 秒…（联网搜索通常 30~90 秒）",
        "retrying": "  [第 {n}/{total} 次尝试]",
        "hosted_turns": "  厂商内部跑了 {n} 轮（这几乎是它唯一愿意告诉我们的事）",
        "hosted_blind": """  注意你看不到的东西：它搜了什么关键词？看了哪些网页？
  中间读到过什么？失败重试过吗？—— 全都没有。只有最后这段文字。""",
        "hosted_unavailable": "  ⚠️  {msg}",
        "hosted_interrupted": "  ✗ hosted 模式没跑完：{msg}",
        "hosted_interrupted_lesson": """
  ── 顺带一提，这次失败正好是本实验的最好例证 ──

  它没跑完。但**你无法知道它卡在哪一步** —— 搜到一半？读网页超时？
  还是在反复改关键词？你手上只有「没跑完」三个字。

  换成 diy 模式跑同一个问题，你会看到每一次搜索和每一次失败：
      python3 agent.py diy "你的问题"

  （想重试 hosted 就再跑一次，这个失败是不确定的，多试一次通常就好。）""",
        # --- 对比表 + 用法说明 ---
        "summary_title": "对比结果",
        "summary_mode": "模式：",
        "summary_visible": "  你能看到的步骤：",
        "summary_you_wrote": "  你写的循环代码：",
        "summary_result": "  结果：",
        "summary_capped": "跑满上限，没给出答案",
        "summary_failed": "（本次未能运行）",
        "lines_zero": "0 行（全在厂商那边）",
        "lines_diy": "整个 run_diy() 循环",
        "steps_hidden": "看不见（只有最终答案）",
        "steps_n": "{n} 步，每一步都可见",
        "unknown_mode": "✗ 不认识的模式：",
        "exp_header": "# 实验 {i}/{total}：{mode}",
        "all_warning": """
⚠️  all 模式要跑 5 个实验，联网搜索比较慢，大约需要 4～10 分钟。""",
        "help": """
======================================================================
 实验 02：工具由谁来跑？
======================================================================

同一个问题，五种跑法。看的是「谁拥有 harness」。

用法：
    python3 agent.py <模式> ["自定义问题"]

【核心三种】
    hosted            厂商跑搜索、也跑循环。你零行代码，也零可见性。
    diy               你跑循环、你实现搜索。每一步都看得见。
    no_search         你跑循环，但不给它搜索工具（基线：它只能靠记忆）

【工具降级两种】证明「工具返回什么，比循环怎么写更重要」
    diy_titles_only   search 只返回标题，不返回摘要
    diy_top1          search 只返回 1 条结果，而不是 3 条

【对比】
    all               五种全跑，最后打印对比表（约 4~10 分钟）

举例：
    python3 agent.py hosted
    python3 agent.py diy
    python3 agent.py diy "珠穆朗玛峰和乔戈里峰差多少米？"

建议顺序：
    1. 先跑 hosted，注意它答得又快又好 —— 但你什么过程都看不到
    2. 再跑 diy，注意慢了很多 —— 但每一次搜索、每一段摘要都在你眼前
    3. 想一想：出了问题，你能 debug 哪一个？

把文件开头的 LANG 改成 "en" 可切换成英文输出。
详细讲解见 README.zh-CN.md。
""",
    },
    "en": {
        "sys_role": "You are an agent that answers questions by searching.",
        "sys_no_tools": "You have no tools and no internet. Answer from memory only.",
        "sys_tools": """You have these tools:
- search(query)       search Wikipedia, returns several titles with snippets
- read(title)         read an article's opening paragraphs, for actual figures
- calc(expression)    evaluate arithmetic, e.g. "828 - 632"

Note that search returns LEADS (titles and snippets), not final answers.
Snippets often lack the exact figure you need — use read to get the article.
""",
        "sys_protocol": """Reply with ONE JSON object and nothing else. Either:
  {"reasoning": "<one short sentence>", "calls": [{"tool": "<name>", "args": {...}}]}
or, when you have the complete answer:
  {"reasoning": "<one short sentence>", "answer": "<answer, with the actual figures and where they came from>"}

`calls` is an array — independent tools can go in one reply.""",
        "sys_no_guessing": "Never guess a figure. If you cannot find it, say so.",
        "hosted_prompt_suffix": "\n\nSearch the web, then answer with the actual figures and your sources.",
        "ctx_task": "QUESTION: ",
        "ctx_step": "--- step {n} ---",
        "ctx_your_reply": "You replied: ",
        "ctx_tool_returned": "Tool {tool} returned: ",
        "ctx_next": "Now give your next JSON reply.",
        "ask_task": "Type the question you want the agent to research (Enter for examples):\n> ",
        "examples_title": "Some you can copy (anything English Wikipedia covers works):",
        "task_examples": [
            "Which is taller, the tallest building in Dubai or the tallest in Shanghai? By how many metres?",
            "How much taller is Everest than K2?",
            "Which river is longer, the Nile or the Amazon, and by how much?",
        ],
        "picked": "  ok, picked #{n}: {task}",
        "number_out_of_range": "  (only {n} examples, treating your input as the question)",
        "interrupted": "\n  Interrupted (Ctrl+C). Run it again to try another question.",
        "need_task": "No question, nothing to research. Put it after the mode, or run without one to be prompted.",
        "no_tty": "Non-interactive environment detected (piped or scripted). Put the question on the command line:\n    python3 agent.py {mode} \"your question\"",
        "rerun_hint": "To compare another mode on the SAME question, copy this and change the mode name:",
        # --- 屏幕输出 ---
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
        "task_label": "Question: ",
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
        "answer": "  [answer] ",
        "hit_cap": "  [cap] hit {n} rounds without answering",
        "no_such_tool": "no such tool: ",
        "search_disabled": "this mode has no search tool",
        "no_hits": "no results",
        "read_failed": "cannot read that article: ",
        # --- hosted 模式专用 ---
        "hosted_title": "  -- hosted mode: the whole job goes to the provider --",
        "hosted_note": """  All we did: send the question as-is, and allow its built-in WebSearch.
  No loop, no tool definitions, no context assembly -- all of that runs on
  the provider's side.""",
        "hosted_waiting": "  waiting for the provider to run the whole thing...",
        "waited": "waited {sec}s... (web search usually takes 30-90s)",
        "retrying": "  [attempt {n}/{total}]",
        "hosted_turns": "  the provider took {n} internal turns (about the only thing it tells us)",
        "hosted_blind": """  Notice what you CANNOT see: which queries did it run? which pages did it
  open? what did it read? did anything fail and get retried? -- none of it.
  Just this final block of text.""",
        "hosted_unavailable": "  !  {msg}",
        "hosted_interrupted": "  x hosted mode did not finish: {msg}",
        "hosted_interrupted_lesson": """
  -- By the way, this failure is the best possible demo of this lab --

  It didn't finish. But you have NO WAY to know where it got stuck: mid-search?
  a page fetch that timed out? rewriting its query over and over? All you have
  is "didn't finish".

  Run the same question in diy mode and you'll see every search and every
  failure:
      python3 agent.py diy "your question"

  (To retry hosted, just run it again -- this failure is non-deterministic.)""",
        # --- 对比表 + 用法说明 ---
        "summary_title": "COMPARISON",
        "summary_mode": "mode: ",
        "summary_visible": "  steps you can see: ",
        "summary_you_wrote": "  loop code you wrote: ",
        "summary_result": "  result: ",
        "summary_capped": "hit the cap without answering",
        "summary_failed": "(did not run)",
        "lines_zero": "0 lines (it all runs at the provider)",
        "lines_diy": "the whole run_diy() loop",
        "steps_hidden": "invisible (final answer only)",
        "steps_n": "{n} steps, every one visible",
        "unknown_mode": "x unknown mode: ",
        "exp_header": "# Experiment {i}/{total}: {mode}",
        "all_warning": """
!  'all' runs 5 experiments with live web searches: roughly 4-10 minutes.""",
        "help": """
======================================================================
 Lab 02: Who runs the tool?
======================================================================

One question, five ways to answer it. The subject is: who owns the harness.

Usage:
    python3 agent.py <mode> ["your own question"]

THE CORE THREE
    hosted            provider runs search AND the loop. Zero code, zero visibility.
    diy               you run the loop and implement search. Everything visible.
    no_search         you run the loop, but hand it no search tool (baseline)

TWO DEGRADED TOOLS - proving the tool's OUTPUT shape matters more than the loop
    diy_titles_only   search returns titles but no snippets
    diy_top1          search returns 1 hit instead of 3

COMPARISON
    all               run all five, then print a table (roughly 4-10 minutes)

Examples:
    python3 agent.py hosted
    python3 agent.py diy
    python3 agent.py diy "How much taller is Everest than K2?"

Suggested order:
    1. Run hosted first. Note how fast and good it is -- and that you saw nothing.
    2. Run diy. Much slower -- but every search and snippet is in front of you.
    3. Then ask yourself: when this breaks, which one can you debug?

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
#  第 1 部分：工具 —— 我们自己实现的那些（Part 1: Tools）
# ==========================================================================
# 维基百科的 API 不需要 key，也不需要第三方包：urllib 是标准库自带的。
# 这样这个实验在哪都能跑。
#
# 注意这套工具的形状：**search 不返回答案，只返回线索**（标题 + 摘要）。
# 想拿到真实数字，必须再用 read 去读正文。
# 这个「两步式」正是真实 agentic search 的样子，
# 也正是朴素 RAG（把检索结果一股脑塞进 prompt）做错的地方。

WIKI_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "ai-engineer-playbook/0.1 (educational lab)"


def _wiki_get(params):
    """向维基百科 API 发一次 GET，返回解析好的 JSON。"""
    url = WIKI_API + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def search(query, limit=3, with_snippets=True):
    """工具 1：搜维基百科。返回的是线索，不是答案。

    limit 和 with_snippets 就是消融模式要调低的两个旋钮。
    """
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
        if with_snippets:
            # API 会用 HTML 标签标出命中词，去掉标签方便阅读。
            snippet = hit.get("snippet", "")
            snippet = snippet.replace('<span class="searchmatch">', "")
            snippet = snippet.replace("</span>", "")
            snippet = snippet.replace("&quot;", '"').replace("&amp;", "&")
            results.append({"title": hit["title"], "snippet": snippet})
        else:
            # ★ 消融点 diy_titles_only：只给线索，不给任何内容。
            results.append({"title": hit["title"]})

    return {"results": results}


def read(title, chars=700):
    """工具 2：读词条开头段落。真实数字都在这里。"""
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


def calc(expression):
    """工具 3：算算术表达式。和实验 1-1 一样。"""
    try:
        answer = eval(str(expression), {"__builtins__": {}}, {})
        return {"result": answer}
    except Exception as error:
        return {"error": str(error)}


def execute_tool(tool_name, tool_args, mode):
    """执行模型点名的工具。mode 决定 search 有多好用。

    ★ 三个消融点都在这里，而且它们**只改 search 返回什么**，
      从不改循环怎么跑。
    """

    if tool_name == "search":
        if mode == "no_search":
            # ★ 消融点 no_search：工具没了。
            # （双保险 —— 系统提示词里也从没提过它。）
            return {"error": t("search_disabled")}

        if mode == "diy_titles_only":
            # ★ 消融点：只有线索，不带内容。
            return search(tool_args.get("query"), limit=3, with_snippets=False)

        if mode == "diy_top1":
            # ★ 消融点：只给一条线索，而不是三条。
            return search(tool_args.get("query"), limit=1)

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


def build_system_prompt(mode):
    """★ 消融点 no_search：工具清单根本不给模型看。"""
    parts = []
    parts.append(t("sys_role"))

    if mode == "no_search":
        parts.append(t("sys_no_tools"))
        parts.append(t("sys_protocol"))
    else:
        parts.append(t("sys_tools"))
        parts.append(t("sys_protocol") + "\n" + t("sys_no_guessing"))

    return "\n\n".join(parts)


# ==========================================================================
#  第 3 部分：拼上下文（和实验 1-1 结构一样）
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
    """把已经走过的每一步渲染成这一轮的提示词。

    和实验 1-1 不同，这里没有历史消融 —— 本实验消融的是**工具**，不是上下文。
    所以每轮都给完整历史。
    """
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
    """归一成「要调的工具」列表。和实验 1-1 是同一个辅助函数。"""
    calls = reply.get("calls")
    if isinstance(calls, list) and len(calls) > 0:
        return calls
    if reply.get("tool"):
        return [{"tool": reply["tool"], "args": reply.get("args", {})}]
    return []


# ==========================================================================
#  第 4 部分：两个 runner —— 这个对比本身就是本实验（Part 4）
# ==========================================================================


def run_hosted(task, verbose=True):
    """把整件事交给厂商。

    看看这个函数有多短。**这里没有循环**，因为循环根本不在我们这边跑。
    搜索、阅读、推理、汇总全在厂商那侧完成，返回给我们的是成品文字。
    """
    if verbose:
        print("")
        print("=" * 68)
        print(t("hosted_title"))
        print("=" * 68)
        print(t("hosted_note"))
        print("")
        print(t("hosted_waiting"), end="", flush=True)

    start_time = time.time()
    try:
        def show_progress(waited, attempt, total):
            # \r 回到行首原地刷新，不会一行行往下滚屏。
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
        return {"mode": "hosted", "answer": None, "turns": None,
                "visible_steps": 0, "seconds": 0, "unavailable": True}
    except HostedInterrupted as error:
        # 重试若干次后厂商那侧仍未跑完。不要甩 traceback ——
        # 而且这次失败本身就是本实验最好的例证，顺手讲一句。
        if verbose:
            print("")
            print(t("hosted_interrupted", msg=str(error)))
            print(t("hosted_interrupted_lesson"))
        return {"mode": "hosted", "answer": None, "turns": None,
                "visible_steps": 0, "seconds": 0, "unavailable": True}
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

    return {"mode": "hosted", "answer": answer, "turns": turns,
            "visible_steps": 0, "seconds": round(elapsed, 1),
            "unavailable": False}


def run_diy(task, mode="diy", max_iterations=8, backend=None, verbose=True):
    """循环我们自己跑。每一次搜索、每一段摘要都看得见。

    这就是实验 1-1 的那个循环，只是换了一套工具 —— 故意这么写，
    好让你看到：**「会联网搜索的 agent」不需要任何新机制**。
    还是那个循环，变的只是工具。
    """
    steps = []
    tool_call_count = 0
    system_prompt = build_system_prompt(mode)
    start_time = time.time()

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
            if has_answer:
                answer = reply["answer"]
            else:
                answer = raw_text.strip()
            if verbose:
                print("")
                print(t("answer") + str(answer))
                print("")
            return {"mode": mode, "answer": answer, "iterations": round_number,
                    "tool_calls": tool_call_count, "visible_steps": len(steps),
                    "seconds": round(time.time() - start_time, 1),
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
                print("  " + label + " " + str(tool_name)
                      + "(" + str(tool_args) + ")")
                # 搜索结果很长，打印时截断一下。
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
            "tool_calls": tool_call_count, "visible_steps": len(steps),
            "seconds": round(time.time() - start_time, 1),
            "hit_cap": True, "unavailable": False}


def run(task, mode="diy", backend=None, verbose=True):
    """分发。注意 hosted 压根不走那个循环。"""
    if mode == "hosted":
        return run_hosted(task, verbose=verbose)
    return run_diy(task, mode=mode, backend=backend, verbose=verbose)


# ==========================================================================
#  第 5 部分：命令行入口（Part 5）
# ==========================================================================


def ask_for_task(mode):
    """让用户输入问题。**故意不设默认值。**

    替他选一个问题，会盖掉本实验最关键的一个旋钮：
    模式对比只有在问题完全相同时才成立，而这件事只有他自己选过问题才体会得到。
    """
    # 管道或脚本里跑时没有键盘可输入 —— 给出明确指引后退出，
    # 而不是卡死在 input() 上。
    if not sys.stdin.isatty():
        print("")
        print(t("no_tty", mode=mode))
        sys.exit(1)

    answer = input(t("ask_task")).strip()
    if answer:
        return _resolve_choice(answer)

    # 直接回车：列几个例子，再问一次。
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
    """如果用户输的是个编号（比如 "3"），就取对应的例子。

    例子是带编号列出来的，人自然会想「输 3 选第三个」。
    不支持的话，"3" 会被原样当成问题发给模型 —— 这是实测踩到的坑。
    """
    if not answer.isdigit():
        return answer

    examples = t("task_examples")
    index = int(answer)
    if 1 <= index <= len(examples):
        chosen = examples[index - 1]
        print(t("picked", n=index, task=chosen))
        return chosen

    # 是数字但超出范围 —— 也可能他真想问一个纯数字，提示一下后照用。
    print(t("number_out_of_range", n=len(examples)))
    return answer


def print_rerun_hint(task, mode_arg):
    """跑完之后，打印用**同一个问题**换个模式跑的完整命令。

    模式对比只有在问题完全相同时才成立，而手抄一长串问题正是悄悄出错的地方。
    """
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
            print(t("summary_you_wrote") + t("lines_zero"))
            print(t("summary_visible") + t("steps_hidden"))
        else:
            print(t("summary_you_wrote") + t("lines_diy"))
            print(t("summary_visible") + t("steps_n", n=r["visible_steps"]))

        if r.get("unavailable"):
            ending = t("summary_failed")
        elif r.get("hit_cap"):
            ending = t("summary_capped")
        else:
            ending = str(r["answer"]).replace("\n", " ")[:60]
        print(t("summary_result") + ending)


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

    if len(sys.argv) > 2:
        task = " ".join(sys.argv[2:])   # 没加引号也兜住：把剩下的都拼回去
    else:
        # 命令行没给问题 → 问他要。没有静默默认值，见 ask_for_task()。
        task = ask_for_task(mode_arg)

    if mode_arg not in MODES and mode_arg != "all":
        print("")
        print(t("unknown_mode") + mode_arg)
        print_help()
        sys.exit(1)

    # 报错要讲人话，不要甩 traceback：「没有后端」是第一次运行最常见的问题，
    # 一堆调用栈对谁都没帮助。
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
