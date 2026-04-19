"""基金相关路由。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from fund_screener.api import schemas
from fund_screener.api.deps import get_db_conn
from fund_screener.api.schemas import PaginatedResponse

router = APIRouter()


@router.get("/funds", response_model=PaginatedResponse)
async def list_funds(
    conn: Annotated["sqlite3.Connection", Depends(get_db_conn)],
    market: str | None = Query(None, description="筛选市场: CN/US/HK"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    sort_by: str = Query("code", description="排序字段: code/name/market"),
    sort_order: str = Query("asc", description="排序方向: asc/desc"),
) -> dict:
    """基金列表 — 支持分页、市场筛选、排序。"""
    where_clauses = []
    params = []
    if market:
        where_clauses.append("market = ?")
        params.append(market.upper())

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    allowed_sort = {"code", "name", "market", "created_at"}
    sort_col = sort_by if sort_by in allowed_sort else "code"
    sort_dir = "DESC" if sort_order.lower() == "desc" else "ASC"

    count_sql = f"SELECT COUNT(*) FROM funds {where_sql}"
    total = conn.execute(count_sql, params).fetchone()[0]

    offset = (page - 1) * page_size
    query_sql = f"""
        SELECT code, name, market
        FROM funds
        {where_sql}
        ORDER BY {sort_col} {sort_dir}
        LIMIT ? OFFSET ?
    """
    cursor = conn.execute(query_sql, params + [page_size, offset])
    rows = cursor.fetchall()

    items = [
        schemas.FundSummary(code=r[0], name=r[1], market=r[2]).model_dump()
        for r in rows
    ]

    return {
        "success": True,
        "data": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/funds/{code}", response_model=schemas.APIResponse)
async def get_fund_detail(
    code: str,
    conn: Annotated["sqlite3.Connection", Depends(get_db_conn)],
) -> dict:
    """单只基金详情 — 基本信息 + 最新持仓 + 最新净值。"""
    row = conn.execute(
        """
        SELECT code, name, market, establish_date, manager_name, fund_scale, track_benchmark
        FROM funds WHERE code = ?
        """,
        (code,),
    ).fetchone()

    if not row:
        return {"success": False, "data": None, "error": f"Fund {code} not found"}

    fund = schemas.FundDetail(
        code=row[0], name=row[1], market=row[2],
        establish_date=row[3], manager_name=row[4],
        fund_scale=row[5], track_benchmark=row[6],
    )

    holdings_cursor = conn.execute(
        """
        SELECT h.stock_code, h.stock_name, h.weight_pct
        FROM holdings h
        JOIN funds f ON h.fund_id = f.id
        WHERE f.code = ?
        ORDER BY h.snapshot_date DESC, h.weight_pct DESC
        LIMIT 10
        """,
        (code,),
    )
    holdings = [
        {"stock_code": r[0], "stock_name": r[1], "weight_pct": r[2]}
        for r in holdings_cursor.fetchall()
    ]

    nav_row = conn.execute(
        """
        SELECT date, nav, adj_nav
        FROM nav_records n
        JOIN funds f ON n.fund_id = f.id
        WHERE f.code = ?
        ORDER BY date DESC
        LIMIT 1
        """,
        (code,),
    ).fetchone()
    latest_nav = {
        "date": nav_row[0], "nav": nav_row[1], "adj_nav": nav_row[2],
    } if nav_row else None

    return {
        "success": True,
        "data": {
            **fund.model_dump(),
            "holdings": holdings,
            "latest_nav": latest_nav,
        },
    }
