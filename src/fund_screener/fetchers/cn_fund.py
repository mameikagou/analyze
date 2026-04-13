"""
向后兼容 shim — 原 CNFundFetcher 已迁移到 providers.akshare_cn.AkshareCNProvider。

保留本模块是为了避免外部引用(例如 tests/test_purchase_filter.py)瞬间断裂。
新代码请直接用:
    from fund_screener.fetchers.providers import AkshareCNProvider
"""
from __future__ import annotations

from fund_screener.fetchers.providers.akshare_cn import AkshareCNProvider as CNFundFetcher

__all__ = ["CNFundFetcher"]
