"""refactor 任务的额外测试。

⚠️ 文件名故意不叫 test_*.py —— 这样 `unittest` 的默认发现规则不会捡到它。
   只有当你跑 refactor 任务时，程序才会把它复制成 test_errors.py 放进工作副本。

  这样一来：
    - fix 任务只跑 test_stats.py（20 个测试）
    - refactor 任务跑 test_stats.py + test_errors.py（20 + 9 个测试）

★ refactor 任务比 fix 难得多：它要在**同一个文件的 7 个不同位置**做几乎一样的改动，
  而那 7 处的上下文**长得一模一样**：

      if len(numbers) == 0:
          raise ValueError("xxx() 需要至少一个数")

  只有引号里的函数名不同。这正是用来考验三种编辑格式的地方。
"""

import unittest

import stats


class TestEmptyDataError(unittest.TestCase):
    """所有函数遇到空输入时，都应该抛 stats.EmptyDataError。"""

    def test_error_class_exists(self):
        self.assertTrue(hasattr(stats, "EmptyDataError"))

    def test_is_a_valueerror(self):
        # 为了不破坏老代码，它应该是 ValueError 的子类
        self.assertTrue(issubclass(stats.EmptyDataError, ValueError))

    def test_mean(self):
        with self.assertRaises(stats.EmptyDataError):
            stats.mean([])

    def test_median(self):
        with self.assertRaises(stats.EmptyDataError):
            stats.median([])

    def test_mode(self):
        with self.assertRaises(stats.EmptyDataError):
            stats.mode([])

    def test_variance(self):
        with self.assertRaises(stats.EmptyDataError):
            stats.variance([])

    def test_data_range(self):
        with self.assertRaises(stats.EmptyDataError):
            stats.data_range([])

    def test_percentile(self):
        with self.assertRaises(stats.EmptyDataError):
            stats.percentile([], 50)

    def test_normalize(self):
        with self.assertRaises(stats.EmptyDataError):
            stats.normalize([])


if __name__ == "__main__":
    unittest.main()
