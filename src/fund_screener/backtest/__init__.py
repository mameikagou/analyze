"""
回测层 —— signal_df × nav_df → 绩效指标。

职责边界（ARCHITECTURE.md 原则三）：
- 做：把信号矩阵变成收益矩阵
- 不做：因子计算（因子层）、数据清洗（storage.py）、报告生成（reporter.py）

用法：
    from fund_screener.backtest import BacktestConfig, BacktestEngine, BacktestResult

    config = BacktestConfig(top_n=10, rebalance_freq="ME", weighting="equal")
    engine = BacktestEngine(nav_panel, config)
    result = engine.run(score_factor, signal_filter=ma_factor)
    response = result.to_api_response()
"""

from .config import BacktestConfig
from .engine import BacktestEngine
from .result import BacktestResult

__all__ = [
    "BacktestConfig",
    "BacktestEngine",
    "BacktestResult",
]
