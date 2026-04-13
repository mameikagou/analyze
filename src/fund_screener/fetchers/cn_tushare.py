"""
向后兼容 shim — 原 CNTushareFetcher 已迁移到 providers.tushare_cn.TushareCNProvider。

保留本模块是为了避免外部引用瞬间断裂。
新代码请直接用:
    from fund_screener.fetchers.providers import TushareCNProvider
或通过 CompositeCNFetcher 按路由表组合调度。
"""
from __future__ import annotations

from fund_screener.fetchers.providers.tushare_cn import TushareCNProvider as CNTushareFetcher

__all__ = ["CNTushareFetcher"]
