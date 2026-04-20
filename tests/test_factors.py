"""
因子层单元测试。

测试策略：
1. 每个因子至少 2 个测试用例（正常 + 边界）
2. 所有因子必须验证 shape 不变性：output.values.shape == nav_panel.shape
3. 合成测试数据（3 基金 × 30 天），避免依赖真实数据库
4. 边界场景：NaN 处理、数据不足、零波动、std=0
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from fund_screener.factors import (
    CompositeFactor,
    MACrossFactor,
    MaxDrawdownFactor,
    MomentumFactor,
    SharpeFactor,
)
from fund_screener.factors.base import BaseFactor, FactorOutput


# ---------------------------------------------------------------------------
# 测试数据工厂
# ---------------------------------------------------------------------------


def make_nav_panel(
    n_days: int = 30,
    n_funds: int = 3,
    uptrend: bool = True,
    with_nan: bool = False,
) -> pd.DataFrame:
    """
    构造合成净值面板用于测试。

    Args:
        n_days: 天数
        n_funds: 基金数量
        uptrend: True=上涨趋势，False=下跌趋势
        with_nan: 是否在部分位置插入 NaN

    Returns:
        DataFrame: index=date(DatetimeIndex), columns=fund_code, values=净值
    """
    dates = pd.date_range("2024-01-01", periods=n_days, freq="D")
    funds = [f"FUND_{chr(65 + i)}" for i in range(n_funds)]

    data: dict[str, list[float]] = {}
    for i, fund in enumerate(funds):
        if uptrend:
            # 基金 A: 1.0 → 1.3 线性上涨
            # 基金 B: 1.0 → 1.2 线性上涨（斜率小一点）
            # 基金 C: 1.0 → 1.1 线性上涨（斜率更小）
            base = 1.0 + i * 0.1
            step = (0.3 - i * 0.05) / max(n_days - 1, 1)
            values = [base + j * step for j in range(n_days)]
        else:
            # 下跌趋势
            base = 1.3 - i * 0.1
            step = -(0.3 - i * 0.05) / max(n_days - 1, 1)
            values = [base + j * step for j in range(n_days)]

        data[fund] = values

    df = pd.DataFrame(data, index=dates)

    if with_nan:
        # 基金 C 前 5 天 NaN（模拟未上市）
        df.iloc[:5, 2] = np.nan
        # 基金 A 中间某天 NaN（模拟停牌）
        df.iloc[15, 0] = np.nan

    return df


# ---------------------------------------------------------------------------
# FactorOutput 基础测试
# ---------------------------------------------------------------------------


class TestFactorOutput:
    """测试 FactorOutput 数据类。"""

    def test_frozen_dataclass(self) -> None:
        """FactorOutput 是 frozen 的，不可修改。"""
        df = pd.DataFrame({"A": [1.0, 2.0]})
        output = FactorOutput(values=df, kind="signal", name="test")

        with pytest.raises(AttributeError):
            output.name = "changed"

    def test_fields_accessible(self) -> None:
        """所有字段可正常访问。"""
        df = pd.DataFrame({"A": [1.0]})
        output = FactorOutput(
            values=df, kind="score", name="momentum", description="test desc"
        )

        assert output.kind == "score"
        assert output.name == "momentum"
        assert output.description == "test desc"
        pd.testing.assert_frame_equal(output.values, df)


# ---------------------------------------------------------------------------
# MACrossFactor 测试
# ---------------------------------------------------------------------------


class TestMACrossFactor:
    """测试 MA 交叉信号因子。"""

    def test_uptrend_produces_true_after_period(self) -> None:
        """上涨趋势中，MA5 > MA10 后应输出 True。"""
        # 构造 30 天明显上涨序列
        nav = make_nav_panel(n_days=30, uptrend=True)
        factor = MACrossFactor(short=5, long=10)
        output = factor.compute(nav)

        assert output.kind == "signal"
        assert output.values.shape == nav.shape
        assert list(output.values.columns) == list(nav.columns)
        assert output.values.index.equals(nav.index)

        # 前 10 天（long 周期）必须全 False
        assert not output.values.iloc[:10].any().any()

        # 上涨序列中，10 天后应该有 True（多头排列成立）
        # 注意：不是所有位置都 True，但至少有部分 True
        assert output.values.iloc[10:].any().any()

    def test_downtrend_all_false_after_period(self) -> None:
        """下跌趋势中，MA5 < MA10，应全 False。"""
        nav = make_nav_panel(n_days=30, uptrend=False)
        factor = MACrossFactor(short=5, long=10)
        output = factor.compute(nav)

        # 前 10 天 False
        assert not output.values.iloc[:10].any().any()

        # 下跌序列中，10 天后也应该全 False（空头排列）
        assert not output.values.iloc[10:].any().any()

    def test_nan_positions_are_false(self) -> None:
        """NaN 位置必须输出 False（不可交易）。"""
        nav = make_nav_panel(n_days=30, with_nan=True)
        factor = MACrossFactor(short=5, long=10)
        output = factor.compute(nav)

        # 基金 C 前 5 天是 NaN，对应信号必须是 False
        # 注意：pandas 布尔矩阵的元素是 np.bool_，不能用 `is False`，要用 `== False`
        for i in range(5):
            assert output.values.iloc[i, 2] == False  # noqa: E712

        # 基金 A 第 15 天是 NaN，对应信号必须是 False
        assert output.values.iloc[15, 0] == False  # noqa: E712

    def test_first_long_days_forced_false(self) -> None:
        """显式验证前 `long` 天强制 False。"""
        nav = make_nav_panel(n_days=30, uptrend=True)
        factor = MACrossFactor(short=5, long=10)
        output = factor.compute(nav)

        # 前 10 行必须全 False
        assert not output.values.iloc[:10].any().any()

        # 第 10 行及以后至少有一些 True（上涨序列）
        assert output.values.iloc[10:].any().any()

    def test_shape_invariant(self) -> None:
        """输出 shape 必须与输入一致。"""
        nav = make_nav_panel(n_days=30, n_funds=5)
        factor = MACrossFactor(short=5, long=10)
        output = factor.compute(nav)

        assert output.values.shape == nav.shape
        assert list(output.values.columns) == list(nav.columns)
        assert output.values.index.equals(nav.index)


# ---------------------------------------------------------------------------
# MomentumFactor 测试
# ---------------------------------------------------------------------------


class TestMomentumFactor:
    """测试动量因子。"""

    def test_positive_momentum_when_price_above_ma(self) -> None:
        """价格在 MA 之上时，动量为正。"""
        # 构造持续上涨序列：价格始终高于 MA20
        dates = pd.date_range("2024-01-01", periods=30, freq="D")
        values = [1.0 + i * 0.01 for i in range(30)]  # 线性上涨
        nav = pd.DataFrame({"FUND_A": values}, index=dates)

        factor = MomentumFactor(ma_period=20)
        output = factor.compute(nav)

        assert output.kind == "score"
        assert output.values.shape == nav.shape

        # 20 天后（MA 成熟后），动量应该为正（价格在 MA 之上）
        # 线性上涨序列中，最新价格 > MA，所以动量 > 0
        late_momentum = output.values.iloc[25:, 0].dropna()
        assert (late_momentum > 0).all()

    def test_negative_momentum_when_price_below_ma(self) -> None:
        """价格在 MA 之下时，动量为负。"""
        dates = pd.date_range("2024-01-01", periods=30, freq="D")
        values = [1.3 - i * 0.01 for i in range(30)]  # 线性下跌
        nav = pd.DataFrame({"FUND_A": values}, index=dates)

        factor = MomentumFactor(ma_period=20)
        output = factor.compute(nav)

        # 20 天后，动量应该为负（价格在 MA 之下）
        late_momentum = output.values.iloc[25:, 0].dropna()
        assert (late_momentum < 0).all()

    def test_shape_invariant(self) -> None:
        """输出 shape 必须与输入一致。"""
        nav = make_nav_panel(n_days=30, n_funds=3)
        factor = MomentumFactor(ma_period=5)
        output = factor.compute(nav)

        assert output.values.shape == nav.shape
        assert list(output.values.columns) == list(nav.columns)
        assert output.values.index.equals(nav.index)

    def test_insufficient_data_returns_nan(self) -> None:
        """数据不足 ma_period 时返回 NaN。"""
        dates = pd.date_range("2024-01-01", periods=5, freq="D")
        nav = pd.DataFrame({"FUND_A": [1.0, 1.1, 1.2, 1.3, 1.4]}, index=dates)

        factor = MomentumFactor(ma_period=10)
        output = factor.compute(nav)

        # 所有值都应该是 NaN（数据不足 10 天）
        assert output.values.isna().all().all()


# ---------------------------------------------------------------------------
# SharpeFactor 测试
# ---------------------------------------------------------------------------


class TestSharpeFactor:
    """测试夏普比率因子。"""

    def test_sufficient_data_returns_finite(self) -> None:
        """数据充足时返回有限浮点数。"""
        # 构造 30 天有波动的序列
        dates = pd.date_range("2024-01-01", periods=30, freq="D")
        np.random.seed(42)
        returns = np.random.normal(0.001, 0.02, 30)  # 日均收益 0.1%，波动 2%
        values = [1.0]
        for r in returns:
            values.append(values[-1] * (1 + r))
        nav = pd.DataFrame({"FUND_A": values[1:]}, index=dates)

        factor = SharpeFactor(lookback=20)  # 用小 lookback 加速测试
        output = factor.compute(nav)

        assert output.kind == "score"
        assert output.values.shape == nav.shape

        # 20 天后应该有有效值（非 NaN、非 inf）
        valid_values = output.values.iloc[20:, 0].dropna()
        assert len(valid_values) > 0
        assert np.isfinite(valid_values).all()

    def test_zero_volatility_returns_nan(self) -> None:
        """零波动序列返回 NaN（避免除以零产生 inf）。"""
        # 构造完全无波动的序列（如停牌或货基）
        dates = pd.date_range("2024-01-01", periods=30, freq="D")
        nav = pd.DataFrame({"FUND_A": [1.0] * 30}, index=dates)

        factor = SharpeFactor(lookback=20)
        output = factor.compute(nav)

        # 所有值都应该是 NaN（零波动，std=0）
        # 注意：pct_change() 第一个值是 NaN，但这里所有值都是 1.0，
        # pct_change 全 0，std=0 → sharpe = NaN
        assert output.values.isna().all().all()

    def test_shape_invariant(self) -> None:
        """输出 shape 必须与输入一致。"""
        nav = make_nav_panel(n_days=30, n_funds=3)
        factor = SharpeFactor(lookback=10)
        output = factor.compute(nav)

        assert output.values.shape == nav.shape
        assert list(output.values.columns) == list(nav.columns)
        assert output.values.index.equals(nav.index)

    def test_uses_math_sqrt(self) -> None:
        """验证使用 math.sqrt(252) 而非 np.sqrt(252) —— 与 risk_metrics.py 保持一致。"""
        # 这个测试更多是文档性质的：确认实现中用了 math.sqrt
        # 实际验证：如果代码用了 math.sqrt(252)，结果应该和手动计算一致
        dates = pd.date_range("2024-01-01", periods=30, freq="D")
        np.random.seed(42)
        returns = np.random.normal(0.001, 0.02, 30)
        values = [1.0]
        for r in returns:
            values.append(values[-1] * (1 + r))
        nav = pd.DataFrame({"FUND_A": values[1:]}, index=dates)

        factor = SharpeFactor(lookback=20, rf_annual=0.02)
        output = factor.compute(nav)

        # 手动计算验证
        # 注意：factor.compute() 内部用 nav.pct_change()，不 dropna，
        # 所以 output 有 30 行（和 nav 一样）。
        pct = nav.pct_change()  # 不 dropna，保持 30 行
        excess = pct - 0.02 / 252
        rolling_mean = excess.rolling(window=20, min_periods=20).mean()
        rolling_std = excess.rolling(window=20, min_periods=20).std(ddof=1)
        expected = (rolling_mean / rolling_std.replace(0, np.nan)) * math.sqrt(252)

        # output.values 是 DataFrame（1 列），expected 也是 DataFrame（1 列）
        # 因为 nav 是 DataFrame，pct_change 返回 DataFrame
        # 提取为 Series 后比较
        output_series = output.values.iloc[:, 0]
        expected_series = expected.iloc[:, 0]
        # 只比较有值的位置（前 20 天是 NaN）
        valid_mask = output_series.notna()
        pd.testing.assert_series_equal(
            output_series[valid_mask],
            expected_series[valid_mask],
            check_names=False,
        )


# ---------------------------------------------------------------------------
# MaxDrawdownFactor 测试
# ---------------------------------------------------------------------------


class TestMaxDrawdownFactor:
    """测试最大回撤因子。"""

    def test_returns_negative_values(self) -> None:
        """最大回撤因子返回负值。"""
        # 构造有回撤的序列：先涨后跌
        dates = pd.date_range("2024-01-01", periods=30, freq="D")
        values = []
        for i in range(30):
            if i < 15:
                values.append(1.0 + i * 0.02)  # 涨到 1.3
            else:
                values.append(1.3 - (i - 15) * 0.015)  # 跌到 1.075
        nav = pd.DataFrame({"FUND_A": values}, index=dates)

        factor = MaxDrawdownFactor(lookback=30)
        output = factor.compute(nav)

        assert output.kind == "score"
        assert output.values.shape == nav.shape

        # 第 2 天后的值应该都是负数或 0
        valid_values = output.values.iloc[2:, 0].dropna()
        assert (valid_values <= 0).all()

    def test_first_two_days_nan(self) -> None:
        """前 2 天返回 NaN（数据不足）。"""
        dates = pd.date_range("2024-01-01", periods=10, freq="D")
        values = [1.0 + i * 0.01 for i in range(10)]
        nav = pd.DataFrame({"FUND_A": values}, index=dates)

        factor = MaxDrawdownFactor(lookback=10)
        output = factor.compute(nav)

        # 第 0、1 天必须是 NaN
        assert pd.isna(output.values.iloc[0, 0])
        assert pd.isna(output.values.iloc[1, 0])

    def test_larger_drawdown_more_negative(self) -> None:
        """回撤越大，值越负。"""
        dates = pd.date_range("2024-01-01", periods=30, freq="D")

        # 基金 A: 小回撤（1.0 → 1.2 → 1.15，回撤 -4.17%）
        values_a = []
        for i in range(30):
            if i < 15:
                values_a.append(1.0 + i * 0.0133)
            else:
                values_a.append(values_a[14] - (i - 14) * 0.003)

        # 基金 B: 大回撤（1.0 → 1.2 → 0.9，回撤 -25%）
        values_b = []
        for i in range(30):
            if i < 15:
                values_b.append(1.0 + i * 0.0133)
            else:
                values_b.append(values_b[14] - (i - 14) * 0.02)

        nav = pd.DataFrame(
            {"FUND_A": values_a, "FUND_B": values_b}, index=dates
        )

        factor = MaxDrawdownFactor(lookback=30)
        output = factor.compute(nav)

        # 取最后一天比较
        dd_a = output.values.iloc[-1, 0]
        dd_b = output.values.iloc[-1, 1]

        # 基金 B 回撤更大，应该更负
        assert dd_b < dd_a
        assert dd_b < -0.1  # 至少 -10%

    def test_shape_invariant(self) -> None:
        """输出 shape 必须与输入一致。"""
        nav = make_nav_panel(n_days=30, n_funds=3)
        factor = MaxDrawdownFactor(lookback=10)
        output = factor.compute(nav)

        assert output.values.shape == nav.shape
        assert list(output.values.columns) == list(nav.columns)
        assert output.values.index.equals(nav.index)


# ---------------------------------------------------------------------------
# CompositeFactor 测试
# ---------------------------------------------------------------------------


class TestCompositeFactor:
    """测试复合因子。"""

    def test_combines_two_score_factors(self) -> None:
        """组合两个 score 因子，输出加权综合分。"""
        nav = make_nav_panel(n_days=30, n_funds=3, uptrend=True)

        momentum = MomentumFactor(ma_period=5)
        sharpe = SharpeFactor(lookback=10)

        composite = CompositeFactor(
            factors=[momentum, sharpe],
            weights=[0.6, 0.4],
            name="test_composite",
        )
        output = composite.compute(nav)

        assert output.kind == "score"
        assert output.name == "test_composite"
        assert output.values.shape == nav.shape

        # 输出应该是有限值（Z-Score 标准化后不应该有 inf）
        # np.isfinite 对 DataFrame 返回 DataFrame，需要 .all().all()
        assert np.isfinite(output.values.fillna(0)).all().all()

    def test_zscore_handles_std_zero(self) -> None:
        """
        Z-Score 处理 std=0 的情况（所有基金同一天分数相同）。

        当某天所有基金的分数都一样时，std=0，Z-Score 应该全 0（不是 NaN/inf）。
        """
        # 构造 3 只基金完全同步的序列（每天价格变化一样 → 动量分数一样）
        dates = pd.date_range("2024-01-01", periods=30, freq="D")
        values = [1.0 + i * 0.01 for i in range(30)]
        nav = pd.DataFrame(
            {"FUND_A": values, "FUND_B": values, "FUND_C": values},
            index=dates,
        )

        momentum = MomentumFactor(ma_period=5)
        composite = CompositeFactor(factors=[momentum], weights=[1.0])
        output = composite.compute(nav)

        # 所有 Z-Score 应该为 0（std=0 → fillna(0)）
        # 注意：前 5 天动量可能是 NaN，Z-Score 也是 NaN
        # 5 天后应该全 0
        late_values = output.values.iloc[5:]
        assert (late_values.fillna(0) == 0).all().all()

    def test_add_syntax_sugar(self) -> None:
        """测试 __add__ 语法糖：factor_a + factor_b → CompositeFactor。"""
        nav = make_nav_panel(n_days=30, n_funds=3)

        momentum = MomentumFactor(ma_period=5)
        sharpe = SharpeFactor(lookback=10)

        # 语法糖
        composite = momentum + sharpe
        assert isinstance(composite, CompositeFactor)

        output = composite.compute(nav)
        assert output.kind == "score"
        assert output.values.shape == nav.shape

    def test_rejects_non_score_factors(self) -> None:
        """CompositeFactor 拒绝 kind != 'score' 的因子。"""
        nav = make_nav_panel(n_days=30, n_funds=3)

        ma = MACrossFactor(short=5, long=10)  # kind="signal"
        momentum = MomentumFactor(ma_period=5)  # kind="score"

        composite = CompositeFactor(factors=[ma, momentum])

        # compute 时应该抛出 ValueError
        with pytest.raises(ValueError, match="只能组合 kind='score' 的因子"):
            composite.compute(nav)

    def test_weights_length_mismatch(self) -> None:
        """权重数量和因子数量不一致时抛出 ValueError。"""
        momentum = MomentumFactor(ma_period=5)
        sharpe = SharpeFactor(lookback=10)

        with pytest.raises(ValueError, match="因子数量.*和权重数量.*不一致"):
            CompositeFactor(
                factors=[momentum, sharpe],
                weights=[0.5],  # 只有一个权重，但有两个因子
            )

    def test_shape_invariant(self) -> None:
        """输出 shape 必须与输入一致。"""
        nav = make_nav_panel(n_days=30, n_funds=3)

        composite = CompositeFactor(
            factors=[
                MomentumFactor(ma_period=5),
                SharpeFactor(lookback=10),
            ],
            weights=[0.5, 0.5],
        )
        output = composite.compute(nav)

        assert output.values.shape == nav.shape
        assert list(output.values.columns) == list(nav.columns)
        assert output.values.index.equals(nav.index)


# ---------------------------------------------------------------------------
# 全局 shape 不变性测试
# ---------------------------------------------------------------------------


class TestShapeInvariant:
    """
    全局 shape 不变性验证 —— 所有因子的输出 shape 必须等于输入 shape。

    这是 ARCHITECTURE.md 原则二的核心约束：信号是唯一契约，
    如果 shape 不一致，回测引擎无法正确对齐日期和基金代码。
    """

    @pytest.mark.parametrize(
        "factor",
        [
            MACrossFactor(short=5, long=10),
            MomentumFactor(ma_period=5),
            SharpeFactor(lookback=10),
            MaxDrawdownFactor(lookback=10),
            CompositeFactor(
                factors=[
                    MomentumFactor(ma_period=5),
                    SharpeFactor(lookback=10),
                ],
                weights=[0.5, 0.5],
            ),
        ],
    )
    def test_all_factors_shape_matches_input(self, factor: BaseFactor) -> None:
        """每个因子的输出 shape 必须与 nav_panel 一致。"""
        nav = make_nav_panel(n_days=30, n_funds=3)
        output = factor.compute(nav)

        assert output.values.shape == nav.shape, (
            f"{factor.name}: output shape {output.values.shape} "
            f"!= input shape {nav.shape}"
        )
        assert list(output.values.columns) == list(nav.columns), (
            f"{factor.name}: columns mismatch"
        )
        assert output.values.index.equals(nav.index), (
            f"{factor.name}: index mismatch"
        )
