"""
Markdown 报告生成器。

将筛选结果格式化为结构化的 Markdown 文件，
同时附带 LLM 分析提示词，方便用户直接拖进 AI Studio / Claude 进行深度分析。

输出结构：
1. 筛选概览（各市场通过率）
2. 按市场分组的基金明细（按 MA 差值降序排列 — 趋势最强的排最前）
3. LLM 分析提示词模板
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fund_screener.models import FundInfo, Market, ScreeningSummary


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
    lines.append("---")
    lines.append("")

    # ---- 按市场分组输出 ----
    market_order = [Market.US, Market.CN, Market.HK]  # 美股优先
    market_emojis = {Market.CN: "CN", Market.US: "US", Market.HK: "HK"}

    for market in market_order:
        market_funds = [f for f in funds if f.market == market]
        if not market_funds:
            continue

        # 按 MA 差值降序（趋势最强的排最前）
        market_funds.sort(key=lambda f: f.ma_diff_pct, reverse=True)

        label = market_labels.get(market, market.value)
        emoji = market_emojis.get(market, "")
        lines.append(f"## [{emoji}] {label} (共 {len(market_funds)} 只)")
        lines.append("")

        for i, fund in enumerate(market_funds, 1):
            lines.append(f"### {i}. {fund.name} ({fund.code})")
            lines.append("")
            lines.append(
                f"- **最新净值/价格**: {fund.nav:.4f} | "
                f"**MA{ma_short_period}**: {fund.ma_short:.4f} | "
                f"**MA{ma_long_period}**: {fund.ma_long:.4f} | "
                f"**差值**: {fund.ma_diff_pct:+.2f}%"
            )

            # 当日涨跌幅
            if fund.daily_change_pct is not None:
                lines.append(f"- **当日涨跌**: {fund.daily_change_pct:+.2f}%")

            # 多周期走势
            if fund.trend_stats is not None:
                parts: list[str] = []
                labels = [
                    ("1周", fund.trend_stats.change_1w),
                    ("1月", fund.trend_stats.change_1m),
                    ("3月", fund.trend_stats.change_3m),
                    ("6月", fund.trend_stats.change_6m),
                    ("1年", fund.trend_stats.change_1y),
                ]
                for period_label, val in labels:
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
                lines.append("#### Top 持仓")
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
                lines.append("#### 行业分布")
                lines.append("| 行业 | 占比 |")
                lines.append("|------|------|")
                for s in fund.sector_exposure[:10]:
                    lines.append(f"| {s.sector} | {s.weight_pct:.2f}% |")
                lines.append("")

            lines.append("---")
            lines.append("")

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
