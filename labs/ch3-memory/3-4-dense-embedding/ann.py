"""两种近似最近邻（ANN）索引，从零实现，只用 numpy。

原书这个实验对比 ANNOY（树）和 HNSW（图）两个库。这里两个都自己写，
理由和实验 3-5 手写 BM25 一样：**你要看的是那个想法，不是那个包的 API。**

（另一个理由更实在：`annoy` 1.17.3 的 wheel 在这台机器上是坏的，
  任何输入都只返回 1 个结果。详见 SOLUTION 第 5 节。）

两种思路的一句话版本：

    投影树（ANNOY）：随机切空间，把邻居切到同一个叶子里。
                     查询时只看落到的那个叶子。多种几棵树补漏。

    可导航图（HNSW）：给每个点连上它的近邻，查询时从某个点出发，
                     一步步往「离查询更近」的邻居走。

两者都用**同一种方式**换性能：**少看一些向量**。
所以本实验统一量一个东西 —— **访问了几个向量**。
"""

import numpy as np


# ==========================================================================
#  第 1 种：随机投影树森林（ANNOY 的思路）
# ==========================================================================


def _build_tree(ids, X, leaf_size, rs):
    """递归切分。返回 ("leaf", ids) 或 ("node", 法向量, 阈值, 左, 右)。"""
    if len(ids) <= leaf_size:
        return ("leaf", ids)

    # ANNOY 的做法：随机挑两个点，用它们连线的中垂面当分割面。
    # 比「完全随机的方向」好，因为这个方向是数据本身给的。
    a, b = rs.choice(len(ids), 2, replace=False)
    normal = X[ids[a]] - X[ids[b]]
    if not np.any(normal):
        return ("leaf", ids)

    projection = X[ids] @ normal
    threshold = float(np.median(projection))     # 按中位数切，保证两边差不多大
    left = ids[projection <= threshold]
    right = ids[projection > threshold]
    if len(left) == 0 or len(right) == 0:
        return ("leaf", ids)

    return ("node", normal, threshold,
            _build_tree(left, X, leaf_size, rs),
            _build_tree(right, X, leaf_size, rs))


def build_forest(X, n_trees, leaf_size, seed=0):
    rs = np.random.default_rng(seed)
    ids = np.arange(len(X))
    return [_build_tree(ids, X, leaf_size, rs) for _ in range(n_trees)]


def _descend(node, q, out):
    """从根一路走到一个叶子，把叶子里的点收进候选集。"""
    while node[0] == "node":
        node = node[3] if q @ node[1] <= node[2] else node[4]
    out.update(int(i) for i in node[1])


def forest_query(forest, X, q, k):
    """返回 (top_k 下标, 访问了几个向量)。

    ★ 注意最后一步：候选集拿到之后**还要精确重排一次**。
      树只负责「把候选集缩小」，不负责排序 —— 这是所有 ANN 的通用结构。
    """
    candidates = set()
    for tree in forest:
        _descend(tree, q, candidates)
    ids = np.fromiter(candidates, dtype=np.int64)
    scores = X[ids] @ q
    return ids[np.argsort(-scores)[:k]], len(ids)


# ==========================================================================
#  第 2 种：可导航近邻图（HNSW 的思路）
# ==========================================================================


def build_graph(X, degree=16, undirected=True):
    """给每个点连上最近的 degree 个邻居。

    ★★ `undirected` 是这个实验最重要的一个开关。

    只连「我的近邻」得到的是**有向图**，它有个致命问题：
    可能走得进去、走不出来。搜索会卡在起点那一小片里，
    而且**把 ef 调大完全没用** —— 因为问题不是搜得不够久，是根本到不了。

    加上反向边（我是你的近邻 → 你也连我）图就连通了。
    HNSW 论文里那些看起来多余的设计（双向连接、多层入口），
    解决的正是这件事。`trap` 模式会让你亲眼看到这个区别。
    """
    similarity = X @ X.T
    np.fill_diagonal(similarity, -2.0)           # 别把自己当自己的邻居
    nearest = np.argsort(-similarity, axis=1)[:, :degree]

    adjacency = [set(int(j) for j in row) for row in nearest]
    if undirected:
        for i in range(len(nearest)):
            for j in nearest[i]:
                adjacency[int(j)].add(i)

    return [np.fromiter(a, dtype=np.int32) for a in adjacency]


def graph_query(graph, X, q, k, ef, entries):
    """贪心最优先搜索。返回 (top_k 下标, 访问了几个向量)。

    ef 是「候选队列」的大小 —— 允许同时记住几个「暂时最好的」。
    ef = k 时几乎是纯贪心，很容易走进死胡同；ef 越大越不容易，也越慢。
    """
    visited = set()
    frontier = []      # 待扩展，存 (-相似度, 下标)，所以排序后 pop(0) 拿到最相似的
    best = []          # 目前最好的 ef 个，存 (相似度, 下标)

    for entry in entries:
        entry = int(entry)
        if entry in visited:
            continue
        visited.add(entry)
        score = float(X[entry] @ q)
        frontier.append((-score, entry))
        best.append((score, entry))

    while frontier:
        frontier.sort()
        neg_score, current = frontier.pop(0)
        # 停止条件：连最有希望的候选都比 best 里最差的还差，就没必要继续了
        if len(best) >= ef and -neg_score < min(b[0] for b in best):
            break
        for neighbour in graph[current]:
            neighbour = int(neighbour)
            if neighbour in visited:
                continue
            visited.add(neighbour)
            score = float(X[neighbour] @ q)
            frontier.append((-score, neighbour))
            best.append((score, neighbour))
            if len(best) > ef:
                best.sort(reverse=True)
                best = best[:ef]

    best.sort(reverse=True)
    return [i for _, i in best[:k]], len(visited)


# ==========================================================================
#  精确检索（基准）
# ==========================================================================


def exact_query(X, q, k):
    """全部算一遍。这就是「访问 N 个向量」的那条基线。"""
    scores = X @ q
    return np.argsort(-scores)[:k], len(X)


def recall_at_k(approx_rows, exact_rows, k):
    """ANN 的召回率 = 和精确结果的重合比例。**不需要任何标注。**"""
    hits = []
    for approx, exact in zip(approx_rows, exact_rows):
        hits.append(len(set(int(i) for i in approx) & set(int(i) for i in exact)) / k)
    return float(np.mean(hits))
