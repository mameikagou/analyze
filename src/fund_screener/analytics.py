"""
OLAP 量化分析核心 — 三个只读分析函数。

设计哲学：
1. 分析层是纯只读的，只接受 sqlite3.Connection，不持有 DataStore 实例
2. 尽量在 SQL 层做聚合（利用索引），Python 层只做 SQL 不擅长的事
3. COALESCE(adj_nav, nav) 兼容旧数据（v1 无 adj_nav 列时 fallback 到 nav）

三个核心函数：
- scan_cross_sectional_momentum: 横截面动量扫描（全市场找"多头排列+缩量回踩"）
- detect_style_drift: 风格漂移检测（基金经理是否偷偷换赛道）
- calculate_correlation_matrix: 底层相关性矩阵（防止买入"变种相关资产"）
"""

from __future__ import annotations

import logging
import math
import sqlite3
from typing import Any

from fund_screener.models import CorrelationPair, MomentumScanResult, StyleDriftResult

logger = logging.getLogger("fund_screener.analytics")


# =====================================================================
# 函数 1: 横截面动量扫描
# =====================================================================

def scan_cross_sectional_momentum(
    conn: sqlite3.Connection,
    scan_date: str,
    ma_short: int = 20,
    ma_long: int = 60,
) -> list[MomentumScanResult]:
    """
    全市场横截面动量扫描 — 找"多头排列 + 缩量回踩"的标的。

    核心逻辑：
    1. SQL Window Function 计算每只基金的 MA_short 和 MA_long
    2. COALESCE(adj_nav, nav) 兼容旧数据
    3. 筛选条件: MA_short > MA_long（多头排列）AND daily_return < 0（回踩）
    4. 返回符合条件的基金列表

    Args:
        conn: SQLite 连接（只读）
        scan_date: 扫描日期 YYYY-MM-DD，用该日期及之前的数据计算
        ma_short: 短期均线周期（默认 20）
        ma_long: 长期均线周期（默认 60）

    Returns:
        list[MomentumScanResult]: 符合"多头排列+回踩"条件的基金列表
    """
    # 用 CTE + Window Function 在 SQL 层完成大部分计算
    # 关键技巧：用 COALESCE(adj_nav, nav) 让旧数据（无复权净值）也能参与计算
    sql = """
    WITH nav_with_rank AS (
        -- 步骤 1: 为每只基金的净值记录标注行号（按日期倒序）
        -- 只取 scan_date 及之前的数据
        SELECT
            n.fund_id,
            n.date,
            COALESCE(n.adj_nav, n.nav) AS effective_nav,
            ROW_NUMBER() OVER (
                PARTITION BY n.fund_id ORDER BY n.date DESC
            ) AS rn
        FROM nav_records n
        WHERE n.date <= ?
    ),
    fund_ma AS (
        -- 步骤 2: 计算每只基金的 MA_short 和 MA_long
        -- 只对数据量 >= ma_long 的基金计算（数据不足则排除）
        SELECT
            fund_id,
            -- MA_short: 最近 ma_short 天的平均值
            AVG(CASE WHEN rn <= ? THEN effective_nav END) AS ma_short_val,
            -- MA_long: 最近 ma_long 天的平均值
            AVG(CASE WHEN rn <= ? THEN effective_nav END) AS ma_long_val,
            -- 最新净值（rn=1）
            MAX(CASE WHEN rn = 1 THEN effective_nav END) AS latest_nav,
            -- 前一天净值（rn=2），用于算 daily return
            MAX(CASE WHEN rn = 2 THEN effective_nav END) AS prev_nav,
            -- 最新日期
            MAX(CASE WHEN rn = 1 THEN date END) AS latest_date,
            -- 数据行数（用于过滤数据不足的基金）
            COUNT(*) AS total_rows
        FROM nav_with_rank
        WHERE rn <= ?
        GROUP BY fund_id
        HAVING total_rows >= ?
    )
    SELECT
        f.code,
        f.name,
        fm.latest_date,
        fm.ma_short_val,
        fm.ma_long_val,
        fm.latest_nav,
        fm.prev_nav
    FROM fund_ma fm
    JOIN funds f ON fm.fund_id = f.id
    WHERE fm.ma_short_val IS NOT NULL
      AND fm.ma_long_val IS NOT NULL
      AND fm.prev_nav IS NOT NULL
      AND fm.prev_nav > 0
      -- 多头排列条件: MA_short > MA_long
      AND fm.ma_short_val > fm.ma_long_val
    """

    try:
        cursor = conn.execute(
            sql,
            (scan_date, ma_short, ma_long, ma_long, ma_long),
        )
        rows = cursor.fetchall()
    except sqlite3.Error as e:
        logger.error("横截面动量扫描 SQL 执行失败: %s", e)
        return []

    results: list[MomentumScanResult] = []
    for row in rows:
        code, name, latest_date, ma_s, ma_l, latest_nav, prev_nav = row

        # Python 层计算 daily return 和 MA 差值
        daily_return = (latest_nav - prev_nav) / prev_nav * 100

        # 回踩条件: daily_return < 0
        if daily_return >= 0:
            continue

        ma_diff_pct = (ma_s - ma_l) / ma_l * 100

        results.append(MomentumScanResult(
            fund_code=code,
            fund_name=name or "",
            scan_date=latest_date,
            ma_short=round(ma_s, 4),
            ma_long=round(ma_l, 4),
            ma_diff_pct=round(ma_diff_pct, 2),
            daily_return=round(daily_return, 2),
            latest_nav=round(latest_nav, 4),
        ))

    # 按 MA 差值降序排列（差值越大，趋势越强）
    results.sort(key=lambda r: r.ma_diff_pct, reverse=True)
    logger.info(
        "横截面动量扫描完成: %d 只基金符合'多头排列+回踩'条件",
        len(results),
    )
    return results


# =====================================================================
# 函数 2: 风格漂移检测
# =====================================================================

def detect_style_drift(
    conn: sqlite3.Connection,
    fund_code: str,
    current_quarter: str,
    prev_quarter: str,
    threshold: float = 20.0,
) -> StyleDriftResult:
    """
    风格漂移穿透 — 检测基金经理是否偷偷换赛道。

    核心逻辑：
    1. 分别查两个季度的 Top10 持仓（holdings 表）
    2. Python 层做 dict merge（为什么不用 SQL？因为 SQLite 不支持 FULL OUTER JOIN，
       且 Top10 最多 20 行，Python dict merge 比模拟 FULL OUTER JOIN 更清晰）
    3. 计算 total_turnover = sum(|curr_weight - prev_weight|) / 2
    4. 标记新进、退出、大幅调仓的个股

    Args:
        conn: SQLite 连接
        fund_code: 基金代码
        current_quarter: 当前季度标签 YYYY-MM-DD（如 '2026-03-31'）
        prev_quarter: 对比季度标签 YYYY-MM-DD（如 '2025-12-31'）
        threshold: 漂移判定阈值百分比（默认 20%）

    Returns:
        StyleDriftResult 包含换手率、是否漂移、变动明细
    """

    def _query_holdings(quarter: str) -> dict[str, float]:
        """查某季度的持仓，返回 {stock_code: weight_pct}。"""
        sql = """
        SELECT h.stock_code, h.weight_pct
        FROM holdings h
        JOIN funds f ON h.fund_id = f.id
        WHERE f.code = ? AND h.snapshot_date = ?
        ORDER BY h.weight_pct DESC
        """
        try:
            rows = conn.execute(sql, (fund_code, quarter)).fetchall()
        except sqlite3.Error as e:
            logger.warning("查询 %s %s 持仓失败: %s", fund_code, quarter, e)
            return {}

        return {
            row[0]: float(row[1]) if row[1] is not None else 0.0
            for row in rows
        }

    prev_holdings = _query_holdings(prev_quarter)
    curr_holdings = _query_holdings(current_quarter)

    # 合并所有出现过的股票代码
    all_stocks = set(prev_holdings.keys()) | set(curr_holdings.keys())

    new_entries: list[str] = []
    exits: list[str] = []
    major_changes: list[dict[str, object]] = []
    total_abs_delta = 0.0

    for stock in all_stocks:
        prev_w = prev_holdings.get(stock, 0.0)
        curr_w = curr_holdings.get(stock, 0.0)
        delta = abs(curr_w - prev_w)
        total_abs_delta += delta

        if stock not in prev_holdings:
            new_entries.append(stock)
        elif stock not in curr_holdings:
            exits.append(stock)

        # 大幅调仓：单只个股权重变动 > 3%
        if delta > 3.0:
            major_changes.append({
                "stock_code": stock,
                "prev_weight": round(prev_w, 2),
                "curr_weight": round(curr_w, 2),
                "delta": round(curr_w - prev_w, 2),
            })

    # 换手率 = sum(|delta|) / 2
    # 除以 2 是因为每一份"卖出"都对应一份"买入"，避免双重计算
    total_turnover = total_abs_delta / 2.0
    is_drifted = total_turnover > threshold

    result = StyleDriftResult(
        fund_code=fund_code,
        current_quarter=current_quarter,
        prev_quarter=prev_quarter,
        total_turnover=round(total_turnover, 2),
        is_drifted=is_drifted,
        threshold=threshold,
        new_entries=new_entries,
        exits=exits,
        major_changes=major_changes,
    )

    logger.info(
        "风格漂移检测 %s: 换手率 %.1f%% (%s)",
        fund_code, total_turnover, "⚠️ 漂移" if is_drifted else "✅ 正常",
    )
    return result


# =====================================================================
# 函数 3: 底层相关性矩阵
# =====================================================================

def calculate_correlation_matrix(
    conn: sqlite3.Connection,
    fund_code_list: list[str],
    threshold: float = 0.3,
) -> dict[str, Any]:
    """
    底层相关性矩阵 — 防止买入"变种相关资产"。

    核心逻辑：
    1. JOIN holdings + stock_sector_mapping，按 sw_sector_l1 聚合行业权重向量
    2. Python 层计算余弦相似度（为什么不在 SQL 层？因为 SQLite 无向量运算，
       且持仓数据量小——每只基金最多 10 个行业，O(n²) 基金对的计算量也很小）
    3. 返回相似度矩阵 + 超阈值报警对

    Args:
        conn: SQLite 连接
        fund_code_list: 基金代码列表
        threshold: 报警阈值（默认 0.3，即 30% 行业权重相似度）

    Returns:
        dict with keys:
            "matrix": dict[str, dict[str, float]] — 两两相似度
            "alerts": list[CorrelationPair] — 超阈值报警对
    """
    if len(fund_code_list) < 2:
        return {"matrix": {}, "alerts": []}

    # 步骤 1: 查询每只基金的行业权重向量
    # JOIN holdings 和 stock_sector_mapping，按 sw_sector_l1 聚合
    fund_sector_vectors: dict[str, dict[str, float]] = {}

    for code in fund_code_list:
        sql = """
        SELECT
            COALESCE(sm.sw_sector_l1, '未分类') AS sector,
            SUM(COALESCE(h.weight_pct, 0)) AS total_weight
        FROM holdings h
        JOIN funds f ON h.fund_id = f.id
        LEFT JOIN stock_sector_mapping sm ON h.stock_code = sm.stock_code
        WHERE f.code = ?
          -- 取最新一期持仓（snapshot_date 最大的那批）
          AND h.snapshot_date = (
              SELECT MAX(h2.snapshot_date)
              FROM holdings h2
              JOIN funds f2 ON h2.fund_id = f2.id
              WHERE f2.code = ?
          )
        GROUP BY sector
        """
        try:
            rows = conn.execute(sql, (code, code)).fetchall()
        except sqlite3.Error as e:
            logger.warning("查询 %s 行业权重向量失败: %s", code, e)
            continue

        if rows:
            vector = {row[0]: float(row[1]) for row in rows}
            fund_sector_vectors[code] = vector

    # 步骤 2: 计算两两余弦相似度
    codes = list(fund_sector_vectors.keys())
    matrix: dict[str, dict[str, float]] = {}
    alerts: list[CorrelationPair] = []

    for i, code_a in enumerate(codes):
        matrix[code_a] = {}
        vec_a = fund_sector_vectors[code_a]

        for j, code_b in enumerate(codes):
            if i == j:
                matrix[code_a][code_b] = 1.0
                continue
            if j < i:
                # 对称矩阵，直接复制
                matrix[code_a][code_b] = matrix[code_b][code_a]
                continue

            vec_b = fund_sector_vectors[code_b]
            similarity = _cosine_similarity(vec_a, vec_b)
            matrix[code_a][code_b] = round(similarity, 4)

            if similarity >= threshold:
                alerts.append(CorrelationPair(
                    fund_a=code_a,
                    fund_b=code_b,
                    similarity=round(similarity, 4),
                    is_alert=True,
                ))

    # 填充对称侧
    for code_a in codes:
        for code_b in codes:
            if code_b not in matrix.get(code_a, {}):
                matrix.setdefault(code_a, {})[code_b] = matrix.get(code_b, {}).get(code_a, 0.0)

    logger.info(
        "相关性矩阵计算完成: %d 只基金, %d 个超阈值报警对",
        len(codes), len(alerts),
    )

    return {"matrix": matrix, "alerts": alerts}


def _cosine_similarity(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
    """
    计算两个稀疏向量的余弦相似度。

    向量表示为 {维度名: 值} 的 dict（稀疏表示，缺失维度视为 0）。
    余弦相似度 = A·B / (|A| × |B|)

    为什么用 dict 而非 numpy array？
    因为行业维度不固定（不同基金可能覆盖不同行业），
    dict 的稀疏表示比固定长度 array 更自然。
    """
    # 所有出现过的维度
    all_keys = set(vec_a.keys()) | set(vec_b.keys())

    dot_product = 0.0
    norm_a = 0.0
    norm_b = 0.0

    for key in all_keys:
        a = vec_a.get(key, 0.0)
        b = vec_b.get(key, 0.0)
        dot_product += a * b
        norm_a += a * a
        norm_b += b * b

    # 防止除零（某只基金完全没有持仓数据时）
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot_product / (math.sqrt(norm_a) * math.sqrt(norm_b))
