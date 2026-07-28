"""
Lab 02 — Who runs the tool?

Lab 01 asked "what is context". This one asks a different question:

    When an agent uses a tool, WHO actually runs it — you, or the provider?

Modern models ship with tools built in. Ask Claude Code a question and it will
search the web, read pages, and answer, all by itself. You wrote no loop. That
is "the model IS the agent" — the provider owns the harness.

The alternative: you define the tools, you run the loop, the model only ever
names what it wants. That is what lab 01 built.

Both are legitimate. They trade off differently, and this lab makes you feel
the trade-off by answering the SAME question five ways.

    python3 agent.py                 # print usage
    python3 agent.py hosted          # the provider does everything
    python3 agent.py diy             # you do everything
    python3 agent.py all             # all five, then a comparison

No API key needed. `hosted` mode uses Claude Code's built-in WebSearch; the
`diy` modes use Wikipedia's public API (no key, standard library only).

Full walkthrough: README.md (English) / README.zh-CN.md (中文).
"""

import json
import sys
import time
import urllib.parse
import urllib.request

from llm import (complete, complete_hosted, detect_backend, parse_json_reply,
                 HostedNotAvailable)


# --------------------------------------------------------------------------
#  Settings you may want to flip
# --------------------------------------------------------------------------

LANG = "zh"          # "zh" | "en" — language of the output AND the prompts

SHOW_PROMPT = False  # True = print the exact text sent to the model each round


MODES = [
    "hosted",            # provider runs search AND the loop. You see almost nothing.
    "diy",               # you run both. You see everything.
    "no_search",         # you run the loop, but give it no search tool at all.
    "diy_titles_only",   # your search returns titles but no snippets.
    "diy_top1",          # your search returns 1 hit instead of 3.
]

# The three diy_* modes share one loop; only the search tool differs.
DIY_MODES = ["diy", "no_search", "diy_titles_only", "diy_top1"]


# --------------------------------------------------------------------------
#  All user-visible strings, per language (prompts included).
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
        "task_default": "迪拜最高的建筑和上海最高的建筑，哪个更高？高多少米？",
        # console
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
        # hosted mode
        "hosted_title": "  ── hosted 模式：整件事都交给厂商 ──",
        "hosted_note": """  我们只做了一件事：把问题原样发出去，并允许它使用自带的 WebSearch。
  没有循环、没有工具定义、没有上下文拼接 —— 那些都在厂商那边跑。""",
        "hosted_waiting": "  正在等厂商跑完整个流程…",
        "hosted_turns": "  厂商内部跑了 {n} 轮（这几乎是它唯一愿意告诉我们的事）",
        "hosted_blind": """  注意你看不到的东西：它搜了什么关键词？看了哪些网页？
  中间读到过什么？失败重试过吗？—— 全都没有。只有最后这段文字。""",
        "hosted_unavailable": "  ⚠️  {msg}",
        # summary
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
        "task_default": "Which is taller, the tallest building in Dubai or the "
                        "tallest in Shanghai? By how many metres?",
        # console
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
        # hosted mode
        "hosted_title": "  -- hosted mode: the whole job goes to the provider --",
        "hosted_note": """  All we did: send the question as-is, and allow its built-in WebSearch.
  No loop, no tool definitions, no context assembly -- all of that runs on
  the provider's side.""",
        "hosted_waiting": "  waiting for the provider to run the whole thing...",
        "hosted_turns": "  the provider took {n} internal turns (about the only thing it tells us)",
        "hosted_blind": """  Notice what you CANNOT see: which queries did it run? which pages did it
  open? what did it read? did anything fail and get retried? -- none of it.
  Just this final block of text.""",
        "hosted_unavailable": "  !  {msg}",
        # summary
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
    """Look up a string for the current language, filling in any {placeholders}."""
    template = TEXT[LANG][key]
    if kwargs:
        return template.format(**kwargs)
    return template


# ==========================================================================
#  Part 1: Tools — the ones WE implement
# ==========================================================================
# Wikipedia's API needs no key and no third-party package: urllib is in the
# standard library. That keeps this lab runnable anywhere.
#
# Note the shape of the toolset. `search` does NOT return answers, it returns
# pointers — titles and snippets. To get a real figure you have to `read` the
# article. That two-step shape is what real agentic search looks like, and it
# is the thing naive "just stuff the search results in the prompt" gets wrong.

WIKI_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "ai-engineer-playbook/0.1 (educational lab)"


def _wiki_get(params):
    """One GET against the Wikipedia API. Returns parsed JSON."""
    url = WIKI_API + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def search(query, limit=3, with_snippets=True):
    """Tool 1: search Wikipedia. Returns leads, not answers.

    limit and with_snippets are what the ablation modes turn down.
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
            # The API marks matches with HTML; strip the tags for readability.
            snippet = hit.get("snippet", "")
            snippet = snippet.replace('<span class="searchmatch">', "")
            snippet = snippet.replace("</span>", "")
            snippet = snippet.replace("&quot;", '"').replace("&amp;", "&")
            results.append({"title": hit["title"], "snippet": snippet})
        else:
            # ABLATION diy_titles_only: leads without any content.
            results.append({"title": hit["title"]})

    return {"results": results}


def read(title, chars=700):
    """Tool 2: read an article's intro. This is where actual figures live."""
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
    """Tool 3: evaluate arithmetic. Same as lab 01."""
    try:
        answer = eval(str(expression), {"__builtins__": {}}, {})
        return {"result": answer}
    except Exception as error:
        return {"error": str(error)}


def execute_tool(tool_name, tool_args, mode):
    """Run the tool the model named. `mode` decides how good search is.

    THREE ABLATIONS LIVE HERE, and all three only change what `search`
    RETURNS — never how the loop works.
    """

    if tool_name == "search":
        if mode == "no_search":
            # ABLATION no_search: the tool is gone. (Belt and braces — the
            # system prompt never mentioned it either.)
            return {"error": t("search_disabled")}

        if mode == "diy_titles_only":
            # ABLATION: leads with no content attached.
            return search(tool_args.get("query"), limit=3, with_snippets=False)

        if mode == "diy_top1":
            # ABLATION: one lead instead of three.
            return search(tool_args.get("query"), limit=1)

        return search(tool_args.get("query"))

    elif tool_name == "read":
        return read(tool_args.get("title"))

    elif tool_name == "calc":
        return calc(tool_args.get("expression"))

    else:
        return {"error": t("no_such_tool") + str(tool_name)}


# ==========================================================================
#  Part 2: System prompt
# ==========================================================================


def build_system_prompt(mode):
    """ABLATION no_search: the tool catalog is never shown."""
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
#  Part 3: Context assembly (same shape as lab 01)
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
    """Render the trajectory so far into this round's prompt.

    Unlike lab 01 there is no history ablation here — lab 02 ablates the TOOLS,
    not the context. Full history every round.
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
    """Normalise into a list of calls. Same helper as lab 01."""
    calls = reply.get("calls")
    if isinstance(calls, list) and len(calls) > 0:
        return calls
    if reply.get("tool"):
        return [{"tool": reply["tool"], "args": reply.get("args", {})}]
    return []


# ==========================================================================
#  Part 4: The two runners — this contrast IS the lab
# ==========================================================================


def run_hosted(task, verbose=True):
    """Hand the entire job to the provider.

    Look at how short this is. There is no loop, because we are not running
    one. The provider searches, reads, reasons and synthesises on its side and
    returns finished prose.
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
        answer, turns = complete_hosted(task + t("hosted_prompt_suffix"))
    except HostedNotAvailable as error:
        if verbose:
            print("")
            print(t("hosted_unavailable", msg=str(error)))
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
    """Run the loop ourselves. Every search and every snippet is visible.

    This is lab 01's loop with a different toolset — deliberately, so you can
    see that "an agent that searches the web" needs no new machinery. It is the
    same loop; only the tools changed.
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
                # Search results get long — show a trimmed version.
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
    """Dispatch. Note that `hosted` does not go through the loop at all."""
    if mode == "hosted":
        return run_hosted(task, verbose=verbose)
    return run_diy(task, mode=mode, backend=backend, verbose=verbose)


# ==========================================================================
#  Part 5: Command line entry point
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


if __name__ == "__main__":

    if len(sys.argv) == 1:
        print_help()
        sys.exit(0)

    mode_arg = sys.argv[1]

    if mode_arg in ("-h", "--help", "help"):
        print_help()
        sys.exit(0)

    if len(sys.argv) > 2:
        task = " ".join(sys.argv[2:])
    else:
        task = t("task_default")

    if mode_arg not in MODES and mode_arg != "all":
        print("")
        print(t("unknown_mode") + mode_arg)
        print_help()
        sys.exit(1)

    # Friendly failure instead of a raw traceback: "no backend" is by far the
    # most likely first-run problem, and a stack trace helps nobody.
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
