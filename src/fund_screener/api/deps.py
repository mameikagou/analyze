"""
依赖注入 — FastAPI Dependencies

提供 DataStore 实例、配置等共享依赖。
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Annotated

from fastapi import Depends, HTTPException, status

from fund_screener.storage import DataStore

logger = logging.getLogger("fund_screener.api")

# 默认 DB 路径，从环境变量或配置文件读取
DEFAULT_DB_PATH = Path(__file__).resolve().parents[3] / "data" / "fund_data.db"
DB_PATH = Path(os.getenv("FUND_DB_PATH", DEFAULT_DB_PATH))


def get_db():
    """
    获取 DataStore 实例。

    yield 模式：每个请求独立创建连接，请求结束后自动关闭。
    同步依赖会在线程池执行，但连接对象会被注入到 async 路由中，
    因此 DataStore._init_db 已设置 check_same_thread=False。
    """
    store = DataStore(DB_PATH)
    try:
        yield store
    except Exception as e:
        logger.error("数据库连接失败: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        ) from e
    finally:
        store.close()


def get_db_conn(store: Annotated[DataStore, Depends(get_db)]) -> "sqlite3.Connection":
    """暴露底层 sqlite3 连接给需要直接执行 SQL 的路由。"""
    return store.get_connection()
