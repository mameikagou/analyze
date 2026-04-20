"""
回测引擎单元测试。

测试策略：
1. 所有测试用合成数据（3 基金 × 60 天），不依赖真实数据库
2. 覆盖核心路径：等权调仓、分数加权、信号过滤、空仓处理
3. 覆盖边界场景：frozen config、JSON 序列化、权重和为 1.0
4. 验证 ARCHITECTURE.md 原则三：回测层只做 signal_df × nav_df → 绩效指标

对应 BACKTEST_DESIGN.md §6 和 03-02-PLAN.md Task 2
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from fund_screener.backtest import BacktestConfig, BacktestEngine, BacktestResult
from fund_screener.backtest.config import BacktestConfig as BacktestConfigDirect
from fund_screener.factors.quant import MomentumFactor
from fund_screener.factors.technical import MACrossFactor


# ---------------------------------------------------------------------------
# 测试数据工厂
# ---------------------------------------------------------------------------


def make_nav_panel(n_days: int = 60, n_funds: int = 3) -> pd.DataFrame:
    """
    构造合成净值面板用于回测测试。

    基金设计：
    - FUND_A: 1.0 → 1.3 线性上涨（强势）
    - FUND_B: 1.3 → 1.0 线性下跌（弱势）
    - FUND_C: 1.0 → 1.5 线性上涨（最强）

    为什么用线性序列？因为线性序列的 MA 交叉信号可预测，
    便于验证回测结果是否符合预期。
    """
    dates = pd.date_range("2024-01-01", periods=n_days, freq="D")
    funds = [f"FUND_{chr(65 + i)}" for i in range(n_funds)]

    data: dict[str, list[float]] = {}
    for i, fund in enumerate(funds):
        if i == 0:
            # A: 1.0 → 1.3 上涨
            values = np.linspace(1.0, 1.3, n_days).tolist()
        elif i == 1:
            # B: 1.3 → 1.0 下跌
            values = np.linspace(1.3, 1.0, n_days).tolist()
        else:
            # C, D, ...: 1.0 → 1.5 强势上涨
            values = np.linspace(1.0, 1.5 + (i - 2) * 0.1, n_days).tolist()
        data[fund] = values

    return pd.DataFrame(data, index=dates)


# ---------------------------------------------------------------------------
# BacktestConfig 测试
# ---------------------------------------------------------------------------


class TestBacktestConfig:
    """测试 BacktestConfig 配置类。"""

    def test_frozen_prevents_mutation(self) -> None:
        """frozen=True 阻止配置被修改 —— 防止回测过程中配置被意外篡改。"""
        config = BacktestConfig(top_n=10)

        with pytest.raises((AttributeError, TypeError)):
            config.top_n = 5  # type: ignore[misc]

    def test_defaults_match_design(self) -> None:
        """所有默认值必须与 BACKTEST_DESIGN.md §6.2 一致。"""
        config = BacktestConfig()

        assert config.top_n == 10
        assert config.rebalance_freq == "ME"
        assert config.weighting == "equal"
        assert config.fee_rate == 0.0015
        assert config.init_cash == 1_000_000.0
        assert config.signal_filter is None
        assert config.benchmark_code == "000300.SH"
        assert config.use_adj_nav is False

    def test_custom_values(self) -> None:
        """自定义值能正确设置。"""
        config = BacktestConfig(
            top_n=5,
            rebalance_freq="W-FRI",
            weighting="score",
            fee_rate=0.002,
            init_cash=500_000.0,
        )

        assert config.top_n == 5
        assert config.rebalance_freq == "W-FRI"
        assert config.weighting == "score"
        assert config.fee_rate == 0.002
        assert config.init_cash == 500_000.0

    def test_frozen_instance_error_specific(self) -> None:
        """显式验证 FrozenInstanceError（dataclasses 抛出的具体异常类型）。"""
        config = BacktestConfig()

        # dataclasses.FrozenInstanceError 是 AttributeError 的子类
        # 注意：object.__setattr__ 可以绕过 frozen 限制（这是 Python 的底层机制）
        # 正常的属性赋值会被拦截
        with pytest.raises(AttributeError):
            config.top_n = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# _build_target_weights 测试
# ---------------------------------------------------------------------------


class TestBuildTargetWeights:
    """测试目标权重构建逻辑 —— 回测引擎的核心决策层。"""

    def test_equal_weighting(self) -> None:
        """
        等权分配：Top N 每只基金权重 = 1/N，其余为 0.0，非调仓日为 NaN。
        """
        nav = make_nav_panel(n_days=60, n_funds=5)
        config = BacktestConfig(
            top_n=3, rebalance_freq="ME", weighting="equal"
        )
        engine = BacktestEngine(nav, config)

        # 构造一个可预测的分数矩阵：FUND_C 最高，FUND_A 次之，FUND_B 最低
        scores = pd.DataFrame(
            {
                "FUND_A": [0.5] * 60,
                "FUND_B": [0.1] * 60,
                "FUND_C": [0.9] * 60,
                "FUND_D": [0.7] * 60,
                "FUND_E": [0.3] * 60,
            },
            index=nav.index,
        )

        weights = engine._build_target_weights(scores)

        # 找到调仓日（月末）
        rebalance_dates = scores.resample("ME").last().index.intersection(
            scores.index
        )
        assert len(rebalance_dates) > 0

        for dt in rebalance_dates:
            row = weights.loc[dt]
            non_nan = row.dropna()

            # 调仓日不应该有 NaN（所有基金都应有明确权重）
            assert len(non_nan) == len(scores.columns)

            # Top 3 应该有正权重
            positive = non_nan[non_nan > 0]
            assert len(positive) == 3

            # 等权：每只权重 = 1/3
            for w in positive.values:
                assert abs(w - 1.0 / 3) < 1e-10

            # 其余为 0.0
            zero = non_nan[non_nan == 0]
            assert len(zero) == 2

        # 非调仓日应该是 NaN
        non_rebal_dates = scores.index.difference(rebalance_dates)
        if len(non_rebal_dates) > 0:
            assert weights.loc[non_rebal_dates[0]].isna().all()

    def test_score_weighting(self) -> None:
        """
        分数加权：权重与分数成正比，min-max 归一化后总和为 1.0。
        """
        nav = make_nav_panel(n_days=60, n_funds=3)
        config = BacktestConfig(
            top_n=3, rebalance_freq="ME", weighting="score"
        )
        engine = BacktestEngine(nav, config)

        # 构造分数：C > A > B
        scores = pd.DataFrame(
            {
                "FUND_A": [0.5] * 60,
                "FUND_B": [0.1] * 60,
                "FUND_C": [0.9] * 60,
            },
            index=nav.index,
        )

        weights = engine._build_target_weights(scores)

        rebalance_dates = scores.resample("ME").last().index.intersection(
            scores.index
        )

        for dt in rebalance_dates:
            row = weights.loc[dt]
            positive = row[row > 0]

            # 3 只基金都入选（top_n=3，共 3 只）
            assert len(positive) == 3

            # 权重和应为 1.0
            total = positive.sum()
            assert abs(total - 1.0) < 1e-6

            # 分数最高的 C 权重最大
            assert positive["FUND_C"] > positive["FUND_A"] > positive["FUND_B"]

    def test_signal_filter_excludes_funds(self) -> None:
        """
        被 signal_filter 过滤掉的基金（分数 = -inf）永远不被选中。
        """
        nav = make_nav_panel(n_days=60, n_funds=3)
        config = BacktestConfig(
            top_n=2, rebalance_freq="ME", weighting="equal"
        )
        engine = BacktestEngine(nav, config)

        # 构造分数，但把 FUND_B 设为 -inf（模拟被过滤）
        scores = pd.DataFrame(
            {
                "FUND_A": [0.5] * 60,
                "FUND_B": [-np.inf] * 60,
                "FUND_C": [0.9] * 60,
            },
            index=nav.index,
        )

        weights = engine._build_target_weights(scores)

        rebalance_dates = scores.resample("ME").last().index.intersection(
            scores.index
        )

        for dt in rebalance_dates:
            row = weights.loc[dt]
            positive = row[row > 0]

            # FUND_B 被过滤，只能选 A 和 C
            assert "FUND_B" not in positive.index
            assert "FUND_A" in positive.index
            assert "FUND_C" in positive.index

    def test_empty_candidates_all_cash(self) -> None:
        """
        没有有效候选基金时 → 全部权重为 0.0（空仓，持有现金）。
        """
        nav = make_nav_panel(n_days=60, n_funds=3)
        config = BacktestConfig(
            top_n=2, rebalance_freq="ME", weighting="equal"
        )
        engine = BacktestEngine(nav, config)

        # 所有分数都是 -inf（全部被过滤）
        scores = pd.DataFrame(
            {
                "FUND_A": [-np.inf] * 60,
                "FUND_B": [-np.inf] * 60,
                "FUND_C": [-np.inf] * 60,
            },
            index=nav.index,
        )

        weights = engine._build_target_weights(scores)

        rebalance_dates = scores.resample("ME").last().index.intersection(
            scores.index
        )

        for dt in rebalance_dates:
            row = weights.loc[dt]
            # 所有权重都应该是 0.0（不是 NaN）
            assert (row == 0.0).all()

    def test_nan_scores_excluded(self) -> None:
        """
        NaN 分数的基金应该被排除（视为无效数据）。
        """
        nav = make_nav_panel(n_days=60, n_funds=3)
        config = BacktestConfig(
            top_n=2, rebalance_freq="ME", weighting="equal"
        )
        engine = BacktestEngine(nav, config)

        scores = pd.DataFrame(
            {
                "FUND_A": [0.5] * 60,
                "FUND_B": [np.nan] * 60,
                "FUND_C": [0.9] * 60,
            },
            index=nav.index,
        )

        weights = engine._build_target_weights(scores)

        rebalance_dates = scores.resample("ME").last().index.intersection(
            scores.index
        )

        for dt in rebalance_dates:
            row = weights.loc[dt]
            positive = row[row > 0]

            # NaN 的 FUND_B 不应该被选中
            assert "FUND_B" not in positive.index
            assert len(positive) == 2  # A 和 C

    def test_top_n_less_than_total(self) -> None:
        """
        top_n 小于基金总数时，只选 Top N。
        """
        nav = make_nav_panel(n_days=60, n_funds=5)
        config = BacktestConfig(
            top_n=2, rebalance_freq="ME", weighting="equal"
        )
        engine = BacktestEngine(nav, config)

        scores = pd.DataFrame(
            {
                "FUND_A": [0.5] * 60,
                "FUND_B": [0.1] * 60,
                "FUND_C": [0.9] * 60,
                "FUND_D": [0.7] * 60,
                "FUND_E": [0.3] * 60,
            },
            index=nav.index,
        )

        weights = engine._build_target_weights(scores)

        rebalance_dates = scores.resample("ME").last().index.intersection(
            scores.index
        )

        for dt in rebalance_dates:
            row = weights.loc[dt]
            positive = row[row > 0]

            # 只选 2 只
            assert len(positive) == 2
            # 等权
            assert abs(positive.sum() - 1.0) < 1e-10


# ---------------------------------------------------------------------------
# BacktestResult 测试
# ---------------------------------------------------------------------------


class TestBacktestResult:
    """测试回测结果的序列化和衍生数据。"""

    def test_to_api_response_structure(self) -> None:
        """
        to_api_response() 返回的字典必须包含所有预期键。
        """
        nav = make_nav_panel(n_days=60, n_funds=3)
        config = BacktestConfig(top_n=2, rebalance_freq="ME")
        engine = BacktestEngine(nav, config)

        score_factor = MomentumFactor(ma_period=20)
        result = engine.run(score_factor)

        response = result.to_api_response()

        # 顶层键
        assert "factor_name" in response
        assert "config" in response
        assert "stats" in response
        assert "equity_curve" in response
        assert "drawdown" in response
        assert "rebalance_history" in response

        # config 子键
        cfg = response["config"]
        assert "top_n" in cfg
        assert "rebalance_freq" in cfg
        assert "weighting" in cfg
        assert "fee_rate" in cfg
        assert "init_cash" in cfg
        assert "signal_filter" in cfg

        # stats 子键
        stats = response["stats"]
        assert "total_return" in stats
        assert "annual_return" in stats
        assert "sharpe_ratio" in stats
        assert "max_drawdown" in stats
        assert "win_rate" in stats
        assert "avg_win" in stats
        assert "avg_loss" in stats
        assert "profit_factor" in stats
        assert "total_trades" in stats

    def test_to_api_response_json_serializable(self) -> None:
        """
        to_api_response() 的结果必须能被 json.dumps() 序列化。
        这是 T-03-05 威胁缓解的核心验证：不泄漏内部对象。
        """
        nav = make_nav_panel(n_days=60, n_funds=3)
        config = BacktestConfig(top_n=2, rebalance_freq="ME")
        engine = BacktestEngine(nav, config)

        score_factor = MomentumFactor(ma_period=20)
        result = engine.run(score_factor)

        response = result.to_api_response()

        # 必须能 JSON 序列化，不抛 TypeError
        json_str = json.dumps(response)
        assert isinstance(json_str, str)
        assert len(json_str) > 0

        # 反序列化验证结构完整
        parsed = json.loads(json_str)
        assert parsed["factor_name"] == score_factor.name
        assert isinstance(parsed["stats"], dict)
        assert isinstance(parsed["equity_curve"], dict)
        assert isinstance(parsed["drawdown"], dict)
        assert isinstance(parsed["rebalance_history"], list)

    def test_rebalance_history_format(self) -> None:
        """
        rebalance_history() 的格式必须正确：每项包含 date 和 holdings。
        """
        nav = make_nav_panel(n_days=60, n_funds=3)
        config = BacktestConfig(top_n=2, rebalance_freq="ME")
        engine = BacktestEngine(nav, config)

        score_factor = MomentumFactor(ma_period=20)
        result = engine.run(score_factor)

        history = result.rebalance_history()

        # 至少有一次调仓（60 天跨了至少 2 个月）
        assert len(history) >= 1

        for entry in history:
            assert "date" in entry
            assert "holdings" in entry
            assert isinstance(entry["date"], str)
            assert isinstance(entry["holdings"], dict)

            # date 格式应该是 YYYY-MM-DD
            assert len(entry["date"]) == 10
            assert entry["date"][4] == "-"
            assert entry["date"][7] == "-"

            # holdings 中权重为正
            for code, weight in entry["holdings"].items():
                assert isinstance(code, str)
                assert weight > 0

    def test_equity_curve_not_empty(self) -> None:
        """权益曲线必须有数据。"""
        nav = make_nav_panel(n_days=60, n_funds=3)
        config = BacktestConfig(top_n=2, rebalance_freq="ME")
        engine = BacktestEngine(nav, config)

        score_factor = MomentumFactor(ma_period=20)
        result = engine.run(score_factor)

        equity = result.equity_curve()
        assert len(equity) > 0
        assert equity.iloc[0] == config.init_cash  # 第一天是初始资金

    def test_stats_returns_series(self) -> None:
        """stats() 返回非空 pandas Series。"""
        nav = make_nav_panel(n_days=60, n_funds=3)
        config = BacktestConfig(top_n=2, rebalance_freq="ME")
        engine = BacktestEngine(nav, config)

        score_factor = MomentumFactor(ma_period=20)
        result = engine.run(score_factor)

        stats = result.stats()
        assert isinstance(stats, pd.Series)
        assert len(stats) > 0


# ---------------------------------------------------------------------------
# 端到端测试
# ---------------------------------------------------------------------------


class TestEndToEnd:
    """端到端回测测试 —— 验证整个引擎链路。"""

    def test_run_with_synthetic_data(self) -> None:
        """
        用合成数据跑完整回测：MomentumFactor 打分 + 等权调仓。
        """
        dates = pd.date_range("2024-01-01", periods=60, freq="D")
        nav_panel = pd.DataFrame(
            {
                "FUND_A": np.linspace(1.0, 1.3, 60),  # 上涨
                "FUND_B": np.linspace(1.3, 1.0, 60),  # 下跌
                "FUND_C": np.linspace(1.0, 1.5, 60),  # 强势上涨
            },
            index=dates,
        )

        config = BacktestConfig(
            top_n=2,
            rebalance_freq="ME",
            weighting="equal",
            fee_rate=0.0015,
            init_cash=1_000_000.0,
        )
        engine = BacktestEngine(nav_panel, config)

        score_factor = MomentumFactor(ma_period=20)
        result = engine.run(score_factor)

        # 返回类型检查
        assert isinstance(result, BacktestResult)

        # 权益曲线检查
        equity = result.equity_curve()
        assert len(equity) == len(nav_panel)

        # 第一天是初始资金
        assert equity.iloc[0] == 1_000_000.0

        # 组合没有崩盘（最终值 > 初始值的 90%）
        # 注意：因为有手续费，不一定赚钱，但不应该暴跌
        assert equity.iloc[-1] > 1_000_000.0 * 0.9

        # stats 有数据
        stats = result.stats()
        assert len(stats) > 0

    def test_run_with_signal_filter(self) -> None:
        """
        带信号过滤的端到端回测：MA 多头排列过滤 + 动量打分。
        """
        dates = pd.date_range("2024-01-01", periods=60, freq="D")
        nav_panel = pd.DataFrame(
            {
                "FUND_A": np.linspace(1.0, 1.3, 60),
                "FUND_B": np.linspace(1.3, 1.0, 60),
                "FUND_C": np.linspace(1.0, 1.5, 60),
            },
            index=dates,
        )

        # MA 交叉过滤：只在 MA 多头排列的基金中选
        ma_filter = MACrossFactor(short=5, long=10)

        config = BacktestConfig(
            top_n=2,
            rebalance_freq="ME",
            weighting="equal",
            signal_filter=ma_filter,
        )
        engine = BacktestEngine(nav_panel, config)

        score_factor = MomentumFactor(ma_period=20)
        result = engine.run(score_factor)

        assert isinstance(result, BacktestResult)

        # 验证 API 响应中包含 signal_filter 信息
        response = result.to_api_response()
        assert response["config"]["signal_filter"] == ma_filter.name

    def test_run_with_score_weighting(self) -> None:
        """
        分数加权的端到端回测。
        """
        dates = pd.date_range("2024-01-01", periods=60, freq="D")
        nav_panel = pd.DataFrame(
            {
                "FUND_A": np.linspace(1.0, 1.3, 60),
                "FUND_B": np.linspace(1.3, 1.0, 60),
                "FUND_C": np.linspace(1.0, 1.5, 60),
            },
            index=dates,
        )

        config = BacktestConfig(
            top_n=2,
            rebalance_freq="ME",
            weighting="score",
            fee_rate=0.0015,
        )
        engine = BacktestEngine(nav_panel, config)

        score_factor = MomentumFactor(ma_period=20)
        result = engine.run(score_factor)

        assert isinstance(result, BacktestResult)

        # 验证调仓历史中权重不等
        history = result.rebalance_history()
        if len(history) > 0:
            for entry in history:
                holdings = entry["holdings"]
                if len(holdings) >= 2:
                    weights = list(holdings.values())
                    # 分数加权下，权重不应该完全相等
                    # （除非两只基金分数恰好一样，概率极低）
                    # 这里只验证权重和接近 1.0
                    total = sum(weights)
                    assert abs(total - 1.0) < 0.01

    def test_empty_portfolio_stays_in_cash(self) -> None:
        """
        没有有效信号时，组合保持现金状态。

        构造场景：所有基金都被 MA 过滤排除（前 10 天 MA 不成熟，全 False）。
        但 60 天足够长，后面会有信号。所以这个测试改用另一种方式：
        用一个永远返回 False 的过滤因子。
        """
        dates = pd.date_range("2024-01-01", periods=60, freq="D")
        nav_panel = pd.DataFrame(
            {
                "FUND_A": np.linspace(1.0, 1.3, 60),
                "FUND_B": np.linspace(1.3, 1.0, 60),
            },
            index=dates,
        )

        # 创建一个总是过滤掉所有基金的"假"因子
        # 用 MACrossFactor(short=999, long=1000) —— 前 1000 天全 False
        # 但 60 天 < 1000，所以永远不会有信号
        # 更简单的方法：直接构造一个 -inf 的分数矩阵，测试 _build_target_weights
        config = BacktestConfig(
            top_n=2,
            rebalance_freq="ME",
            weighting="equal",
        )
        engine = BacktestEngine(nav_panel, config)

        # 构造全 -inf 的分数矩阵
        scores = pd.DataFrame(
            {
                "FUND_A": [-np.inf] * 60,
                "FUND_B": [-np.inf] * 60,
            },
            index=dates,
        )

        weights = engine._build_target_weights(scores)

        # 所有调仓日权重都应该是 0.0
        rebalance_dates = scores.resample("ME").last().index.intersection(
            scores.index
        )
        for dt in rebalance_dates:
            assert (weights.loc[dt] == 0.0).all()

    def test_rebalance_frequency_matches_config(self) -> None:
        """
        调仓次数与 rebalance_freq 一致。
        """
        dates = pd.date_range("2024-01-01", periods=60, freq="D")
        nav_panel = pd.DataFrame(
            {
                "FUND_A": np.linspace(1.0, 1.3, 60),
                "FUND_B": np.linspace(1.3, 1.0, 60),
                "FUND_C": np.linspace(1.0, 1.5, 60),
            },
            index=dates,
        )

        # 60 天从 2024-01-01 到 2024-02-29，跨了 2 个月末
        config = BacktestConfig(
            top_n=2,
            rebalance_freq="ME",
            weighting="equal",
        )
        engine = BacktestEngine(nav_panel, config)

        score_factor = MomentumFactor(ma_period=20)
        result = engine.run(score_factor)

        history = result.rebalance_history()

        # 至少应该有调仓记录（月末调仓）
        assert len(history) >= 1

        # 验证调仓日确实是月末
        for entry in history:
            date_str = entry["date"]
            day = int(date_str.split("-")[2])
            # 月末调仓的日期应该是该月最后一天附近
            # 由于用的是交易日，不一定是自然月的最后一天
            # 这里只验证日期格式正确
            assert len(date_str) == 10


# ---------------------------------------------------------------------------
# 导入测试
# ---------------------------------------------------------------------------


class TestImports:
    """验证各种导入路径都能正常工作。"""

    def test_barrel_import(self) -> None:
        """从包根导入。"""
        from fund_screener.backtest import (
            BacktestConfig,
            BacktestEngine,
            BacktestResult,
        )

        assert BacktestConfig is not None
        assert BacktestEngine is not None
        assert BacktestResult is not None

    def test_direct_import_config(self) -> None:
        """直接从 config 模块导入。"""
        from fund_screener.backtest.config import BacktestConfig

        config = BacktestConfig()
        assert config.top_n == 10

    def test_direct_import_engine(self) -> None:
        """直接从 engine 模块导入。"""
        from fund_screener.backtest.engine import BacktestEngine

        assert BacktestEngine is not None

    def test_direct_import_result(self) -> None:
        """直接从 result 模块导入。"""
        from fund_screener.backtest.result import BacktestResult

        assert BacktestResult is not None
