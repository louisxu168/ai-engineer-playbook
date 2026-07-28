"""
后端适配层 —— 让实验在「没有 API key」的情况下也能跑。

+----------------------------------------------------------------------+
|  第一次学的话，这个文件可以完全跳过，不影响你理解 agent 的原理。      |
|                                                                       |
|                                                                       |
|  It exposes exactly four things:                                      |
|      complete(prompt, system)  -> the model's reply, as text          |
|      complete_hosted(prompt)   -> reply, with the PROVIDER's own web  |
|                                   search tool switched on             |
|      detect_backend()          -> which backend is in use             |
|      parse_json_reply(text)    -> pull the JSON object out as a dict  |
|                                                                       |
|  complete() and complete_hosted() are the whole point of lab 02:      |
|  the first forbids the provider's built-in tools so YOU own the loop, |
|  the second hands the entire job over to the provider.                |
|                                                                       |
|  Everything else in here is the plumbing for driving a CLI as if it   |
|  were an LLM API.                                                     |
+----------------------------------------------------------------------+

大部分学习者没有付费 API key，但很可能已经装了 Claude Code 或 Codex。
这两个 CLI 都能非交互调用，用的是你已有的订阅登录态。

探测顺序（可用环境变量 LAB_BACKEND 强制指定）：
    1. claude   -> Claude Code CLI      （订阅登录，零配置）
    2. codex    -> Codex CLI            （订阅登录，零配置）
    3. api      -> OpenAI 兼容 API      （需要 key，最快最省）

每个实验都自带一份这个文件的副本。**重复是故意的** ——
这才让「只下载一个文件夹就能跑」成立。
"""

import json
import os
import re
import shutil
import subprocess

TIMEOUT = 300

# 两个 CLI 后端共用。Claude Code 和 Codex 自带一堆内置工具（Bash、Read…）。
# 我们只想把它们当「纯文本补全」用，所以必须显式禁止 ——
# 否则模型会去调 Bash，然后撞上 --max-turns 直接失败。这是实测踩过的坑。
_NO_BUILTIN_TOOLS = (
    "\n\nIMPORTANT: do not invoke any built-in tool (Bash, Read, Write, Task, "
    "TodoWrite, ...). There is no filesystem and no shell here. Your entire "
    "reply is the single JSON object described above."
)


def detect_backend():
    """返回当前该用哪个后端。"""
    forced = os.getenv("LAB_BACKEND")
    if forced:
        return forced
    if shutil.which("claude"):
        return "claude"
    if shutil.which("codex"):
        return "codex"
    if _api_key():
        return "api"
    raise RuntimeError(
        "No usable backend. Install Claude Code or Codex, or set one of "
        "DEEPSEEK_API_KEY / OPENAI_API_KEY / OPENROUTER_API_KEY."
    )


def _api_key():
    for name in ("DEEPSEEK_API_KEY", "OPENROUTER_API_KEY", "OPENAI_API_KEY"):
        if os.getenv(name):
            return name
    return None


# --- the three backends ----------------------------------------------------

def _complete_claude(prompt, system, attempts=3):
    """Claude Code 无头模式。

    我们从不传 --continue/--resume，所以**每次调用都是无状态的**。
    这意味着上下文完全由我们自己拼 —— 而这正是消融实验需要的控制权。
    """
    last = ""
    for _ in range(attempts):
        proc = subprocess.run(
            ["claude", "-p", prompt,
             "--system-prompt", system + _NO_BUILTIN_TOOLS,
             "--max-turns", "3",
             "--exclude-dynamic-system-prompt-sections",
             "--output-format", "json"],
            capture_output=True, text=True, timeout=TIMEOUT,
        )
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            last = f"CLI output was not JSON (rc={proc.returncode}): {proc.stderr[:200]}"
            continue
        if payload.get("result"):
            return payload["result"]
        # 偶发：它还是去调了内置工具。这是不确定性问题，重试即可。
        last = f"no result (rc={proc.returncode}, stop={payload.get('stop_reason')})"
    raise RuntimeError(f"claude failed {attempts} times in a row: {last}")


def _complete_codex(prompt, system):
    """Codex 无头模式。codex exec 没有 --system-prompt，
    所以把 system 文本拼在提示词前面。"""
    proc = subprocess.run(
        ["codex", "exec", "--skip-git-repo-check", "--json",
         system + _NO_BUILTIN_TOOLS + "\n\n---\n\n" + prompt],
        capture_output=True, text=True, timeout=TIMEOUT,
    )
    text = None
    for line in proc.stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        item = event.get("item", {})
        if item.get("type") == "agent_message":
            text = item.get("text")          # 取最后一条 agent_message
    if text is None:
        raise RuntimeError(
            f"codex returned no message (rc={proc.returncode}): {proc.stderr[:200]}")
    return text


def _complete_api(prompt, system):
    """标准 OpenAI 兼容接口。最快最省，但要 key。"""
    from openai import OpenAI

    key_name = _api_key()
    base, model = {
        "DEEPSEEK_API_KEY": ("https://api.deepseek.com", "deepseek-v4-flash"),
        "OPENROUTER_API_KEY": ("https://openrouter.ai/api/v1", "deepseek/deepseek-v4-flash"),
        "OPENAI_API_KEY": (None, "gpt-5.5"),
    }[key_name]
    client = OpenAI(api_key=os.environ[key_name], base_url=base)
    resp = client.chat.completions.create(
        model=os.getenv("LAB_MODEL", model),
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return resp.choices[0].message.content


_BACKENDS = {"claude": _complete_claude, "codex": _complete_codex, "api": _complete_api}


def complete(prompt, system, backend=None):
    """一次无状态补全。返回模型回复的原始文本。"""
    backend = backend or detect_backend()
    if backend not in _BACKENDS:
        raise ValueError(f"unknown backend {backend!r}; expected one of {sorted(_BACKENDS)}")
    return _BACKENDS[backend](prompt, system)


# --- hosted mode: hand the whole job to the provider ----------------------
#
# Everything above forbids the provider's built-in tools, because in lab 01 we
# wanted to own the loop. Here we do the opposite: switch WebSearch ON and let
# the provider run search, loop and synthesis by itself.
#
# Compare the two functions. That contrast IS lab 02.


class HostedNotAvailable(Exception):
    """当前后端没有自带的联网搜索能力时抛出。"""


class HostedInterrupted(Exception):
    """厂商那侧的流程没跑完（比如撞上轮数上限）时抛出。

    这个失败本身很有教学意义：出问题时你**看不到它卡在哪一步**，
    只知道「没跑完」。这正是 hosted 模式的代价。
    """


def complete_hosted(prompt, max_turns=30, attempts=3):
    """Let the PROVIDER search the web and answer. No loop of our own.

    Returns (answer_text, turns) where `turns` is how many internal steps the
    provider took — one of the very few things it tells us about the run.
    """
    backend = detect_backend()

    if backend != "claude":
        raise HostedNotAvailable(
            f"hosted mode needs Claude Code's built-in WebSearch; "
            f"current backend is '{backend}'. Install Claude Code, or use "
            f"LAB_BACKEND=claude, or run the other modes."
        )

    # 和 _complete_claude 一样要重试：厂商那边跑几轮是不确定的，
    # 实测这个问题通常 4 轮就够，但偶尔会多搜几次。
    # max_turns 给足余量（没用到的轮次不花钱），再加重试兜底。
    last = ""
    for _ in range(attempts):
        proc = subprocess.run(
            ["claude", "-p", prompt,
             # 和 _complete_claude 唯一实质的区别：那边禁止所有内置工具，
             # 这边恰好放行一个 —— WebSearch。
             "--allowedTools", "WebSearch",
             "--max-turns", str(max_turns),
             "--output-format", "json"],
            capture_output=True, text=True, timeout=TIMEOUT,
        )
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            last = f"CLI 输出不是 JSON（rc={proc.returncode}）：{proc.stderr[:200]}"
            continue

        if payload.get("result"):
            return payload["result"], payload.get("num_turns")

        # stop_reason == "tool_use" 意味着它还想继续调工具，却撞上了 max_turns。
        last = (f"厂商跑到一半被打断了（rc={proc.returncode}，"
                f"stop={payload.get('stop_reason')}，"
                f"已跑 {payload.get('num_turns')} 轮 / 上限 {max_turns}）")

    raise HostedInterrupted(last)


def parse_json_reply(text):
    """把模型回复文本里的 JSON 对象抠出来。抠不到就返回 {}。

    这是走 CLI 后端不得不做的妥协：claude -p 和 codex exec 拿不到结构化的
    tool_use block，所以工具调用只能约定成一段 JSON 文本自己解析。
    想看真正的 structured tool calling，用 LAB_BACKEND=api。
    """
    match = re.search(r"\{.*\}", text or "", re.S)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
