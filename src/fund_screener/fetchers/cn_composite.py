"""
A股组合 Fetcher — 按方法路由到不同数据源 provider。

===============================================================================
为什么要做这个中间层 (Why)
===============================================================================
原架构下 cli.py 直接硬编码某一个 Provider (CNFundFetcher 或 CNTushareFetcher),
切换数据源要改代码。而 akshare 和 tushare 各有互补字段:
  - akshare 独占: 申购限额金额、基金经理姓名、行业分布
  - tushare 独占: 付费 SLA 稳定、字段规范

CompositeCNFetcher 把"每个方法走哪家"做成配置驱动:
  cli.py → CompositeCNFetcher → 查路由表 → 派发给对应 Provider

设计模式: Strategy + Registry + Facade
  - Facade: Composite 对外暴露统一的 BaseFetcher 接口
  - Registry: providers dict 存已注册的底层 provider
  - Strategy: route_table 决定每个方法用哪个 strategy

===============================================================================
配置示例 (config.yaml)
===============================================================================
cn_fund:
  data_source:
    primary: akshare              # 未命中 route 时的兜底主源
    route:
      fetch_fund_list: akshare
      fetch_nav_history: tushare  # ← tushare 补充:规范 SLA 净值
      fetch_holdings: akshare
      fetch_sector_exposure: akshare
      fetch_fund_detail: akshare
      fetch_purchase_limit_map: akshare

===============================================================================
扩展指南
===============================================================================
新增第三家数据源(例如同花顺):
  1. 在 providers/ 新增 tonghushun_cn.py,实现 BaseFetcher
  2. 在 cli._build_cn_fetcher 里注册: providers["tonghuashun"] = TonghuashunCNProvider(...)
  3. 在 config.yaml 的 route 里指定哪些方法走它
  不需要改动本文件。
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from fund_screener.cache import FileCache
from fund_screener.config import CNFundConfig, RateLimitConfig
from fund_screener.fetchers.base import BaseFetcher
from fund_screener.models import Holding, Market, SectorWeight

logger = logging.getLogger(__name__)


# BaseFetcher 契约方法集合 —— Composite 必须全部转发
_BASEFETCHER_METHODS: frozenset[str] = frozenset({
    "fetch_fund_list",
    "fetch_nav_history",
    "fetch_holdings",
    "fetch_sector_exposure",
    "fetch_fund_detail",
})

# 非契约但 CLI 会用到的扩展方法(仅部分 provider 实现)
_EXTENSION_METHODS: frozenset[str] = frozenset({
    "fetch_purchase_limit_map",
})


class CompositeCNFetcher(BaseFetcher):
    """
    A股组合 Fetcher — 实现 BaseFetcher 接口,内部按路由表派发到 provider。

    构造器参数:
        cache: 共享的 FileCache (BaseFetcher 契约需要,但本类不直接使用)
        rate_limit_config: 限速配置 (同上,provider 各自有自己的限速)
        cn_config: 含 data_source 路由配置的 CN 基金配置
        providers: 已实例化的 provider 映射,例如:
            {"akshare": AkshareCNProvider(...), "tushare": TushareCNProvider(...)}

    构造时会做 fail-fast 路由校验:
      - data_source.primary 必须在 providers 里
      - data_source.route 中每个 value 必须在 providers 里
      - data_source.route 中每个 key 必须是已知方法名(BaseFetcher 契约 + 扩展)
    """

    def __init__(
        self,
        cache: FileCache,
        rate_limit_config: RateLimitConfig,
        cn_config: CNFundConfig,
        providers: dict[str, BaseFetcher],
    ) -> None:
        super().__init__(
            market=Market.CN,
            cache=cache,
            rate_limit_config=rate_limit_config,
        )
        self._cn_config = cn_config
        self._providers: dict[str, BaseFetcher] = dict(providers)
        self._primary: str = cn_config.data_source.primary
        self._route: dict[str, str] = dict(cn_config.data_source.route)
        self._validate_routing()
        logger.info(
            "CompositeCNFetcher 初始化完成 — primary=%s, providers=%s, route=%s",
            self._primary, list(self._providers), self._route,
        )

    # ------------------------------------------------------------------
    # 路由核心
    # ------------------------------------------------------------------

    @property
    def _delay_sec(self) -> float:
        """Composite 本身不发起请求,限速交给底层 provider 处理。"""
        return 0.0

    def _validate_routing(self) -> None:
        """
        启动时校验路由表配置,错配直接 fail-fast,不让问题延迟到运行时。

        校验项:
        1. primary 必须在 providers 里(否则未命中 route 时没得兜底)
        2. route 的每个 value 必须在 providers 里
        3. route 的每个 key 必须是已知方法(防止 yaml 里拼错方法名)
        """
        if self._primary not in self._providers:
            raise ValueError(
                f"data_source.primary='{self._primary}' 未注册,"
                f"已注册 providers: {sorted(self._providers)}",
            )

        known_methods = _BASEFETCHER_METHODS | _EXTENSION_METHODS
        for method_name, provider_name in self._route.items():
            if method_name not in known_methods:
                raise ValueError(
                    f"data_source.route 含未知方法名 '{method_name}',"
                    f"允许: {sorted(known_methods)}",
                )
            if provider_name not in self._providers:
                raise ValueError(
                    f"data_source.route['{method_name}']='{provider_name}' 未注册,"
                    f"已注册 providers: {sorted(self._providers)}",
                )

    def _resolve(self, method_name: str) -> BaseFetcher:
        """
        根据方法名解析出对应的 provider。

        命中 route → 用 route 里的 provider
        未命中     → 用 primary 主源兜底
        """
        provider_name = self._route.get(method_name, self._primary)
        provider = self._providers[provider_name]  # 已在 _validate_routing 保证存在
        logger.debug(
            "CompositeCNFetcher.%s → %s (%s)",
            method_name, provider_name, type(provider).__name__,
        )
        return provider

    # ------------------------------------------------------------------
    # BaseFetcher 契约方法 — 全部转发到 resolve 出的 provider
    # ------------------------------------------------------------------

    def fetch_fund_list(self) -> list[dict[str, str]]:
        return self._resolve("fetch_fund_list").fetch_fund_list()

    def fetch_nav_history(self, code: str, days: int) -> pd.DataFrame:
        return self._resolve("fetch_nav_history").fetch_nav_history(code, days)

    def fetch_holdings(self, code: str) -> list[Holding]:
        return self._resolve("fetch_holdings").fetch_holdings(code)

    def fetch_sector_exposure(self, code: str) -> list[SectorWeight]:
        return self._resolve("fetch_sector_exposure").fetch_sector_exposure(code)

    def fetch_fund_detail(self, code: str) -> dict[str, Any]:
        return self._resolve("fetch_fund_detail").fetch_fund_detail(code)

    # ------------------------------------------------------------------
    # 扩展方法 — 非 BaseFetcher 契约,只有部分 provider 实现
    # ------------------------------------------------------------------

    def fetch_purchase_limit_map(self) -> dict[str, tuple[float, str]]:
        """
        获取全市场基金申购限额映射表。

        这个方法不在 BaseFetcher 抽象里(akshare 独占精确金额,tushare 只有二元状态),
        用 hasattr 兜底:如果路由命中的 provider 没实现,返回空 dict 不阻塞主流程。
        """
        provider = self._resolve("fetch_purchase_limit_map")
        if not hasattr(provider, "fetch_purchase_limit_map"):
            logger.warning(
                "provider %s 未实现 fetch_purchase_limit_map,返回空 dict",
                type(provider).__name__,
            )
            return {}
        return provider.fetch_purchase_limit_map()  # type: ignore[no-any-return]
