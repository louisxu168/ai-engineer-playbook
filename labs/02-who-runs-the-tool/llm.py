"""
Backend adapter — lets the labs run WITHOUT an API key.

+----------------------------------------------------------------------+
|  You can skip this whole file on a first read. It does not matter for |
|  understanding how agents work.                                       |
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

Most learners have no paid API key, but many already have Claude Code or
Codex installed. Both can be called non-interactively and both authenticate
with the subscription you are already logged into.

Detection order (override with the LAB_BACKEND environment variable):
    1. claude   -> Claude Code CLI    (subscription login, zero config)
    2. codex    -> Codex CLI          (subscription login, zero config)
    3. api      -> OpenAI-compatible API (needs a key; fastest and cheapest)

Every lab ships its own copy of this file. The duplication is deliberate:
it is what makes "download one folder and run it" true.
"""

import json
import os
import re
import shutil
import subprocess

TIMEOUT = 300

# Shared by both CLI backends. Claude Code and Codex come with their own
# built-in tools (Bash, Read, ...). We want them as plain text completion only,
# so we have to forbid those explicitly — otherwise the model reaches for Bash,
# blows past --max-turns and the call fails. Learned the hard way.
_NO_BUILTIN_TOOLS = (
    "\n\nIMPORTANT: do not invoke any built-in tool (Bash, Read, Write, Task, "
    "TodoWrite, ...). There is no filesystem and no shell here. Your entire "
    "reply is the single JSON object described above."
)


def detect_backend():
    """Return the name of the backend to use."""
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
    """Claude Code headless mode.

    We never pass --continue/--resume, so every call is STATELESS. That means
    the context is entirely ours to assemble — which is exactly what the
    ablation experiment needs.
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
        # Occasionally it reaches for a built-in tool anyway. Non-deterministic,
        # so just retry.
        last = f"no result (rc={proc.returncode}, stop={payload.get('stop_reason')})"
    raise RuntimeError(f"claude failed {attempts} times in a row: {last}")


def _complete_codex(prompt, system):
    """Codex headless mode. `codex exec` has no --system-prompt, so the system
    text is prepended to the prompt instead."""
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
            text = item.get("text")          # keep the last agent_message
    if text is None:
        raise RuntimeError(
            f"codex returned no message (rc={proc.returncode}): {proc.stderr[:200]}")
    return text


def _complete_api(prompt, system):
    """Standard OpenAI-compatible endpoint. Fastest and cheapest, needs a key."""
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
    """One stateless completion. Returns the model's raw reply text."""
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
    """Raised when the current backend has no built-in web search."""


def complete_hosted(prompt, max_turns=8):
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

    proc = subprocess.run(
        ["claude", "-p", prompt,
         # The one meaningful difference from _complete_claude: instead of
         # forbidding built-in tools, we allow exactly one — WebSearch.
         "--allowedTools", "WebSearch",
         "--max-turns", str(max_turns),
         "--output-format", "json"],
        capture_output=True, text=True, timeout=TIMEOUT,
    )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(
            f"CLI output was not JSON (rc={proc.returncode}): {proc.stderr[:200]}")

    if not payload.get("result"):
        raise RuntimeError(
            f"no result (rc={proc.returncode}, stop={payload.get('stop_reason')})")

    return payload["result"], payload.get("num_turns")


def parse_json_reply(text):
    """Pull the JSON object out of the model's reply text. Returns {} if absent.

    This is the compromise the CLI backends force on us: `claude -p` and
    `codex exec` do not expose structured tool_use blocks, so tool calls have
    to be a JSON text protocol we parse ourselves. Use LAB_BACKEND=api to see
    real structured tool calling.
    """
    match = re.search(r"\{.*\}", text or "", re.S)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
