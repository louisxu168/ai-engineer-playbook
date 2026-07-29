"""Ollama 向量嵌入客户端 —— 只用标准库，不装任何第三方包。

为什么不用 openai / sentence-transformers / langchain？
  因为这个实验想让你看清**向量检索到底是什么**：
  一段文字进去，一串浮点数出来，然后比余弦相似度。就这样。
  中间不该有一层框架帮你把这件事藏起来。

Ollama 的嵌入接口只有一个：POST /api/embed
    {"model": "nomic-embed-text", "input": ["句子1", "句子2", ...]}
  → {"embeddings": [[0.014, 0.026, ...], [...]]}

⚠️ 注意：不是所有模型都能做嵌入。qwen3:0.6b 会直接报
   "This server does not support embeddings" —— 生成模型和嵌入模型是两类东西。
"""

import json
import urllib.error
import urllib.request

HOST = "http://127.0.0.1:11434"


class OllamaNotRunning(Exception):
    """连不上 11434 端口。"""


class ModelMissing(Exception):
    """Ollama 在跑，但本地没这个模型。"""


class NotAnEmbeddingModel(Exception):
    """这个模型不能做嵌入（比如把生成模型名字填进来了）。"""


def _post(path, payload, timeout=900):
    request = urllib.request.Request(
        HOST + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        # 连不上和「连上了但返回错误」要分开处理
        if isinstance(exc, urllib.error.HTTPError):
            body = exc.read().decode("utf-8", "replace")
            if "does not support embeddings" in body:
                raise NotAnEmbeddingModel(body)
            if "not found" in body:
                raise ModelMissing(body)
            raise
        raise OllamaNotRunning(str(exc))


def list_models():
    try:
        with urllib.request.urlopen(HOST + "/api/tags", timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise OllamaNotRunning(str(exc))
    return [m.get("name", "") for m in data.get("models", [])]


def ensure_ready(model):
    """确认 Ollama 在跑、模型在本地、而且这个模型真的能做嵌入。"""
    have = list_models()
    if model not in have and (model + ":latest") not in have:
        raise ModelMissing(model)
    embed([" "], model)          # 拿一个空格试一下，能过就说明真能嵌入


def embed(texts, model, batch=128):
    """把一批文字变成向量。返回 list[list[float]]。

    分批是必要的：一次塞几千条进去，Ollama 那边会顶不住。
    """
    out = []
    for start in range(0, len(texts), batch):
        chunk = texts[start:start + batch]
        data = _post("/api/embed", {"model": model, "input": chunk})
        vectors = data.get("embeddings")
        if not vectors:
            raise NotAnEmbeddingModel(json.dumps(data)[:200])
        out.extend(vectors)
    return out
