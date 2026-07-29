"""
实验 5-1：Coding Agent 怎么改代码 —— 三种编辑格式，一样的模型

这是本仓库判据最硬的一个实验：**改完之后真的跑单元测试，过就是过，不过就是不过。**
没有关键词匹配，没有模型判分，没有解释空间。

一个 coding agent 最核心的工程决定，不是「用什么模型」，而是：

    **你让模型用什么格式把「改哪儿」说出来？**

有三种主流做法，真实产品各选了一种：

    whole_file      让它输出**整个文件**的新内容        —— 最笨，也最不会错
    search_replace  让它输出「把这段换成那段」          —— Aider / Claude Code 这一类
    line_range      让它输出「第 12 到 15 行换成……」    —— 最省 token，也最容易错位

这个实验让同一个模型、修同一个 bug，只换编辑格式，看：

    - 测试过了没有（★ 客观判据）
    - 花了几轮
    - 模型一共吐了多少字（成本）
    - 编辑应用失败了几次（格式本身的可靠性）

    python3 agent.py                 # 打印用法说明
    python3 agent.py whole_file      # 输出整个文件
    python3 agent.py search_replace  # 输出「把这段换成那段」★
    python3 agent.py line_range      # 输出「第 N 到 M 行换成……」
    python3 agent.py all             # 三种全跑 + 对比表

不需要 API key，也不联网。

⚠️ 安全说明：这个实验会**执行文件里的代码**（跑单元测试）。
   它跑的是一份从 workspace/ 复制出来的副本，模型只能改那份副本，
   而且**改不了测试文件**（程序会拦）。但它终究是在你机器上跑模型写的代码 ——
   和实验 1-3 一样，**这不是沙箱**。真实项目请用容器。

详细讲解见 README.zh-CN.md（中文）/ README.md（英文）。
"""

import json
import os
import shutil
import subprocess
import sys
import time

from llm import complete, detect_backend, parse_json_reply


# --------------------------------------------------------------------------
#  可以改的开关（Settings）
# --------------------------------------------------------------------------

LANG = "zh"          # "zh" | "en" —— 同时切换输出和发给模型的提示词

MAX_ROUNDS = 6       # 最多让它改几轮

TEST_TIMEOUT = 60    # 跑测试的超时（秒）

SHOW_PROMPT = False  # 改成 True 会打印每轮真正发给模型的完整文本


MODES = [
    "whole_file",      # 输出整个文件的新内容
    "search_replace",  # 输出「把这段换成那段」
    "line_range",      # 输出「第 N 到 M 行换成……」
]

SOURCE_FILE = "stats.py"       # 允许改的文件
TEST_FILE = "test_stats.py"    # ★ 不允许改的文件

# 两个难度不同的任务
TASKS = ["fix", "refactor"]

# refactor 任务额外用到的测试文件（平时不参与发现，跑 refactor 时才复制进去）
EXTRA_TEST_SOURCE = "extra_test_errors.py"
EXTRA_TEST_TARGET = "test_errors.py"


# --------------------------------------------------------------------------
#  所有对用户可见的文字，按语言分开放（包含发给模型的提示词）
# --------------------------------------------------------------------------

TEXT = {
    "zh": {
        "sys_role": """你是一个 coding agent。下面给你一个 Python 文件和它的测试失败信息，
请修好它，让所有测试通过。

规则：
- 只能修改 {source}，**不允许修改 {test}**（那是判分用的）
- 不要重写无关的代码，改动越小越好
- 不要改测试的期望值来「让它通过」""",
        # --- 三种编辑格式的说明（本实验的核心差异）---
        "fmt_whole_file": """输出这个 JSON：
  {{"reasoning": "<一句话说明你改了什么>",
   "path": "{source}",
   "content": "<这个文件修改后的【完整内容】，一个字都不能少>"}}

注意：content 必须是整个文件，不是片段。""",
        "fmt_search_replace": """输出这个 JSON：
  {{"reasoning": "<一句话说明你改了什么>",
   "path": "{source}",
   "edits": [{{"old": "<原文里要被替换掉的那一段，逐字照抄>",
              "new": "<替换成什么>"}}]}}

关键要求：
- old 必须和原文**逐字完全一致**，包括缩进和空行
- old 必须在文件里**只出现一次**（不唯一就多带几行上下文进来）
- 只改需要改的那几行，别把整个函数都塞进 old""",
        "fmt_line_range": """输出这个 JSON：
  {{"reasoning": "<一句话说明你改了什么>",
   "path": "{source}",
   "edits": [{{"start": <起始行号>, "end": <结束行号>,
              "new": "<这些行替换成什么>"}}]}}

关键要求：
- 行号从 1 开始，start 和 end 都**包含在内**
- 文件内容前面标了行号，但 new 里**不要写行号**
- 缩进要自己写对""",
        "task_fix": "任务：这个文件有一个 bug，测试抓到了。修好它，让所有测试通过。",
        "task_refactor": """任务：给这个文件加一个自定义异常类，并全面替换掉现有的 ValueError。

具体要求：
1. 定义 `class EmptyDataError(ValueError)`（必须是 ValueError 的子类，别破坏老代码）
2. 把**所有**「输入为空时抛 ValueError」的地方，改成抛 EmptyDataError
   —— 一共有 7 处，分布在 mean / median / mode / variance / data_range /
      percentile / normalize 里，**一处都不能漏**
3. 原来的报错文字保持不变
4. 顺便：文件里原本就有的那个 bug 也要修掉（测试同样会查）""",
        "ctx_file_head": "===== {path} =====",
        "ctx_test_head": "===== 测试失败信息 =====",
        "ctx_prev_head": "===== 上一轮你的改动出了问题 =====",
        "ctx_next": "现在输出你的 JSON 回复。",
        # --- 应用编辑时的错误信息 ---
        "err_no_path": "回复里没有 path 字段。",
        "err_bad_path": "只能修改 {source}，你想改的是 {got}。",
        "err_test_file": "☠ 不允许修改测试文件 {test}。请去修 {source} 里真正的 bug。",
        "err_no_content": "whole_file 模式必须给出 content 字段（完整文件内容）。",
        "err_no_edits": "必须给出 edits 数组，且至少有一条。",
        "err_old_missing": "第 {i} 条编辑的 old 在文件里**找不到**。请逐字照抄原文（注意缩进和空行）。",
        "err_old_ambiguous": "第 {i} 条编辑的 old 在文件里出现了 {n} 次，不唯一。请多带几行上下文让它唯一。",
        "err_bad_range": "第 {i} 条编辑的行号 {start}-{end} 不合法（文件共 {total} 行）。",
        "err_no_change": "这次改动之后文件内容没有任何变化。",
        # --- 交互输入 ---
        "ask_task": "这个实验的任务是固定的（修 stats.py 的 bug），直接回车开始：\n> ",
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
        "workspace": "工作副本：{path}（每次跑都是全新复制的，不会动 workspace/ 原件）",
        "mode_line": "  模式：{mode}      任务：{task}",
        "mode_desc": "  编辑格式：{desc}",
        "desc_whole_file": "让模型输出整个文件的新内容",
        "desc_search_replace": "让模型输出「把这段换成那段」",
        "desc_line_range": "让模型输出「第 N 到 M 行换成……」",
        "baseline": "  改之前：{passed}/{total} 个测试通过",
        "round_line": "  ── 第 {n} 轮 / 最多 {total} 轮 ──",
        "asking": "  正在问模型…",
        "took": " 用了 {sec} 秒",
        "thinking": "  [思路] ",
        "output_size": "  [输出] 模型这轮吐了 {n} 字",
        "apply_ok": "  ✓ 编辑已应用（{n} 处改动，文件 {before} → {after} 行）",
        "apply_fail": "  ✗ 编辑没能应用：{why}",
        "test_running": "  正在跑测试…",
        "test_pass": "  ✓ 测试全过（{total} 个）",
        "test_fail": "  ✗ 还有 {n} 个测试没过（共 {total} 个）",
        "cheated": "  ☠ 它改了测试文件 —— 这次不算通过",
        "verdict_head": "  ─── 结果 ───",
        "verdict_ok": "  ✓ 修好了：第 {n} 轮通过全部测试",
        "verdict_bad": "  ✗ 没修好：跑满 {n} 轮，测试仍未全过",
        "stats_line": "  轮数 {rounds}   模型输出共 {chars} 字   编辑失败 {fails} 次",
        "diff_head": "  ┌─ 它最终改了什么（和原件比）─────────────",
        "diff_line_add": "  │ + {line}",
        "diff_line_del": "  │ - {line}",
        "diff_none": "  │ （没有任何改动）",
        "diff_foot": "  └────────────────────────────────────────────",
        "diff_more": "  │ …（还有 {n} 行改动没显示）",
        # --- 对比表 ---
        "summary_title": "对比结果",
        "summary_mode": "模式：{mode}",
        "task_banner": "任务：{task}（{desc}）",
        "taskdesc_fix": "改 1 处，2 行",
        "taskdesc_refactor": "改 8 处，其中 7 处上下文几乎一模一样",
        "summary_result": "  测试：{r}",
        "summary_ok": "✓ 全过",
        "summary_bad": "✗ 没过",
        "summary_rounds": "  轮数：{n}",
        "summary_chars": "  模型输出：{n} 字",
        "summary_fails": "  编辑应用失败：{n} 次",
        "summary_verify": """
一张表怎么读：

  「测试」那一列是**客观的** —— 真的跑了 unittest，没有解释空间。

  然后比「模型输出」那一列 —— 这是三种格式的**成本差别**：
    whole_file      每轮都要重吐整个文件
    search_replace  只吐改动的那几行
    line_range      吐得更少（连原文都不用重复）

  最后比「编辑应用失败」那一列 —— 这是三种格式的**可靠性差别**：
    whole_file      基本不会失败（它就是整个文件）
    search_replace  old 抄错一个空格就失败
    line_range      行号数错一行就改错地方（而且**可能不报错**，直接改坏）

★ 注意最后一句：line_range 最危险的地方不是「失败」，是**它可能"成功"地改错地方**。
  whole_file 和 search_replace 出错时会明确报错，line_range 会安静地改坏。""",
        "unknown_mode": "✗ 不认识的模式：",
        "exp_header": "# 实验 {i}/{total}：{mode}",
        "all_warning": "\n⚠️  all 模式要跑 3 个实验，不联网，大约 2～5 分钟。",
        "help": """
======================================================================
 实验 5-1：Coding Agent 怎么改代码 —— 三种编辑格式
======================================================================

同一个模型、同一个 bug，只换「让模型怎么描述改动」这一件事。

用法：
    python3 agent.py <模式> [任务]

【两个任务】
    fix        （默认）修一个 bug —— 改 1 处、2 行。三种格式的**简单**情况
    refactor   加自定义异常并替换 7 处 ValueError —— 改 8 处，
               而且那 7 处的上下文**几乎一模一样**。这才是格式差异真正显现的地方 ★

【三种模式】
    whole_file      让它输出整个文件的新内容（最笨最稳）
    search_replace  让它输出「把这段换成那段」（Aider / Claude Code 这一类）★
    line_range      让它输出「第 N 到 M 行换成……」（最省 token，最容易错）

【对比】
    all             三种全跑，最后打印对比表（约 2~5 分钟，不联网）

★ 判据是**真的跑单元测试** —— 本仓库里最硬的判据，没有解释空间。

程序会告诉你：
    - 测试过了没有、第几轮过的
    - 模型一共吐了多少字（三种格式的成本差别）
    - 编辑应用失败了几次（三种格式的可靠性差别）
    - 它最终到底改了哪几行

⚠️ 这个实验会执行代码（跑测试）。它跑的是 workspace/ 的一份副本，
   模型改不了测试文件。但**这不是沙箱** —— 真实项目请用容器。

把文件开头的 LANG 改成 "en" 可切换成英文输出。
详细讲解见 README.zh-CN.md。
""",
    },
    "en": {
        "sys_role": """You are a coding agent. Below is a Python file and its failing test output.
Fix it so all tests pass.

Rules:
- You may only modify {source}. **You may NOT modify {test}** (that's the grader)
- Don't rewrite unrelated code; keep the change minimal
- Don't change the tests' expected values to "make them pass\"""",
        "fmt_whole_file": """Reply with this JSON:
  {{"reasoning": "<one sentence on what you changed>",
   "path": "{source}",
   "content": "<the COMPLETE contents of the file after your change>"}}

Note: content must be the entire file, not a fragment.""",
        "fmt_search_replace": """Reply with this JSON:
  {{"reasoning": "<one sentence on what you changed>",
   "path": "{source}",
   "edits": [{{"old": "<the exact snippet to replace, copied verbatim>",
              "new": "<what to replace it with>"}}]}}

Critical requirements:
- old must match the file **character for character**, including indentation and blank lines
- old must appear **exactly once** in the file (add surrounding lines if it isn't unique)
- Change only the lines that need changing; don't paste a whole function into old""",
        "fmt_line_range": """Reply with this JSON:
  {{"reasoning": "<one sentence on what you changed>",
   "path": "{source}",
   "edits": [{{"start": <first line>, "end": <last line>,
              "new": "<what those lines become>"}}]}}

Critical requirements:
- Line numbers start at 1; start and end are both **inclusive**
- The file below is shown with line numbers, but **do not put line numbers in new**
- Get the indentation right yourself""",
        "task_fix": "TASK: this file has a bug that the tests caught. Fix it so all tests pass.",
        "task_refactor": """TASK: add a custom exception class to this file and replace the existing ValueErrors with it.

Requirements:
1. Define `class EmptyDataError(ValueError)` (it MUST subclass ValueError so
   existing callers keep working)
2. Change **every** place that raises ValueError for empty input so it raises
   EmptyDataError instead - there are 7 of them, in mean / median / mode /
   variance / data_range / percentile / normalize. **Do not miss any.**
3. Keep the existing error message text unchanged
4. Also: the file already contains a bug - fix that too (the tests check it)""",
        "ctx_file_head": "===== {path} =====",
        "ctx_test_head": "===== FAILING TEST OUTPUT =====",
        "ctx_prev_head": "===== YOUR PREVIOUS EDIT HAD A PROBLEM =====",
        "ctx_next": "Now give your JSON reply.",
        "err_no_path": "No path field in the reply.",
        "err_bad_path": "You may only modify {source}; you targeted {got}.",
        "err_test_file": "! You may not modify the test file {test}. Go fix the real bug in {source}.",
        "err_no_content": "whole_file mode requires a content field (the complete file).",
        "err_no_edits": "You must supply an edits array with at least one entry.",
        "err_old_missing": "Edit {i}: its old text was **not found** in the file. Copy it verbatim (mind the indentation and blank lines).",
        "err_old_ambiguous": "Edit {i}: its old text appears {n} times, so it isn't unique. Include more surrounding lines.",
        "err_bad_range": "Edit {i}: line range {start}-{end} is invalid (the file has {total} lines).",
        "err_no_change": "The file is unchanged after applying that edit.",
        "ask_task": "This lab's task is fixed (fix the bug in stats.py). Press Enter to start:\n> ",
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
        "workspace": "Working copy: {path} (freshly copied each run; workspace/ is never touched)",
        "mode_line": "  Mode: {mode}      task: {task}",
        "mode_desc": "  Edit format: {desc}",
        "desc_whole_file": "the model emits the entire new file",
        "desc_search_replace": "the model emits 'replace this with that'",
        "desc_line_range": "the model emits 'lines N to M become ...'",
        "baseline": "  before the fix: {passed}/{total} tests passing",
        "round_line": "  -- Round {n} of at most {total} --",
        "asking": "  asking the model...",
        "took": " took {sec}s",
        "thinking": "  [plan] ",
        "output_size": "  [output] the model emitted {n} chars this round",
        "apply_ok": "  ok edit applied ({n} change(s), file {before} -> {after} lines)",
        "apply_fail": "  x  edit could not be applied: {why}",
        "test_running": "  running tests...",
        "test_pass": "  ok all {total} tests pass",
        "test_fail": "  x  {n} of {total} tests still failing",
        "cheated": "  ! it modified the test file - this does not count as passing",
        "verdict_head": "  --- result ---",
        "verdict_ok": "  ok FIXED: all tests passed in round {n}",
        "verdict_bad": "  x  NOT FIXED: {n} rounds used, tests still failing",
        "stats_line": "  rounds {rounds}   model output {chars} chars   failed edits {fails}",
        "diff_head": "  +- what it actually changed (vs the original) ------",
        "diff_line_add": "  | + {line}",
        "diff_line_del": "  | - {line}",
        "diff_none": "  | (no changes at all)",
        "diff_foot": "  +--------------------------------------------",
        "diff_more": "  | ...({n} more changed lines not shown)",
        "summary_title": "COMPARISON",
        "summary_mode": "mode: {mode}",
        "task_banner": "task: {task} ({desc})",
        "taskdesc_fix": "1 site, 2 lines",
        "taskdesc_refactor": "8 sites, 7 of which have near-identical context",
        "summary_result": "  tests: {r}",
        "summary_ok": "ok all pass",
        "summary_bad": "x failing",
        "summary_rounds": "  rounds: {n}",
        "summary_chars": "  model output: {n} chars",
        "summary_fails": "  failed edit applications: {n}",
        "summary_verify": """
How to read this table:

  The "tests" column is **objective** - unittest actually ran. No room for
  interpretation.

  Then compare "model output" - that's the **cost** difference between formats:
    whole_file      re-emits the entire file every round
    search_replace  emits only the changed lines
    line_range      emits even less (it doesn't repeat the original text)

  Then compare "failed edit applications" - the **reliability** difference:
    whole_file      basically can't fail (it IS the file)
    search_replace  one wrong space in old and it fails
    line_range      one miscounted line and it edits the wrong place - and it
                    **may not report an error at all**

* That last point matters most: line_range's danger isn't failing, it's
  **"succeeding" at editing the wrong place.** whole_file and search_replace
  fail loudly; line_range corrupts quietly.""",
        "unknown_mode": "x unknown mode: ",
        "exp_header": "# Experiment {i}/{total}: {mode}",
        "all_warning": "\n!  'all' runs 3 experiments. No network; roughly 2-5 minutes.",
        "help": """
======================================================================
 Lab 5-1: How a coding agent edits code - three edit formats
======================================================================

Same model, same bug. The only thing that changes is how the model is asked
to describe its edit.

Usage:
    python3 agent.py <mode> [task]

TWO TASKS
    fix        (default) fix one bug - 1 site, 2 lines. The EASY case for all
               three formats
    refactor   add a custom exception and replace 7 ValueErrors - 8 sites, and
               7 of them have near-identical context. This is where the formats
               actually diverge  <-

THE THREE MODES
    whole_file      emit the entire new file (dumbest, most reliable)
    search_replace  emit 'replace this with that' (Aider / Claude Code style)  <-
    line_range      emit 'lines N to M become ...' (cheapest, most fragile)

COMPARISON
    all             run all three, then print a table (2-5 minutes, no network)

* The verdict is a REAL unittest run - the hardest verdict in this repo.

The program reports:
    - whether the tests pass, and in which round
    - how many characters the model emitted (the cost difference)
    - how many edits failed to apply (the reliability difference)
    - which lines it actually changed

⚠️ This lab EXECUTES code (it runs the tests). It runs a copy of workspace/,
   and the model cannot modify the test file. But **this is not a sandbox** -
   use a container for real work.

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
#  第 1 部分：工作副本（Part 1）
# ==========================================================================
#
# 每次跑都从 workspace/ 复制一份全新的出来，在副本上改。
# 好处有两个：
#   1. 三种模式的起点完全一样，比较才成立
#   2. 你的 workspace/ 原件永远不会被模型改坏


HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(HERE, "workspace")


def make_workspace(mode, task="fix"):
    """复制一份干净的工作副本，返回它的路径。

    refactor 任务会多放一个测试文件进去 —— 那 9 个测试只有改完 7 处才会全过。
    """
    target = os.path.join(HERE, ".run_" + mode + "_" + task)
    if os.path.exists(target):
        shutil.rmtree(target)
    shutil.copytree(TEMPLATE_DIR, target)

    # extra_test_errors.py 不匹配 unittest 的 test*.py 发现规则，所以平时不会被跑到。
    # refactor 任务把它复制成 test_errors.py，它才开始生效。
    if task == "refactor":
        shutil.copy(os.path.join(target, EXTRA_TEST_SOURCE),
                    os.path.join(target, EXTRA_TEST_TARGET))
    return target


def read_source(workspace):
    with open(os.path.join(workspace, SOURCE_FILE), "r", encoding="utf-8") as f:
        return f.read()


def write_source(workspace, text):
    with open(os.path.join(workspace, SOURCE_FILE), "w", encoding="utf-8") as f:
        f.write(text)


def with_line_numbers(text):
    """给每行加上行号 —— 只有 line_range 模式需要。"""
    lines = text.split("\n")
    out = []
    for i in range(len(lines)):
        out.append(str(i + 1).rjust(4) + " | " + lines[i])
    return "\n".join(out)


# ==========================================================================
#  第 2 部分：跑测试  ★ 本实验的判据 ★
# ==========================================================================
#
# 就是真的 subprocess 跑一遍 `python3 -m unittest`。
# 返回 (通过了吗, 通过数, 总数, 原始输出)。
#
# ⚠️ 这一步会**执行文件里的代码**。模型改过的代码也会被执行。
#    程序限制了它只能改 stats.py、改不了测试，但这**不构成沙箱**。


def run_tests(workspace):
    try:
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "-v"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=TEST_TIMEOUT,
        )
        output = result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, 0, 0, "测试超时（可能死循环了）" if LANG == "zh" else "tests timed out (infinite loop?)"

    # unittest -v 每个测试打一行，结尾是 ok / FAIL / ERROR
    total = output.count(" ... ok") + output.count(" ... FAIL") + output.count(" ... ERROR")
    passed = output.count(" ... ok")
    ok = ("OK" in output.split("\n")[-2:][0] or output.rstrip().endswith("OK"))
    ok = ok and passed == total and total > 0
    return ok, passed, total, output


def short_test_output(output, limit=1600):
    """测试输出可能很长，截一段有用的喂回给模型。"""
    if len(output) <= limit:
        return output
    return output[:limit] + "\n…（输出已截断）" if LANG == "zh" \
        else output[:limit] + "\n...(output truncated)"


# ==========================================================================
#  第 3 部分：三种编辑格式怎么应用  ★★★ 本实验的核心 ★★★
# ==========================================================================
#
# 三个函数，对应三种格式。每个都返回 (新的文件内容, 出错原因)。
# 出错原因是 None 就表示应用成功。
#
# ★ 请注意每种格式**能出什么错**，这才是它们真正的差别：
#
#   whole_file      几乎不会出错 —— 它给的就是最终结果
#   search_replace  会出错，但**错了一定报错**（找不到 / 不唯一）
#   line_range      会出错，而且**可能不报错** —— 行号偏一行，
#                   它照样能"成功"应用，只是改错了地方


def apply_whole_file(original, reply):
    content = reply.get("content")
    if not isinstance(content, str) or content.strip() == "":
        return None, t("err_no_content")
    return content, None


def apply_search_replace(original, reply):
    edits = reply.get("edits")
    if not isinstance(edits, list) or len(edits) == 0:
        return None, t("err_no_edits")

    text = original
    for i in range(len(edits)):
        one = edits[i]
        old = one.get("old")
        new = one.get("new", "")
        if not isinstance(old, str) or old == "":
            return None, t("err_old_missing", i=i + 1)

        count = text.count(old)
        if count == 0:
            return None, t("err_old_missing", i=i + 1)
        if count > 1:
            return None, t("err_old_ambiguous", i=i + 1, n=count)

        text = text.replace(old, new, 1)

    return text, None


def apply_line_range(original, reply):
    edits = reply.get("edits")
    if not isinstance(edits, list) or len(edits) == 0:
        return None, t("err_no_edits")

    lines = original.split("\n")

    # 从后往前改，否则前面的改动会让后面的行号全部错位
    # —— 这本身就是 line_range 格式麻烦的地方之一
    ordered = sorted(range(len(edits)),
                     key=lambda i: edits[i].get("start", 0), reverse=True)

    for i in ordered:
        one = edits[i]
        start = one.get("start")
        end = one.get("end")
        new = one.get("new", "")
        if not isinstance(start, int) or not isinstance(end, int) \
                or start < 1 or end < start or end > len(lines):
            return None, t("err_bad_range", i=i + 1, start=start, end=end,
                           total=len(lines))
        lines[start - 1:end] = new.split("\n")

    return "\n".join(lines), None


APPLIERS = {
    "whole_file": apply_whole_file,
    "search_replace": apply_search_replace,
    "line_range": apply_line_range,
}


# ==========================================================================
#  第 4 部分：防作弊（Part 4）
# ==========================================================================
#
# 为什么要防？因为「把测试改成期望错误答案」是让测试通过最省事的办法，
# 而且 AI 写代码时**真的会这么干**。
#
# 我们做两件事：
#   1. 在提示词里明说不许改（第 1 部分的 sys_role）
#   2. 在代码里拦住（下面这个函数）
#
# ★ 这正好呼应实验 4-1 的结论：**约束能在接口层面拦住的，别只写在提示词里。**


def check_path(reply):
    """返回出错原因；None 表示这个 path 没问题。"""
    path = reply.get("path")
    if not isinstance(path, str) or path.strip() == "":
        return t("err_no_path")
    name = os.path.basename(path.strip())
    if name in (TEST_FILE, EXTRA_TEST_TARGET, EXTRA_TEST_SOURCE):
        return t("err_test_file", test=TEST_FILE, source=SOURCE_FILE)
    if name != SOURCE_FILE:
        return t("err_bad_path", source=SOURCE_FILE, got=path)
    return None


def test_file_untouched(workspace):
    """再保险一道：比对所有测试文件有没有被改过。"""
    pairs = [(TEST_FILE, TEST_FILE)]
    if os.path.exists(os.path.join(workspace, EXTRA_TEST_TARGET)):
        pairs.append((EXTRA_TEST_SOURCE, EXTRA_TEST_TARGET))
    for template_name, run_name in pairs:
        with open(os.path.join(TEMPLATE_DIR, template_name),
                  "r", encoding="utf-8") as f:
            original = f.read()
        with open(os.path.join(workspace, run_name),
                  "r", encoding="utf-8") as f:
            current = f.read()
        if original != current:
            return False
    return True


# ==========================================================================
#  第 5 部分：拼上下文（Part 5）
# ==========================================================================


def build_system_prompt(mode):
    fmt_key = "fmt_" + mode
    return "\n\n".join([
        t("sys_role", source=SOURCE_FILE, test=TEST_FILE),
        t(fmt_key, source=SOURCE_FILE),
    ])


def build_prompt(mode, source_text, test_output, last_error, task="fix"):
    shown = with_line_numbers(source_text) if mode == "line_range" else source_text

    parts = [t("task_" + task), ""]
    parts.append(t("ctx_file_head", path=SOURCE_FILE))
    parts.append(shown)
    parts.append("")
    parts.append(t("ctx_test_head"))
    parts.append(short_test_output(test_output))
    if last_error:
        parts.append("")
        parts.append(t("ctx_prev_head"))
        parts.append(last_error)
    parts.append("")
    parts.append(t("ctx_next"))
    return "\n".join(parts)


def show_diff(original, current, verbose=True, limit=14):
    """把改动列出来 —— 让你一眼看到它到底动了哪几行。"""
    import difflib
    a = original.split("\n")
    b = current.split("\n")
    shown = 0
    printed_any = False
    print(t("diff_head"))
    for line in difflib.unified_diff(a, b, lineterm="", n=0):
        if line.startswith("---") or line.startswith("+++") or line.startswith("@@"):
            continue
        if shown >= limit:
            remaining = 0
            for rest in difflib.unified_diff(a, b, lineterm="", n=0):
                if rest.startswith(("+", "-")) and not rest.startswith(("---", "+++")):
                    remaining = remaining + 1
            print(t("diff_more", n=max(0, remaining - limit)))
            break
        if line.startswith("+"):
            print(t("diff_line_add", line=line[1:]))
            shown = shown + 1
            printed_any = True
        elif line.startswith("-"):
            print(t("diff_line_del", line=line[1:]))
            shown = shown + 1
            printed_any = True
    if not printed_any:
        print(t("diff_none"))
    print(t("diff_foot"))


# ==========================================================================
#  第 6 部分：主循环（Part 6）
# ==========================================================================


def run(mode="search_replace", task="fix", backend=None, verbose=True):
    workspace = make_workspace(mode, task)
    original_source = read_source(workspace)

    desc = {"whole_file": t("desc_whole_file"),
            "search_replace": t("desc_search_replace"),
            "line_range": t("desc_line_range")}[mode]

    if verbose:
        print("")
        print("=" * 68)
        print(t("mode_line", mode=mode, task=task))
        print(t("mode_desc", desc=desc))
        print("=" * 68)
        print("")
        print(t("workspace", path=os.path.basename(workspace)))

    ok, passed, total, test_output = run_tests(workspace)
    if verbose:
        print(t("baseline", passed=passed, total=total))

    system_prompt = build_system_prompt(mode)
    total_chars = 0
    apply_fails = 0
    last_error = None
    success_round = None
    cheated = False

    for round_number in range(1, MAX_ROUNDS + 1):
        source_text = read_source(workspace)
        prompt = build_prompt(mode, source_text, test_output, last_error, task)

        if verbose:
            print("")
            print(t("round_line", n=round_number, total=MAX_ROUNDS))

        if SHOW_PROMPT:
            print("")
            print("  ┌─── 实际发给模型的内容 " + "-" * 38)
            for one_line in prompt.split("\n"):
                print("  │ " + one_line)
            print("  └" + "-" * 60)

        if verbose:
            print(t("asking"), end="", flush=True)

        call_start = time.time()
        raw_text = complete(prompt, system_prompt, backend=backend)
        if verbose:
            print(t("took", sec=round(time.time() - call_start, 1)))

        total_chars = total_chars + len(raw_text)
        reply = parse_json_reply(raw_text)

        if verbose:
            if reply.get("reasoning"):
                print(t("thinking") + str(reply["reasoning"]))
            print(t("output_size", n=len(raw_text)))

        # --- 先查 path（防作弊）---
        last_error = check_path(reply)
        if last_error:
            apply_fails = apply_fails + 1
            if verbose:
                print(t("apply_fail", why=last_error))
            continue

        # --- 应用编辑 ---
        new_text, why = APPLIERS[mode](source_text, reply)
        if why:
            apply_fails = apply_fails + 1
            last_error = why
            if verbose:
                print(t("apply_fail", why=why))
            continue

        if new_text == source_text:
            apply_fails = apply_fails + 1
            last_error = t("err_no_change")
            if verbose:
                print(t("apply_fail", why=last_error))
            continue

        write_source(workspace, new_text)
        last_error = None

        if verbose:
            n_edits = 1 if mode == "whole_file" else len(reply.get("edits", []))
            print(t("apply_ok", n=n_edits,
                    before=len(source_text.split("\n")),
                    after=len(new_text.split("\n"))))
            print(t("test_running"))

        ok, passed, total, test_output = run_tests(workspace)

        if not test_file_untouched(workspace):
            cheated = True
            if verbose:
                print(t("cheated"))
            break

        if verbose:
            if ok:
                print(t("test_pass", total=total))
            else:
                print(t("test_fail", n=max(0, total - passed), total=total))

        if ok:
            success_round = round_number
            break

    if verbose:
        print("")
        print(t("verdict_head"))
        if success_round is not None and not cheated:
            print(t("verdict_ok", n=success_round))
        else:
            print(t("verdict_bad", n=MAX_ROUNDS))
        print(t("stats_line", rounds=MAX_ROUNDS if success_round is None
                else success_round, chars=total_chars, fails=apply_fails))
        print("")
        show_diff(original_source, read_source(workspace))
        print("")

    return {"mode": mode, "task": task,
            "ok": success_round is not None and not cheated,
            "rounds": success_round if success_round is not None else MAX_ROUNDS,
            "chars": total_chars, "fails": apply_fails}


# ==========================================================================
#  第 7 部分：命令行入口（Part 7）
# ==========================================================================


def print_help():
    print(t("help"))


def print_summary(results, task):
    print("")
    print("=" * 70)
    print(t("summary_title"))
    print("=" * 70)
    print(t("task_banner", task=task, desc=t("taskdesc_" + task)))
    for r in results:
        print("")
        print(t("summary_mode", mode=r["mode"]))
        print(t("summary_result",
                r=t("summary_ok") if r["ok"] else t("summary_bad")))
        print(t("summary_rounds", n=r["rounds"]))
        print(t("summary_chars", n=r["chars"]))
        print(t("summary_fails", n=r["fails"]))
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

    # 第二个参数是任务：fix（默认，改 1 处）或 refactor（改 8 处）
    task_arg = "fix"
    if len(sys.argv) > 2:
        task_arg = sys.argv[2]
        if task_arg not in TASKS:
            print("")
            print(t("unknown_mode") + task_arg + "  (fix | refactor)")
            sys.exit(1)

    try:
        backend = detect_backend()
    except RuntimeError:
        print("")
        print(t("no_backend_title"))
        print(t("no_backend_help"))
        sys.exit(1)

    print(t("backend") + backend)

    if mode_arg == "all":
        print(t("all_warning"))
        results = []
        for mode_index in range(len(MODES)):
            m = MODES[mode_index]
            print("")
            print("#" * 70)
            print(t("exp_header", i=mode_index + 1, total=len(MODES), mode=m))
            print("#" * 70)
            results.append(run(mode=m, task=task_arg, backend=backend))
        print_summary(results, task_arg)
    else:
        run(mode=mode_arg, task=task_arg, backend=backend)
