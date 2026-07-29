"""
实验 3-5：从零写检索 —— 为什么关键词搜不到该搜的东西

实验 3-1 结束在一个问题上：**记忆攒到几百条，全塞进上下文就装不下了。**

于是你需要「检索」：每次只取出**这次用得上**的那几条。

这个实验从零手写一个 BM25 检索器（不到 40 行，没有任何第三方库），
然后让你亲眼看到它**搜不到什么**：

    用户问：「帮我列一个成都出差期间的餐厅清单」
    该取出的记忆：「对花生过敏，误食会送医院」

    这两句话**一个字都不重合**。

关键词检索对此无能为力 —— 这不是 BM25 写得不好，是**关键词这条路本身的边界**。
这也正是 embedding（向量检索）被发明出来的原因。

本实验没有 embedding（那需要下载模型权重），但会给你另一条同样有效、
而且更贴近 agent 思路的解法：**让模型自己想清楚要搜什么**。

    python3 agent.py                 # 打印用法说明
    python3 agent.py stuff_all       # 不检索，全塞进去（天花板基准）
    python3 agent.py keyword         # BM25 取 top-5
    python3 agent.py expanded        # 先让模型扩展查询，再检索 ★
    python3 agent.py agentic         # 让 agent 自己反复搜 ★★
    python3 agent.py all             # 四种全跑 + 对比表

不需要 API key，也不联网。

★ 最关键的指标（召回率）**完全不需要模型就能算出来** —— 所以那部分结果
  每个人跑出来都一模一样，不受模型随机性影响。

详细讲解见 README.zh-CN.md（中文）/ README.md（英文）。
"""

import math
import re
import sys
import time

from llm import complete, detect_backend, parse_json_reply


# --------------------------------------------------------------------------
#  可以改的开关（Settings）
# --------------------------------------------------------------------------

LANG = "zh"          # "zh" | "en" —— 同时切换输出和发给模型的提示词

TOP_K = 5            # 每次检索取几条。改小改大都试试，看召回率怎么变

SHOW_PROMPT = False  # 改成 True 会打印每次真正发给模型的完整文本

AGENTIC_ROUNDS = 3   # agentic 模式最多搜几轮


MODES = [
    "stuff_all",   # 不检索，全部塞进上下文（天花板：召回率必然 100%）
    "keyword",     # BM25 取 top-K —— 会漏掉关键的东西
    "expanded",    # 先让模型把问题扩展成几个查询，再检索 ★
    "agentic",     # 让 agent 自己搜、自己看结果、自己决定再搜什么 ★★
]


# ==========================================================================
#  第 1 部分：记忆库（Part 1）
# ==========================================================================
#
# 这是实验 3-1 那个用户攒了半年的记忆。36 条。
#
# ⚠️ 36 条其实还塞得进上下文 —— 这是**故意**的。
#    正因为塞得下，stuff_all 才能当「天花板」用：
#    它的召回率必然是 100%，其他三种模式漏了什么，一比就知道。
#
#    真实系统里这个数字是几千几万条，那时候 stuff_all 这一列就不存在了。


MEMORIES = {
    "zh": [
        # --- 饮食（这次问题真正需要的在这里）---
        "对花生过敏，误食会送医院（严重过敏）",
        "完全不吃辣，一点辣都不能接受",
        "不喜欢香菜",
        "早饭习惯喝黑咖啡，不加糖不加奶",
        "乳糖不耐，喝牛奶会不舒服",
        # --- 工作 ---
        "职业：后端开发，主要写 Go 和 Python",
        "常驻工作地为上海浦东（2026 年 8 月起调岗生效）",
        "不再在北京工作",
        "工作日中午通常在公司楼下吃午饭",
        "每周三下午有团队例会，尽量不要安排别的事",
        "在用的笔记本是 2024 款 MacBook Pro，16 寸",
        "公司报销标准：出差住宿每晚不超过 600 元",
        # --- 行程 ---
        "2026-08-03 至 2026-08-09 期间赴成都出差三天，住在春熙路附近（临时行程，结束后失效）",
        "去年十月去过一次杭州出差，住在西湖边上，觉得性价比一般",
        "护照有效期到 2029 年 3 月",
        "坐飞机偏好靠过道的座位",
        "晕船，坐船超过半小时会难受",
        # --- 家庭与生活 ---
        "有一只叫「豆豆」的橘猫，五岁",
        "父母住在南京，每两个月回去一次",
        "住的小区叫「金桥新苑」，离地铁 9 号线走路 8 分钟",
        "健身卡在公司楼下那家，一周去三次",
        "不喜欢人多拥挤的场所",
        # --- 兴趣 ---
        "在学吉他，水平大概是能弹几首完整的曲子",
        "喜欢看科幻小说，最近在读《三体》第三部",
        "周末常去骑车，一次骑 40 公里左右",
        "不打游戏，觉得费时间",
        "在追一部叫《漫长的季节》的剧",
        # --- 健康 ---
        "颈椎不太好，久坐一小时就得起来活动",
        "对青霉素过敏",
        "近视 500 度，戴隐形眼镜",
        "作息偏早，晚上 11 点前睡",
        # --- 购物与消费 ---
        "买东西偏好用支付宝",
        "上个月买了一台扫地机器人，型号是石头 G20",
        "衣服尺码：上衣 L，裤子 32 腰",
        "不喜欢订阅制服务，能买断的尽量买断",
        "常用的外卖软件是美团",
    ],
    "en": [
        "Severely allergic to peanuts - ingestion means the ER",
        "Does not eat spicy food at all, not even mildly",
        "Dislikes coriander",
        "Drinks black coffee at breakfast, no sugar, no milk",
        "Lactose intolerant - milk causes discomfort",
        "Job: backend developer, mainly Go and Python",
        "Based in Shanghai Pudong (transfer effective August 2026)",
        "No longer works in Beijing",
        "Usually eats lunch downstairs from the office on weekdays",
        "Team meeting every Wednesday afternoon - keep it clear",
        "Laptop is a 2024 MacBook Pro, 16 inch",
        "Company expense policy: max 600 CNY per night for work travel",
        "Three-day work trip to Chengdu 2026-08-03 to 2026-08-09, staying near Chunxi Road (temporary, expires after)",
        "Went to Hangzhou for work last October, stayed by West Lake, thought it was poor value",
        "Passport valid until March 2029",
        "Prefers an aisle seat on flights",
        "Gets seasick - anything over half an hour on a boat is rough",
        "Has a five-year-old ginger cat called Doudou",
        "Parents live in Nanjing, visits every couple of months",
        "Lives in the Jinqiao Xinyuan complex, 8 minutes walk from metro line 9",
        "Gym membership is the one downstairs from the office, goes three times a week",
        "Dislikes crowded places",
        "Learning guitar - can play a few pieces all the way through",
        "Enjoys science fiction, currently reading the third Three-Body book",
        "Cycles most weekends, around 40 km a time",
        "Doesn't play games, considers it a waste of time",
        "Currently watching a show called The Long Season",
        "Bad neck - has to get up and move after an hour of sitting",
        "Allergic to penicillin",
        "Short-sighted, -5.00 dioptres, wears contact lenses",
        "Early riser, in bed before 11pm",
        "Prefers to pay with Alipay",
        "Bought a robot vacuum last month, a Roborock G20",
        "Clothing sizes: tops L, trousers 32 waist",
        "Dislikes subscriptions - buys outright where possible",
        "Usual food delivery app is Meituan",
    ],
}


# 这次问题真正**必须**取到的记忆（按上面列表里的下标）。
# 之所以能自动算召回率，是因为这几条是我们自己指定的标准答案。
TARGET_INDEXES = [0, 1, 12]     # 花生过敏 / 不吃辣 / 成都出差行程


# --------------------------------------------------------------------------
#  所有对用户可见的文字，按语言分开放（包含发给模型的提示词）
# --------------------------------------------------------------------------

TEXT = {
    "zh": {
        # --- 提示词 ---
        "sys_answer": "你是一个长期陪伴用户的生活助手。",
        "sys_with_memory": """下面是你**记得的关于这个用户的事**：
{memory}

回答时要主动照顾这些信息，不需要用户再说一遍。""",
        "sys_answer_protocol": """只输出一个 JSON 对象，不要有别的内容：
  {"answer": "<你的回答>"}""",
        "sys_expand": """你在帮一个助手检索「用户档案」。用户提了一个问题，
你要想清楚：**回答这个问题，需要知道用户的哪些方面？**

关键在于：**别只重复问题里的词。** 问题里通常不会出现真正该查的那个词。
比如问「推荐餐厅」，真正该查的是「过敏」「忌口」「口味」——
这些词一个都没出现在问题里。

请给出 4 到 6 个检索查询，覆盖不同方面。

只输出 JSON：{"queries": ["查询1", "查询2", ...]}""",
        "sys_agentic": """你在帮一个助手检索「用户档案」。你可以反复搜索，直到你认为
已经拿到了足够回答问题的信息。

注意：**用户档案里的措辞，通常和问题里的措辞完全不一样。**
搜「餐厅」大概率搜不到「对花生过敏」这条。想清楚该用什么词去搜。

每次回复一个 JSON：
  想继续搜：{"reasoning": "<一句话>", "queries": ["查询1", "查询2"]}
  搜够了：  {"reasoning": "<一句话>", "done": true}""",
        "agentic_state": """用户的问题是：{question}

你已经搜过这些查询：{used}

目前取到的记忆：
{found}

要继续搜吗？""",
        # --- 交互输入 ---
        "ask_task": "请输入用户这次要问什么（直接回车看例子）：\n> ",
        "examples_title": "几个可以直接复制的例子（第 1 个是文档里用的那个）：",
        "task_examples": [
            "帮我列一个成都出差期间的餐厅清单。",
            "我下周出差，帮我列个行前准备清单。",
            "周末想约朋友出去玩，有什么建议？",
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
        "task_label": "用户问：",
        "corpus_size": "记忆库：{n} 条",
        "mode_desc_line": "  检索策略：{desc}",
        "desc_stuff_all": "不检索 —— {n} 条全塞进上下文（天花板基准）",
        "desc_keyword": "BM25 取 top-{k}",
        "desc_expanded": "先让模型扩展查询，再对每个查询各取 top-{k}",
        "desc_agentic": "让 agent 自己反复搜，最多 {r} 轮",
        "phase_retrieve": "  ── 第 1 步：检索 ──",
        "phase_answer": "  ── 第 2 步：把取到的记忆拼进上下文，回答 ──",
        "expanding": "  正在让模型扩展查询…",
        "asking": "  正在问模型…",
        "took": " 用了 {sec} 秒",
        "queries_head": "  模型想出来的查询：",
        "query_line": "    • {q}",
        "agent_round": "  第 {n} 轮搜索",
        "thinking": "  [思考] ",
        "agent_done": "  agent 认为搜够了",
        "retrieved_head": "  ┌─ 取到的 {n} 条记忆（模型只能看到这些）───────",
        "retrieved_line": "  │ {mark} {text}",
        "retrieved_foot": "  └────────────────────────────────────────────",
        "recall_head": "  ─── 召回率：这次真正该取到的 3 条，取到了几条？ ───",
        "recall_hit": "  ✓ 取到了：{text}",
        "recall_miss": "  ✗ 漏掉了：{text}",
        "recall_score": "  召回率：{n}/3  {bar}",
        "answer": "  [回答] ",
        "verdict_head": "  ─── 回答有没有照顾到用户的情况 ───",
        "verdict_hit": "  ✓ 照顾到了：{desc}",
        "verdict_miss": "  ✗ 没照顾到：{desc}",
        "fact_allergy": "花生过敏",
        "fact_spice": "不吃辣",
        # --- 对比表 + 用法说明 ---
        "summary_title": "对比结果",
        "summary_mode": "模式：",
        "summary_n": "  取了 {n} 条记忆",
        "summary_recall": "  召回率：{n}/3",
        "summary_calls": "  模型调用：{n} 次",
        "summary_answer": "  回答照顾到：{n}/2",
        "summary_verify": """
一张表看懂四条路：
  stuff_all   全塞 —— 召回率必然 100%，但记忆一多就装不下
  keyword     BM25 —— 快、免费、可解释，但**搜不到不共享关键词的东西**
  expanded    模型先想「该搜什么」，再检索 —— 一次额外调用换回召回率
  agentic     模型边搜边看边调整 —— 最贵，但能处理它一开始想不到的情况

★ 核心结论：keyword 漏掉的那两条，和问题**一个字都不重合**。
  这不是 BM25 写得不好 —— 这是关键词检索的**结构性边界**。
  跨过这条边界只有两条路：换成向量检索，或者**让模型来搭那座桥**。""",
        "unknown_mode": "✗ 不认识的模式：",
        "exp_header": "# 实验 {i}/{total}：{mode}",
        "all_warning": "\n⚠️  all 模式要跑 4 个实验，不联网所以很快，大约 2～4 分钟。",
        "help": """
======================================================================
 实验 3-5：从零写检索 —— 为什么关键词搜不到该搜的东西
======================================================================

36 条用户记忆，同一个问题，四种检索策略。

用法：
    python3 agent.py <模式> ["用户的问题"]

【四种模式】
    stuff_all   不检索，全部塞进上下文（天花板基准，召回率必然 100%）
    keyword     从零手写的 BM25，取 top-5
    expanded    先让模型扩展查询，再检索 ★
    agentic     让 agent 自己反复搜 ★★

【对比】
    all         四种全跑，最后打印对比表（约 2~4 分钟，不联网）

程序会在每次跑完后直接告诉你：
    - 取到了哪几条记忆（原文列出来）
    - **召回率**：这次必须取到的 3 条，取到了几条
    - 花了几次模型调用
    - 最终回答有没有照顾到用户的情况

★ 召回率这个指标**不需要模型**就能算 —— 所以 stuff_all 和 keyword 两种模式
  的召回率结果是完全确定的，你跑十遍都一样。

建议顺序：
    1. 先跑 stuff_all，确认「全给它就一定答得对」
    2. 再跑 keyword —— **重点看漏掉了哪两条，以及为什么**
    3. 跑 expanded，看模型想出了什么查询词
    4. 最后 agentic，看它怎么自己纠正

把文件开头的 LANG 改成 "en" 可切换成英文输出。
TOP_K 改小改大都试试，看召回率怎么变。
详细讲解见 README.zh-CN.md。
""",
    },
    "en": {
        "sys_answer": "You are a long-term personal assistant for this user.",
        "sys_with_memory": """Here is **what you remember about this user**:
{memory}

Take these into account without making the user repeat themselves.""",
        "sys_answer_protocol": """Reply with ONE JSON object and nothing else:
  {"answer": "<your reply>"}""",
        "sys_expand": """You are helping an assistant search a user profile. The user asked a question.
Work out: **which aspects of this user do you need to know to answer it?**

The key point: **don't just repeat words from the question.** The word you actually
need to search for usually doesn't appear in the question at all. Asked to
"recommend a restaurant", what you really need is "allergy", "dietary", "taste" -
none of which are in the question.

Give 4 to 6 search queries covering different aspects.

Reply with JSON only: {"queries": ["query 1", "query 2", ...]}""",
        "sys_agentic": """You are helping an assistant search a user profile. You may search repeatedly
until you think you have enough to answer.

Note: **the profile's wording is usually nothing like the question's wording.**
Searching "restaurant" will very likely not surface "allergic to peanuts". Think
about what words to actually search for.

Reply with one JSON object each turn:
  to keep searching: {"reasoning": "<one sentence>", "queries": ["q1", "q2"]}
  when done:         {"reasoning": "<one sentence>", "done": true}""",
        "agentic_state": """The user's question is: {question}

Queries you've already run: {used}

Memories retrieved so far:
{found}

Search again?""",
        "ask_task": "Type what the user asks (Enter for examples):\n> ",
        "examples_title": "Copy one (#1 is the one used throughout the docs):",
        "task_examples": [
            "Put together a restaurant list for my Chengdu trip.",
            "I'm travelling for work next week - make me a packing checklist.",
            "I want to go out with friends this weekend, any suggestions?",
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
        "task_label": "User asks: ",
        "corpus_size": "Memory store: {n} items",
        "mode_desc_line": "  Retrieval strategy: {desc}",
        "desc_stuff_all": "none - paste all {n} items into the context (ceiling baseline)",
        "desc_keyword": "BM25, top-{k}",
        "desc_expanded": "model expands the query first, then top-{k} per query",
        "desc_agentic": "the agent searches on its own, up to {r} rounds",
        "phase_retrieve": "  -- Step 1: retrieve --",
        "phase_answer": "  -- Step 2: paste the retrieved memories into the context, answer --",
        "expanding": "  asking the model to expand the query...",
        "asking": "  asking the model...",
        "took": " took {sec}s",
        "queries_head": "  Queries the model came up with:",
        "query_line": "    - {q}",
        "agent_round": "  Search round {n}",
        "thinking": "  [thinking] ",
        "agent_done": "  the agent decided it has enough",
        "retrieved_head": "  +- {n} memories retrieved (all the model gets to see) ------",
        "retrieved_line": "  | {mark} {text}",
        "retrieved_foot": "  +--------------------------------------------",
        "recall_head": "  --- recall: of the 3 that genuinely matter, how many came back? ---",
        "recall_hit": "  ok retrieved: {text}",
        "recall_miss": "  x MISSED: {text}",
        "recall_score": "  recall: {n}/3  {bar}",
        "answer": "  [answer] ",
        "verdict_head": "  --- did the answer take the user into account? ---",
        "verdict_hit": "  ok honoured: {desc}",
        "verdict_miss": "  x missed: {desc}",
        "fact_allergy": "peanut allergy",
        "fact_spice": "no spicy food",
        "summary_title": "COMPARISON",
        "summary_mode": "mode: ",
        "summary_n": "  {n} memories retrieved",
        "summary_recall": "  recall: {n}/3",
        "summary_calls": "  model calls: {n}",
        "summary_answer": "  answer honoured: {n}/2",
        "summary_verify": """
Four approaches in one table:
  stuff_all   paste everything - recall is necessarily 100%, but it stops fitting
  keyword     BM25 - fast, free, explainable, but **cannot find what shares no
              keywords with the query**
  expanded    the model works out what to search for first - one extra call buys
              back the recall
  agentic     the model searches, reads, adjusts - priciest, but handles cases it
              couldn't anticipate up front

* The core finding: the two memories keyword missed share **not a single character**
  with the question. That isn't bad BM25 - it's the **structural boundary** of
  keyword retrieval. Only two ways across it: vector search, or **have the model
  build the bridge**.""",
        "unknown_mode": "x unknown mode: ",
        "exp_header": "# Experiment {i}/{total}: {mode}",
        "all_warning": "\n!  'all' runs 4 experiments. No network, so it's quick: 2-4 minutes.",
        "help": """
======================================================================
 Lab 3-5: Retrieval from scratch - why keywords miss what matters
======================================================================

36 user memories, one question, four retrieval strategies.

Usage:
    python3 agent.py <mode> ["the user's question"]

THE FOUR MODES
    stuff_all   no retrieval, paste everything (ceiling - recall is always 100%)
    keyword     BM25 written from scratch, top-5
    expanded    model expands the query first, then retrieve  <-
    agentic     the agent searches on its own, repeatedly  <-<-

COMPARISON
    all         run all four, then print a table (2-4 minutes, no network)

After each run the program tells you:
    - which memories came back (printed in full)
    - **recall**: of the 3 that genuinely matter, how many were retrieved
    - how many model calls it cost
    - whether the final answer took the user into account

* Recall needs no model to compute - so stuff_all's and keyword's recall numbers
  are fully deterministic. Run them ten times, same result.

Suggested order:
    1. Run stuff_all to confirm "given everything, it answers correctly"
    2. Run keyword - **focus on which two it missed, and why**
    3. Run expanded and look at the queries the model invented
    4. Finally agentic, and watch it correct itself

Set LANG = "zh" at the top of this file for Chinese output.
Try changing TOP_K up and down and watch recall move.
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
#  第 2 部分：从零写一个 BM25 检索器  ★★★ 本实验的核心 ★★★
# ==========================================================================
#
# BM25 是搜索引擎用了三十年的经典打分公式。它只做一件事：
#
#     给定一个查询，给每篇文档打个分，分高的排前面。
#
# 打分的直觉就三条：
#   1. 查询里的词在文档里出现得越多 → 分越高
#   2. 但这个词如果**到处都是**（比如「的」）→ 它不值钱，降权
#   3. 文档越长 → 词出现得多是应该的，要按长度归一化
#
# 下面不到 40 行就是全部。没有任何第三方库。


def tokenize(text):
    """把一段文字切成「词」。

    中文没有空格，正规做法要上分词器。这里用一个更简单也更稳的办法：
    **相邻两个字组成一个词**（叫 bigram / 二元组）。

        「花生过敏」 → 花生、生过、过敏

    这招不需要任何词典，对搜索场景效果出奇地好 ——
    真实搜索引擎处理中文时也常用它兜底。

    英文/数字就按空格和标点切，正常处理。
    """
    tokens = []

    # 英文单词和数字
    for word in re.findall(r"[a-zA-Z0-9]+", text.lower()):
        tokens.append(word)

    # 中日韩文字：取所有相邻两字组合
    cjk = re.findall(r"[一-鿿]+", text)
    for run in cjk:
        if len(run) == 1:
            tokens.append(run)
        for i in range(len(run) - 1):
            tokens.append(run[i:i + 2])

    return tokens


def build_index(documents):
    """预处理：把每篇文档切好词，并统计每个词在多少篇文档里出现过。

    返回 (每篇文档的词表, 每个词的文档频率, 平均文档长度)
    """
    doc_tokens = [tokenize(d) for d in documents]

    doc_freq = {}
    for tokens in doc_tokens:
        for w in set(tokens):                     # 用 set：同一篇里出现多次只算一次
            doc_freq[w] = doc_freq.get(w, 0) + 1

    avg_len = sum(len(x) for x in doc_tokens) / max(1, len(doc_tokens))
    return doc_tokens, doc_freq, avg_len


def bm25_scores(query, doc_tokens, doc_freq, avg_len):
    """给每篇文档算一个 BM25 分数。

    k1 和 b 是 BM25 的两个调节参数，这两个值是几十年下来的通用默认值。
    k1 控制「同一个词出现很多次」的收益衰减速度；b 控制长度归一化的强度。
    """
    k1 = 1.5
    b = 0.75
    n_docs = len(doc_tokens)
    query_tokens = tokenize(query)

    scores = []
    for i in range(n_docs):
        tokens = doc_tokens[i]
        doc_len = len(tokens)
        score = 0.0

        for w in set(query_tokens):
            tf = tokens.count(w)                 # 这个词在这篇文档里出现几次
            if tf == 0:
                continue

            df = doc_freq.get(w, 0)              # 这个词在几篇文档里出现过
            # IDF：出现得越普遍，权重越低。这是第 2 条直觉。
            idf = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))

            # 第 1 条 + 第 3 条：词频饱和 + 长度归一化
            norm = tf * (k1 + 1) / (tf + k1 * (1 - b + b * doc_len / avg_len))
            score = score + idf * norm

        scores.append(score)

    return scores


def search(query, memories, index, top_k):
    """检索：返回得分最高的 top_k 条记忆的**下标**（分数为 0 的不要）。"""
    doc_tokens, doc_freq, avg_len = index
    scores = bm25_scores(query, doc_tokens, doc_freq, avg_len)

    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    hits = []
    for i in ranked:
        if scores[i] <= 0:
            break
        hits.append(i)
        if len(hits) >= top_k:
            break
    return hits


# ==========================================================================
#  第 3 部分：四种检索策略（Part 3）
# ==========================================================================


def retrieve_stuff_all(question, memories, index, backend, verbose):
    """不检索。全部给它。这是天花板 —— 召回率必然 100%。"""
    return list(range(len(memories))), 0


def retrieve_keyword(question, memories, index, backend, verbose):
    """直接拿用户的问题当查询。最朴素、也最常见的做法。"""
    return search(question, memories, index, TOP_K), 0


def retrieve_expanded(question, memories, index, backend, verbose):
    """★ 先问模型：「回答这个问题，需要知道用户的哪些方面？」

    模型给出几个查询，每个查询各检索一次，结果取并集。

    这一步做的事，本质是**替关键词检索补上它缺的语义**：
    问题里没有「过敏」这个词，但模型知道推荐餐厅要考虑过敏。
    """
    if verbose:
        print(t("expanding"), end="", flush=True)

    call_start = time.time()
    raw_text = complete(question, t("sys_expand"), backend=backend)
    if verbose:
        print(t("took", sec=round(time.time() - call_start, 1)))

    queries = parse_json_reply(raw_text).get("queries", [])
    if not isinstance(queries, list) or len(queries) == 0:
        queries = [question]

    if verbose:
        print(t("queries_head"))
        for q in queries:
            print(t("query_line", q=str(q)))

    found = []
    for q in queries:
        for i in search(str(q), memories, index, TOP_K):
            if i not in found:
                found.append(i)
    return found, 1


def retrieve_agentic(question, memories, index, backend, verbose):
    """★★ 让 agent 自己搜：搜 → 看结果 → 决定还要不要再搜。

    和 expanded 的区别：expanded 是**一次性**想好所有查询；
    agentic 能**看到搜出来什么**再决定下一步 —— 这是实验 1-2 里那个循环。
    """
    found = []
    used = []
    calls = 0

    for round_number in range(1, AGENTIC_ROUNDS + 1):
        found_text = "\n".join(["- " + memories[i] for i in found])
        if not found_text:
            found_text = "（还没搜到任何东西）" if LANG == "zh" else "(nothing yet)"

        state = t("agentic_state", question=question,
                  used="、".join(used) if used else "—", found=found_text)

        if verbose:
            print("")
            print(t("agent_round", n=round_number))
            print("  " + t("asking"), end="", flush=True)

        call_start = time.time()
        raw_text = complete(state, t("sys_agentic"), backend=backend)
        calls = calls + 1
        if verbose:
            print(t("took", sec=round(time.time() - call_start, 1)))

        reply = parse_json_reply(raw_text)

        if verbose and reply.get("reasoning"):
            print(t("thinking") + str(reply["reasoning"]))

        if reply.get("done"):
            if verbose:
                print(t("agent_done"))
            break

        queries = reply.get("queries", [])
        if not isinstance(queries, list) or len(queries) == 0:
            break

        if verbose:
            print(t("queries_head"))
        for q in queries:
            if verbose:
                print(t("query_line", q=str(q)))
            used.append(str(q))
            for i in search(str(q), memories, index, TOP_K):
                if i not in found:
                    found.append(i)

    return found, calls


RETRIEVERS = {
    "stuff_all": retrieve_stuff_all,
    "keyword": retrieve_keyword,
    "expanded": retrieve_expanded,
    "agentic": retrieve_agentic,
}


# ==========================================================================
#  第 4 部分：判定（Part 4）
# ==========================================================================
#
# ★ 注意：召回率这个指标**完全不需要模型**。
#   我们自己指定了标准答案（TARGET_INDEXES），取到没取到是纯粹的集合运算。
#   所以 stuff_all 和 keyword 两种模式的召回率，你跑十遍都一样。
#
#   这一点很重要 —— 本仓库里大多数判据都靠关键词匹配，会误判（见实验 3-1）。
#   这个不会。


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


def count_markers(text, table):
    hit_names = []
    lowered = str(text).lower()
    for name_key, words in table:
        for w in words:
            if w.lower() in lowered:
                hit_names.append(t(name_key))
                break
    return len(hit_names), hit_names


# ==========================================================================
#  第 5 部分：主流程（Part 5）
# ==========================================================================


def run(question, mode="keyword", backend=None, verbose=True):
    memories = MEMORIES[LANG]
    index = build_index(memories)

    desc = {
        "stuff_all": t("desc_stuff_all", n=len(memories)),
        "keyword": t("desc_keyword", k=TOP_K),
        "expanded": t("desc_expanded", k=TOP_K),
        "agentic": t("desc_agentic", r=AGENTIC_ROUNDS),
    }[mode]

    if verbose:
        print("")
        print("=" * 68)
        print(t("mode_desc_line", desc=desc))
        print("=" * 68)
        print("")
        print(t("phase_retrieve"))
        print("")

    found, calls = RETRIEVERS[mode](question, memories, index, backend, verbose)

    # ---- 把取到的东西列出来 ----
    if verbose:
        print("")
        print(t("retrieved_head", n=len(found)))
        for i in found:
            mark = "★" if i in TARGET_INDEXES else " "
            print(t("retrieved_line", mark=mark, text=memories[i]))
        print(t("retrieved_foot"))

    # ---- 召回率（不需要模型）----
    recall_hits = [i for i in TARGET_INDEXES if i in found]

    if verbose:
        print("")
        print(t("recall_head"))
        for i in TARGET_INDEXES:
            if i in found:
                print(t("recall_hit", text=memories[i]))
            else:
                print(t("recall_miss", text=memories[i]))
        bar = "█" * (len(recall_hits) * 8)
        print(t("recall_score", n=len(recall_hits), bar=bar))

    # ---- 拼上下文，回答 ----
    memory_text = "\n".join(["- " + memories[i] for i in found])
    system_prompt = "\n\n".join([
        t("sys_answer"),
        t("sys_with_memory", memory=memory_text),
        t("sys_answer_protocol"),
    ])

    if verbose:
        print("")
        print(t("phase_answer"))

    if SHOW_PROMPT:
        print("")
        print("  ┌─── 实际发给模型的系统提示词 " + "-" * 30)
        for one_line in system_prompt.split("\n"):
            print("  │ " + one_line)
        print("  └" + "-" * 60)

    if verbose:
        print("")
        print(t("asking"), end="", flush=True)

    call_start = time.time()
    raw_text = complete(question, system_prompt, backend=backend)
    calls = calls + 1
    if verbose:
        print(t("took", sec=round(time.time() - call_start, 1)))

    answer = parse_json_reply(raw_text).get("answer", raw_text.strip())
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

    return {"mode": mode, "n_found": len(found), "recall": len(recall_hits),
            "calls": calls, "answer_facts": answer_n, "answer": answer}


# ==========================================================================
#  第 6 部分：命令行入口（Part 6）
# ==========================================================================


def ask_for_task(mode):
    """让用户输入问题。故意不设默认值。"""
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
        print(t("summary_n", n=r["n_found"]))
        print(t("summary_recall", n=r["recall"]))
        print(t("summary_calls", n=r["calls"]))
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
    print(t("corpus_size", n=len(MEMORIES[LANG])))
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
