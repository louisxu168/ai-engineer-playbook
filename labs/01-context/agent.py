"""
实验 1-1：上下文消融（Context Ablation）

===============================================================================
 一句话原理
===============================================================================

    Agent = LLM + 上下文 + 工具，套在一个 while 循环里。

LLM 是个纯函数：给它一段文本，它返回一段文本。它没有记忆，也不能执行任何东西。

它唯一能做的事，是输出一段 JSON 说「我想调 search_products('keyboard')」。
真正去跑这个函数的是**你的 Python 代码**，跑完你再把结果拼回文本里，重新问它一遍。
一直循环，直到它不再要求调工具、而是直接给答案为止。

所以：**模型是个会说 JSON 的规划器，你是它的手。**

===============================================================================
 这个文件怎么读
===============================================================================

按下面的顺序，从上往下读就行，每一部分都有大标题：

    第 1 部分   工具        —— 就是三个普通的 Python 函数
    第 2 部分   系统提示词  —— 告诉模型「你有哪些工具、该怎么回话」
    第 3 部分   拼上下文    ★ 五种消融全在这里，是整个实验的核心
    第 4 部分   执行工具    —— 模型点名要调哪个，我们就跑哪个
    第 5 部分   主循环      —— 把上面四块串起来
    第 6 部分   命令行入口  —— 处理 `python agent.py xxx` 的参数

旁边还有个 `llm.py`，那是「怎么调用大模型」的适配层。**第一次读可以完全跳过它**，
你只需要知道它提供了一个函数 `complete(提示词, 系统提示词)`，返回模型的回复文本。

===============================================================================
 怎么跑
===============================================================================

    python3 agent.py                 # ← 不带参数会打印完整用法说明，先跑这个
    python3 agent.py full            # 跑「基线」这一个实验（约 30 秒）
    python3 agent.py no_history      # 跑「删掉历史」这一个实验
    python3 agent.py all             # ⚠️ 把 5 个实验挨个跑一遍（约 3~8 分钟）

注意 `all` 不是第六种模式，它是「批量跑上面全部 5 个模式」的意思。
跑的时候屏幕上会连着出现 5 段输出、轮数各自从 1 重新开始 —— 那不是死循环。

不需要 API key —— 默认会用你已经装好的 Claude Code 或 Codex。
"""

import json     # 用来把 Python 的字典 <-> JSON 文本 互相转换
import sys      # 用来读命令行参数，比如 `python agent.py full` 里的 "full"
import time     # 用来给每次模型调用计时，好让你知道程序没卡死

# 从隔壁的 llm.py 里借三个函数来用
from llm import complete            # complete(提示词, 系统提示词) -> 模型回复的文本
from llm import detect_backend      # 自动判断该用 claude 还是 codex 还是 API
from llm import parse_json_reply    # 把模型回复的文本里那段 JSON 抠成 Python 字典


# ★★★ 想亲眼看看「上下文」到底长什么样？把下面这行改成 True，再跑一次。★★★
# 它会在每一轮把发给模型的完整文本打印出来。强烈建议至少开一次。
SHOW_PROMPT = True


# 这个实验的五种模式。后面到处都会用到这个列表。
MODES = [
    "full",              # 完整上下文（基线，什么都不删）
    "no_history",        # 删掉历史，只留最近一步
    "no_reasoning",      # 删掉模型自己的思考过程
    "no_tool_calls",     # 压根不给它工具
    "no_tool_results",   # 工具照调，但不给它看返回值
]

# 每个模式一句话说明，打印帮助的时候用。
MODE_HELP = {
    "full":            "完整上下文 —— 基线，先跑这个",
    "no_history":      "删掉历史，只留最近一步",
    "no_reasoning":    "删掉模型自己的思考过程（reasoning 字段）",
    "no_tool_calls":   "压根不告诉它有工具",
    "no_tool_results": "工具照调，但不给它看返回值",
}


# =============================================================================
#  第 1 部分：工具
# =============================================================================
#
# 「工具」听起来很高级，其实就是普通的 Python 函数，没有任何特殊之处。
#
# 关键点：**模型执行不了这些函数**。它只能说出函数名和参数，
# 由我们（第 4 部分）去调用。
#
# 每个工具都返回一个字典（dict），成功和失败都返回字典 —— 这样第 4 部分
# 可以统一处理，不用管是哪个工具。

# 假装这是个商品数据库。真实项目里这里会是一次数据库查询或者 HTTP 请求。
CATALOG = {
    "mechanical keyboard": {"name": "Keychron Q1 Pro", "usd": 199.0},
    "wireless mouse": {"name": "Logitech MX Master 4", "usd": 119.0},
    "monitor": {"name": "Dell U2723QE 27寸 4K", "usd": 579.0},
}

# 假装这是实时汇率表。数字的含义是「1 美元 = 多少这个货币」。
RATES = {
    "USD": 1.0,
    "CNY": 7.24,
    "EUR": 0.92,
    "JPY": 149.50,
}


def search_products(keyword):
    """工具 1：按关键词查商品，返回商品名和美元单价。"""

    # .strip() 去掉首尾空格，.lower() 转成小写 —— 这样 " Mechanical Keyboard "
    # 也能匹配上字典里的 "mechanical keyboard"。
    clean_keyword = str(keyword).strip().lower()

    # 字典的 .get() 方法：找得到就返回值，找不到返回 None（而不是报错）。
    product = CATALOG.get(clean_keyword)

    if product is None:
        # 注意：出错也返回字典，不要抛异常。
        # 因为这个错误信息会被塞回上下文给模型看，让它自己纠正。
        return {"error": "没找到这个商品；可选关键词：" + str(sorted(CATALOG))}

    return product


def get_rate(from_currency, to_currency):
    """工具 2：查两种货币之间的汇率。"""

    source = str(from_currency).upper()   # 统一转成大写，"usd" -> "USD"
    target = str(to_currency).upper()

    if source not in RATES:
        return {"error": "不支持的货币 " + source + "；可选：" + str(sorted(RATES))}
    if target not in RATES:
        return {"error": "不支持的货币 " + target + "；可选：" + str(sorted(RATES))}

    rate = RATES[target] / RATES[source]

    return {"rate": round(rate, 4), "from": source, "to": target}


def calc(expression):
    """工具 3：算一个算术表达式，比如 "199 * 3"。"""

    # eval() 会把一段字符串当成 Python 代码执行。
    # 第二个参数 {"__builtins__": {}} 是在切断它对内置函数的访问，
    # 免得模型传一段危险代码进来（比如删文件）。
    #
    # ⚠️ 真实项目里不要这样用 eval，这里只是为了让实验代码短一点。
    try:
        answer = eval(str(expression), {"__builtins__": {}}, {})
        return {"result": answer}
    except Exception as error:
        # 算错了也返回字典，让模型看到错误信息自己改。
        return {"error": str(error)}


# =============================================================================
#  第 2 部分：系统提示词（System Prompt）
# =============================================================================
#
# 系统提示词就是「给模型的岗位说明书」，每次调用都会发过去。
# 它规定了两件事：你有哪些工具、你该用什么格式回话。
#
# 这里要意识到一件事：**这段文字就是你的程序**。
# 你调教 agent 的主要手段不是写 Python，而是改这段中文。

TOOL_CATALOG = """你可以使用这些工具：
- search_products(keyword)              按关键词查商品，返回名称和美元单价
- get_rate(from_currency, to_currency)  查汇率
- calc(expression)                      算算术表达式，如 "199 * 3"
"""

PROTOCOL = """只输出一个 JSON 对象，不要有别的内容。要么是：
  {"reasoning": "<一句话思路>", "calls": [{"tool": "<工具名>", "args": {...}}]}
要么，当你已经得出完整答案时：
  {"reasoning": "<一句话思路>", "answer": "<答案>"}

注意 calls 是个数组，可以一次放多个工具调用：
  · 如果几个工具**彼此不依赖**（谁都不需要另一个的结果），就一次全放进去，
    它们会被同时执行，这样能少跑好几轮。
  · 如果后一个工具需要前一个的返回值，那就只放前一个，等结果出来下一轮再调。"""

# 这一句只在「有工具」的时候才有意义。
# 如果把它留在 no_tool_calls 模式里，模型会遵守它、然后拒绝作答 ——
# 那你看到的就是「守规矩」的后果，而不是「没工具」的后果，实验就白做了。
# 这是我们第一次跑的时候真踩到的坑，详见 SOLUTION.md。
NO_GUESSING = "绝对不要猜一个本可以用工具查到的数字。"


def build_system_prompt(mode):
    """拼出这一次实验要用的系统提示词。

    ★ 消融点之一：no_tool_calls 模式下，工具清单根本不给模型看。
    """

    # 先准备一个列表，往里放几段文字，最后拼起来。
    parts = []

    parts.append("你是一个一步步解决任务的 agent。")

    if mode == "no_tool_calls":
        # 【消融】不告诉它有任何工具。它只能凭记忆瞎编。
        parts.append("你没有任何工具，只能凭自己的知识回答。")
        parts.append(PROTOCOL)
    else:
        # 正常情况：告诉它有哪些工具，并且叮嘱它不要瞎猜数字。
        parts.append(TOOL_CATALOG)
        parts.append(PROTOCOL + "\n" + NO_GUESSING)

    # "\n\n".join(列表) 的意思是：用两个换行把列表里的每一段连起来。
    return "\n\n".join(parts)


# =============================================================================
#  第 3 部分：拼上下文   ★★★ 整个实验最重要的函数 ★★★
# =============================================================================
#
# 先理解一个反直觉的事实：
#
#     大模型的接口是**无状态**的。服务器那边什么都不存。
#     每问一次，你都得把前面发生过的所有事情，重新完整地发一遍。
#
# 所以「上下文」不是什么玄学，它就是下面这个函数拼出来的一段文本。
# Agent 在第 5 轮「知道」的一切，就是这段文本里写了的东西。没有别的了。
#
# 五种消融里有三种在这个函数里实现，而且每种只改一两行。
# 这就是本实验的核心结论：**上下文工程 = 对这段文本做增删改**。


def pick_visible_steps(steps, mode):
    """决定这一轮让模型看到历史里的哪几步。

    ★ 消融 A：no_history 就在这里 —— 只留最近一步，前面的全丢掉。

    单独抽成一个函数，是因为 run() 打印进度时也要知道「这轮给它看了哪几步」，
    两边共用同一份规则，不会打架。
    """

    if mode == "no_history":
        if len(steps) == 0:
            return []
        # steps[-1] 是列表的最后一项。用中括号包起来，是为了让返回值
        # 仍然是个「列表」，这样调用方的 for 循环写法不用改。
        return [steps[-1]]

    # 其他模式：从头到尾全部给它看。
    return steps


def describe_visible_steps(visible_steps):
    """把「这轮给模型看了哪几步」说成一句人话，用来打印进度。"""

    if len(visible_steps) == 0:
        return "上下文里还没有历史"

    first_number = visible_steps[0]["number"]
    last_number = visible_steps[-1]["number"]

    if first_number == last_number:
        return "上下文只含第 " + str(first_number) + " 步"

    return ("上下文含第 " + str(first_number)
            + "~" + str(last_number) + " 步")


def render_context(task, steps, mode):
    """把「已经走过的每一步」渲染成这一轮要发给模型的提示词。

    ─────────────────────────────────────────────────────────────────
     「轮」和「步」是什么关系？—— 同一个计数器的两个视角
    ─────────────────────────────────────────────────────────────────

        第 N 轮 = 程序视角：主循环的第 N 次迭代，也就是「现在正在问模型」
        第 N 步 = 模型视角：第 N 轮那次问答的结果，已经被记进历史了

    所以第 N 轮发出去的提示词里，装的是第 1 步 ~ 第 N-1 步：

        第 1 轮  →  历史是空的（还没发生过任何事）
        第 2 轮  →  历史里有「第 1 步」
        第 3 轮  →  历史里有「第 1 步」「第 2 步」
        第 4 轮  →  历史里有「第 1、2、3 步」

    一句话：**「轮」是正在发生的，「步」是已经发生的。**
    （no_history 模式除外 —— 那里故意只给它看最后一步。）

    参数：
        task  —— 用户的原始任务，一句话字符串
        steps —— 一个列表，记录走过的每一步。每一项是这样一个字典：
                 {
                     "number":    第几步（整数，等于当时是第几轮）,
                     "assistant": 模型当时的回复（字典）,
                     "results":   这一步调的所有工具及其返回值（列表），
                                  形如 [{"tool": "get_rate", "result": {...}}, ...]
                                  —— 是列表，因为一轮可以并行调多个工具
                 }
        mode  —— 五种模式之一

    返回：一整段字符串，就是要发给模型的提示词。
    """

    # ---- 消融 A：no_history —— 规则在上面的 pick_visible_steps() 里 ----
    visible_steps = pick_visible_steps(steps, mode)

    # ---- 开始拼文本。先准备一个列表装每一行，最后用换行连起来。--------
    lines = []
    lines.append("任务：" + task)
    lines.append("")          # 空一行，让模型看得清楚点

    for step in visible_steps:

        # ---- 消融 B：no_reasoning —— 抹掉模型自己的思考 ----------------
        # dict(...) 是「复制一份字典」。必须复制！
        # 否则下面的删除操作会改坏 steps 里存的原始记录。
        assistant_reply = dict(step["assistant"])

        if mode == "no_reasoning":
            # .pop(键, None) 的意思是：有这个键就删掉，没有也不报错。
            assistant_reply.pop("reasoning", None)

        lines.append("--- 第 " + str(step["number"]) + " 步 ---")

        # json.dumps() 把 Python 字典转成 JSON 文本。
        # ensure_ascii=False 是让中文正常显示，不然会变成 你好 那种。
        lines.append("你的回复：" + json.dumps(assistant_reply, ensure_ascii=False))

        # ---- 消融 C：no_tool_results —— 不给它看工具返回了什么 --------
        #
        # 一轮可能调了好几个工具，所以这里要再套一层循环，把每个结果都拼上。
        # 每行都标上是哪个工具返回的，否则模型分不清哪个结果对应哪个调用。
        for one_result in step["results"]:

            if mode == "no_tool_results":
                result_text = "[结果已隐藏]"
            else:
                # json.dumps() 把 Python 字典转成 JSON 文本。
                # ensure_ascii=False 是让中文正常显示。
                result_text = json.dumps(one_result["result"], ensure_ascii=False)

            lines.append("工具 " + str(one_result["tool"])
                         + " 返回：" + result_text)

        lines.append("")

    lines.append("现在给出你的下一条 JSON 回复。")

    # 用换行符把所有行连成一整段文本
    return "\n".join(lines)


# 小结一下这个函数里的三处消融：
#
#   no_history        删掉除最近一步外的所有历史        → 它会重复做已经做过的事
#   no_reasoning      删掉 reasoning 字段              → 它每轮都要重新想一遍
#   no_tool_results   工具返回值换成 "[结果已隐藏]"     → 它只能瞎编
#
# 第四种（no_tool_calls）在第 2 部分的 build_system_prompt() 里。
#
# 四种加起来，改动量不超过 10 行。**没有一行是在改模型或者改循环。**


# =============================================================================
#  第 4 部分：执行模型点名的工具
# =============================================================================


def extract_tool_calls(reply):
    """从模型回复里取出「这一轮要调哪些工具」，统一成一个列表。

    为什么要单独一个函数？因为模型可能用两种写法回你：

        新写法（可以并行）：{"calls": [{"tool": "a", "args": {}},
                                      {"tool": "b", "args": {}}]}
        老写法（只有一个）：{"tool": "a", "args": {}}

    两种都兜住，后面 run() 里就只需要处理「一个列表」这一种情况，不用到处写 if。
    这在真实项目里叫「归一化」，是很常见的做法 —— 在入口把杂乱的输入
    收拾成统一格式，让核心逻辑保持干净。

    返回：一个列表。没有要调的工具就返回空列表 []。
    """

    calls = reply.get("calls")

    # isinstance(x, list) 的意思是「x 是不是一个列表」。
    # 要检查一下，因为模型有可能把 calls 写成别的东西（比如一个字符串）。
    if isinstance(calls, list) and len(calls) > 0:
        return calls

    # 老写法：顶层直接是 tool + args，包成只有一项的列表返回。
    if reply.get("tool"):
        return [{"tool": reply["tool"], "args": reply.get("args", {})}]

    # 两种都不是 —— 说明它没打算调工具（多半是直接给答案了）。
    return []


def execute_tool(tool_name, tool_args):
    """模型说它想调某个工具，这里真正去调。

    参数：
        tool_name —— 工具名，字符串，比如 "search_products"
        tool_args —— 参数，字典，比如 {"keyword": "mechanical keyboard"}

    返回：工具的返回值（字典）。
    """

    # 这里故意用最笨的 if / elif 写法，一眼就能看懂哪个名字对应哪个函数。
    #
    # 老手通常会写成一个「名字 -> 函数」的字典再配合 **tool_args 解包，
    # 代码更短，但对新手来说不好读，所以这里不用。

    if tool_name == "search_products":
        # .get("keyword") 取参数。模型有可能少传参数，用 .get() 就不会报错。
        return search_products(tool_args.get("keyword"))

    elif tool_name == "get_rate":
        return get_rate(tool_args.get("from_currency"),
                        tool_args.get("to_currency"))

    elif tool_name == "calc":
        return calc(tool_args.get("expression"))

    else:
        # 模型可能会点名一个根本不存在的工具（这在实验里真的会发生！）。
        # 不要让程序崩掉，而是把「没有这个工具」当成一条错误信息还给它，
        # 让它自己换一个。这是真实 agent 必备的容错。
        return {"error": "没有这个工具：" + str(tool_name)}


# =============================================================================
#  第 5 部分：主循环   ← Agent 的心脏，就这么点东西
# =============================================================================


def run(task, mode="full", max_iterations=8, backend=None, verbose=True):
    """跑一次完整的 agent 循环。

    参数：
        task           —— 任务描述
        mode           —— 五种模式之一
        max_iterations —— 最多循环几轮（安全阀，防止无限循环烧钱）
        backend        —— 用哪个后端，None 表示自动探测
        verbose        —— 要不要打印过程

    返回：一个字典，记录这次跑的统计结果。
    """

    steps = []          # 走过的每一步，会不断往里加
    tool_call_count = 0 # 一共调了几次工具

    system_prompt = build_system_prompt(mode)

    # range(1, max_iterations + 1) 会产生 1, 2, 3, ... max_iterations
    for round_number in range(1, max_iterations + 1):

        # ---- 第一步：把目前为止的一切拼成提示词 ----------------------
        prompt = render_context(task, steps, mode)

        if verbose:
            # 顺便把「这一轮的上下文里装了哪几步」打出来 ——
            # 这样「轮」和「步」的关系一眼就能看明白，
            # 而且 no_history 模式的效果会变得非常直观。
            visible = pick_visible_steps(steps, mode)

            print("")
            print("")
            print("═" * 68)
            print("  第 " + str(round_number) + " 轮 / 共 " + str(max_iterations)
                  + " 轮     模式：" + mode)
            print("  " + describe_visible_steps(visible)
                  + "     提示词 " + str(len(prompt)) + " 字符")
            print("═" * 68)

        if SHOW_PROMPT:
            print("")
            print("  ┌─── 实际发给模型的内容 " + "─" * 38)
            # 把提示词的每一行都缩进两格，看起来是「框里的内容」
            for one_line in prompt.split("\n"):
                print("  │ " + one_line)
            print("  └" + "─" * 60)

        # ---- 第二步：问模型 ------------------------------------------
        #
        # 这一行是整个程序里最慢的地方 —— 走 Claude Code / Codex 后端时，
        # 每次大约要等 5～15 秒。所以先打印一句「正在等」，
        # 否则屏幕半天不动，看起来就像卡死了（其实只是在等模型回话）。
        if verbose:
            print("")
            print("  正在问模型…", end="", flush=True)

        start_time = time.time()
        raw_text = complete(prompt, system_prompt, backend=backend)
        elapsed = time.time() - start_time

        if verbose:
            print(" 用了 " + str(round(elapsed, 1)) + " 秒")

        # 模型回的是一段文本，我们期望里面有个 JSON 对象，把它抠出来变成字典
        reply = parse_json_reply(raw_text)

        # ---- 把模型这一轮的「思考」立刻打出来 -------------------------
        #
        # reasoning 是模型**这一轮就返回**的东西，跟工具调用装在同一个 JSON 里。
        # 所以要在工具之前打印，读起来才顺：思考 → 调工具 → 拿结果。
        # （以前没打印它，你只能在下一轮的提示词转储里看到，还埋在一坨 JSON 里，
        #   看着就像「思考」慢了一拍 —— 其实是我没显示。）
        if verbose and reply.get("reasoning"):
            print("")
            print("  [思考] " + str(reply["reasoning"]))

            if mode == "no_reasoning":
                # 消融说明：这句思考确实产生了，只是不会被拼回下一轮的上下文。
                print("         ↑ 但 no_reasoning 模式下，它不会被带进下一轮")

        # ---- 第三步：判断该停了还是该继续 ----------------------------
        #
        # 停止条件有两种：
        #   1. 模型给了 "answer" 字段 —— 它认为做完了
        #   2. 模型没有要求调任何工具 —— 说明它在用大白话回答，也算做完了
        #
        has_answer = "answer" in reply

        # 把回复归一成一个「要调的工具」列表（可能有 0 个、1 个或多个）
        wanted_calls = extract_tool_calls(reply)

        if has_answer or len(wanted_calls) == 0:
            if has_answer:
                answer = reply["answer"]
            else:
                # 连 JSON 都没解析出来，那就把模型的原始文本当答案。
                # （在 no_tool_calls 模式下经常这样 —— 它直接用散文回答了。）
                answer = raw_text.strip()

            if verbose:
                print("")
                print("  [答案] " + str(answer))
                print("")

            return {
                "mode": mode,
                "iterations": round_number,
                "tool_calls": tool_call_count,
                "answer": answer,
                "hit_cap": False,
            }

        # ---- 第四步：模型点名要调工具 —— 我们去执行，把结果记下来 ----
        #
        # 这一轮可能要调好几个工具（模型判断它们互不依赖时会一次全报出来）。
        # 挨个执行，结果攒成一个列表。
        #
        # 注：真实项目里这些独立调用可以用多线程真正**同时**跑，省时间。
        #     这里为了代码好读用了顺序执行 —— 省掉的是「往返模型的次数」，
        #     而那才是大头（每次往返要等模型好几秒，本地函数只要几微秒）。
        results_this_round = []

        if verbose:
            print("")

        for call_index in range(len(wanted_calls)):
            one_call = wanted_calls[call_index]

            tool_name = one_call.get("tool")
            tool_args = one_call.get("args", {})   # 没有 args 就用空字典

            result = execute_tool(tool_name, tool_args)
            tool_call_count = tool_call_count + 1

            if verbose:
                # 只有一个工具就不标编号，有多个才标 1/2、2/2，看得清楚些
                if len(wanted_calls) > 1:
                    label = "[工具 " + str(call_index + 1) + "/" + str(len(wanted_calls)) + "]"
                else:
                    label = "[工具]"

                # 调用和返回值分两行，不然一行太长挤成一团
                print("  " + label + " " + str(tool_name)
                      + "(" + str(tool_args) + ")")
                print("        └→ " + str(result))

            # 把工具名一起存下来。因为一轮可能有多个结果，
            # 模型需要知道哪个结果是哪个工具返回的。
            # （真实 API 里靠 tool_use_id 配对，这里用工具名，道理一样。）
            results_this_round.append({
                "tool": tool_name,
                "result": result,
            })

        if verbose and len(wanted_calls) > 1:
            print("  ↑ 这一轮并行调了 " + str(len(wanted_calls))
                  + " 个工具（模型判断它们互不依赖）")

        # 把这一步存进 steps。下一轮 render_context() 会把它拼回提示词里 ——
        # **这就是 agent 的「记忆」，全部的记忆。**
        steps.append({
            "number": round_number,
            "assistant": reply,
            "results": results_this_round,   # 注意是复数：一轮可能有多个结果
        })

    # 循环跑满了还没给答案（no_history 模式经常这样）
    if verbose:
        print("")
        print("  [上限] 跑满 " + str(max_iterations) + " 轮仍未给出答案")
        print("")

    return {
        "mode": mode,
        "iterations": max_iterations,
        "tool_calls": tool_call_count,
        "answer": None,
        "hit_cap": True,
    }


# =============================================================================
#  第 6 部分：命令行入口
# =============================================================================
#
# 下面这些只是处理 `python agent.py xxx` 的参数，跟 agent 原理没关系，
# 第一次读可以跳过。

TASK = "我想买 3 个 mechanical keyboard，帮我查一下单价，算出总价，并折算成人民币。"


def print_help():
    """打印使用说明。不带参数运行、或者参数写错的时候都会调到这里。"""

    print("")
    print("=" * 70)
    print(" 实验 1-1：上下文消融")
    print("=" * 70)
    print("")
    print("用法：")
    print("    python3 agent.py <模式> [\"自定义任务\"]")
    print("")
    print("【单个模式】跑一次，约 30 秒 ~ 1 分钟：")
    for m in MODES:
        print("    " + m.ljust(18) + MODE_HELP[m])
    print("")
    print("【对比模式】把上面 5 个挨个跑一遍，约 3 ~ 8 分钟：")
    print("    " + "all".ljust(18) + "五种模式全跑，最后打印一张对比表")
    print("")
    print("举例：")
    print("    python3 agent.py full")
    print("    python3 agent.py no_history")
    print("    python3 agent.py all")
    print("    python3 agent.py full \"我想买 2 个 monitor，折算成日元多少钱？\"")
    print("")
    print("建议顺序：")
    print("    1. 先跑 full，建立基线，记住它用了几轮、调了几次工具")
    print("    2. 再一个个跑消融模式 —— 每跑一个之前，先猜结果会怎么变")
    print("    3. 最后跑 all，看那张对比表")
    print("")
    print("想看「上下文」到底长什么样：把文件开头的 SHOW_PROMPT 改成 True。")
    print("（注意：开着它跑 all 会刷屏，建议只在单个模式下开。）")
    print("")


def print_summary(results):
    """把 all 模式的结果打印成一张对比表。"""

    print("")
    print("=" * 70)
    print("对比结果")
    print("=" * 70)

    for r in results:
        if r["hit_cap"]:
            ending = "跑满上限，没给出答案"
        else:
            # 答案可能很长，截断一下，并且把换行去掉免得表格乱掉
            ending = str(r["answer"]).replace("\n", " ")[:40]

        print("")
        print("模式：" + r["mode"])
        print("  轮数：" + str(r["iterations"])
              + "   工具调用：" + str(r["tool_calls"]) + " 次")
        print("  结果：" + ending)


# 这行的意思是「只有直接运行这个文件时才执行下面的代码」。
# 如果是被别的文件 import 进去，下面就不会跑。
if __name__ == "__main__":

    # sys.argv 是命令行参数的列表。
    # 跑 `python agent.py full` 时，sys.argv 就是 ["agent.py", "full"]。
    #
    # 什么都不写的话，与其闷头跑一个模式，不如先把有哪些选项告诉你。
    if len(sys.argv) == 1:
        print_help()
        sys.exit(0)

    mode_arg = sys.argv[1]

    if mode_arg in ("-h", "--help", "help", "帮助"):
        print_help()
        sys.exit(0)

    # 第二个参数（可选）是自定义任务：
    #     python agent.py full "我想买 2 个 monitor，总价多少人民币？"
    # 注意任务要用引号整个包起来，否则 shell 会按空格拆成好多个参数。
    if len(sys.argv) > 2:
        task = " ".join(sys.argv[2:])   # 没加引号也兜住：把剩下的都拼回去
    else:
        task = TASK                     # 不指定就用默认任务

    if mode_arg not in MODES and mode_arg != "all":
        print("")
        print("✗ 不认识的模式：" + mode_arg)
        print_help()
        sys.exit(1)

    backend = detect_backend()
    print("后端：" + backend)
    print("任务：" + task)

    if mode_arg == "all":
        # ---- 先把丑话说在前面，免得你以为程序卡死了 --------------------
        # 5 个模式 × 最多 8 轮 = 最多 40 次模型调用。
        # 走 Claude Code / Codex 后端每次约 5～15 秒，所以整个 all 要跑几分钟。
        print("")
        print("⚠️  all 模式要跑 5 个实验，最多 40 次模型调用，大约需要 3～8 分钟。")
        print("    过程中屏幕会一直有输出，那是正常的，不是死循环。")
        print("    想快很多的话：LAB_BACKEND=api DEEPSEEK_API_KEY=xxx python agent.py all")
        if SHOW_PROMPT:
            print("    另外你把 SHOW_PROMPT 打开了，输出会非常长 ——")
            print("    想看对比表的话，建议先把它改回 False。")
        print("")

        results = []
        for mode_index in range(len(MODES)):
            m = MODES[mode_index]
            print("")
            print("#" * 70)
            print("# 实验 " + str(mode_index + 1) + "/" + str(len(MODES)) + "：" + m)
            print("#" * 70)
            results.append(run(task, mode=m, backend=backend))
        print_summary(results)

    else:
        run(task, mode=mode_arg, backend=backend)
