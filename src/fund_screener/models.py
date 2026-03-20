"""
数据模型定义 — 全市场基金/ETF 筛选器的核心数据结构。

所有模块（fetcher、screener、reporter）都依赖这些模型，
使用 Pydantic BaseModel 实现类型安全 + 序列化 + 校验一体化。
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Market(str, Enum):
    """支持的市场类型"""
    CN = "CN"   # A股公募基金
    US = "US"   # 美股 ETF
    HK = "HK"   # 港股 ETF


class NAVRecord(BaseModel):
    """单日净值/价格记录"""
    date: date
    nav: float = Field(description="单位净值或收盘价")


class Holding(BaseModel):
    """基金/ETF 的单只持仓股票"""
    stock_code: str = Field(description="股票代码")
    stock_name: str = Field(description="股票名称")
    weight_pct: float | None = Field(
        default=None,
        description="持仓权重百分比，部分数据源可能拿不到",
    )


class SectorWeight(BaseModel):
    """行业/板块权重"""
    sector: str = Field(description="行业名称")
    weight_pct: float = Field(description="占比百分比")


class TrendStats(BaseModel):
    """
    多周期涨跌幅统计。

    用最新净值 vs N 交易日前的净值计算累计涨跌幅百分比。
    数据不足某个周期时填 None，而不是硬算一个不靠谱的数字。
    """
    change_1w: float | None = None   # 近 1 周涨跌幅 %
    change_1m: float | None = None   # 近 1 月涨跌幅 %
    change_3m: float | None = None   # 近 3 月涨跌幅 %
    change_6m: float | None = None   # 近 6 月涨跌幅 %
    change_1y: float | None = None   # 近 1 年涨跌幅 %


class ScreenResult(BaseModel):
    """MA 筛选结果"""
    ma_short: float = Field(description="短期均线值 (如 MA20)")
    ma_long: float = Field(description="长期均线值 (如 MA60)")
    ma_diff_pct: float = Field(description="(MA_short - MA_long) / MA_long * 100")
    passed: bool = Field(description="是否通过筛选 (MA_short > MA_long)")


class FundInfo(BaseModel):
    """
    通过筛选的基金/ETF 完整信息。

    这是最终输出到报告的核心数据结构，包含：
    - 基本信息（代码、名称、市场）
    - 最新净值/价格
    - MA 技术指标
    - 持仓明细（Top 10）
    - 行业分布
    """
    code: str = Field(description="基金/ETF 代码")
    name: str = Field(description="基金/ETF 名称")
    market: Market = Field(description="所属市场")
    nav: float = Field(description="最新单位净值或收盘价")
    ma_short: float = Field(description="短期均线值")
    ma_long: float = Field(description="长期均线值")
    ma_diff_pct: float = Field(description="MA 差值百分比")
    top_holdings: list[Holding] = Field(
        default_factory=list,
        description="Top 10 持仓股票",
    )
    sector_exposure: list[SectorWeight] = Field(
        default_factory=list,
        description="行业分布",
    )
    daily_change_pct: float | None = Field(
        default=None,
        description="当日涨跌幅百分比",
    )
    trend_stats: TrendStats | None = Field(
        default=None,
        description="多周期涨跌幅统计（1周/1月/3月/6月/1年）",
    )
    data_date: date = Field(description="数据日期")
    holdings_date: str | None = Field(
        default=None,
        description="持仓数据的报告期（如 '2025Q4'），A股基金持仓滞后约 1 个季度",
    )


class ScreeningSummary(BaseModel):
    """筛选结果汇总统计"""
    market: Market
    total_scanned: int = Field(description="扫描的基金总数")
    total_passed: int = Field(description="通过筛选的基金数")
    pass_rate: float = Field(description="通过率百分比")
