"""
CLI 入口 — 编排全流程的调度中心。

使用 click 框架构建命令行接口，把 fetcher / screener / reporter 串联起来。

执行流程：
1. 加载配置
2. 初始化缓存和 fetcher
3. 按市场遍历：获取基金列表 → 拉净值历史 → MA 筛选 → 获取持仓
4. 生成 Markdown 报告

用法：
    uv run fund-screener --market all --verbose
    uv run fund-screener --market us --no-cache
"""

from __future__ import annotations

import logging
import sys
from datetime import date
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
    # 为什么单独处理 A 股？因为 ak.fund_em_open_fund_daily() 一次请求就能拿到
    # 全市场的"日增长率"字段，比逐只基金从历史数据算效率高得多，且数据更准确。
    cn_daily_map: dict[str, float] = {}
    if market == Market.CN:
        try:
            import akshare as ak

            logger.info("正在获取 A 股当日涨跌幅数据...")
            daily_df = ak.fund_open_fund_daily_em()
            if daily_df is not None and not daily_df.empty:
                # 识别基金代码列和日增长率列
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

            # MA 筛选
            result = screen_fund(nav_df, config.ma_short, config.ma_long)
            if result is None or not result.passed:
                continue

            # 通过筛选！获取持仓和行业分布
            logger.debug("通过: %s (%s), MA差值: %+.2f%%", name, code, result.ma_diff_pct)

            holdings = fetcher.fetch_holdings(code)
            sectors = fetcher.fetch_sector_exposure(code)

            # 计算多周期涨跌幅（从已有 nav_df 直接算，零额外请求）
            trend_stats = calculate_trend_stats(nav_df)

            # 计算当日涨跌幅
            daily_change: float | None = None
            if market == Market.CN:
                # A 股：从预加载的全市场映射表查
                daily_change = cn_daily_map.get(code)
            else:
                # 美股/港股：从 nav_history 最后两天价格算
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


@click.command()
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
@click.option("--verbose", "-v", is_flag=True, help="输出详细日志")
def main(
    config_path: str,
    market: str,
    output_path: str | None,
    no_cache: bool,
    verbose: bool,
) -> None:
    """
    全市场基金/ETF 趋势筛选器。

    抓取 A股/美股/港股基金数据，用 MA 均线筛选右侧趋势标的，
    生成结构化 Markdown 报告供 LLM 深度分析。
    """
    _setup_logging(verbose)
    logger.info("基金/ETF 趋势筛选器启动")

    # 加载配置
    config = load_config(config_path)
    logger.info("配置加载完成: MA%d/MA%d, 回看 %d 天", config.ma_short, config.ma_long, config.lookback_days)

    # 初始化缓存
    cache_ttl = 0 if no_cache else config.cache_ttl_hours
    cache = FileCache(config.cache_dir, default_ttl_hours=cache_ttl)
    if no_cache:
        logger.info("缓存已禁用，将强制重新拉取所有数据")

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

    for mkt, fetcher in fetchers.items():
        funds, summary = _process_market(fetcher, config)
        all_funds.extend(funds)
        all_summaries.append(summary)

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


if __name__ == "__main__":
    main()
