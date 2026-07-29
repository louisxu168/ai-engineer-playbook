"""
实验 10-1：单 agent vs 多 agent —— 多几个到底换来了什么

「多 Agent 协作」是最容易被神化的一个词。这个实验把它拆成四种具体做法，
用**同一个任务、同一个模型**跑一遍，然后量三件事：

    找到了几个真问题（召回率）  ·  误报了几个  ·  花了几次模型调用

任务：审查 24 段代码，找出有安全问题的那些。
**恰好有 8 段有问题**，分布在 4 个类别里，每类一段明显、一段隐蔽。

    python3 agent.py                 # 打印用法说明
    python3 agent.py single          # 1 个 agent 看全部 24 段（基线）
    python3 agent.py chunked         # 按【数据】切成 4 份，4 个 agent 各看 6 段
    python3 agent.py specialists     # 按【关注点】切成 4 份，每人只找一类，但看全部 ★
    python3 agent.py critic          # 先找，再让另一个 agent 逐条复核 ★★
    python3 agent.py all             # 四种全跑 + 对比表

不需要 API key，也不联网。

★ 判据是机械的：标准答案是写死的 8 个 id，召回和误报都是集合运算。
  不靠模型判分，也不靠关键词 —— 和实验 3-2 是同一类判据。

详细讲解见 README.zh-CN.md（中文）/ README.md（英文）。
"""

import json
import sys
import time

from llm import complete, detect_backend, parse_json_reply
from snippets import (SNIPPETS, GROUND_TRUTH, CATEGORIES, CATEGORIES_EN,
                      render_snippets, all_ids)


# --------------------------------------------------------------------------
#  可以改的开关（Settings）
# --------------------------------------------------------------------------

LANG = "zh"          # "zh" | "en" —— 同时切换输出和发给模型的提示词

CHUNKS = 4           # chunked 模式切成几份

SHOW_PROMPT = False  # 改成 True 会打印真正发给模型的完整文本


MODES = [
    "single",       # 1 个 agent 看全部
    "chunked",      # 按【数据】切分：4 个 agent 各看 6 段
    "specialists",  # 按【关注点】切分：4 个 agent 各找一类，但都看全部 ★
    "critic",       # 找 + 复核两阶段 ★★
]


# --------------------------------------------------------------------------
#  所有对用户可见的文字，按语言分开放（包含发给模型的提示词）
# --------------------------------------------------------------------------

TEXT = {
    "zh": {
        "sys_reviewer": """你是一个代码安全审查员。下面是若干段代码，每段有一个编号（如 S01）。

请找出**有安全问题**的那些段。只关注这四类问题：

- **SQL 注入**：把外部输入拼进 SQL 字符串，而不是用参数化查询
- **硬编码密钥**：把 API key、token、密码直接写在代码里
- **路径穿越**：用外部输入拼文件路径，没有限制在允许的目录内
- **未校验输入**：直接使用外部传入的值，没有校验类型/范围/白名单

不是这四类的问题（性能、风格、命名）**一律不要报**。
没问题的代码**不要凑数**——误报是有代价的。

只输出 JSON：
  {"findings": [{"id": "<编号>", "category": "<SQLI|SECRET|PATH|INPUT>",
                 "why": "<一句话>"}]}""",

        "sys_specialist": """你是一个代码安全审查员，**这一轮只负责一类问题**：

**{category}**

下面是若干段代码，每段有一个编号。请**只找这一类问题**，
别的类型的问题（哪怕你看到了）**这一轮一律不报**。

请逐段看完，不要跳过。

只输出 JSON：
  {{"findings": [{{"id": "<编号>", "category": "{cat_key}", "why": "<一句话>"}}]}}""",

        "sys_critic": """你是一个代码安全审查的**复核员**。上一位审查员报了一些问题，
你的任务是**逐条判断哪些是真的、哪些是误报**。

标准：只有这四类算真问题 —— SQL 注入、硬编码密钥、路径穿越、未校验输入。
如果代码已经做了防护（参数化查询、从环境变量读密钥、路径做了限制、
输入做了白名单校验），那就**不是问题**，应该判为误报。

对每一条给出 keep（真问题）或 drop（误报）。

只输出 JSON：
  {"verdicts": [{"id": "<编号>", "decision": "<keep|drop>", "why": "<一句话>"}]}""",

        "ctx_code": "待审查的代码：",
        "ctx_findings": "上一位审查员报的问题：",

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
        "corpus": "素材：{n} 段代码，其中 {k} 段有问题（4 类 × 每类 1 明显 + 1 隐蔽）",
        "mode_line": "  模式：{mode}",
        "mode_desc": "  {desc}",
        "desc_single": "1 个 agent 看全部 24 段",
        "desc_chunked": "按【数据】切分：{n} 个 agent，各看 6 段",
        "desc_specialists": "按【关注点】切分：4 个 agent，各找一类，但都看全部 24 段",
        "desc_critic": "两阶段：先用 single 找一遍，再让复核员逐条判真伪",
        "agent_run": "  [agent {i}/{n}] {what}",
        "asking": "  正在问模型…",
        "took": " {sec} 秒",
        "found_line": "     报了 {n} 条：{ids}",
        "critic_head": "  ── 第 2 阶段：复核 ──",
        "critic_line": "     {id}  {decision}  {why}",
        "keep": "保留",
        "drop": "判为误报",
        "result_head": "  ─── 结果（对照 {k} 个标准答案）───",
        "hit_line": "  ✓ 找到：{ids}",
        "miss_line": "  ✗ 漏掉：{ids}",
        "fp_line": "  ☠ 误报：{ids}",
        "fp_none": "  ✓ 无误报",
        "recall_line": "  召回率：{n}/{k}  {bar}",
        "by_difficulty": "  其中：明显的 {ob}/4，隐蔽的 {sub}/4",
        "cost_line": "  模型调用：{n} 次",
        # --- 对比表 ---
        "summary_title": "对比结果",
        "summary_mode": "模式：{mode}",
        "summary_recall": "  召回：{n}/{k}    （明显 {ob}/4，隐蔽 {sub}/4）",
        "summary_fp": "  误报：{n}",
        "summary_calls": "  模型调用：{n} 次",
        "summary_verify": """
一张表怎么读：

  ★ 先比 chunked 和 specialists —— 这两个都是「4 个 agent」，**成本一样**，
    但切分的**依据**完全不同：

      chunked      按【数据】切：每人看 1/4 的代码，找全部 4 类问题
      specialists  按【关注点】切：每人看全部代码，只找 1 类问题

    **多 agent 的收益不来自「人多」，来自「切得对」。**
    切错了维度，你只是把同一个 agent 的工作量分摊了，什么也没多得到。

  ★ 再看 critic —— 它多花一次调用，买的不是召回，是**精确率**。
    如果前一步本来就没误报，这次调用就是纯浪费。

  ★ 最后看「隐蔽」那一列 —— 明显的问题谁都找得到，
    **多 agent 的价值全在隐蔽的那 4 个上**。""",
        "unknown_mode": "✗ 不认识的模式：",
        "exp_header": "# 实验 {i}/{total}：{mode}",
        "all_warning": "\n⚠️  all 模式要跑 4 种协作方式（共 10 次模型调用），大约 3～6 分钟。",
        "help": """
======================================================================
 实验 10-1：单 agent vs 多 agent —— 多几个到底换来了什么
======================================================================

同一个任务、同一个模型，四种协作方式。

任务：审查 24 段代码，找出有安全问题的。**恰好 8 段有问题**，
4 个类别 × 每类（1 段明显 + 1 段隐蔽）。

用法：
    python3 agent.py <模式>

【四种模式】
    single       1 个 agent 看全部 24 段（基线，1 次调用）
    chunked      按【数据】切成 4 份，4 个 agent 各看 6 段（4 次调用）
    specialists  按【关注点】切成 4 份，每人只找一类但看全部（4 次调用）★
    critic       先找一遍，再让复核员逐条判真伪（2 次调用）★★

【对比】
    all          四种全跑，最后打印对比表（约 3~6 分钟）

★ 判据是机械的：标准答案是写死的 8 个编号，召回和误报都是集合运算。

程序会告诉你：
    - 找到了几个（以及**明显的**几个、**隐蔽的**几个）
    - 误报了几个
    - 花了几次模型调用

★ 重点对比 chunked 和 specialists：**成本一模一样（都是 4 次调用）**，
  差别只在「按什么切」。这才是多 agent 真正的设计问题。

把文件开头的 LANG 改成 "en" 可切换成英文输出。
详细讲解见 README.zh-CN.md。
""",
    },
    "en": {
        "sys_reviewer": """You are a code security reviewer. Below are several code snippets, each with
an id (like S01).

Find the ones with **security problems**. Consider only these four categories:

- **SQL injection**: external input concatenated into SQL rather than parameterised
- **Hardcoded secret**: an API key, token or password written directly in the source
- **Path traversal**: a file path built from external input without confining it to
  an allowed directory
- **Unvalidated input**: an externally supplied value used directly with no
  type/range/allowlist check

Do **not** report anything outside those four (performance, style, naming).
Do **not** pad the list with clean code - false positives have a cost.

Reply with JSON only:
  {"findings": [{"id": "<id>", "category": "<SQLI|SECRET|PATH|INPUT>",
                 "why": "<one sentence>"}]}""",

        "sys_specialist": """You are a code security reviewer, and **this pass covers one category only**:

**{category}**

Below are several code snippets, each with an id. Report **only this category**.
Even if you notice other kinds of problem, **do not report them this pass**.

Read every snippet; don't skip any.

Reply with JSON only:
  {{"findings": [{{"id": "<id>", "category": "{cat_key}", "why": "<one sentence>"}}]}}""",

        "sys_critic": """You are the **verifier** for a code security review. A previous reviewer
reported some findings. Your job is to decide, **one by one**, which are real and
which are false positives.

The standard: only these four count - SQL injection, hardcoded secrets, path
traversal, unvalidated input. If the code already defends itself (parameterised
query, secret read from an environment variable, path confined, input checked
against an allowlist) then it is **not** a problem and should be dropped.

Give keep (real) or drop (false positive) for each.

Reply with JSON only:
  {"verdicts": [{"id": "<id>", "decision": "<keep|drop>", "why": "<one sentence>"}]}""",

        "ctx_code": "Code under review:",
        "ctx_findings": "What the previous reviewer reported:",

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
        "corpus": "Material: {n} snippets, {k} of them flawed (4 categories x 1 obvious + 1 subtle)",
        "mode_line": "  Mode: {mode}",
        "mode_desc": "  {desc}",
        "desc_single": "one agent reads all 24 snippets",
        "desc_chunked": "split by DATA: {n} agents, 6 snippets each",
        "desc_specialists": "split by CONCERN: 4 agents, one category each, all 24 snippets",
        "desc_critic": "two stages: run single, then have a verifier judge each finding",
        "agent_run": "  [agent {i}/{n}] {what}",
        "asking": "  asking the model...",
        "took": " {sec}s",
        "found_line": "     reported {n}: {ids}",
        "critic_head": "  -- stage 2: verification --",
        "critic_line": "     {id}  {decision}  {why}",
        "keep": "KEEP",
        "drop": "DROPPED as false positive",
        "result_head": "  --- result (against {k} known flaws) ---",
        "hit_line": "  ok found: {ids}",
        "miss_line": "  x  missed: {ids}",
        "fp_line": "  !  false positives: {ids}",
        "fp_none": "  ok no false positives",
        "recall_line": "  recall: {n}/{k}  {bar}",
        "by_difficulty": "  of which: obvious {ob}/4, subtle {sub}/4",
        "cost_line": "  model calls: {n}",
        "summary_title": "COMPARISON",
        "summary_mode": "mode: {mode}",
        "summary_recall": "  recall: {n}/{k}    (obvious {ob}/4, subtle {sub}/4)",
        "summary_fp": "  false positives: {n}",
        "summary_calls": "  model calls: {n}",
        "summary_verify": """
How to read this table:

  * First compare chunked with specialists - both are "4 agents" and cost
    **exactly the same**, but they split on completely different axes:

      chunked      split by DATA: each agent sees 1/4 of the code, hunts all 4 categories
      specialists  split by CONCERN: each agent sees all the code, hunts 1 category

    **Multi-agent's gain doesn't come from having more agents; it comes from
    splitting on the right axis.** Split wrong and you've merely divided one
    agent's workload without gaining anything.

  * Then look at critic - the extra call doesn't buy recall, it buys **precision**.
    If the previous stage had no false positives, that call was pure waste.

  * Finally look at the "subtle" column - anyone finds the obvious flaws.
    **Multi-agent's entire value lives in the 4 subtle ones.**""",
        "unknown_mode": "x unknown mode: ",
        "exp_header": "# Experiment {i}/{total}: {mode}",
        "all_warning": "\n!  'all' runs 4 collaboration patterns (10 model calls total), roughly 3-6 minutes.",
        "help": """
======================================================================
 Lab 10-1: One agent vs many - what do the extra agents actually buy?
======================================================================

Same task, same model, four collaboration patterns.

Task: review 24 code snippets and find the insecure ones. **Exactly 8 are
flawed**, across 4 categories, each with 1 obvious and 1 subtle instance.

Usage:
    python3 agent.py <mode>

THE FOUR MODES
    single       one agent reads all 24 (baseline, 1 call)
    chunked      split by DATA into 4, each agent sees 6 snippets (4 calls)
    specialists  split by CONCERN into 4, one category each, all snippets (4 calls) <-
    critic       find, then have a verifier judge each finding (2 calls)  <-<-

COMPARISON
    all          run all four, then print a table (3-6 minutes)

* The verdict is mechanical: ground truth is 8 hard-coded ids; recall and false
  positives are set arithmetic.

The program reports:
    - how many flaws were found (and how many **obvious** vs **subtle**)
    - how many false positives
    - how many model calls it cost

* The comparison that matters is chunked vs specialists: **identical cost
  (4 calls each)**, differing only in what they split on. That's the real
  multi-agent design question.

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
#  第 1 部分：一次审查（所有模式共用的最小单元）
# ==========================================================================


def review(system_prompt, subset, backend, verbose, label):
    """让一个 agent 审查一批片段，返回它报出来的 id 列表。"""
    prompt = t("ctx_code") + "\n\n" + render_snippets(subset)

    if SHOW_PROMPT:
        print("")
        print("  ┌─── 实际发给模型的内容 " + "-" * 38)
        for one_line in (system_prompt + "\n\n" + prompt).split("\n"):
            print("  │ " + one_line)
        print("  └" + "-" * 60)

    if verbose:
        print("  " + t("asking"), end="", flush=True)
    call_start = time.time()
    raw = complete(prompt, system_prompt, backend=backend)
    if verbose:
        print(t("took", sec=round(time.time() - call_start, 1)))

    findings = parse_json_reply(raw).get("findings", [])
    if not isinstance(findings, list):
        findings = []

    ids = []
    for one in findings:
        if isinstance(one, dict) and one.get("id"):
            snippet_id = str(one["id"]).strip().upper()
            if snippet_id not in ids:
                ids.append(snippet_id)

    if verbose:
        print(t("found_line", n=len(ids), ids=", ".join(ids) if ids else "—"))
    return ids


# ==========================================================================
#  第 2 部分：四种协作方式  ★★★ 本实验的核心 ★★★
# ==========================================================================
#
# ★ 请注意 chunked 和 specialists 的对比：
#   **它们的成本完全一样（都是 4 次调用）**，差别只在「按什么切」：
#
#     chunked      按【数据】切 —— 每个 agent 看 1/4 的代码，找全部 4 类问题
#     specialists  按【关注点】切 —— 每个 agent 看全部代码，只找 1 类问题
#
#   这才是多 agent 真正的设计问题：**不是"要不要多"，是"按什么维度拆"。**


def run_single(backend, verbose):
    """1 个 agent 看全部。这是基线。"""
    if verbose:
        print(t("agent_run", i=1, n=1, what="全部 24 段" if LANG == "zh" else "all 24 snippets"))
    ids = review(t("sys_reviewer"), None, backend, verbose, "single")
    return ids, 1


def run_chunked(backend, verbose):
    """按【数据】切分：把 24 段切成 4 份，每个 agent 看 6 段。

    这是很多人对「多 agent」的第一反应 —— 分头干活。
    但请想清楚：**每个 agent 看到的信息更少了。**
    """
    every = all_ids()
    size = len(every) // CHUNKS
    found = []
    for i in range(CHUNKS):
        subset = every[i * size:(i + 1) * size] if i < CHUNKS - 1 else every[i * size:]
        if verbose:
            print(t("agent_run", i=i + 1, n=CHUNKS,
                    what=(("看 " + subset[0] + "~" + subset[-1]) if LANG == "zh"
                          else ("snippets " + subset[0] + "-" + subset[-1]))))
        for one in review(t("sys_reviewer"), subset, backend, verbose, "chunk"):
            if one not in found:
                found.append(one)
    return found, CHUNKS


def run_specialists(backend, verbose):
    """按【关注点】切分：4 个 agent 各负责一类问题，但**都看全部 24 段**。

    ★ 成本和 chunked 一模一样（4 次调用），但每个 agent 看到的信息**没有减少**，
      减少的是它要同时操心的**事情种类**。
    """
    found = []
    keys = list(CATEGORIES.keys())
    table = CATEGORIES if LANG == "zh" else CATEGORIES_EN
    for i in range(len(keys)):
        key = keys[i]
        if verbose:
            print(t("agent_run", i=i + 1, n=len(keys), what=key))
        system_prompt = t("sys_specialist", category=table[key], cat_key=key)
        for one in review(system_prompt, None, backend, verbose, key):
            if one not in found:
                found.append(one)
    return found, len(keys)


def run_critic(backend, verbose):
    """两阶段：先用 single 找一遍，再让另一个 agent 逐条复核真伪。

    ★ 注意它买的是**精确率**，不是召回率 —— 复核员只能删，不能加。
      第一阶段漏掉的，第二阶段永远找不回来。
    """
    if verbose:
        print(t("agent_run", i=1, n=2, what="全部 24 段" if LANG == "zh" else "all 24 snippets"))
    candidates = review(t("sys_reviewer"), None, backend, verbose, "find")

    if len(candidates) == 0:
        return [], 1

    if verbose:
        print("")
        print(t("critic_head"))

    prompt = (t("ctx_code") + "\n\n" + render_snippets(candidates) + "\n\n"
              + t("ctx_findings") + " " + ", ".join(candidates))
    if verbose:
        print("  " + t("asking"), end="", flush=True)
    call_start = time.time()
    raw = complete(prompt, t("sys_critic"), backend=backend)
    if verbose:
        print(t("took", sec=round(time.time() - call_start, 1)))

    verdicts = parse_json_reply(raw).get("verdicts", [])
    if not isinstance(verdicts, list):
        verdicts = []

    kept = []
    decided = set()
    for one in verdicts:
        if not isinstance(one, dict) or not one.get("id"):
            continue
        snippet_id = str(one["id"]).strip().upper()
        decided.add(snippet_id)
        keep = str(one.get("decision", "")).lower().startswith("keep")
        if keep and snippet_id not in kept:
            kept.append(snippet_id)
        if verbose:
            print(t("critic_line", id=snippet_id,
                    decision=t("keep") if keep else t("drop"),
                    why=str(one.get("why", ""))[:50]))

    # 复核员没提到的，保守起见保留
    for one in candidates:
        if one not in decided and one not in kept:
            kept.append(one)

    return kept, 2


RUNNERS = {"single": run_single, "chunked": run_chunked,
           "specialists": run_specialists, "critic": run_critic}


# ==========================================================================
#  第 3 部分：判分（Part 3）
# ==========================================================================
#
# ★ 纯集合运算，不需要模型，也不靠关键词。
#   跟实验 3-2 的召回率是同一类判据 —— 本仓库里最可靠的那一类。


def score(found):
    hits = [x for x in GROUND_TRUTH if x in found]
    misses = [x for x in GROUND_TRUTH if x not in found]
    false_positives = [x for x in found if x not in GROUND_TRUTH]

    obvious = 0
    subtle = 0
    for snippet_id, _code, bad, _cat, difficulty in SNIPPETS:
        if bad and snippet_id in found:
            if difficulty in ("明显",):
                obvious = obvious + 1
            else:
                subtle = subtle + 1
    return hits, misses, false_positives, obvious, subtle


# ==========================================================================
#  第 4 部分：主流程（Part 4）
# ==========================================================================


def run(mode="single", backend=None, verbose=True):
    desc = {"single": t("desc_single"),
            "chunked": t("desc_chunked", n=CHUNKS),
            "specialists": t("desc_specialists"),
            "critic": t("desc_critic")}[mode]

    if verbose:
        print("")
        print("=" * 70)
        print(t("mode_line", mode=mode))
        print(t("mode_desc", desc=desc))
        print("=" * 70)
        print("")

    found, calls = RUNNERS[mode](backend, verbose)
    hits, misses, false_positives, obvious, subtle = score(found)

    if verbose:
        print("")
        print(t("result_head", k=len(GROUND_TRUTH)))
        print(t("hit_line", ids=", ".join(hits) if hits else "—"))
        print(t("miss_line", ids=", ".join(misses) if misses else "—"))
        if false_positives:
            print(t("fp_line", ids=", ".join(false_positives)))
        else:
            print(t("fp_none"))
        bar = "█" * (len(hits) * 4)
        print(t("recall_line", n=len(hits), k=len(GROUND_TRUTH), bar=bar))
        print(t("by_difficulty", ob=obvious, sub=subtle))
        print(t("cost_line", n=calls))
        print("")

    return {"mode": mode, "recall": len(hits), "fp": len(false_positives),
            "calls": calls, "obvious": obvious, "subtle": subtle}


# ==========================================================================
#  第 5 部分：命令行入口（Part 5）
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
        print(t("summary_mode", mode=r["mode"]))
        print(t("summary_recall", n=r["recall"], k=len(GROUND_TRUTH),
                ob=r["obvious"], sub=r["subtle"]))
        print(t("summary_fp", n=r["fp"]))
        print(t("summary_calls", n=r["calls"]))
    print(t("summary_verify"))


def _quiet_ctrl_c(exc_type, exc_value, tb):
    if exc_type is KeyboardInterrupt:
        print("")
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

    try:
        backend = detect_backend()
    except RuntimeError:
        print("")
        print(t("no_backend_title"))
        print(t("no_backend_help"))
        sys.exit(1)

    print(t("backend") + backend)
    print(t("corpus", n=len(SNIPPETS), k=len(GROUND_TRUTH)))

    if mode_arg == "all":
        print(t("all_warning"))
        results = []
        for mode_index in range(len(MODES)):
            m = MODES[mode_index]
            print("")
            print("#" * 70)
            print(t("exp_header", i=mode_index + 1, total=len(MODES), mode=m))
            print("#" * 70)
            results.append(run(mode=m, backend=backend))
        print_summary(results)
    else:
        run(mode=mode_arg, backend=backend)
