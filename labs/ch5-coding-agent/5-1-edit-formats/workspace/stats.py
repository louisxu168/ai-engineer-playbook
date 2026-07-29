"""一个很小的统计工具库。

⚠️ 这个文件里**有一个 bug**，被 test_stats.py 抓到了。
   实验 5-1 就是让 agent 来修它。

（你可以先自己找找看 —— 找到了也别改，改了实验就没得跑了。）
"""


def mean(numbers):
    """算术平均数。"""
    if len(numbers) == 0:
        raise ValueError("mean() 需要至少一个数")
    return sum(numbers) / len(numbers)


def median(numbers):
    """中位数：把数排好序，取中间那个。

    如果个数是偶数，中间有两个数，应该取这两个数的平均值。
    """
    if len(numbers) == 0:
        raise ValueError("median() 需要至少一个数")
    ordered = sorted(numbers)
    middle = len(ordered) // 2
    return ordered[middle]


def mode(numbers):
    """众数：出现次数最多的那个数。多个并列时返回最小的那个。"""
    if len(numbers) == 0:
        raise ValueError("mode() 需要至少一个数")
    counts = {}
    for one in numbers:
        counts[one] = counts.get(one, 0) + 1
    best_count = max(counts.values())
    winners = [k for k in counts if counts[k] == best_count]
    return min(winners)


def variance(numbers):
    """总体方差（除以 n，不是 n-1）。"""
    if len(numbers) == 0:
        raise ValueError("variance() 需要至少一个数")
    m = mean(numbers)
    total = 0.0
    for one in numbers:
        total = total + (one - m) ** 2
    return total / len(numbers)


def stdev(numbers):
    """总体标准差。"""
    return variance(numbers) ** 0.5


def data_range(numbers):
    """极差：最大值减最小值。"""
    if len(numbers) == 0:
        raise ValueError("data_range() 需要至少一个数")
    return max(numbers) - min(numbers)


def percentile(numbers, p):
    """第 p 百分位数，用最近秩法（nearest-rank）。

    p 取 0 到 100。
    """
    if len(numbers) == 0:
        raise ValueError("percentile() 需要至少一个数")
    if not (0 <= p <= 100):
        raise ValueError("p 必须在 0 到 100 之间")
    ordered = sorted(numbers)
    if p == 0:
        return ordered[0]
    rank = int(-(-len(ordered) * p // 100))   # 向上取整
    return ordered[rank - 1]


def summarize(numbers):
    """把上面这些指标打包成一个字典。"""
    return {
        "count": len(numbers),
        "mean": mean(numbers),
        "median": median(numbers),
        "mode": mode(numbers),
        "variance": variance(numbers),
        "stdev": stdev(numbers),
        "range": data_range(numbers),
        "p25": percentile(numbers, 25),
        "p50": percentile(numbers, 50),
        "p75": percentile(numbers, 75),
    }


def normalize(numbers):
    """把一组数缩放到 0~1 之间。"""
    if len(numbers) == 0:
        raise ValueError("normalize() 需要至少一个数")
    low = min(numbers)
    high = max(numbers)
    if high == low:
        return [0.0 for _ in numbers]
    return [(one - low) / (high - low) for one in numbers]


def moving_average(numbers, window):
    """移动平均。window 是窗口大小。"""
    if window <= 0:
        raise ValueError("window 必须是正整数")
    if len(numbers) < window:
        return []
    result = []
    for i in range(len(numbers) - window + 1):
        chunk = numbers[i:i + window]
        result.append(sum(chunk) / window)
    return result
