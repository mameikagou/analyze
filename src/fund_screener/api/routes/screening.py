"""筛选结果路由。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from fund_screener.api import schemas
from fund_screener.api.deps import get_db_conn

router = APIRouter()


@router.get("/screening", response_model=schemas.APIResponse)
async def get_screening_results(
    conn: Annotated["sqlite3.Connection", Depends(get_db_conn)],
    date: str | None = Query(None, description="筛选日期 YYYY-MM-DD，默认最新"),
    market: str | None = Query(None, description="市场筛选: CN/US/HK"),
    min_ma_diff: float | None = Query(None, description="最小 MA 差值 %"),
    limit: int = Query(50, ge=1, le=200, description="返回数量上限"),
) -> dict:
    """获取 MA 筛选结果 — 按日期返回通过 MA 均线筛选的基金列表。"""
    if date:
        screening_date = date
    else:
        row = conn.execute(
            "SELECT MAX(screening_date) FROM screening_results"
        ).fetchone()
        screening_date = row[0] if row[0] else None

    if not screening_date:
        return {"success": True, "data": [], "error": "No screening data available"}

    where_clauses = ["s.screening_date = ?"]
    params = [screening_date]

    if market:
        where_clauses.append("f.market = ?")
        params.append(market.upper())

    if min_ma_diff is not None:
        where_clauses.append("s.ma_diff_pct >= ?")
        params.append(min_ma_diff)

    where_sql = " AND ".join(where_clauses)

    cursor = conn.execute(
        f"""
        SELECT
            f.code, f.name, f.market,
            s.nav, s.ma_short, s.ma_long, s.ma_diff_pct,
            s.daily_change_pct, s.purchase_status, s.purchase_limit,
            s.screening_date
        FROM screening_results s
        JOIN funds f ON s.fund_id = f.id
        WHERE {where_sql}
        ORDER BY s.ma_diff_pct DESC
        LIMIT ?
        """,
        params + [limit],
    )

    rows = cursor.fetchall()
    results = [
        schemas.ScreeningResult(
            code=r[0], name=r[1], market=r[2],
            nav=r[3], ma_short=r[4], ma_long=r[5], ma_diff_pct=r[6],
            daily_change_pct=r[7], purchase_status=r[8],
            purchase_limit=r[9], screening_date=r[10],
        ).model_dump()
        for r in rows
    ]

    return {
        "success": True,
        "data": {
            "screening_date": screening_date,
            "count": len(results),
            "results": results,
        },
    }
