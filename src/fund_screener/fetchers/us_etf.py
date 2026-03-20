"""
美股 ETF 数据获取器。

数据源：
- 价格历史：yfinance（Yahoo Finance 的 Python 封装）
- 持仓明细：us_holdings.py 模块（etfdb.com 爬虫 + 静态 JSON 兜底）

为什么美股 ETF 最复杂？
yfinance 能拿到价格历史，但拿不到 ETF 的 top holdings 明细。
所以持仓数据需要额外从 etfdb.com 爬取，爬虫不稳定时 fallback 到静态 JSON。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from fund_screener.cache import FileCache
from fund_screener.config import RateLimitConfig, USETFConfig
from fund_screener.fetchers.base import BaseFetcher, with_retry
from fund_screener.fetchers.us_holdings import fetch_etf_holdings_from_web
from fund_screener.models import Holding, Market, SectorWeight

logger = logging.getLogger(__name__)


class USETFFetcher(BaseFetcher):
    """美股 ETF 数据获取器（yfinance + etfdb 爬虫）。"""

    def __init__(
        self,
        cache: FileCache,
        rate_limit_config: RateLimitConfig,
        us_config: USETFConfig,
    ) -> None:
        super().__init__(
            market=Market.US,
            cache=cache,
            rate_limit_config=rate_limit_config,
        )
        self._us_config = us_config
        self._static_data: dict[str, dict] | None = None

    @property
    def _delay_sec(self) -> float:
        return self.rate_limit_config.yfinance_delay_sec

    def _load_static_data(self) -> dict[str, dict]:
        """
        加载静态 ETF 数据（us_etf_universe.json）。

        这个文件包含 300+ 主流 ETF 的代码、名称、行业分类，
        以及部分热门 ETF 的 top holdings 数据。
        用作爬虫失败时的兜底方案。
        """
        if self._static_data is not None:
            return self._static_data

        source_path = Path(self._us_config.ticker_source)
        if not source_path.exists():
            logger.warning("静态 ETF 数据文件不存在: %s", source_path)
            self._static_data = {}
            return self._static_data

        try:
            with open(source_path, encoding="utf-8") as f:
                data = json.load(f)
            # 期望格式：[{"ticker": "SPY", "name": "...", "sector": "...", "holdings": [...]}]
            self._static_data = {item["ticker"]: item for item in data}
        except (json.JSONDecodeError, KeyError) as e:
            logger.error("静态 ETF 数据文件格式错误: %s", e)
            self._static_data = {}

        return self._static_data

    def fetch_fund_list(self) -> list[dict[str, str]]:
        """
        获取美股 ETF 列表。

        数据来源：静态 JSON 文件 + 用户配置的额外 ticker。
        """
        cache_key = self._cache_key("all", "fund_list")
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        static_data = self._load_static_data()

        result: list[dict[str, str]] = [
            {"code": ticker, "name": info.get("name", ticker)}
            for ticker, info in static_data.items()
        ]

        # 追加用户配置的额外 ticker
        existing_codes = {item["code"] for item in result}
        for ticker in self._us_config.extra_tickers:
            if ticker not in existing_codes:
                result.append({"code": ticker, "name": ticker})

        self.cache.set(cache_key, result)
        logger.info("美股 ETF 列表加载完成: %d 只", len(result))
        return result

    @with_retry(max_retries=3, backoff_sec=2.0)
    def fetch_nav_history(self, code: str, days: int) -> pd.DataFrame:
        """
        获取美股 ETF 的价格历史（收盘价）。

        使用 yfinance 的 Ticker.history()。
        注意：yfinance 对部分冷门 ETF 可能返回空数据。
        """
        import yfinance as yf

        cache_key = self._cache_key(code, "nav_history")
        cached = self.cache.get(cache_key)
        if cached is not None:
            return pd.DataFrame(cached)

        self._rate_limit()

        try:
            ticker = yf.Ticker(code)
            # yfinance 用 period 参数比 start/end 更可靠
            period = "6mo" if days <= 180 else "1y"
            df = ticker.history(period=period)
        except Exception as e:
            logger.warning("获取 ETF %s 价格历史失败: %s", code, e)
            return pd.DataFrame(columns=["date", "nav"])

        if df is None or df.empty:
            logger.debug("ETF %s 无价格数据", code)
            return pd.DataFrame(columns=["date", "nav"])

        result_df = pd.DataFrame({
            "date": df.index.tz_localize(None) if df.index.tz else df.index,
            "nav": df["Close"].values,
        })
        result_df = result_df.dropna().sort_values("date").reset_index(drop=True)

        # 只保留最近 N 天
        if days > 0 and len(result_df) > 0:
            cutoff = datetime.now() - timedelta(days=days)
            result_df = result_df[result_df["date"] >= cutoff]

        # 缓存
        cache_data = result_df.copy()
        cache_data["date"] = cache_data["date"].dt.strftime("%Y-%m-%d")
        self.cache.set(cache_key, cache_data.to_dict(orient="records"))

        return result_df

    def fetch_holdings(self, code: str) -> list[Holding]:
        """
        获取美股 ETF 持仓。

        优先级：
        1. 缓存
        2. etfdb.com 爬虫（us_holdings.py）
        3. 静态 JSON 兜底
        """
        cache_key = self._cache_key(code, "holdings")
        cached = self.cache.get(cache_key)
        if cached is not None:
            return [Holding(**h) for h in cached]

        # 方案 1：爬虫获取
        holdings = fetch_etf_holdings_from_web(
            ticker=code,
            delay_sec=self.rate_limit_config.etfdb_delay_sec,
        )

        # 方案 2：静态数据兜底
        if not holdings:
            static_data = self._load_static_data()
            static_info = static_data.get(code, {})
            static_holdings = static_info.get("holdings", [])
            holdings = [
                Holding(
                    stock_code=h.get("code", ""),
                    stock_name=h.get("name", ""),
                    weight_pct=h.get("weight"),
                )
                for h in static_holdings
            ]

        self.cache.set(cache_key, [h.model_dump() for h in holdings])
        return holdings

    def fetch_sector_exposure(self, code: str) -> list[SectorWeight]:
        """
        获取美股 ETF 行业分布。

        优先从静态数据取（比爬虫稳定），爬虫只在静态数据没有时才用。
        """
        cache_key = self._cache_key(code, "sectors")
        cached = self.cache.get(cache_key)
        if cached is not None:
            return [SectorWeight(**s) for s in cached]

        # 先查静态数据
        static_data = self._load_static_data()
        static_info = static_data.get(code, {})
        sectors_data = static_info.get("sectors", [])

        sectors = [
            SectorWeight(sector=s.get("sector", ""), weight_pct=s.get("weight", 0))
            for s in sectors_data
            if s.get("sector") and s.get("weight", 0) > 0
        ]

        if sectors:
            self.cache.set(cache_key, [s.model_dump() for s in sectors])

        return sectors
