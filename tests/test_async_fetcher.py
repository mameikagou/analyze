"""AsyncBulkFetcher 单元测试。"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from fund_screener.async_fetcher import AsyncBulkFetcher
from fund_screener.error_queue import ErrorQueue
from fund_screener.models import Market
from fund_screener.storage import DataStore


@pytest.fixture()
def mock_fetcher() -> MagicMock:
    """Mock fetcher，模拟正常返回。"""
    fetcher = MagicMock()
    fetcher.market = Market.CN
    fetcher.fetch_nav_history.return_value = pd.DataFrame({
        "date": ["2026-03-20"],
        "nav": [2.5],
    })
    fetcher.fetch_fund_detail.return_value = {"manager_name": "测试经理"}
    return fetcher


@pytest.fixture()
def store(tmp_path: object) -> DataStore:
    db_path = tmp_path / "async_test.db"  # type: ignore[operator]
    s = DataStore(str(db_path))
    yield s  # type: ignore[misc]
    s.close()


@pytest.fixture()
def error_queue(tmp_path: object) -> ErrorQueue:
    log_path = tmp_path / "error_log.json"  # type: ignore[operator]
    return ErrorQueue(log_path=str(log_path))


class TestAsyncBulkFetcher:
    """异步批量抓取测试。"""

    def test_successful_fetch(
        self, mock_fetcher: MagicMock, store: DataStore, error_queue: ErrorQueue,
    ) -> None:
        """正常抓取流程。"""
        bulk = AsyncBulkFetcher(
            fetcher=mock_fetcher, store=store, error_queue=error_queue,
            concurrency=2, batch_size=5,
        )
        stats = asyncio.run(bulk.bulk_fetch(["005827", "016873"]))
        bulk.shutdown()

        assert stats["success"] == 2
        assert stats["failed"] == 0
        assert stats["total"] == 2

    def test_failed_fetch_enters_error_queue(
        self, store: DataStore, error_queue: ErrorQueue,
    ) -> None:
        """抓取失败 → 自动入 ErrorQueue。"""
        fetcher = MagicMock()
        fetcher.market = Market.CN
        fetcher.fetch_nav_history.side_effect = ConnectionError("timeout")

        bulk = AsyncBulkFetcher(
            fetcher=fetcher, store=store, error_queue=error_queue,
            concurrency=2, batch_size=5,
        )
        stats = asyncio.run(bulk.bulk_fetch(["005827"]))
        bulk.shutdown()

        assert stats["failed"] == 1
        assert len(error_queue) == 1
        assert error_queue.get_retry_queue() == ["005827"]

    def test_concurrency_limit(
        self, mock_fetcher: MagicMock, store: DataStore, error_queue: ErrorQueue,
    ) -> None:
        """并发数不应超过 Semaphore 设定。"""
        import threading
        import time

        max_concurrent = 0
        current_concurrent = 0
        lock = threading.Lock()

        nav_result = pd.DataFrame({"date": ["2026-03-20"], "nav": [2.5]})

        def tracked_fetch(*args: object, **kwargs: object) -> pd.DataFrame:
            nonlocal max_concurrent, current_concurrent
            with lock:
                current_concurrent += 1
                if current_concurrent > max_concurrent:
                    max_concurrent = current_concurrent
            # 模拟网络延迟，让并发可观察
            time.sleep(0.05)
            with lock:
                current_concurrent -= 1
            return nav_result

        mock_fetcher.fetch_nav_history.side_effect = tracked_fetch
        mock_fetcher.fetch_fund_detail.return_value = {}

        bulk = AsyncBulkFetcher(
            fetcher=mock_fetcher, store=store, error_queue=error_queue,
            concurrency=3, batch_size=10,
        )
        asyncio.run(bulk.bulk_fetch([f"fund_{i}" for i in range(10)], fetch_detail=False))
        bulk.shutdown()

        # 由于 asyncio.to_thread + Semaphore，实际并发不应超过 concurrency
        assert max_concurrent <= 3
