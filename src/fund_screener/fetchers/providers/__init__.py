"""
A股数据源 Provider 子包 — 底层数据拉取实现。

每个 Provider 实现 BaseFetcher 接口,可单独使用;
上层通常通过 CompositeCNFetcher 按路由表组合调度。
"""
from __future__ import annotations

from fund_screener.fetchers.providers.akshare_cn import AkshareCNProvider
from fund_screener.fetchers.providers.tushare_cn import TushareCNProvider

__all__ = ["AkshareCNProvider", "TushareCNProvider"]
