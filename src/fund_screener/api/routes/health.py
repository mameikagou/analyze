"""健康检查路由。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from fund_screener.api import schemas
from fund_screener.api.deps import get_db
from fund_screener.storage import DataStore

router = APIRouter()


@router.get("/health", response_model=schemas.APIResponse)
async def health_check(
    store: Annotated[DataStore, Depends(get_db)],
) -> dict:
    """健康检查 — 验证数据库连接和 schema 版本。"""
    try:
        conn = store.get_connection()
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        return {
            "success": True,
            "data": schemas.HealthCheck(
                status="ok",
                db_connected=True,
                db_version=version,
            ).model_dump(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Health check failed: {e}",
        ) from e
