"""
CLI 入口 — 编排全流程的调度中心。

V2 架构升级：从 @click.command() 重构为 @click.group()，
用 invoke_without_command=True 保持向后兼容。

原有用法完全不变：
    uv run fund-screener --market all --verbose
    uv run fund-screener --market us --no-cache

新增子命令：
    uv run fund-screener scan-momentum --date 2026-03-20
    uv run fund-screener detect-drift --fund-code 005827 ...
    uv run fund-screener correlation --funds 005827,016873
    uv run fund-screener bulk-fetch --market cn --concurrency 10
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import click
from tqdm import tqdm

from fund_screener.cache import FileCache
from fund_screener.config import AppConfig, load_config
from fund_screener.fetchers.base import BaseFetcher
from fund_screener.fetchers.cn_fund import CNFundFetcher
from fund_screener.fetchers.hk_etf import HKETFFetcher
from fund_screener.fetchers.us_etf import USETFFetcher
from fund_screener.models import FundInfo, Market, ScreeningSummary
from fund_screener.reporter import generate_report
from fund_screener.screener import calculate_trend_stats, screen_fund
from fund_screener.storage import DataStore

logger = logging.getLogger("fund_screener")


def _setup_logging(verbose: bool) -> None:
    """配置日志格式和级别。"""
    level = logging.DEBUG if verbose else logging.INFO
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    ))
    root_logger = logging.getLogger("fund_screener")
    root_logger.setLevel(level)
    # 避免重复添加 handler
    if not root_logger.handlers:
        root_logger.addHandler(handler)


def _create_fetchers(
    config: AppConfig,
    cache: FileCache,
    markets: list[Market],
) -> dict[Market, BaseFetcher]:
    """
    根据配置创建各市场的 fetcher 实例。

    策略模式的威力：新增市场只需在这里加一个 elif，
    不需要改任何其他代码。
    """
    fetchers: dict[Market, BaseFetcher] = {}

    if Market.CN in markets and config.cn_fund.enabled:
        fetchers[Market.CN] = CNFundFetcher(
            cache=cache,
            rate_limit_config=config.rate_limit,
            cn_config=config.cn_fund,
        )

    if Market.US in markets and config.us_etf.enabled:
        fetchers[Market.US] = USETFFetcher(
            cache=cache,
            rate_limit_config=config.rate_limit,
            us_config=config.us_etf,
        )

    if Market.HK in markets and config.hk_etf.enabled:
        fetchers[Market.HK] = HKETFFetcher(
            cache=cache,
            rate_limit_config=config.rate_limit,
            hk_config=config.hk_etf,
        )

    return fetchers


def _process_market(
    fetcher: BaseFetcher,
    config: AppConfig,
    store: DataStore | None = None,
) -> tuple[list[FundInfo], ScreeningSummary]:
    """
    处理单个市场的完整流程：获取列表 → 筛选 → 获取持仓。

    这是整个工具的核心编排逻辑。

    Returns:
        (通过筛选的基金列表, 筛选统计)
    """
    market = fetcher.market
    market_labels = {Market.CN: "A股基金", Market.US: "美股 ETF", Market.HK: "港股 ETF"}
    label = market_labels.get(market, market.value)

    logger.info("=" * 50)
    logger.info("开始处理: %s", label)

    # Step 0: A 股市场预加载当日涨跌幅映射表
    cn_daily_map: dict[str, float] = {}
    if market == Market.CN:
        try:
            import akshare as ak

            logger.info("正在获取 A 股当日涨跌幅数据...")
            daily_df = ak.fund_open_fund_daily_em()
            if daily_df is not None and not daily_df.empty:
                code_col: str | None = None
                change_col: str | None = None
                for col in daily_df.columns:
                    col_str = str(col)
                    if "代码" in col_str:
                        code_col = col
                    elif "日增长率" in col_str:
                        change_col = col

                if code_col is not None and change_col is not None:
                    for _, row in daily_df.iterrows():
                        try:
                            cn_daily_map[str(row[code_col]).strip()] = float(row[change_col])
                        except (ValueError, TypeError):
                            pass
                    logger.info("A 股当日涨跌幅加载完成: %d 只基金", len(cn_daily_map))
                else:
                    logger.warning("A 股当日涨跌幅数据列名不匹配: %s", list(daily_df.columns))
        except Exception as e:
            logger.warning("获取 A 股当日涨跌幅数据失败（不影响主流程）: %s", e)

    # Step 1: 获取基金列表
    fund_list = fetcher.fetch_fund_list()
    if not fund_list:
        logger.warning("%s 基金列表为空，跳过", label)
        return [], ScreeningSummary(
            market=market, total_scanned=0, total_passed=0, pass_rate=0.0,
        )

    # 注入点 1: 持久化基金列表到数据湖
    if store is not None:
        store.persist_fund_list(market.value, fund_list)

    logger.info("%s 共 %d 只基金，开始筛选...", label, len(fund_list))

    # Step 2: 遍历每只基金，拉净值 → MA 筛选
    passed_funds: list[FundInfo] = []
    total_scanned = 0

    for fund_info in tqdm(fund_list, desc=f"{label} MA筛选", unit="只"):
        code = fund_info["code"]
        name = fund_info.get("name", code)
        total_scanned += 1

        try:
            # 拉净值历史
            nav_df = fetcher.fetch_nav_history(code, days=config.lookback_days)
            if nav_df.empty:
                continue

            # 注入点 2: 全量持久化净值历史（MA 筛选之前，不管是否通过都存）
            if store is not None:
                store.persist_nav_records(market.value, code, nav_df)

            # V2 注入点: 持久化基金详情
            if store is not None:
                try:
                    detail = fetcher.fetch_fund_detail(code)
                    if detail:
                        store.persist_fund_detail(market.value, code, detail)
                except Exception as e:
                    logger.debug("获取 %s 基金详情失败（不影响主流程）: %s", code, e)

            # MA 筛选
            result = screen_fund(nav_df, config.ma_short, config.ma_long)
            if result is None or not result.passed:
                continue

            # 通过筛选！获取持仓和行业分布
            logger.debug("通过: %s (%s), MA差值: %+.2f%%", name, code, result.ma_diff_pct)

            holdings = fetcher.fetch_holdings(code)
            sectors = fetcher.fetch_sector_exposure(code)

            # 注入点 3: 持久化持仓和行业分布
            if store is not None:
                store.persist_holdings(market.value, code, holdings, sectors)

            # 计算多周期涨跌幅（从已有 nav_df 直接算，零额外请求）
            trend_stats = calculate_trend_stats(nav_df)

            # 计算当日涨跌幅
            daily_change: float | None = None
            if market == Market.CN:
                daily_change = cn_daily_map.get(code)
            else:
                if len(nav_df) >= 2:
                    today_nav = float(nav_df["nav"].iloc[-1])
                    yesterday_nav = float(nav_df["nav"].iloc[-2])
                    if yesterday_nav != 0:
                        daily_change = round(
                            (today_nav - yesterday_nav) / yesterday_nav * 100, 2,
                        )

            # 获取最新净值
            latest_nav = float(nav_df["nav"].iloc[-1])
            latest_date = nav_df["date"].iloc[-1]
            if hasattr(latest_date, "date"):
                latest_date = latest_date.date()
            elif isinstance(latest_date, str):
                from datetime import datetime
                latest_date = datetime.strptime(latest_date, "%Y-%m-%d").date()

            fund = FundInfo(
                code=code,
                name=name,
                market=market,
                nav=latest_nav,
                ma_short=result.ma_short,
                ma_long=result.ma_long,
                ma_diff_pct=result.ma_diff_pct,
                top_holdings=holdings,
                sector_exposure=sectors,
                daily_change_pct=daily_change,
                trend_stats=trend_stats,
                data_date=latest_date,
            )
            # 注入点 4: 持久化筛选结果
            if store is not None:
                store.persist_screening_result(fund)

            passed_funds.append(fund)

        except Exception as e:
            logger.warning("处理基金 %s (%s) 时出错: %s", name, code, e)
            continue

    # 统计
    pass_rate = (len(passed_funds) / total_scanned * 100) if total_scanned > 0 else 0.0
    summary = ScreeningSummary(
        market=market,
        total_scanned=total_scanned,
        total_passed=len(passed_funds),
        pass_rate=round(pass_rate, 1),
    )

    logger.info(
        "%s 筛选完成: %d/%d 只通过 (%.1f%%)",
        label, len(passed_funds), total_scanned, pass_rate,
    )

    return passed_funds, summary


def _print_db_stats(config: AppConfig) -> None:
    """
    打印数据湖统计信息 — 直观展示数据湖全貌。

    把枯燥的 SQL 查询结果格式化成人类友好的表格输出。
    """
    db_path = config.db_path
    if not Path(db_path).exists():
        click.echo(f"数据库文件不存在: {db_path}")
        click.echo("请先运行一次筛选（不带 --no-store）来初始化数据湖。")
        return

    with DataStore(db_path) as store:
        stats = store.get_stats()

    click.echo()
    click.echo("=" * 55)
    click.echo("  数据湖统计  ".center(55, "="))
    click.echo("=" * 55)
    click.echo(f"  数据库路径: {db_path}")
    click.echo(f"  文件大小:   {stats.get('db_size_mb', 0)} MB")
    click.echo()

    # 各表记录数
    click.echo("--- 表记录数 ---")
    table_names = {
        "funds_count": "基金维度表 (funds)",
        "nav_records_count": "净值时序 (nav_records)",
        "holdings_count": "持仓快照 (holdings)",
        "sector_exposure_count": "行业分布 (sector_exposure)",
        "screening_results_count": "筛选结果 (screening_results)",
        "stock_sector_mapping_count": "申万行业映射 (stock_sector_mapping)",
    }
    for key, label in table_names.items():
        click.echo(f"  {label:<40s} {stats.get(key, 0):>8,} 条")
    click.echo()

    # 按市场维度
    funds_by_market: dict[str, int] = stats.get("funds_by_market", {})
    nav_by_market: dict[str, int] = stats.get("nav_by_market", {})
    if funds_by_market:
        click.echo("--- 按市场统计 ---")
        click.echo(f"  {'市场':<10s} {'基金数':>8s} {'净值记录数':>12s}")
        click.echo(f"  {'----':<10s} {'------':>8s} {'----------':>12s}")
        for mkt in sorted(set(list(funds_by_market.keys()) + list(nav_by_market.keys()))):
            f_count = funds_by_market.get(mkt, 0)
            n_count = nav_by_market.get(mkt, 0)
            click.echo(f"  {mkt:<10s} {f_count:>8,} {n_count:>12,}")
        click.echo()

    # 净值时间范围
    date_min, date_max = stats.get("nav_date_range", (None, None))
    if date_min:
        click.echo("--- 净值数据时间范围 ---")
        click.echo(f"  最早: {date_min}")
        click.echo(f"  最新: {date_max}")
        click.echo()

    # 最近筛选记录
    recent: list[dict[str, object]] = stats.get("recent_screenings", [])
    if recent:
        click.echo("--- 最近 5 次筛选 ---")
        click.echo(f"  {'日期':<14s} {'通过数量':>8s}")
        click.echo(f"  {'----':<14s} {'------':>8s}")
        for entry in recent:
            click.echo(f"  {entry['date']:<14s} {entry['count']:>8,} 只")
        click.echo()

    click.echo("=" * 55)


# =====================================================================
# CLI 主入口 — click.Group（向后兼容）
#
# 设计决策：用 invoke_without_command=True 让不带子命令的调用
# 仍然执行原有的筛选流程，保持 100% 向后兼容。
# =====================================================================

@click.group(invoke_without_command=True)
@click.option(
    "--config", "config_path",
    default="config.yaml",
    help="配置文件路径",
    type=click.Path(),
)
@click.option(
    "--market",
    default="all",
    type=click.Choice(["cn", "us", "hk", "all"], case_sensitive=False),
    help="筛选哪个市场 (默认 all)",
)
@click.option(
    "--output", "output_path",
    default=None,
    help="输出报告路径 (默认 output/fund_report.md)",
    type=click.Path(),
)
@click.option("--no-cache", is_flag=True, help="忽略缓存，强制重新拉取数据")
@click.option("--no-store", is_flag=True, help="禁用 SQLite 数据湖持久化")
@click.option("--db-stats", is_flag=True, help="查看数据湖统计信息（不执行筛选）")
@click.option("--update-sectors", is_flag=True, help="更新申万行业映射表")
@click.option("--verbose", "-v", is_flag=True, help="输出详细日志")
@click.pass_context
def main(
    ctx: click.Context,
    config_path: str,
    market: str,
    output_path: str | None,
    no_cache: bool,
    no_store: bool,
    db_stats: bool,
    update_sectors: bool,
    verbose: bool,
) -> None:
    """
    全市场基金/ETF 趋势筛选器 + 量化分析中枢。

    抓取 A股/美股/港股基金数据，用 MA 均线筛选右侧趋势标的，
    生成结构化 Markdown 报告供 LLM 深度分析。

    \b
    OLAP 子命令：
      scan-momentum  横截面动量扫描
      detect-drift   风格漂移检测
      correlation    底层相关性矩阵
      bulk-fetch     异步批量抓取
    """
    _setup_logging(verbose)

    # 将配置存入 context，供子命令使用
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config_path
    ctx.obj["verbose"] = verbose

    # 如果有子命令被调用，不执行默认的筛选流程
    if ctx.invoked_subcommand is not None:
        return

    # ---- 以下是原有的默认筛选流程（向后兼容）----

    logger.info("基金/ETF 趋势筛选器启动")

    config = load_config(config_path)

    # --db-stats: 查看数据湖统计信息后直接退出
    if db_stats:
        _print_db_stats(config)
        return

    # --update-sectors: 更新申万行业映射后直接退出
    if update_sectors:
        _run_sector_update(config)
        return

    logger.info("配置加载完成: MA%d/MA%d, 回看 %d 天", config.ma_short, config.ma_long, config.lookback_days)

    # 初始化缓存
    cache_ttl = 0 if no_cache else config.cache_ttl_hours
    cache = FileCache(config.cache_dir, default_ttl_hours=cache_ttl)
    if no_cache:
        logger.info("缓存已禁用，将强制重新拉取所有数据")

    # 初始化数据湖
    store: DataStore | None = None
    if config.store_enabled and not no_store:
        store = DataStore(config.db_path)
        logger.info("数据湖已启用: %s", config.db_path)
    else:
        logger.info("数据湖已禁用")

    # 确定要处理的市场
    if market == "all":
        markets = [Market.US, Market.CN, Market.HK]
    else:
        market_map = {"cn": Market.CN, "us": Market.US, "hk": Market.HK}
        markets = [market_map[market.lower()]]

    # 创建 fetcher
    fetchers = _create_fetchers(config, cache, markets)
    if not fetchers:
        logger.error("没有可用的数据源，请检查配置")
        sys.exit(1)

    # 处理每个市场
    all_funds: list[FundInfo] = []
    all_summaries: list[ScreeningSummary] = []

    for _mkt, fetcher in fetchers.items():
        funds, summary = _process_market(fetcher, config, store=store)
        all_funds.extend(funds)
        all_summaries.append(summary)

    # 关闭数据湖连接
    if store is not None:
        store.close()

    # 生成报告
    if not all_funds:
        logger.warning("没有任何基金通过筛选！")
        logger.info("可能原因: 当前市场整体处于下跌趋势，或数据获取失败")
        return

    report_path = output_path or f"{config.output_dir}/fund_report.md"
    result_path = generate_report(
        funds=all_funds,
        summaries=all_summaries,
        ma_short_period=config.ma_short,
        ma_long_period=config.ma_long,
        output_path=report_path,
    )

    logger.info("=" * 50)
    logger.info("报告已生成: %s", result_path)
    logger.info("共 %d 只基金/ETF 处于上涨趋势", len(all_funds))
    logger.info("下一步: 把报告文件拖进 Claude / Gemini AI Studio 进行深度分析")


def _run_sector_update(config: AppConfig) -> None:
    """执行申万行业映射全量更新。"""
    from fund_screener.sector_fetcher import fetch_and_persist_sector_mapping

    logger.info("开始更新申万行业映射...")
    with DataStore(config.db_path) as store:
        count = fetch_and_persist_sector_mapping(store)

    if count > 0:
        click.echo(f"申万行业映射更新完成: {count} 条记录")
    else:
        click.echo("申万行业映射更新失败或数据为空")


# =====================================================================
# 子命令 1: scan-momentum
# =====================================================================

@main.command("scan-momentum")
@click.option("--date", "scan_date", required=True, help="扫描日期 YYYY-MM-DD")
@click.option("--ma-short", default=20, help="短期均线周期 (默认 20)")
@click.option("--ma-long", default=60, help="长期均线周期 (默认 60)")
@click.pass_context
def cmd_scan_momentum(
    ctx: click.Context,
    scan_date: str,
    ma_short: int,
    ma_long: int,
) -> None:
    """横截面动量扫描 — 全市场找"多头排列+缩量回踩"的标的。"""
    from fund_screener.analytics import scan_cross_sectional_momentum

    config = load_config(ctx.obj["config_path"])

    if not Path(config.db_path).exists():
        click.echo("错误: 数据库不存在，请先运行数据采集")
        sys.exit(1)

    with DataStore(config.db_path) as store:
        conn = store.get_connection()
        results = scan_cross_sectional_momentum(conn, scan_date, ma_short, ma_long)

    if not results:
        click.echo("未找到符合条件的基金（多头排列+回踩）")
        return

    # 输出结构化表格
    click.echo()
    click.echo(f"横截面动量扫描结果 (日期: {scan_date}, MA{ma_short}/MA{ma_long})")
    click.echo("=" * 90)
    click.echo(
        f"  {'代码':<10s} {'名称':<20s} {'最新净值':>10s} "
        f"{'MA差值%':>8s} {'日涨跌%':>8s} {'信号':>6s}",
    )
    click.echo("-" * 90)

    for r in results:
        click.echo(
            f"  {r.fund_code:<10s} {r.fund_name:<20s} {r.latest_nav:>10.4f} "
            f"{r.ma_diff_pct:>+8.2f} {r.daily_return:>+8.2f} {'回踩':>6s}",
        )

    click.echo("-" * 90)
    click.echo(f"共 {len(results)} 只基金")
    click.echo()


# =====================================================================
# 子命令 2: detect-drift
# =====================================================================

@main.command("detect-drift")
@click.option("--fund-code", required=True, help="基金代码")
@click.option("--current-quarter", required=True, help="当前季度日期 YYYY-MM-DD")
@click.option("--prev-quarter", required=True, help="对比季度日期 YYYY-MM-DD")
@click.option("--threshold", default=20.0, help="漂移判定阈值百分比 (默认 20)")
@click.pass_context
def cmd_detect_drift(
    ctx: click.Context,
    fund_code: str,
    current_quarter: str,
    prev_quarter: str,
    threshold: float,
) -> None:
    """风格漂移检测 — 检测基金经理是否偷偷换赛道。"""
    from fund_screener.analytics import detect_style_drift

    config = load_config(ctx.obj["config_path"])

    if not Path(config.db_path).exists():
        click.echo("错误: 数据库不存在，请先运行数据采集")
        sys.exit(1)

    with DataStore(config.db_path) as store:
        conn = store.get_connection()
        result = detect_style_drift(conn, fund_code, current_quarter, prev_quarter, threshold)

    # 输出结果
    click.echo()
    click.echo(f"风格漂移检测: {fund_code}")
    click.echo(f"对比区间: {prev_quarter} → {current_quarter}")
    click.echo("=" * 55)
    click.echo(f"  总换手率: {result.total_turnover:.1f}%")
    click.echo(f"  判定阈值: {result.threshold:.1f}%")

    status = "⚠️  检测到风格漂移！" if result.is_drifted else "✅ 风格稳定"
    click.echo(f"  结论: {status}")
    click.echo()

    if result.new_entries:
        click.echo(f"  新进持仓: {', '.join(result.new_entries)}")
    if result.exits:
        click.echo(f"  退出持仓: {', '.join(result.exits)}")

    if result.major_changes:
        click.echo()
        click.echo("  大幅调仓明细:")
        for change in result.major_changes:
            click.echo(
                f"    {change['stock_code']}: "
                f"{change['prev_weight']}% → {change['curr_weight']}% "
                f"(Δ{change['delta']:+.2f}%)",
            )

    click.echo()


# =====================================================================
# 子命令 3: correlation
# =====================================================================

@main.command("correlation")
@click.option("--funds", required=True, help="基金代码列表（逗号分隔）")
@click.option("--threshold", default=0.3, help="报警阈值 (默认 0.3)")
@click.pass_context
def cmd_correlation(
    ctx: click.Context,
    funds: str,
    threshold: float,
) -> None:
    """底层相关性矩阵 — 防止买入"变种相关资产"。"""
    from fund_screener.analytics import calculate_correlation_matrix

    config = load_config(ctx.obj["config_path"])

    if not Path(config.db_path).exists():
        click.echo("错误: 数据库不存在，请先运行数据采集")
        sys.exit(1)

    fund_list = [f.strip() for f in funds.split(",") if f.strip()]
    if len(fund_list) < 2:
        click.echo("错误: 至少需要 2 只基金代码")
        sys.exit(1)

    with DataStore(config.db_path) as store:
        conn = store.get_connection()
        result = calculate_correlation_matrix(conn, fund_list, threshold)

    matrix: dict[str, dict[str, float]] = result["matrix"]
    alerts: list[object] = result["alerts"]

    if not matrix:
        click.echo("无相关性数据（可能基金未入库或无持仓记录）")
        return

    # 输出矩阵
    codes = list(matrix.keys())
    click.echo()
    click.echo(f"行业权重余弦相似度矩阵 (阈值: {threshold})")
    click.echo("=" * (12 + 10 * len(codes)))

    # 表头
    header = f"  {'':>10s}"
    for c in codes:
        header += f" {c:>9s}"
    click.echo(header)
    click.echo("-" * (12 + 10 * len(codes)))

    # 矩阵行
    for code_a in codes:
        line = f"  {code_a:>10s}"
        for code_b in codes:
            val = matrix.get(code_a, {}).get(code_b, 0.0)
            line += f" {val:>9.4f}"
        click.echo(line)

    click.echo()

    # 报警
    if alerts:
        click.echo("⚠️  超阈值报警:")
        for pair in alerts:
            click.echo(
                f"  {pair.fund_a} ↔ {pair.fund_b}: "  # type: ignore[union-attr]
                f"相似度 {pair.similarity:.4f}",  # type: ignore[union-attr]
            )
    else:
        click.echo("✅ 无超阈值报警")

    click.echo()


# =====================================================================
# 子命令 4: bulk-fetch
# =====================================================================

@main.command("bulk-fetch")
@click.option(
    "--market",
    required=True,
    type=click.Choice(["cn", "us", "hk"], case_sensitive=False),
    help="目标市场",
)
@click.option("--concurrency", default=10, help="并发数 (默认 10)")
@click.pass_context
def cmd_bulk_fetch(
    ctx: click.Context,
    market: str,
    concurrency: int,
) -> None:
    """异步批量抓取 — 并发获取净值+详情数据。"""
    from fund_screener.async_fetcher import AsyncBulkFetcher
    from fund_screener.error_queue import ErrorQueue

    config = load_config(ctx.obj["config_path"])

    # 初始化缓存和 fetcher
    cache = FileCache(config.cache_dir, default_ttl_hours=config.cache_ttl_hours)
    market_map = {"cn": Market.CN, "us": Market.US, "hk": Market.HK}
    target_market = market_map[market.lower()]

    fetchers = _create_fetchers(config, cache, [target_market])
    if target_market not in fetchers:
        click.echo(f"错误: {market} 市场未启用，请检查配置")
        sys.exit(1)

    fetcher = fetchers[target_market]
    store = DataStore(config.db_path)
    error_queue = ErrorQueue()

    # 获取基金列表
    click.echo(f"正在获取 {market.upper()} 市场基金列表...")
    fund_list = fetcher.fetch_fund_list()
    if not fund_list:
        click.echo("基金列表为空")
        store.close()
        return

    # 持久化基金列表
    store.persist_fund_list(target_market.value, fund_list)

    # 合并重试队列
    retry_codes = error_queue.get_retry_queue()
    fund_codes = [f["code"] for f in fund_list]
    # 把重试队列中的代码加到前面优先处理
    all_codes = list(dict.fromkeys(retry_codes + fund_codes))

    click.echo(
        f"开始批量抓取: {len(all_codes)} 只基金 "
        f"(其中 {len(retry_codes)} 只来自重试队列), 并发={concurrency}",
    )

    # 运行异步抓取
    async_fetcher = AsyncBulkFetcher(
        fetcher=fetcher,
        store=store,
        error_queue=error_queue,
        concurrency=concurrency,
    )

    stats = asyncio.run(async_fetcher.bulk_fetch(all_codes))
    async_fetcher.shutdown()
    store.close()

    click.echo()
    click.echo(f"批量抓取完成:")
    click.echo(f"  成功: {stats['success']}")
    click.echo(f"  失败: {stats['failed']}")
    click.echo(f"  总计: {stats['total']}")

    remaining = len(error_queue)
    if remaining > 0:
        click.echo(f"  待重试: {remaining} (详见 data/error_log.json)")
    click.echo()


if __name__ == "__main__":
    main()
