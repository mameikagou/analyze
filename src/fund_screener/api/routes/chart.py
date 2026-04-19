"""图表数据路由 — 净值历史时序。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from fund_screener.api import schemas
from fund_screener.api.deps import get_db_conn

router = APIRouter()


@router.get("/chart/{code}", response_model=schemas.APIResponse)
async def get_chart_data(
    code: str,
    conn: Annotated["sqlite3.Connection", Depends(get_db_conn)],
    days: int = Query(90, ge=7, le=730, description="拉取天数"),
) -> dict:
    """获取单只基金的净值历史时序数据 — 供 TV Charts 使用。"""
    cursor = conn.execute(
        """
        SELECT n.date, n.nav, n.adj_nav
        FROM nav_records n
        JOIN funds f ON n.fund_id = f.id
        WHERE f.code = ?
        ORDER BY n.date DESC
        LIMIT ?
        """,
        (code, days),
    )

    rows = cursor.fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail=f"No NAV data found for {code}")

    rows.reverse()

    data = [
        schemas.ChartDataPoint(
            time=r[0],
            value=round(r[1], 4),
            adj_value=round(r[2], 4) if r[2] is not None else None,
        ).model_dump()
        for r in rows
    ]

    return {
        "success": True,
        "data": {
            "code": code,
            "points": len(data),
            "history": data,
        },
    }
