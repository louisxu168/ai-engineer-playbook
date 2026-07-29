"""
实验 2-0：本地小模型 —— 看清楚 API 底下到底发生了什么

这是本仓库里**唯一一个不用云端模型**的实验。前面所有实验都是通过
Claude Code / Codex / API 去问一个很大的模型，那些接口很贴心地把
「原始输出」洗干净了才给你。这个实验把那层洗掉的东西拿回来。

在一台 M 系列 Mac 上跑一个 **0.6B（六亿参数）** 的模型，你会亲眼看到：

    1. **原始 token 流** —— 包括 <think> 思考标签、特殊标记，
       这些在 OpenAI/Anthropic 的 API 里是看不到的
    2. **0.6B 也能调工具** —— 模型大小不是唯一决定因素
    3. **TTFT 和 tokens/s** —— 延迟到底花在哪
    4. **前缀缓存（KV Cache）** —— 改一个字符的系统提示词，
       首 token 延迟会发生什么

    python3 agent.py                 # 打印用法说明
    python3 agent.py raw             # 原始 token 流，一个字符都不解析 ★
    python3 agent.py parsed          # 把 思考/回复/工具调用 拆开
    python3 agent.py react           # 完整 ReAct 循环（含并行工具调用）
    python3 agent.py cache           # 前缀缓存对照实验 ★★
    python3 agent.py all             # 全部跑一遍

⚠️ 这个实验**需要装 Ollama 并下载一个 0.6B 模型**（约 500MB），
   是本仓库唯一有额外安装步骤的实验。不需要独立显卡/CUDA —— Apple Silicon 上 Ollama 会用 Metal，实测 M3 上 113~131 token/s。
   跑不起来时程序会告诉你该敲哪两行命令。

依赖：**只用 Python 标准库**。不装任何 pip 包 —— 因为本实验的重点就是
看清楚底下发生了什么，用 SDK 反而把要看的东西包起来了。

详细讲解见 README.zh-CN.md（中文）/ README.md（英文）。
"""

import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone

from ollama_client import (OllamaNotRunning, ModelMissing, chat_stream,
                           ensure_ready, list_models)


# --------------------------------------------------------------------------
#  可以改的开关（Settings）
# --------------------------------------------------------------------------

LANG = "zh"            # "zh" | "en"

MODEL = "qwen3:0.6b"   # 想试别的就改这里：qwen3:1.7b、llama3.2:1b、gemma3:1b …

MAX_ROUNDS = 4         # ReAct 最多几轮


MODES = ["raw", "parsed", "react", "cache"]


# ==========================================================================
#  第 1 部分：两个工具（都不联网，结果确定）
# ==========================================================================
#
# 用「温哥华现在几点 + 天气怎么样」这个例子，是因为这两件事**互不依赖** ——
# 一个好的模型会在**同一次输出里**把两个工具调用一起发出来，
# 这样 agent 框架就能并行执行。react 模式会让你看到这一点。

CITY_TZ = {
    "vancouver": -7, "温哥华": -7,
    "beijing": 8, "北京": 8,
    "tokyo": 9, "东京": 9,
    "london": 1, "伦敦": 1,
    "new york": -4, "纽约": -4,
}

# 假天气 —— 写死是为了让实验可复现，也为了不联网
CITY_WEATHER = {
    "vancouver": ("小雨", 14), "温哥华": ("小雨", 14),
    "beijing": ("晴", 31), "北京": ("晴", 31),
    "tokyo": ("多云", 27), "东京": ("多云", 27),
    "london": ("阴", 18), "伦敦": ("阴", 18),
    "new york": ("晴", 26), "纽约": ("晴", 26),
}


def _norm(city):
    return str(city).strip().lower()


def tool_get_time(args):
    city = _norm(args.get("city", ""))
    if city not in CITY_TZ:
        return {"error": "unknown city: " + str(args.get("city"))}
    now = datetime.now(timezone(timedelta(hours=CITY_TZ[city])))
    return {"city": args.get("city"), "time": now.strftime("%Y-%m-%d %H:%M")}


def tool_get_weather(args):
    city = _norm(args.get("city", ""))
    if city not in CITY_WEATHER:
        return {"error": "unknown city: " + str(args.get("city"))}
    condition, celsius = CITY_WEATHER[city]
    return {"city": args.get("city"), "weather": condition, "celsius": celsius}


TOOLS = {"get_time": tool_get_time, "get_weather": tool_get_weather}


# --------------------------------------------------------------------------
#  文字（中英双语）
# --------------------------------------------------------------------------

TEXT = {
    "zh": {
        # ★ 故意用「文本协议」而不是 Ollama 原生的 tools 参数 ——
        #   因为本实验就是要**看见**工具调用长什么样。
        #   用原生 tools 的话，这段格式会被服务端解析掉，你就看不到了。
        "sys": """你是一个助手，可以使用下面两个工具：

get_time(city)      查一个城市现在几点
get_weather(city)   查一个城市的天气

需要调用工具时，输出一行（可以输出多行来一次调用多个工具）：
TOOL: {"name": "get_time", "args": {"city": "Vancouver"}}

不需要调用工具、可以直接回答时，就正常说话。""",
        "sys_variant": """你是一名助手，可以使用下面两个工具：

get_time(city)      查一个城市现在几点
get_weather(city)   查一个城市的天气

需要调用工具时，输出一行（可以输出多行来一次调用多个工具）：
TOOL: {"name": "get_time", "args": {"city": "Vancouver"}}

不需要调用工具、可以直接回答时，就正常说话。""",
        "question": "温哥华现在几点？天气怎么样？",

        "no_ollama_title": "✗ 连不上 Ollama（这个实验需要一个本地模型）",
        "no_ollama_help": """
这是本仓库**唯一**需要额外安装的实验。两步，大约 5 分钟：

  1. 装 Ollama
       macOS:  brew install ollama
       其他:   https://ollama.com/download

  2. 起服务 + 下模型（约 500MB，只需一次）
       ollama serve          # 另开一个终端窗口让它一直跑
       ollama pull {model}

  装好后回到这个目录再跑一次。

⚠️ 不需要独立显卡/CUDA。Apple Silicon 上会走 Metal，实测 M3 上 113~131 token/s。
   不想装的话，本章其他三个实验（2-1/2-2/2-3）都不需要它。
""",
        "no_model_title": "✗ Ollama 在跑，但没有这个模型：{model}",
        "no_model_help": """
下一行就能装（约 500MB，只需一次）：

    ollama pull {model}

你本地现在有的模型：{have}

也可以改本文件开头的 MODEL，换成你已经有的那个。
""",
        "model_line": "模型：{model}   （本地运行，不联网，不花钱）",
        "question_line": "问题：{q}",

        "mode_head": "  模式：{mode}",
        "mode_desc": "  {desc}",
        "desc_raw": "原始 token 流 —— 模型吐什么就打什么，一个字符都不解析",
        "desc_parsed": "把同一段输出拆成：思考 / 给用户的话 / 工具调用",
        "desc_react": "完整 ReAct 循环：思考 → 调工具 → 把结果喂回去 → 再想",
        "desc_cache": "前缀缓存对照：同样的系统提示词跑两次，再改一个字重跑",

        "raw_head": "  ┌─ 模型吐出来的原始文本（未经任何处理）───────────",
        "raw_foot": "  └──────────────────────────────────────────────",
        "raw_note": """
  ★ 看那个 [thinking] / [content] 标签 —— **那条线不是模型划的，是 Ollama 划的。**
    模型吐出来的本来是一整段带 <think>…</think> 的文本，
    Ollama 在服务端把标签剥掉、拆成两个字段才发给你。

    也就是说：**「API 把原始输出洗干净」这件事，本地部署一样会发生**，
    只是洗它的从云厂商变成了你自己机器上的那个进程。
    想真正看到 <think> 三个字符，得绕过模板层 —— README 第 2 节讲了我怎么试的、
    以及为什么最后没成。""",
        "stats": "  TTFT {ttft} ms   ·   生成 {tokens} token   ·   {tps} token/s   ·   输入 {ptok} token",
        "prefill": "  预填充（处理输入）耗时：{ms} ms   ← 前缀缓存主要影响这个数",

        "seg_think": "  ┌─ ① 内部思考（<think> 标签里的东西）",
        "seg_reply": "  ┌─ ② 给用户看的话",
        "seg_tools": "  ┌─ ③ 工具调用请求",
        "seg_none": "  │ （这一段是空的）",
        "seg_foot": "  └──────────────────────────────────────────────",
        "seg_note": """
  ★ 注意这三段的**顺序**：先思考，再说话，最后发工具调用。
    这个顺序是固定的，也是流式 UI 能做出「思考中…」状态的原因 ——
    你一看到 <think> 就切状态，一看到第一个完整的工具调用就可以开始执行，
    **不用等模型把话说完**。""",

        "round_line": "  ── 第 {n} 轮 ──",
        "tool_call": "  [调用] {name}({args})",
        "tool_result": "     → {result}",
        "parallel_note": "  ★ 这一轮它一次发了 {n} 个工具调用 —— 两件事互不依赖，可以并行执行",
        "final_answer": "  [最终回答] {text}",
        "no_tool_round": "  （这一轮没有工具调用，视为最终回答）",

        "cache_head": "  ─── 预填充耗时对照（约 2000 token 的长系统提示词）───",
        "cache_base": "你是一个助手。",
        "cache_rule": "规则 {n}：处理请求时请保持简洁、准确，并优先使用工具获取实时信息。",
        "cache_id_prefix": "会话 ID：REQ-{n}-XYZ",
        "cache_stat2": "     {label:<26} 输入 {ptok} token   预填充 {prefill} ms   TTFT {ttft} ms",
        "cache_warmup": "预热（先跑一次）",
        "cache_nth": "第 {n} 次",
        "cache_group_warm": "  A. 完全固定的系统提示词，连跑 3 次",
        "cache_group_head": "  B. 每次在【开头】塞一个从没出现过的会话 ID",
        "cache_group_tail": "  C. 每次在【结尾】塞一个从没出现过的会话 ID",
        "cache_summary": """
  预填充耗时汇总（毫秒）：

    A 固定前缀          平均 {warm}
    B ID 在开头          第 1 次 {head_first}   之后平均 {head_rest}
    C ID 在结尾          第 1 次 {tail_first}   之后平均 {tail_rest}""",
        "cache_verdict": """
  ⚠️ **这个实验我没能复现书上的说法，如实告诉你。**

  书上（和几乎所有讲 KV Cache 的文章）说：改动系统提示词**开头**会让前缀缓存失效，
  所以 B 应该明显比 C 慢。**实测 B 和 C 没有稳定差别** ——
  两组都是「第一次很慢、之后就快了」，和 ID 放在开头还是结尾无关。

  **唯一稳定复现的效应是这个：**

      模型冷加载后的第一次调用   ≈ 1000 ms 量级
      之后的每一次调用           ≈ 10~40 ms 量级

  差了大约**两个数量级**，而且每次都能复现。

  ★ 那书上说错了吗？不一定。更可能是：
    1. Ollama / llama.cpp 会**同时缓存多个前缀**，所以你交替用两个提示词时，
       两个都在缓存里，看不出失效
    2. `prompt_eval_duration` 这个数字在这个版本上**是否真实反映重算量**，我无法确认
    3. 效应可能要在更长的上下文、更大的模型、或 vLLM 那类推理栈上才显现

  ★ 但下面这条结论是**站得住**的，而且它才是上下文工程的真正理由：

      **2050 token 的输入，冷启动预填充要 1 秒。**
      输入越长，这个数越大 —— 而它是**每次请求都要付**的（缓存没命中的话）。

    这就是实验 2-1（上下文压缩）存在的原因。

  💡 想自己往下挖？README 的练习 4 给了几个方向。
    **如果你复现出了「开头 vs 结尾」的差别，那是个真发现，值得记下来。**""",

        "summary_title": "小结",
        "summary_verify": """
这个实验和本仓库其他实验最大的不同：**它让你看到了平时看不到的东西。**

  · <think> 标签       —— 云端 API 通常把它剥掉或单独放一个字段
  · TOOL: {...} 那一行 —— 用原生 tools 参数的话，它会被服务端解析掉
  · TTFT / 预填充耗时  —— 这是「延迟花在哪」的唯一直接证据
  · 0.6B 也能调对工具  —— 模型大小不是唯一决定因素

★ 而下一个实验（2-1 上下文压缩）要解决的问题，根子就在这里：
  **输入越长，预填充越慢、越贵。** 你在这里量到的那个数，
  就是上下文工程为什么值得做的原因。""",

        "unknown_mode": "✗ 不认识的模式：",
        "exp_header": "# {i}/{total}：{mode}",
        "help": """
======================================================================
 实验 2-0：本地小模型 —— 看清楚 API 底下到底发生了什么
======================================================================

本仓库唯一一个**不用云端模型**的实验。在你自己的机器上跑一个 0.6B 的模型，
看见那些被 API 洗掉的东西。

用法：
    python3 agent.py <模式>

【四种模式】
    raw       原始 token 流，一个字符都不解析 ★
              —— 你会看到 <think> 标签和 TOOL: 那一行长什么样
    parsed    把同一段输出拆成 思考 / 回复 / 工具调用 三段
    react     完整 ReAct 循环，含并行工具调用
    cache     前缀缓存对照实验：同样的提示词 ×2，再改一个字 ★★

    all       全部跑一遍

【前置条件】这是本仓库唯一需要额外安装的实验：

    brew install ollama          # 或 https://ollama.com/download
    ollama serve                 # 另开一个终端让它一直跑
    ollama pull qwen3:0.6b       # 约 500MB，只需一次

⚠️ 不需要独立显卡/CUDA。Apple Silicon 上会走 Metal，实测 M3 上 113~131 token/s。

【Python 依赖】没有。只用标准库 —— 因为本实验的重点就是看清底层，
用 SDK 反而会把要看的东西包起来。

把文件开头的 LANG 改成 "en" 可切换成英文输出。
MODEL 可以换成 qwen3:1.7b 等，对比大一点的模型强多少。
详细讲解见 README.zh-CN.md。
""",
    },
    "en": {
        "sys": """You are an assistant with access to two tools:

get_time(city)      look up the current time in a city
get_weather(city)   look up the weather in a city

To call a tool, output a line like this (several lines = several calls at once):
TOOL: {"name": "get_time", "args": {"city": "Vancouver"}}

If no tool is needed, just answer normally.""",
        "sys_variant": """You are an AI assistant with access to two tools:

get_time(city)      look up the current time in a city
get_weather(city)   look up the weather in a city

To call a tool, output a line like this (several lines = several calls at once):
TOOL: {"name": "get_time", "args": {"city": "Vancouver"}}

If no tool is needed, just answer normally.""",
        "question": "What time is it in Vancouver, and what's the weather like?",

        "no_ollama_title": "x Can't reach Ollama (this lab needs a local model)",
        "no_ollama_help": """
This is the **only** lab in this repo that needs an extra install. Two steps, ~5 min:

  1. Install Ollama
       macOS:  brew install ollama
       other:  https://ollama.com/download

  2. Start it and pull the model (~500MB, one time)
       ollama serve          # leave this running in another terminal
       ollama pull {model}

  Then come back to this folder and run again.

⚠️ No discrete GPU / CUDA required. On Apple silicon Ollama uses Metal; measured 113-131 tok/s on an M3.
   If you'd rather not install it, the other three labs in this chapter
   (2-1 / 2-2 / 2-3) don't need it.
""",
        "no_model_title": "x Ollama is running but doesn't have this model: {model}",
        "no_model_help": """
One command (~500MB, one time):

    ollama pull {model}

Models you currently have: {have}

Or change MODEL at the top of this file to one you already have.
""",
        "model_line": "Model: {model}   (running locally, no network, no cost)",
        "question_line": "Question: {q}",

        "mode_head": "  Mode: {mode}",
        "mode_desc": "  {desc}",
        "desc_raw": "the raw token stream - printed exactly as emitted, nothing parsed",
        "desc_parsed": "the same output split into: thinking / reply / tool calls",
        "desc_react": "a full ReAct loop: think -> call tools -> feed results back -> think again",
        "desc_cache": "prefix-cache comparison: same system prompt twice, then change one character",

        "raw_head": "  +- raw text emitted by the model (completely unprocessed) ------",
        "raw_foot": "  +--------------------------------------------------------------",
        "raw_note": """
  * Look at the [thinking] / [content] labels - **that line was drawn by Ollama,
    not by the model.** The model emits one continuous span wrapped in
    <think>...</think>; Ollama strips the tags server-side and splits it into two
    fields before you ever see it.

    Which means: **"the API washes the raw output" happens with local deployment
    too** - the only change is that the thing washing it is now a process on your
    own machine. To actually see the literal <think> characters you have to bypass
    the template layer; README section 2 documents how I tried and why it failed.""",
        "stats": "  TTFT {ttft} ms   ·   {tokens} tokens generated   ·   {tps} tok/s   ·   {ptok} input tokens",
        "prefill": "  prefill (processing the input): {ms} ms   <- this is what the prefix cache mainly affects",

        "seg_think": "  +- (1) internal thinking (inside the <think> tags)",
        "seg_reply": "  +- (2) the part meant for the user",
        "seg_tools": "  +- (3) tool call requests",
        "seg_none": "  | (this segment is empty)",
        "seg_foot": "  +--------------------------------------------------------------",
        "seg_note": """
  * Note the ORDER of those three: think first, then speak, then call tools.
    That order is fixed, and it's why a streaming UI can show a "thinking..."
    state: switch state the moment <think> appears, and start executing the
    moment the first complete tool call is parsed - **without waiting for the
    model to finish talking.**""",

        "round_line": "  -- round {n} --",
        "tool_call": "  [call] {name}({args})",
        "tool_result": "     -> {result}",
        "parallel_note": "  * it emitted {n} tool calls at once - the two are independent, so they can run in parallel",
        "final_answer": "  [final answer] {text}",
        "no_tool_round": "  (no tool calls this round - treating it as the final answer)",

        "cache_head": "  --- prefill timing comparison (~2000-token system prompt) ---",
        "cache_base": "You are a helpful assistant.",
        "cache_rule": "Rule {n}: keep responses concise and accurate, and prefer tools for live information.",
        "cache_id_prefix": "Session ID: REQ-{n}-XYZ",
        "cache_stat2": "     {label:<30} {ptok} input tokens   prefill {prefill} ms   TTFT {ttft} ms",
        "cache_warmup": "warm-up (one run first)",
        "cache_nth": "run {n}",
        "cache_group_warm": "  A. completely fixed system prompt, 3 runs",
        "cache_group_head": "  B. a never-seen session ID injected at the START each time",
        "cache_group_tail": "  C. a never-seen session ID injected at the END each time",
        "cache_summary": """
  Prefill timings (ms):

    A fixed prefix         mean {warm}
    B ID at the start      run 1 {head_first}   mean of the rest {head_rest}
    C ID at the end        run 1 {tail_first}   mean of the rest {tail_rest}""",
        "cache_verdict": """
  ⚠️ **I could not reproduce the textbook claim here, and I'm telling you so.**

  The book (and nearly every article on KV caching) says: changing the START of a
  system prompt invalidates the prefix cache, so B should be clearly slower than C.
  **Measured, B and C show no stable difference** - both are "slow the first time,
  fast afterwards", regardless of whether the ID sits at the start or the end.

  **The one effect that reproduces every time is this:**

      first call after the model is cold-loaded   ~1000 ms
      every call after that                       ~10-40 ms

  About **two orders of magnitude**, reliably.

  * Is the book wrong? Not necessarily. More likely:
    1. Ollama / llama.cpp caches **several prefixes at once**, so alternating
       between two prompts keeps both cached and hides the invalidation
    2. Whether `prompt_eval_duration` faithfully reflects recomputation on this
       version, I cannot confirm
    3. The effect may need longer contexts, bigger models, or a stack like vLLM

  * But this conclusion **does hold**, and it's the real case for context engineering:

      **A 2050-token input costs ~1 second of prefill when cold.**
      The longer the input, the bigger that number - and you pay it on every
      request that misses the cache.

    That is why lab 2-1 (context compaction) exists.

  💡 Want to dig further? README exercise 4 suggests directions.
    **If you do reproduce a start-vs-end difference, that's a real finding - write it down.**""",

        "summary_title": "Summary",
        "summary_verify": """
What makes this lab different from every other one here: **it shows you things you
normally can't see.**

  · the <think> tags     - cloud APIs usually strip them or move them to a separate field
  · the TOOL: {...} line - with a native tools parameter, the server parses this away
  · TTFT / prefill time  - the only direct evidence of where latency actually goes
  · a 0.6B model calling tools correctly - size is not the only thing that matters

* And the problem the next lab (2-1, context compaction) exists to solve is rooted
  right here: **longer input means slower and pricier prefill.** The number you
  just measured is why context engineering is worth doing at all.""",

        "unknown_mode": "x unknown mode: ",
        "exp_header": "# {i}/{total}: {mode}",
        "help": """
======================================================================
 Lab 2-0: A local small model - seeing what's under the API
======================================================================

The only lab here that uses **no cloud model**. Run a 0.6B model on your own
machine and see what the APIs wash away.

Usage:
    python3 agent.py <mode>

THE FOUR MODES
    raw       the raw token stream, nothing parsed  <-
              you'll see what <think> tags and the TOOL: line actually look like
    parsed    the same output split into thinking / reply / tool calls
    react     a full ReAct loop, including parallel tool calls
    cache     prefix-cache comparison: same prompt x2, then change one char  <-<-

    all       run everything

PREREQUISITE - the only lab here that needs an extra install:

    brew install ollama          # or https://ollama.com/download
    ollama serve                 # leave running in another terminal
    ollama pull qwen3:0.6b       # ~500MB, one time

⚠️ No discrete GPU / CUDA needed. Apple silicon uses Metal; measured 113-131 tok/s on an M3.

PYTHON DEPENDENCIES: none. Standard library only - an SDK would wrap up
exactly the things this lab exists to show you.

Set LANG = "zh" at the top for Chinese output.
Change MODEL to qwen3:1.7b etc. to compare against a bigger model.
Full walkthrough: README.md
""",
    },
}


def t(key, **kwargs):
    template = TEXT[LANG][key]
    return template.format(**kwargs) if kwargs else template


# ==========================================================================
#  第 2 部分：解析原始输出  ★ 这是 raw 和 parsed 的全部差别 ★
# ==========================================================================
#
# 模型吐出来的是**一整段文本**。所谓「思考 / 回复 / 工具调用」这三段，
# 不是模型分三个字段给你的 —— 是**我们自己用字符串处理切出来的**。
#
# 云端 API 之所以能给你结构化的字段，也是在服务端做了同样的事。
# 这一节让你看清楚：那层「结构」是后加的，底下就是一串 token。


THINK_RE = re.compile(r"<think>(.*?)</think>", re.S)
TOOL_RE = re.compile(r"^\s*TOOL:\s*(\{.*\})\s*$", re.M)


def split_output(text):
    """把原始输出切成 (思考, 给用户的话, 工具调用列表)。"""
    think_parts = THINK_RE.findall(text)
    thinking = "\n".join(x.strip() for x in think_parts).strip()

    # 去掉 <think> 段和未闭合的残留
    rest = THINK_RE.sub("", text)
    rest = re.sub(r"<think>.*", "", rest, flags=re.S)

    calls = []
    for match in TOOL_RE.findall(rest):
        try:
            one = json.loads(match)
        except json.JSONDecodeError:
            continue
        if isinstance(one, dict) and one.get("name"):
            calls.append(one)

    reply = TOOL_RE.sub("", rest).strip()
    return thinking, reply, calls


# ==========================================================================
#  第 3 部分：四种模式（Part 3）
# ==========================================================================


def _fmt(value, digits=0):
    if value is None:
        return "?"
    return ("%." + str(digits) + "f") % value


def print_stats(result):
    print("")
    print(t("stats", ttft=_fmt(result["ttft_ms"]), tokens=result["tokens"],
            tps=_fmt(result["tps"], 1), ptok=result["prompt_tokens"]))
    if result["prefill_ms"] is not None:
        print(t("prefill", ms=_fmt(result["prefill_ms"])))


def run_raw():
    """★ 尽可能接近「原始」地打印模型输出，并**标出每段来自哪个字段**。

    ⚠️ 这里有个重要的事实（README 第 2 节详细讲）：
       你其实**拿不到**真正的原始 token 流。Qwen3 生成的是
       `<think>…</think>` 包着的一整段文本，但 **Ollama 在服务端就把它解析掉了**，
       拆成 `thinking` 和 `content` 两个字段才发给你。

       所以下面打印的是「Ollama 解析之后、你能拿到的最原始形态」，
       并且用 [thinking] / [content] 标出了那条被服务端划下的线。

       **「API 会把原始输出洗干净」这件事，本地部署也不例外** ——
       只是洗它的人从云厂商变成了你自己机器上的 Ollama。
    """
    messages = [{"role": "system", "content": t("sys")},
                {"role": "user", "content": t("question")}]

    print("")
    print(t("raw_head"))

    state = {"field": None}

    def on_token(field, piece):
        if field != state["field"]:
            # 换字段了，起一行新的并标注来源
            print("")
            print("  │ [" + field + "] ", end="", flush=True)
            state["field"] = field
        sys.stdout.write(piece.replace("\n", "\n  │ "))
        sys.stdout.flush()

    result = chat_stream(MODEL, messages, on_token=on_token, think=True)
    print("")
    print(t("raw_foot"))
    print(t("raw_note"))
    print_stats(result)
    return result


def run_parsed():
    """同一段输出，切成三段给你看。"""
    messages = [{"role": "system", "content": t("sys")},
                {"role": "user", "content": t("question")}]
    result = chat_stream(MODEL, messages, think=True)
    # thinking 来自 Ollama 的字段；工具调用还得我们自己从 content 里切
    _inline_think, reply, calls = split_output(result["text"])
    thinking = (result.get("thinking") or _inline_think).strip()

    print("")
    for head, body in [(t("seg_think"), thinking), (t("seg_reply"), reply)]:
        print(head)
        if body:
            for line in body.split("\n"):
                print("  │ " + line)
        else:
            print(t("seg_none"))
        print(t("seg_foot"))

    print(t("seg_tools"))
    if calls:
        for one in calls:
            print("  │ " + json.dumps(one, ensure_ascii=False))
    else:
        print(t("seg_none"))
    print(t("seg_foot"))
    print(t("seg_note"))
    print_stats(result)
    return result


def run_react():
    """完整的 ReAct 循环 —— 和实验 1-1 是同一个循环，只是模型换成了本地的。"""
    messages = [{"role": "system", "content": t("sys")},
                {"role": "user", "content": t("question")}]

    for round_number in range(1, MAX_ROUNDS + 1):
        print("")
        print(t("round_line", n=round_number))
        result = chat_stream(MODEL, messages)
        thinking, reply, calls = split_output(result["text"])

        if thinking:
            print("  [think] " + thinking.replace("\n", " ")[:120])

        if not calls:
            print(t("no_tool_round"))
            print(t("final_answer", text=(reply or result["text"]).strip()[:400]))
            print_stats(result)
            return result

        if len(calls) > 1:
            print(t("parallel_note", n=len(calls)))

        messages.append({"role": "assistant", "content": result["text"]})

        for one in calls:
            name = one.get("name")
            args = one.get("args", {}) or {}
            print(t("tool_call", name=name,
                    args=json.dumps(args, ensure_ascii=False)))
            if name in TOOLS:
                out = TOOLS[name](args)
            else:
                out = {"error": "no such tool: " + str(name)}
            print(t("tool_result", result=json.dumps(out, ensure_ascii=False)))
            messages.append({"role": "user",
                             "content": "TOOL_RESULT " + name + ": "
                                        + json.dumps(out, ensure_ascii=False)})

    print_stats(result)
    return result


def run_cache():
    """★★ 预填充耗时对照 —— 一个**部分没能复现**的实验。

    书上说：改掉系统提示词的开头，前缀缓存失效，首 token 会明显变慢。
    我用下面这个测法试了很多次，**没能稳定复现那个现象**（详见 SOLUTION）。

    所以这个模式现在做的是一件更诚实的事：**把四组数字都量出来摆在你面前**，
    让你自己判断哪个效应真的存在。

    量的是 `prompt_eval_duration`（预填充耗时）—— 处理【输入】花的时间，
    和生成速度无关。上下文越长，这个数越大。
    """
    # ★ 用一个约 2000 token 的长系统提示词。
    #   之前用 110 token 的短提示词时，预填充只有 10ms 左右，
    #   **完全淹没在噪声里** —— 这本身就是一课：
    #   要测一个效应，先确认它大到能被测出来。
    filler = "\n".join(
        t("cache_rule", n=i) for i in range(1, 220))
    stable = t("cache_base") + "\n" + filler

    def one(system_prompt, label):
        messages = [{"role": "system", "content": system_prompt},
                    {"role": "user", "content": t("question")}]
        result = chat_stream(MODEL, messages,
                             options={"num_predict": 8}, think=False)
        print(t("cache_stat2", label=label,
                ptok=result["prompt_tokens"],
                prefill=_fmt(result["prefill_ms"], 1),
                ttft=_fmt(result["ttft_ms"], 1)))
        return result["prefill_ms"] or 0.0

    print("")
    print(t("cache_head"))

    print("")
    print(t("cache_group_warm"))
    one(stable, t("cache_warmup"))
    warm = [one(stable, t("cache_nth", n=i + 1)) for i in range(3)]

    print("")
    print(t("cache_group_head"))
    head = [one(t("cache_id_prefix", n=9000 + i) + "\n" + stable,
                t("cache_nth", n=i + 1)) for i in range(3)]

    print("")
    print(t("cache_group_tail"))
    tail = [one(stable + "\n" + t("cache_id_prefix", n=9100 + i),
                t("cache_nth", n=i + 1)) for i in range(3)]

    def avg(xs):
        return sum(xs) / max(1, len(xs))

    print("")
    print(t("cache_summary",
            warm=_fmt(avg(warm), 1),
            head_first=_fmt(head[0], 1), head_rest=_fmt(avg(head[1:]), 1),
            tail_first=_fmt(tail[0], 1), tail_rest=_fmt(avg(tail[1:]), 1)))
    print(t("cache_verdict"))
    return {"warm": warm, "head": head, "tail": tail}


RUNNERS = {"raw": run_raw, "parsed": run_parsed,
           "react": run_react, "cache": run_cache}

DESCS = {"raw": "desc_raw", "parsed": "desc_parsed",
         "react": "desc_react", "cache": "desc_cache"}


# ==========================================================================
#  第 4 部分：命令行入口（Part 4）
# ==========================================================================


def _quiet_ctrl_c(exc_type, exc_value, tb):
    if exc_type is KeyboardInterrupt:
        print("")
        sys.exit(130)
    sys.__excepthook__(exc_type, exc_value, tb)


sys.excepthook = _quiet_ctrl_c


def preflight():
    """检查 Ollama 和模型在不在。不在就给出准确的安装指引。"""
    try:
        ensure_ready(MODEL)
    except OllamaNotRunning:
        print("")
        print(t("no_ollama_title"))
        print(t("no_ollama_help", model=MODEL))
        sys.exit(1)
    except ModelMissing:
        have = ", ".join(list_models()) or "(无)"
        print("")
        print(t("no_model_title", model=MODEL))
        print(t("no_model_help", model=MODEL, have=have))
        sys.exit(1)


if __name__ == "__main__":

    if len(sys.argv) == 1:
        print(t("help"))
        sys.exit(0)

    mode_arg = sys.argv[1]
    if mode_arg in ("-h", "--help", "help"):
        print(t("help"))
        sys.exit(0)

    if mode_arg not in MODES and mode_arg != "all":
        print("")
        print(t("unknown_mode") + mode_arg)
        print(t("help"))
        sys.exit(1)

    preflight()

    print(t("model_line", model=MODEL))
    print(t("question_line", q=t("question")))

    todo = MODES if mode_arg == "all" else [mode_arg]
    for i in range(len(todo)):
        m = todo[i]
        print("")
        print("=" * 70)
        if len(todo) > 1:
            print(t("exp_header", i=i + 1, total=len(todo), mode=m))
        print(t("mode_head", mode=m))
        print(t("mode_desc", desc=t(DESCS[m])))
        print("=" * 70)
        RUNNERS[m]()

    if mode_arg == "all":
        print("")
        print("=" * 70)
        print(t("summary_title"))
        print("=" * 70)
        print(t("summary_verify"))
