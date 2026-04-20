"""
回测配置 —— 所有可调整参数的集中定义。

设计意图：
1. frozen=True 保证配置对象不可变，避免回测过程中被意外修改。
   回测是确定性计算，配置一旦确定就不该变，否则调试时会出现"我明明设的 top_n=10，
   怎么变成 5 了"的诡异问题。
2. 所有参数集中在一处，方便前端表单直接映射到这个 dataclass。
3. signal_filter 用 Optional[BaseFactor] 而非字符串，保证类型安全 ——
   编译期就能发现传错类型，而不是运行到一半才报错。

对应 BACKTEST_DESIGN.md §6.2
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Optional

if TYPE_CHECKING:
    # TYPE_CHECKING 避免循环导入：config.py 被 engine.py 和 result.py 同时导入，
    # 而 BaseFactor 在 factors/base.py 里，如果直接 import 会形成循环依赖。
    from fund_screener.factors.base import BaseFactor


@dataclass(frozen=True)
class BacktestConfig:
    """
    回测配置 —— frozen dataclass，所有字段在创建后不可修改。

    Attributes:
        top_n: 每次调仓选多少只基金
        rebalance_freq: 调仓频率，pandas offset alias
            - "ME" = 月末 (Month End)
            - "W-FRI" = 每周五
            - "QE" = 季末 (Quarter End)
        weighting: 权重分配策略
            - "equal": 等权，每只入选基金 1/N
            - "score": 按分数加权，分数越高权重越大
        fee_rate: 单边交易成本（申购费），默认 0.0015 = 0.15%
            一折后的 typical 申购费率，如果未来支持场内 ETF 可改更低
        init_cash: 初始资金，默认 100 万
        signal_filter: 信号过滤因子（可选），必须是 kind='signal' 的因子
            例如 MACrossFactor(20, 60) 表示"只在 MA 多头排列的基金中选"
        benchmark_code: 基准指数代码，用于对比（如 "000300.SH" 沪深300）
        use_adj_nav: 是否使用复权净值（Phase 3 先 False，回填完成后切 True）
    """

    # 组合构建规则
    top_n: int = 10
    rebalance_freq: str = "ME"  # pandas offset alias
    weighting: Literal["equal", "score"] = "equal"

    # 交易成本
    fee_rate: float = 0.0015  # 申购费率（一折后约 0.15%）

    # 初始资金
    init_cash: float = 1_000_000.0

    # 信号过滤（可选）— 必须是 kind='signal' 的因子
    signal_filter: Optional["BaseFactor"] = None

    # 基准
    benchmark_code: Optional[str] = "000300.SH"

    # 数据列选择
    use_adj_nav: bool = False  # Phase 3 先 False，回填完成后切 True
