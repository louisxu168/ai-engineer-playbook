"""
实验 1-1：上下文消融（Context Ablation）

    Agent = LLM + 上下文 + 工具，套在一个 while 循环里。

LLM 是个纯函数：给它文本，它返回文本。它没有记忆，也不能执行任何东西。
它唯一会做的，是输出一段 JSON 说「我想调 search_products('keyboard')」。
真正跑这个函数的是**你的 Python**，跑完把结果拼回文本再问一次。
一直循环，直到它不再要求调工具、而是直接给答案。

所以：**模型是个会说 JSON 的规划器，你是它的手。**

这个实验做的事：同一个任务跑五遍，每遍删掉上下文的一个组成部分，看它怎么坏。

    python3 agent.py             # 打印用法说明
    python3 agent.py full        # 基线
    python3 agent.py all         # 五种模式全跑一遍 + 对比

不需要 API key —— 会用你已经登录的 Claude Code / Codex。

详细讲解见 README.zh-CN.md（中文）/ README.md（英文）。
改下面的 LANG 可以同时切换输出和发给模型的提示词的语言。
"""

import json
import sys
import time

from llm import complete, detect_backend, parse_json_reply


# --------------------------------------------------------------------------
#  可以改的开关（Settings）
# --------------------------------------------------------------------------

LANG = "zh"          # "zh" | "en" — language of the output AND the prompts

SHOW_PROMPT = True   # True = print the exact text sent to the model each round.
                     # 强烈建议至少打开一次：你会看到所谓「上下文」
                     # 无非就是一段你自己拼出来的字符串。


MODES = [
    "full",              # full context (baseline)
    "no_history",        # drop history, keep only the latest step
    "no_reasoning",      # drop the model's own reasoning
    "no_tool_calls",     # never tell it tools exist
    "no_tool_results",   # call tools, but hide what they returned
]


# --------------------------------------------------------------------------
#  所有对用户可见的文字，按语言分开放。
#  注意这里也包含**发给模型的提示词**，不只是屏幕输出 —— 用英文提示词问，
#  模型就用英文回答，所以整个运行过程会一起切换语言。
# --------------------------------------------------------------------------

TEXT = {
    "zh": {
        # --- 发给模型的文字 ---
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
        "ask_task": "请输入你要让 agent 完成的任务（直接回车看例子）：\n> ",
        "examples_title": "几个可以直接复制的例子（工具只认这三个商品）：",
        "task_examples": [
            "我想买 3 个 mechanical keyboard，帮我查一下单价，算出总价，并折算成人民币。",
            "买 2 个 monitor 和 1 个 wireless mouse，一共多少美元？",
            "1 个 monitor 折算成日元是多少？",
        ],
        "picked": "  ✓ 已选第 {n} 个：{task}",
        "number_out_of_range": "  （只有 {n} 个例子，就按你输的内容当问题了）",
        "interrupted": "\n  已中断（Ctrl+C）。想换个问题重跑就再执行一次。",
        "need_task": "没有任务就没法跑。把任务写在模式后面，或者不带任务运行进入交互输入。",
        "no_tty": "检测到非交互环境（比如管道/脚本里跑），请把任务直接写在命令行：\n    python3 agent.py {mode} \"你的任务\"",
        "rerun_hint": "想用同一个任务跑别的模式做对比，复制这行改模式名即可：",
        # --- 屏幕输出 ---
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
        # --- 对比表 + 用法说明 ---
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
        "ask_task": "Type the task you want the agent to do (Enter for examples):\n> ",
        "examples_title": "Some you can copy (the tools only know these three products):",
        "task_examples": [
            "I want to buy 3 mechanical keyboards. Look up the unit price, compute the total, and convert it to CNY.",
            "Buy 2 monitors and 1 wireless mouse - how much in USD?",
            "What is 1 monitor in JPY?",
        ],
        "picked": "  ok, picked #{n}: {task}",
        "number_out_of_range": "  (only {n} examples, treating your input as the question)",
        "interrupted": "\n  Interrupted (Ctrl+C). Run it again to try another question.",
        "need_task": "No task, nothing to run. Put the task after the mode, or run without one to be prompted.",
        "no_tty": "Non-interactive environment detected (piped or scripted). Put the task on the command line:\n    python3 agent.py {mode} \"your task\"",
        "rerun_hint": "To compare another mode on the SAME task, copy this and change the mode name:",
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
    """按当前语言取一段文字，并把 {占位符} 填上。"""
    template = TEXT[LANG][key]
    if kwargs:
        return template.format(**kwargs)
    return template


# ==========================================================================
#  第 1 部分：工具（Part 1: Tools）
# ==========================================================================
# 「工具」就是普通的 Python 函数，没有任何特殊之处。
# 关键点：**模型执行不了这些函数**，它只能说出名字，由我们（第 4 部分）去调。
# 每个工具不管成功失败都返回字典，这样第 4 部分可以统一处理。

# 假装这是个商品数据库。真实项目里这里会是一次数据库查询或 HTTP 请求。
CATALOG = {
    "mechanical keyboard": {"name": "Keychron Q1 Pro", "usd": 199.0},
    "wireless mouse": {"name": "Logitech MX Master 4", "usd": 119.0},
    "monitor": {"name": "Dell U2723QE 27-inch 4K", "usd": 579.0},
}

# 假装这是实时汇率表。数字含义是「1 美元 = 多少这个货币」。
RATES = {
    "USD": 1.0,
    "CNY": 7.24,
    "EUR": 0.92,
    "JPY": 149.50,
}


def search_products(keyword):
    """工具 1：按关键词查商品。"""

    clean_keyword = str(keyword).strip().lower()

    # 字典的 .get()：找不到返回 None，而不是像 [] 那样直接报错。
    product = CATALOG.get(clean_keyword)

    if product is None:
        # 出错也返回字典，不要抛异常 ——
        # 这段错误信息会被塞回上下文给模型看，让它自己纠正。
        return {"error": t("err_product") + str(sorted(CATALOG))}

    return product


def get_rate(from_currency, to_currency):
    """工具 2：查两种货币之间的汇率。"""

    source = str(from_currency).upper()
    target = str(to_currency).upper()

    if source not in RATES:
        return {"error": t("err_currency", c=source) + str(sorted(RATES))}
    if target not in RATES:
        return {"error": t("err_currency", c=target) + str(sorted(RATES))}

    rate = RATES[target] / RATES[source]

    return {"rate": round(rate, 4), "from": source, "to": target}


def calc(expression):
    """工具 3：算一个算术表达式，比如 "199 * 3"。"""

    # {"__builtins__": {}} 切断了 eval 对内置函数的访问，
    # 免得模型传一段危险代码进来（比如删文件）。
    # ⚠️ 真实项目里不要这样用 eval，这里只是为了让实验代码短一点。
    try:
        answer = eval(str(expression), {"__builtins__": {}}, {})
        return {"result": answer}
    except Exception as error:
        return {"error": str(error)}


# ==========================================================================
#  第 2 部分：系统提示词（Part 2: System prompt）
# ==========================================================================
# 系统提示词就是「给模型的岗位说明书」，每次调用都会重新发过去。
# 想明白这句话的分量：**这段文字就是你的程序**。
# 你调教 agent 的主要手段不是写 Python，而是改这段中文。


def build_system_prompt(mode):
    """拼出这一次实验要用的系统提示词。

    ★ 消融点：no_tool_calls 模式下，工具清单根本不给模型看。
    """

    parts = []
    parts.append(t("sys_role"))

    if mode == "no_tool_calls":
        parts.append(t("sys_no_tools"))
        parts.append(t("sys_protocol"))
    else:
        parts.append(t("sys_tools"))
        # 「不要猜数字」这句只在有工具时才有意义。
        # 如果把它留在 no_tool_calls 模式里，模型会遵守它、然后拒绝作答 ——
        # 那你看到的是「守规矩」的后果，而不是「没工具」的后果，实验就污染了。
        # 这是我们第一次跑时真踩到的坑，详见 SOLUTION.zh-CN.md。
        parts.append(t("sys_protocol") + "\n" + t("sys_no_guessing"))

    return "\n\n".join(parts)


# ==========================================================================
#  第 3 部分：拼上下文（Part 3）  ★★★ 整个实验最重要的地方 ★★★
# ==========================================================================
# 大模型的接口是**无状态**的。服务器那边什么都不存。
# 每问一次，你都得把前面发生过的所有事情重新完整发一遍。
#
# 所以「上下文」不是什么玄学，它就是下面这个函数拼出来的一段字符串。
# Agent 在第 5 轮「知道」的一切，就是这段字符串里写了的东西。没有别的了。
#
# 五种消融里有三种在这里实现，每种只改一两行。
# 这就是本实验的核心结论：**上下文工程 = 对这段字符串做增删改**。


def pick_visible_steps(steps, mode):
    """决定这一轮让模型看到历史里的哪几步。

    ★ 消融点：no_history 只留最近一步，前面的全丢掉。

    单独抽成函数，是因为 run() 打印进度时也要知道「这轮给它看了哪几步」，
    两边共用同一份规则，不会打架。
    """

    if mode == "no_history":
        if len(steps) == 0:
            return []
        # 用中括号包成列表，这样调用方的 for 循环写法不用改。
        return [steps[-1]]

    return steps


def describe_visible_steps(visible_steps):
    """把「这轮给模型看了哪几步」说成一句人话，用来打印进度。"""

    if len(visible_steps) == 0:
        return t("no_history_yet")

    first_number = visible_steps[0]["number"]
    last_number = visible_steps[-1]["number"]

    if first_number == last_number:
        return t("only_step", n=first_number)

    return t("steps_range", a=first_number, b=last_number)


def render_context(task, steps, mode):
    """把已经走过的每一步，渲染成这一轮要发给模型的提示词。

    「轮」和「步」是什么关系？—— 同一个计数器的两个视角：
        第 N 轮 = 程序视角：主循环的第 N 次迭代，也就是「现在正在问模型」
        第 N 步 = 模型视角：第 N 轮那次问答的结果，已经被记进历史了

    所以第 N 轮发出去的提示词里，装的是第 1 步 ~ 第 N-1 步。
    （no_history 模式除外 —— 那里故意只给它看最后一步。）

    steps 是一个列表，每项形如：
        {"number":    第几步（整数，等于当时是第几轮）,
         "assistant": 模型当时的回复（字典）,
         "results":   [{"tool": 工具名, "result": {...}}, ...]  ← 是个**列表**，
                      因为一轮可以并行调多个工具}
    """

    visible_steps = pick_visible_steps(steps, mode)

    lines = []
    lines.append(t("ctx_task") + task)
    lines.append("")

    for step in visible_steps:

        # ★ 消融点：no_reasoning 抹掉模型自己的思考。
        # dict(...) 是**复制**一份 —— 不复制的话，下一行的 pop() 会改坏原始记录。
        assistant_reply = dict(step["assistant"])

        if mode == "no_reasoning":
            assistant_reply.pop("reasoning", None)

        lines.append(t("ctx_step", n=step["number"]))

        # ensure_ascii=False 让中文正常显示，不然会变成 \uXXXX 那种转义。
        lines.append(t("ctx_your_reply")
                     + json.dumps(assistant_reply, ensure_ascii=False))

        # 一轮可能有好几个结果，所以要再套一层循环。
        # 每行都标上是哪个工具返回的，否则模型分不清哪个结果对应哪个调用。
        for one_result in step["results"]:

            # ★ 消融点：no_tool_results 把返回值换成一句占位文字。
            if mode == "no_tool_results":
                result_text = t("ctx_hidden")
            else:
                result_text = json.dumps(one_result["result"], ensure_ascii=False)

            lines.append(t("ctx_tool_returned", tool=str(one_result["tool"]))
                         + result_text)

        lines.append("")

    lines.append(t("ctx_next"))

    return "\n".join(lines)


# 小结四种消融：
#   no_history        删掉除最近一步外的历史   → 它会重复做已经做过的事
#   no_reasoning      删掉 reasoning 字段      → 它每轮都要重新想一遍
#   no_tool_results   藏起工具返回值           → 它只能瞎编
#   no_tool_calls     （在上面的系统提示词里）  → 它自信地胡说
#
# 加起来不到十行。**没有一行是在改模型或者改循环。**


# ==========================================================================
#  第 4 部分：执行模型点名的工具（Part 4）
# ==========================================================================


def extract_tool_calls(reply):
    """把模型回复归一成「要调的工具」列表。

    两种写法都兜住：
        新写法（可并行）：{"calls": [{"tool": "a", "args": {}}, ...]}
        老写法（只一个）：{"tool": "a", "args": {}}

    在入口把杂乱输入收拾成统一格式，后面 run() 里就不用到处写 if 判断形状。
    这叫「归一化」，真实项目里很常见。

    返回：列表。没有要调的工具就返回空列表 []。
    """

    calls = reply.get("calls")

    if isinstance(calls, list) and len(calls) > 0:
        return calls

    if reply.get("tool"):
        return [{"tool": reply["tool"], "args": reply.get("args", {})}]

    return []


def execute_tool(tool_name, tool_args):
    """模型说它想调某个工具，这里真正去调。返回一个字典。"""

    # 这里故意用最笨的 if / elif：一眼就能看懂哪个名字对应哪个函数。
    # 老手通常写成「名字 -> 函数」的字典配合 **kwargs 解包，代码更短，
    # 但对新手不好读，所以这里不用。

    if tool_name == "search_products":
        return search_products(tool_args.get("keyword"))

    elif tool_name == "get_rate":
        return get_rate(tool_args.get("from_currency"),
                        tool_args.get("to_currency"))

    elif tool_name == "calc":
        return calc(tool_args.get("expression"))

    else:
        # 模型有时真的会点名一个根本不存在的工具（实验里会遇到）。
        # 不要让程序崩掉，把「没有这个工具」当错误信息还给它，让它自己换一个。
        return {"error": t("no_such_tool") + str(tool_name)}


# ==========================================================================
#  第 5 部分：主循环（Part 5）  ← Agent 的心脏，就这么点东西
# ==========================================================================


def run(task, mode="full", max_iterations=8, backend=None, verbose=True):
    """跑一次完整的 agent 循环。返回一个记录统计结果的字典。"""

    steps = []
    tool_call_count = 0

    system_prompt = build_system_prompt(mode)

    for round_number in range(1, max_iterations + 1):

        # ---- 第一步：把目前为止的一切拼成提示词 ----
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

        # ---- 第二步：问模型 ----
        # 这是整个程序最慢的地方：走 CLI 后端每次要等 5~15 秒。
        # 先打印一句「正在问模型…」，否则屏幕半天不动，看着像卡死了。
        if verbose:
            print("")
            print(t("asking"), end="", flush=True)

        start_time = time.time()
        raw_text = complete(prompt, system_prompt, backend=backend)
        elapsed = time.time() - start_time

        if verbose:
            print(t("took", sec=round(elapsed, 1)))

        reply = parse_json_reply(raw_text)

        # reasoning 是**这一轮就返回**的，跟工具调用装在同一个 JSON 里，
        # 所以要在工具之前打印，读起来才顺：思考 → 调工具 → 拿结果。
        if verbose and reply.get("reasoning"):
            print("")
            print(t("thinking") + str(reply["reasoning"]))
            if mode == "no_reasoning":
                # 这句思考确实产生了，只是不会被拼回下一轮的上下文。
                print(t("thinking_dropped"))

        # ---- 第三步：判断该停了还是该继续 ----
        # 两种停止条件：给了 "answer" 字段；或者根本没要求调工具
        # （说明它在用大白话回答，也算做完了）。
        has_answer = "answer" in reply
        wanted_calls = extract_tool_calls(reply)

        if has_answer or len(wanted_calls) == 0:
            if has_answer:
                answer = reply["answer"]
            else:
                # 连 JSON 都没解析出来，那就把原始文本当答案。
                # no_tool_calls 模式下经常这样 —— 它直接用散文回答了。
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

        # ---- 第四步：执行它点名的每个工具，把结果攒起来 ----
        # 当模型判断几个工具互不依赖时，一轮可能要调好几个。
        # 真实项目里这些独立调用可以用多线程真正同时跑，这里为了好读用了顺序执行 ——
        # 省掉的是**往返模型的次数**（每次好几秒），而不是本地函数调用（几微秒）。
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
                # 调用和返回值分两行打印，挤在一行太长看不清。
                print("  " + label + " " + str(tool_name)
                      + "(" + str(tool_args) + ")")
                print("        -> " + str(result))

            # 把工具名和结果存在一起：一轮有多个结果时，
            # 模型需要知道哪个结果是哪个工具返回的。
            # （真实 API 里靠 tool_use_id 配对，道理一样。）
            results_this_round.append({
                "tool": tool_name,
                "result": result,
            })

        if verbose and len(wanted_calls) > 1:
            print(t("parallel", n=len(wanted_calls)))

        # 存进 steps。下一轮 render_context() 会把它拼回提示词里 ——
        # **这就是 agent 的记忆，全部的记忆。**
        steps.append({
            "number": round_number,
            "assistant": reply,
            "results": results_this_round,
        })

    # 循环跑满了还没给答案（no_history 模式经常这样）。
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
#  第 6 部分：命令行入口（Part 6）
# ==========================================================================
# 只是处理命令行参数，跟 agent 原理没关系，第一次读可以跳过。


def ask_for_task(mode):
    """让用户输入任务。**故意不设默认值。**

    替他选一个任务，会盖掉本实验最关键的一个旋钮：
    消融对比只有在任务完全相同时才成立，而这件事只有他自己选过任务才体会得到。
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
    """跑完之后，打印用**同一个任务**换个模式跑的完整命令。

    消融对比只有在任务完全相同时才成立，而手抄一长串任务正是悄悄出错的地方。
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
        if r["hit_cap"]:
            ending = t("summary_capped")
        else:
            ending = str(r["answer"]).replace("\n", " ")[:40]

        print("")
        print(t("summary_mode") + r["mode"])
        print(t("summary_stats", r=r["iterations"], t=r["tool_calls"]))
        print(t("summary_result") + ending)


def _quiet_ctrl_c(exc_type, exc_value, tb):
    """Ctrl+C 是正常操作，不是崩溃 —— 不要甩一屏 traceback 吓人。"""
    if exc_type is KeyboardInterrupt:
        print(t("interrupted"))
        sys.exit(130)
    sys.__excepthook__(exc_type, exc_value, tb)


sys.excepthook = _quiet_ctrl_c


if __name__ == "__main__":

    # 不带参数：把有哪些选项告诉他，而不是闷头替他选一个。
    if len(sys.argv) == 1:
        print_help()
        sys.exit(0)

    mode_arg = sys.argv[1]

    if mode_arg in ("-h", "--help", "help"):
        print_help()
        sys.exit(0)

    # 第二个参数（可选）：你自己的任务，记得用引号包起来。
    if len(sys.argv) > 2:
        task = " ".join(sys.argv[2:])   # 没加引号也兜住：把剩下的都拼回去
    else:
        # 命令行没给任务 → 问他要。没有静默默认值，见 ask_for_task()。
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
        # 先把耗时说在前面，免得他以为程序卡死了。
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
        print_rerun_hint(task, mode_arg)
