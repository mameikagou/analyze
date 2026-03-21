"""
错误日志 + 重试队列 — 异步批量抓取的容错基石。

设计思路：
抓取几百只基金时，个别失败是常态（网络抖动、反爬封 IP 等）。
ErrorQueue 把失败记录持久化到 JSON 文件，下次启动时自动重试。
这样"失败"不会丢失，也不需要每次从头全量重跑。

存储格式：
    data/error_log.json
    [
        {"fund_code": "005827", "error_type": "timeout", "message": "...",
         "timestamp": "2026-03-21T10:30:00", "retry_count": 0, "resolved": false},
        ...
    ]
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("fund_screener.error_queue")


class ErrorQueue:
    """
    错误日志 + 重试队列。

    生命周期：
    1. 启动时 load() 加载上次残留的错误记录
    2. 抓取过程中 log_error() 记录新失败
    3. get_retry_queue() 返回需要重试的 fund_code 列表
    4. 重试成功后 mark_resolved() 移除
    5. 结束时 flush() 写盘
    """

    def __init__(self, log_path: str | Path = "data/error_log.json") -> None:
        self._log_path = Path(log_path)
        self._entries: list[dict[str, Any]] = []
        self.load()

    def load(self) -> None:
        """从 JSON 文件加载错误记录。文件不存在则初始化为空列表。"""
        if self._log_path.exists():
            try:
                text = self._log_path.read_text(encoding="utf-8")
                self._entries = json.loads(text) if text.strip() else []
                logger.debug("ErrorQueue: 加载了 %d 条错误记录", len(self._entries))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("ErrorQueue: 加载错误日志失败，重置为空: %s", e)
                self._entries = []
        else:
            self._entries = []

    def log_error(
        self,
        fund_code: str,
        error_type: str,
        message: str,
    ) -> None:
        """
        记录一个错误。

        如果同一个 fund_code 已有未解决的记录，更新其 retry_count 和 message，
        而不是重复追加（避免 error_log.json 无限膨胀）。
        """
        # 查找已有的未解决记录
        for entry in self._entries:
            if entry["fund_code"] == fund_code and not entry.get("resolved", False):
                entry["retry_count"] = entry.get("retry_count", 0) + 1
                entry["message"] = message
                entry["error_type"] = error_type
                entry["timestamp"] = datetime.now().isoformat(timespec="seconds")
                logger.debug(
                    "ErrorQueue: 更新错误记录 %s (retry_count=%d)",
                    fund_code, entry["retry_count"],
                )
                return

        # 新记录
        self._entries.append({
            "fund_code": fund_code,
            "error_type": error_type,
            "message": message,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "retry_count": 0,
            "resolved": False,
        })
        logger.debug("ErrorQueue: 新增错误记录 %s (%s)", fund_code, error_type)

    def get_retry_queue(self) -> list[str]:
        """返回所有未解决的 fund_code 列表（去重）。"""
        seen: set[str] = set()
        result: list[str] = []
        for entry in self._entries:
            code = entry["fund_code"]
            if not entry.get("resolved", False) and code not in seen:
                seen.add(code)
                result.append(code)
        return result

    def mark_resolved(self, fund_code: str) -> None:
        """将某个 fund_code 的所有未解决记录标记为已解决。"""
        for entry in self._entries:
            if entry["fund_code"] == fund_code and not entry.get("resolved", False):
                entry["resolved"] = True
        logger.debug("ErrorQueue: 标记 %s 为已解决", fund_code)

    def flush(self) -> None:
        """将当前状态写入 JSON 文件。只保留未解决的记录，已解决的清除。"""
        # 清除已解决的记录，防止文件无限增长
        self._entries = [
            e for e in self._entries if not e.get("resolved", False)
        ]

        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_path.write_text(
            json.dumps(self._entries, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.debug("ErrorQueue: 已写盘 %d 条未解决记录", len(self._entries))

    @property
    def entries(self) -> list[dict[str, Any]]:
        """只读访问内部记录列表（供测试和调试用）。"""
        return self._entries

    def __len__(self) -> int:
        """返回未解决的错误数量。"""
        return sum(1 for e in self._entries if not e.get("resolved", False))
