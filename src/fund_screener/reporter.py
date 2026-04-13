"""
Markdown 报告生成器。

将筛选结果格式化为结构化的 Markdown 文件，
同时附带 LLM 分析提示词，方便用户直接拖进 AI Studio / Claude 进行深度分析。

输出结构：
1. 筛选概览（各市场通过率 + CN 市场申购状态统计）
2. 按市场分组的基金明细
   - CN 市场：按申购状态分三组（可正常申购 → 限额申购 → 暂停申购）
   - US/HK 市场：按 MA 差值降序
3. LLM 分析提示词模板

V3 改动（申购限额标注）：
- CN 市场报告按申购状态分组展示，优质限购基金也能被发现
- 分组阈值：>= 1e8（1 亿）视为无限制，> 0 且 < 1e8 为限额，= 0 为暂停
- US/HK 市场不涉及申购限额，保持原有排序
"""

from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path

from fund_screener.models import FundInfo, Market, ScreeningSummary, ScoredFund

# 申购状态分组阈值（元）
# >= 1e8（1 亿）视为"无限制"（东方财富用 1e11 表示无限制，1e8 是保守分界线）
_PURCHASE_LIMIT_NORMAL_THRESHOLD = 1e8


def generate_report(
    funds: list[FundInfo],
    summaries: list[ScreeningSummary],
    ma_short_period: int = 20,
    ma_long_period: int = 60,
    output_path: str | Path = "output/fund_report.md",
) -> Path:
    """
    生成完整的 Markdown 筛选报告。

    Args:
        funds: 通过筛选的所有基金列表
        summaries: 各市场的筛选统计
        ma_short_period: 短期均线周期
        ma_long_period: 长期均线周期
        output_path: 输出文件路径

    Returns:
        报告文件的绝对路径
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines: list[str] = []

    # ---- 标题 ----
    lines.append(f"# 基金/ETF 趋势筛选报告")
    lines.append(f"> 生成时间: {now} | 筛选条件: MA{ma_short_period} > MA{ma_long_period}")
    lines.append("")

    # ---- 筛选概览 ----
    lines.append("## 筛选概览")
    lines.append("")

    market_labels = {Market.CN: "A股公募基金", Market.US: "美股 ETF", Market.HK: "港股 ETF"}

    for summary in summaries:
        label = market_labels.get(summary.market, summary.market.value)
        lines.append(
            f"- **{label}**: 通过 {summary.total_passed}/{summary.total_scanned} 只 "
            f"(通过率 {summary.pass_rate:.1f}%)"
        )
    lines.append("")

    total_passed = sum(s.total_passed for s in summaries)
    total_scanned = sum(s.total_scanned for s in summaries)
    lines.append(f"**全市场合计**: {total_passed}/{total_scanned} 只基金处于上涨趋势")
    lines.append("")

    # CN 市场申购状态统计（如果有标注数据）
    cn_funds = [f for f in funds if f.market == Market.CN]
    if cn_funds:
        normal, limited, suspended, unknown = _classify_by_purchase(cn_funds)
        lines.append("**A股申购状态分布**:")
        lines.append(f"- 可正常申购: {len(normal)} 只")
        lines.append(f"- 限额申购: {len(limited)} 只")
        lines.append(f"- 暂停申购: {len(suspended)} 只")
        lines.append(f"- 状态未知: {len(unknown)} 只")
        lines.append("")

    lines.append("---")
    lines.append("")

    # ---- 按市场分组输出 ----
    market_order = [Market.US, Market.CN, Market.HK]  # 美股优先
    market_emojis = {Market.CN: "CN", Market.US: "US", Market.HK: "HK"}

    for market in market_order:
        market_funds = [f for f in funds if f.market == market]
        if not market_funds:
            continue

        label = market_labels.get(market, market.value)
        emoji = market_emojis.get(market, "")

        # CN 市场：按申购状态分组展示
        if market == Market.CN:
            normal, limited, suspended, unknown = _classify_by_purchase(market_funds)
            lines.append(f"## [{emoji}] {label} (共 {len(market_funds)} 只)")
            lines.append("")

            # 全局序号计数器（跨分组连续编号）
            counter = 0

            if normal:
                lines.append(f"### 一、可正常申购 (日限额 >= 1 亿，共 {len(normal)} 只)")
                lines.append("")
                normal.sort(key=lambda f: f.ma_diff_pct, reverse=True)
                for fund in normal:
                    counter += 1
                    _render_fund_detail(lines, fund, counter, ma_short_period, ma_long_period)

            if limited:
                lines.append(f"### 二、限额申购 (0 < 日限额 < 1 亿，共 {len(limited)} 只)")
                lines.append("")
                limited.sort(key=lambda f: f.ma_diff_pct, reverse=True)
                for fund in limited:
                    counter += 1
                    _render_fund_detail(lines, fund, counter, ma_short_period, ma_long_period)

            if suspended:
                lines.append(f"### 三、暂停申购 (日限额 = 0，共 {len(suspended)} 只)")
                lines.append("")
                suspended.sort(key=lambda f: f.ma_diff_pct, reverse=True)
                for fund in suspended:
                    counter += 1
                    _render_fund_detail(lines, fund, counter, ma_short_period, ma_long_period)

            if unknown:
                lines.append(f"### 四、申购状态未知 (共 {len(unknown)} 只)")
                lines.append("")
                unknown.sort(key=lambda f: f.ma_diff_pct, reverse=True)
                for fund in unknown:
                    counter += 1
                    _render_fund_detail(lines, fund, counter, ma_short_period, ma_long_period)
        else:
            # US/HK 市场：按 MA 差值降序（无申购限额概念）
            market_funds.sort(key=lambda f: f.ma_diff_pct, reverse=True)
            lines.append(f"## [{emoji}] {label} (共 {len(market_funds)} 只)")
            lines.append("")

            for i, fund in enumerate(market_funds, 1):
                _render_fund_detail(lines, fund, i, ma_short_period, ma_long_period)

    # ---- LLM 分析提示词 ----
    lines.append("## LLM 深度分析提示词")
    lines.append("")
    lines.append("以下提示词可直接复制粘贴到 Claude / Gemini 中使用：")
    lines.append("")
    lines.append("```")
    lines.append(_get_llm_prompt(ma_short_period, ma_long_period))
    lines.append("```")
    lines.append("")

    # 写入文件
    content = "\n".join(lines)
    output_path.write_text(content, encoding="utf-8")

    return output_path.resolve()


def _classify_by_purchase(
    funds: list[FundInfo],
) -> tuple[list[FundInfo], list[FundInfo], list[FundInfo], list[FundInfo]]:
    """
    按申购状态将基金分为四组。

    分组逻辑：
    - 正常：purchase_limit >= 1e8（1 亿）或 purchase_limit 非常大（东财用 1e11 表示无限制）
    - 限额：0 < purchase_limit < 1e8
    - 暂停：purchase_limit == 0
    - 未知：purchase_limit is None 或 < 0（获取失败）或 NaN

    Returns:
        (正常申购, 限额申购, 暂停申购, 状态未知) 四个列表
    """
    normal: list[FundInfo] = []
    limited: list[FundInfo] = []
    suspended: list[FundInfo] = []
    unknown: list[FundInfo] = []

    for fund in funds:
        limit = fund.purchase_limit
        if limit is None or limit < 0 or (isinstance(limit, float) and math.isnan(limit)):
            unknown.append(fund)
        elif limit == 0:
            suspended.append(fund)
        elif limit >= _PURCHASE_LIMIT_NORMAL_THRESHOLD:
            normal.append(fund)
        else:
            limited.append(fund)

    return normal, limited, suspended, unknown


def _format_purchase_limit(limit: float | None) -> str:
    """
    将日累计限定金额格式化为人类可读字符串。

    Examples:
        1e11 → "无限制"
        1e4  → "1.00 万"
        1e8  → "1.00 亿"
        0    → "暂停"
        None → "未知"
    """
    if limit is None or limit < 0 or (isinstance(limit, float) and math.isnan(limit)):
        return "未知"
    if limit == 0:
        return "暂停"
    if limit >= _PURCHASE_LIMIT_NORMAL_THRESHOLD:
        if limit >= 1e10:
            return "无限制"
        return f"{limit / 1e8:.2f} 亿"
    if limit >= 1e4:
        return f"{limit / 1e4:.2f} 万"
    return f"{limit:.0f} 元"


def _render_fund_detail(
    lines: list[str],
    fund: FundInfo,
    index: int,
    ma_short_period: int,
    ma_long_period: int,
) -> None:
    """
    渲染单只基金的详细信息到 lines 列表中。

    抽取为独立函数避免 CN/US/HK 三个分支重复代码。
    """
    lines.append(f"#### {index}. {fund.name} ({fund.code})")
    lines.append("")

    ma_line = (
        f"- **最新净值/价格**: {fund.nav:.4f} | "
        f"**MA{ma_short_period}**: {fund.ma_short:.4f} | "
        f"**MA{ma_long_period}**: {fund.ma_long:.4f} | "
        f"**差值**: {fund.ma_diff_pct:+.2f}%"
    )
    lines.append(ma_line)

    # 申购限额标注（仅 CN 市场有此数据）
    if fund.purchase_limit is not None or fund.purchase_status_text is not None:
        limit_str = _format_purchase_limit(fund.purchase_limit)
        status_str = fund.purchase_status_text or "未知"
        lines.append(f"- **申购状态**: {status_str} | **日限额**: {limit_str}")

    # 当日涨跌幅
    if fund.daily_change_pct is not None:
        lines.append(f"- **当日涨跌**: {fund.daily_change_pct:+.2f}%")

    # 多周期走势
    if fund.trend_stats is not None:
        parts: list[str] = []
        period_labels = [
            ("1周", fund.trend_stats.change_1w),
            ("1月", fund.trend_stats.change_1m),
            ("3月", fund.trend_stats.change_3m),
            ("6月", fund.trend_stats.change_6m),
            ("1年", fund.trend_stats.change_1y),
        ]
        for period_label, val in period_labels:
            if val is not None:
                parts.append(f"{period_label} {val:+.2f}%")
            else:
                parts.append(f"{period_label} N/A")
        lines.append(f"- **走势**: {' | '.join(parts)}")

    if fund.holdings_date:
        lines.append(f"- **持仓报告期**: {fund.holdings_date}")

    lines.append(f"- **数据日期**: {fund.data_date}")
    lines.append("")

    # Top Holdings 表格
    if fund.top_holdings:
        lines.append("##### Top 持仓")
        lines.append("| 排名 | 股票代码 | 股票名称 | 持仓占比 |")
        lines.append("|------|----------|----------|----------|")
        for j, h in enumerate(fund.top_holdings[:10], 1):
            weight_str = f"{h.weight_pct:.2f}%" if h.weight_pct is not None else "N/A"
            lines.append(
                f"| {j} | {h.stock_code} | {h.stock_name} | {weight_str} |"
            )
        lines.append("")

    # 行业分布表格
    if fund.sector_exposure:
        lines.append("##### 行业分布")
        lines.append("| 行业 | 占比 |")
        lines.append("|------|------|")
        for s in fund.sector_exposure[:10]:
            lines.append(f"| {s.sector} | {s.weight_pct:.2f}% |")
        lines.append("")

    lines.append("---")
    lines.append("")


def _get_llm_prompt(ma_short: int, ma_long: int) -> str:
    """生成 LLM 分析提示词模板。"""
    return f"""System Context:
你是一个理性的、基于第一性原理的量化策略分析师。你只相信客观数据，拒绝任何主观预测和情绪化分析。

Input Data:
上面是我通过 Python 代码初步筛选出的，目前在技术面上完全符合"右侧上涨趋势"（MA{ma_short} > MA{ma_long}）的基金/ETF 池及其重仓成分股。

Task Execution:
请你基于以上数据，完成以下分析并制定最终执行方案：

1. 趋势强度排名：
   按 MA 差值百分比排序，找出趋势最强的 Top 10 标的，分析它们为什么这么强。

2. 资金抱团穿透：
   交叉对比这些基金/ETF 的重仓股成分，找出被重复重仓最多的"底层股票"或"行业板块"。
   不要讲废话，直接告诉我资金流向了哪里。

3. 风险隔离标的选拔：
   如果我只能买 3 只基金/ETF 来跟踪这波右侧趋势，要求：
   - 底层重仓股重合度最低（分散行业风险）
   - 覆盖不同市场（如可能，分散地域风险）
   - 趋势强度排名靠前
   请选出这 3 只，并用数据证明你的选择。

4. 止损/离场机械纪律：
   根据这 3 只标的的波动特性，给我制定一个无需思考的机械式止损指标。
   例如：当 MA{ma_short} 跌破 MA{ma_long} 时离场。

5. 风险提示：
   指出当前数据中你发现的任何潜在风险信号（如行业过度集中、估值泡沫迹象等）。

请以结构化的方式输出你的分析结果。"""


# =====================================================================
# V4: 量化打分报告
# =====================================================================


def generate_scored_report(
    scored_funds: list[ScoredFund],
    weights_desc: str,
    output_path: str | Path = "output/scored_report.md",
) -> Path:
    """
    生成量化打分排行榜 Markdown 报告。

    输出内容：
    1. 打分概览（候选池大小、权重配置、Top N 截取数）
    2. 排行榜摘要表格（排名 / 代码 / 名称 / 总分 / 三因子原始值 / Z-Score）
    3. 每只基金的详细卡片（含持仓、行业分布、走势）
    4. LLM 分析提示词

    Args:
        scored_funds: 已排序的 ScoredFund 列表（由 scoring.score_funds 输出）
        weights_desc: 权重描述字符串（如 "动量40% + 回撤30% + 夏普30%"）
        output_path: 输出文件路径

    Returns:
        报告文件的绝对路径
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines: list[str] = []

    # ---- 标题 ----
    lines.append("# 量化打分排行榜")
    lines.append(f"> 生成时间: {now} | 权重: {weights_desc}")
    lines.append(f"> 候选基金: {len(scored_funds)} 只")
    lines.append("")

    if not scored_funds:
        lines.append("**无符合条件的基金。**")
        content = "\n".join(lines)
        output_path.write_text(content, encoding="utf-8")
        return output_path.resolve()

    # ---- 摘要排行表 ----
    lines.append("## 排行榜摘要")
    lines.append("")
    lines.append(
        "| # | 代码 | 名称 | 市场 | 总分 | 动量 | 回撤 | 夏普 | "
        "z动量 | z回撤 | z夏普 |"
    )
    lines.append(
        "|---|------|------|------|------|------|------|------|"
        "------|------|------|"
    )

    for sf in scored_funds:
        f = sf.fund
        m = sf.risk_metrics
        lines.append(
            f"| {sf.rank} | {f.code} | {f.name[:20]} | {f.market.value} | "
            f"{sf.composite_score:+.4f} | "
            f"{m.momentum:+.4f} | {m.max_drawdown:+.2%} | {m.sharpe:.2f} | "
            f"{sf.z_momentum:+.2f} | {sf.z_drawdown:+.2f} | {sf.z_sharpe:+.2f} |"
        )

    lines.append("")
    lines.append("---")
    lines.append("")

    # ---- 详细卡片 ----
    lines.append("## 详细分析")
    lines.append("")

    for sf in scored_funds:
        f = sf.fund
        m = sf.risk_metrics

        lines.append(f"### {sf.rank}. {f.name} ({f.code}) [{f.market.value}]")
        lines.append("")
        lines.append(
            f"- **综合得分**: {sf.composite_score:+.4f} | "
            f"**最新净值**: {f.nav:.4f}"
        )
        lines.append(
            f"- **趋势爆发力**: {m.momentum:+.4f} (z={sf.z_momentum:+.2f}) | "
            f"**最大回撤**: {m.max_drawdown:+.2%} (z={sf.z_drawdown:+.2f}) | "
            f"**夏普比率**: {m.sharpe:.2f} (z={sf.z_sharpe:+.2f})"
        )
        lines.append(f"- **数据天数**: {m.nav_count} | **数据日期**: {f.data_date}")

        # 走势
        if f.trend_stats is not None:
            parts: list[str] = []
            period_labels = [
                ("1周", f.trend_stats.change_1w),
                ("1月", f.trend_stats.change_1m),
                ("3月", f.trend_stats.change_3m),
                ("6月", f.trend_stats.change_6m),
                ("1年", f.trend_stats.change_1y),
            ]
            for label, val in period_labels:
                if val is not None:
                    parts.append(f"{label} {val:+.2f}%")
                else:
                    parts.append(f"{label} N/A")
            lines.append(f"- **走势**: {' | '.join(parts)}")

        # 申购状态
        if f.purchase_limit is not None or f.purchase_status_text is not None:
            limit_str = _format_purchase_limit(f.purchase_limit)
            status_str = f.purchase_status_text or "未知"
            lines.append(f"- **申购状态**: {status_str} | **日限额**: {limit_str}")

        lines.append("")

        # Top Holdings
        if f.top_holdings:
            lines.append("**Top 持仓**")
            lines.append("| 排名 | 股票代码 | 股票名称 | 占比 |")
            lines.append("|------|----------|----------|------|")
            for j, h in enumerate(f.top_holdings[:10], 1):
                w = f"{h.weight_pct:.2f}%" if h.weight_pct is not None else "N/A"
                lines.append(f"| {j} | {h.stock_code} | {h.stock_name} | {w} |")
            lines.append("")

        lines.append("---")
        lines.append("")

    # ---- LLM 提示词 ----
    lines.append("## LLM 深度分析提示词")
    lines.append("")
    lines.append("```")
    lines.append(_get_scored_llm_prompt(weights_desc))
    lines.append("```")

    content = "\n".join(lines)
    output_path.write_text(content, encoding="utf-8")
    return output_path.resolve()


def _get_scored_llm_prompt(weights_desc: str) -> str:
    """生成量化打分专用的 LLM 分析提示词。"""
    return f"""System Context:
你是一个理性的、基于第一性原理的量化策略分析师。你只相信客观数据，拒绝任何主观预测和情绪化分析。

Input Data:
上面是我通过 Python 量化打分引擎（{weights_desc}）筛选出的 Top N 基金/ETF 及其重仓成分股。
每只基金已标注：趋势爆发力（动量）、最大回撤、夏普比率、Z-Score 标准化分数、综合得分排名。

Task Execution:
1. 排行合理性审核：
   - Top 10 的得分分布是否存在断层？（如第 1 名远超第 2 名，可能是异常值）
   - 是否存在"高动量但高回撤"的危险标的？指出来。

2. 行业集中度穿透：
   - 交叉对比 Top 10 的重仓股，找出被重复重仓的"底层股票/行业板块"
   - 如果 Top 10 中超过 5 只集中在同一行业，发出行业集中度预警

3. 风险隔离组合推荐：
   如果我只能买 3 只来构建分散组合，要求：
   - 底层重仓股重合度最低
   - 覆盖不同市场/行业
   - 综合得分排名靠前
   选出并用数据证明选择。

4. 止损纪律：
   为推荐的 3 只标的各设一个机械式离场指标。

5. 风险提示：
   基于当前数据发现的潜在风险信号。

请以结构化方式输出。"""
