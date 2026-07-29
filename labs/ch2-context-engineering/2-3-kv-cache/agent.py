"""
实验 2-3：五种常见的错误上下文管理模式

原书实验 2-3 讲了几种「看起来合理、实际有害」的上下文管理写法。
这个实验把它们一个个做出来，然后**量两件事**：

    ① 预填充耗时（prefill）—— 缓存被破坏了吗？
    ② 最终答案对不对   —— 模型的能力被破坏了吗？

★ 关键设计：**历史是程序化构造的，不是让模型生成的。**
  12 条消息（模拟一个 agent 读了 5 个数），写死。
  五种策略对**完全一样**的历史做不同处理，然后问同一个问题：

      「你之前读到的 1 号传感器的读数是多少？」

  正确答案是写死的，所以判分是**机械的**。
  每种策略只花 1~2 次模型调用，跑得很快。

    python3 agent.py                  # 用法说明
    python3 agent.py good             # 标准做法（基线）
    python3 agent.py dynamic_prompt   # 系统提示词开头塞时间戳 ★
    python3 agent.py dynamic_profile  # 系统提示词末尾塞「剩余额度」★★
    python3 agent.py shuffled_tools   # 每次打乱工具顺序
    python3 agent.py sliding_window   # 只保留最近几条 ★★
    python3 agent.py flattened        # 拍平成 "USER: ... ASSISTANT: ..." 纯文本
    python3 agent.py all              # 全部 + 对比表

⚠️ 需要本地 Ollama（和实验 2-1 同一套环境）。装法见 2-0 的 README。
   之所以必须用本地模型：**只有它会告诉你 prefill 耗时。**
   云端 API 不暴露这个数，你就没法量缓存效应。

详细讲解见 README.zh-CN.md（中文）/ README.md（英文）。
"""

import json
import random
import sys
import time
from datetime import datetime

from ollama_client import (OllamaNotRunning, ModelMissing, chat_stream,
                           ensure_ready, list_models)


# --------------------------------------------------------------------------
#  可以改的开关
# --------------------------------------------------------------------------

LANG = "zh"

MODEL = "qwen3:0.6b"

WINDOW = 6        # sliding_window 模式保留最近几条消息

CREDITS_START = 4831   # dynamic_profile 模式的初始额度，每次请求减 1

REPEATS = 2       # 每种策略跑几次（第 2 次用来看缓存命中）

SHOW_PROMPT = False


MODES = ["good", "dynamic_prompt", "dynamic_profile", "shuffled_tools",
         "sliding_window", "flattened"]

# ★ 交错测量用的三个模式。见下面 run_interleaved 的注释——
#   **顺序跑会测错**，这是本实验最重要的一个方法论教训。
CACHE_MODES = ["good", "dynamic_prompt", "dynamic_profile"]

ROUNDS = 8        # cache 模式跑几轮


# ==========================================================================
#  第 1 部分：写死的历史  ★★★ 本实验可复现的关键 ★★★
# ==========================================================================
#
# 为什么不让模型自己跑出一段历史？因为那样每种策略面对的历史就不一样了，
# 比较就不成立。这里把历史**完全写死**，五种策略处理的是同一份输入。
#
# 剧本：一个 agent 用 read_sensor 读了 5 个传感器的值，中间夹着一些闲聊。
# 最后问它：这 5 个数加起来是多少？

SENSOR_VALUES = [37, 12, 58, 21, 44]

# ★ 判据用【检索最早的那个读数】，不用【求和】。
#   原因：0.6B 能准确复述一个数，但加 5 个两位数经常算错——
#   用求和当判据，测到的是它的算术能力，而不是上下文管理策略。**变量会混。**
#   而 1 号传感器的读数在最早的消息里，正好是 sliding_window 一定会丢掉的东西。
TARGET_SENSOR = 1
TRUE_ANSWER = SENSOR_VALUES[TARGET_SENSOR - 1]      # = 37

# 五个工具的定义（shuffled_tools 模式会打乱它们的顺序）
TOOL_DEFS = [
    ("read_sensor", "读取指定编号传感器的当前读数"),
    ("list_sensors", "列出所有可用的传感器编号"),
    ("get_calibration", "查询某个传感器的校准参数"),
    ("export_report", "把读数导出成一份报表文件"),
    ("check_status", "检查采集系统的运行状态"),
]


def build_history(lang):
    """构造那 12 条消息。返回 [(role, content), ...]。"""
    t_ = TEXT[lang]
    messages = []
    for i in range(5):
        messages.append(("assistant",
                         '{"tool": "read_sensor", "args": {"id": %d}}' % (i + 1)))
        messages.append(("user",
                         t_["hist_tool_result"].format(id=i + 1,
                                                       value=SENSOR_VALUES[i])))
    # 两条无关的闲聊，让历史更像真的
    messages.append(("assistant", t_["hist_chat_a"]))
    messages.append(("user", t_["hist_chat_u"]))
    return messages


# --------------------------------------------------------------------------
#  文案（中英双语）
# --------------------------------------------------------------------------

TEXT = {
    "zh": {
        "sys_head": "你是一个数据采集助手。可用工具：",
        "sys_tail": """
回答问题时，请直接给出答案。如果需要用到之前读到的数据，就用你上下文里已经有的，
**不要重复调用工具**。

只输出一个 JSON：{"answer": "<你的回答>"}""",
        "hist_tool_result": "工具返回：{{\"sensor\": {id}, \"value\": {value}}}",
        "profile_line": "\n\n[用户状态] 账户 alice，本月剩余调用额度：{credits} 次。",
        "hist_chat_a": "好的，5 个传感器都读完了。",
        "hist_chat_u": "收到，先放着，我等下要用。",
        "question": "你之前读到的 1 号传感器的读数是多少？只回答一个数字。",

        "no_ollama_title": "✗ 连不上 Ollama（这个实验需要本地模型来量 prefill）",
        "no_ollama_help": """
和实验 2-1 是同一套环境：

    brew install ollama
    ollama serve                 # 另开一个终端让它一直跑
    ollama pull {model}

⚠️ 为什么必须用本地模型？因为**只有它会告诉你 prefill 耗时**。
   云端 API 不暴露这个数字，缓存效应就没法量。
""",
        "no_model_title": "✗ Ollama 在跑，但没有这个模型：{model}",
        "no_model_help": "    ollama pull {model}\n\n你本地有的：{have}\n",

        "model_line": "模型：{model}   历史：12 条消息   问 1 号传感器读数，正确答案：{ans}",
        "mode_head": "  模式：{mode}",
        "mode_desc": "  {desc}",
        "desc_good": "标准做法：稳定的系统提示词 + 完整历史 + 标准消息格式",
        "desc_dynamic_prompt": "把变化的时间戳塞进系统提示词【开头】",
        "desc_dynamic_profile": "把每次都在变的「剩余额度」塞进系统提示词【末尾】（只差 1 个字符）",
        "desc_shuffled_tools": "每次请求都打乱工具定义的顺序",
        "desc_sliding_window": "只保留最近 {n} 条消息，更早的丢掉",
        "desc_flattened": "把所有消息拍平成 \"USER: … ASSISTANT: …\" 一整段纯文本",

        "ctx_stat": "  上下文：{n} 条消息 → {ptok} 个输入 token",
        "run_line": "  第 {i} 次：预填充 {prefill} ms   TTFT {ttft} ms",
        "answer_line": "  [回答] {text}",
        "verdict_ok": "  ✓ 答对了（{ans}）",
        "verdict_bad": "  ✗ 答错了：说的是 {got}，正确答案是 {ans}",
        "verdict_none": "  ✗ 没给出数字",
        "lost_note": "  ☠ 注意：窗口滑掉了前 {n} 条，模型**根本看不到**前几个读数了",

        "summary_title": "对比结果",
        "summary_mode": "模式：{mode}",
        "summary_ctx": "  输入 token：{ptok}",
        "summary_prefill": "  预填充：第 1 次 {p1} ms → 第 2 次 {p2} ms",
        "summary_answer": "  答案：{r}",
        "summary_ok": "✓ 对",
        "summary_bad": "✗ 错（{got}）",
        "summary_verify": """
一张表怎么读 —— **两类破坏要分开看**：

  【A 类：破坏缓存】只影响成本和延迟，不影响对错
     dynamic_prompt    时间戳在系统提示词开头 → 前缀每次都变
     dynamic_profile   剩余额度在系统提示词末尾 → 前缀从那一个字符起全变
     shuffled_tools    工具顺序每次都变 → 前缀每次都变
     → 看「预填充：第 1 次 → 第 2 次」这一列。
       good 应该第 2 次明显更快（命中缓存）；这两个应该【不会】变快。

  【B 类：破坏能力】直接让答案错掉
     sliding_window    早期的工具结果被丢掉了 → 模型看不到，只能瞎猜
     flattened         偏离了模型训练时的消息格式（书里说的）
     → 看「答案」那一列。

★ 最值得记住的是这两类的**代价完全不同**：
    A 类是**钱和延迟**的问题 —— 你会一直付，但不会出错
    B 类是**正确性**的问题 —— 它会安静地给你一个错答案

⚠️ 两个如实交代（跑之前先想想，跑完再回来对）：

  1) 这张 `all` 表**不适合用来测缓存**。它是顺序跑的（一种模式跑完再跑下一种），
     而本地后端的状态会随时间漂移 —— 于是「模式」和「先后顺序」两个变量绑死了。
     → **要测缓存请用 `python3 agent.py cache`**（交错测量）。
       我第一版就是拿这张顺序表下的结论，结果同一个配置量出过 180ms 也量出过 11ms。

  2) sliding_window 在这里**缓存是命中的**（第 2 次会变快）。
     不是书错了 —— 是**这个实验测不到那一面**：两次请求窗口位置一样，
     前缀自然一样。书说的是对话往前走、窗口跟着滑时前缀才会变。
     本实验能测到的是它的另一面：**信息真的没了，答案真的错了。**""",

        "cache_head": "交错测量（{n} 轮，每轮三种模式各发一次）—— 量的是预填充耗时",
        "cache_round": "轮次",
        "cache_stat": "  {mode} 区间 {lo} ~ {hi} ms，其中慢档（>60ms）{slow}/{total} 次",
        "cache_verdict": """
怎么读这张表 —— **横着看，不要竖着看**：

  good            应该**每一轮都快**（前缀从没变过）
  dynamic_prompt  应该**每一轮都慢**（微秒时间戳在第 0 个 token，前缀永远全新）
  dynamic_profile ← ★ 这一列才是重点，自己看它是什么样

★ 我实测的结论写在 SOLUTION 里，先别看。
  提示：dynamic_profile 只改了 1 个字符，而且改在系统提示词【末尾】。
  如果「变化点之后全部作废」这个说法是对的，它应该和 dynamic_prompt 一样慢。
  **它是吗？**""",
        "unknown_mode": "✗ 不认识的模式：",
        "exp_header": "# {i}/{total}：{mode}",
        "help": """
======================================================================
 实验 2-3：五种常见的错误上下文管理模式
======================================================================

对**同一段写死的 12 条消息历史**施加六种上下文管理策略（1 对 + 5 错），
然后问同一个问题（「1 号传感器的读数是多少」），量两件事：

    ① 预填充耗时 —— 缓存被破坏了吗？（成本问题）
    ② 答案对不对 —— 能力被破坏了吗？（正确性问题）

用法：
    python3 agent.py <模式>

【六种模式 = 1 种对的 + 5 种错的】
    good             标准做法（基线）
    dynamic_prompt   系统提示词【开头】塞变化的时间戳     ← 破坏缓存
    dynamic_profile  系统提示词【末尾】塞变化的剩余额度   ← 破坏缓存 ★★
    shuffled_tools   每次打乱工具顺序                    ← 破坏缓存
    sliding_window   只保留最近 6 条                     ← 破坏缓存【和】能力 ★★
    flattened        拍平成纯文本                        ← 破坏能力

    all              全部跑一遍 + 对比表
    cache            ★ 交错测量缓存效应（想量缓存就用这个，别用 all）

★ 判分是机械的：正确答案写死（37），比对数字即可。
★ 历史是程序化构造的，六种策略面对的输入完全一样。

⚠️ 需要本地 Ollama（同实验 2-1）。
   必须用本地模型的原因：**只有它会告诉你 prefill 耗时。**

把开头的 LANG 改成 "en" 可切英文。
详细讲解见 README.zh-CN.md。
""",
    },
    "en": {
        "sys_head": "You are a data-collection assistant. Available tools:",
        "sys_tail": """
Answer the question directly. If you need data you read earlier, use what is
already in your context - **do not call the tool again**.

Reply with one JSON object: {"answer": "<your answer>"}""",
        "hist_tool_result": "Tool returned: {{\"sensor\": {id}, \"value\": {value}}}",
        "profile_line": "\n\n[User state] account alice, calls remaining this month: {credits}.",
        "hist_chat_a": "OK, all five sensors have been read.",
        "hist_chat_u": "Got it, hold on to those - I'll need them shortly.",
        "question": "What reading did you get from sensor 1 earlier? Answer with just a number.",

        "no_ollama_title": "x Can't reach Ollama (this lab needs a local model to measure prefill)",
        "no_ollama_help": """
Same setup as lab 2-1:

    brew install ollama
    ollama serve                 # leave running in another terminal
    ollama pull {model}

⚠️ Why a local model is required: **only it reports prefill time.**
   Cloud APIs don't expose that number, so the cache effect can't be measured.
""",
        "no_model_title": "x Ollama is running but lacks this model: {model}",
        "no_model_help": "    ollama pull {model}\n\nYou have: {have}\n",

        "model_line": "Model: {model}   history: 12 messages   asking for sensor 1, correct answer: {ans}",
        "mode_head": "  Mode: {mode}",
        "mode_desc": "  {desc}",
        "desc_good": "the right way: stable system prompt + full history + standard message format",
        "desc_dynamic_prompt": "a changing timestamp injected at the START of the system prompt",
        "desc_dynamic_profile": "a changing \"credits remaining\" injected at the END of the system prompt (1 character differs)",
        "desc_shuffled_tools": "tool definitions reordered on every request",
        "desc_sliding_window": "only the last {n} messages kept; older ones dropped",
        "desc_flattened": "everything flattened into one \"USER: ... ASSISTANT: ...\" text blob",

        "ctx_stat": "  context: {n} messages -> {ptok} input tokens",
        "run_line": "  run {i}: prefill {prefill} ms   TTFT {ttft} ms",
        "answer_line": "  [answer] {text}",
        "verdict_ok": "  ok correct ({ans})",
        "verdict_bad": "  x wrong: said {got}, correct is {ans}",
        "verdict_none": "  x no number given",
        "lost_note": "  ! note: the window dropped the first {n} messages - the model literally cannot see the early readings",

        "summary_title": "COMPARISON",
        "summary_mode": "mode: {mode}",
        "summary_ctx": "  input tokens: {ptok}",
        "summary_prefill": "  prefill: run 1 {p1} ms -> run 2 {p2} ms",
        "summary_answer": "  answer: {r}",
        "summary_ok": "ok correct",
        "summary_bad": "x wrong ({got})",
        "summary_verify": """
How to read this - **two different kinds of damage**:

  [Type A: breaks the cache] costs money and latency; correctness unaffected
     dynamic_prompt    timestamp at the start of the system prompt -> prefix changes every time
     dynamic_profile   credits at the END of the system prompt -> everything from that character on changes
     shuffled_tools    tool order changes every time -> prefix changes every time
     -> Look at "prefill: run 1 -> run 2".
        `good` should be clearly faster on run 2 (cache hit); these two should NOT be.

  [Type B: breaks capability] makes the answer wrong
     sliding_window    early tool results dropped -> the model can't see them, so it guesses
     flattened         deviates from the message format the model was trained on (the book's claim)
     -> Look at the "answer" column.

* The thing worth remembering is that the two costs are **completely different**:
    Type A is a **money and latency** problem - you pay forever, but stay correct
    Type B is a **correctness** problem - it quietly hands you a wrong answer

! Two honest caveats (predict first, then come back and check):

  1) This `all` table is **not a good instrument for measuring cache**. It runs modes
     sequentially, and the local backend's state drifts over time - so "which mode" and
     "which position in the sequence" are confounded.
     -> **Use `python3 agent.py cache`** (interleaved) to measure cache.
       My first write-up drew conclusions from this sequential table, and the same
       configuration measured 180ms on one pass and 11ms on another.

  2) sliding_window **does hit the cache here** (run 2 gets faster). The book isn't
     wrong - **this lab can't measure that side**: both requests use the same window
     position, so the prefix is identical. The book's claim is about the prefix
     changing as the conversation advances and the window slides along.
     What this lab does measure is the other side: **information is genuinely gone,
     and the answer is genuinely wrong.**""",

        "cache_head": "Interleaved measurement ({n} rounds, one request per mode per round) - measuring prefill",
        "cache_round": "round",
        "cache_stat": "  {mode} range {lo} ~ {hi} ms; slow (>60ms) on {slow}/{total}",
        "cache_verdict": """
How to read this - **read across the rows, not down the columns**:

  good            should be **fast every round** (the prefix never changed)
  dynamic_prompt  should be **slow every round** (microsecond timestamp at token 0)
  dynamic_profile <- * this is the interesting column; look at it yourself

* My measured conclusion is in SOLUTION. Don't look yet.
  Hint: dynamic_profile changes exactly one character, at the **END** of the system
  prompt. If "everything after the change point is invalidated" were the whole story,
  it should be as slow as dynamic_prompt. **Is it?**""",
        "unknown_mode": "x unknown mode: ",
        "exp_header": "# {i}/{total}: {mode}",
        "help": """
======================================================================
 Lab 2-3: Five common context-management anti-patterns
======================================================================

Apply six context-management strategies (1 right + 5 wrong) to **the same
hard-coded 12-message history**, ask the same question ("what was sensor 1's reading?"), and
measure two things:

    1) prefill time - was the cache broken?      (a cost problem)
    2) is the answer right - was capability broken? (a correctness problem)

Usage:
    python3 agent.py <mode>

THE SIX MODES = 1 right + 5 wrong
    good             the right way (baseline)
    dynamic_prompt   changing timestamp at the START of the system prompt  <- breaks cache
    dynamic_profile  changing credits at the END of the system prompt      <- breaks cache **
    shuffled_tools   tool order shuffled every time                        <- breaks cache
    sliding_window   only the last 6 messages kept          <- breaks cache AND capability
    flattened        flattened into plain text                             <- breaks capability

    all              run everything + comparison table
    cache            * interleaved cache measurement (use THIS to measure cache, not `all`)

* Scoring is mechanical: the correct answer is hard-coded (37).
* The history is constructed programmatically, so all six see identical input.

⚠️ Needs local Ollama (same as lab 2-1).
   Why local is required: **only it reports prefill time.**

Set LANG = "zh" at the top for Chinese.
Full walkthrough: README.md
""",
    },
}


def t(key, **kwargs):
    template = TEXT[LANG][key]
    return template.format(**kwargs) if kwargs else template


# ==========================================================================
#  第 2 部分：五种策略  ★★★ 本实验的核心 ★★★
# ==========================================================================
#
# 每个函数拿到同一份 (system_prompt, history)，返回要发出去的 messages。
# 差别只在这里。


def render_tools(shuffle=False, seed=0):
    tools = list(TOOL_DEFS)
    if shuffle:
        random.Random(seed).shuffle(tools)
    lines = [t("sys_head")]
    for name, desc in tools:
        lines.append("  " + name + " —— " + desc if LANG == "zh"
                     else "  " + name + " - " + desc)
    return "\n".join(lines)


def build_messages(mode, history, run_index):
    """把历史按某种策略装配成最终要发的 messages。"""

    # ---- 系统提示词 ----
    if mode == "dynamic_prompt":
        # ☠ 错误做法：把每次都在变的时间戳放在【最前面】
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        system = ("Current time: " + stamp + "\n"
                  + render_tools() + t("sys_tail"))
    elif mode == "dynamic_profile":
        # ☠ 错误做法：把每次都在变的用户状态（剩余额度）塞进系统提示词。
        #   ★ 注意它放在【末尾】—— 很多人以为「放后面一点就不影响前面的缓存了」。
        #     这个模式就是用来测这个想法的。CREDITS_START 每次请求减 1，
        #     所以两次请求之间**只有一个字符不一样**。
        system = (render_tools() + t("sys_tail")
                  + t("profile_line", credits=CREDITS_START - run_index))
    elif mode == "shuffled_tools":
        # ☠ 错误做法：每次请求工具顺序都不一样
        system = render_tools(shuffle=True, seed=run_index) + t("sys_tail")
    else:
        system = render_tools() + t("sys_tail")

    # ---- 历史 ----
    used = history
    if mode == "sliding_window":
        # ☠ 错误做法：只留最近几条 —— 早期的工具结果直接没了
        used = history[-WINDOW:]

    if mode == "flattened":
        # ☠ 错误做法：把结构化消息拍平成纯文本
        blob = []
        for role, content in used:
            blob.append(("USER: " if role == "user" else "ASSISTANT: ") + content)
        blob.append("USER: " + t("question"))
        return [{"role": "system", "content": system},
                {"role": "user", "content": "\n".join(blob)}]

    messages = [{"role": "system", "content": system}]
    for role, content in used:
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": t("question")})
    return messages


# ==========================================================================
#  第 3 部分：判分（机械的）
# ==========================================================================


def extract_number(text):
    """从回答里抠出第一个整数。抠不到返回 None。"""
    import re
    found = re.findall(r"-?\d+", str(text).replace(",", ""))
    if not found:
        return None
    # 优先找等于正确答案的那个（避免它把 5 个数原样列出来时误判）
    for one in found:
        if int(one) == TRUE_ANSWER:
            return TRUE_ANSWER
    return int(found[-1])


def _fmt(value, digits=1):
    return "?" if value is None else ("%." + str(digits) + "f") % value


# ==========================================================================
#  第 4 部分：跑一种策略
# ==========================================================================


def run(mode, backend=None, verbose=True):
    history = build_history(LANG)

    desc = {
        "good": t("desc_good"),
        "dynamic_prompt": t("desc_dynamic_prompt"),
        "dynamic_profile": t("desc_dynamic_profile"),
        "shuffled_tools": t("desc_shuffled_tools"),
        "sliding_window": t("desc_sliding_window", n=WINDOW),
        "flattened": t("desc_flattened"),
    }[mode]

    if verbose:
        print("")
        print("=" * 70)
        print(t("mode_head", mode=mode))
        print(t("mode_desc", desc=desc))
        print("=" * 70)

    prefills = []
    answer_text = ""
    ptok = 0

    for i in range(REPEATS):
        messages = build_messages(mode, history, i)
        if SHOW_PROMPT and i == 0:
            print("")
            for m in messages:
                print("  │ [" + m["role"] + "] " + m["content"][:150])
        result = chat_stream(MODEL, messages,
                             options={"num_predict": 64}, think=False)
        prefills.append(result["prefill_ms"] or 0.0)
        answer_text = result["text"]
        ptok = result["prompt_tokens"]
        if verbose:
            if i == 0:
                print("")
                print(t("ctx_stat", n=len(messages), ptok=ptok))
                if mode == "sliding_window":
                    print(t("lost_note", n=len(history) - WINDOW))
            print(t("run_line", i=i + 1,
                    prefill=_fmt(result["prefill_ms"]),
                    ttft=_fmt(result["ttft_ms"])))

    # 解析答案
    parsed = answer_text
    try:
        obj = json.loads(answer_text.strip())
        if isinstance(obj, dict) and "answer" in obj:
            parsed = str(obj["answer"])
    except Exception:
        pass

    got = extract_number(parsed)
    ok = (got == TRUE_ANSWER)

    if verbose:
        print("")
        print(t("answer_line", text=str(parsed)[:120].replace("\n", " ")))
        if got is None:
            print(t("verdict_none"))
        elif ok:
            print(t("verdict_ok", ans=TRUE_ANSWER))
        else:
            print(t("verdict_bad", got=got, ans=TRUE_ANSWER))
        print("")

    return {"mode": mode, "prefills": prefills, "ptok": ptok,
            "ok": ok, "got": got}


# ==========================================================================
#  第 4.5 部分：交错测量  ★★★ 想量缓存，必须用这个 ★★★
# ==========================================================================
#
# 为什么不能「先把 good 跑 N 次，再把 dynamic_prompt 跑 N 次」？
#
#   因为本地推理后端的状态会**随时间漂移**（模型刚加载完、缓存槽的内容、
#   Metal 那边的预热……）。顺序跑的话，「模式」和「时间」这两个变量是绑死的：
#   你以为在比模式，其实在比「先跑的 vs 后跑的」。
#
#   我第一版就是顺序跑的，结果同一个配置能给出 180ms 和 11ms 两种答案——
#   取决于它排在第几个。**那不是效应，那是漂移。**
#
# 交错跑（每一轮里三种模式各发一次）就把时间这个变量摊平了：
# 任何时刻的漂移，三种模式**同时**吃到。


def run_interleaved(rounds=ROUNDS):
    history = build_history(LANG)
    print("")
    print(t("cache_head", n=rounds))
    print("")
    header = "  " + t("cache_round").ljust(8)
    for m in CACHE_MODES:
        header += m.rjust(18)
    print(header)
    print("  " + "-" * (8 + 18 * len(CACHE_MODES)))

    collected = {m: [] for m in CACHE_MODES}
    for i in range(rounds):
        line = "  " + ("%d" % (i + 1)).ljust(8)
        for m in CACHE_MODES:
            result = chat_stream(MODEL, build_messages(m, history, i),
                                 options={"num_predict": 8}, think=False)
            ms = result["prefill_ms"] or 0.0
            collected[m].append(ms)
            line += ("%.1f ms" % ms).rjust(18)
        print(line)

    print("")
    for m in CACHE_MODES:
        vals = collected[m]
        slow = [v for v in vals if v > 60]
        print(t("cache_stat", mode=m.ljust(16),
                lo=_fmt(min(vals)), hi=_fmt(max(vals)),
                slow=len(slow), total=len(vals)))
    print(t("cache_verdict"))


# ==========================================================================
#  第 5 部分：入口
# ==========================================================================


def print_summary(results):
    print("")
    print("=" * 70)
    print(t("summary_title"))
    print("=" * 70)
    for r in results:
        print("")
        print(t("summary_mode", mode=r["mode"]))
        print(t("summary_ctx", ptok=r["ptok"]))
        p = r["prefills"]
        print(t("summary_prefill", p1=_fmt(p[0]),
                p2=_fmt(p[1]) if len(p) > 1 else "?"))
        print(t("summary_answer",
                r=t("summary_ok") if r["ok"] else t("summary_bad", got=r["got"])))
    print(t("summary_verify"))


def _quiet_ctrl_c(exc_type, exc_value, tb):
    if exc_type is KeyboardInterrupt:
        print("")
        sys.exit(130)
    sys.__excepthook__(exc_type, exc_value, tb)


sys.excepthook = _quiet_ctrl_c


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print(t("help"))
        sys.exit(0)

    mode_arg = sys.argv[1]
    if mode_arg in ("-h", "--help", "help"):
        print(t("help"))
        sys.exit(0)
    if mode_arg not in MODES and mode_arg not in ("all", "cache"):
        print("")
        print(t("unknown_mode") + mode_arg)
        print(t("help"))
        sys.exit(1)

    try:
        ensure_ready(MODEL)
    except OllamaNotRunning:
        print("")
        print(t("no_ollama_title"))
        print(t("no_ollama_help", model=MODEL))
        sys.exit(1)
    except ModelMissing:
        print("")
        print(t("no_model_title", model=MODEL))
        print(t("no_model_help", model=MODEL,
                have=", ".join(list_models()) or "-"))
        sys.exit(1)

    print(t("model_line", model=MODEL, ans=TRUE_ANSWER))

    if mode_arg == "cache":
        run_interleaved()
        sys.exit(0)

    todo = MODES if mode_arg == "all" else [mode_arg]
    results = []
    for i in range(len(todo)):
        if len(todo) > 1:
            print("")
            print("#" * 70)
            print(t("exp_header", i=i + 1, total=len(todo), mode=todo[i]))
            print("#" * 70)
        results.append(run(todo[i]))
    if mode_arg == "all":
        print_summary(results)
