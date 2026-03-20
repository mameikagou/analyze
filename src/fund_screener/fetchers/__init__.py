"""数据获取模块 — 三个市场各一个 Fetcher 实现。"""

from fund_screener.fetchers.base import BaseFetcher
from fund_screener.fetchers.cn_fund import CNFundFetcher
from fund_screener.fetchers.hk_etf import HKETFFetcher
from fund_screener.fetchers.us_etf import USETFFetcher

__all__ = ["BaseFetcher", "CNFundFetcher", "USETFFetcher", "HKETFFetcher"]
