"""
Lab 01 — Context Ablation.

    Agent = LLM + context + tools, wrapped in a while loop.

An LLM is a pure function: text in, text out. It has no memory and cannot
execute anything. All it does is emit JSON saying "I'd like to call
search_products('keyboard')". YOUR Python runs the function, pastes the result
back into the text, and asks again. Loop until it answers instead of calling.

The experiment: run one task five times, deleting one part of the context each
time, and watch HOW it breaks.

    python3 agent.py             # print usage
    python3 agent.py full        # baseline
    python3 agent.py all         # run all 5 modes, print a comparison

No API key needed — it uses your existing Claude Code / Codex login.

Full walkthrough: README.md (English) / README.zh-CN.md (中文).
Set LANG below to switch the language of both the output and the prompts.
"""

import json
import sys
import time

from llm import complete, detect_backend, parse_json_reply


# --------------------------------------------------------------------------
#  Settings you may want to flip
# --------------------------------------------------------------------------

LANG = "zh"          # "zh" | "en" — language of the output AND the prompts

SHOW_PROMPT = True   # True = print the exact text sent to the model each round.
                     # Worth turning on at least once: it shows that "context"
                     # is nothing but a string you assembled yourself.


MODES = [
    "full",              # full context (baseline)
    "no_history",        # drop history, keep only the latest step
    "no_reasoning",      # drop the model's own reasoning
    "no_tool_calls",     # never tell it tools exist
    "no_tool_results",   # call tools, but hide what they returned
]


# --------------------------------------------------------------------------
#  All user-visible strings, per language.
#  This covers the PROMPTS too, not just console output — a model prompted in
#  English answers in English, so the whole run switches together.
# --------------------------------------------------------------------------

TEXT = {
    "zh": {
        # --- text sent to the model ---
        "sys_role": "你是一个一步步解决任务的 agent。",
        "sys_no_tools": "你没有任何工具，只能凭自己的知识回答。",
        "sys_tools": """你可以使用这些工具：
- search_products(keyword)              按关键词查商品，返回名称和美元单价
- get_rate(from_currency, to_currency)  查汇率
- calc(expression)                      算算术表达式，如 "199 * 3"
""",
        "sys_protocol": """只输出一个 JSON 对象，不要有别的内容。要么是：
  {"reasoning": "<一句话思路>", "calls": [{"tool": "<工具名>", "args": {...}}]}
要么，当你已经得出完整答案时：
  {"reasoning": "<一句话思路>", "answer": "<答案>"}

注意 calls 是个数组，可以一次放多个工具调用：
  · 如果几个工具彼此不依赖（谁都不需要另一个的结果），就一次全放进去，
    它们会被同时执行，这样能少跑好几轮。
  · 如果后一个工具需要前一个的返回值，那就只放前一个，等结果出来下一轮再调。""",
        "sys_no_guessing": "绝对不要猜一个本可以用工具查到的数字。",
        "ctx_task": "任务：",
        "ctx_step": "--- 第 {n} 步 ---",
        "ctx_your_reply": "你的回复：",
        "ctx_tool_returned": "工具 {tool} 返回：",
        "ctx_hidden": "[结果已隐藏]",
        "ctx_next": "现在给出你的下一条 JSON 回复。",
        "task_default": "我想买 3 个 mechanical keyboard，帮我查一下单价，算出总价，并折算成人民币。",
        # --- console output ---
        "no_history_yet": "上下文里还没有历史",
        "only_step": "上下文只含第 {n} 步",
        "steps_range": "上下文含第 {a}~{b} 步",
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
        "round_line2": "  {ctx}     提示词 {chars} 字符",
        "box_top": "  ┌─── 实际发给模型的内容 ",
        "asking": "  正在问模型…",
        "took": " 用了 {sec} 秒",
        "thinking": "  [思考] ",
        "thinking_dropped": "         ↑ 但 no_reasoning 模式下，它不会被带进下一轮",
        "tool": "[工具]",
        "tool_n": "[工具 {i}/{total}]",
        "parallel": "  ↑ 这一轮并行调了 {n} 个工具（模型判断它们互不依赖）",
        "answer": "  [答案] ",
        "hit_cap": "  [上限] 跑满 {n} 轮仍未给出答案",
        "no_such_tool": "没有这个工具：",
        "err_product": "没找到这个商品；可选关键词：",
        "err_currency": "不支持的货币 {c}；可选：",
        # --- summary + help ---
        "summary_title": "对比结果",
        "summary_capped": "跑满上限，没给出答案",
        "summary_mode": "模式：",
        "summary_stats": "  轮数：{r}   工具调用：{t} 次",
        "summary_result": "  结果：",
        "unknown_mode": "✗ 不认识的模式：",
        "all_warning": """
⚠️  all 模式要跑 5 个实验，最多 40 次模型调用，大约需要 3～8 分钟。
    过程中屏幕会一直有输出，那是正常的，不是死循环。
    想快很多的话：LAB_BACKEND=api DEEPSEEK_API_KEY=xxx python3 agent.py all""",
        "all_show_prompt": """    另外你把 SHOW_PROMPT 打开了，输出会非常长 ——
    想看对比表的话，建议先把它改回 False。""",
        "exp_header": "# 实验 {i}/{total}：{mode}",
        "help": """
======================================================================
 实验 01：上下文消融
======================================================================

用法：
    python3 agent.py <模式> ["自定义任务"]

【单个模式】跑一次，约 30 秒 ~ 1 分钟：
    full              完整上下文 —— 基线，先跑这个
    no_history        删掉历史，只留最近一步
    no_reasoning      删掉模型自己的思考过程（reasoning 字段）
    no_tool_calls     压根不告诉它有工具
    no_tool_results   工具照调，但不给它看返回值

【对比模式】把上面 5 个挨个跑一遍，约 3 ~ 8 分钟：
    all               五种模式全跑，最后打印一张对比表

举例：
    python3 agent.py full
    python3 agent.py no_history
    python3 agent.py all
    python3 agent.py full "我想买 2 个 monitor，折算成日元多少钱？"

建议顺序：
    1. 先跑 full，建立基线，记住它用了几轮、调了几次工具
    2. 再一个个跑消融模式 —— 每跑一个之前，先猜结果会怎么变
    3. 最后跑 all，看那张对比表

把文件开头的 LANG 改成 "en" 可切换成英文输出。
详细讲解见 README.zh-CN.md。
""",
    },
    "en": {
        # --- text sent to the model ---
        "sys_role": "You are an agent that solves tasks step by step.",
        "sys_no_tools": "You have no tools. Answer from your own knowledge.",
        "sys_tools": """You have these tools:
- search_products(keyword)              look up a product, returns name and USD price
- get_rate(from_currency, to_currency)  look up an exchange rate
- calc(expression)                      evaluate arithmetic, e.g. "199 * 3"
""",
        "sys_protocol": """Reply with ONE JSON object and nothing else. Either:
  {"reasoning": "<one short sentence>", "calls": [{"tool": "<name>", "args": {...}}]}
or, when you have the complete answer:
  {"reasoning": "<one short sentence>", "answer": "<your answer>"}

Note that `calls` is an array — you may put several tool calls in it at once:
  - If the tools are INDEPENDENT (none needs another's result), put them all in
    one reply. They run together, which saves whole round trips.
  - If a later tool needs an earlier one's return value, request only the
    earlier one now and call the other next round.""",
        "sys_no_guessing": "Never guess a number you could look up with a tool.",
        "ctx_task": "TASK: ",
        "ctx_step": "--- step {n} ---",
        "ctx_your_reply": "You replied: ",
        "ctx_tool_returned": "Tool {tool} returned: ",
        "ctx_hidden": "[result hidden]",
        "ctx_next": "Now give your next JSON reply.",
        "task_default": "I want to buy 3 mechanical keyboards. Look up the unit "
                        "price, compute the total, and convert it to CNY.",
        # --- console output ---
        "no_history_yet": "no history in context yet",
        "only_step": "context holds step {n} only",
        "steps_range": "context holds steps {a}-{b}",
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
        "round_line2": "  {ctx}     prompt {chars} chars",
        "box_top": "  +--- exact text sent to the model ",
        "asking": "  asking the model...",
        "took": " took {sec}s",
        "thinking": "  [thinking] ",
        "thinking_dropped": "             ^ but in no_reasoning mode this is NOT carried forward",
        "tool": "[tool]",
        "tool_n": "[tool {i}/{total}]",
        "parallel": "  ^ {n} tools called in parallel (model judged them independent)",
        "answer": "  [answer] ",
        "hit_cap": "  [cap] hit {n} rounds without answering",
        "no_such_tool": "no such tool: ",
        "err_product": "product not found; try one of: ",
        "err_currency": "unsupported currency {c}; try one of: ",
        # --- summary + help ---
        "summary_title": "COMPARISON",
        "summary_capped": "hit the cap without answering",
        "summary_mode": "mode: ",
        "summary_stats": "  rounds: {r}   tool calls: {t}",
        "summary_result": "  result: ",
        "unknown_mode": "x unknown mode: ",
        "all_warning": """
!  'all' runs 5 experiments, up to 40 model calls, roughly 3-8 minutes.
   Output keeps scrolling the whole time. That is normal, not an infinite loop.
   Much faster: LAB_BACKEND=api DEEPSEEK_API_KEY=xxx python3 agent.py all""",
        "all_show_prompt": """   Also, SHOW_PROMPT is on, so the output will be very long --
   set it back to False if you want to see the comparison table.""",
        "exp_header": "# Experiment {i}/{total}: {mode}",
        "help": """
======================================================================
 Lab 01: Context Ablation
======================================================================

Usage:
    python3 agent.py <mode> ["your own task"]

SINGLE MODE - one run, roughly 30-60 seconds:
    full              full context -- the baseline, start here
    no_history        drop history, keep only the latest step
    no_reasoning      drop the model's own reasoning field
    no_tool_calls     never tell it that tools exist
    no_tool_results   call tools, but hide what they returned

COMPARISON - runs all 5 of the above, roughly 3-8 minutes:
    all               run every mode, then print a comparison table

Examples:
    python3 agent.py full
    python3 agent.py no_history
    python3 agent.py all
    python3 agent.py full "Buy 2 monitors -- what is the total in JPY?"

Suggested order:
    1. Run full first. Note how many rounds and tool calls it took.
    2. Then each ablation -- PREDICT the result before running each one.
    3. Run all last, for the comparison table.

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
#  Part 1: Tools
# ==========================================================================
# Tools are ordinary Python functions. Nothing special about them.
# The model CANNOT run these — it can only name one, and we call it (Part 4).
# Every tool returns a dict on success and on failure alike, so Part 4 can
# handle them uniformly.

# Pretend this is a product database. In a real project: a DB or HTTP call.
CATALOG = {
    "mechanical keyboard": {"name": "Keychron Q1 Pro", "usd": 199.0},
    "wireless mouse": {"name": "Logitech MX Master 4", "usd": 119.0},
    "monitor": {"name": "Dell U2723QE 27-inch 4K", "usd": 579.0},
}

# Pretend this is a live rate table. Each number = "1 USD is this much".
RATES = {
    "USD": 1.0,
    "CNY": 7.24,
    "EUR": 0.92,
    "JPY": 149.50,
}


def search_products(keyword):
    """Tool 1: look up a product by keyword."""

    clean_keyword = str(keyword).strip().lower()

    # dict.get() returns None instead of raising when the key is missing.
    product = CATALOG.get(clean_keyword)

    if product is None:
        # Return an error dict rather than raising: this text goes back into
        # the context, so the model can see it and correct itself.
        return {"error": t("err_product") + str(sorted(CATALOG))}

    return product


def get_rate(from_currency, to_currency):
    """Tool 2: look up the exchange rate between two currencies."""

    source = str(from_currency).upper()
    target = str(to_currency).upper()

    if source not in RATES:
        return {"error": t("err_currency", c=source) + str(sorted(RATES))}
    if target not in RATES:
        return {"error": t("err_currency", c=target) + str(sorted(RATES))}

    rate = RATES[target] / RATES[source]

    return {"rate": round(rate, 4), "from": source, "to": target}


def calc(expression):
    """Tool 3: evaluate an arithmetic expression such as "199 * 3"."""

    # {"__builtins__": {}} cuts eval off from built-in functions, so a hostile
    # expression cannot reach the filesystem.
    # WARNING: do not use eval like this in a real project. It is here only to
    # keep the lab short.
    try:
        answer = eval(str(expression), {"__builtins__": {}}, {})
        return {"result": answer}
    except Exception as error:
        return {"error": str(error)}


# ==========================================================================
#  Part 2: System prompt
# ==========================================================================
# The system prompt is the agent's job description, resent on every call.
# Realise what this means: THIS TEXT IS YOUR PROGRAM. You steer an agent
# mainly by editing prose, not by editing Python.


def build_system_prompt(mode):
    """Assemble the system prompt for this run.

    ABLATION: in no_tool_calls mode the tool catalog is simply never shown.
    """

    parts = []
    parts.append(t("sys_role"))

    if mode == "no_tool_calls":
        parts.append(t("sys_no_tools"))
        parts.append(t("sys_protocol"))
    else:
        parts.append(t("sys_tools"))
        # The "never guess" line only makes sense when tools exist. Leaving it
        # in no_tool_calls mode contaminates the experiment: the model obeys it
        # and refuses, so you observe rule-following, not tool-lessness.
        # We hit this for real on the first run — see SOLUTION.md.
        parts.append(t("sys_protocol") + "\n" + t("sys_no_guessing"))

    return "\n\n".join(parts)


# ==========================================================================
#  Part 3: Assembling the context   *** the heart of this lab ***
# ==========================================================================
# The LLM endpoint is STATELESS. The server stores nothing. On every single
# call you resend everything that has happened so far.
#
# So "context" is not mystical: it is the string the function below builds.
# Everything the agent knows on round 5 is whatever that string says.
#
# Three of the five ablations live here, one or two lines each. That is the
# lesson of this lab: context engineering IS editing this string.


def pick_visible_steps(steps, mode):
    """Decide which past steps the model gets to see this round.

    ABLATION: no_history keeps only the most recent step.

    Split into its own function because run() also needs this to report
    "context holds steps 1-3" — one rule, one place.
    """

    if mode == "no_history":
        if len(steps) == 0:
            return []
        # Wrapped in a list so callers can always iterate the same way.
        return [steps[-1]]

    return steps


def describe_visible_steps(visible_steps):
    """One-line description of what is in context, for the progress output."""

    if len(visible_steps) == 0:
        return t("no_history_yet")

    first_number = visible_steps[0]["number"]
    last_number = visible_steps[-1]["number"]

    if first_number == last_number:
        return t("only_step", n=first_number)

    return t("steps_range", a=first_number, b=last_number)


def render_context(task, steps, mode):
    """Render the trajectory so far into this round's prompt.

    "ROUND" vs "STEP" — two views of the same counter:
        round N = the loop's Nth iteration, i.e. what is happening NOW
        step  N = the result of round N, already recorded into history

    So round N sends steps 1 .. N-1. (Except in no_history mode, which
    deliberately shows only the last one.)

    steps is a list of:
        {"number":    int, same as the round that produced it,
         "assistant": the model's reply that round (dict),
         "results":   [{"tool": name, "result": {...}}, ...]  <- a LIST,
                      because one round can call several tools in parallel}
    """

    visible_steps = pick_visible_steps(steps, mode)

    lines = []
    lines.append(t("ctx_task") + task)
    lines.append("")

    for step in visible_steps:

        # ABLATION: no_reasoning strips the model's own thinking.
        # dict(...) COPIES — without it, pop() would corrupt the stored record.
        assistant_reply = dict(step["assistant"])

        if mode == "no_reasoning":
            assistant_reply.pop("reasoning", None)

        lines.append(t("ctx_step", n=step["number"]))

        # ensure_ascii=False keeps non-ASCII readable instead of \uXXXX escapes.
        lines.append(t("ctx_your_reply")
                     + json.dumps(assistant_reply, ensure_ascii=False))

        # One round may hold several results, so loop. Each line is labelled
        # with its tool name — otherwise the model cannot tell them apart.
        for one_result in step["results"]:

            # ABLATION: no_tool_results replaces the payload with a placeholder.
            if mode == "no_tool_results":
                result_text = t("ctx_hidden")
            else:
                result_text = json.dumps(one_result["result"], ensure_ascii=False)

            lines.append(t("ctx_tool_returned", tool=str(one_result["tool"]))
                         + result_text)

        lines.append("")

    lines.append(t("ctx_next"))

    return "\n".join(lines)


# Recap of the ablations:
#   no_history        drop all but the latest step   -> it redoes finished work
#   no_reasoning      drop the reasoning field       -> it re-derives its plan
#   no_tool_results   hide the return values         -> it invents numbers
#   no_tool_calls     (in build_system_prompt above) -> it hallucinates
#
# Under ten lines in total. Not one of them touches the model or the loop.


# ==========================================================================
#  Part 4: Running the tools the model named
# ==========================================================================


def extract_tool_calls(reply):
    """Normalise the reply into a list of tool calls.

    Accepts both shapes the model might send:
        new (parallel-capable): {"calls": [{"tool": "a", "args": {}}, ...]}
        old (single):           {"tool": "a", "args": {}}

    Normalising at the edge keeps run() free of shape-checking branches.
    Returns [] when no tool was requested.
    """

    calls = reply.get("calls")

    if isinstance(calls, list) and len(calls) > 0:
        return calls

    if reply.get("tool"):
        return [{"tool": reply["tool"], "args": reply.get("args", {})}]

    return []


def execute_tool(tool_name, tool_args):
    """Actually call the tool the model asked for. Returns a dict."""

    # Deliberately a plain if/elif chain: you can see at a glance which name
    # maps to which function. The idiomatic version (a name->function dict plus
    # **kwargs unpacking) is shorter but harder for a beginner to read.

    if tool_name == "search_products":
        return search_products(tool_args.get("keyword"))

    elif tool_name == "get_rate":
        return get_rate(tool_args.get("from_currency"),
                        tool_args.get("to_currency"))

    elif tool_name == "calc":
        return calc(tool_args.get("expression"))

    else:
        # The model does sometimes name a tool that does not exist. Do not
        # crash — hand the error back so it can pick a different one.
        return {"error": t("no_such_tool") + str(tool_name)}


# ==========================================================================
#  Part 5: The loop   <- the whole agent, right here
# ==========================================================================


def run(task, mode="full", max_iterations=8, backend=None, verbose=True):
    """Run one full agent loop. Returns a dict of statistics."""

    steps = []
    tool_call_count = 0

    system_prompt = build_system_prompt(mode)

    for round_number in range(1, max_iterations + 1):

        # ---- 1. Assemble everything so far into a prompt ----
        prompt = render_context(task, steps, mode)

        if verbose:
            visible = pick_visible_steps(steps, mode)
            print("")
            print("=" * 68)
            print(t("round_line1", n=round_number,
                    total=max_iterations, mode=mode))
            print(t("round_line2", ctx=describe_visible_steps(visible),
                    chars=len(prompt)))
            print("=" * 68)

        if SHOW_PROMPT:
            print("")
            print(t("box_top") + "-" * 38)
            for one_line in prompt.split("\n"):
                print("  | " + one_line)
            print("  +" + "-" * 60)

        # ---- 2. Ask the model ----
        # Slowest line in the program: 5-15s per call on the CLI backends.
        # Print "asking" first, or the screen looks frozen.
        if verbose:
            print("")
            print(t("asking"), end="", flush=True)

        start_time = time.time()
        raw_text = complete(prompt, system_prompt, backend=backend)
        elapsed = time.time() - start_time

        if verbose:
            print(t("took", sec=round(elapsed, 1)))

        reply = parse_json_reply(raw_text)

        # `reasoning` arrives in the SAME reply as the tool calls, so print it
        # before them. Reads in the natural order: think -> call -> result.
        if verbose and reply.get("reasoning"):
            print("")
            print(t("thinking") + str(reply["reasoning"]))
            if mode == "no_reasoning":
                # It was produced — it just won't be fed back next round.
                print(t("thinking_dropped"))

        # ---- 3. Stop, or keep going? ----
        # Two stopping conditions: an "answer" field, or no tool requested at
        # all (it replied in prose, which also counts as done).
        has_answer = "answer" in reply
        wanted_calls = extract_tool_calls(reply)

        if has_answer or len(wanted_calls) == 0:
            if has_answer:
                answer = reply["answer"]
            else:
                # No parseable JSON: treat the raw text as the answer.
                # Common in no_tool_calls mode, where it just writes prose.
                answer = raw_text.strip()

            if verbose:
                print("")
                print(t("answer") + str(answer))
                print("")

            return {
                "mode": mode,
                "iterations": round_number,
                "tool_calls": tool_call_count,
                "answer": answer,
                "hit_cap": False,
            }

        # ---- 4. Run every tool it named, collect the results ----
        # A round may hold several calls when the model judges them independent.
        # Real projects would run them on threads; sequential here for clarity.
        # What we save is ROUND TRIPS to the model (seconds each), not the local
        # function calls (microseconds each).
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
                # Call and result on separate lines; one line gets too long.
                print("  " + label + " " + str(tool_name)
                      + "(" + str(tool_args) + ")")
                print("        -> " + str(result))

            # Store the tool name alongside its result: with several results in
            # one round, the model needs to know which is which. (Real APIs pair
            # them with tool_use_id; same idea.)
            results_this_round.append({
                "tool": tool_name,
                "result": result,
            })

        if verbose and len(wanted_calls) > 1:
            print(t("parallel", n=len(wanted_calls)))

        # Append to steps. Next round render_context() folds this back into the
        # prompt — THIS IS THE AGENT'S MEMORY, all of it.
        steps.append({
            "number": round_number,
            "assistant": reply,
            "results": results_this_round,
        })

    # Ran out of rounds without an answer (common in no_history mode).
    if verbose:
        print("")
        print(t("hit_cap", n=max_iterations))
        print("")

    return {
        "mode": mode,
        "iterations": max_iterations,
        "tool_calls": tool_call_count,
        "answer": None,
        "hit_cap": True,
    }


# ==========================================================================
#  Part 6: Command line entry point
# ==========================================================================
# Argument plumbing only — nothing to do with how agents work. Skip on a first
# read.


def print_help():
    print(t("help"))


def print_summary(results):
    print("")
    print("=" * 70)
    print(t("summary_title"))
    print("=" * 70)

    for r in results:
        if r["hit_cap"]:
            ending = t("summary_capped")
        else:
            ending = str(r["answer"]).replace("\n", " ")[:40]

        print("")
        print(t("summary_mode") + r["mode"])
        print(t("summary_stats", r=r["iterations"], t=r["tool_calls"]))
        print(t("summary_result") + ending)


if __name__ == "__main__":

    # No arguments: show what the options are rather than silently picking one.
    if len(sys.argv) == 1:
        print_help()
        sys.exit(0)

    mode_arg = sys.argv[1]

    if mode_arg in ("-h", "--help", "help"):
        print_help()
        sys.exit(0)

    # Optional second argument: your own task, in quotes.
    if len(sys.argv) > 2:
        task = " ".join(sys.argv[2:])   # rejoin if the quotes were forgotten
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
        # Say up front how long this takes, so it doesn't look hung.
        print(t("all_warning"))
        if SHOW_PROMPT:
            print(t("all_show_prompt"))
        print("")

        results = []
        for mode_index in range(len(MODES)):
            m = MODES[mode_index]
            print("")
            print("#" * 70)
            print(t("exp_header", i=mode_index + 1,
                    total=len(MODES), mode=m))
            print("#" * 70)
            results.append(run(task, mode=m, backend=backend))
        print_summary(results)

    else:
        run(task, mode=mode_arg, backend=backend)
