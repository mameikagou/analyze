"""
本地文件缓存模块。

基于 JSON 文件 + TTL 的轻量级缓存，避免重复请求数据源被限速/封 IP。
缓存目录结构：.cache/{market}/{fund_code}_{data_type}.json

每个缓存文件格式：
{
    "timestamp": "2026-03-20T15:00:00",
    "ttl_hours": 12,
    "data": <实际缓存数据>
}
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class FileCache:
    """
    基于本地 JSON 文件的简单缓存。

    设计决策：不引入 Redis/SQLite 依赖，用文件系统就够了。
    每个缓存 key 对应一个 JSON 文件，读取时检查 TTL 是否过期。
    """

    def __init__(self, cache_dir: str | Path, default_ttl_hours: int = 12) -> None:
        self._cache_dir = Path(cache_dir)
        self._default_ttl_hours = default_ttl_hours
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _key_to_path(self, key: str) -> Path:
        """
        将缓存 key 转换为文件路径。

        key 格式约定："{market}/{fund_code}_{data_type}"
        例如："CN/005827_nav_history" -> .cache/CN/005827_nav_history.json
        """
        # 清理 key 中的非法文件名字符
        safe_key = key.replace(":", "_").replace("?", "_").replace("&", "_")
        return self._cache_dir / f"{safe_key}.json"

    def get(self, key: str) -> Any | None:
        """
        获取缓存数据。如果缓存不存在或已过期，返回 None。

        Args:
            key: 缓存键

        Returns:
            缓存的数据，或 None（未命中/过期）
        """
        path = self._key_to_path(key)
        if not path.exists():
            return None

        try:
            with open(path, encoding="utf-8") as f:
                cached = json.load(f)

            timestamp = datetime.fromisoformat(cached["timestamp"])
            ttl_hours = cached.get("ttl_hours", self._default_ttl_hours)

            if datetime.now() - timestamp > timedelta(hours=ttl_hours):
                logger.debug("缓存已过期: %s", key)
                return None

            logger.debug("缓存命中: %s", key)
            return cached["data"]
        except (json.JSONDecodeError, KeyError, ValueError):
            logger.warning("缓存文件损坏，将忽略: %s", path)
            return None

    def set(self, key: str, data: Any, ttl_hours: int | None = None) -> None:
        """
        写入缓存。

        Args:
            key: 缓存键
            data: 要缓存的数据（必须可 JSON 序列化）
            ttl_hours: 自定义 TTL，不传则用默认值
        """
        path = self._key_to_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)

        cache_entry = {
            "timestamp": datetime.now().isoformat(),
            "ttl_hours": ttl_hours or self._default_ttl_hours,
            "data": data,
        }

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cache_entry, f, ensure_ascii=False, default=str)
            logger.debug("缓存已写入: %s", key)
        except (TypeError, OSError) as e:
            logger.warning("缓存写入失败: %s, 原因: %s", key, e)

    def invalidate(self, key: str) -> None:
        """删除指定缓存。"""
        path = self._key_to_path(key)
        if path.exists():
            path.unlink()
            logger.debug("缓存已删除: %s", key)
