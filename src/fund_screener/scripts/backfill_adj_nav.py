"""adj_nav historical backfill script.

adj_nav 历史回填脚本 —— 为已有净值记录补充复权净值。

设计意图（修改前必须输出）：
为什么 adj_nav 回填要独立成一个脚本，而不是在回测引擎里自动做？

1. 回填是"一次性数据修复"，回测是"反复执行的计算"。混在一起会让回测引擎
   承担不该有的 I/O 职责（ARCHITECTURE.md 原则三）。
2. 回填需要调外部 API（tushare/akshare），有速率限制，可能持续几天。
   回测引擎不应该被这种长时任务阻塞。
3. 回填完成后，adj_nav 列就有值了，后续回测直接读就行，不需要每次都回填。

执行策略：
1. 找出 nav_records 中 adj_nav 为 NULL 的基金
2. 创建 backfill_log 表记录已完成 fund_id（支持断点续传）
3. 逐基金拉取历史复权净值，UPDATE nav_records
4. 每基金 commit + sleep(0.5) 限速
5. 失败时 rollback + log，继续下一只

用法:
    uv run python -m fund_screener.scripts.backfill_adj_nav
    uv run python -m fund_screener.scripts.backfill_adj_nav --db-path data/fund_data.db

对应 BACKTEST_DESIGN.md §10
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path

import pandas as pd

from fund_screener.config import load_config
from fund_screener.fetchers.cn_composite import CompositeCNFetcher


# ---------------------------------------------------------------------------
# 数据库操作
# ---------------------------------------------------------------------------


def create_backfill_log_table(conn: sqlite3.Connection) -> None:
    """Create backfill_log table if not exists."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS backfill_log (
            fund_id INTEGER PRIMARY KEY,
            completed_at TEXT DEFAULT (datetime('now')),
            records_updated INTEGER
        )
    """)
    conn.commit()


def get_funds_to_backfill(conn: sqlite3.Connection) -> list[tuple[int, str, str, str]]:
    """Get list of funds that need adj_nav backfill.

    Returns:
        List of (fund_id, market, code, name) tuples.
    """
    cursor = conn.execute("""
        SELECT DISTINCT f.id, f.market, f.code, f.name
        FROM funds f
        JOIN nav_records nr ON f.id = nr.fund_id
        WHERE nr.adj_nav IS NULL
        ORDER BY f.id
    """)
    return cursor.fetchall()


def is_fund_backfilled(conn: sqlite3.Connection, fund_id: int) -> bool:
    """Check if fund has already been backfilled."""
    row = conn.execute(
        "SELECT 1 FROM backfill_log WHERE fund_id = ?",
        (fund_id,),
    ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# 单基金回填
# ---------------------------------------------------------------------------


def backfill_fund(
    conn: sqlite3.Connection,
    fetcher: CompositeCNFetcher,
    fund_id: int,
    code: str,
    name: str,
) -> int:
    """Backfill adj_nav for a single fund.

    Args:
        conn: SQLite connection
        fetcher: CompositeCNFetcher instance
        fund_id: Fund ID in database
        code: Fund code
        name: Fund name

    Returns:
        Number of records updated.

    事务策略：
    - 成功：commit（持久化 UPDATE + backfill_log INSERT）
    - 失败：rollback（不污染数据库状态）
    """
    try:
        nav_df = fetcher.fetch_nav_history(code, lookback_days=9999)
        if nav_df is None or nav_df.empty:
            print(f"  跳过 {code}: 无数据")
            return 0

        updated = 0
        for _, row in nav_df.iterrows():
            adj_nav = row.get("adj_nav")
            if adj_nav is not None and pd.notna(adj_nav):
                conn.execute(
                    "UPDATE nav_records SET adj_nav = ? WHERE fund_id = ? AND date = ?",
                    (float(adj_nav), fund_id, row["date"]),
                )
                updated += 1

        conn.execute(
            "INSERT INTO backfill_log (fund_id, records_updated) VALUES (?, ?)",
            (fund_id, updated),
        )
        conn.commit()
        return updated

    except Exception as e:
        print(f"  失败 {code}: {e}")
        conn.rollback()
        return 0


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------


def backfill_adj_nav(db_path: str, batch_size: int = 50) -> None:
    """Main backfill entry point.

    Args:
        db_path: Path to SQLite database
        batch_size: Not used (reserved for future batching optimization)
    """
    conn = sqlite3.connect(db_path)
    create_backfill_log_table(conn)

    funds = get_funds_to_backfill(conn)
    if not funds:
        print("所有记录的 adj_nav 已填充，无需回填。")
        conn.close()
        return

    print(f"需要回填 {len(funds)} 只基金的 adj_nav")
    print(f"数据库: {db_path}")

    config = load_config()
    fetcher = CompositeCNFetcher(config)

    completed = 0
    skipped = 0
    failed = 0

    for fund_id, market, code, name in funds:
        if is_fund_backfilled(conn, fund_id):
            skipped += 1
            continue

        print(f"[{completed + 1}/{len(funds)}] 回填: {code} {name}")
        updated = backfill_fund(conn, fetcher, fund_id, code, name)

        if updated > 0:
            completed += 1
            print(f"  完成: 更新 {updated} 条记录")
        elif updated == 0:
            failed += 1

        time.sleep(0.5)  # Rate limiting — 礼貌限速，防止被封 IP

    conn.close()

    print()
    print("=" * 55)
    print(f"回填完成: 成功 {completed}, 跳过 {skipped}, 失败 {failed}")
    print("=" * 55)


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="adj_nav 历史回填脚本")
    parser.add_argument(
        "--db-path",
        default="data/fund_data.db",
        help="数据库路径",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="批次大小（预留，当前未使用）",
    )
    args = parser.parse_args()

    if not Path(args.db_path).exists():
        print(f"错误: 数据库不存在: {args.db_path}")
        sys.exit(1)

    backfill_adj_nav(args.db_path, args.batch_size)


if __name__ == "__main__":
    main()
