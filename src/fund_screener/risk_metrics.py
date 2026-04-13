"""
风险指标计算模块 — 三个纯函数。

设计哲学：
1. 纯函数，无副作用：输入 pd.Series，输出 float
2. 边界防御：数据不足 / 零波动 / 空序列 → 返回 float('nan')
3. 不持有状态，不访问数据库，不做 I/O

三个核心指标（详见 specs/quant_scoring_spec.md）：
- momentum_score: 趋势爆发力 = (latest_nav - MA20) / MA20
- max_drawdown: 最大回撤 = min(drawdown_series)，返回负数
- sharpe_ratio: 夏普比率 = (excess_mean / excess_std) * sqrt(252)
"""

from __future__ import annotations

import math

import pandas as pd

from fund_screener.screener import calculate_ma


def momentum_score(nav_series: pd.Series, ma_period: int = 20) -> float:
    """
    趋势爆发力 — 当前价格偏离短期均线的幅度。

    公式: (latest_nav - MA_period) / MA_period
    正值 = 价格在均线之上（上涨势头），值越大势越猛。

    Args:
        nav_series: 净值/价格序列，按时间升序排列，dtype 应可转 float
        ma_period: 均线周期，默认 20（MA20）

    Returns:
        趋势爆发力分数。数据不足时返回 NaN。

    复用: screener.py:77 的 calculate_ma() 计算 SMA，
    避免重复实现移动平均逻辑。
    """
    if len(nav_series) < ma_period:
        return float("nan")

    nav = nav_series.astype(float)
    latest_nav = nav.iloc[-1]

    # 复用已有的 calculate_ma 函数
    ma = calculate_ma(nav, ma_period)
    latest_ma = ma.iloc[-1]

    # MA 值为 NaN（理论上数据够就不会，但防御性编程）
    if pd.isna(latest_ma) or latest_ma == 0:
        return float("nan")

    return float((latest_nav - latest_ma) / latest_ma)


def max_drawdown(nav_series: pd.Series) -> float:
    """
    最大回撤 — 区间内从峰值到谷底的最大跌幅。

    公式:
        cummax = nav_series.cummax()
        drawdown_series = (nav_series - cummax) / cummax
        max_drawdown = min(drawdown_series)

    返回负数（如 -0.25 表示 -25% 回撤），完美上涨序列返回 0.0。

    Args:
        nav_series: 净值/价格序列，按时间升序排列

    Returns:
        最大回撤（负数或零）。数据不足（< 2 条）时返回 NaN。

    新手容易踩的坑：
    1. cummax 必须在时间升序序列上计算，否则"历史最高"是错的
    2. 回撤是负数，打分时需要反转方向（在 scoring.py 里处理，不在这里）
    3. 如果整个区间净值一直涨，drawdown_series 全是 0，min=0，这是正确行为
    """
    if len(nav_series) < 2:
        return float("nan")

    nav = nav_series.astype(float)

    # 第一个值如果是 0 或负数，整个序列不可信
    if nav.iloc[0] <= 0:
        return float("nan")

    cummax = nav.cummax()

    # cummax 中任何值为 0 都会导致除零
    # 实际中净值不可能为 0，但做防御
    if (cummax == 0).any():
        return float("nan")

    drawdown_series = (nav - cummax) / cummax
    return float(drawdown_series.min())


def sharpe_ratio(
    nav_series: pd.Series,
    rf_annual: float = 0.02,
    periods_per_year: int = 252,
) -> float:
    """
    夏普比率 — 每承担 1 单位风险获得的超额收益。

    公式:
        daily_returns = nav_series.pct_change().dropna()
        rf_daily = rf_annual / periods_per_year
        excess_mean = daily_returns.mean() - rf_daily
        excess_std = daily_returns.std(ddof=1)
        sharpe = (excess_mean / excess_std) * sqrt(periods_per_year)

    Args:
        nav_series: 净值/价格序列，按时间升序排列
        rf_annual: 年化无风险利率，默认 0.02（2%，近似中国国债收益率）
        periods_per_year: 每年交易日数，默认 252

    Returns:
        年化夏普比率。数据不足（< 2 条）或零波动时返回 NaN。

    新手容易踩的坑：
    1. pct_change() 第一个值是 NaN，必须 dropna()
    2. std(ddof=1) 用样本标准差（N-1），不是总体标准差（N）
    3. 零波动（如货基）会导致 std=0 除零 — 这里返回 NaN 而非 inf
    4. 年化公式：乘 sqrt(periods_per_year) 而非 periods_per_year
       （收益率乘 N 年化，波动率乘 sqrt(N) 年化，比值里 N 消掉变成 sqrt(N)）
    """
    if len(nav_series) < 2:
        return float("nan")

    nav = nav_series.astype(float)
    daily_returns = nav.pct_change().dropna()

    if len(daily_returns) < 1:
        return float("nan")

    rf_daily = rf_annual / periods_per_year
    excess_mean = daily_returns.mean() - rf_daily
    excess_std = daily_returns.std(ddof=1)

    # 零波动 → 无法计算夏普（货基、停牌等场景）
    if excess_std == 0 or math.isnan(excess_std):
        return float("nan")

    return float((excess_mean / excess_std) * math.sqrt(periods_per_year))
