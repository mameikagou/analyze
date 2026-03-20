"""
Fetcher 抽象基类 — 定义所有数据源必须实现的统一接口。

设计模式：策略模式 (Strategy Pattern)
三个市场（CN / US / HK）各实现一个 BaseFetcher 子类，
新增数据源只需加一个类，不动现有代码。
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any

import pandas as pd
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from fund_screener.cache import FileCache
from fund_screener.config import RateLimitConfig
from fund_screener.models import Holding, Market, SectorWeight

logger = logging.getLogger(__name__)


class BaseFetcher(ABC):
    """
    数据源抽象基类。

    子类必须实现四个核心方法：
    - fetch_fund_list: 获取基金/ETF 代码列表
    - fetch_nav_history: 获取单只基金的净值/价格历史
    - fetch_holdings: 获取单只基金的持仓明细
    - fetch_sector_exposure: 获取行业分布

    基类提供：
    - 统一的限速机制 (_rate_limit)
    - 统一的缓存访问 (cache)
    - 通用的重试装饰器模式
    """

    def __init__(
        self,
        market: Market,
        cache: FileCache,
        rate_limit_config: RateLimitConfig,
    ) -> None:
        self.market = market
        self.cache = cache
        self.rate_limit_config = rate_limit_config
        self._last_request_time: float = 0.0

    @property
    @abstractmethod
    def _delay_sec(self) -> float:
        """每次请求之间的最小间隔秒数（子类根据数据源设定）。"""
        ...

    def _rate_limit(self) -> None:
        """
        简单的限速：确保两次请求之间至少间隔 _delay_sec 秒。

        为什么不用 asyncio？因为 akshare/yfinance 本身是同步库，
        异步化收益不大，反而增加复杂度。保持简单。
        """
        elapsed = time.time() - self._last_request_time
        if elapsed < self._delay_sec:
            time.sleep(self._delay_sec - elapsed)
        self._last_request_time = time.time()

    def _cache_key(self, fund_code: str, data_type: str) -> str:
        """生成统一格式的缓存 key。"""
        return f"{self.market.value}/{fund_code}_{data_type}"

    @abstractmethod
    def fetch_fund_list(self) -> list[dict[str, str]]:
        """
        获取该市场所有基金/ETF 列表。

        Returns:
            list of {"code": "005827", "name": "易方达蓝筹精选混合"}
        """
        ...

    @abstractmethod
    def fetch_nav_history(self, code: str, days: int) -> pd.DataFrame:
        """
        获取单只基金的净值/价格历史。

        Args:
            code: 基金/ETF 代码
            days: 需要的历史天数

        Returns:
            DataFrame with columns ["date", "nav"]，按日期升序排列
        """
        ...

    @abstractmethod
    def fetch_holdings(self, code: str) -> list[Holding]:
        """
        获取基金/ETF 的 Top 持仓。

        Args:
            code: 基金/ETF 代码

        Returns:
            持仓列表，按权重降序
        """
        ...

    @abstractmethod
    def fetch_sector_exposure(self, code: str) -> list[SectorWeight]:
        """
        获取行业/板块分布。

        Args:
            code: 基金/ETF 代码

        Returns:
            行业权重列表
        """
        ...


def with_retry(max_retries: int = 3, backoff_sec: float = 2.0) -> Any:
    """
    创建重试装饰器的工厂函数。

    使用 tenacity 库实现指数退避重试，比手写 while loop 更健壮。
    只重试网络相关的异常，逻辑错误（如 ValueError）不重试。
    """
    return retry(
        stop=stop_after_attempt(max_retries),
        wait=wait_exponential(multiplier=backoff_sec, min=1, max=30),
        retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
        before_sleep=lambda retry_state: logger.warning(
            "请求失败，%s 秒后重试 (第 %d/%d 次): %s",
            retry_state.next_action.sleep,  # type: ignore[union-attr]
            retry_state.attempt_number,
            max_retries,
            retry_state.outcome.exception() if retry_state.outcome else "unknown",  # type: ignore[union-attr]
        ),
        reraise=True,
    )
