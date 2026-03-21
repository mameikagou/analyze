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

import pandas as pd

if TYPE_CHECKING:
    from fund_screener.models import FundInfo, Holding, SectorWeight

logger = logging.getLogger("fund_screener.storage")

# 当前 schema 版本号，v3 新增申购限额字段
_SCHEMA_VERSION = 3

# ---------------------------------------------------------------------------
# V1 建表 DDL（保留给测试构造 v1 DB 用）
# ---------------------------------------------------------------------------
_CREATE_TABLES_SQL_V1 = """
CREATE TABLE IF NOT EXISTS funds (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    market      TEXT    NOT NULL,
    code        TEXT    NOT NULL,
    name        TEXT    NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(market, code)
);
CREATE TABLE IF NOT EXISTS nav_records (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_id     INTEGER NOT NULL REFERENCES funds(id),
    date        TEXT    NOT NULL,
    nav         REAL    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(fund_id, date)
);
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
CREATE TABLE IF NOT EXISTS sector_exposure (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_id         INTEGER NOT NULL REFERENCES funds(id),
    sector          TEXT    NOT NULL,
    weight_pct      REAL    NOT NULL,
    snapshot_date   TEXT    NOT NULL,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(fund_id, sector, snapshot_date)
);
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
CREATE INDEX IF NOT EXISTS idx_nav_records_date ON nav_records(fund_id, date);
CREATE INDEX IF NOT EXISTS idx_screening_date ON screening_results(screening_date);
"""

# ---------------------------------------------------------------------------
# V1 → V2 迁移脚本
#
# 设计决策：用 ALTER TABLE 而非新建表，保持外键关系和现有代码兼容。
# 注意：SQLite ALTER TABLE 新列必须允许 NULL 或有 DEFAULT 值。
# ---------------------------------------------------------------------------
_MIGRATION_V1_TO_V2 = """
-- funds 表：增加基金详情字段（成立日期、基金经理、规模、跟踪基准）
ALTER TABLE funds ADD COLUMN establish_date TEXT;
ALTER TABLE funds ADD COLUMN manager_name   TEXT;
ALTER TABLE funds ADD COLUMN fund_scale     REAL;
ALTER TABLE funds ADD COLUMN track_benchmark TEXT;

-- nav_records 表：增加复权净值字段（旧数据 NULL，COALESCE 兜底）
ALTER TABLE nav_records ADD COLUMN unit_nav       REAL;
ALTER TABLE nav_records ADD COLUMN cumulative_nav REAL;
ALTER TABLE nav_records ADD COLUMN adj_nav        REAL;

-- holdings 表：增加持股数量字段
ALTER TABLE holdings ADD COLUMN hold_shares REAL;

-- 新建申万行业映射表
CREATE TABLE IF NOT EXISTS stock_sector_mapping (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code    TEXT    NOT NULL UNIQUE,
    stock_name    TEXT    NOT NULL DEFAULT '',
    sw_sector_l1  TEXT    NOT NULL,
    is_hard_tech  INTEGER NOT NULL DEFAULT 0,
    is_resource   INTEGER NOT NULL DEFAULT 0,
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- 分析查询索引：加速 OLAP 函数
CREATE INDEX IF NOT EXISTS idx_holdings_stock ON holdings(stock_code);
CREATE INDEX IF NOT EXISTS idx_sector_mapping_l1 ON stock_sector_mapping(sw_sector_l1);
CREATE INDEX IF NOT EXISTS idx_nav_adj ON nav_records(fund_id, date, adj_nav);
"""

# ---------------------------------------------------------------------------
# V2 → V3 迁移脚本
#
# 设计决策：screening_results 新增申购限额两列，用于存储标注信息。
# 新列允许 NULL（旧记录无此数据，COALESCE 兜底）。
# ---------------------------------------------------------------------------
_MIGRATION_V2_TO_V3 = """
-- screening_results 表：增加申购限额字段
ALTER TABLE screening_results ADD COLUMN purchase_limit REAL;
ALTER TABLE screening_results ADD COLUMN purchase_status TEXT;
"""

# ---------------------------------------------------------------------------
# V3 全量建表 DDL — 全新 DB 直接用这个（包含所有 v3 新列和新表）
# ---------------------------------------------------------------------------
_CREATE_TABLES_SQL = """
-- 基金维度表：一只基金一行，market+code 唯一
CREATE TABLE IF NOT EXISTS funds (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    market          TEXT    NOT NULL,
    code            TEXT    NOT NULL,
    name            TEXT    NOT NULL DEFAULT '',
    establish_date  TEXT,
    manager_name    TEXT,
    fund_scale      REAL,
    track_benchmark TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(market, code)
);

-- 净值时序数据：最大的表，fund_id+date 唯一
CREATE TABLE IF NOT EXISTS nav_records (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_id         INTEGER NOT NULL REFERENCES funds(id),
    date            TEXT    NOT NULL,
    nav             REAL    NOT NULL,
    unit_nav        REAL,
    cumulative_nav  REAL,
    adj_nav         REAL,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(fund_id, date)
);

-- 持仓快照：fund_id+stock_code+snapshot_date 唯一
CREATE TABLE IF NOT EXISTS holdings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_id         INTEGER NOT NULL REFERENCES funds(id),
    stock_code      TEXT    NOT NULL,
    stock_name      TEXT    NOT NULL DEFAULT '',
    weight_pct      REAL,
    hold_shares     REAL,
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
    purchase_limit  REAL,
    purchase_status TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(fund_id, screening_date)
);

-- 申万行业映射表
CREATE TABLE IF NOT EXISTS stock_sector_mapping (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code    TEXT    NOT NULL UNIQUE,
    stock_name    TEXT    NOT NULL DEFAULT '',
    sw_sector_l1  TEXT    NOT NULL,
    is_hard_tech  INTEGER NOT NULL DEFAULT 0,
    is_resource   INTEGER NOT NULL DEFAULT 0,
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_nav_records_date ON nav_records(fund_id, date);
CREATE INDEX IF NOT EXISTS idx_screening_date ON screening_results(screening_date);
CREATE INDEX IF NOT EXISTS idx_holdings_stock ON holdings(stock_code);
CREATE INDEX IF NOT EXISTS idx_sector_mapping_l1 ON stock_sector_mapping(sw_sector_l1);
CREATE INDEX IF NOT EXISTS idx_nav_adj ON nav_records(fund_id, date, adj_nav);
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
        """
        初始化数据库连接 + 建表 + 设置 PRAGMA。

        Schema 迁移策略：
        - version 0（全新 DB）：直接执行 V2 全量建表
        - version 1（旧 DB）：执行 V1→V2 增量迁移脚本
        - version 2（已是最新）：什么都不做
        """
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")

        current_version = self._conn.execute("PRAGMA user_version").fetchone()[0]

        if current_version == 0:
            # 全新数据库：直接用 V3 全量建表
            self._conn.executescript(_CREATE_TABLES_SQL)
            self._conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
            self._conn.commit()
            logger.debug("DataStore schema 全量初始化完成 (v%d)", _SCHEMA_VERSION)
        elif current_version == 1:
            # v1 → v2 → v3 链式迁移
            logger.info("DataStore: 检测到 v1 schema，开始迁移到 v3...")
            self._conn.executescript(_MIGRATION_V1_TO_V2)
            self._conn.executescript(_MIGRATION_V2_TO_V3)
            self._conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
            self._conn.commit()
            logger.info("DataStore: v1 → v3 迁移完成")
        elif current_version == 2:
            # v2 → v3 增量迁移
            logger.info("DataStore: 检测到 v2 schema，开始迁移到 v3...")
            self._conn.executescript(_MIGRATION_V2_TO_V3)
            self._conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
            self._conn.commit()
            logger.info("DataStore: v2 → v3 迁移完成")

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
        V2 增强：可选列 'unit_nav', 'cumulative_nav', 'adj_nav'，
        有则写入，没有就写 NULL（兼容旧 fetcher 返回的 2 列 DataFrame）。
        """
        try:
            if nav_df.empty:
                return

            assert self._conn is not None
            fund_id = self._get_or_create_fund_id(market, code)

            # 检测 DataFrame 是否包含 V2 新列
            has_unit_nav = "unit_nav" in nav_df.columns
            has_cumulative_nav = "cumulative_nav" in nav_df.columns
            has_adj_nav = "adj_nav" in nav_df.columns

            records: list[tuple[Any, ...]] = []
            for _, row in nav_df.iterrows():
                record = (
                    fund_id,
                    self._normalize_date(row["date"]),
                    float(row["nav"]),
                    float(row["unit_nav"]) if has_unit_nav and pd.notna(row.get("unit_nav")) else None,
                    float(row["cumulative_nav"]) if has_cumulative_nav and pd.notna(row.get("cumulative_nav")) else None,
                    float(row["adj_nav"]) if has_adj_nav and pd.notna(row.get("adj_nav")) else None,
                )
                records.append(record)

            self._conn.executemany(
                """
                INSERT INTO nav_records (fund_id, date, nav, unit_nav, cumulative_nav, adj_nav)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(fund_id, date)
                DO UPDATE SET nav            = excluded.nav,
                              unit_nav       = COALESCE(excluded.unit_nav, nav_records.unit_nav),
                              cumulative_nav = COALESCE(excluded.cumulative_nav, nav_records.cumulative_nav),
                              adj_nav        = COALESCE(excluded.adj_nav, nav_records.adj_nav)
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
                    INSERT INTO holdings
                        (fund_id, stock_code, stock_name, weight_pct, hold_shares, snapshot_date)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(fund_id, stock_code, snapshot_date)
                    DO UPDATE SET stock_name  = excluded.stock_name,
                                  weight_pct  = excluded.weight_pct,
                                  hold_shares = COALESCE(excluded.hold_shares, holdings.hold_shares)
                    """,
                    [
                        (
                            fund_id, h.stock_code, h.stock_name, h.weight_pct,
                            getattr(h, "hold_shares", None), snap,
                        )
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
                    (fund_id, screening_date, nav, ma_short, ma_long, ma_diff_pct,
                     daily_change_pct, purchase_limit, purchase_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(fund_id, screening_date)
                DO UPDATE SET nav = excluded.nav,
                              ma_short = excluded.ma_short,
                              ma_long = excluded.ma_long,
                              ma_diff_pct = excluded.ma_diff_pct,
                              daily_change_pct = excluded.daily_change_pct,
                              purchase_limit = excluded.purchase_limit,
                              purchase_status = excluded.purchase_status
                """,
                (
                    fund_id,
                    screening_date,
                    fund.nav,
                    fund.ma_short,
                    fund.ma_long,
                    fund.ma_diff_pct,
                    fund.daily_change_pct,
                    fund.purchase_limit,
                    fund.purchase_status_text,
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
    # V2 新增 API：OLAP 量化分析支撑方法
    # ------------------------------------------------------------------

    def get_connection(self) -> sqlite3.Connection:
        """
        暴露只读连接给 analytics 层。

        analytics.py 中的 OLAP 函数需要直接执行 SQL 查询，
        但不应该持有 DataStore 实例（分析是只读的，不应和 CRUD 耦合）。
        """
        assert self._conn is not None, "DataStore 连接已关闭"
        return self._conn

    def persist_fund_detail(
        self,
        market: str,
        code: str,
        detail_dict: dict[str, Any],
    ) -> None:
        """
        UPSERT 基金详情增强字段（成立日期、经理、规模、基准）。

        detail_dict 示例:
            {"establish_date": "2018-09-05", "manager_name": "张坤",
             "fund_scale": 200.5, "track_benchmark": "沪深300"}
        """
        try:
            assert self._conn is not None
            fund_id = self._get_or_create_fund_id(market, code)

            # 只更新 detail_dict 中实际提供的字段，跳过 None 值
            updatable_fields = {
                "establish_date", "manager_name", "fund_scale", "track_benchmark",
            }
            set_clauses: list[str] = []
            values: list[Any] = []
            for field in updatable_fields:
                if field in detail_dict and detail_dict[field] is not None:
                    set_clauses.append(f"{field} = ?")
                    values.append(detail_dict[field])

            if not set_clauses:
                return

            set_clauses.append("updated_at = datetime('now')")
            values.append(fund_id)

            sql = f"UPDATE funds SET {', '.join(set_clauses)} WHERE id = ?"  # noqa: S608
            self._conn.execute(sql, values)
            self._conn.commit()
            logger.debug("DataStore: 已更新 %s:%s 的基金详情", market, code)
        except Exception:
            logger.warning(
                "DataStore: persist_fund_detail(%s:%s) 失败",
                market, code,
                exc_info=True,
            )

    def persist_sector_mapping(
        self,
        mappings: list[dict[str, Any]],
    ) -> None:
        """
        批量 UPSERT 申万行业映射表。

        mappings 格式:
            [{"stock_code": "600519", "stock_name": "贵州茅台",
              "sw_sector_l1": "食品饮料", "is_hard_tech": False, "is_resource": False}, ...]
        """
        try:
            if not mappings:
                return

            assert self._conn is not None
            self._conn.executemany(
                """
                INSERT INTO stock_sector_mapping
                    (stock_code, stock_name, sw_sector_l1, is_hard_tech, is_resource, updated_at)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(stock_code)
                DO UPDATE SET stock_name    = excluded.stock_name,
                              sw_sector_l1  = excluded.sw_sector_l1,
                              is_hard_tech  = excluded.is_hard_tech,
                              is_resource   = excluded.is_resource,
                              updated_at    = datetime('now')
                """,
                [
                    (
                        m["stock_code"],
                        m.get("stock_name", ""),
                        m["sw_sector_l1"],
                        int(m.get("is_hard_tech", False)),
                        int(m.get("is_resource", False)),
                    )
                    for m in mappings
                ],
            )
            self._conn.commit()
            logger.debug(
                "DataStore: 已持久化 %d 条申万行业映射", len(mappings),
            )
        except Exception:
            logger.warning("DataStore: persist_sector_mapping 失败", exc_info=True)

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
        for table in ("funds", "nav_records", "holdings", "sector_exposure", "screening_results", "stock_sector_mapping"):
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
