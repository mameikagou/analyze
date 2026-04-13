"""
复合量化打分引擎 — 多因子 Z-Score 标准化 + 加权排名。

设计哲学：
1. 打分层是纯计算，不访问网络、不调 API
2. 输入：(FundInfo, nav_series) 列表 + 权重配置
3. 输出：按 composite_score 降序排列的 ScoredFund 列表

流程（详见 specs/quant_scoring_spec.md）：
    原始基金池
    → QDII 名称二次过滤（剔除债基）
    → 对每只基金算三因子 RiskMetrics
    → Z-Score 标准化（回撤方向反转）
    → 加权求和 → 排名 → 截取 Top N
"""

from __future__ import annotations

import logging
import math

import pandas as pd

from fund_screener.config import ScoringWeights
from fund_screener.models import FundInfo, RiskMetrics, ScoredFund
from fund_screener.risk_metrics import max_drawdown, momentum_score, sharpe_ratio

logger = logging.getLogger("fund_screener.scoring")

# ---------------------------------------------------------------------------
# QDII 债基名称排除关键词
#
# 为什么用排除法而非包含法？见 specs/quant_scoring_spec.md §2.2
# 简言之：QDII 权益基金名称五花八门（纳斯达克/标普/科技/...），穷举不现实；
# 而 QDII 债基名称几乎全含"债"字，排除法误杀率低。
# ---------------------------------------------------------------------------
_QDII_BOND_KEYWORDS: frozenset[str] = frozenset({
    "债", "纯债", "利率", "增利", "信用", "收益债",
    "短债", "中短债", "超短债",
})


def _is_qdii_bond(fund_name: str) -> bool:
    """
    判断一只 QDII 基金是否为债券类（应被排除出打分池）。

    通过名称关键词匹配，命中任一关键词即判定为债基。
    仅对 QDII 基金调用，非 QDII 基金不应走此逻辑。
    """
    return any(kw in fund_name for kw in _QDII_BOND_KEYWORDS)


def _compute_z_scores(values: list[float]) -> list[float]:
    """
    对一组数值做 Z-Score 标准化。

    Z = (x - mean) / std

    处理边界情况：
    - 全部为 NaN → 返回全 0
    - std == 0（所有值相同）→ 返回全 0（该因子不贡献分数）
    - 单个 NaN 值 → 该位置返回 0（不惩罚也不奖励）
    """
    # 过滤出有效值计算统计量
    valid = [v for v in values if not math.isnan(v)]

    if len(valid) < 2:
        return [0.0] * len(values)

    mean = sum(valid) / len(valid)
    variance = sum((v - mean) ** 2 for v in valid) / (len(valid) - 1)
    std = math.sqrt(variance)

    if std == 0:
        return [0.0] * len(values)

    return [
        (v - mean) / std if not math.isnan(v) else 0.0
        for v in values
    ]


def score_funds(
    funds_with_nav: list[tuple[FundInfo, pd.DataFrame]],
    weights: ScoringWeights,
    top_n: int = 30,
    min_nav_days: int = 60,
    filter_qdii_bonds: bool = True,
) -> list[ScoredFund]:
    """
    复合量化打分 — 从原始基金池中选出 Top N。

    完整流程：
    1. QDII 名称二次过滤（可选）
    2. 数据充足性检查（nav_count >= min_nav_days）
    3. 对每只基金计算三因子 RiskMetrics
    4. 过滤掉三因子中有 NaN 的基金（数据不足以打分）
    5. Z-Score 标准化（回撤方向反转：乘 -1 后再标准化）
    6. 加权求和 → composite_score
    7. 降序排名 → 截取 Top N

    Args:
        funds_with_nav: 列表，每个元素是 (FundInfo, nav_df) 元组。
            nav_df 必须包含 "nav" 列，按日期升序排列。
        weights: 三因子权重配置
        top_n: 截取前 N 名
        min_nav_days: 最低数据量门槛
        filter_qdii_bonds: 是否过滤 QDII 债基（默认 True）

    Returns:
        按 composite_score 降序排列的 ScoredFund 列表（最多 top_n 条）

    踩坑预警：
    1. Z-Score 零标准差 → _compute_z_scores 已处理，返回全 0
    2. 回撤是负数 → 反转后再标准化（值大 = 回撤小 = 好）
    3. 权重之和不强制 == 1.0，允许实验性调整
    """
    # Step 1: QDII 名称二次过滤
    filtered: list[tuple[FundInfo, pd.DataFrame]] = []
    qdii_bond_count = 0

    for fund, nav_df in funds_with_nav:
        # QDII 债基过滤：仅对 QDII 类型基金执行
        if filter_qdii_bonds and "QDII" in fund.name.upper():
            # 名称里不一定有 QDII 字样，但 fund_types 过滤已确保只有 QDII 型进来
            # 这里对所有基金检查关键词，更保险
            pass

        if filter_qdii_bonds and _is_qdii_bond(fund.name):
            qdii_bond_count += 1
            logger.debug("QDII 债基过滤: %s (%s)", fund.name, fund.code)
            continue

        filtered.append((fund, nav_df))

    if qdii_bond_count > 0:
        logger.info("QDII 债基过滤: 剔除 %d 只", qdii_bond_count)

    # Step 2 + 3: 计算三因子，同时检查数据充足性
    candidates: list[tuple[FundInfo, RiskMetrics]] = []

    for fund, nav_df in filtered:
        if nav_df.empty or len(nav_df) < min_nav_days:
            logger.debug(
                "数据不足跳过: %s (%s), nav_count=%d < %d",
                fund.name, fund.code, len(nav_df), min_nav_days,
            )
            continue

        nav = nav_df["nav"].astype(float)

        m = momentum_score(nav)
        d = max_drawdown(nav)
        s = sharpe_ratio(nav)

        # Step 4: 三因子中任一为 NaN → 数据有问题，不参与打分
        if math.isnan(m) or math.isnan(d) or math.isnan(s):
            logger.debug(
                "因子计算异常跳过: %s (%s), momentum=%.4f, drawdown=%.4f, sharpe=%.4f",
                fund.name, fund.code, m, d, s,
            )
            continue

        metrics = RiskMetrics(
            momentum=round(m, 6),
            max_drawdown=round(d, 6),
            sharpe=round(s, 4),
            nav_count=len(nav),
        )
        candidates.append((fund, metrics))

    logger.info(
        "打分候选池: %d 只基金 (原始 %d, QDII 债基 -%d, 数据/因子不足 -%d)",
        len(candidates),
        len(funds_with_nav),
        qdii_bond_count,
        len(filtered) - len(candidates),
    )

    if not candidates:
        return []

    # Step 5: Z-Score 标准化
    momentums = [m.momentum for _, m in candidates]
    # 回撤方向反转：max_drawdown 是负数，乘 -1 后"值大 = 回撤小 = 好"
    drawdowns_inverted = [-m.max_drawdown for _, m in candidates]
    sharpes = [m.sharpe for _, m in candidates]

    z_momentums = _compute_z_scores(momentums)
    z_drawdowns = _compute_z_scores(drawdowns_inverted)
    z_sharpes = _compute_z_scores(sharpes)

    # Step 6: 加权求和
    scored: list[ScoredFund] = []

    for i, (fund, metrics) in enumerate(candidates):
        composite = (
            weights.momentum * z_momentums[i]
            + weights.drawdown * z_drawdowns[i]
            + weights.sharpe * z_sharpes[i]
        )

        scored.append(ScoredFund(
            fund=fund,
            risk_metrics=metrics,
            z_momentum=round(z_momentums[i], 4),
            z_drawdown=round(z_drawdowns[i], 4),
            z_sharpe=round(z_sharpes[i], 4),
            composite_score=round(composite, 4),
            rank=0,  # 排名在排序后填充
        ))

    # Step 7: 降序排名 + 截取 Top N
    scored.sort(key=lambda sf: sf.composite_score, reverse=True)

    for rank, sf in enumerate(scored, 1):
        sf.rank = rank

    result = scored[:top_n]

    if result:
        logger.info(
            "打分完成: Top %d (最高分 %.4f, 最低分 %.4f)",
            len(result),
            result[0].composite_score,
            result[-1].composite_score,
        )

    return result
