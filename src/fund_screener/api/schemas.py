"""
API 响应模型 — Pydantic schemas

所有 API 响应统一用这些模型序列化，保证前后端契约稳定。
"""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


# ── 通用包装 ──────────────────────────────────────────────

class APIResponse(BaseModel):
    """统一 API 响应包装。"""
    success: bool = True
    data: Any | None = None
    error: str | None = None


class PaginatedResponse(BaseModel):
    """分页响应包装。"""
    success: bool = True
    data: list[Any] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
    error: str | None = None


# ── Fund 相关 ─────────────────────────────────────────────

class FundSummary(BaseModel):
    """基金列表项。"""
    code: str
    name: str
    market: str


class FundDetail(BaseModel):
    """基金详情。"""
    code: str
    name: str
    market: str
    establish_date: str | None = None
    manager_name: str | None = None
    fund_scale: float | None = None
    track_benchmark: str | None = None


class FundWithMetrics(BaseModel):
    """基金 + 最新 MA 指标。"""
    code: str
    name: str
    market: str
    ma_short: float | None = None
    ma_long: float | None = None
    ma_diff_pct: float | None = None
    score: float | None = None
    purchase_status: str | None = None
    purchase_limit: float | None = None


# ── Screening 相关 ────────────────────────────────────────

class ScreeningResult(BaseModel):
    """单次筛选结果。"""
    code: str
    name: str
    market: str
    nav: float
    ma_short: float
    ma_long: float
    ma_diff_pct: float
    daily_change_pct: float | None = None
    score: float | None = None
    purchase_status: str | None = None
    purchase_limit: float | None = None
    screening_date: str


# ── Chart 相关 ────────────────────────────────────────────

class ChartDataPoint(BaseModel):
    """单点净值数据。"""
    time: str  # YYYY-MM-DD
    value: float
    adj_value: float | None = None


# ── Stats 相关 ────────────────────────────────────────────

class DashboardStats(BaseModel):
    """仪表盘统计。"""
    total_funds: int
    funds_by_market: dict[str, int]
    total_nav_records: int
    nav_date_range: tuple[str | None, str | None]
    latest_screening_date: str | None
    latest_screening_count: int
    db_size_mb: float


class HealthCheck(BaseModel):
    """健康检查。"""
    status: str = "ok"
    db_connected: bool
    db_version: int
