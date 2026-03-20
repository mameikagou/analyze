"""
SQLite 数据湖 — 永久持久化层。

与 FileCache 并行运行，互不干扰：
- FileCache: 临时缓存，TTL 12 小时，做 API 限速保护
- DataStore: 永久存储，零过期，为量化分析积累全量数据

设计哲学：
1. 只用标准库 sqlite3，零额外依赖
2. 所有写入 try-except 包裹，失败只 warning 不中断主流程
3. WAL 模式 + NORMAL 同步，兼顾写入性能和数据安全
4. PRAGMA user_version 做 schema 版本管理，预留未来 migration 通道
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pandas as pd

    from fund_screener.models import FundInfo, Holding, SectorWeight

logger = logging.getLogger("fund_screener.storage")

# 当前 schema 版本号，未来 migration 时递增
_SCHEMA_VERSION = 1

# 建表 DDL — 每张表都有 UNIQUE 约束做幂等 UPSERT
_CREATE_TABLES_SQL = """
-- 基金维度表：一只基金一行，market+code 唯一
CREATE TABLE IF NOT EXISTS funds (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    market      TEXT    NOT NULL,
    code        TEXT    NOT NULL,
    name        TEXT    NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(market, code)
);

-- 净值时序数据：最大的表，fund_id+date 唯一
CREATE TABLE IF NOT EXISTS nav_records (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_id     INTEGER NOT NULL REFERENCES funds(id),
    date        TEXT    NOT NULL,
    nav         REAL    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(fund_id, date)
);

-- 持仓快照：fund_id+stock_code+snapshot_date 唯一
CREATE TABLE IF NOT EXISTS holdings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_id         INTEGER NOT NULL REFERENCES funds(id),
    stock_code      TEXT    NOT NULL,
    stock_name      TEXT    NOT NULL DEFAULT '',
    weight_pct      REAL,
    snapshot_date   TEXT    NOT NULL,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(fund_id, stock_code, snapshot_date)
);

-- 行业分布快照：fund_id+sector+snapshot_date 唯一
CREATE TABLE IF NOT EXISTS sector_exposure (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_id         INTEGER NOT NULL REFERENCES funds(id),
    sector          TEXT    NOT NULL,
    weight_pct      REAL    NOT NULL,
    snapshot_date   TEXT    NOT NULL,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(fund_id, sector, snapshot_date)
);

-- 筛选结果快照：fund_id+screening_date 唯一
CREATE TABLE IF NOT EXISTS screening_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_id         INTEGER NOT NULL REFERENCES funds(id),
    screening_date  TEXT    NOT NULL,
    nav             REAL    NOT NULL,
    ma_short        REAL    NOT NULL,
    ma_long         REAL    NOT NULL,
    ma_diff_pct     REAL    NOT NULL,
    daily_change_pct REAL,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(fund_id, screening_date)
);

-- 索引：加速按日期范围查询净值
CREATE INDEX IF NOT EXISTS idx_nav_records_date ON nav_records(fund_id, date);
CREATE INDEX IF NOT EXISTS idx_screening_date ON screening_results(screening_date);
"""


class DataStore:
    """
    SQLite 全量数据湖。

    用法（推荐 context manager）：
        with DataStore("./data/fund_data.db") as store:
            store.persist_fund_list("US", fund_list)
            store.persist_nav_records("US", "SPY", nav_df)

    所有 persist_* 方法内部捕获异常，保证不会中断主流程。
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        # 内存缓存：(market, code) -> fund_id，避免每次写 nav 前查 DB
        self._fund_id_cache: dict[tuple[str, str], int] = {}
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _init_db(self) -> None:
        """初始化数据库连接 + 建表 + 设置 PRAGMA。"""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")

        # Schema migration：用 user_version 做版本管理
        current_version = self._conn.execute("PRAGMA user_version").fetchone()[0]
        if current_version < _SCHEMA_VERSION:
            self._conn.executescript(_CREATE_TABLES_SQL)
            self._conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
            self._conn.commit()
            logger.debug("DataStore schema 初始化完成 (v%d)", _SCHEMA_VERSION)

    def close(self) -> None:
        """关闭数据库连接。"""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> DataStore:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        self.close()

    # ------------------------------------------------------------------
    # 内部工具方法
    # ------------------------------------------------------------------

    def _get_or_create_fund_id(self, market: str, code: str, name: str = "") -> int:
        """
        获取 fund_id，不存在则创建。结果缓存在内存中。

        为什么要缓存？因为 persist_nav_records 会对同一个 fund 写几百条记录，
        如果每条都 SELECT 一次，性能会很差。内存缓存让第二次起的查询零 IO。
        """
        cache_key = (market, code)
        if cache_key in self._fund_id_cache:
            return self._fund_id_cache[cache_key]

        assert self._conn is not None
        cursor = self._conn.execute(
            "SELECT id FROM funds WHERE market = ? AND code = ?",
            (market, code),
        )
        row = cursor.fetchone()

        if row is not None:
            fund_id = row[0]
        else:
            cursor = self._conn.execute(
                "INSERT INTO funds (market, code, name) VALUES (?, ?, ?)",
                (market, code, name),
            )
            fund_id = cursor.lastrowid
            assert fund_id is not None
            self._conn.commit()

        self._fund_id_cache[cache_key] = fund_id
        return fund_id

    @staticmethod
    def _normalize_date(d: Any) -> str:
        """
        把各种日期格式统一转成 'YYYY-MM-DD' 字符串。

        为什么需要这个？因为 pandas 的 date 列可能是 datetime64、date、str 三种类型，
        如果不统一，UNIQUE 约束会因为类型不同认为是不同记录，导致重复插入。
        """
        if isinstance(d, str):
            return d[:10]  # 截断可能的时间部分
        if isinstance(d, datetime):
            return d.strftime("%Y-%m-%d")
        if isinstance(d, date):
            return d.isoformat()
        # pandas Timestamp 等其他类型
        return str(d)[:10]

    # ------------------------------------------------------------------
    # 公开 API：persist_* 系列方法
    # ------------------------------------------------------------------

    def persist_fund_list(
        self,
        market: str,
        fund_list: list[dict[str, str]],
    ) -> None:
        """
        批量 UPSERT 基金维度表。

        fund_list 格式：[{"code": "SPY", "name": "SPDR S&P 500"}, ...]
        """
        try:
            assert self._conn is not None
            self._conn.executemany(
                """
                INSERT INTO funds (market, code, name)
                VALUES (?, ?, ?)
                ON CONFLICT(market, code)
                DO UPDATE SET name = excluded.name, updated_at = datetime('now')
                """,
                [
                    (market, f["code"], f.get("name", ""))
                    for f in fund_list
                ],
            )
            self._conn.commit()
            # 预热缓存：批量查出所有 fund_id
            cursor = self._conn.execute(
                "SELECT id, market, code FROM funds WHERE market = ?",
                (market,),
            )
            for row in cursor:
                self._fund_id_cache[(row[1], row[2])] = row[0]

            logger.debug("DataStore: 已持久化 %d 只 %s 基金", len(fund_list), market)
        except Exception:
            logger.warning("DataStore: persist_fund_list 失败", exc_info=True)

    def persist_nav_records(
        self,
        market: str,
        code: str,
        nav_df: pd.DataFrame,
    ) -> None:
        """
        批量 UPSERT 净值时序数据。

        nav_df 必须包含 'date' 和 'nav' 两列。
        同一 fund+date 的记录会被更新（ON CONFLICT DO UPDATE）。
        """
        try:
            if nav_df.empty:
                return

            assert self._conn is not None
            fund_id = self._get_or_create_fund_id(market, code)

            records = [
                (fund_id, self._normalize_date(row["date"]), float(row["nav"]))
                for _, row in nav_df.iterrows()
            ]

            self._conn.executemany(
                """
                INSERT INTO nav_records (fund_id, date, nav)
                VALUES (?, ?, ?)
                ON CONFLICT(fund_id, date)
                DO UPDATE SET nav = excluded.nav
                """,
                records,
            )
            self._conn.commit()
            logger.debug(
                "DataStore: 已持久化 %s:%s 的 %d 条净值记录",
                market, code, len(records),
            )
        except Exception:
            logger.warning(
                "DataStore: persist_nav_records(%s:%s) 失败",
                market, code,
                exc_info=True,
            )

    def persist_holdings(
        self,
        market: str,
        code: str,
        holdings: list[Holding],
        sectors: list[SectorWeight],
        snapshot_date: str | None = None,
    ) -> None:
        """
        持仓 + 行业分布一起存，共享同一个 snapshot_date。

        snapshot_date 默认用当天日期。
        """
        try:
            assert self._conn is not None
            fund_id = self._get_or_create_fund_id(market, code)
            snap = snapshot_date or date.today().isoformat()

            if holdings:
                self._conn.executemany(
                    """
                    INSERT INTO holdings (fund_id, stock_code, stock_name, weight_pct, snapshot_date)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(fund_id, stock_code, snapshot_date)
                    DO UPDATE SET stock_name = excluded.stock_name,
                                  weight_pct = excluded.weight_pct
                    """,
                    [
                        (fund_id, h.stock_code, h.stock_name, h.weight_pct, snap)
                        for h in holdings
                    ],
                )

            if sectors:
                self._conn.executemany(
                    """
                    INSERT INTO sector_exposure (fund_id, sector, weight_pct, snapshot_date)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(fund_id, sector, snapshot_date)
                    DO UPDATE SET weight_pct = excluded.weight_pct
                    """,
                    [
                        (fund_id, s.sector, s.weight_pct, snap)
                        for s in sectors
                    ],
                )

            self._conn.commit()
            logger.debug(
                "DataStore: 已持久化 %s:%s 的 %d 条持仓 + %d 条行业",
                market, code, len(holdings), len(sectors),
            )
        except Exception:
            logger.warning(
                "DataStore: persist_holdings(%s:%s) 失败",
                market, code,
                exc_info=True,
            )

    def persist_screening_result(self, fund: FundInfo) -> None:
        """
        存筛选结果快照。

        每只通过筛选的基金，按 (fund_id, screening_date) 做幂等写入。
        同一天多次跑筛选，只保留最后一次的结果。
        """
        try:
            assert self._conn is not None
            fund_id = self._get_or_create_fund_id(
                fund.market.value, fund.code, fund.name,
            )
            screening_date = date.today().isoformat()

            self._conn.execute(
                """
                INSERT INTO screening_results
                    (fund_id, screening_date, nav, ma_short, ma_long, ma_diff_pct, daily_change_pct)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(fund_id, screening_date)
                DO UPDATE SET nav = excluded.nav,
                              ma_short = excluded.ma_short,
                              ma_long = excluded.ma_long,
                              ma_diff_pct = excluded.ma_diff_pct,
                              daily_change_pct = excluded.daily_change_pct
                """,
                (
                    fund_id,
                    screening_date,
                    fund.nav,
                    fund.ma_short,
                    fund.ma_long,
                    fund.ma_diff_pct,
                    fund.daily_change_pct,
                ),
            )
            self._conn.commit()
            logger.debug(
                "DataStore: 已持久化筛选结果 %s:%s",
                fund.market.value, fund.code,
            )
        except Exception:
            logger.warning(
                "DataStore: persist_screening_result(%s) 失败",
                fund.code,
                exc_info=True,
            )

    # ------------------------------------------------------------------
    # 查询 API：数据湖统计
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """
        查询数据湖的全貌统计信息。

        Returns:
            包含各表记录数、市场维度统计、时间范围等信息的字典。
        """
        assert self._conn is not None
        stats: dict[str, Any] = {}

        # 1. 各表总记录数
        for table in ("funds", "nav_records", "holdings", "sector_exposure", "screening_results"):
            count = self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608
            stats[f"{table}_count"] = count

        # 2. 按市场维度的基金数
        cursor = self._conn.execute(
            "SELECT market, COUNT(*) FROM funds GROUP BY market ORDER BY market",
        )
        stats["funds_by_market"] = {row[0]: row[1] for row in cursor.fetchall()}

        # 3. 按市场维度的净值记录数
        cursor = self._conn.execute(
            """
            SELECT f.market, COUNT(*)
            FROM nav_records n JOIN funds f ON n.fund_id = f.id
            GROUP BY f.market ORDER BY f.market
            """,
        )
        stats["nav_by_market"] = {row[0]: row[1] for row in cursor.fetchall()}

        # 4. 净值数据时间范围
        cursor = self._conn.execute(
            "SELECT MIN(date), MAX(date) FROM nav_records",
        )
        row = cursor.fetchone()
        stats["nav_date_range"] = (row[0], row[1]) if row[0] else (None, None)

        # 5. 最近的筛选日期和数量
        cursor = self._conn.execute(
            """
            SELECT screening_date, COUNT(*)
            FROM screening_results
            GROUP BY screening_date
            ORDER BY screening_date DESC
            LIMIT 5
            """,
        )
        stats["recent_screenings"] = [
            {"date": row[0], "count": row[1]} for row in cursor.fetchall()
        ]

        # 6. DB 文件大小
        if self._db_path.exists():
            size_bytes = self._db_path.stat().st_size
            stats["db_size_mb"] = round(size_bytes / (1024 * 1024), 2)

        return stats
