"""
MA 均线筛选引擎。

核心筛选逻辑：MA_short > MA_long（均线金叉 / 多头排列）。
这是典型的"右侧交易"信号 — 趋势已经确立才入场。

重要提醒（给用户的）：
- MA 交叉是滞后指标，它确认趋势而非预测趋势
- 这是过滤器，不是预测器。通过筛选 ≠ 一定赚钱
- 用户需要结合其他分析（LLM 交叉分析）做最终决策
"""

from __future__ import annotations

import logging

import pandas as pd

from fund_screener.models import ScreenResult, TrendStats

logger = logging.getLogger(__name__)


# 多周期涨跌幅的交易日映射
# 为什么用交易日而不是自然日？因为股市周末不开盘，
# 用自然日会把周末算进去，导致"1 周"实际跨了 9 天。
_TREND_PERIODS: dict[str, int] = {
    "change_1w": 5,    # 1 周 ≈ 5 个交易日
    "change_1m": 22,   # 1 月 ≈ 22 个交易日
    "change_3m": 66,   # 3 月 ≈ 66 个交易日
    "change_6m": 132,  # 6 月 ≈ 132 个交易日
    "change_1y": 252,  # 1 年 ≈ 252 个交易日
}


def calculate_trend_stats(nav_history: pd.DataFrame) -> TrendStats:
    """
    从净值历史计算多周期涨跌幅。

    逻辑：取最新净值 vs N 交易日前的净值，算百分比差。
    数据不足某个周期就填 None — 宁可没有数据，也不给用户一个误导性的数字。

    Args:
        nav_history: DataFrame，必须包含 "nav" 列，按日期升序排列

    Returns:
        TrendStats 包含各周期涨跌幅百分比
    """
    if nav_history.empty:
        return TrendStats()

    nav = nav_history["nav"].astype(float)
    latest_nav = nav.iloc[-1]

    # 避免除以零（净值为 0 的基金理论上不存在，但防御性编程）
    if latest_nav == 0:
        return TrendStats()

    changes: dict[str, float | None] = {}
    for field_name, trading_days in _TREND_PERIODS.items():
        if len(nav) > trading_days:
            # iloc[-trading_days - 1] 取 N 个交易日前的净值
            # 例如 trading_days=5，总共 100 条数据，取 iloc[-6] = 第 94 条
            old_nav = nav.iloc[-(trading_days + 1)]
            if old_nav != 0:
                changes[field_name] = round(
                    (latest_nav - old_nav) / old_nav * 100, 2,
                )
            else:
                changes[field_name] = None
        else:
            changes[field_name] = None

    return TrendStats(**changes)


def calculate_ma(nav_series: pd.Series, period: int) -> pd.Series:
    """
    计算简单移动平均线 (SMA)。

    Args:
        nav_series: 净值/价格序列，按时间升序排列
        period: 均线周期（如 20、60）

    Returns:
        移动平均线序列（前 period-1 个值为 NaN）
    """
    return nav_series.rolling(window=period, min_periods=period).mean()


def screen_fund(
    nav_history: pd.DataFrame,
    ma_short_period: int = 20,
    ma_long_period: int = 60,
) -> ScreenResult | None:
    """
    对单只基金进行 MA 趋势筛选。

    判断逻辑：最新一天的 MA_short > MA_long 即为通过。

    Args:
        nav_history: DataFrame，必须包含 "date" 和 "nav" 列，按日期升序
        ma_short_period: 短期均线周期，默认 20
        ma_long_period: 长期均线周期，默认 60

    Returns:
        ScreenResult（包含 MA 值和是否通过），
        如果数据不足则返回 None

    新手容易踩的坑：
    1. 数据不足 ma_long 天时，MA_long 的最后一个值是 NaN，
       直接比较会报错。这里前置检查数据长度。
    2. nav_history 必须按日期升序，否则 MA 计算结果是错的。
    """
    if nav_history.empty:
        return None

    if len(nav_history) < ma_long_period:
        logger.debug(
            "数据不足: 需要 %d 天，实际只有 %d 天",
            ma_long_period,
            len(nav_history),
        )
        return None

    nav = nav_history["nav"].astype(float)

    ma_short = calculate_ma(nav, ma_short_period)
    ma_long = calculate_ma(nav, ma_long_period)

    # 取最新一天的 MA 值
    latest_ma_short = ma_short.iloc[-1]
    latest_ma_long = ma_long.iloc[-1]

    # 检查 NaN（理论上数据长度够就不会是 NaN，但防御性编程）
    if pd.isna(latest_ma_short) or pd.isna(latest_ma_long):
        return None

    # 避免除以零
    if latest_ma_long == 0:
        return None

    ma_diff_pct = (latest_ma_short - latest_ma_long) / latest_ma_long * 100
    passed = latest_ma_short > latest_ma_long

    return ScreenResult(
        ma_short=round(latest_ma_short, 4),
        ma_long=round(latest_ma_long, 4),
        ma_diff_pct=round(ma_diff_pct, 2),
        passed=passed,
    )
