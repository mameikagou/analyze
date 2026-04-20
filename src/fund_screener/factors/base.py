"""
因子层抽象基类与统一输出契约。

设计意图：
1. 因子（Factor）和策略（Strategy）必须解耦 —— ARCHITECTURE.md 原则一。
   因子只管"给每只基金打分/产生信号"，策略只管"拿到信号后怎么交易"。
2. 信号（Signal）是因子和回测之间的唯一契约 —— ARCHITECTURE.md 原则二。
   所有因子无论内部怎么算，最终必须吐出同一种 FactorOutput 格式。
3. 因子层不做任何 I/O（不读 DB、不调 API），纯矩阵运算。
   外部数据通过 nav_panel 和 **context 传入，保证可测试性和无副作用。

为什么用 frozen dataclass 做 FactorOutput？
- frozen=True 保证输出不可变，防止因子实现或调用方意外修改值，
  避免"我明明算出来是 True，怎么变成 False 了"的调试噩梦。
- dataclass 自动生成 __repr__、__eq__，方便日志输出和断言比对。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

import pandas as pd


@dataclass(frozen=True)
class FactorOutput:
    """
    所有因子的统一输出格式 —— 因子层和回测层之间的唯一契约。

    对应 ARCHITECTURE.md 原则二：信号（Signal）是因子和回测之间的唯一契约。

    Attributes:
        values: 宽表 DataFrame，index=date(DatetimeIndex)，columns=fund_code。
                shape 必须与输入 nav_panel 完全一致。
        kind: 因子的性质，决定它在回测里怎么被使用。
              - "signal": 布尔值，True=持有，False=空仓（如 MA 多头排列）
              - "score":  连续值，越大越好（如夏普比率，用于排序选 Top N）
              - "weight": 权重值，sum<=1（预留，Phase 3 暂不支持）
        name: 因子标识名，用于日志和报告。
        description: 因子描述，用于前端展示。
    """

    values: pd.DataFrame
    kind: Literal["signal", "score", "weight"]
    name: str
    description: str = ""


class BaseFactor(ABC):
    """
    所有因子的抽象基类。

    子类必须实现 compute() 方法。因子层不做任何 I/O（不读 DB、不调 API），
    所有外部数据通过 nav_panel 和 **context 传入。
    """

    @abstractmethod
    def compute(
        self,
        nav_panel: pd.DataFrame,  # index=date, columns=fund_code
        **context,  # 预留给需要额外数据的因子（如新闻、持仓）
    ) -> FactorOutput:
        """
        核心方法：输入净值面板，输出因子值。

        Args:
            nav_panel: 宽表 DataFrame，index 为日期（DatetimeIndex，日频），
                       columns 为基金代码，values 为净值（已处理 NaN，见 BACKTEST_DESIGN.md §5）
            **context: 额外上下文数据。例如：
                       - context['news_df']: 新闻情感分面板（后期时政因子用）
                       - context['holdings_df']: 持仓权重面板（后期 weight 因子用）

        Returns:
            FactorOutput，values 的 shape 必须与 nav_panel 完全一致
            （相同的 index 和 columns，允许 values 中有 NaN）
        """
        ...

    def __add__(self, other: BaseFactor) -> CompositeFactor:
        """
        语法糖：factor_a + factor_b → CompositeFactor

        注意：只有 kind='score' 的因子可以用 + 组合。
        CompositeFactor 的实现见 factors/composite.py。

        为什么需要语法糖？
        让因子组合写起来像数学表达式：momentum + sharpe，而不是
        CompositeFactor([momentum, sharpe], [0.5, 0.5])，降低心智负担。
        """
        from .composite import CompositeFactor

        return CompositeFactor([self, other])
