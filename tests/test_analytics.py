"""OLAP 分析函数单元测试。"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from fund_screener.analytics import (
    _cosine_similarity,
    calculate_correlation_matrix,
    detect_style_drift,
    scan_cross_sectional_momentum,
)
from fund_screener.storage import DataStore


@pytest.fixture()
def store(tmp_path: object) -> DataStore:
    """创建 V2 DataStore 并预填充测试数据。"""
    db_path = tmp_path / "test_analytics.db"  # type: ignore[operator]
    s = DataStore(str(db_path))
    yield s  # type: ignore[misc]
    s.close()


def _seed_nav_data(
    store: DataStore,
    code: str,
    name: str,
    days: int,
    base_nav: float,
    trend: float = 0.01,
    adj_nav_offset: float | None = None,
) -> None:
    """
    生成 mock 净值数据并写入 DB。

    trend > 0: 上涨趋势（MA_short > MA_long）
    trend < 0: 下跌趋势
    最后一天故意设为微跌（daily_return < 0），模拟"回踩"信号。
    """
    assert store._conn is not None
    store.persist_fund_list("CN", [{"code": code, "name": name}])
    fund_id = store._get_or_create_fund_id("CN", code)

    today = date(2026, 3, 20)
    records = []
    for i in range(days):
        d = today - timedelta(days=days - 1 - i)
        nav = base_nav + trend * i

        # 最后一天微跌（模拟回踩信号）
        if i == days - 1:
            nav = nav - 0.02

        adj = nav + adj_nav_offset if adj_nav_offset is not None else None
        records.append((fund_id, d.isoformat(), nav, nav, None, adj))

    store._conn.executemany(
        """
        INSERT INTO nav_records (fund_id, date, nav, unit_nav, cumulative_nav, adj_nav)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(fund_id, date) DO UPDATE SET
            nav = excluded.nav, adj_nav = excluded.adj_nav
        """,
        records,
    )
    store._conn.commit()


def _seed_holdings(
    store: DataStore,
    code: str,
    snapshot_date: str,
    holdings: list[tuple[str, str, float]],
) -> None:
    """写入持仓数据: [(stock_code, stock_name, weight_pct), ...]"""
    assert store._conn is not None
    fund_id = store._get_or_create_fund_id("CN", code)
    store._conn.executemany(
        """
        INSERT INTO holdings (fund_id, stock_code, stock_name, weight_pct, snapshot_date)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(fund_id, stock_code, snapshot_date) DO UPDATE SET weight_pct = excluded.weight_pct
        """,
        [(fund_id, sc, sn, w, snapshot_date) for sc, sn, w in holdings],
    )
    store._conn.commit()


def _seed_sector_mapping(store: DataStore, mappings: list[tuple[str, str]]) -> None:
    """写入行业映射: [(stock_code, sw_sector_l1), ...]"""
    store.persist_sector_mapping([
        {"stock_code": sc, "sw_sector_l1": sector}
        for sc, sector in mappings
    ])


# =====================================================================
# TestMomentumScan
# =====================================================================

class TestMomentumScan:
    """横截面动量扫描测试。"""

    def test_detects_bullish_pullback(self, store: DataStore) -> None:
        """多头排列 + 回踩 → 应被检出。"""
        # 60+ 天上涨趋势数据，最后一天微跌
        _seed_nav_data(store, "005827", "易方达蓝筹", days=80, base_nav=2.0, trend=0.01)

        conn = store.get_connection()
        results = scan_cross_sectional_momentum(conn, "2026-03-20", ma_short=20, ma_long=60)

        assert len(results) >= 1
        codes = [r.fund_code for r in results]
        assert "005827" in codes

        # 验证字段
        r = next(r for r in results if r.fund_code == "005827")
        assert r.ma_short > r.ma_long  # 多头排列
        assert r.daily_return < 0  # 回踩
        assert r.ma_diff_pct > 0

    def test_insufficient_data_excluded(self, store: DataStore) -> None:
        """数据不足 ma_long 天 → 不应出现在结果中。"""
        _seed_nav_data(store, "000001", "短数据基金", days=30, base_nav=1.0, trend=0.01)

        conn = store.get_connection()
        results = scan_cross_sectional_momentum(conn, "2026-03-20", ma_short=20, ma_long=60)

        codes = [r.fund_code for r in results]
        assert "000001" not in codes

    def test_adj_nav_null_falls_back_to_nav(self, store: DataStore) -> None:
        """adj_nav 为 NULL 时应 fallback 到 nav（COALESCE 兼容旧数据）。"""
        # adj_nav_offset=None → adj_nav 全为 NULL
        _seed_nav_data(store, "016873", "旧数据基金", days=80, base_nav=1.5, trend=0.01, adj_nav_offset=None)

        conn = store.get_connection()
        results = scan_cross_sectional_momentum(conn, "2026-03-20", ma_short=20, ma_long=60)

        # 应该仍然能计算（用 nav 兜底）
        codes = [r.fund_code for r in results]
        assert "016873" in codes

    def test_downtrend_not_detected(self, store: DataStore) -> None:
        """下跌趋势（MA_short < MA_long）不应被检出。"""
        _seed_nav_data(store, "999999", "下跌基金", days=80, base_nav=3.0, trend=-0.01)

        conn = store.get_connection()
        results = scan_cross_sectional_momentum(conn, "2026-03-20", ma_short=20, ma_long=60)

        codes = [r.fund_code for r in results]
        assert "999999" not in codes


# =====================================================================
# TestStyleDrift
# =====================================================================

class TestStyleDrift:
    """风格漂移检测测试。"""

    def test_high_turnover_triggers_drift(self, store: DataStore) -> None:
        """权重变化 > 20% → is_drifted=True。"""
        store.persist_fund_list("CN", [{"code": "005827", "name": "test"}])

        # 前一季度：重仓白酒
        _seed_holdings(store, "005827", "2025-12-31", [
            ("600519", "贵州茅台", 15.0),
            ("000858", "五粮液", 12.0),
            ("000568", "泸州老窖", 10.0),
        ])
        # 当前季度：完全换赛道到新能源
        _seed_holdings(store, "005827", "2026-03-31", [
            ("300750", "宁德时代", 14.0),
            ("002594", "比亚迪", 11.0),
            ("601012", "隆基绿能", 9.0),
        ])

        conn = store.get_connection()
        result = detect_style_drift(conn, "005827", "2026-03-31", "2025-12-31", threshold=20.0)

        assert result.is_drifted is True
        assert result.total_turnover > 20.0
        # 所有旧持仓都退出了
        assert len(result.exits) == 3
        # 所有新持仓都是新进的
        assert len(result.new_entries) == 3

    def test_minor_adjustment_no_drift(self, store: DataStore) -> None:
        """正常微调 → is_drifted=False。"""
        store.persist_fund_list("CN", [{"code": "016873", "name": "test"}])

        _seed_holdings(store, "016873", "2025-12-31", [
            ("600519", "贵州茅台", 15.0),
            ("000858", "五粮液", 12.0),
        ])
        # 微调：权重小幅变动
        _seed_holdings(store, "016873", "2026-03-31", [
            ("600519", "贵州茅台", 13.0),
            ("000858", "五粮液", 14.0),
        ])

        conn = store.get_connection()
        result = detect_style_drift(conn, "016873", "2026-03-31", "2025-12-31", threshold=20.0)

        assert result.is_drifted is False
        assert result.total_turnover < 20.0


# =====================================================================
# TestCorrelation
# =====================================================================

class TestCorrelation:
    """底层相关性矩阵测试。"""

    def test_identical_holdings_high_similarity(self, store: DataStore) -> None:
        """相同持仓 → 相似度接近 1.0。"""
        store.persist_fund_list("CN", [
            {"code": "FUND_A", "name": "A"},
            {"code": "FUND_B", "name": "B"},
        ])

        same_holdings = [
            ("600519", "贵州茅台", 15.0),
            ("000858", "五粮液", 12.0),
        ]
        _seed_holdings(store, "FUND_A", "2026-03-31", same_holdings)
        _seed_holdings(store, "FUND_B", "2026-03-31", same_holdings)

        # 行业映射
        _seed_sector_mapping(store, [
            ("600519", "食品饮料"),
            ("000858", "食品饮料"),
        ])

        conn = store.get_connection()
        result = calculate_correlation_matrix(conn, ["FUND_A", "FUND_B"], threshold=0.3)

        matrix = result["matrix"]
        assert matrix["FUND_A"]["FUND_B"] == pytest.approx(1.0, abs=0.01)

    def test_different_sectors_low_similarity(self, store: DataStore) -> None:
        """不同行业 → 相似度接近 0。"""
        store.persist_fund_list("CN", [
            {"code": "FUND_C", "name": "C"},
            {"code": "FUND_D", "name": "D"},
        ])

        # FUND_C: 全部食品饮料
        _seed_holdings(store, "FUND_C", "2026-03-31", [
            ("600519", "贵州茅台", 15.0),
        ])
        # FUND_D: 全部电子
        _seed_holdings(store, "FUND_D", "2026-03-31", [
            ("002371", "北方华创", 15.0),
        ])

        _seed_sector_mapping(store, [
            ("600519", "食品饮料"),
            ("002371", "电子"),
        ])

        conn = store.get_connection()
        result = calculate_correlation_matrix(conn, ["FUND_C", "FUND_D"], threshold=0.3)

        matrix = result["matrix"]
        assert matrix["FUND_C"]["FUND_D"] == pytest.approx(0.0, abs=0.01)

    def test_above_threshold_triggers_alert(self, store: DataStore) -> None:
        """超阈值 → 出现在 alerts 列表。"""
        store.persist_fund_list("CN", [
            {"code": "FUND_E", "name": "E"},
            {"code": "FUND_F", "name": "F"},
        ])

        # 两只基金都重仓相同行业
        _seed_holdings(store, "FUND_E", "2026-03-31", [
            ("600519", "贵州茅台", 15.0),
            ("601318", "中国平安", 10.0),
        ])
        _seed_holdings(store, "FUND_F", "2026-03-31", [
            ("000858", "五粮液", 14.0),
            ("601601", "中国太保", 11.0),
        ])

        _seed_sector_mapping(store, [
            ("600519", "食品饮料"),
            ("000858", "食品饮料"),
            ("601318", "非银金融"),
            ("601601", "非银金融"),
        ])

        conn = store.get_connection()
        result = calculate_correlation_matrix(conn, ["FUND_E", "FUND_F"], threshold=0.3)

        # 两只基金行业分布相似（食品饮料+非银金融），应超阈值
        alerts = result["alerts"]
        assert len(alerts) >= 1
        assert alerts[0].fund_a == "FUND_E"
        assert alerts[0].fund_b == "FUND_F"
        assert alerts[0].is_alert is True


# =====================================================================
# TestCosineSimilarity（辅助函数单测）
# =====================================================================

class TestCosineSimilarity:
    """余弦相似度计算。"""

    def test_identical_vectors(self) -> None:
        vec = {"a": 3.0, "b": 4.0}
        assert _cosine_similarity(vec, vec) == pytest.approx(1.0)

    def test_orthogonal_vectors(self) -> None:
        vec_a = {"a": 1.0}
        vec_b = {"b": 1.0}
        assert _cosine_similarity(vec_a, vec_b) == pytest.approx(0.0)

    def test_empty_vector(self) -> None:
        assert _cosine_similarity({}, {"a": 1.0}) == pytest.approx(0.0)
        assert _cosine_similarity({}, {}) == pytest.approx(0.0)
