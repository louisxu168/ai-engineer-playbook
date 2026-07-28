"""
后端适配层：让实验在「没有 API key」的情况下也能跑。

┌──────────────────────────────────────────────────────────────────────┐
│  第一次学的话，这个文件可以完全跳过，不影响你理解 agent 的原理。       │
│                                                                      │
│  你只需要知道它对外提供了三个函数：                                   │
│      complete(提示词, 系统提示词)  -> 模型回复的文本                  │
│      detect_backend()             -> 当前用的是哪个后端              │
│      parse_json_reply(文本)        -> 把文本里的 JSON 抠成字典         │
│                                                                      │
│  这里面全是「怎么把命令行工具当大模型用」的脏活，跟 agent 原理无关。   │
└──────────────────────────────────────────────────────────────────────┘

大部分学习者手里没有付费 API key，但很可能已经装了 Claude Code 或 Codex。
这两个 CLI 都能非交互调用，并且用的是你已有的订阅登录态。

自动探测顺序（可用环境变量 LAB_BACKEND 强制指定）：
    1. claude   -> Claude Code CLI（订阅登录，零配置）
    2. codex    -> Codex CLI（订阅登录，零配置）
    3. api      -> OpenAI 兼容 API（需要 key，最快最省）

每个 lab 都自带一份这个文件的副本 —— 故意重复，这样你只下载一个文件夹就能跑。
"""

import json
import os
import re
import shutil
import subprocess

TIMEOUT = 300

# CLI 后端共用：Claude Code / Codex 自带一堆内置工具（Bash、Read 等）。
# 我们只想把它们当"纯文本补全"用，所以必须显式禁止，否则它会去调 Bash，
# 然后撞上 --max-turns 直接失败。这是实测踩过的坑。
_NO_BUILTIN_TOOLS = (
    "\n\n重要：不要调用任何内置工具（Bash、Read、Write、Task、TodoWrite 等）。"
    "这里没有文件系统也没有 shell。你的整个回复就是上面要求的那个 JSON 对象。"
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
        "没有可用后端。装个 Claude Code 或 Codex，"
        "或设置 DEEPSEEK_API_KEY / OPENAI_API_KEY / OPENROUTER_API_KEY。"
    )


def _api_key():
    for name in ("DEEPSEEK_API_KEY", "OPENROUTER_API_KEY", "OPENAI_API_KEY"):
        if os.getenv(name):
            return name
    return None


# --- 三个后端 ---------------------------------------------------------------

def _complete_claude(prompt, system, attempts=3):
    """Claude Code 无头模式。不传 --continue/--resume，所以每次调用都是无状态的
    —— 上下文完全由我们自己拼，这正是消融实验需要的。"""
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
            last = f"CLI 输出不是 JSON (rc={proc.returncode}): {proc.stderr[:200]}"
            continue
        if payload.get("result"):
            return payload["result"]
        # 偶发：它还是去调了内置工具。不确定性问题，重试即可。
        last = f"无结果 (rc={proc.returncode}, stop={payload.get('stop_reason')})"
    raise RuntimeError(f"claude 连续 {attempts} 次失败：{last}")


def _complete_codex(prompt, system):
    """Codex 无头模式。codex exec 没有 --system-prompt，所以把 system 拼在前面。"""
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
        raise RuntimeError(f"codex 没返回消息 (rc={proc.returncode}): {proc.stderr[:200]}")
    return text


def _complete_api(prompt, system):
    """标准 OpenAI 兼容接口。最快、最省，但要 key。"""
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
    """一次无状态补全。返回模型的原始文本。"""
    backend = backend or detect_backend()
    if backend not in _BACKENDS:
        raise ValueError(f"未知后端 {backend!r}，可选：{sorted(_BACKENDS)}")
    return _BACKENDS[backend](prompt, system)


def parse_json_reply(text):
    """把模型文本里的 JSON 对象抠出来。抠不到就返回 {}。

    注意：这是 CLI 后端的妥协 —— 通过 claude -p / codex exec 拿不到结构化的
    tool_use block，所以工具调用只能约定成一段 JSON 文本自己解析。
    """
    match = re.search(r"\{.*\}", text or "", re.S)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
