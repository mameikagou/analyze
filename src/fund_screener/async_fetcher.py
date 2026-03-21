"""
异步批量抓取协调器 — 用 asyncio 并发加速数据获取。

设计决策：
1. 用 asyncio.to_thread() 包装同步 fetcher，而非重写为 async
   - 因为 akshare/yfinance 底层是同步库，async 重写收益不大
   - to_thread 是最小侵入式的并发方案
2. Semaphore 控制并发数，防止 IP 被封
3. 每个 batch 间随机 sleep，模拟"人类浏览"行为
4. 失败自动入 ErrorQueue，下次启动自动重试

注意：
    asyncio.to_thread 的线程池默认 max_workers = min(32, cpu_count + 4)。
    如果 Semaphore(10) 但线程池只有 8，实际并发受限于线程池。
    所以需要显式设置线程池大小 >= concurrency。
"""

from __future__ import annotations

import asyncio
import logging
import random
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from fund_screener.error_queue import ErrorQueue
from fund_screener.fetchers.base import BaseFetcher
from fund_screener.storage import DataStore

logger = logging.getLogger("fund_screener.async_fetcher")


class AsyncBulkFetcher:
    """
    异步批量抓取协调器。

    Usage:
        fetcher = AsyncBulkFetcher(cn_fetcher, store, error_queue, concurrency=10)
        await fetcher.bulk_fetch(fund_codes)
    """

    def __init__(
        self,
        fetcher: BaseFetcher,
        store: DataStore,
        error_queue: ErrorQueue,
        concurrency: int = 10,
        batch_size: int = 50,
    ) -> None:
        self._fetcher = fetcher
        self._store = store
        self._error_queue = error_queue
        self._concurrency = concurrency
        self._batch_size = batch_size
        self._semaphore: asyncio.Semaphore | None = None
        # 显式设置线程池大小 >= concurrency，避免线程池成为瓶颈
        self._executor = ThreadPoolExecutor(max_workers=max(concurrency, 8))

    async def bulk_fetch(
        self,
        fund_codes: list[str],
        fetch_detail: bool = True,
    ) -> dict[str, int]:
        """
        批量抓取净值历史和基金详情。

        Args:
            fund_codes: 基金代码列表
            fetch_detail: 是否同时抓取基金详情

        Returns:
            {"success": N, "failed": M, "total": len(fund_codes)}
        """
        self._semaphore = asyncio.Semaphore(self._concurrency)
        success_count = 0
        fail_count = 0

        # 分批处理，每批之间随机 sleep
        for batch_start in range(0, len(fund_codes), self._batch_size):
            batch = fund_codes[batch_start:batch_start + self._batch_size]
            batch_num = batch_start // self._batch_size + 1
            total_batches = (len(fund_codes) + self._batch_size - 1) // self._batch_size

            logger.info(
                "批次 %d/%d: 处理 %d 只基金 (并发=%d)",
                batch_num, total_batches, len(batch), self._concurrency,
            )

            tasks = [
                self._fetch_single(code, fetch_detail)
                for code in batch
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for code, result in zip(batch, results):
                if isinstance(result, Exception):
                    fail_count += 1
                    self._error_queue.log_error(
                        code, type(result).__name__, str(result),
                    )
                elif result:
                    success_count += 1
                else:
                    fail_count += 1

            # 批次间随机 sleep（0.5~1.5s），模拟人类行为
            if batch_start + self._batch_size < len(fund_codes):
                sleep_sec = random.uniform(0.5, 1.5)
                logger.debug("批次间休眠 %.1f 秒", sleep_sec)
                await asyncio.sleep(sleep_sec)

        # 写盘错误日志
        self._error_queue.flush()

        stats = {
            "success": success_count,
            "failed": fail_count,
            "total": len(fund_codes),
        }
        logger.info(
            "批量抓取完成: 成功 %d / 失败 %d / 总计 %d",
            success_count, fail_count, len(fund_codes),
        )
        return stats

    async def _fetch_single(
        self,
        code: str,
        fetch_detail: bool,
    ) -> bool:
        """
        抓取单只基金的所有数据（受 Semaphore 控制并发）。

        Returns:
            True if 成功, False if 失败
        """
        assert self._semaphore is not None
        async with self._semaphore:
            try:
                # 抓取净值历史（同步调用包装为 async）
                nav_df = await asyncio.to_thread(
                    self._fetcher.fetch_nav_history, code, 150,
                )
                if not nav_df.empty:
                    await asyncio.to_thread(
                        self._store.persist_nav_records,
                        self._fetcher.market.value, code, nav_df,
                    )

                # 抓取基金详情
                if fetch_detail:
                    detail = await asyncio.to_thread(
                        self._fetcher.fetch_fund_detail, code,
                    )
                    if detail:
                        await asyncio.to_thread(
                            self._store.persist_fund_detail,
                            self._fetcher.market.value, code, detail,
                        )

                logger.debug("成功抓取 %s", code)
                return True

            except Exception as e:
                logger.warning("抓取 %s 失败: %s", code, e)
                self._error_queue.log_error(code, type(e).__name__, str(e))
                return False

    def shutdown(self) -> None:
        """关闭线程池。"""
        self._executor.shutdown(wait=False)
