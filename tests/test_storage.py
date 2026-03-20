"""DataStore (SQLite 数据湖) 单元测试。"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from unittest.mock import patch

import pandas as pd
import pytest

from fund_screener.models import FundInfo, Holding, Market, SectorWeight
from fund_screener.storage import DataStore


@pytest.fixture()
def store(tmp_path: object) -> DataStore:
    """创建一个临时 DataStore 实例，测试完自动清理。"""
    db_path = tmp_path / "test.db"  # type: ignore[operator]
    s = DataStore(str(db_path))
    yield s  # type: ignore[misc]
    s.close()


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
        assert version == 1


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
