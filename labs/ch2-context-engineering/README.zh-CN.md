# 第 2 章：上下文工程

[English](README.md) · **简体中文**

第 1 章告诉你「上下文是什么」。这一章问的是：**上下文该怎么管？**

因为真实 agent 一定会撞上这些问题：对话变长装不下、外部内容里藏着攻击指令、
日志里有不该发给模型的敏感信息。

> **编号说明**：本章的文件夹名和编号**直接沿用原书**
> （[《深入理解 AI Agent》第 2 章](https://bojieli.github.io/ai-agent-book/chapter2/)）。
> `2-3-kv-cache` 就是原书的实验 2-3 `kv-cache`，一一对应，不需要查表。
> 其他章节暂时还是本仓库自己的编号。

---

## 本章实验：和原书一一对应

原书第 2 章有 **8 个配套项目**，占 **9 个实验编号**
（实验 2-2 和实验 2-7 共用 `attention_visualization` 这一个项目）。
**8 个全部做了。**

| 原书编号 | 原书项目 | 本仓库文件夹 | 核心结论 |
|---|---|---|---|
| **2-1** | `local_llm_serving` | [2-1-local-llm-serving](2-1-local-llm-serving/README.zh-CN.md) | 「原始输出」是分层的；本地部署一样会洗 |
| **2-2**, **2-7** | `attention_visualization` | [2-2-attention-visualization](2-2-attention-visualization/README.zh-CN.md) | 第一个 token 拿走 81% 且**与语义无关**；状态栏的单字密度是流水账的 3.8 倍（这就是实验 2-7） |
| **2-3** | `kv-cache` | [2-3-kv-cache](2-3-kv-cache/README.zh-CN.md) | 破坏缓存 vs 破坏能力，代价完全不同；**量缓存必须交错测** |
| **2-4** | `prompt-engineering` | [2-4-prompt-engineering](2-4-prompt-engineering/README.zh-CN.md) | 书里「打乱组织掉 30%」没能复现；只有工具描述那一维还成立 |
| **2-5** | `prompt-injection` | [2-5-prompt-injection](2-5-prompt-injection/README.zh-CN.md) | 关键词过滤不是防御；真正有效的是几句话 |
| **2-6** | `agent-skills-ppt` | [2-6-agent-skills](2-6-agent-skills/README.zh-CN.md) | 渐进式披露和检索同形，但筛选权在模型手里 |
| **2-8** | `system-hint` | [2-8-system-hint](2-8-system-hint/README.zh-CN.md) | 书里的主张复现了；但赢的是 TODO——因为它给了替代动作 |
| **2-9** | `context-compression` | [2-9-context-compression](2-9-context-compression/README.zh-CN.md) | 三条路都要付钱，你只能选在哪付；压缩质量 ≈ 压缩提示词质量 |

**没有 `2-7-` 文件夹，因为原书也没有 2-7 这个项目。** 原书的实验 2-7
（《通过注意力可视化验证 Agent 状态栏的效果》）明写「基于 `attention_visualization` 项目」，
所以它在本仓库里就是 `2-2-attention-visualization` 的 `status_bar` 模式：

```bash
cd 2-2-attention-visualization
python3 agent.py status_bar        # ← 这就是原书实验 2-7
```

> 原书的**实验 3-3 `log-sanitization`** 也做了，但它的编号在第 3 章下，
> 所以放在 [../ch3-memory/3-3-log-sanitization](../ch3-memory/3-3-log-sanitization/README.zh-CN.md)。

---

## 本章不再有「暂时不做」的条目

以前这里列过三个：`local_llm_serving`(2-1)、`kv-cache`(2-3)、
`attention_visualization`(2-2/2-7)，理由写的是「需要跑 GPU 推理」。
**那个理由是错的**，而且三个后来都做了。

真实门槛只有 2-2 那一个，而且不是 GPU：是 ~2.5GB 的 `torch` + `transformers`
依赖，在 CPU 上跑 0.6B 完全够用。

---

## 代码是独立重写的：每个实验改了什么

| 编号 | 和原书的差别 |
|---|---|
| 2-1 | 用 Ollama + qwen3:0.6b；额外量了 TTFT / 预填充 |
| 2-2 | 真的加载 Qwen3-0.6B 取注意力矩阵（`attn_implementation="eager"`）；量化复现了实验 2-7 的状态栏主张（单字密度 3.8×），并**如实报告稀释曲线不单调**及原因 |
| 2-3 | 原书 5 种错误模式（含**动态用户配置**）+ 正确基线，六种全做了；历史程序化写死。原书用 Kimi 读 `cached_tokens`，本地只能读预填充耗时，所以加了 `cache` 交错测量模式 |
| 2-4 | 不用 τ-bench，换成一个调用顺序可机械判定的客服流程；加了 `--weak` 开关在本地 0.6B 上跑同一套 |
| 2-5 | 加了自动判定攻击成功与否的判据，防御有没有效是测出来的而不是说出来的 |
| 2-6 | 不生成真的 .pptx（那要 python-pptx），只把**渐进式披露机制本身**拎出来量：判据是「答案含不含那个只写在第 3 层的参数格式」+ 上下文 token 数 |
| 2-8 | 用书里那个 Xfinity 三通电话的场景，但换成**机械判据**（会不会打第 4 通）；在 0.6B 上 n=40 验证了书里那句「小模型对照组 A 经常违规」 |
| 2-9 | 换了任务和实现；加了可量化的字符数可视化 |

---

## 这一章想让你建立什么

第 1 章的三个实验都在**拆解**：把 agent 拆开，看每个零件掉了会怎样。

这一章开始**建造**：面对真实约束（窗口有限、外部内容不可信），
工程上有哪些做法，各自的代价是什么。

**2-9（上下文压缩）** 是个好起点，因为它的代价完全可量化 ——
每轮的提示词字符数直接打在屏幕上，你能看着那根条子涨上去、又被压下来。

**2-5（Prompt 注入）和 3-3（日志脱敏）要连起来读**，
按顺序读会撞出一个值得琢磨的矛盾：
2-5 实测到关键词过滤**挡不住**注入，3-3 实测到正则过滤**挡得住** PII 泄露。
同一种手段，相反的结论。差别在于**有没有一个会适应你规则的对手**——
这恰好是判断任何安全设计时第一个该问的问题。

**2-3 和 2-2 也要连起来读**：2-3 量的是「上下文管理策略」的代价，
2-2 是打开模型去看**注意力到底落在哪**。前者是行为，后者是机制。

---

## 跑法

每个实验都是**独立文件夹**，自带全部代码：

```bash
cd 2-3-kv-cache
python3 agent.py            # 先看用法说明
```

不需要 API key。

← [返回总目录](../../README.zh-CN.md)
