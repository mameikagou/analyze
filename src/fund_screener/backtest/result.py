"""
回测结果 —— 封装 vectorbt Portfolio 并提供序列化能力。

设计意图（修改前必须输出）：
为什么把 Portfolio 对象和序列化分开？

1. vectorbt 的 Portfolio 对象不可 JSON 序列化（内部包含 NumPy 数组、Numba 函数等）。
   直接传给前端会序列化失败。
2. 但 Portfolio 对象本身很有用 —— 可以调用 .stats()、.value()、.drawdown() 等方法
   获取各种衍生指标。如果只在 to_api_response() 里提取一次，会丢失灵活性。
3. 所以设计为：BacktestResult 持有 Portfolio 对象（供内部使用），
   to_api_response() 负责提取可序列化的子集（供 API 返回）。

威胁缓解（T-03-05）：
- to_api_response() 只提取显式列出的字段，绝不泄漏 Portfolio 对象本身
- 所有浮点数 round 到 2-4 位小数，避免 JSON 序列化时的浮点精度噪音
- 日期转为字符串，避免 pandas Timestamp 的序列化问题

对应 BACKTEST_DESIGN.md §6.4
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from .config import BacktestConfig

# vectorbt 导入做容错处理
try:
    import vectorbt as vbt
except ImportError as e:
    raise ImportError(
        "vectorbt is required but not installed or failed to import. "
        "Please run: uv add vectorbt==0.26.0\n"
        f"Original error: {e}"
    ) from e


@dataclass
class BacktestResult:
    """
    回测结果 —— 包含 vectorbt Portfolio 对象和衍生数据。

    注意：Portfolio 对象不可 JSON 序列化，to_api_response() 负责提取可序列化的数据。

    Attributes:
        portfolio: vectorbt Portfolio 对象，内部持有回测的所有计算结果
        target_weights: 每日目标持仓权重矩阵（调仓日有值，非调仓日为 NaN）
        score_factor_name: 打分因子的名称（用于报告展示）
        config: 回测配置（frozen，不可变）
    """

    portfolio: "vbt.Portfolio"
    target_weights: pd.DataFrame
    score_factor_name: str
    config: BacktestConfig

    # ------------------------------------------------------------------
    # 核心指标（直接委托给 vectorbt）
    # ------------------------------------------------------------------

    def stats(self) -> pd.Series:
        """标准绩效指标（总收益、年化收益、夏普、最大回撤、胜率等）。"""
        return self.portfolio.stats()

    def equity_curve(self) -> pd.Series:
        """组合净值曲线（每日组合总价值）。"""
        return self.portfolio.value()

    def drawdown_curve(self) -> pd.Series:
        """回撤曲线（每日相对历史高点的跌幅，负值）。"""
        return self.portfolio.drawdown()

    def returns(self) -> pd.Series:
        """日收益率序列。"""
        return self.portfolio.returns()

    # ------------------------------------------------------------------
    # 调仓历史（供前端展示）
    # ------------------------------------------------------------------

    def rebalance_history(self) -> list[dict[str, Any]]:
        """
        历次调仓的持仓明细。

        Returns:
            [
                {
                    'date': '2020-01-31',
                    'holdings': {'510300': 0.1, '510500': 0.1, ...}
                },
                ...
            ]
        """
        # dropna(how="all") 只保留至少有一只基金有调仓指令的日期
        rebal = self.target_weights.dropna(how="all")
        return [
            {
                "date": str(idx.date()),
                "holdings": row[row > 0].round(4).to_dict(),
            }
            for idx, row in rebal.iterrows()
        ]

    # ------------------------------------------------------------------
    # 序列化（供 API 返回）
    # ------------------------------------------------------------------

    def to_api_response(self) -> dict[str, Any]:
        """
        序列化为前端可用的字典。

        威胁缓解（T-03-05）：
        - 只提取显式列出的可序列化字段
        - 所有浮点数 round 到 2-4 位小数
        - 日期转为字符串
        - 绝不包含 Portfolio 对象或 pd.Series

        注意：
        - equity_curve 和 drawdown 可能很长（几千个点），前端可能只需要抽样
        - 这里返回全量，前端按自己的抽样策略处理

        Returns:
            JSON-可序列化的字典
        """
        stats = self.stats()

        # equity_curve: { '2020-01-02': 1000000.0, '2020-01-03': 1001200.0, ... }
        equity = self.equity_curve()
        equity_dict: dict[str, float] = {
            str(k.date()): round(float(v), 2)
            for k, v in equity.items()
            if pd.notna(v)
        }

        # drawdown: 同上格式，转为百分比
        dd = self.drawdown_curve()
        dd_dict: dict[str, float] = {
            str(k.date()): round(float(v) * 100, 4)  # 转百分比
            for k, v in dd.items()
            if pd.notna(v)
        }

        # stats 提取关键字段 —— 显式列出，避免泄漏内部对象
        # vectorbt 的 stats() 返回的 Series 索引名可能因版本不同有差异，
        # 用 .get() 提供默认值，兼容不同版本
        stats_dict: dict[str, Any] = {
            "total_return": float(stats.get("Total Return [%]", 0)),
            "annual_return": float(stats.get("Annual Return [%]", 0)),
            "sharpe_ratio": float(stats.get("Sharpe Ratio", 0)),
            "max_drawdown": float(stats.get("Max Drawdown [%]", 0)),
            "win_rate": float(stats.get("Win Rate [%]", 0)),
            "avg_win": float(stats.get("Avg Winning Trade [%]", 0)),
            "avg_loss": float(stats.get("Avg Losing Trade [%]", 0)),
            "profit_factor": float(stats.get("Profit Factor", 0)),
            "total_trades": int(stats.get("Total Trades", 0)),
        }

        return {
            "factor_name": self.score_factor_name,
            "config": {
                "top_n": self.config.top_n,
                "rebalance_freq": self.config.rebalance_freq,
                "weighting": self.config.weighting,
                "fee_rate": self.config.fee_rate,
                "init_cash": self.config.init_cash,
                "signal_filter": (
                    self.config.signal_filter.name
                    if self.config.signal_filter is not None
                    else None
                ),
            },
            "stats": stats_dict,
            "equity_curve": equity_dict,
            "drawdown": dd_dict,
            "rebalance_history": self.rebalance_history(),
        }
