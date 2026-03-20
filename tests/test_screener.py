"""screener 模块单元测试。"""

from datetime import datetime, timedelta

import pandas as pd
import pytest

from fund_screener.screener import calculate_ma, calculate_trend_stats, screen_fund


class TestCalculateMA:
    """测试移动平均线计算。"""

    def test_basic_ma(self) -> None:
        """基本 MA 计算：5 个数据点，period=3。"""
        series = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])
        result = calculate_ma(series, period=3)

        assert pd.isna(result.iloc[0])
        assert pd.isna(result.iloc[1])
        assert result.iloc[2] == pytest.approx(20.0)  # (10+20+30)/3
        assert result.iloc[3] == pytest.approx(30.0)  # (20+30+40)/3
        assert result.iloc[4] == pytest.approx(40.0)  # (30+40+50)/3

    def test_ma_with_insufficient_data(self) -> None:
        """数据不足时返回全 NaN。"""
        series = pd.Series([10.0, 20.0])
        result = calculate_ma(series, period=5)
        assert result.isna().all()


class TestCalculateTrendStats:
    """测试多周期涨跌幅计算。"""

    def _make_nav_df(self, values: list[float]) -> pd.DataFrame:
        """构造测试用的 nav DataFrame。"""
        dates = [
            datetime.now() - timedelta(days=len(values) - i - 1)
            for i in range(len(values))
        ]
        return pd.DataFrame({"date": dates, "nav": values})

    def test_sufficient_data_calculates_1w(self) -> None:
        """数据足够时应该计算出 1 周涨跌幅。"""
        # 7 条数据 > 5 交易日阈值，可以算 1 周
        # 从 100 涨到 110，iloc[-6] = 100, iloc[-1] = 110
        values = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 110.0]
        nav_df = self._make_nav_df(values)

        result = calculate_trend_stats(nav_df)

        assert result.change_1w is not None
        # (110 - 101) / 101 * 100 = 8.91%
        # iloc[-6] = values[1] = 101.0
        assert result.change_1w == pytest.approx(8.91, abs=0.01)
        # 数据不足 1 月（22 交易日），应该是 None
        assert result.change_1m is None

    def test_empty_dataframe(self) -> None:
        """空 DataFrame 返回全 None 的 TrendStats。"""
        nav_df = pd.DataFrame(columns=["date", "nav"])
        result = calculate_trend_stats(nav_df)

        assert result.change_1w is None
        assert result.change_1m is None
        assert result.change_1y is None

    def test_large_dataset_all_periods(self) -> None:
        """300 条数据应该能算出所有周期。"""
        # 从 100 线性涨到 200
        values = [100.0 + i * (100.0 / 299) for i in range(300)]
        nav_df = self._make_nav_df(values)

        result = calculate_trend_stats(nav_df)

        assert result.change_1w is not None
        assert result.change_1m is not None
        assert result.change_3m is not None
        assert result.change_6m is not None
        assert result.change_1y is not None
        # 所有周期应该都是正数（线性上涨）
        assert result.change_1w > 0
        assert result.change_1y > result.change_1w  # 长期涨幅应大于短期


class TestScreenFund:
    """测试基金筛选逻辑。"""

    def _make_nav_df(self, values: list[float]) -> pd.DataFrame:
        """构造测试用的 nav DataFrame。"""
        dates = [
            datetime.now() - timedelta(days=len(values) - i - 1)
            for i in range(len(values))
        ]
        return pd.DataFrame({"date": dates, "nav": values})

    def test_uptrend_passes(self) -> None:
        """上涨趋势（MA5 > MA10）应该通过。"""
        # 构造一个明显上涨的序列
        values = list(range(1, 21))  # 1, 2, 3, ..., 20
        nav_df = self._make_nav_df([float(v) for v in values])

        result = screen_fund(nav_df, ma_short_period=5, ma_long_period=10)

        assert result is not None
        assert result.passed is True
        assert result.ma_diff_pct > 0

    def test_downtrend_fails(self) -> None:
        """下跌趋势（MA5 < MA10）应该不通过。"""
        # 构造一个明显下跌的序列
        values = list(range(20, 0, -1))  # 20, 19, 18, ..., 1
        nav_df = self._make_nav_df([float(v) for v in values])

        result = screen_fund(nav_df, ma_short_period=5, ma_long_period=10)

        assert result is not None
        assert result.passed is False
        assert result.ma_diff_pct < 0

    def test_insufficient_data_returns_none(self) -> None:
        """数据不足应该返回 None。"""
        nav_df = self._make_nav_df([1.0, 2.0, 3.0])

        result = screen_fund(nav_df, ma_short_period=5, ma_long_period=10)
        assert result is None

    def test_empty_dataframe_returns_none(self) -> None:
        """空 DataFrame 返回 None。"""
        nav_df = pd.DataFrame(columns=["date", "nav"])
        result = screen_fund(nav_df)
        assert result is None
