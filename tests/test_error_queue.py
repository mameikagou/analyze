"""ErrorQueue 单元测试 — 全生命周期验证。"""

from __future__ import annotations

import json

import pytest

from fund_screener.error_queue import ErrorQueue


@pytest.fixture()
def error_queue(tmp_path: object) -> ErrorQueue:
    """创建一个临时 ErrorQueue 实例。"""
    log_path = tmp_path / "error_log.json"  # type: ignore[operator]
    return ErrorQueue(log_path=str(log_path))


class TestErrorQueueLifecycle:
    """ErrorQueue 全生命周期：写入 → 读取 → 重试 → 解决 → flush。"""

    def test_log_error_creates_entry(self, error_queue: ErrorQueue) -> None:
        error_queue.log_error("005827", "timeout", "Connection timed out")
        assert len(error_queue) == 1
        assert error_queue.entries[0]["fund_code"] == "005827"
        assert error_queue.entries[0]["error_type"] == "timeout"
        assert error_queue.entries[0]["retry_count"] == 0

    def test_duplicate_error_increments_retry_count(self, error_queue: ErrorQueue) -> None:
        """同一个 fund_code 重复报错，应更新而非追加。"""
        error_queue.log_error("005827", "timeout", "first error")
        error_queue.log_error("005827", "timeout", "second error")

        # 只有一条记录
        assert len(error_queue) == 1
        assert error_queue.entries[0]["retry_count"] == 1
        assert error_queue.entries[0]["message"] == "second error"

    def test_get_retry_queue(self, error_queue: ErrorQueue) -> None:
        error_queue.log_error("005827", "timeout", "err1")
        error_queue.log_error("016873", "http_500", "err2")

        retry = error_queue.get_retry_queue()
        assert set(retry) == {"005827", "016873"}

    def test_mark_resolved_removes_from_retry(self, error_queue: ErrorQueue) -> None:
        error_queue.log_error("005827", "timeout", "err1")
        error_queue.log_error("016873", "http_500", "err2")

        error_queue.mark_resolved("005827")

        retry = error_queue.get_retry_queue()
        assert retry == ["016873"]
        assert len(error_queue) == 1

    def test_flush_writes_to_disk(self, error_queue: ErrorQueue) -> None:
        error_queue.log_error("005827", "timeout", "err1")
        error_queue.flush()

        # 读取文件验证
        with open(error_queue._log_path, encoding="utf-8") as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["fund_code"] == "005827"

    def test_flush_removes_resolved_entries(self, error_queue: ErrorQueue) -> None:
        """flush 时应清除已解决的记录。"""
        error_queue.log_error("005827", "timeout", "err1")
        error_queue.log_error("016873", "http_500", "err2")
        error_queue.mark_resolved("005827")
        error_queue.flush()

        with open(error_queue._log_path, encoding="utf-8") as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["fund_code"] == "016873"

    def test_load_from_existing_file(self, error_queue: ErrorQueue) -> None:
        """写入后创建新实例，应能加载之前的记录。"""
        error_queue.log_error("005827", "timeout", "err1")
        error_queue.flush()

        # 创建新实例加载同一文件
        eq2 = ErrorQueue(log_path=str(error_queue._log_path))
        assert len(eq2) == 1
        assert eq2.get_retry_queue() == ["005827"]

    def test_empty_queue_on_fresh_start(self, error_queue: ErrorQueue) -> None:
        """新文件时队列应为空。"""
        assert len(error_queue) == 0
        assert error_queue.get_retry_queue() == []
