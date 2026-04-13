"""
配置加载与校验模块。

使用 Pydantic BaseSettings 加载 config.yaml，
提供类型安全的配置访问 + 默认值兜底。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


# ---- 子配置模型 ----

class CNDataSourceConfig(BaseModel):
    """
    A股数据源路由配置 — 组合 fetcher 的核心开关。

    设计思路：
    - primary 是"未命中 route 时的兜底主源"
    - route 是"每个抽象方法具体走哪家 provider"，key 为 BaseFetcher 方法名
    - 不在 route 里的方法默认走 primary，避免新增方法时忘了配
    """
    primary: str = Field(
        default="akshare",
        description="主数据源（route 未命中时的兜底），可选: akshare / tushare",
    )
    route: dict[str, str] = Field(
        default_factory=lambda: {
            "fetch_fund_list": "akshare",
            "fetch_nav_history": "tushare",   # tushare 补充：规范 SLA 净值
            "fetch_holdings": "akshare",
            "fetch_sector_exposure": "akshare",
            "fetch_fund_detail": "akshare",
            "fetch_purchase_limit_map": "akshare",
        },
        description="方法→provider 路由表，key 为 BaseFetcher 方法名",
    )


class CNFundConfig(BaseModel):
    """A股公募基金配置"""
    enabled: bool = True
    fund_types: list[str] = Field(default_factory=lambda: ["股票型", "混合型", "指数型"])
    max_funds: int = 500
    annotate_purchase: bool = Field(
        default=True,
        description="是否标注申购限额信息（默认开启，仅标注不过滤）",
    )
    filter_purchase: bool = Field(
        default=False,
        description="是否过滤限额不足的基金（默认关闭，需配合 --purchase-filter 使用）",
    )
    purchase_min_limit: float = Field(
        default=1000.0,
        description="申购过滤阈值（元），仅 filter_purchase=true 时生效",
    )
    data_source: CNDataSourceConfig = Field(
        default_factory=CNDataSourceConfig,
        description="数据源路由配置，支持多 provider 组合",
    )


class USETFConfig(BaseModel):
    """美股 ETF 配置"""
    enabled: bool = True
    ticker_source: str = "data/us_etf_universe.json"
    extra_tickers: list[str] = Field(default_factory=list)


class HKETFConfig(BaseModel):
    """港股 ETF 配置"""
    enabled: bool = True
    max_funds: int = 200


class RateLimitConfig(BaseModel):
    """限速配置 — 防止被数据源封 IP"""
    tushare_delay_sec: float = 0.3
    akshare_delay_sec: float = 0.5   # akshare 爬东财，必须保守限速防封 IP
    yfinance_delay_sec: float = 0.3
    etfdb_delay_sec: float = 1.0
    max_retries: int = 3
    retry_backoff_sec: float = 2.0


# ---- 主配置 ----

class AppConfig(BaseModel):
    """
    应用主配置。

    加载优先级：config.yaml > 代码默认值
    所有路径字段在加载后会被解析为绝对路径。
    """
    ma_short: int = 20
    ma_long: int = 60
    lookback_days: int = 150

    output_dir: str = "./output"
    cache_dir: str = "./.cache"
    cache_ttl_hours: int = 12

    db_path: str = "./data/fund_data.db"
    store_enabled: bool = True

    cn_fund: CNFundConfig = Field(default_factory=CNFundConfig)
    us_etf: USETFConfig = Field(default_factory=USETFConfig)
    hk_etf: HKETFConfig = Field(default_factory=HKETFConfig)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)


def load_config(config_path: str | Path = "config.yaml") -> AppConfig:
    """
    从 YAML 文件加载配置。

    如果文件不存在，使用全部默认值（不报错，方便首次运行）。

    Args:
        config_path: 配置文件路径，默认当前目录下的 config.yaml

    Returns:
        校验后的 AppConfig 实例
    """
    config_path = Path(config_path)

    config_data: dict[str, Any] = {}
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
            if isinstance(raw, dict):
                config_data = raw

    config = AppConfig(**config_data)

    # 确保输出目录和缓存目录存在
    Path(config.output_dir).mkdir(parents=True, exist_ok=True)
    Path(config.cache_dir).mkdir(parents=True, exist_ok=True)

    # 确保数据库文件的父目录存在
    Path(config.db_path).parent.mkdir(parents=True, exist_ok=True)

    return config
