"""
申购限额标注 + 可选过滤功能的单元测试。

覆盖范围：
1. fetch_purchase_limit_map() — 正常解析、异常兜底、缓存命中
2. 报告分组逻辑 — _classify_by_purchase 的边界值（0、1000、1e8、1e11、NaN、None）
3. _format_purchase_limit() — 金额格式化
4. Schema V2→V3 迁移 — 新增列存在性
"""

from __future__ import annotations

import math
import sqlite3
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from fund_screener.models import FundInfo, Market
from fund_screener.reporter import (
    _classify_by_purchase,
    _format_purchase_limit,
    _PURCHASE_LIMIT_NORMAL_THRESHOLD,
)
from fund_screener.storage import DataStore, _MIGRATION_V1_TO_V2


# =====================================================================
# 辅助工厂：快速构建 FundInfo 测试数据
# =====================================================================

def _make_fund(
    code: str = "000001",
    purchase_limit: float | None = None,
    purchase_status_text: str | None = None,
    ma_diff_pct: float = 1.0,
) -> FundInfo:
    """构建一个最小化的 FundInfo，只填申购相关字段 + 必填字段。"""
    return FundInfo(
        code=code,
        name=f"测试基金{code}",
        market=Market.CN,
        nav=1.0,
        ma_short=1.1,
        ma_long=1.0,
        ma_diff_pct=ma_diff_pct,
        data_date=date(2026, 3, 21),
        purchase_limit=purchase_limit,
        purchase_status_text=purchase_status_text,
    )


# =====================================================================
# 1. fetch_purchase_limit_map() 测试
# =====================================================================


class TestFetchPurchaseLimitMap:
    """测试 CNFundFetcher.fetch_purchase_limit_map()。"""

    def test_normal_parsing(self) -> None:
        """正常数据应被正确解析为 {code: (limit, status)} 映射。"""
        from fund_screener.cache import FileCache
        from fund_screener.config import CNFundConfig, RateLimitConfig
        from fund_screener.fetchers.cn_fund import CNFundFetcher

        cache = MagicMock(spec=FileCache)
        cache.get.return_value = None  # 缓存未命中

        fetcher = CNFundFetcher(
            cache=cache,
            rate_limit_config=RateLimitConfig(),
            cn_config=CNFundConfig(),
        )

        # mock akshare 返回数据
        mock_df = pd.DataFrame({
            "基金代码": ["000001", "000002", "000003"],
            "日累计限定金额": [1e11, 1e4, 0.0],
            "申购状态": ["开放申购", "暂停大额申购", "暂停申购"],
        })

        with patch("akshare.fund_purchase_em", return_value=mock_df):
            result = fetcher.fetch_purchase_limit_map()

        assert len(result) == 3
        assert result["000001"] == (1e11, "开放申购")
        assert result["000002"] == (1e4, "暂停大额申购")
        assert result["000003"] == (0.0, "暂停申购")

        # 验证结果被缓存
        cache.set.assert_called_once()

    def test_nan_handling(self) -> None:
        """NaN 值应被替换为 -1.0（标记为未知）。"""
        from fund_screener.cache import FileCache
        from fund_screener.config import CNFundConfig, RateLimitConfig
        from fund_screener.fetchers.cn_fund import CNFundFetcher

        cache = MagicMock(spec=FileCache)
        cache.get.return_value = None

        fetcher = CNFundFetcher(
            cache=cache,
            rate_limit_config=RateLimitConfig(),
            cn_config=CNFundConfig(),
        )

        mock_df = pd.DataFrame({
            "基金代码": ["000001"],
            "日累计限定金额": [float("nan")],
            "申购状态": ["开放申购"],
        })

        with patch("akshare.fund_purchase_em", return_value=mock_df):
            result = fetcher.fetch_purchase_limit_map()

        assert result["000001"][0] == -1.0  # NaN → -1.0

    def test_api_failure_returns_empty_dict(self) -> None:
        """API 调用失败应返回空 dict，不抛异常。"""
        from fund_screener.cache import FileCache
        from fund_screener.config import CNFundConfig, RateLimitConfig
        from fund_screener.fetchers.cn_fund import CNFundFetcher

        cache = MagicMock(spec=FileCache)
        cache.get.return_value = None

        fetcher = CNFundFetcher(
            cache=cache,
            rate_limit_config=RateLimitConfig(),
            cn_config=CNFundConfig(),
        )

        with patch("akshare.fund_purchase_em", side_effect=Exception("network error")):
            result = fetcher.fetch_purchase_limit_map()

        assert result == {}

    def test_cache_hit(self) -> None:
        """缓存命中时应直接返回，不调用 API。"""
        from fund_screener.cache import FileCache
        from fund_screener.config import CNFundConfig, RateLimitConfig
        from fund_screener.fetchers.cn_fund import CNFundFetcher

        cached_data = [
            {"code": "000001", "limit": 1e11, "status": "开放申购"},
        ]

        cache = MagicMock(spec=FileCache)
        cache.get.return_value = cached_data

        fetcher = CNFundFetcher(
            cache=cache,
            rate_limit_config=RateLimitConfig(),
            cn_config=CNFundConfig(),
        )

        result = fetcher.fetch_purchase_limit_map()
        assert result == {"000001": (1e11, "开放申购")}

    def test_missing_columns_returns_empty(self) -> None:
        """列名不匹配（缺少代码列）应返回空 dict。"""
        from fund_screener.cache import FileCache
        from fund_screener.config import CNFundConfig, RateLimitConfig
        from fund_screener.fetchers.cn_fund import CNFundFetcher

        cache = MagicMock(spec=FileCache)
        cache.get.return_value = None

        fetcher = CNFundFetcher(
            cache=cache,
            rate_limit_config=RateLimitConfig(),
            cn_config=CNFundConfig(),
        )

        # 故意用不含"代码"的列名
        mock_df = pd.DataFrame({
            "fund_id": ["000001"],
            "amount": [1e11],
        })

        with patch("akshare.fund_purchase_em", return_value=mock_df):
            result = fetcher.fetch_purchase_limit_map()

        assert result == {}


# =====================================================================
# 2. 报告分组逻辑测试
# =====================================================================


class TestClassifyByPurchase:
    """测试 _classify_by_purchase 分组逻辑的各种边界值。"""

    def test_normal_purchase(self) -> None:
        """日限额 >= 1e8 → 正常申购组。"""
        fund = _make_fund(purchase_limit=1e11)
        normal, limited, suspended, unknown = _classify_by_purchase([fund])
        assert len(normal) == 1
        assert len(limited) == 0

    def test_limited_purchase(self) -> None:
        """0 < 日限额 < 1e8 → 限额申购组。"""
        fund_1w = _make_fund(code="001", purchase_limit=1e4)
        fund_100w = _make_fund(code="002", purchase_limit=1e6)
        normal, limited, suspended, unknown = _classify_by_purchase([fund_1w, fund_100w])
        assert len(limited) == 2
        assert len(normal) == 0

    def test_suspended_purchase(self) -> None:
        """日限额 = 0 → 暂停申购组。"""
        fund = _make_fund(purchase_limit=0.0)
        normal, limited, suspended, unknown = _classify_by_purchase([fund])
        assert len(suspended) == 1

    def test_unknown_none(self) -> None:
        """purchase_limit is None → 未知组。"""
        fund = _make_fund(purchase_limit=None)
        _, _, _, unknown = _classify_by_purchase([fund])
        assert len(unknown) == 1

    def test_unknown_negative(self) -> None:
        """purchase_limit < 0（获取失败标记）→ 未知组。"""
        fund = _make_fund(purchase_limit=-1.0)
        _, _, _, unknown = _classify_by_purchase([fund])
        assert len(unknown) == 1

    def test_unknown_nan(self) -> None:
        """purchase_limit = NaN → 未知组。"""
        fund = _make_fund(purchase_limit=float("nan"))
        _, _, _, unknown = _classify_by_purchase([fund])
        assert len(unknown) == 1

    def test_boundary_1e8(self) -> None:
        """日限额 = 1e8（正好 1 亿）→ 正常申购组（阈值是 >=）。"""
        fund = _make_fund(purchase_limit=1e8)
        normal, limited, _, _ = _classify_by_purchase([fund])
        assert len(normal) == 1
        assert len(limited) == 0

    def test_boundary_just_below_1e8(self) -> None:
        """日限额 = 9999_9999（略低于 1 亿）→ 限额申购组。"""
        fund = _make_fund(purchase_limit=9999_9999)
        normal, limited, _, _ = _classify_by_purchase([fund])
        assert len(limited) == 1
        assert len(normal) == 0

    def test_mixed_funds(self) -> None:
        """混合多种状态的基金，验证分组正确性。"""
        funds = [
            _make_fund(code="001", purchase_limit=1e11),      # 正常
            _make_fund(code="002", purchase_limit=1e4),       # 限额
            _make_fund(code="003", purchase_limit=0.0),       # 暂停
            _make_fund(code="004", purchase_limit=None),      # 未知
            _make_fund(code="005", purchase_limit=1e8),       # 正常（边界）
            _make_fund(code="006", purchase_limit=-1.0),      # 未知（失败标记）
        ]
        normal, limited, suspended, unknown = _classify_by_purchase(funds)
        assert len(normal) == 2    # 001, 005
        assert len(limited) == 1   # 002
        assert len(suspended) == 1 # 003
        assert len(unknown) == 2   # 004, 006


# =====================================================================
# 3. 金额格式化测试
# =====================================================================


class TestFormatPurchaseLimit:
    """测试 _format_purchase_limit 金额格式化。"""

    def test_unlimited(self) -> None:
        assert _format_purchase_limit(1e11) == "无限制"
        assert _format_purchase_limit(1e10) == "无限制"

    def test_yi(self) -> None:
        assert _format_purchase_limit(5e8) == "5.00 亿"
        assert _format_purchase_limit(1e8) == "1.00 亿"

    def test_wan(self) -> None:
        assert _format_purchase_limit(1e4) == "1.00 万"
        assert _format_purchase_limit(5e5) == "50.00 万"

    def test_yuan(self) -> None:
        assert _format_purchase_limit(100) == "100 元"
        assert _format_purchase_limit(1) == "1 元"

    def test_suspended(self) -> None:
        assert _format_purchase_limit(0) == "暂停"
        assert _format_purchase_limit(0.0) == "暂停"

    def test_unknown(self) -> None:
        assert _format_purchase_limit(None) == "未知"
        assert _format_purchase_limit(-1.0) == "未知"
        assert _format_purchase_limit(float("nan")) == "未知"


# =====================================================================
# 4. Schema V2→V3 迁移测试
# =====================================================================


class TestMigrationV2ToV3:
    """从 V2 schema 迁移到 V3。"""

    @pytest.fixture()
    def v2_db_path(self, tmp_path: object) -> str:
        """创建一个 V2 schema 的 DB 文件（模拟旧数据库）。"""
        db_path = tmp_path / "v2.db"  # type: ignore[operator]
        conn = sqlite3.connect(str(db_path))

        # 先建 V1 结构
        from fund_screener.storage import _CREATE_TABLES_SQL_V1
        conn.executescript(_CREATE_TABLES_SQL_V1)
        # 再执行 V1→V2 迁移
        conn.executescript(_MIGRATION_V1_TO_V2)
        conn.execute("PRAGMA user_version = 2")
        conn.commit()

        # 写入一些 V2 数据
        conn.execute(
            "INSERT INTO funds (market, code, name) VALUES ('CN', '005827', '易方达蓝筹')",
        )
        conn.execute(
            "INSERT INTO screening_results "
            "(fund_id, screening_date, nav, ma_short, ma_long, ma_diff_pct) "
            "VALUES (1, '2026-03-20', 2.5, 2.6, 2.4, 8.33)",
        )
        conn.commit()
        conn.close()
        return str(db_path)

    def test_migration_updates_version_to_3(self, v2_db_path: str) -> None:
        """打开 v2 DB 后应自动迁移到 v3。"""
        store = DataStore(v2_db_path)
        assert store._conn is not None
        version = store._conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == 3
        store.close()

    def test_migration_adds_purchase_columns(self, v2_db_path: str) -> None:
        """迁移后 screening_results 应有 purchase_limit 和 purchase_status 列。"""
        store = DataStore(v2_db_path)
        assert store._conn is not None

        cursor = store._conn.execute("PRAGMA table_info(screening_results)")
        cols = {row[1] for row in cursor.fetchall()}
        assert "purchase_limit" in cols
        assert "purchase_status" in cols
        store.close()

    def test_migration_preserves_old_screening_data(self, v2_db_path: str) -> None:
        """迁移后旧的筛选结果数据应完好，新列为 NULL。"""
        store = DataStore(v2_db_path)
        assert store._conn is not None

        row = store._conn.execute(
            "SELECT nav, ma_diff_pct, purchase_limit, purchase_status "
            "FROM screening_results WHERE screening_date = '2026-03-20'",
        ).fetchone()
        assert row[0] == 2.5
        assert row[1] == pytest.approx(8.33)
        assert row[2] is None  # 新列为 NULL
        assert row[3] is None  # 新列为 NULL
        store.close()

    def test_persist_screening_with_purchase_fields(self, v2_db_path: str) -> None:
        """迁移后应能写入含申购字段的筛选结果。"""
        store = DataStore(v2_db_path)

        fund = FundInfo(
            code="000001",
            name="测试基金",
            market=Market.CN,
            nav=1.5,
            ma_short=1.6,
            ma_long=1.4,
            ma_diff_pct=14.29,
            data_date=date(2026, 3, 21),
            purchase_limit=1e4,
            purchase_status_text="暂停大额申购",
        )
        store.persist_screening_result(fund)

        assert store._conn is not None
        row = store._conn.execute(
            "SELECT purchase_limit, purchase_status "
            "FROM screening_results WHERE fund_id = ("
            "  SELECT id FROM funds WHERE code = '000001'"
            ")",
        ).fetchone()
        assert row[0] == pytest.approx(1e4)
        assert row[1] == "暂停大额申购"
        store.close()
