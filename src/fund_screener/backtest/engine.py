"""
回测引擎 —— signal_df × nav_df → 绩效指标。

设计意图（修改前必须输出）：
为什么用 vectorbt v1 的 Portfolio.from_orders(size_type='targetpercent')？

组合回测中最容易出错的环节不是"算收益率"，而是"资金管理"：
- 今天信号说买 A 和 B，各 50% 权重
- 但昨天 A 涨了 10%，B 跌了 5%，实际仓位已经偏了
- 再平衡时怎么算？卖掉一部分 A、买一部分 B，还是只调差额？
- 如果现金不够买齐怎么办？如果某只基金停牌怎么办？

from_orders(size_type='targetpercent') 在底层用 Numba 写了完整的资金分配逻辑：
- 每天检查目标权重 vs 实际权重
- 计算需要买卖的份额
- 处理现金不足、停牌、价格缺失等边界
- 自动扣除手续费

我们只用 vectorbt 的这一件事：生成组合净值曲线和绩效指标。
因子计算全用 pandas。

职责边界（ARCHITECTURE.md 原则三）：
- 做：signal_df × nav_df → 组合净值 → 绩效指标
- 不做：因子计算（因子层）、数据清洗（storage.py）、报告生成（reporter.py）

对应 BACKTEST_DESIGN.md §6.3
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from fund_screener.factors.base import BaseFactor

from .config import BacktestConfig
from .result import BacktestResult

# vectorbt 导入做容错处理 —— BACKTEST_DESIGN.md §12 风险回退方案
# 如果 vectorbt 安装失败（numba 编译问题），给出清晰的错误提示
try:
    import vectorbt as vbt
except ImportError as e:
    raise ImportError(
        "vectorbt is required but not installed or failed to import. "
        "Please run: uv add vectorbt==0.26.0\n"
        f"Original error: {e}"
    ) from e


class BacktestEngine:
    """
    基于 vectorbt v1 的回测引擎。

    核心流程：
    1. 用 score_factor 给所有基金每天打分
    2. 用 signal_filter 过滤掉不想要的（如 MA 空头排列的）
    3. 按 rebalance_freq 定期调仓，选 Top N
    4. 用 vectorbt 模拟交易，输出绩效指标
    """

    def __init__(self, nav_panel: pd.DataFrame, config: BacktestConfig) -> None:
        """
        初始化回测引擎。

        Args:
            nav_panel: 宽表 DataFrame，index=date(DatetimeIndex)，columns=fund_code，values=净值
            config: 回测配置
        """
        self.nav_panel = nav_panel
        self.config = config

    def run(
        self,
        score_factor: BaseFactor,
        context: Optional[dict] = None,
    ) -> BacktestResult:
        """
        执行回测。

        Args:
            score_factor: 用于打分选 Top N 的因子（kind='score'）
            context: 额外数据，传给因子的 compute()

        Returns:
            BacktestResult，包含净值曲线、回撤、绩效指标、调仓历史
        """
        context = context or {}

        # Step 1: 计算打分因子（面板级运算，一次性算完所有日期、所有基金）
        score_output = score_factor.compute(self.nav_panel, **context)
        scores = score_output.values  # DataFrame: date × fund_code

        # Step 2: 应用 signal 过滤（如 MA 多头排列）
        if self.config.signal_filter is not None:
            filter_output = self.config.signal_filter.compute(
                self.nav_panel, **context
            )
            # 被过滤掉的基金：分数设为 -inf（永远选不上）
            # 用 where 语义：filter 为 True 的位置保留原分数，False 的位置设为 -inf
            scores = scores.where(filter_output.values, other=-np.inf)

        # Step 3: 构建目标持仓权重矩阵
        target_weights = self._build_target_weights(scores)

        # Step 4: 用 vectorbt 跑回测
        # size_type='targetpercent' 是关键：每天按目标权重百分比调整持仓
        # vectorbt 会自动处理：
        #   - NaN = 不下单 = 保持当前持仓
        #   - 0.0 = 清仓
        #   - 正数 = 按目标百分比分配资金
        pf = vbt.Portfolio.from_orders(
            close=self.nav_panel,
            size=target_weights,
            size_type="targetpercent",
            fees=self.config.fee_rate,
            init_cash=self.config.init_cash,
            cash_sharing=True,  # 所有基金共享一个现金池
            group_by=True,  # 作为一个组合整体回测
            freq="1D",
        )

        return BacktestResult(
            portfolio=pf,
            target_weights=target_weights,
            score_factor_name=score_factor.name,
            config=self.config,
        )

    def _build_target_weights(self, scores: pd.DataFrame) -> pd.DataFrame:
        """
        把打分矩阵变成目标持仓权重矩阵。

        核心逻辑：
        1. 确定调仓日（按 rebalance_freq）
        2. 每个调仓日，选当前分数最高的 Top N
        3. 根据 weighting 策略分配权重
        4. 非调仓日：NaN（vbt 会忽略，保持当前持仓不变）
        5. 被 signal 过滤掉的：从候选池剔除（分数为 -inf）

        Returns:
            DataFrame: index=date, columns=fund_code, values=目标权重(0~1) 或 NaN

        威胁缓解（T-03-06）：
        - 等权：1/N × N = 1.0，保证和为 1.0
        - 分数加权：shifted / shifted.sum()，保证和为 1.0
        - 空仓：全部设为 0.0
        """
        # 生成调仓日（如每月最后一个交易日）
        rebalance_dates = scores.resample(self.config.rebalance_freq).last().index
        rebalance_dates = rebalance_dates.intersection(scores.index)

        # 初始化权重矩阵（全 NaN = 不下单 = 保持当前持仓）
        # 为什么用 NaN 而不是 0.0？
        # 因为 vbt 的 from_orders 中，NaN 表示"不下单"，保持当前持仓；
        # 0.0 表示"清仓"。非调仓日我们希望保持持仓不变，所以用 NaN。
        weights = pd.DataFrame(
            np.nan, index=scores.index, columns=scores.columns
        )

        for dt in rebalance_dates:
            row = scores.loc[dt]

            # 排除被 signal_filter 过滤掉的（-inf）和 NaN
            valid_scores = row[row > -np.inf]
            # 同时排除 NaN（数据缺失的基金）
            valid_scores = valid_scores.dropna()

            # 选 Top N
            top_funds = valid_scores.nlargest(self.config.top_n)

            if len(top_funds) == 0:
                # 空仓：所有基金权重设为 0（触发全部卖出）
                weights.loc[dt] = 0.0
                continue

            if self.config.weighting == "equal":
                # 等权分配
                w = 1.0 / len(top_funds)
                weights.loc[dt, top_funds.index] = w
                # 其他基金显式设为 0（触发卖出）
                others = weights.columns.difference(top_funds.index)
                weights.loc[dt, others] = 0.0

            elif self.config.weighting == "score":
                # 按分数加权 —— min-max 归一化后加权
                # 先处理负数：shift 到全正，避免负权重
                min_score = top_funds.min()
                shifted = top_funds - min_score + 1e-6  # 1e-6 避免全 0
                normalized = shifted / shifted.sum()
                weights.loc[dt, normalized.index] = normalized.values
                others = weights.columns.difference(normalized.index)
                weights.loc[dt, others] = 0.0

        return weights
