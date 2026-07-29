"""和本地 Ollama 说话的最小客户端 —— 只用 Python 标准库，没有任何第三方依赖。

为什么不用 `ollama` 那个 pip 包？因为本实验的目的就是**看清楚底下发生了什么**。
用官方 SDK 的话，流式解析、计时、原始 token 这些全被它包起来了，
而那正是我们要看的东西。

Ollama 的 HTTP 接口非常简单：

    POST http://localhost:11434/api/chat
    {"model": "qwen3:0.6b", "messages": [...], "stream": true}

它会一行一行地吐 JSON（每行一个 token 左右），最后一行带 done=true 和一堆计时数据。
下面这个文件就干这一件事。
"""

import json
import time
import urllib.error
import urllib.request


OLLAMA_URL = "http://localhost:11434"

CONNECT_TIMEOUT = 5      # 连不上就别等太久
GENERATE_TIMEOUT = 300   # 0.6B 很快，但第一次加载模型可能慢


class OllamaNotRunning(Exception):
    """Ollama 没装、或者 `ollama serve` 没起来。"""


class ModelMissing(Exception):
    """Ollama 在跑，但没有这个模型。"""


def _post_stream(path, payload):
    """发一个流式 POST，逐行 yield 解析好的 JSON。"""
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        OLLAMA_URL + path, data=data,
        headers={"Content-Type": "application/json"})
    try:
        response = urllib.request.urlopen(request, timeout=GENERATE_TIMEOUT)
    except urllib.error.URLError as exc:
        raise OllamaNotRunning(str(exc))

    for raw_line in response:
        line = raw_line.decode("utf-8").strip()
        if not line:
            continue
        yield json.loads(line)


def list_models():
    """列出本地已有的模型。顺便用来探测 Ollama 在不在。"""
    try:
        with urllib.request.urlopen(OLLAMA_URL + "/api/tags",
                                    timeout=CONNECT_TIMEOUT) as response:
            body = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise OllamaNotRunning(str(exc))
    return [m.get("name", "") for m in body.get("models", [])]


def ensure_ready(model):
    """检查 Ollama 在跑、而且有这个模型。不满足就抛出对应的异常。"""
    names = list_models()
    # Ollama 里 "qwen3:0.6b" 和 "qwen3:0.6b-xxx" 都算命中
    for one in names:
        if one == model or one.startswith(model):
            return True
    raise ModelMissing(model)


# ==========================================================================
#  核心：一次流式生成，把「原始 token 流」和「计时」同时交出来
# ==========================================================================


def chat_stream(model, messages, on_token=None, options=None, think=None):
    """跟模型说一次话，流式接收。

    返回一个字典，包含：
        text            content 字段拼起来的完整文本
        thinking        thinking 字段拼起来的完整文本（think=True 时才有）
        segments        [(字段名, 文字), ...] —— 按到达顺序记录，
                        用来看清 Ollama 把原始输出拆成了哪几段
        ttft_ms         Time To First Token —— 从发出请求到收到第一个 token 的毫秒数
        total_ms        整个生成过程的毫秒数
        tokens          生成了多少 token（Ollama 报的 eval_count）
        tps             每秒多少 token
        prompt_tokens   输入侧有多少 token（prompt_eval_count）
        prefill_ms      ★ 处理输入的耗时（prompt_eval_duration）
                        —— 前缀缓存命中与否，最直接就反映在这个数字上

    on_token 是个回调，每收到一段文本就调一次，用来做实时打印。
    """
    payload = {"model": model, "messages": messages, "stream": True}
    if options:
        payload["options"] = options
    if think is not None:
        payload["think"] = think

    start = time.time()
    ttft_ms = None
    pieces = []
    think_pieces = []
    # ★ segments 记录「每一段文字是从哪个字段来的、按什么顺序到达的」
    #   —— 这是本实验能看清 Ollama 帮你做了什么解析的关键
    segments = []
    final = {}

    for chunk in _post_stream("/api/chat", payload):
        message = chunk.get("message", {})
        # thinking 和 content 是 Ollama 分好的两个字段（见 README 第 2 节）
        for field in ("thinking", "content"):
            piece = message.get(field) or ""
            if not piece:
                continue
            if ttft_ms is None:
                # ★ 第一个 token 到达的那一刻
                ttft_ms = (time.time() - start) * 1000.0
            if field == "thinking":
                think_pieces.append(piece)
            else:
                pieces.append(piece)
            if not segments or segments[-1][0] != field:
                segments.append([field, ""])
            segments[-1][1] += piece
            if on_token:
                on_token(field, piece)
        if chunk.get("done"):
            final = chunk

    total_ms = (time.time() - start) * 1000.0
    text = "".join(pieces)
    thinking = "".join(think_pieces)

    # Ollama 用纳秒报计时
    def ns_to_ms(key):
        value = final.get(key)
        return (value / 1e6) if value else None

    eval_count = final.get("eval_count") or 0
    eval_ms = ns_to_ms("eval_duration")
    tps = (eval_count / (eval_ms / 1000.0)) if (eval_ms and eval_count) else None

    return {
        "text": text,
        "thinking": thinking,
        "segments": [(f, t) for f, t in segments],
        "ttft_ms": ttft_ms if ttft_ms is not None else total_ms,
        "total_ms": total_ms,
        "tokens": eval_count,
        "tps": tps,
        "prompt_tokens": final.get("prompt_eval_count") or 0,
        "prefill_ms": ns_to_ms("prompt_eval_duration"),
        "load_ms": ns_to_ms("load_duration"),
    }
