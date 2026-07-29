"""
实验 2-2：注意力可视化 —— 把模型打开看一眼

这是本仓库**唯一一个真正打开模型**的实验。前面所有实验看的都是
「输入进去、输出出来」，这个实验把中间那层注意力权重取出来，直接打印。

三件事：

    basic       「北京的天气怎么样」——「怎么样」这个词最关注前面哪个词？
                 直观理解 Query / Key / Value 在干嘛
    dilution    把同一条关键信息塞进 10 / 50 / 200 token 的上下文里，
                看它拿到的注意力权重怎么掉 ★ 这就是「上下文腐化」的机制
    status_bar  复现书里 2-7：有没有状态栏，注意力分布差多少 ★★
                （行为层面的对照在实验 2-8，这里看的是**内部机制**）

⚠️ **这是本仓库唯一需要重量级依赖的实验**：torch + transformers +
   Qwen3-0.6B 权重，一共约 2.5GB。装法见 README。

   不装也没关系 —— 本章其他 8 个实验都不需要它。

详细讲解见 README.zh-CN.md（中文）/ README.md（英文）。
"""

import sys

# --------------------------------------------------------------------------
#  可以改的开关
# --------------------------------------------------------------------------

LANG = "zh"

MODEL_NAME = "Qwen/Qwen3-0.6B"

# 看哪些层的注意力。取最后几层的平均 —— 越靠后的层越"语义化"。
LAYERS_FROM_END = 4

MODES = ["basic", "dilution", "status_bar"]


# --------------------------------------------------------------------------
#  文案
# --------------------------------------------------------------------------

TEXT = {
    "zh": {
        "no_deps_title": "✗ 缺少依赖（这是本仓库唯一需要重量级依赖的实验）",
        "no_deps_help": """
这个实验要把模型内部的注意力权重取出来，所以必须在本地跑一个**真的**模型
（不能用 Ollama —— 它不暴露注意力矩阵）。

    # 建议单独建一个 venv，不要污染你现有环境
    uv venv .venv-attn --python 3.12
    uv pip install --python .venv-attn/bin/python torch transformers

    .venv-attn/bin/python agent.py basic

首次运行会下载 Qwen3-0.6B 权重（约 1.2GB）。
torch + transformers 本身约 1.3GB。**一共约 2.5GB。**

⚠️ 不想装完全没关系 —— 本章其他 8 个实验一个都不需要它。
   想删干净：`rm -rf .venv-attn ~/.cache/huggingface`
""",
        "loading": "正在加载 {model}（首次会下载约 1.2GB）…",
        "loaded": "加载完成：{layers} 层 × {heads} 个注意力头",

        "mode_head": "  模式：{mode}",
        "mode_desc": "  {desc}",
        "desc_basic": "看「怎么样」最关注前面哪个词 —— Q/K/V 在干嘛",
        "desc_dilution": "同一条信息，放进越来越长的上下文里，注意力怎么掉 ★",
        "desc_status_bar": "有没有状态栏，注意力分布差多少 ★★",

        # --- basic ---
        "basic_sent": "北京 的 天气 怎么样",
        "basic_head": "  句子：{s}",
        "basic_q": "  当模型处理最后一个 token「{tok}」时，它在往回看谁：",
        "basic_row": "  {bar} {w:5.1%}  {tok}",
        "sink_note": """
  ⚠️ 等一下 —— 第一个 token {tok} 拿了 {w:.1%}，这**不是**因为它语义上最相关。

    这叫**注意力汇聚点**（attention sink）：Transformer 里的第 1 个 token
    会系统性地吸走大量注意力，几乎与内容无关。
    可以理解成模型的「垃圾桶」—— 当它不知道该看哪时，就把权重倒在那里。

    **这是你直接看注意力时最容易误读的地方。**
    剔掉它重新归一化，剩下的才是语义分布：""",
        "sink_head": "  剔除汇聚点后的分布：",
        "basic_note": """
  ★ 这就是注意力机制在做的事：
    最后那个 token 发出一个 **Query**（「我在找什么？」），
    和前面每个 token 的 **Key**（「我是什么」）算匹配度，
    然后按匹配度加权取它们的 **Value**（「我的内容」）。

    上面那一列百分比，就是**匹配度**（注意力权重）本身。
    你现在看到的是模型「觉得哪些词重要」的**直接证据** ——
    而不是从它的输出反推的。""",

        # --- dilution ---
        "dil_head": "  同一条关键信息「{needle}」，放进不同长度的上下文里：",
        "dil_row": "  上下文 {n:4d} token   针拿到的注意力 {w:7.3%}   {bar}",
        "dil_note": """
  ⚠️ **先看你自己跑出来的那三个数** —— 它们大概率**不是单调下降的**。

    我也没测出干净的单调曲线（见 SOLUTION）。原因是这个测法里
    至少有三个效应缠在一起：

      稀释    —— token 变多，每个分到的变少（这是我想测的）
      距离    —— 针离问题越来越远，近因效应让它权重下降
      汇聚点  —— 第 1 个 token 吸走一大块，且这块占比随长度变化

    **三个混在一起，单调性就没了。**

  ★ 但下面这条机制本身是**确定成立**的，不依赖这次的测量：

    注意力权重加起来必须等于 1（softmax 的性质）。
    所以上下文里的 token 越多，**平均每个 token 分到的就越少**。

    注意力权重加起来必须等于 1（softmax 的性质）。
    所以上下文里的 token 越多，**每个 token 分到的就越少** ——
    哪怕那条关键信息一个字都没变。

    这不是「模型变笨了」，是「那条信息被稀释了」——
    窗口还远没满，但关键信息已经淹没在无关内容里。
    **这正是为什么"信息密度"比"上下文长度"更值得关心。**

  ★ 而这直接解释了前面几个实验为什么有用：
    2-1 压缩、2-7 按需加载 —— 它们减少的不只是 token 数，
    **更是分母**。""",

        # --- status_bar ---
        "sb_head": "  问题：{q}",
        "sb_mode_a": "  【对照组 A】没有状态栏 —— 3 次通话记录散落在轨迹里",
        "sb_mode_b": "  【对照组 B】有状态栏 —— 末尾直接写着「已达上限 3/3」",
        "sb_row2": "     轨迹拿到 {w:6.1%}   每字密度 {per:.3%}  {bar}",
        "sb_row3": "     轨迹拿到 {w:6.1%}   每字密度 {per:.3%}  {bar}",
        "sb_row4": "     状态栏   {w:6.1%}   每字密度 {per:.3%}  {bar}  ← 只有 15 个字",
        "sb_ratio": "  ★ 状态栏的**每字注意力密度是轨迹的 {r:.1f} 倍**；\n"
                    "    而且加了状态栏之后，轨迹本身拿到的注意力下降了 {drop:.1%}。",
        "sb_note": """
  ★ 书里实验 2-7 的说法：

    对照组 A：注意力**高度分散**，在三次电话调用的区域形成几个聚焦点，
              模型在**从原始信息里做统计**
    对照组 B：注意力**高度集中**在状态栏上，直接用已经算好的结论

    上面的数字是这句话的量化版。

  ★ 而行为层面的后果，在[实验 2-8](../2-8-system-hint/README.zh-CN.md)里量过了：
    0.6B 在无状态栏时违规率 50%，加了状态栏降到 32.5%。

    **两个实验合起来才完整**：2-6 告诉你「行为变了」，
    2-8（本实验）告诉你「**为什么**变了」。""",

        "unknown_mode": "✗ 不认识的模式：",
        "exp_header": "# {i}/{total}：{mode}",
        "help": """
======================================================================
 实验 2-2：注意力可视化 —— 把模型打开看一眼
======================================================================

本仓库唯一一个**真正打开模型**的实验。取出注意力权重矩阵直接打印。

用法：
    python3 agent.py <模式>

【三种模式】
    basic       「怎么样」最关注前面哪个词 —— 直观理解 Q/K/V
    dilution    同一条信息放进 10/50/200 token 的上下文，看权重怎么掉 ★
                这就是「上下文腐化」的机制
    status_bar  有无状态栏时注意力分布对比 ★★（书里实验 2-7）

    all         全部跑一遍

⚠️ **本仓库唯一需要重量级依赖的实验**：torch + transformers + 0.6B 权重，
   约 2.5GB。装法：

    uv venv .venv-attn --python 3.12
    uv pip install --python .venv-attn/bin/python torch transformers
    .venv-attn/bin/python agent.py all

   不装完全没关系 —— 本章其他 8 个实验都不需要它。

把开头的 LANG 改成 "en" 可切英文。
详细讲解见 README.zh-CN.md。
""",
    },
    "en": {
        "no_deps_title": "x Missing dependencies (the only lab here that needs heavy ones)",
        "no_deps_help": """
This lab extracts the model's internal attention weights, so it must run a **real**
model locally (Ollama won't do - it doesn't expose attention matrices).

    # A separate venv is recommended so you don't pollute your environment
    uv venv .venv-attn --python 3.12
    uv pip install --python .venv-attn/bin/python torch transformers

    .venv-attn/bin/python agent.py basic

The first run downloads Qwen3-0.6B weights (~1.2GB); torch + transformers are
another ~1.3GB. **About 2.5GB in total.**

⚠️ Skipping it is completely fine - none of this chapter's other 8 labs need it.
   To remove: `rm -rf .venv-attn ~/.cache/huggingface`
""",
        "loading": "Loading {model} (first run downloads ~1.2GB)...",
        "loaded": "Loaded: {layers} layers x {heads} attention heads",

        "mode_head": "  Mode: {mode}",
        "mode_desc": "  {desc}",
        "desc_basic": "what the last token attends to - seeing Q/K/V at work",
        "desc_dilution": "the same fact in ever-longer contexts: how its attention decays *",
        "desc_status_bar": "attention with and without a status bar **",

        "basic_sent": "The weather in Beijing is",
        "basic_head": "  Sentence: {s}",
        "basic_q": "  While processing the final token \"{tok}\", here's what it looks back at:",
        "basic_row": "  {bar} {w:5.1%}  {tok}",
        "sink_note": """
  ⚠️ Hold on - the first token {tok} took {w:.1%}, and that is **not** because it's
    the most semantically relevant.

    This is the **attention sink**: in a Transformer the first token systematically
    absorbs a large share of attention almost regardless of content. Think of it as
    the model's dustbin - when it doesn't know where to look, it dumps weight there.

    **This is the single easiest thing to misread when looking at raw attention.**
    Drop it and renormalise, and the semantic distribution appears:""",
        "sink_head": "  Distribution after removing the sink:",
        "basic_note": """
  * This is what attention does:
    the final token emits a **Query** ("what am I looking for?"),
    scores it against every earlier token's **Key** ("what I am"),
    and takes a weighted sum of their **Values** ("my content").

    The percentages above ARE those match scores - the attention weights.
    You're looking at **direct evidence** of what the model considers relevant,
    rather than inferring it from the output.""",

        "dil_head": "  The same key fact \"{needle}\", placed in contexts of different lengths:",
        "dil_row": "  context {n:4d} tokens   attention on the needle {w:7.3%}   {bar}",
        "dil_note": """
  * This is the mechanism behind **context rot**.

    Attention weights must sum to 1 (that's softmax). So the more tokens in the
    context, **the less each one gets** - even though the key fact is unchanged.

    ⚠️ Note this isn't "the model got dumber", it's "that fact got diluted".
    The window is nowhere near full, yet the key information is drowning in
    irrelevant content - **which is why information DENSITY matters more than
    context LENGTH.**

  * And it explains why the earlier labs work: 2-1 compaction and 2-7 on-demand
    loading don't just cut token count, **they cut the denominator.**""",

        "sb_head": "  Question: {q}",
        "sb_mode_a": "  [Control A] no status bar - 3 call records scattered through the trace",
        "sb_mode_b": "  [Control B] status bar - the end states \"limit reached 3/3\"",
        "sb_row2": "     trace gets {w:6.1%}   per-char {per:.3%}  {bar}",
        "sb_row3": "     trace gets {w:6.1%}   per-char {per:.3%}  {bar}",
        "sb_row4": "     status bar {w:6.1%}   per-char {per:.3%}  {bar}  <- only 15 chars",
        "sb_ratio": "  * The status bar's **per-character attention density is {r:.1f}x the trace's**;\n"
                    "    and adding it pulled the trace's own attention down by {drop:.1%}.",
        "sb_note": """
  * The book's experiment 2-7 describes it as:

    Control A: attention is **highly dispersed**, forming focal points around the
               three call sites - the model is **doing statistics on raw data**
    Control B: attention is **highly concentrated** on the status bar, using the
               already-computed conclusion

    The numbers above are the quantified version of that sentence.

  * The behavioural consequence was measured in [lab 2-8](../2-8-system-hint/README.md):
    the 0.6B violated 50% of the time without a status bar, 32.5% with one.

    **The two labs are only complete together**: 2-6 tells you the behaviour changed,
    2-8 (this one) tells you **why**.""",

        "unknown_mode": "x unknown mode: ",
        "exp_header": "# {i}/{total}: {mode}",
        "help": """
======================================================================
 Lab 2-2: Attention visualisation - opening the model up
======================================================================

The only lab here that actually **opens the model**, pulling out the attention
weight matrices and printing them.

Usage:
    python3 agent.py <mode>

THREE MODES
    basic       what the final token attends to - Q/K/V made concrete
    dilution    the same fact in 10/50/200-token contexts, watching weights decay *
                this is the mechanism behind context rot
    status_bar  attention with and without a status bar ** (the book's 2-7)

    all         run everything

⚠️ **The only lab here needing heavy dependencies**: torch + transformers + 0.6B
   weights, ~2.5GB:

    uv venv .venv-attn --python 3.12
    uv pip install --python .venv-attn/bin/python torch transformers
    .venv-attn/bin/python agent.py all

   Skipping it is fine - none of this chapter's other 8 labs need it.

Set LANG = "zh" for Chinese.
Full walkthrough: README.md
""",
    },
}


def t(key, **kwargs):
    template = TEXT[LANG][key]
    return template.format(**kwargs) if kwargs else template


# ==========================================================================
#  第 1 部分：把注意力取出来
# ==========================================================================
#
# ★ 关键就一行：`output_attentions=True`。
#   transformers 会把每一层、每个头的注意力矩阵一并返回。
#
#   形状是 (batch, heads, query_len, key_len)。
#   att[L][0, H, i, j] = 第 L 层第 H 个头里，第 i 个 token 对第 j 个 token 的注意力。


def load_model():
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    print(t("loading", model=MODEL_NAME), flush=True)
    tok = AutoTokenizer.from_pretrained(MODEL_NAME)
    # attn_implementation="eager" 是必须的 —— 快速实现（sdpa/flash）
    # 为了性能不会把注意力矩阵物化出来，你就拿不到。
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME, dtype=torch.float32, attn_implementation="eager")
    model.eval()
    cfg = model.config
    print(t("loaded", layers=cfg.num_hidden_layers,
            heads=cfg.num_attention_heads))
    return tok, model


def last_token_attention(tok, model, text, want_offsets=False):
    """返回 (tokens, weights)：最后一个 token 对前面每个 token 的注意力。

    对最后 LAYERS_FROM_END 层、所有头取平均 —— 单看一个头噪声太大。

    want_offsets=True 时额外返回每个 token 的字符区间 —— 用来按**字符位置**
    精确圈出某一段的注意力。
    ★ 别用「token 文本里有没有某个关键词」来圈，中文分词会把词切开，
      匹配不到就悄悄算成 0（我第一版就是这么错的，见 SOLUTION）。
    """
    import torch
    ids = tok(text, return_tensors="pt")
    offsets = None
    if want_offsets:
        enc = tok(text, return_offsets_mapping=True)
        offsets = enc["offset_mapping"]
    with torch.no_grad():
        out = model(**ids, output_attentions=True)

    # 取最后几层，每层 shape = (1, heads, q, k)
    picked = out.attentions[-LAYERS_FROM_END:]
    stacked = torch.stack(picked)                 # (L, 1, heads, q, k)
    avg = stacked.mean(dim=(0, 2))[0]             # (q, k)  —— 层和头都平均掉
    last_row = avg[-1]                            # 最后一个 token 那一行

    token_ids = ids["input_ids"][0].tolist()
    tokens = [tok.decode([i]) for i in token_ids]
    if want_offsets:
        return tokens, last_row.tolist(), offsets
    return tokens, last_row.tolist()


def attention_on_span(weights, offsets, start, end):
    """把字符区间 [start, end) 覆盖到的所有 token 的注意力加起来。"""
    total = 0.0
    for w, (a, b) in zip(weights, offsets):
        if b > start and a < end:      # token 和区间有重叠
            total += w
    return total


def bar(weight, scale=40):
    n = int(round(weight * scale))
    return "█" * max(0, min(scale, n))


# ==========================================================================
#  第 2 部分：三种模式
# ==========================================================================


def run_basic(tok, model):
    text = t("basic_sent")
    tokens, weights = last_token_attention(tok, model, text)
    print("")
    print(t("basic_head", s=text))
    print("")
    print(t("basic_q", tok=tokens[-1]))
    print("")
    # 除掉最后一个（它对自己），按权重排序展示
    pairs = list(zip(tokens[:-1], weights[:-1]))
    for token_text, w in sorted(pairs, key=lambda x: -x[1]):
        print(t("basic_row", bar=bar(w, 30).ljust(30),
                w=w, tok=repr(token_text)))

    # ★ 第一个 token 是「注意力汇聚点」（attention sink），它会吸走大部分权重。
    #   这不是语义关系，是 Transformer 的一个已知副作用。
    #   剔掉它再归一化，剩下的才是「语义上谁重要」。
    print(t("sink_note", tok=repr(tokens[0]), w=weights[0]))
    rest = pairs[1:]
    total = sum(w for _, w in rest)
    if total > 0:
        print("")
        print(t("sink_head"))
        for token_text, w in sorted(rest, key=lambda x: -x[1]):
            share = w / total
            print(t("basic_row", bar=bar(share, 30).ljust(30),
                    w=share, tok=repr(token_text)))
    print(t("basic_note"))


def run_dilution(tok, model):
    """★ 把同一条「针」放进越来越长的上下文，看它拿到的注意力怎么掉。"""
    needle = "密码 是 7391" if LANG == "zh" else "the code is 7391"
    filler_unit = ("今天 天气 不错 我们 出去 走走 顺便 买点 东西 回来 "
                   if LANG == "zh" else
                   "the weather is fine today so we went out for a walk and shopping ")
    question = "密码是多少" if LANG == "zh" else "what is the code"

    print("")
    print(t("dil_head", needle=needle))
    print("")

    for repeats in (1, 6, 24):
        # ★ 针放在【中间】—— 不能放开头，因为第 1 个 token 是注意力汇聚点，
        #   放那儿的话它会一直吸到 ~78% 的权重，什么稀释都测不出来。
        #   （我第一版就是这么错的，见 SOLUTION。）
        half = filler_unit * repeats
        text = half + needle + " " + half + " " + question
        tokens, weights = last_token_attention(tok, model, text)

        prefix_len = len(tok(half)["input_ids"])
        needle_len = len(tok(needle)["input_ids"])
        needle_attention = sum(weights[prefix_len:prefix_len + needle_len])
        print(t("dil_row", n=len(tokens), w=needle_attention,
                bar=bar(needle_attention * 60, 40)))

    print(t("dil_note"))


def run_status_bar(tok, model):
    """★★ 复现书里 2-7：有没有状态栏，注意力分布差多少。"""
    if LANG == "zh":
        trace = ("打电话 给 Xfinity 结果 无进展 "
                 "搜索 网络 结果 很多 用户 反映 延迟 "
                 "打电话 给 Xfinity 结果 升级 二线 "
                 "搜索 网络 结果 可以 要求 转接 主管 "
                 "打电话 给 Xfinity 结果 主管 承诺 回电 ")
        status = "状态 已达 拨打 上限 三次 "
        question = "还要 再 打 一次 吗"
        key_a = "打电话"      # A 组的关键信息散落在三处「打电话」
        key_b = "上限"        # B 组的关键信息集中在状态栏
    else:
        trace = ("called Xfinity result no progress "
                 "searched web result many users report delays "
                 "called Xfinity result escalated to tier two "
                 "searched web result you may request a supervisor "
                 "called Xfinity result supervisor promised a callback ")
        status = "status maximum calls reached three of three "
        question = "should we call again"
        key_a = "called"
        key_b = "maximum"

    print("")
    print(t("sb_head", q=question))
    print("")

    # ★ 两个关键的测量决定（都是我第一版做错、改过来的，见 SOLUTION）：
    #
    #   1. **排除注意力汇聚点**。第 1 个 token 吃掉约 80%，两组都一样，
    #      留着它会把真正的差别压得看不见。
    #   2. **算「每字注意力密度」而不是总量**。状态栏只有 15 个字，
    #      轨迹有 112 个字 —— 直接比总量对状态栏不公平。
    #
    #   书里说的「注意力高度集中在状态栏上」，指的正是**密度**。

    def measure(text, spans):
        tokens, weights, offsets = last_token_attention(
            tok, model, text, want_offsets=True)
        rest = sum(weights[1:])          # 剔除汇聚点后的总量
        out = {}
        for name, (a, b) in spans.items():
            total = 0.0
            for i, (w, (x, y)) in enumerate(zip(weights, offsets)):
                if i == 0:
                    continue             # ← 排除汇聚点
                if y > a and x < b:
                    total += w
            out[name] = total / rest
        return out

    text_a = trace + question
    text_b = trace + status + question

    a = measure(text_a, {"trace": (0, len(trace))})
    b = measure(text_b, {"trace": (0, len(trace)),
                         "status": (len(trace), len(trace) + len(status))})

    print(t("sb_mode_a"))
    print(t("sb_row2", w=a["trace"], per=a["trace"] / len(trace),
            bar=bar(a["trace"] / len(trace) * 40, 40)))
    print("")
    print(t("sb_mode_b"))
    print(t("sb_row3", w=b["trace"], per=b["trace"] / len(trace),
            bar=bar(b["trace"] / len(trace) * 40, 40)))
    print(t("sb_row4", w=b["status"], per=b["status"] / len(status),
            bar=bar(b["status"] / len(status) * 40, 40)))
    print("")
    ratio = (b["status"] / len(status)) / max(1e-9, b["trace"] / len(trace))
    print(t("sb_ratio", r=ratio, drop=a["trace"] - b["trace"]))
    print("")

    print(t("sb_note"))


RUNNERS = {"basic": run_basic, "dilution": run_dilution,
           "status_bar": run_status_bar}


# ==========================================================================
#  第 3 部分：入口
# ==========================================================================


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
    if mode_arg not in MODES and mode_arg != "all":
        print("")
        print(t("unknown_mode") + mode_arg)
        print(t("help"))
        sys.exit(1)

    try:
        import torch          # noqa: F401
        import transformers   # noqa: F401
    except ImportError:
        print("")
        print(t("no_deps_title"))
        print(t("no_deps_help"))
        sys.exit(1)

    tok, model = load_model()

    todo = MODES if mode_arg == "all" else [mode_arg]
    for i in range(len(todo)):
        m = todo[i]
        print("")
        print("=" * 70)
        if len(todo) > 1:
            print(t("exp_header", i=i + 1, total=len(todo), mode=m))
        print(t("mode_head", mode=m))
        print(t("mode_desc", desc=t("desc_" + m)))
        print("=" * 70)
        RUNNERS[m](tok, model)
