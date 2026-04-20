"""Backtest execution route.

回测执行路由 —— 暴露 POST /api/backtest/run 端点。

设计意图（修改前必须输出）：
为什么把 BacktestRequest/BacktestResponse 定义在 backtest.py 而不是 schemas.py？

1. 回测相关的 schema 只有这个路由用，其他路由不依赖它。
2. 自包含的路由文件降低耦合 —— 读 backtest.py 就能看到完整的请求/响应契约，
   不需要跳转到 schemas.py 再回来。
3. 如果未来回测参数扩展（加新字段），只需要改这一个文件。

DataStore 连接复用模式：
路由从 get_db_conn() 拿到 sqlite3.Connection，需要调用 DataStore.load_nav_panel()。
为了不新建连接（避免连接泄漏和性能损耗），用 DataStore.from_connection() 工厂方法
包装已有连接。这是 storage.py 提供的显式 API，比 __new__ 更干净。

对应 BACKTEST_DESIGN.md §8
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from fund_screener.api.deps import get_db_conn
from fund_screener.backtest.config import BacktestConfig
from fund_screener.backtest.engine import BacktestEngine
from fund_screener.factors.composite import CompositeFactor
from fund_screener.factors.quant import MaxDrawdownFactor, MomentumFactor, SharpeFactor
from fund_screener.factors.technical import MACrossFactor
from fund_screener.storage import DataStore

router = APIRouter()


# ── 请求/响应模型 ──────────────────────────────────────────────


class BacktestRequest(BaseModel):
    """回测请求参数。

    所有字段均有 Pydantic Field 校验，防止恶意/错误输入：
    - top_n: 1~50，防止请求过大的组合
    - fee_rate: 0~0.1（0%~10%），防止极端费率
    """

    score_factor: str = Field(
        default="three_factor",
        description="打分因子: three_factor | momentum | sharpe | drawdown",
    )
    score_weights: dict[str, float] | None = Field(
        default=None,
        description="组合因子的权重覆盖（如 {'momentum': 0.5, 'sharpe': 0.3, 'drawdown': 0.2}）",
    )
    signal_filter: str | None = Field(
        default="ma_cross_20_60",
        description="信号过滤: ma_cross_20_60 | null",
    )
    top_n: int = Field(default=10, ge=1, le=50)
    rebalance_freq: str = Field(
        default="ME",
        description="调仓频率: ME=月末, W-FRI=周五, QE=季末",
    )
    weighting: str = Field(
        default="equal",
        description="权重分配: equal | score",
    )
    fee_rate: float = Field(default=0.0015, ge=0, le=0.1)
    start_date: str = Field(..., description="回测开始日期 YYYY-MM-DD")
    end_date: str = Field(..., description="回测结束日期 YYYY-MM-DD")
    market: str = Field(default="cn", description="市场: cn | us | hk")


class BacktestResponse(BaseModel):
    """回测响应包装 —— 统一格式 {success, data, error}。"""

    success: bool = True
    data: dict | None = None
    error: str | None = None


# ── 因子注册表 ─────────────────────────────────────────────────

_FACTOR_REGISTRY: dict[str, type] = {
    "ma_cross_20_60": lambda: MACrossFactor(20, 60),
    "momentum": lambda: MomentumFactor(20),
    "sharpe": lambda: SharpeFactor(252),
    "drawdown": lambda: MaxDrawdownFactor(252),
    "three_factor": lambda: CompositeFactor(
        factors=[MomentumFactor(), SharpeFactor(), MaxDrawdownFactor()],
        weights=[0.4, 0.25, 0.35],
        name="three_factor",
    ),
}


# ── 路由处理器 ─────────────────────────────────────────────────


@router.post("/backtest/run", response_model=BacktestResponse)
async def run_backtest(
    req: BacktestRequest,
    conn: Annotated["sqlite3.Connection", Depends(get_db_conn)],
) -> dict:
    """Execute backtest and return results.

    完整流程：
    1. 解析并校验请求参数（Pydantic 自动处理）
    2. 根据字符串名称从 _FACTOR_REGISTRY 解析因子实例
    3. 从数据库加载净值面板（宽表 DataFrame）
    4. 构建 BacktestConfig 和 BacktestEngine
    5. 运行回测 → BacktestResult
    6. 序列化为 JSON-safe 字典返回

    威胁缓解（T-03-07）：
    - 未知因子名 → HTTP 400（不暴露内部错误）
    - 空数据范围 → success=False + 友好错误消息
    - 所有数值参数有 Field 边界校验
    """
    # 1. Resolve score factor
    if req.score_factor not in _FACTOR_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown factor: {req.score_factor}",
        )
    score_factor = _FACTOR_REGISTRY[req.score_factor]()

    # 1b. Apply score_weights override if provided
    if req.score_weights is not None and req.score_factor == "three_factor":
        # 校验 score_weights：只允许合法键、非负值、和为 1.0
        _VALID_KEYS = {"momentum", "sharpe", "drawdown"}
        invalid_keys = set(req.score_weights.keys()) - _VALID_KEYS
        if invalid_keys:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid score_weights keys: {invalid_keys}",
            )
        weights_list = [
            req.score_weights.get("momentum", 0.4),
            req.score_weights.get("sharpe", 0.25),
            req.score_weights.get("drawdown", 0.35),
        ]
        if any(w < 0 for w in weights_list):
            raise HTTPException(
                status_code=400,
                detail="score_weights must be non-negative",
            )
        total = sum(weights_list)
        if abs(total - 1.0) > 1e-6:
            raise HTTPException(
                status_code=400,
                detail=f"score_weights must sum to 1.0, got {total}",
            )
        score_factor = CompositeFactor(
            factors=[MomentumFactor(), SharpeFactor(), MaxDrawdownFactor()],
            weights=weights_list,
            name="three_factor_custom",
        )

    # 2. Resolve signal filter
    signal_filter = None
    if req.signal_filter and req.signal_filter in _FACTOR_REGISTRY:
        signal_filter = _FACTOR_REGISTRY[req.signal_filter]()

    # 3. Load data — reuse existing connection via DataStore.from_connection()
    store = DataStore.from_connection(conn)
    nav_panel = store.load_nav_panel(
        market=req.market,
        start_date=req.start_date,
        end_date=req.end_date,
        use_adj_nav=False,  # Phase 3: use nav, switch to adj_nav after backfill
    )

    if nav_panel.empty:
        return {
            "success": False,
            "data": None,
            "error": "No data in specified date range",
        }

    # 4. Build config and engine
    config = BacktestConfig(
        top_n=req.top_n,
        rebalance_freq=req.rebalance_freq,
        weighting=req.weighting,  # type: ignore[arg-type]
        fee_rate=req.fee_rate,
        signal_filter=signal_filter,
    )
    engine = BacktestEngine(nav_panel, config)

    # 5. Run backtest
    result = engine.run(score_factor)

    # 6. Return serialized response
    return {
        "success": True,
        "data": result.to_api_response(),
        "error": None,
    }
