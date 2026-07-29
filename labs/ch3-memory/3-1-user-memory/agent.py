"""
实验 3-1：用户记忆 —— 跨会话记住一个人

第 2 章讲的都是**一次会话之内**的上下文。这一章问的是：

    **会话结束了，上下文清空了。下次他再来，你怎么还认得他？**

很多人第一反应是「把聊天记录全存下来，下次全塞进去」。
能用，但你马上会撞上第 2 章那面墙 —— 越存越大，最后装不下。

真正的解法是：**存之前先提取**。把一场会话里值得长期记住的东西
（他对花生过敏）挑出来，把不值得记的（他今天淋雨了）扔掉。

这个实验让你亲眼看到「挑得好」和「挑不好」的差别 ——
而差别的全部，就藏在一段**提取提示词**里。

    python3 agent.py                 # 打印用法说明
    python3 agent.py no_memory       # 没有记忆（基线）
    python3 agent.py full_log        # 把聊天记录全存下来
    python3 agent.py naive_extract   # 提取，但提示词很随便
    python3 agent.py extracted       # 提取，提示词写得好 ★核心
    python3 agent.py all             # 四种全跑 + 对比表

不需要 API key，也不联网。

⚠️ 这个实验会在当前目录写 `memory_<模式>.json` 文件 —— **那不是临时文件，
   那就是 agent 的记忆本体**。跑完记得打开看看，这是本实验最有价值的一步。

详细讲解见 README.zh-CN.md（中文）/ README.md（英文）。
"""

import json
import os
import sys
import time

from llm import complete, detect_backend, parse_json_reply


# --------------------------------------------------------------------------
#  可以改的开关（Settings）
# --------------------------------------------------------------------------

LANG = "zh"          # "zh" | "en" —— 同时切换输出和发给模型的提示词

SHOW_PROMPT = False  # 改成 True 会打印每次真正发给模型的完整文本


MODES = [
    "no_memory",      # 每次都从零开始（基线）
    "full_log",       # 把历史会话原文全存下来
    "naive_extract",  # 让模型提取，但提示词很随便
    "extracted",      # 让模型提取，提示词写得好 ★核心
]


# --------------------------------------------------------------------------
#  剧本：前两次会话（写死，保证每个人跑出来的都一样）
# --------------------------------------------------------------------------
#
# 为什么写死？因为本实验要比较的是**四种记忆策略**，不是比较模型的聊天能力。
# 前两次会话的内容固定下来，四种模式面对的输入才完全一样，比较才成立。
#
# 剧本里故意埋了三类东西，对应记忆系统的三个真实难点：
#
#   1. **该长期记住的**：花生过敏、不吃辣（第 1 次会话）
#   2. **当天就过期的噪声**：下雨、忘带伞、感冒、排队（第 3、4 次会话）
#      —— 记忆系统真正的难点不是「记住」，是**「不记什么」**
#   3. **中途变了的事实**：先说在北京上班，第 5 次会话说调岗到上海（第 2、5 次会话）
#      —— 这是最难的一类：一个只会追加的记忆，会同时记住两个矛盾的版本


# --------------------------------------------------------------------------
#  所有对用户可见的文字，按语言分开放（包含发给模型的提示词和剧本）
# --------------------------------------------------------------------------

TEXT = {
    "zh": {
        # --- 剧本 ---
        "sessions": [
            "我对花生过敏，吃到会直接送医院，这个千万记住。另外我完全不吃辣，一点都不行。",
            "我在北京国贸上班，做后端开发，平时中午就在公司楼下吃。",
            "今天下雨我忘带伞，淋了一路，现在有点感冒，晚上打算早点睡。",
            "上周末去了趟环球影城，人太多了，排队排到怀疑人生，我是真受不了人挤人的地方。",
            "更新一下：我下个月调岗，以后常驻上海浦东了，北京这边不去了。",
            "我下周要去成都出差三天，住在春熙路附近。",
        ],
        "session_label": "第 {n} 次会话（用户说）",
        # --- 提取提示词：本实验的核心对照 ---
        "extract_naive": """把下面这段会话里的信息提取成记忆条目。

只输出 JSON：{"memories": ["条目1", "条目2", ...]}""",
        "extract_good": """你在为一个长期助手维护「用户档案」。从下面这段会话里提取值得**长期记住**的信息。

判断标准（**这几条决定了记忆系统的成败**）：
1. **只记长期为真的事**：过敏、忌口、职业、家庭、稳定偏好
2. **明确扔掉当下状态**：今天的天气、此刻的心情、临时的身体不适、
   一次性的琐事 —— 这些下周就没用了，留着只会污染记忆
3. **有时限的事要写清时限**（比如「下周出差」要写成日期范围或标注会过期）
4. **一条只说一件事**，别把两件事塞进一条
5. **原样保留具体值**（数字、地名、名称），不要概括成「有一些忌口」

只输出 JSON：{"memories": ["条目1", "条目2", ...]}""",
        "extract_input": "会话内容：",
        # --- 回答提示词 ---
        "sys_answer": "你是一个长期陪伴用户的生活助手。",
        "sys_with_memory": """下面是你**记得的关于这个用户的事**（来自以前的会话）：
{memory}

回答时要主动照顾这些信息，不需要用户再说一遍。""",
        "sys_no_memory": "你和这个用户是第一次对话，你对他一无所知。",
        "sys_answer_protocol": """只输出一个 JSON 对象，不要有别的内容：
  {"answer": "<你的回答>"}""",
        # --- 交互输入 ---
        "ask_task": "第 7 次会话，请输入用户这次想问什么（直接回车看例子）：\n> ",
        "examples_title": "几个可以直接复制的例子（都会用到前面会话里的信息）：",
        "task_examples": [
            "帮我列一个成都出差期间的餐厅清单。",
            "我明天要请客户吃饭，帮我挑一家餐厅并说说点什么菜。",
            "帮我规划一下出差这三天的三餐。",
        ],
        "picked": "  ✓ 已选第 {n} 个：{task}",
        "number_out_of_range": "  （只有 {n} 个例子，就按你输的内容当问题了）",
        "need_task": "没有问题就没法跑。把问题写在模式后面，或者不带问题运行进入交互输入。",
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
        "task_label": "最后一次会话要问：",
        "phase1": "  ── 第 1 步：回放前 6 次会话，边放边更新记忆 ──",
        "phase2": "  ── 第 2 步：新会话开始，装配上下文 ──",
        "phase3": "  ── 第 3 步：回答 + 判定 ──",
        "mode_desc_line": "  记忆策略：{desc}",
        "desc_no_memory": "不记 —— 每次从零开始",
        "desc_full_log": "全记 —— 聊天记录原样存下来",
        "desc_naive_extract": "提取 —— 但提取提示词很随便",
        "desc_extracted": "提取 —— 提取提示词写清了「记什么、不记什么」",
        "extracting": "  正在让模型提取记忆…",
        "took": " 用了 {sec} 秒",
        "asking": "  正在问模型…",
        "no_update": "  （这个模式不更新记忆）",
        "mem_head": "  ┌─ 记忆文件 {file} ───────────────",
        "mem_empty": "  │ （空）",
        "mem_foot": "  └────────────────────────────────────────────",
        "mem_size": "  记忆体积：{n} 字  {bar}",
        "mem_facts": "  关键事实：记住了 {n}/2 条  {detail}",
        "mem_noise": "  无用信息：混进了 {n} 条  {detail}",
        "mem_noise_none": "  无用信息：0 条  ✓ 干净",
        "mem_stale": "  过期事实：{detail} —— 还留在记忆里，会误导后面的回答",
        "mem_stale_none": "  过期事实：无  ✓ 记忆被正确更新了",
        "mem_stale_na": "  过期事实：不适用（这个模式根本没有记忆）",
        "answer": "  [回答] ",
        "verdict_head": "  ─── 回答有没有照顾到用户的情况 ───",
        "verdict_hit": "  ✓ 照顾到了：{desc}",
        "verdict_miss": "  ✗ 没照顾到：{desc}",
        "fact_allergy": "花生过敏",
        "fact_spice": "不吃辣",
        "noise_rain": "今天下雨",
        "noise_umbrella": "忘带伞",
        "noise_cold": "有点感冒",
        "noise_sleep": "打算早点睡",
        "noise_park": "上周末去环球影城",
        "stale_beijing": "北京（已经调岗到上海了）",
        # --- 对比表 + 用法说明 ---
        "summary_title": "对比结果",
        "summary_mode": "模式：",
        "summary_size": "  记忆体积：{n} 字",
        "summary_facts": "  关键事实：{n}/2",
        "summary_noise": "  无用信息：{n} 条",
        "summary_stale": "  过期事实：{s}",
        "stale_yes": "✗ 还留着",
        "stale_no": "✓ 已更新",
        "stale_na": "— 不适用（没有记忆）",
        "summary_answer": "  回答照顾到：{n}/2",
        "summary_verify": """
一张表看懂四条路：
  no_memory       什么都不记 —— 用户得把自己重新介绍一遍
  full_log        全记 —— 记住了，但体积随会话数无限增长，垃圾和过期事实一起留着
  naive_extract   会提取了 —— 但没告诉它「什么不该记、事实变了怎么办」
  extracted       提示词写清了标准 —— 又小又准  ← 差别只在那段提示词

★ 特别注意「过期事实」那一行：用户第 5 次会话说了「调岗到上海，北京不去了」。
  一个只会追加、不会更新的记忆系统，会同时记住「在北京上班」和「常驻上海」。

★ 现在打开这四个 memory_*.json 文件对比着看，比看这张表更有感觉。""",
        "unknown_mode": "✗ 不认识的模式：",
        "exp_header": "# 实验 {i}/{total}：{mode}",
        "all_warning": "\n⚠️  all 模式要跑 4 个实验，不联网所以很快，大约 1～3 分钟。",
        "help": """
======================================================================
 实验 3-1：用户记忆 —— 跨会话记住一个人
======================================================================

同一个用户，同样的 7 次会话，四种记忆策略。看的是「记什么」有多重要。

用法：
    python3 agent.py <模式> ["最后一次会话要问什么"]

【四种模式】
    no_memory       不记，每次从零开始（基线）
    full_log        聊天记录原样全存
    naive_extract   让模型提取，但提示词很随便
    extracted       让模型提取，提示词写清标准 ★核心

【对比】
    all             四种全跑，最后打印对比表（约 1~3 分钟，不联网）

程序会在每次跑完后直接告诉你：
    - 记忆有多大（字数）—— 会话越多，四种模式差距越大
    - 2 条关键事实记住了几条
    - 混进了几条当天就过期的无用信息
    - **已经作废的事实还留着没有**（用户中途换了城市）
    - 最终回答有没有照顾到用户的情况

建议顺序：
    1. 先跑 no_memory，看没有记忆是什么体验
    2. 再跑 full_log —— 记住了，但注意看记忆体积和垃圾
    3. 跑 naive_extract，再跑 extracted，**对比这两个的记忆文件**

⚠️ 会在当前目录写 memory_<模式>.json —— 那就是 agent 的记忆本体，一定要打开看。

把文件开头的 LANG 改成 "en" 可切换成英文输出。
详细讲解见 README.zh-CN.md。
""",
    },
    "en": {
        "sessions": [
            "I'm allergic to peanuts - eating one sends me to the ER, please never forget "
            "this. I also don't eat spicy food at all, not even a little.",
            "I work in Beijing, in the Guomao district, as a backend developer. I usually "
            "just eat downstairs from the office at lunch.",
            "It rained today and I forgot my umbrella, got soaked the whole way, so I've "
            "got a bit of a cold now - planning an early night.",
            "Went to Universal Studios last weekend. Way too crowded, queued until I "
            "questioned my life choices. I really can't stand packed places.",
            "Update: I'm transferring next month and will be based in Shanghai Pudong from "
            "then on. No longer going in to Beijing.",
            "I'm travelling to Chengdu for a three-day work trip next week, staying near "
            "Chunxi Road.",
        ],
        "session_label": "Session {n} (the user says)",
        "extract_naive": """Extract memory items from the conversation below.

Reply with JSON only: {"memories": ["item 1", "item 2", ...]}""",
        "extract_good": """You maintain a long-term user profile for an assistant. Extract what is worth
remembering **long term** from the conversation below.

Criteria (**these decide whether the memory system works**):
1. **Only lastingly-true things**: allergies, dietary rules, job, family, stable preferences
2. **Explicitly drop present state**: today's weather, current mood, temporary
   ailments, one-off trivia - useless next week, and they only pollute the memory
3. **Time-bounded facts must carry their bound** ("trip next week" -> a date range,
   or mark it as expiring)
4. **One item, one fact** - don't pack two things into one line
5. **Keep concrete values verbatim** (numbers, places, names) - never generalize to
   "has some dietary restrictions"

Reply with JSON only: {"memories": ["item 1", "item 2", ...]}""",
        "extract_input": "Conversation: ",
        "sys_answer": "You are a long-term personal assistant for this user.",
        "sys_with_memory": """Here is **what you remember about this user** (from earlier sessions):
{memory}

Take these into account without making the user repeat themselves.""",
        "sys_no_memory": "This is your first ever conversation with this user. You know nothing about them.",
        "sys_answer_protocol": """Reply with ONE JSON object and nothing else:
  {"answer": "<your reply>"}""",
        "ask_task": "Session 7 - type what the user asks this time (Enter for examples):\n> ",
        "examples_title": "Copy one (all of them need something from the earlier sessions):",
        "task_examples": [
            "Put together a restaurant list for my Chengdu trip.",
            "I'm hosting a client for dinner tomorrow - pick a restaurant and suggest dishes.",
            "Plan all my meals for the three days of the trip.",
        ],
        "picked": "  ok, picked #{n}: {task}",
        "number_out_of_range": "  (only {n} examples, treating your input as the question)",
        "need_task": "No question, nothing to run. Put it after the mode, or run without one to be prompted.",
        "no_tty": "Non-interactive environment detected. Put the question on the command line:\n    python3 agent.py {mode} \"your question\"",
        "interrupted": "\n  Interrupted (Ctrl+C). Run it again to try another question.",
        "rerun_hint": "To compare another mode on the SAME question, copy this and change the mode name:",
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
        "task_label": "Final session question: ",
        "phase1": "  -- Step 1: replay the first 6 sessions, updating memory as we go --",
        "phase2": "  -- Step 2: a new session begins, assemble the context --",
        "phase3": "  -- Step 3: answer + verdict --",
        "mode_desc_line": "  Memory strategy: {desc}",
        "desc_no_memory": "none - start from zero every time",
        "desc_full_log": "everything - store the transcript verbatim",
        "desc_naive_extract": "extract - but with a careless extraction prompt",
        "desc_extracted": "extract - prompt spells out what to keep and what to drop",
        "extracting": "  asking the model to extract memories...",
        "took": " took {sec}s",
        "asking": "  asking the model...",
        "no_update": "  (this mode does not update the memory)",
        "mem_head": "  +- memory file {file} -----------------",
        "mem_empty": "  | (empty)",
        "mem_foot": "  +--------------------------------------------",
        "mem_size": "  memory size: {n} chars  {bar}",
        "mem_facts": "  key facts: {n}/2 remembered  {detail}",
        "mem_noise": "  junk: {n} item(s) leaked in  {detail}",
        "mem_noise_none": "  junk: 0 items  ok clean",
        "mem_stale": "  stale facts: {detail} - still in memory, will mislead later answers",
        "mem_stale_none": "  stale facts: none  ok the memory was correctly updated",
        "mem_stale_na": "  stale facts: n/a (this mode has no memory at all)",
        "answer": "  [answer] ",
        "verdict_head": "  --- did the answer take the user into account? ---",
        "verdict_hit": "  ok honoured: {desc}",
        "verdict_miss": "  x missed: {desc}",
        "fact_allergy": "peanut allergy",
        "fact_spice": "no spicy food",
        "noise_rain": "it rained today",
        "noise_umbrella": "forgot the umbrella",
        "noise_cold": "has a cold",
        "noise_sleep": "an early night",
        "noise_park": "the theme park last weekend",
        "stale_beijing": "Beijing (they already transferred to Shanghai)",
        "summary_title": "COMPARISON",
        "summary_mode": "mode: ",
        "summary_size": "  memory size: {n} chars",
        "summary_facts": "  key facts: {n}/2",
        "summary_noise": "  junk: {n} item(s)",
        "summary_stale": "  stale facts: {s}",
        "stale_yes": "x still there",
        "stale_no": "ok updated",
        "stale_na": "- n/a (no memory)",
        "summary_answer": "  answer honoured: {n}/2",
        "summary_verify": """
Four approaches in one table:
  no_memory       remembers nothing - the user re-introduces themselves every time
  full_log        remembers everything - works, but grows without bound and keeps
                  both the junk and the facts that have since been superseded
  naive_extract   extracts - but was never told what NOT to keep, or what to do
                  when a fact changes
  extracted       the prompt spells out the criteria - small and accurate  <- the
                  only difference is that prompt

* Watch the "stale facts" line especially: in session 5 the user said they're
  transferring to Shanghai and no longer going to Beijing. An append-only memory
  ends up holding "works in Beijing" AND "based in Shanghai" at the same time.

* Now open the four memory_*.json files side by side. More convincing than this table.""",
        "unknown_mode": "x unknown mode: ",
        "exp_header": "# Experiment {i}/{total}: {mode}",
        "all_warning": "\n!  'all' runs 4 experiments. No network, so it's quick: 1-3 minutes.",
        "help": """
======================================================================
 Lab 3-1: User memory - remembering a person across sessions
======================================================================

Same user, same 7 sessions, four memory strategies. Subject: how much
"what you choose to remember" matters.

Usage:
    python3 agent.py <mode> ["what the user asks in the final session"]

THE FOUR MODES
    no_memory       nothing is kept, start from zero (baseline)
    full_log        keep the whole transcript verbatim
    naive_extract   let the model extract, with a careless prompt
    extracted       let the model extract, with a prompt that spells out the
                    criteria  <- the core one

COMPARISON
    all             run all four, then print a table (1-3 minutes, no network)

After each run the program tells you:
    - how big the memory is (characters) - the gap widens with every session
    - how many of the 2 key facts survived
    - how many same-day-expiry junk items leaked in
    - **whether a since-superseded fact is still in there** (the user changed city)
    - whether the final answer took the user into account

Suggested order:
    1. Run no_memory to feel what no memory is like
    2. Run full_log - it remembers, but watch the size and the junk
    3. Run naive_extract, then extracted, and **diff the two memory files**

⚠️ Writes memory_<mode>.json in this folder. That file IS the agent's memory -
   open it.

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


# 自动判分用的关键词表。
# 之所以能自动判分，是因为我们**自己写的剧本**，知道正确答案该包含什么。
# 真实的记忆系统评测没这么容易（见原书 user-memory-evaluation）。
FACT_MARKERS = {
    "zh": [
        ("fact_allergy", ["花生"]),
        ("fact_spice", ["不辣", "不吃辣", "清淡", "忌辣", "少辣", "微辣",
                        "避开辣", "无辣", "不放辣", "非辣", "不能吃辣"]),
    ],
    "en": [
        ("fact_allergy", ["peanut"]),
        ("fact_spice", ["spicy", "non-spicy", "mild", "no chilli", "no chili"]),
    ],
}

NOISE_MARKERS = {
    "zh": [
        ("noise_rain", ["下雨", "雨"]),
        ("noise_umbrella", ["伞"]),
        ("noise_cold", ["感冒"]),
        ("noise_sleep", ["早点睡", "早睡"]),
        ("noise_park", ["环球影城", "排队"]),
    ],
    "en": [
        ("noise_rain", ["rain"]),
        ("noise_umbrella", ["umbrella"]),
        ("noise_cold", ["cold", "unwell"]),
        ("noise_sleep", ["early night", "early to bed"]),
        ("noise_park", ["universal studios", "queue", "theme park"]),
    ],
}

# 「过期事实」表：用户在第 5 次会话里说了「调岗到上海，北京不去了」。
# 记忆里如果还留着北京，说明这个记忆系统**只会追加、不会更新** ——
# 这是记忆系统里最难、也最容易被忽略的一个问题。
STALE_MARKERS = {
    "zh": [("stale_beijing", ["北京", "国贸"])],
    "en": [("stale_beijing", ["beijing", "guomao"])],
}


def count_markers(text, table):
    """数一数 text 里命中了几组关键词，返回（命中数, 命中的名字列表）。"""
    hit_names = []
    lowered = str(text).lower()
    for name_key, words in table:
        for w in words:
            if w.lower() in lowered:
                hit_names.append(t(name_key))
                break
    return len(hit_names), hit_names


# ==========================================================================
#  第 1 部分：记忆的存与取  ★★★ 本实验的核心 ★★★
# ==========================================================================
#
# 一个记忆系统只有两个动作：
#
#     写：会话结束 → 决定留下什么 → 存到文件
#     读：新会话开始 → 把存的东西拼进上下文
#
# 四种模式的差别**全在「写」这一步**。「读」四种完全一样。
#
# 这一点值得停下来想想：大家常把记忆想成一个检索问题（怎么找出来），
# 但真正决定质量的往往是入口 —— **你一开始就存错了，再好的检索也救不回来。**


def memory_path(mode):
    """每个模式一个记忆文件，方便你跑完打开对比。"""
    return "memory_" + mode + ".json"


def load_memory(mode):
    """读记忆。文件不存在就当成空的。"""
    path = memory_path(mode)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_memory(mode, memories):
    """写记忆。注意这里用 indent=2 —— 是为了让你打开文件时看得舒服。"""
    with open(memory_path(mode), "w", encoding="utf-8") as f:
        json.dump(memories, f, ensure_ascii=False, indent=2)


def update_memory(mode, session_text, backend, verbose=True):
    """一次会话结束后更新记忆。★ 四种模式的全部差别就在这个函数里。"""

    if mode == "no_memory":
        # 什么都不做。下次来还是陌生人。
        return []

    if mode == "full_log":
        # 原样追加。零思考，也零信息损失 —— 代价是无限增长。
        memories = load_memory(mode)
        memories.append(session_text)
        save_memory(mode, memories)
        return memories

    # naive_extract 和 extracted：都让模型提取，**区别只有提示词一句**
    if mode == "naive_extract":
        extract_prompt = t("extract_naive")
    else:
        extract_prompt = t("extract_good")

    if verbose:
        print(t("extracting"), end="", flush=True)

    call_start = time.time()
    raw_text = complete(t("extract_input") + session_text, extract_prompt,
                        backend=backend)
    if verbose:
        print(t("took", sec=round(time.time() - call_start, 1)))

    reply = parse_json_reply(raw_text)
    new_items = reply.get("memories", [])
    if not isinstance(new_items, list):
        new_items = [str(new_items)]

    memories = load_memory(mode)
    memories.extend([str(x) for x in new_items])
    save_memory(mode, memories)
    return memories


def render_memory(memories):
    """把记忆拼成一段字符串，准备塞进上下文。四种模式这一步完全一样。"""
    if len(memories) == 0:
        return ""
    lines = []
    for i in range(len(memories)):
        lines.append("- " + memories[i])
    return "\n".join(lines)


# ==========================================================================
#  第 2 部分：新会话里怎么用记忆（Part 2）
# ==========================================================================


def build_system_prompt(memory_text):
    parts = [t("sys_answer")]
    if memory_text:
        parts.append(t("sys_with_memory", memory=memory_text))
    else:
        parts.append(t("sys_no_memory"))
    parts.append(t("sys_answer_protocol"))
    return "\n\n".join(parts)


# ==========================================================================
#  第 3 部分：主流程（Part 3）
# ==========================================================================


def run(question, mode="extracted", backend=None, verbose=True):

    # 每次跑之前先清掉旧记忆，保证四种模式起点一样（否则重复跑会越滚越多）
    if os.path.exists(memory_path(mode)):
        os.remove(memory_path(mode))

    desc = {"no_memory": t("desc_no_memory"), "full_log": t("desc_full_log"),
            "naive_extract": t("desc_naive_extract"),
            "extracted": t("desc_extracted")}[mode]

    if verbose:
        print("")
        print("=" * 68)
        print(t("mode_desc_line", desc=desc))
        print("=" * 68)

    # ---- 第 1 步：回放前两次会话，边放边更新记忆 ----
    if verbose:
        print("")
        print(t("phase1"))

    sessions = t("sessions")
    memories = []
    for i in range(len(sessions)):
        if verbose:
            print("")
            print("  " + t("session_label", n=i + 1) + "：")
            print("  「" + sessions[i] + "」")
        if mode == "no_memory":
            if verbose:
                print(t("no_update"))
            continue
        memories = update_memory(mode, sessions[i], backend, verbose=verbose)

    # ---- 记忆长什么样 + 量一量 ----
    memory_text = render_memory(memories)

    if verbose:
        print("")
        print(t("mem_head", file=memory_path(mode)))
        if memory_text:
            for line in memory_text.split("\n"):
                print("  │ " + line)
        else:
            print(t("mem_empty"))
        print(t("mem_foot"))

    size = len(memory_text)
    bar = "█" * min(40, size // 15)
    facts_n, facts_hit = count_markers(memory_text, FACT_MARKERS[LANG])
    noise_n, noise_hit = count_markers(memory_text, NOISE_MARKERS[LANG])
    stale_n, stale_hit = count_markers(memory_text, STALE_MARKERS[LANG])

    if verbose:
        print("")
        print(t("mem_size", n=size, bar=bar))
        print(t("mem_facts", n=facts_n, detail="、".join(facts_hit)))
        if noise_n > 0:
            print(t("mem_noise", n=noise_n, detail="、".join(noise_hit)))
        else:
            print(t("mem_noise_none"))
        if not memory_text:
            print(t("mem_stale_na"))
        elif stale_n > 0:
            print(t("mem_stale", detail="、".join(stale_hit)))
        else:
            print(t("mem_stale_none"))

    # ---- 第 2 步：新会话，装配上下文 ----
    system_prompt = build_system_prompt(memory_text)

    if verbose:
        print("")
        print(t("phase2"))

    if SHOW_PROMPT:
        print("")
        print("  ┌─── 实际发给模型的系统提示词 " + "-" * 30)
        for one_line in system_prompt.split("\n"):
            print("  │ " + one_line)
        print("  └" + "-" * 60)

    # ---- 第 3 步：回答 + 判定 ----
    if verbose:
        print("")
        print(t("phase3"))
        print("")
        print(t("asking"), end="", flush=True)

    call_start = time.time()
    raw_text = complete(question, system_prompt, backend=backend)
    if verbose:
        print(t("took", sec=round(time.time() - call_start, 1)))

    reply = parse_json_reply(raw_text)
    answer = reply.get("answer", raw_text.strip())

    answer_n, answer_hit = count_markers(answer, FACT_MARKERS[LANG])

    if verbose:
        print("")
        print(t("answer") + str(answer))
        print("")
        print(t("verdict_head"))
        for name_key, _words in FACT_MARKERS[LANG]:
            if t(name_key) in answer_hit:
                print(t("verdict_hit", desc=t(name_key)))
            else:
                print(t("verdict_miss", desc=t(name_key)))
        print("")

    return {"mode": mode, "size": size, "facts": facts_n, "noise": noise_n,
            "stale": stale_n, "answer_facts": answer_n, "answer": answer}


# ==========================================================================
#  第 4 部分：命令行入口（Part 4）
# ==========================================================================


def ask_for_task(mode):
    """让用户输入第 3 次会话的问题。故意不设默认值。"""
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


def print_rerun_hint(question, mode_arg):
    others = [m for m in MODES if m != mode_arg]
    if len(others) == 0:
        return
    print("")
    print(t("rerun_hint"))
    print('    python3 agent.py ' + others[0] + ' "' + question + '"')
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
        print(t("summary_size", n=r["size"]))
        print(t("summary_facts", n=r["facts"]))
        print(t("summary_noise", n=r["noise"]))
        if r["size"] == 0:
            print(t("summary_stale", s=t("stale_na")))
        elif r["stale"] > 0:
            print(t("summary_stale", s=t("stale_yes")))
        else:
            print(t("summary_stale", s=t("stale_no")))
        print(t("summary_answer", n=r["answer_facts"]))
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
        question = " ".join(sys.argv[2:])
    else:
        question = ask_for_task(mode_arg)

    try:
        backend = detect_backend()
    except RuntimeError:
        print("")
        print(t("no_backend_title"))
        print(t("no_backend_help"))
        sys.exit(1)

    print(t("backend") + backend)
    print(t("task_label") + question)

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
            results.append(run(question, mode=m, backend=backend))
        print_summary(results)
    else:
        run(question, mode=mode_arg, backend=backend)
        print_rerun_hint(question, mode_arg)
