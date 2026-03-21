"""DataStore (SQLite 数据湖) 单元测试。"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from unittest.mock import patch

import pandas as pd
import pytest

from fund_screener.models import FundInfo, Holding, Market, SectorWeight
from fund_screener.storage import DataStore, _CREATE_TABLES_SQL_V1


@pytest.fixture()
def store(tmp_path: object) -> DataStore:
    """创建一个临时 DataStore 实例（V2 全量建表），测试完自动清理。"""
    db_path = tmp_path / "test.db"  # type: ignore[operator]
    s = DataStore(str(db_path))
    yield s  # type: ignore[misc]
    s.close()


@pytest.fixture()
def v1_db_path(tmp_path: object) -> str:
    """创建一个 V1 schema 的 DB 文件路径（模拟旧数据库）。"""
    db_path = tmp_path / "v1.db"  # type: ignore[operator]
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_CREATE_TABLES_SQL_V1)
    conn.execute("PRAGMA user_version = 1")
    conn.commit()
    # 写入一些旧数据
    conn.execute("INSERT INTO funds (market, code, name) VALUES ('CN', '005827', '易方达蓝筹')")
    conn.execute(
        "INSERT INTO nav_records (fund_id, date, nav) VALUES (1, '2026-03-20', 2.5)",
    )
    conn.execute(
        "INSERT INTO holdings (fund_id, stock_code, stock_name, weight_pct, snapshot_date) "
        "VALUES (1, '600519', '贵州茅台', 8.5, '2025-12-31')",
    )
    conn.commit()
    conn.close()
    return str(db_path)


class TestInitCreatesTable:
    """新 DB 自动建 5 张表。"""

    def test_all_tables_exist(self, store: DataStore) -> None:
        assert store._conn is not None
        cursor = store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name",
        )
        tables = {row[0] for row in cursor.fetchall()}
        expected = {"funds", "nav_records", "holdings", "sector_exposure", "screening_results"}
        assert expected.issubset(tables)

    def test_schema_version_set(self, store: DataStore) -> None:
        assert store._conn is not None
        version = store._conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == 3


class TestPersistFundList:
    """基金列表 UPSERT 测试。"""

    def test_insert_and_upsert(self, store: DataStore) -> None:
        fund_list = [
            {"code": "SPY", "name": "SPDR S&P 500"},
            {"code": "QQQ", "name": "Invesco QQQ"},
        ]
        store.persist_fund_list("US", fund_list)

        assert store._conn is not None
        count = store._conn.execute("SELECT COUNT(*) FROM funds").fetchone()[0]
        assert count == 2

        # 再次插入，更新名称
        updated_list = [
            {"code": "SPY", "name": "SPDR S&P 500 ETF Trust"},
        ]
        store.persist_fund_list("US", updated_list)

        name = store._conn.execute(
            "SELECT name FROM funds WHERE code = 'SPY'",
        ).fetchone()[0]
        assert name == "SPDR S&P 500 ETF Trust"

        # 总数不应该增加
        count = store._conn.execute("SELECT COUNT(*) FROM funds").fetchone()[0]
        assert count == 2


class TestPersistNavRecords:
    """净值记录 UPSERT 测试。"""

    def test_insert_and_upsert(self, store: DataStore) -> None:
        store.persist_fund_list("US", [{"code": "SPY", "name": "SPY"}])

        dates = [date.today() - timedelta(days=i) for i in range(5)]
        nav_df = pd.DataFrame({
            "date": dates,
            "nav": [100.0, 101.0, 102.0, 103.0, 104.0],
        })
        store.persist_nav_records("US", "SPY", nav_df)

        assert store._conn is not None
        count = store._conn.execute("SELECT COUNT(*) FROM nav_records").fetchone()[0]
        assert count == 5

        # 再次插入相同日期，nav 值更新
        nav_df_updated = pd.DataFrame({
            "date": dates[:2],
            "nav": [200.0, 201.0],
        })
        store.persist_nav_records("US", "SPY", nav_df_updated)

        count = store._conn.execute("SELECT COUNT(*) FROM nav_records").fetchone()[0]
        assert count == 5  # 不增加

        nav = store._conn.execute(
            "SELECT nav FROM nav_records WHERE date = ?",
            (dates[0].isoformat(),),
        ).fetchone()[0]
        assert nav == 200.0  # 被更新

    def test_empty_df_no_op(self, store: DataStore) -> None:
        empty_df = pd.DataFrame(columns=["date", "nav"])
        store.persist_nav_records("US", "SPY", empty_df)

        assert store._conn is not None
        count = store._conn.execute("SELECT COUNT(*) FROM nav_records").fetchone()[0]
        assert count == 0


class TestPersistHoldings:
    """持仓和行业分布入库测试。"""

    def test_holdings_and_sectors(self, store: DataStore) -> None:
        store.persist_fund_list("US", [{"code": "SPY", "name": "SPY"}])

        holdings = [
            Holding(stock_code="AAPL", stock_name="Apple", weight_pct=7.5),
            Holding(stock_code="MSFT", stock_name="Microsoft", weight_pct=6.8),
        ]
        sectors = [
            SectorWeight(sector="Technology", weight_pct=30.0),
            SectorWeight(sector="Healthcare", weight_pct=15.0),
        ]
        store.persist_holdings("US", "SPY", holdings, sectors)

        assert store._conn is not None
        h_count = store._conn.execute("SELECT COUNT(*) FROM holdings").fetchone()[0]
        assert h_count == 2

        s_count = store._conn.execute("SELECT COUNT(*) FROM sector_exposure").fetchone()[0]
        assert s_count == 2


class TestPersistScreeningResult:
    """筛选结果入库测试。"""

    def test_screening_result(self, store: DataStore) -> None:
        fund = FundInfo(
            code="SPY",
            name="SPDR S&P 500",
            market=Market.US,
            nav=450.0,
            ma_short=448.0,
            ma_long=440.0,
            ma_diff_pct=1.82,
            daily_change_pct=0.5,
            data_date=date.today(),
        )
        store.persist_screening_result(fund)

        assert store._conn is not None
        count = store._conn.execute("SELECT COUNT(*) FROM screening_results").fetchone()[0]
        assert count == 1

        row = store._conn.execute(
            "SELECT nav, ma_diff_pct FROM screening_results",
        ).fetchone()
        assert row[0] == 450.0
        assert row[1] == pytest.approx(1.82)


class TestStoreFailureDoesNotRaise:
    """DB 写入失败只 warning 不 crash。"""

    def test_persist_with_closed_connection(self, store: DataStore) -> None:
        """关闭连接后调用 persist 方法不应抛异常。"""
        store.close()
        # 这些调用应该只 warning，不 raise
        store.persist_fund_list("US", [{"code": "X", "name": "X"}])
        store.persist_nav_records(
            "US", "X",
            pd.DataFrame({"date": [date.today()], "nav": [1.0]}),
        )

    def test_persist_with_corrupted_store(self, tmp_path: object) -> None:
        """模拟写入失败的场景：将 _conn 替换为一个会抛异常的 mock。"""
        db_path = tmp_path / "broken.db"  # type: ignore[operator]
        s = DataStore(str(db_path))

        # 替换整个 _conn 为 mock，模拟所有 DB 操作失败
        from unittest.mock import MagicMock

        mock_conn = MagicMock()
        mock_conn.executemany.side_effect = sqlite3.OperationalError("disk full")
        mock_conn.execute.side_effect = sqlite3.OperationalError("disk full")
        s._conn = mock_conn

        # 不应抛异常
        s.persist_fund_list("US", [{"code": "X", "name": "X"}])

        s._conn = None  # 避免 close() 再出错


# =====================================================================
# V2 新增测试：Schema 迁移 + 新 persist 方法
# =====================================================================


class TestMigrationV1ToV2:
    """从 V1 schema 迁移到 V2。"""

    def test_migration_updates_version(self, v1_db_path: str) -> None:
        """打开 v1 DB 后应自动迁移到 v2。"""
        store = DataStore(v1_db_path)
        assert store._conn is not None
        version = store._conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == 3
        store.close()

    def test_migration_adds_new_columns(self, v1_db_path: str) -> None:
        """迁移后 funds/nav_records/holdings 应有新列。"""
        store = DataStore(v1_db_path)
        assert store._conn is not None

        # funds 新列
        cursor = store._conn.execute("PRAGMA table_info(funds)")
        fund_cols = {row[1] for row in cursor.fetchall()}
        assert "establish_date" in fund_cols
        assert "manager_name" in fund_cols
        assert "fund_scale" in fund_cols
        assert "track_benchmark" in fund_cols

        # nav_records 新列
        cursor = store._conn.execute("PRAGMA table_info(nav_records)")
        nav_cols = {row[1] for row in cursor.fetchall()}
        assert "unit_nav" in nav_cols
        assert "cumulative_nav" in nav_cols
        assert "adj_nav" in nav_cols

        # holdings 新列
        cursor = store._conn.execute("PRAGMA table_info(holdings)")
        hold_cols = {row[1] for row in cursor.fetchall()}
        assert "hold_shares" in hold_cols

        store.close()

    def test_migration_preserves_old_data(self, v1_db_path: str) -> None:
        """迁移后旧数据应完好，新列为 NULL。"""
        store = DataStore(v1_db_path)
        assert store._conn is not None

        # 旧 fund 数据完好
        row = store._conn.execute(
            "SELECT code, name, establish_date FROM funds WHERE code = '005827'",
        ).fetchone()
        assert row[0] == "005827"
        assert row[1] == "易方达蓝筹"
        assert row[2] is None  # 新列为 NULL

        # 旧 nav 数据完好
        row = store._conn.execute(
            "SELECT nav, adj_nav FROM nav_records WHERE date = '2026-03-20'",
        ).fetchone()
        assert row[0] == 2.5
        assert row[1] is None  # 新列为 NULL

        store.close()

    def test_migration_creates_sector_mapping_table(self, v1_db_path: str) -> None:
        """迁移后 stock_sector_mapping 表应存在且可写入。"""
        store = DataStore(v1_db_path)
        assert store._conn is not None

        # 表存在
        cursor = store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='stock_sector_mapping'",
        )
        assert cursor.fetchone() is not None

        # 可以写入
        store.persist_sector_mapping([{
            "stock_code": "600519",
            "stock_name": "贵州茅台",
            "sw_sector_l1": "食品饮料",
            "is_hard_tech": False,
            "is_resource": False,
        }])
        count = store._conn.execute(
            "SELECT COUNT(*) FROM stock_sector_mapping",
        ).fetchone()[0]
        assert count == 1

        store.close()


class TestPersistFundDetail:
    """基金详情 UPSERT 测试。"""

    def test_update_fund_detail(self, store: DataStore) -> None:
        store.persist_fund_list("CN", [{"code": "005827", "name": "易方达蓝筹"}])
        store.persist_fund_detail("CN", "005827", {
            "establish_date": "2018-09-05",
            "manager_name": "张坤",
            "fund_scale": 200.5,
            "track_benchmark": "沪深300",
        })

        assert store._conn is not None
        row = store._conn.execute(
            "SELECT establish_date, manager_name, fund_scale, track_benchmark "
            "FROM funds WHERE code = '005827'",
        ).fetchone()
        assert row[0] == "2018-09-05"
        assert row[1] == "张坤"
        assert row[2] == pytest.approx(200.5)
        assert row[3] == "沪深300"


class TestPersistSectorMapping:
    """申万行业映射批量 UPSERT 测试。"""

    def test_batch_upsert(self, store: DataStore) -> None:
        mappings = [
            {"stock_code": "600519", "stock_name": "贵州茅台", "sw_sector_l1": "食品饮料"},
            {"stock_code": "601318", "stock_name": "中国平安", "sw_sector_l1": "非银金融"},
        ]
        store.persist_sector_mapping(mappings)

        assert store._conn is not None
        count = store._conn.execute("SELECT COUNT(*) FROM stock_sector_mapping").fetchone()[0]
        assert count == 2

        # UPSERT: 更新行业
        store.persist_sector_mapping([
            {"stock_code": "600519", "stock_name": "贵州茅台", "sw_sector_l1": "白酒"},
        ])
        sector = store._conn.execute(
            "SELECT sw_sector_l1 FROM stock_sector_mapping WHERE stock_code = '600519'",
        ).fetchone()[0]
        assert sector == "白酒"

        # 总数不变（是 UPSERT 不是 INSERT）
        count = store._conn.execute("SELECT COUNT(*) FROM stock_sector_mapping").fetchone()[0]
        assert count == 2


class TestPersistNavV2:
    """V2 增强的净值记录（含 adj_nav）测试。"""

    def test_nav_with_adj_nav(self, store: DataStore) -> None:
        store.persist_fund_list("CN", [{"code": "005827", "name": "test"}])

        nav_df = pd.DataFrame({
            "date": ["2026-03-20", "2026-03-21"],
            "nav": [2.5, 2.6],
            "unit_nav": [2.5, 2.6],
            "cumulative_nav": [3.0, 3.1],
            "adj_nav": [3.0, 3.1],
        })
        store.persist_nav_records("CN", "005827", nav_df)

        assert store._conn is not None
        row = store._conn.execute(
            "SELECT nav, adj_nav FROM nav_records WHERE date = '2026-03-20'",
        ).fetchone()
        assert row[0] == 2.5
        assert row[1] == 3.0

    def test_nav_without_adj_nav_backward_compat(self, store: DataStore) -> None:
        """旧格式（只有 date+nav 两列）仍能正常写入。"""
        store.persist_fund_list("US", [{"code": "SPY", "name": "SPY"}])

        nav_df = pd.DataFrame({
            "date": ["2026-03-20"],
            "nav": [450.0],
        })
        store.persist_nav_records("US", "SPY", nav_df)

        assert store._conn is not None
        row = store._conn.execute(
            "SELECT nav, adj_nav FROM nav_records WHERE date = '2026-03-20'",
        ).fetchone()
        assert row[0] == 450.0
        assert row[1] is None  # 旧格式无 adj_nav


class TestGetConnection:
    """暴露连接给 analytics 层。"""

    def test_get_connection_returns_valid_conn(self, store: DataStore) -> None:
        conn = store.get_connection()
        assert conn is not None
        # 能执行查询
        result = conn.execute("SELECT 1").fetchone()
        assert result[0] == 1
