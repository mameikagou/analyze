"""仪表盘统计路由。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from fund_screener.api import schemas
from fund_screener.api.deps import get_db_conn

router = APIRouter()


@router.get("/stats", response_model=schemas.APIResponse)
async def get_dashboard_stats(
    conn: Annotated["sqlite3.Connection", Depends(get_db_conn)],
) -> dict:
    """
    仪表盘统计 — 总基金数、今日通过 MA、平均分、数据湖记录数。
    """
    # 总基金数
    total_funds = conn.execute("SELECT COUNT(*) FROM funds").fetchone()[0]

    # 按市场分布
    cursor = conn.execute(
        "SELECT market, COUNT(*) FROM funds GROUP BY market ORDER BY market"
    )
    funds_by_market = {row[0]: row[1] for row in cursor.fetchall()}

    # 净值记录总数
    total_nav = conn.execute("SELECT COUNT(*) FROM nav_records").fetchone()[0]

    # 净值时间范围
    nav_range = conn.execute(
        "SELECT MIN(date), MAX(date) FROM nav_records"
    ).fetchone()

    # 最新筛选结果
    screening_row = conn.execute(
        """
        SELECT screening_date, COUNT(*)
        FROM screening_results
        GROUP BY screening_date
        ORDER BY screening_date DESC
        LIMIT 1
        """
    ).fetchone()

    # 最新筛选的平均 MA 差值
    avg_ma_diff = None
    if screening_row:
        avg_row = conn.execute(
            """
            SELECT AVG(ma_diff_pct)
            FROM screening_results
            WHERE screening_date = ?
            """,
            (screening_row[0],),
        ).fetchone()
        avg_ma_diff = round(avg_row[0], 2) if avg_row[0] else None

    # DB 文件大小
    db_size_mb = 0.0
    try:
        from fund_screener.api.deps import DB_PATH
        if DB_PATH.exists():
            db_size_mb = round(DB_PATH.stat().st_size / (1024 * 1024), 2)
    except Exception:
        pass

    return {
        "success": True,
        "data": {
            "total_funds": total_funds,
            "funds_by_market": funds_by_market,
            "total_nav_records": total_nav,
            "nav_date_range": (nav_range[0], nav_range[1]) if nav_range else (None, None),
            "latest_screening_date": screening_row[0] if screening_row else None,
            "latest_screening_count": screening_row[1] if screening_row else 0,
            "latest_screening_avg_ma_diff": avg_ma_diff,
            "db_size_mb": db_size_mb,
        },
    }
