"""
技术面信号因子 —— MA 均线交叉（多头排列）。

对应现有 screener.py:screen_fund() 的核心逻辑，但改为面板级矩阵运算。
面板级运算的优势：一次性算完所有基金的所有日期，避免逐只基金循环的低效。

与现有代码的关系：
- screener.py:calculate_ma() 和 screen_fund() 保留不动，继续给 CLI 和 API 用
- MACrossFactor 是同一逻辑的面板级重写，面向回测场景
"""

from __future__ import annotations

import pandas as pd

from .base import BaseFactor, FactorOutput


class MACrossFactor(BaseFactor):
    """
    MA 短期均线 > 长期均线时产生持有信号。

    当 short 周期均线在长期均线之上时，认为该基金处于上升趋势（多头排列），
    输出 True（建议持有）；反之输出 False（空仓）。

    边界处理：
    1. 前 `long` 天数据不足，强制置 False（不可交易，避免用不成熟的 MA 值做决策）
    2. NaN 位置（基金未上市或数据缺失）置 False（不可交易）
    """

    def __init__(self, short: int = 20, long: int = 60) -> None:
        self.short = short
        self.long = long
        self.name = f"ma_cross_{short}_{long}"

    def compute(self, nav_panel: pd.DataFrame, **context) -> FactorOutput:
        """
        计算 MA 交叉信号矩阵。

        Args:
            nav_panel: 宽表 DataFrame，index=date，columns=fund_code，values=净值
            **context: 预留，暂未使用

        Returns:
            FactorOutput，values 为布尔矩阵，kind="signal"
        """
        # 宽表矩阵运算：一次性算完所有基金的滚动均值
        # rolling(..., min_periods=period) 保证前 period-1 个值为 NaN，
        # 这样 fast > slow 在这些位置也是 NaN，后续会被强制置 False
        fast = nav_panel.rolling(window=self.short, min_periods=self.short).mean()
        slow = nav_panel.rolling(window=self.long, min_periods=self.long).mean()

        # 信号矩阵：True = MA_short > MA_long（多头排列）
        signal = fast > slow

        # 前 `long` 天数据不足，强制置 False（不可交易）
        # 为什么用 iloc[:self.long] 而不是等 self.long 天自然成熟？
        # 因为 rolling(min_periods=period) 已经保证了第 period 天才有有效值，
        # 但 fast(20) 和 slow(60) 的"有效"不同步 —— 第 20 天 fast 有值但 slow 还是 NaN。
        # 这里显式强制前 60 天全 False，避免任何歧义。
        signal.iloc[: self.long] = False

        # NaN 位置（基金未上市或数据缺失）置 False
        # 用 where 比 fillna 语义更清晰："只在 nav_panel 有值的位置保留信号，其他置 False"
        signal = signal.where(nav_panel.notna(), False)

        return FactorOutput(
            values=signal,
            kind="signal",
            name=self.name,
            description=f"MA{self.short} 上穿 MA{self.long} 多头排列信号",
        )
