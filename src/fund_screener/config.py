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

class CNFundConfig(BaseModel):
    """A股公募基金配置"""
    enabled: bool = True
    fund_types: list[str] = Field(default_factory=lambda: ["股票型", "混合型", "指数型"])
    max_funds: int = 500


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
    akshare_delay_sec: float = 0.5
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

    return config
