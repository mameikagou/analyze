"""
量化因子 —— 动量、夏普比率、最大回撤。

这三个因子对应现有 risk_metrics.py 的三个纯函数，但改为面板级滚动计算。
区别：
- risk_metrics.py: 输入单只基金的 nav_series，输出单个 float（最新值）
- factors/quant.py: 输入全量基金的 nav_panel，输出滚动时间序列（每只基金每天的分数）

设计决策：
1. 用 math.sqrt() 而非 np.sqrt() 做标量开方 —— 与 risk_metrics.py 保持一致
2. 零波动 → NaN（不返回 inf），与 risk_metrics.py 的防御策略一致
3. MaxDrawdownFactor 用 O(n²) 朴素实现，文档中标注性能风险和优化路径
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .base import BaseFactor, FactorOutput


class MomentumFactor(BaseFactor):
    """
    趋势爆发力 = (nav - MA) / MA，滚动计算。

    正值 = 价格在均线之上（上涨势头），值越大势越猛。
    对应 risk_metrics.py:momentum_score() 的面板级版本。
    """

    def __init__(self, ma_period: int = 20) -> None:
        self.ma_period = ma_period
        self.name = f"momentum_ma{ma_period}"

    def compute(self, nav_panel: pd.DataFrame, **context) -> FactorOutput:
        """
        计算动量分数矩阵。

        Args:
            nav_panel: 宽表 DataFrame，index=date，columns=fund_code，values=净值
            **context: 预留，暂未使用

        Returns:
            FactorOutput，values 为浮点矩阵，kind="score"
        """
        ma = nav_panel.rolling(window=self.ma_period, min_periods=self.ma_period).mean()
        momentum = (nav_panel - ma) / ma

        return FactorOutput(
            values=momentum,
            kind="score",
            name=self.name,
            description=f"偏离 MA{self.ma_period} 的幅度（越大 = 冲劲越足）",
        )


class SharpeFactor(BaseFactor):
    """
    滚动年化夏普比率。

    公式：
        daily_returns = nav.pct_change()
        excess = daily_returns - rf/252
        rolling_mean = excess.rolling(window=lookback).mean()
        rolling_std = excess.rolling(window=lookback).std(ddof=1)
        sharpe = (rolling_mean / rolling_std) * sqrt(252)

    零波动（如货基、停牌）→ std=0 → 返回 NaN（不返回 inf）。
    对应 risk_metrics.py:sharpe_ratio() 的面板级版本。
    """

    def __init__(self, lookback: int = 252, rf_annual: float = 0.02) -> None:
        self.lookback = lookback
        self.rf = rf_annual / 252  # 日无风险利率
        self.name = f"sharpe_{lookback}"

    def compute(self, nav_panel: pd.DataFrame, **context) -> FactorOutput:
        """
        计算滚动夏普比率矩阵。

        Args:
            nav_panel: 宽表 DataFrame，index=date，columns=fund_code，values=净值
            **context: 预留，暂未使用

        Returns:
            FactorOutput，values 为浮点矩阵，kind="score"
        """
        returns = nav_panel.pct_change()
        excess = returns - self.rf

        rolling_mean = excess.rolling(
            window=self.lookback, min_periods=self.lookback
        ).mean()
        rolling_std = excess.rolling(
            window=self.lookback, min_periods=self.lookback
        ).std(ddof=1)

        # std == 0 → 除零 → 用 replace(0, np.nan) 避免 inf
        sharpe = (rolling_mean / rolling_std.replace(0, np.nan)) * math.sqrt(252)

        return FactorOutput(
            values=sharpe,
            kind="score",
            name=self.name,
            description=f"{self.lookback} 日滚动年化夏普比率",
        )


class MaxDrawdownFactor(BaseFactor):
    """
    滚动最大回撤（负数）。

    返回负值，越接近 0 越好（回撤越小）。
    CompositeFactor 在组合时会根据权重决定方向（通常给负权重，因为回撤是反向指标）。

    性能注意：
    当前实现是 O(n²) 的朴素算法 —— 对每个日期 i，计算 window[0:i+1] 的 cummax 和回撤。
    对于 1000 只基金 × 2000 天的面板，可能较慢。
    优化路径（未来）：
    1. 用 numba 加速 _rolling_max_dd 函数
    2. 预计算全区间回撤后截断到 lookback 窗口
    3. 用 expanding().apply() 替代逐列循环

    对应 risk_metrics.py:max_drawdown() 的面板级版本。
    """

    def __init__(self, lookback: int = 252) -> None:
        self.lookback = lookback
        self.name = f"max_dd_{lookback}"

    def compute(self, nav_panel: pd.DataFrame, **context) -> FactorOutput:
        """
        计算滚动最大回撤矩阵。

        Args:
            nav_panel: 宽表 DataFrame，index=date，columns=fund_code，values=净值
            **context: 预留，暂未使用

        Returns:
            FactorOutput，values 为浮点矩阵（负数），kind="score"
        """

        def _rolling_max_dd(series: pd.Series) -> pd.Series:
            """
            对单只基金计算滚动最大回撤。

            O(n²) 朴素实现：对每个位置 i，取前 i+1 天的数据计算历史最大回撤。
            为什么不用更高效的算法？因为 pandas 没有内置的 expanding().cummax()，
            且 rolling apply 不支持有状态的 cummax。先保证正确性，性能后续优化。
            """
            result = pd.Series(index=series.index, dtype=float)
            for i in range(len(series)):
                if i < 2:
                    # 前 2 天无法计算有意义的回撤（至少需要 2 个价格点）
                    result.iloc[i] = np.nan
                    continue
                window = series.iloc[: i + 1]
                cummax = window.cummax()
                # 防御：cummax 中任何值为 0 会导致除零
                cummax_safe = cummax.replace(0, np.nan)
                dd = (window - cummax_safe) / cummax_safe
                result.iloc[i] = dd.min()
            return result

        # 对每列（每只基金）应用滚动最大回撤计算
        # apply(axis=0) 按列遍历，每列是一个基金的净值序列
        dd_df = nav_panel.apply(_rolling_max_dd, axis=0)

        return FactorOutput(
            values=dd_df,
            kind="score",
            name=self.name,
            description=f"{self.lookback} 日滚动最大回撤（负数，越接近 0 越好）",
        )
