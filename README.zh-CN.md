# AI Engineer Playbook

[English](README.md) · **简体中文**

> 一套动手实验，用来真正搞明白 AI Agent 是怎么运转的。
> **不需要 API key** —— 如果你已经装了 Claude Code 或 Codex，clone 下来就能跑。

---

## 这个仓库解决什么问题

市面上讲 Agent 的教程大致两类，都不太好用：

- **纯理论**：讲了一堆 ReAct、Function Calling、Context Engineering 的概念，
  但你合上文章还是不知道该怎么写第一行代码。
- **能跑的代码**：要么依赖一堆框架（LangChain / LlamaIndex），把最该看懂的循环
  藏在抽象层后面；要么开头就让你去注册一个付费 API key，直接劝退一半人。

这个 Playbook 的做法是：**每个实验都是一个零框架、能一口气读完的独立脚本**，
默认跑在你已经有的 Claude Code / Codex 订阅上，不用花钱。

更重要的是，实验的重点不在「跑通」，而在**把它跑坏**——通过系统性地删掉 agent 的某个
组成部分，观察它以什么方式失败。因为真实项目里你遇到的从来不是「怎么让它跑起来」，
而是「它为什么又抽风了」。

---

## 30 秒上手

```bash
git clone https://github.com/louisxu168/ai-engineer-playbook.git
cd ai-engineer-playbook/labs/01-context
pip install -r requirements.txt
python3 agent.py          # 先看用法说明
python3 agent.py full     # 跑基线
```

没有 `.env`，没有注册，没有充值。

---

## 两个不太一样的地方

### 一、不需要 API key

大部分学习者手上没有付费 API key，但很可能已经在用 Claude Code 或 Codex。
这两个 CLI 都能非交互调用，用的是你**已有的订阅登录态**：

```bash
claude -p "你好" --output-format json    # Claude Code 无头模式
codex exec --json "你好"                 # Codex 无头模式
```

每个实验里的 `llm.py` 会自动探测，顺序是 `claude` → `codex` → API key。
想强制指定或者想跑快点：

```bash
LAB_BACKEND=codex python3 agent.py full
LAB_BACKEND=api DEEPSEEK_API_KEY=sk-... python3 agent.py full   # 最快最省
```

> **代价说在前面**：走 CLI 拿不到结构化的 `tool_use` block，所以工具调用是约定成一段
> JSON 文本自己解析的。循环、上下文、消融逻辑都是真的，只有工具调用的**传输方式**是简化版。
> 想看真正的 structured tool calling，用 `LAB_BACKEND=api`。

### 二、让 Claude Code / Codex 当你的助教，而不是代打

仓库根目录有一份 [`AGENTS.md`](AGENTS.md)（Claude Code 通过 `CLAUDE.md` 引用同一份）。
它告诉你的编码 agent：**你现在是助教，不是替学习者做作业的**。

| 你说 | 它不会 | 它会 |
|---|---|---|
| "这个实验怎么做" | 直接写完整实现 | 让你先读 `agent.py`，问你觉得循环在哪几行 |
| "跑出来报错了" | 直接改好 | 把报错读给你听，问你觉得是哪一步的问题 |
| "为什么会这样" | 直接解释 | 先反问："你运行之前预测的是什么？" |

但环境问题（装依赖、后端探测失败、CLI 超时）它会直接帮你解决，不浪费你时间。

Claude Code 用户还有个 slash command：

```
/lab 01
```

它会检查环境、讲清概念、让你先读代码、再让你预测结果——按教学顺序走一遍。

> 有点绕但值得说破：**Claude Code / Codex 本身就是一个 agent harness**，而这些实验讲的
> 正是 harness 的构成。你随时可以问它「你自己是怎么管理上下文的？」——你手上跑的玩具版
> 和它是同一套原理。

---

## 实验列表

| # | 实验 | 学到什么 | 状态 |
|---|---|---|---|
| 01 | [上下文消融](labs/01-context/) | Agent = LLM + 上下文 + 工具；删掉上下文的任一部分，它会怎么坏 | ✅ 可用 |
| 02 | [工具由谁来跑](labs/02-who-runs-the-tool/) | 厂商托管工具 vs 自己搭 harness；不写循环时你放弃了什么 | ✅ 可用 |
| 03 | 工具设计 | schema 怎么写、描述写烂了会怎样、报错怎么回传给模型 | 📋 计划中 |
| 04 | 跨会话记忆 | 文件式 memory：什么该记、什么不该记 | 📋 计划中 |
| 05 | 上下文压缩 | 对话撑爆窗口时，压缩和裁剪的区别 | 📋 计划中 |
| 06 | 检索增强 | 为什么朴素 RAG 打不过 agentic search | 📋 计划中 |
| 07 | 规划与子代理 | 什么时候该拆任务，什么时候拆了反而更慢 | 📋 计划中 |
| 08 | 怎么评测 agent | LLM-as-judge，以及它什么时候不靠谱 | 📋 计划中 |
| 09 | 从经验中学习 | 让 agent 把踩过的坑写下来，下次少踩 | 📋 计划中 |

### 实验 01 长什么样

跑 `python3 agent.py full`，你会看到：

```
════════════════════════════════════════════════════════════════════
  第 1 轮 / 共 8 轮     模式：full
  上下文里还没有历史     提示词 72 字符
════════════════════════════════════════════════════════════════════

  正在问模型… 用了 10.0 秒

  [思考] 先查商品单价和美元兑人民币汇率，这两个调用互不依赖，可以并行。

  [工具 1/2] search_products({'keyword': 'mechanical keyboard'})
        └→ {'name': 'Keychron Q1 Pro', 'usd': 199.0}
  [工具 2/2] get_rate({'from_currency': 'USD', 'to_currency': 'CNY'})
        └→ {'rate': 7.24, 'from': 'USD', 'to': 'CNY'}
  ↑ 这一轮并行调了 2 个工具（模型判断它们互不依赖）
```

然后把 `SHOW_PROMPT` 改成 `True`，它会把**每一轮真正发给模型的完整文本**原样打出来。
看完那一眼你就会发现，所谓「上下文」根本没有玄学——**它就是一段拼出来的字符串**。

---

## 仓库结构

```
ai-engineer-playbook/
├── README.md / README.zh-CN.md   中英两版
├── AGENTS.md                     助教模式指令（Claude Code / Codex 都读）
├── CLAUDE.md                     → 引用 AGENTS.md
├── .claude/commands/lab.md       /lab 01 这个 slash command
└── labs/
    ├── 01-context/               每个实验一个独立文件夹
    └── 02-who-runs-the-tool/
        ├── README.zh-CN.md       实验说明：概念 + 步骤 + 练习
        ├── README.md             同上（英文）
        ├── agent.py              主体
        ├── llm.py                后端适配（claude / codex / api）
        ├── AGENTS.md             这个实验专属的助教指令
        ├── SOLUTION.zh-CN.md     参考答案 —— 自己试过之后再看
        └── requirements.txt
```

> **代码注释是英文的。** 这是开源惯例，为了让英文用户 clone 下来能直接读。
> 中文的详细讲解全部在 `README.zh-CN.md` 里 —— 讲解归文档，代码归代码。
> 把 `agent.py` 开头的 `LANG` 改成 `"en"`，输出和发给模型的提示词会一起切成英文。

**每个实验文件夹都是自包含的**，`llm.py` 在每个实验里都有一份副本。
这是故意的：重复换来的是「只下载一个文件夹就能跑」。

---

## 前置知识

会写 Python 就行。不需要懂机器学习、不需要 GPU、不需要读过论文。

代码里刻意避开了 Python 的简写语法（三元表达式、列表推导、`**kwargs` 解包等），
全用最笨但最好读的写法——**会写 `for` 和 `if` 就能读懂**。

代码注释是英文的（开源惯例），但都是短句；**中文的详细讲解在各实验的
`README.zh-CN.md` 里**，包括 Python 语法速查。对着文档读代码即可。

如果你连「LLM 是个函数」这句话都还没概念，直接从实验 01 开始，它就是讲这个的。

---

## 参与贡献

欢迎 issue 和 PR。特别欢迎这几类：

- **跑出来和文档不一样**：请开 issue 贴上输出。模型是随机的，
  多人多次的结果比我一个人跑一次可信得多。
- **某段代码看不懂**：这算 bug，不算你的问题。告诉我卡在第几行，我来改。
- **新实验**：先开 issue 聊聊要教什么、怎么让人跑坏它，再动手写。

---

## 致谢

实验主题受 [bojieli/ai-agent-book](https://github.com/bojieli/ai-agent-book)
《深入理解 AI Agent》启发。代码是独立重写的，跑法（零 API key、助教模式）也不一样。
想看更系统的理论讲解，推荐读原书。

## License

[MIT](LICENSE)
