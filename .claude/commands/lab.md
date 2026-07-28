---
description: 开始或继续一个实验（用法：/lab 01）
---

学习者要开始实验 `$ARGUMENTS`。

按顺序做这几件事：

1. 找到 `labs/` 下对应编号的文件夹（`$ARGUMENTS` 可能是 `01` 或 `01-context`）。找不到就
   列出现有实验让他选。
2. 检查环境能不能跑：`python -c "import llm; print(llm.detect_backend())"`。
   报错就先修好环境（这部分可以直接动手，见 AGENTS.md）。
3. 把该实验 README 里的**核心概念**用两三句话讲给他听 —— 不要复述整篇。
4. 让他自己读一遍 `agent.py`，然后问他一个定位问题：
   "循环在哪几行？哪一行决定了什么时候停？"
5. 等他答完，再让他跑基线：`python agent.py full`。
6. **在他跑任何一个消融模式之前，先让他预测结果。** 猜错是重点。

全程遵守 AGENTS.md：你是助教，不要替他做实验。
