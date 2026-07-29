"""
实验 3-4：稠密向量检索 —— 它救回了什么，又漏掉了什么

实验 3-5 停在一个很难受的地方：BM25 漏掉了「对花生过敏」，
因为那句话和「成都出差餐厅清单」**一个字都不重合**。

标准答案是「上 embedding 就好了」。这个实验去验证这句话。

    第一部分（compare）：稠密 vs 稀疏，同一个语料同一个问题
        → 结论不是「稠密赢了」。**最危险的那条记忆，两边都漏。**

    第二部分（ann / trap / scale）：原书这个实验真正的主题 ——
        向量多到几十万条之后，精确检索也慢了，
        投影树（ANNOY 的思路）和可导航图（HNSW 的思路）各是什么代价。
        两个索引都从零写在 ann.py 里，只用 numpy。

    python3 agent.py                  # 用法说明
    python3 agent.py compare          # 稠密 vs BM25 ★★★ 先跑这个
    python3 agent.py ann              # 精确 / 投影树 / 图，三方对比
    python3 agent.py trap             # ★ 一个「调参数完全没用」的坑
    python3 agent.py scale            # ANN 从多大规模开始才划算
    python3 agent.py all              # 全部

⚠️ 需要本地 Ollama + 一个**嵌入模型**（和第 2 章那套环境一样）：

    ollama pull nomic-embed-text      # 274MB

   不需要 API key。生成模型（qwen3 之类）不能做嵌入，会直接报错。

★ 本实验所有关键指标都是**机械可判定**的：
  第一部分的召回率比对的是写死的标准答案下标；
  第二部分的召回率比对的是精确检索的结果。**都不需要模型来当裁判。**

详细讲解见 README.zh-CN.md（中文）/ README.md（英文）。
"""

import os
import sys
import time

try:
    import numpy as np
except ImportError:                                      # pragma: no cover
    print("")
    print("x 需要 numpy：pip3 install numpy")
    sys.exit(1)

import ann
from embed_client import (ModelMissing, NotAnEmbeddingModel, OllamaNotRunning,
                          embed, ensure_ready, list_models)


# --------------------------------------------------------------------------
#  可以改的开关（Settings）
# --------------------------------------------------------------------------

LANG = "zh"                      # "zh" | "en"

MODEL = "nomic-embed-text"       # 换成 bge-m3 再跑一遍，看结论变不变 ★

TOP_K = 5                        # compare 模式取几条

CORPUS_N = 2000                  # ann / trap 模式用多少条向量

N_QUERIES = 50                   # 量 ANN 召回率时用几条查询

CACHE_DIR = ".cache"             # 嵌入结果缓存在这儿，第二次跑就不用重算


MODES = ["compare", "ann", "trap", "scale"]


# ==========================================================================
#  第 1 部分：语料 —— 和实验 3-5 完全同一份
# ==========================================================================
#
# 故意一字不改地照抄 3-5 的 36 条记忆和标准答案下标，
# 这样两个实验的召回率**可以直接放在一张表里比**。
# 换了语料的对比是没有意义的。

MEMORIES = {
    "zh": [
        "对花生过敏，误食会送医院（严重过敏）",
        "完全不吃辣，一点辣都不能接受",
        "不喜欢香菜",
        "早饭习惯喝黑咖啡，不加糖不加奶",
        "乳糖不耐，喝牛奶会不舒服",
        "职业：后端开发，主要写 Go 和 Python",
        "常驻工作地为上海浦东（2026 年 8 月起调岗生效）",
        "不再在北京工作",
        "工作日中午通常在公司楼下吃午饭",
        "每周三下午有团队例会，尽量不要安排别的事",
        "在用的笔记本是 2024 款 MacBook Pro，16 寸",
        "公司报销标准：出差住宿每晚不超过 600 元",
        "2026-08-03 至 2026-08-09 期间赴成都出差三天，住在春熙路附近（临时行程，结束后失效）",
        "去年十月去过一次杭州出差，住在西湖边上，觉得性价比一般",
        "护照有效期到 2029 年 3 月",
        "坐飞机偏好靠过道的座位",
        "晕船，坐船超过半小时会难受",
        "有一只叫「豆豆」的橘猫，五岁",
        "父母住在南京，每两个月回去一次",
        "住的小区叫「金桥新苑」，离地铁 9 号线走路 8 分钟",
        "健身卡在公司楼下那家，一周去三次",
        "不喜欢人多拥挤的场所",
        "在学吉他，水平大概是能弹几首完整的曲子",
        "喜欢看科幻小说，最近在读《三体》第三部",
        "周末常去骑车，一次骑 40 公里左右",
        "不打游戏，觉得费时间",
        "在追一部叫《漫长的季节》的剧",
        "颈椎不太好，久坐一小时就得起来活动",
        "对青霉素过敏",
        "近视 500 度，戴隐形眼镜",
        "作息偏早，晚上 11 点前睡",
        "买东西偏好用支付宝",
        "上个月买了一台扫地机器人，型号是石头 G20",
        "衣服尺码：上衣 L，裤子 32 腰",
        "不喜欢订阅制服务，能买断的尽量买断",
        "常用的外卖软件是美团",
    ],
    "en": [
        "Severely allergic to peanuts - ingestion means the ER",
        "Does not eat spicy food at all, not even mildly",
        "Dislikes coriander",
        "Drinks black coffee at breakfast, no sugar, no milk",
        "Lactose intolerant - milk causes discomfort",
        "Job: backend developer, mainly Go and Python",
        "Based in Shanghai Pudong (transfer effective August 2026)",
        "No longer works in Beijing",
        "Usually eats lunch downstairs from the office on weekdays",
        "Team meeting every Wednesday afternoon - keep it clear",
        "Laptop is a 2024 MacBook Pro, 16 inch",
        "Company expense policy: max 600 CNY per night for work travel",
        "Three-day work trip to Chengdu 2026-08-03 to 2026-08-09, staying near Chunxi Road (temporary, expires after)",
        "Went to Hangzhou for work last October, stayed by West Lake, thought it was poor value",
        "Passport valid until March 2029",
        "Prefers an aisle seat on flights",
        "Gets seasick - anything over half an hour on a boat is rough",
        "Has a five-year-old ginger cat called Doudou",
        "Parents live in Nanjing, visits every couple of months",
        "Lives in the Jinqiao Xinyuan complex, 8 minutes walk from metro line 9",
        "Gym membership is the one downstairs from the office, goes three times a week",
        "Dislikes crowded places",
        "Learning guitar - can play a few pieces all the way through",
        "Enjoys science fiction, currently reading the third Three-Body book",
        "Cycles most weekends, around 40 km a time",
        "Doesn't play games, considers it a waste of time",
        "Currently watching a show called The Long Season",
        "Bad neck - has to get up and move after an hour of sitting",
        "Allergic to penicillin",
        "Short-sighted, -5.00 dioptres, wears contact lenses",
        "Early riser, in bed before 11pm",
        "Prefers to pay with Alipay",
        "Bought a robot vacuum last month, a Roborock G20",
        "Clothing sizes: tops L, trousers 32 waist",
        "Dislikes subscriptions - buys outright where possible",
        "Usual food delivery app is Meituan",
    ],
}

# 这次问题真正**必须**取到的记忆下标（和实验 3-5 一致）
# 0  = 对花生过敏     ← 漏了可能出人命
# 1  = 完全不吃辣     ← 漏了整份建议就是错的
# 12 = 成都出差行程   ← 漏了不知道在哪
TARGET_INDEXES = [0, 1, 12]


# ==========================================================================
#  第 2 部分：BM25 —— 从实验 3-5 抄过来的对照组
# ==========================================================================
#
# 只有 30 行。抄过来是为了让 compare 模式能在**一次运行里**
# 把稀疏和稠密的结果并排打出来 —— 隔着两个实验对比是看不清的。


def tokenize(text):
    """中文按字切二元组，英文按词。和实验 3-5 用的同一套。"""
    import re
    text = text.lower()
    words = re.findall(r"[a-z0-9]+", text)
    chinese = re.findall(r"[一-鿿]", text)
    bigrams = [chinese[i] + chinese[i + 1] for i in range(len(chinese) - 1)]
    return words + chinese + bigrams


def bm25_scores(query, docs, k1=1.5, b=0.75):
    import math
    from collections import Counter
    doc_tokens = [tokenize(d) for d in docs]
    lengths = [len(t) for t in doc_tokens]
    avg_len = sum(lengths) / max(1, len(lengths))
    df = Counter()
    for tokens in doc_tokens:
        for term in set(tokens):
            df[term] += 1

    scores = []
    q_tokens = tokenize(query)
    for i, tokens in enumerate(doc_tokens):
        counts = Counter(tokens)
        total = 0.0
        for term in q_tokens:
            if term not in counts:
                continue
            idf = math.log(1 + (len(docs) - df[term] + 0.5) / (df[term] + 0.5))
            tf = counts[term]
            total += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * lengths[i] / avg_len))
        scores.append(total)
    return np.array(scores, dtype="float32")


# ==========================================================================
#  第 3 部分：合成语料（给 ANN 用）
# ==========================================================================
#
# ANN 只在「向量很多」的时候才有意义 —— 36 条记忆用精确检索就够了。
# 所以这里程序化生成几千条句子。它们是假的，但**嵌入是真的**，
# 所以几何结构（这才是 ANN 关心的东西）是真的。

_SUBJECTS = ["用户", "他", "她", "这位用户"]
_ADVERBS = ["很喜欢", "不喜欢", "偶尔会", "从不", "每周都",
            "最近开始", "已经放弃", "打算尝试", "一直在", "特别在意"]
_ITEMS = ["咖啡", "牛奶", "辣椒", "海鲜", "牛肉", "米饭", "面条", "水果", "蛋糕", "茶",
          "会议", "出差", "加班", "远程办公", "晋升", "培训", "报销", "同事", "客户", "项目",
          "跑步", "游泳", "骑车", "登山", "瑜伽", "健身", "篮球", "羽毛球", "滑雪", "散步"]
_TOPICS = ["饮食", "工作", "行程", "家庭", "兴趣", "健康", "消费", "居住", "运动", "阅读"]


def synth_corpus(n, seed=0):
    rs = np.random.default_rng(seed)
    out = []
    for i in range(n):
        out.append("%s%s%s（%s类，第 %d 条）" % (
            _SUBJECTS[int(rs.integers(len(_SUBJECTS)))],
            _ADVERBS[int(rs.integers(len(_ADVERBS)))],
            _ITEMS[int(rs.integers(len(_ITEMS)))],
            _TOPICS[int(rs.integers(len(_TOPICS)))],
            i))
    return out


def clustered_corpus(n):
    """★ trap 模式专用：故意生成**大量近重复**的语料。

    做法很土：所有字段都按模数循环，于是每 30 条就出现一个「同款」句子。
    为什么要这样？因为真实的记忆库就是这样 ——
    同一个偏好会在不同会话里被反复记下来，措辞略有不同。
    实验 3-1 那四种策略里，`remember_all` 产出的就是这种东西。

    这个退化结构是 trap 模式能复现的**前提**。用分布均匀的语料是复现不出来的
    —— 这一点本身就是那一节最该学的东西。
    """
    out = []
    for i in range(n):
        out.append("%s%s%s%s（%s类，第 %d 条）" % (
            _SUBJECTS[i % len(_SUBJECTS)],
            _ADVERBS[i % len(_ADVERBS)],
            _ITEMS[i % len(_ITEMS)],
            "这件事" if i % 2 else "",
            _TOPICS[i % len(_TOPICS)], i))
    return out


def normalise(matrix):
    """归一化之后，余弦相似度就是简单的点积。"""
    matrix = np.asarray(matrix, dtype="float32")
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def embed_cached(texts, tag):
    """嵌入 + 落盘缓存。第一次要等，之后是瞬间。"""
    if not os.path.isdir(CACHE_DIR):
        os.makedirs(CACHE_DIR)
    # ★ 缓存名里必须带上 LANG 和模型名。
    #   第一版只用了 tag + 条数 —— 中英文语料都是 36 条，于是切成英文之后
    #   **静默读到了中文的向量**，跑出一组看起来正常、实际全错的数。
    #   这个 bug 不报错，只是数字变了。
    path = os.path.join(CACHE_DIR, "%s-%s-%s-%d.npy"
                        % (tag, LANG, MODEL.replace(":", "_"), len(texts)))
    if os.path.exists(path):
        return normalise(np.load(path)), True
    started = time.time()
    vectors = np.array(embed(texts, MODEL), dtype="float32")
    np.save(path, vectors)
    print(t("embedded", n=len(texts), sec=time.time() - started,
            rate=len(texts) / max(0.001, time.time() - started)))
    return normalise(vectors), False


# --------------------------------------------------------------------------
#  文案（中英双语，包含所有输出）
# --------------------------------------------------------------------------

TEXT = {
    "zh": {
        "backend": "嵌入模型：",
        "corpus_size": "记忆库：{n} 条",
        "task_label": "问题：",
        "embedded": "  已嵌入 {n} 条，用了 {sec:.1f} 秒（{rate:.0f} 条/秒），已缓存",
        "cache_hit": "  （命中缓存，没有重新计算）",

        "ask_task": "请输入用户的问题（直接回车看示例）：",
        "examples_title": "几个示例（输入编号也行）：",
        "task_examples": [
            "帮我列一个成都出差期间的餐厅清单。",
            "下周出差要带什么？",
            "帮我订一家适合请客户吃饭的餐厅。",
            "周末想安排一次户外活动，有什么建议？",
        ],
        "need_task": "x 没有输入问题，退出。这个实验刻意不设默认问题 —— 检索的效果完全取决于问的是什么。",
        "no_tty": "检测到非交互环境，请把问题写在命令行：\n    python3 agent.py {mode} \"你的问题\"",

        "no_ollama_title": "x 连不上 Ollama（这个实验需要本地嵌入模型）",
        "no_ollama_help": """
和第 2 章那套环境一样：

    brew install ollama
    ollama serve                    # 另开一个终端让它一直跑
    ollama pull {model}             # 274MB，嵌入专用模型

不需要 API key。
""",
        "no_model_title": "x Ollama 在跑，但本地没有这个模型：{model}",
        "no_model_help": "    ollama pull {model}\n\n你本地有的：{have}\n",
        "not_embed_title": "x 这个模型不能做嵌入：{model}",
        "not_embed_help": """
生成模型和嵌入模型是**两类东西**。qwen3:0.6b 这种是用来生成文字的，
它会直接告诉你 "This server does not support embeddings"。

    ollama pull nomic-embed-text    # 或者 bge-m3

然后把本文件开头的 MODEL 改成它。
""",

        # ---- compare ----
        "cmp_title": "第一部分：稠密向量 vs 稀疏关键词（同一份语料，同一个问题）",
        "cmp_head": "  {name}",
        "cmp_row": "    {mark} {score:.4f}  {text}",
        "cmp_recall": "    召回率 {hit}/{total}",
        "cmp_missed": "    ☠ 漏掉了：{text}",
        "cmp_rank_title": "  三条标准答案在各自排序里排第几（共 {n} 条）：",
        "cmp_rank_row": "    {text:<34} 稀疏 #{sparse:<4} 稠密 #{dense}",
        "cmp_verdict": """
怎么读 —— **先看那三条标准答案各自排第几，再看召回率。**

  召回率只告诉你「进没进 top-{k}」，排名告诉你「差多远」。
  一条排第 21 的记忆，不是「差一点」，是**这条路上救不回来**。

★ 跑完想一件事：稠密检索把稀疏漏掉的救回来了吗？
  救回来几条？**剩下的那条是哪一条？**
  （提示：看一眼哪条记忆漏了会出人命。）

答案和分析在 SOLUTION 里，但先自己看数字。""",

        # ---- ann ----
        "ann_title": "第二部分：向量多了之后 —— 精确 / 投影树 / 可导航图",
        "ann_setup": "  语料 {n} 条 · 维度 {d} · top-{k} · 用 {q} 条查询量平均值",
        "ann_header": "  {name:<26}{build:>11}{query:>13}{recall:>9}{visited:>16}",
        "ann_cols": ("方法", "建索引", "每次查询", "召回率", "访问向量数"),
        "ann_row": "  {name:<26}{build:>8.0f} ms{query:>9.3f} ms{recall:>9.3f}{visited:>12d}/{total}",
        "ann_verdict": """
怎么读这张表 —— **「访问向量数」是解释其他三列的那一列。**

  精确检索访问全部 {n} 个 → 召回率必然 1.000，代价是每次都全算一遍。
  ANN 的全部本事就是**少看一些**：看得越少越快，也越容易漏。

  所以这张表里没有「哪个更好」，只有**你想在哪一点上停**。

★ 但请特别注意「建索引」那一列和「每次查询」那一列的**绝对值**：
  在 {n} 条这个规模上，ANN 是不是真的赢了精确检索？
  自己算一下。跑 `scale` 模式看这个答案什么时候会变。""",

        # ---- trap ----
        "trap_title": "第二部分之二：一个「调参数完全没用」的坑 ★★",
        "trap_intro": """
图索引有个参数叫 ef —— 候选队列的大小，也就是「允许同时记住几个暂时最好的」。
教科书说：ef 调大 → 搜得更久 → 召回率更高。

下面测两个变量的组合：

    ① 建图时**要不要加反向边**（ann.py 里 build_graph 的 undirected 开关，一行）
    ② 语料是**分布均匀**的，还是**有大量近重复**的

每一格都换 20 个不同的入口点各测一遍，因为这个坑是**入口相关**的 ——
只试一个入口点，你可能正好躲过去，也可能正好只踩到它。

先猜：哪一格的 ef 会失效？
""",
        "trap_corpus_head": "  语料：{name}（每个点到最近邻的相似度，中位数 {crowd:.4f}）",
        "trap_corpus_spread": "分布均匀（字段随机组合）",
        "trap_corpus_clustered": "大量近重复（字段按模数循环）",
        "trap_row": "    {name:<22} 卡死 {stuck:>2}/{total}   召回率不足 {broken:>2}/{total}   ef=200 召回率 min {lo:.3f} 中位 {mid:.3f}",
        "trap_name_directed": "只连「我的近邻」",
        "trap_name_undirected": "再加上反向边",
        "trap_verdict": """
★ 两列指标的意思：

  「卡死」  = 把 ef 从 {lo} 提到 {hi}，召回率**一个数都没动，而且还没到 1.000**
  「不足」  = ef 已经开到 {hi} 了，召回率仍然不到 1.000 的入口点个数

  ⚠️ 为什么要加「而且还没到 1.000」这个条件？因为「ef 无效」有两种相反的原因：
     召回率已经满了（好事），和卡在起点那片里出不来（坏事）。
     我第一版只数「ef 无效」，于是**全对的那一格显示 13/20，看起来像最坏的一格**。

  「卡死」不为 0 时，意味着：这不是「参数调得不够大」，是**根本到不了**。
  只连出边的图，搜索会卡在起点那一小片里；它访问的向量确实变多了，
  多访问的都是同一片里的。

  **一个 kNN 图不等于一个可导航的图。**
  HNSW 论文里那些看起来多余的设计（双向连接、多层入口点），解决的正是这件事。

★★ 但真正该带走的是**两份语料的对比**：

  分布均匀的那份，两种图都没问题 —— 这个 bug **根本不出现**。
  只有语料里塞满近重复时，有向图才塌。

  而真实的记忆库**就是**后者：同一个偏好在不同会话里被反复记下来，
  措辞略有不同。实验 3-1 的 `remember_all` 产出的正是这种东西。

  → 所以这个 bug 会**通过你的测试、然后在线上炸**。
    不是因为它难，是因为你的测试数据太干净。

☠ 而且它**不报错**。你会得到一个能跑、能返回结果、参数看起来也调过的
  检索系统，而某些入口点上它的召回率是 0.08。

⚠️ 交代一句：这个模式我返工过一次。第一版只对比有向/无向，用的是均匀语料，
   **复现不出来**（两组都是 1.000），我差点把这一节删掉。
   触发条件是语料的退化程度 —— 那才是这一节真正的内容。
""",
        "scale_title": "第二部分之三：ANN 从多大规模开始才划算",
        "scale_note": """
这一节用**随机向量**（不是真嵌入）—— 因为这里只量速度随规模怎么变，
和向量是什么意思无关。维度和真实嵌入一样（{d} 维）。
""",
        "scale_header": "  {n:>10}{exact:>16}{tree:>18}{verdict:>14}",
        "scale_cols": ("向量数", "精确 ms/次", "投影树20棵 ms/次", "谁更快"),
        "scale_row": "  {n:>10}{exact:>13.3f} ms{tree:>15.3f} ms{verdict:>14}",
        "scale_win_exact": "精确快 {x:.1f}×",
        "scale_win_tree": "树快 {x:.1f}×",
        "scale_verdict": """
★ 精确检索是 O(N)：向量翻 10 倍，时间就翻 10 倍。
  投影树是 O(log N)：翻 10 倍，时间只多一点。

  所以这不是「ANN 更快」，是**两条不同斜率的线**，它们有一个交点。
  交点左边用 ANN 是纯亏：多写几百行代码、多一份索引内存、
  召回率还从 1.000 掉下来 —— 换来的是更慢。

  实验 3-5 那 36 条记忆，和这里的 {small} 条，都在交点左边。
  **先量一下你的 N 在哪边，再决定要不要上 ANN。**""",

        "hint_rerun": "\n下一步：\n    {cmd}\n",
        "unknown_mode": "x 不认识的模式：",
        "help": """
======================================================================
 实验 3-4：稠密向量检索 —— 它救回了什么，又漏掉了什么
======================================================================

实验 3-5 结束在一个洞上：BM25 漏掉了「对花生过敏」，因为那句话和
问题**一个字都不重合**。标准答案是「上 embedding」。这个实验去验证它。

用法：
    python3 agent.py <模式> ["用户的问题"]

【模式】
    compare   稠密 vs 稀疏，同一份语料同一个问题     ★★★ 先跑这个
    ann       精确 / 投影树 / 可导航图，三方对比
    trap      一个「调参数完全没用」的坑              ★★
    scale     ANN 从多大规模开始才划算
    all       全部跑一遍

⚠️ 需要本地 Ollama + 一个嵌入模型：

    ollama pull nomic-embed-text          # 274MB

   不需要 API key。生成模型不能做嵌入。

★ 两个索引都从零写在 ann.py 里，只用 numpy，没有 annoy / hnswlib。
★ 所有召回率都是机械算出来的，不需要模型当裁判。

把开头的 LANG 改成 "en" 可切英文；把 MODEL 换成 bge-m3 可以看结论稳不稳。
详细讲解见 README.zh-CN.md。
""",
    },
    "en": {
        "backend": "Embedding model: ",
        "corpus_size": "Memory store: {n} entries",
        "task_label": "Question: ",
        "embedded": "  embedded {n} in {sec:.1f}s ({rate:.0f}/s), cached",
        "cache_hit": "  (cache hit, nothing recomputed)",

        "ask_task": "Enter the user's question (press Enter to see examples): ",
        "examples_title": "Some examples (a number works too):",
        "task_examples": [
            "Put together a restaurant list for my Chengdu work trip.",
            "What should I pack for next week's trip?",
            "Book me a restaurant suitable for entertaining a client.",
            "I want to plan an outdoor activity this weekend - suggestions?",
        ],
        "need_task": "x No question given, exiting. This lab deliberately has no default - retrieval quality depends entirely on what you ask.",
        "no_tty": "Non-interactive environment detected. Put the question on the command line:\n    python3 agent.py {mode} \"your question\"",

        "no_ollama_title": "x Can't reach Ollama (this lab needs a local embedding model)",
        "no_ollama_help": """
Same setup as chapter 2:

    brew install ollama
    ollama serve                    # leave running in another terminal
    ollama pull {model}             # 274MB, embedding-only model

No API key needed.
""",
        "no_model_title": "x Ollama is running but lacks this model: {model}",
        "no_model_help": "    ollama pull {model}\n\nYou have: {have}\n",
        "not_embed_title": "x This model cannot produce embeddings: {model}",
        "not_embed_help": """
Generative models and embedding models are **two different things**. Something
like qwen3:0.6b generates text; it will tell you outright
"This server does not support embeddings".

    ollama pull nomic-embed-text    # or bge-m3

Then set MODEL at the top of this file to it.
""",

        "cmp_title": "Part 1: dense vectors vs sparse keywords (same corpus, same question)",
        "cmp_head": "  {name}",
        "cmp_row": "    {mark} {score:.4f}  {text}",
        "cmp_recall": "    recall {hit}/{total}",
        "cmp_missed": "    ! MISSED: {text}",
        "cmp_rank_title": "  Where each of the three gold memories ranks (out of {n}):",
        "cmp_rank_row": "    {text:<34} sparse #{sparse:<4} dense #{dense}",
        "cmp_verdict": """
How to read this - **look at the three gold memories' ranks first, recall second.**

  Recall only tells you "did it make top-{k}". The rank tells you "by how far".
  A memory sitting at rank 21 isn't "close" - it is **unreachable by this route**.

* Once it's run, ask yourself: did dense retrieval rescue what sparse missed?
  How many? **Which one is still missing?**
  (Hint: look at which memory, if missed, sends someone to hospital.)

The answer and the analysis are in SOLUTION - but read the numbers yourself first.""",

        "ann_title": "Part 2: once there are a lot of vectors - exact / projection tree / navigable graph",
        "ann_setup": "  {n} vectors · dim {d} · top-{k} · averaged over {q} queries",
        "ann_header": "  {name:<26}{build:>11}{query:>13}{recall:>9}{visited:>16}",
        "ann_cols": ("method", "build", "per query", "recall", "vectors seen"),
        "ann_row": "  {name:<26}{build:>8.0f} ms{query:>9.3f} ms{recall:>9.3f}{visited:>12d}/{total}",
        "ann_verdict": """
How to read this - **"vectors seen" is the column that explains the other three.**

  Exact search looks at all {n}, so recall is necessarily 1.000, and the price is
  computing everything every time. An ANN index's entire trick is **looking at
  fewer**: fewer means faster, and fewer means more misses.

  So there's no "which is better" in this table, only **where you want to stop**.

* But look hard at the ABSOLUTE numbers in the build and per-query columns:
  at {n} vectors, did ANN actually beat exact search?
  Work it out. Then run `scale` to see when that answer changes.""",

        "trap_title": "Part 2b: a knob that does absolutely nothing **",
        "trap_intro": """
Graph indexes have a parameter called ef - the size of the candidate queue, i.e. how many
"best so far" results you may hold at once. Textbook: raise ef -> search longer -> higher
recall.

Below, two variables are crossed:

    (1) whether **reverse edges** are added when building the graph (the one-line
        `undirected` flag in ann.py's build_graph)
    (2) whether the corpus is **evenly spread** or **full of near-duplicates**

Every cell is measured from 20 different entry points, because this trap is
**entry-point dependent** - try only one and you may dodge it entirely, or hit only it.

Predict first: in which cell does ef stop working?
""",
        "trap_corpus_head": "  Corpus: {name} (median nearest-neighbour similarity {crowd:.4f})",
        "trap_corpus_spread": "evenly spread (fields combined at random)",
        "trap_corpus_clustered": "many near-duplicates (fields cycled modulo)",
        "trap_row": "    {name:<22} stuck {stuck:>2}/{total}   short of 1.000 {broken:>2}/{total}   recall@ef=200 min {lo:.3f} med {mid:.3f}",
        "trap_name_directed": "only \"my neighbours\"",
        "trap_name_undirected": "plus reverse edges",
        "trap_verdict": """
* What the two columns mean:

  "stuck"  = raising ef from {lo} to {hi} moved recall **not at all, and it is still below
             1.000**
  "short"  = entry points whose recall is still below 1.000 even at ef={hi}

  ⚠️ Why the "and still below 1.000" clause? Because "ef does nothing" has two opposite
     causes: recall is already perfect (good), and the search is trapped in the entry
     point's pocket (bad). My first version counted only "ef does nothing", so **the
     fully-correct cell showed 13/20 and looked like the worst one**.

  When "stuck" isn't 0, it means this is not "the knob wasn't turned far enough" - it is
  **cannot get there**. A graph with only outgoing edges traps the search in the entry
  point's pocket; it genuinely visits more vectors, all inside the same pocket.

  **A kNN graph is not the same thing as a navigable graph.** Those seemingly redundant
  parts of the HNSW paper (bidirectional links, multiple entry points across layers) are
  solving exactly this.

** But the thing actually worth taking away is the **comparison between the two corpora**:

  On the evenly spread corpus, both graphs are fine - the bug **does not appear at all**.
  Only when the corpus is packed with near-duplicates does the directed graph collapse.

  And a real memory store **is** the latter: the same preference recorded again and again
  across sessions, worded slightly differently. That is exactly what lab 3-1's
  `remember_all` produces.

  -> So this bug **passes your tests and then breaks in production** - not because it's
     subtle, but because your test data was too clean.

! And it raises no error. You get a retrieval system that runs, returns results, and has
  apparently been tuned - with recall 0.08 from some entry points.

⚠️ Disclosure: I reworked this mode once. The first version only contrasted directed vs
   undirected, on the evenly spread corpus, and **did not reproduce** (both were 1.000) -
   I nearly deleted the section. The trigger is how degenerate the corpus is, and that
   turned out to be the real content.
""",
        "scale_title": "Part 2c: at what scale does ANN start paying off?",
        "scale_note": """
This part uses **random vectors** (not real embeddings) - it only measures how
speed scales with size, which has nothing to do with what the vectors mean. The
dimensionality matches real embeddings ({d}).
""",
        "scale_header": "  {n:>10}{exact:>16}{tree:>18}{verdict:>14}",
        "scale_cols": ("vectors", "exact ms/query", "tree(20) ms/query", "winner"),
        "scale_row": "  {n:>10}{exact:>13.3f} ms{tree:>15.3f} ms{verdict:>14}",
        "scale_win_exact": "exact {x:.1f}x",
        "scale_win_tree": "tree {x:.1f}x",
        "scale_verdict": """
* Exact search is O(N): 10x the vectors, 10x the time.
  A projection tree is O(log N): 10x the vectors, barely more time.

  So this isn't "ANN is faster" - they're **two lines with different slopes**, and
  they cross. To the left of that crossing, ANN is a pure loss: several hundred
  more lines of code, an extra index in memory, recall dropping below 1.000 - in
  exchange for being slower.

  Lab 3-5's 36 memories, and the {small} here, are both left of the crossing.
  **Measure which side your N is on before reaching for an ANN index.**""",

        "hint_rerun": "\nNext:\n    {cmd}\n",
        "unknown_mode": "x unknown mode: ",
        "help": """
======================================================================
 Lab 3-4: Dense vector retrieval - what it rescues, what it still misses
======================================================================

Lab 3-5 ended on a hole: BM25 missed "severely allergic to peanuts" because that
sentence shares **not one word** with the question. The standard answer is "use
embeddings". This lab checks that answer.

Usage:
    python3 agent.py <mode> ["the user's question"]

MODES
    compare   dense vs sparse, same corpus, same question    *** start here
    ann       exact / projection tree / navigable graph
    trap      a knob that does absolutely nothing            **
    scale     at what scale does ANN start paying off
    all       run everything

⚠️ Needs local Ollama plus an embedding model:

    ollama pull nomic-embed-text          # 274MB

   No API key. Generative models cannot produce embeddings.

* Both indexes are written from scratch in ann.py using only numpy - no annoy,
  no hnswlib.
* Every recall figure is computed mechanically; no model acts as judge.

Set LANG = "en" at the top for English; set MODEL to bge-m3 to check whether the
conclusions hold.
Full walkthrough: README.md
""",
    },
}


def t(key, **kwargs):
    value = TEXT[LANG][key]
    if isinstance(value, str) and kwargs:
        return value.format(**kwargs)
    return value


# ==========================================================================
#  第 4 部分：compare —— 稠密 vs 稀疏  ★★★ 本实验的头条 ★★★
# ==========================================================================


def run_compare(question):
    memories = MEMORIES[LANG]
    vectors, cached = embed_cached(memories, "memories")
    if cached:
        print(t("cache_hit"))
    query_vec = normalise(np.array(embed([question], MODEL), dtype="float32"))[0]

    dense = vectors @ query_vec
    sparse = bm25_scores(question, memories)

    print("")
    print("=" * 70)
    print(t("cmp_title"))
    print("=" * 70)

    ranks = {}
    for name, scores in (("BM25 (sparse)", sparse), ("dense (%s)" % MODEL, dense)):
        order = np.argsort(-scores)
        ranks[name] = {int(v): r + 1 for r, v in enumerate(order)}
        top = [int(i) for i in order[:TOP_K]]
        print("")
        print(t("cmp_head", name=name))
        for i in top:
            print(t("cmp_row", mark="★" if i in TARGET_INDEXES else " ",
                    score=float(scores[i]), text=memories[i][:46]))
        hits = [i for i in TARGET_INDEXES if i in top]
        print(t("cmp_recall", hit=len(hits), total=len(TARGET_INDEXES)))
        for i in TARGET_INDEXES:
            if i not in top:
                print(t("cmp_missed", text=memories[i][:46]))

    print("")
    print(t("cmp_rank_title", n=len(memories)))
    for i in TARGET_INDEXES:
        print(t("cmp_rank_row", text=memories[i][:32],
                sparse=ranks["BM25 (sparse)"][i],
                dense=ranks["dense (%s)" % MODEL][i]))
    print(t("cmp_verdict", k=TOP_K))


# ==========================================================================
#  第 5 部分：ann —— 三种索引的代价
# ==========================================================================


def _corpus_vectors():
    texts = synth_corpus(CORPUS_N)
    vectors, cached = embed_cached(texts, "synth")
    if cached:
        print(t("cache_hit"))
    return vectors


def _queries(vectors):
    rs = np.random.default_rng(0)
    return vectors[rs.choice(len(vectors), min(N_QUERIES, len(vectors)), replace=False)]


def run_ann(vectors=None):
    X = _corpus_vectors() if vectors is None else vectors
    Q = _queries(X)
    k = 10

    print("")
    print("=" * 70)
    print(t("ann_title"))
    print("=" * 70)
    print(t("ann_setup", n=len(X), d=X.shape[1], k=k, q=len(Q)))
    print("")
    cols = t("ann_cols")
    print(t("ann_header", name=cols[0], build=cols[1], query=cols[2],
            recall=cols[3], visited=cols[4]))
    print("  " + "-" * 74)

    started = time.time()
    exact = [ann.exact_query(X, q, k)[0] for q in Q]
    exact_ms = (time.time() - started) / len(Q) * 1000
    print(t("ann_row", name="exact (brute force)", build=0.0, query=exact_ms,
            recall=1.0, visited=len(X), total=len(X)))

    for n_trees, leaf in ((1, 32), (5, 32), (20, 32), (5, 8)):
        started = time.time()
        forest = ann.build_forest(X, n_trees, leaf)
        build_ms = (time.time() - started) * 1000
        started = time.time()
        rows = [ann.forest_query(forest, X, q, k) for q in Q]
        query_ms = (time.time() - started) / len(Q) * 1000
        print(t("ann_row", name="tree  trees=%d leaf=%d" % (n_trees, leaf),
                build=build_ms, query=query_ms,
                recall=ann.recall_at_k([r[0] for r in rows], exact, k),
                visited=int(np.mean([r[1] for r in rows])), total=len(X)))

    rs = np.random.default_rng(1)
    entries = list(rs.choice(len(X), 8, replace=False))
    started = time.time()
    graph = ann.build_graph(X, 16, undirected=True)
    build_ms = (time.time() - started) * 1000
    for ef in (10, 50, 200):
        started = time.time()
        rows = [ann.graph_query(graph, X, q, k, ef, entries) for q in Q]
        query_ms = (time.time() - started) / len(Q) * 1000
        print(t("ann_row", name="graph deg=16 ef=%d" % ef,
                build=build_ms, query=query_ms,
                recall=ann.recall_at_k([r[0] for r in rows], exact, k),
                visited=int(np.mean([r[1] for r in rows])), total=len(X)))

    print(t("ann_verdict", n=len(X)))


# ==========================================================================
#  第 6 部分：trap —— 一行代码决定 ef 有没有用  ★★
# ==========================================================================


def _sweep_entries(X, graph, Q, exact, k, efs, entries):
    """对每个入口点单独测一遍。返回 [(入口, {ef: 召回率})]。"""
    out = []
    for entry in entries:
        by_ef = {}
        for ef in efs:
            rows = [ann.graph_query(graph, X, q, k, ef, [int(entry)])[0] for q in Q]
            by_ef[ef] = ann.recall_at_k(rows, exact, k)
        out.append((int(entry), by_ef))
    return out


def run_trap():
    """★★ 一行代码（反向边）× 语料结构，两者一起决定 ef 有没有用。

    ⚠️ 这个模式的设计经过一次返工。第一版只对比「有向 vs 无向」，
       用的是分布均匀的语料 —— **复现不出来**（两组都是 1.000）。
       真正的触发条件是**语料里有大量近重复**。
       所以现在两种语料都跑，让你看到它是数据相关的。
    """
    k = 10
    efs = (10, 200)
    rs = np.random.default_rng(7)

    print("")
    print("=" * 70)
    print(t("trap_title"))
    print("=" * 70)
    print(t("trap_intro"))

    for corpus_key, texts in (("trap_corpus_spread", synth_corpus(CORPUS_N)),
                              ("trap_corpus_clustered", clustered_corpus(CORPUS_N))):
        tag = "synth" if corpus_key.endswith("spread") else "clustered"
        X, cached = embed_cached(texts, tag)
        if cached:
            print(t("cache_hit"))
        Q = _queries(X)
        exact = [ann.exact_query(X, q, k)[0] for q in Q]

        # 量一下这份语料有多「挤」：每个点到最近邻的相似度
        sim = X @ X.T
        np.fill_diagonal(sim, -2.0)
        crowding = float(np.median(sim.max(axis=1)))

        print("")
        print(t("trap_corpus_head", name=t(corpus_key), crowd=crowding))

        entries = [0, 1, 2] + list(rs.choice(len(X), 17, replace=False))
        for undirected, name_key in ((False, "trap_name_directed"),
                                     (True, "trap_name_undirected")):
            graph = ann.build_graph(X, 16, undirected=undirected)
            swept = _sweep_entries(X, graph, Q, exact, k, efs, entries)
            finals = [by[efs[-1]] for _, by in swept]

            # ★ 这两个指标必须分开数，我第一版把它们混成一个，直接读出了反的结论。
            #
            #   「ef 无效」有两种完全相反的原因：
            #     ① 召回率已经是 1.000 了 —— ef 当然没用，这是**好事**
            #     ② 卡在起点那一片里出不来 —— ef 再大也没用，这是**坏事**
            #
            #   只数「ef 无效」会把这两种算成一样。均匀语料 + 无向图那一格
            #   会显示 13/20「ef 无效」，而它其实是全对的那一格。
            stuck = [e for e, by in swept
                     if abs(by[efs[-1]] - by[efs[0]]) < 1e-9 and by[efs[-1]] < 0.99]
            broken = [f for f in finals if f < 0.99]
            print(t("trap_row", name=t(name_key),
                    stuck=len(stuck), broken=len(broken), total=len(swept),
                    lo=min(finals), mid=float(np.median(finals))))

    print(t("trap_verdict", lo=efs[0], hi=efs[-1]))


# ==========================================================================
#  第 7 部分：scale —— 交点在哪
# ==========================================================================


def run_scale():
    dim = 768
    k = 10
    rs = np.random.default_rng(0)

    print("")
    print("=" * 70)
    print(t("scale_title"))
    print("=" * 70)
    print(t("scale_note", d=dim))
    cols = t("scale_cols")
    print(t("scale_header", n=cols[0], exact=cols[1], tree=cols[2], verdict=cols[3]))
    print("  " + "-" * 58)

    for n in (2000, 10000, 50000, 200000):
        X = normalise(rs.normal(size=(n, dim)))
        Q = X[rs.choice(n, 20, replace=False)]

        started = time.time()
        for q in Q:
            ann.exact_query(X, q, k)
        exact_ms = (time.time() - started) / len(Q) * 1000

        forest = ann.build_forest(X, 20, 32)
        started = time.time()
        for q in Q:
            ann.forest_query(forest, X, q, k)
        tree_ms = (time.time() - started) / len(Q) * 1000

        if exact_ms < tree_ms:
            verdict = t("scale_win_exact", x=tree_ms / max(1e-9, exact_ms))
        else:
            verdict = t("scale_win_tree", x=exact_ms / max(1e-9, tree_ms))
        print(t("scale_row", n=n, exact=exact_ms, tree=tree_ms, verdict=verdict))
        del X

    print(t("scale_verdict", small=CORPUS_N))


# ==========================================================================
#  第 8 部分：入口
# ==========================================================================


def ask_for_task(mode):
    """让用户输入问题。故意不设默认值。"""
    if not sys.stdin.isatty():
        print("")
        print(t("no_tty", mode=mode))
        sys.exit(1)

    answer = input(t("ask_task")).strip()
    if not answer:
        print("")
        print(t("examples_title"))
        examples = t("task_examples")
        for i in range(len(examples)):
            print("  " + str(i + 1) + ". " + examples[i])
        print("")
        answer = input(t("ask_task")).strip()
    if not answer:
        print("")
        print(t("need_task"))
        sys.exit(1)
    if answer.isdigit():
        examples = t("task_examples")
        index = int(answer)
        if 1 <= index <= len(examples):
            return examples[index - 1]
    return answer


def _quiet_ctrl_c(exc_type, exc_value, tb):
    if exc_type is KeyboardInterrupt:
        print("")
        sys.exit(130)
    sys.__excepthook__(exc_type, exc_value, tb)


sys.excepthook = _quiet_ctrl_c


if __name__ == "__main__":
    if len(sys.argv) == 1 or sys.argv[1] in ("-h", "--help", "help"):
        print(t("help"))
        sys.exit(0)

    mode = sys.argv[1]
    if mode not in MODES and mode != "all":
        print("")
        print(t("unknown_mode") + mode)
        print(t("help"))
        sys.exit(1)

    needs_question = mode in ("compare", "all")
    question = None
    if needs_question:
        question = sys.argv[2] if len(sys.argv) > 2 else ask_for_task(mode)

    # scale 模式不碰 Ollama（用随机向量），所以不用检查嵌入模型
    if mode != "scale":
        try:
            ensure_ready(MODEL)
        except OllamaNotRunning:
            print("")
            print(t("no_ollama_title"))
            print(t("no_ollama_help", model=MODEL))
            sys.exit(1)
        except ModelMissing:
            print("")
            print(t("no_model_title", model=MODEL))
            print(t("no_model_help", model=MODEL, have=", ".join(list_models()) or "-"))
            sys.exit(1)
        except NotAnEmbeddingModel:
            print("")
            print(t("not_embed_title", model=MODEL))
            print(t("not_embed_help"))
            sys.exit(1)
        print(t("backend") + MODEL)

    if question:
        print(t("corpus_size", n=len(MEMORIES[LANG])))
        print(t("task_label") + question)

    if mode == "compare":
        run_compare(question)
        print(t("hint_rerun", cmd="python3 agent.py ann"))
    elif mode == "ann":
        run_ann()
        print(t("hint_rerun", cmd="python3 agent.py trap"))
    elif mode == "trap":
        run_trap()
        print(t("hint_rerun", cmd="python3 agent.py scale"))
    elif mode == "scale":
        run_scale()
    else:
        run_compare(question)
        run_ann()
        run_trap()          # trap 自己管语料（要用退化那份），不复用 ann 的
        run_scale()
