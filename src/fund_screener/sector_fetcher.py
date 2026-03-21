"""
申万行业映射获取器 — 将全 A 股按申万一级行业分类。

数据源：ak.stock_board_industry_name_sw()（申万行业分类）
用途：为 OLAP 相关性矩阵提供行业维度的"底层穿透"能力。

规则引擎：
- HARD_TECH: 硬科技赛道（电子/计算机/通信/军工/电力设备）
- RESOURCE: 资源类赛道（煤炭/石油石化/有色/钢铁/基础化工）
"""

from __future__ import annotations

import logging
from typing import Any

from fund_screener.storage import DataStore

logger = logging.getLogger("fund_screener.sector_fetcher")

# 硬科技赛道关键词集合
HARD_TECH_SECTORS: frozenset[str] = frozenset({
    "电子", "计算机", "通信", "国防军工", "电力设备",
})

# 资源类赛道关键词集合
RESOURCE_SECTORS: frozenset[str] = frozenset({
    "煤炭", "石油石化", "有色金属", "钢铁", "基础化工",
})


def fetch_and_persist_sector_mapping(store: DataStore) -> int:
    """
    全量获取申万行业分类并持久化到 stock_sector_mapping 表。

    流程：
    1. 调用 ak.stock_board_industry_name_sw() 获取所有申万行业
    2. 对每个行业，调用 ak.stock_board_industry_cons_sw() 获取成分股
    3. 用规则引擎标记 is_hard_tech / is_resource
    4. 批量写入 stock_sector_mapping 表

    Returns:
        成功写入的映射条数
    """
    import akshare as ak
    import time

    # 步骤 1: 获取所有申万一级行业列表
    try:
        industry_df = ak.stock_board_industry_name_sw()
    except Exception as e:
        logger.error("获取申万行业列表失败: %s", e)
        return 0

    if industry_df is None or industry_df.empty:
        logger.warning("申万行业列表为空")
        return 0

    # 识别行业名称列
    name_col = None
    for col in industry_df.columns:
        col_str = str(col)
        if "行业" in col_str or "名称" in col_str or "板块" in col_str:
            name_col = col
            break
    if name_col is None and len(industry_df.columns) >= 1:
        name_col = industry_df.columns[0]

    if name_col is None:
        logger.error("申万行业列表列名无法识别: %s", list(industry_df.columns))
        return 0

    industries = [str(row[name_col]).strip() for _, row in industry_df.iterrows()]
    logger.info("获取到 %d 个申万一级行业", len(industries))

    # 步骤 2: 对每个行业获取成分股
    all_mappings: list[dict[str, Any]] = []
    for industry in industries:
        is_hard_tech = industry in HARD_TECH_SECTORS
        is_resource = industry in RESOURCE_SECTORS

        try:
            time.sleep(0.3)  # 限速，防止被东财封 IP
            cons_df = ak.stock_board_industry_cons_sw(symbol=industry)
        except Exception as e:
            logger.warning("获取申万行业 '%s' 成分股失败: %s", industry, e)
            continue

        if cons_df is None or cons_df.empty:
            continue

        # 识别代码列和名称列
        code_col = None
        stock_name_col = None
        for col in cons_df.columns:
            col_str = str(col)
            if "代码" in col_str:
                code_col = col
            elif "名称" in col_str or "简称" in col_str:
                stock_name_col = col

        if code_col is None:
            continue

        for _, row in cons_df.iterrows():
            stock_code = str(row[code_col]).strip()
            stock_name = str(row[stock_name_col]).strip() if stock_name_col else ""

            all_mappings.append({
                "stock_code": stock_code,
                "stock_name": stock_name,
                "sw_sector_l1": industry,
                "is_hard_tech": is_hard_tech,
                "is_resource": is_resource,
            })

        logger.debug("行业 '%s': %d 只成分股", industry, len(cons_df))

    # 步骤 3: 批量写入数据库
    if all_mappings:
        store.persist_sector_mapping(all_mappings)
        logger.info("申万行业映射全量更新完成: %d 条", len(all_mappings))

    return len(all_mappings)
