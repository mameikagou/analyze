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
    hold_shares: float | None = Field(
        default=None,
        description="持股数量（万股），V2 新增",
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
    purchase_limit: float | None = Field(
        default=None,
        description="日累计限定金额（元），None=未知，0=暂停申购，1e11=无限制",
    )
    purchase_status_text: str | None = Field(
        default=None,
        description="申购状态原始文本（如 '开放申购'、'暂停申购'、'暂停大额申购'）",
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


# =====================================================================
# OLAP 量化分析模型 — v2 新增
# =====================================================================


class StockSectorMapping(BaseModel):
    """
    股票申万行业映射。

    每只 A 股股票对应一个申万一级行业分类，
    附带 is_hard_tech / is_resource 标签用于快速风格判定。
    """
    stock_code: str = Field(description="股票代码，如 '600519'")
    stock_name: str = Field(default="", description="股票名称")
    sw_sector_l1: str = Field(description="申万一级行业，如 '食品饮料'")
    is_hard_tech: bool = Field(
        default=False,
        description="是否属于硬科技赛道（电子/计算机/通信/军工/电力设备）",
    )
    is_resource: bool = Field(
        default=False,
        description="是否属于资源类（煤炭/石油石化/有色/钢铁/基础化工）",
    )


class MomentumScanResult(BaseModel):
    """
    横截面动量扫描结果 — 单只基金的扫描快照。

    筛选逻辑：MA_short > MA_long（多头排列）且 daily_return < 0（缩量回踩）。
    这类标的处于趋势上行中的短期回调，是经典的"右侧回踩买入"信号。
    """
    fund_code: str = Field(description="基金代码")
    fund_name: str = Field(default="", description="基金名称")
    scan_date: str = Field(description="扫描日期 YYYY-MM-DD")
    ma_short: float = Field(description="短期均线值")
    ma_long: float = Field(description="长期均线值")
    ma_diff_pct: float = Field(description="MA 差值百分比")
    daily_return: float = Field(description="当日涨跌幅百分比")
    latest_nav: float = Field(description="最新净值/价格")


class StyleDriftResult(BaseModel):
    """
    风格漂移检测结果。

    比较两个季度的 Top10 持仓变化，计算换手率，
    标记新进/退出/大幅调仓的个股。
    """
    fund_code: str = Field(description="基金代码")
    current_quarter: str = Field(description="当前季度标签，如 '2026-03-31'")
    prev_quarter: str = Field(description="对比季度标签，如 '2025-12-31'")
    total_turnover: float = Field(
        description="总换手率百分比 = sum(|delta_weight|) / 2",
    )
    is_drifted: bool = Field(description="是否判定为风格漂移（超阈值）")
    threshold: float = Field(description="漂移判定阈值百分比")
    new_entries: list[str] = Field(
        default_factory=list,
        description="新进持仓股票代码列表",
    )
    exits: list[str] = Field(
        default_factory=list,
        description="退出持仓股票代码列表",
    )
    major_changes: list[dict[str, object]] = Field(
        default_factory=list,
        description="大幅调仓明细 [{'stock_code': ..., 'prev_weight': ..., 'curr_weight': ...}]",
    )


class CorrelationPair(BaseModel):
    """
    基金对相关性 — 两只基金之间的行业持仓相似度。

    基于行业权重向量的余弦相似度，用于检测"买了看似不同、实际高度相关"的基金。
    """
    fund_a: str = Field(description="基金 A 代码")
    fund_b: str = Field(description="基金 B 代码")
    similarity: float = Field(description="余弦相似度 [0, 1]")
    is_alert: bool = Field(description="是否超过报警阈值")
