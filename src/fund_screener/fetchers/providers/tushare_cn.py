"""
A股公募基金数据获取器 — tushare Pro 版。

替换原 akshare 爬虫方案，使用 tushare Pro 付费 API 获取数据。

数据源迁移映射：
┌─────────────────────┬──────────────────────────┬──────────────────────────┐
│ 功能                │ akshare (旧)             │ tushare Pro (新)         │
├─────────────────────┼──────────────────────────┼──────────────────────────┤
│ 基金列表            │ fund_open_fund_rank_em   │ fund_basic(market='O')   │
│ 净值历史            │ fund_open_fund_info_em   │ fund_nav                 │
│ 持仓数据            │ fund_portfolio_hold_em   │ fund_portfolio           │
│ 行业分布            │ fund_portfolio_industry  │ 从持仓推导（暂返回空）   │
│ 基金详情            │ fund_individual_basic    │ fund_basic 字段已含      │
│ 申购限额            │ fund_purchase_em         │ fund_basic.status 简化   │
│ 当日涨跌幅          │ fund_open_fund_daily_em  │ 从 fund_nav 最近两日算   │
└─────────────────────┴──────────────────────────┴──────────────────────────┘

迁移注意事项：
1. tushare 基金代码格式为 ts_code（如 005827.OF），内部统一用纯数字（005827）
2. fund_portfolio 需要 5000 积分，积分不足时优雅降级返回空列表
3. tushare 无申购限额金额数据，仅做 "开放/暂停" 二元判断
4. 日期格式：tushare 用 YYYYMMDD 字符串，pandas 用 datetime，注意转换
5. fund_nav 单次最大 2000 行，单只基金 150 天足够，不需要分页
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import tushare as ts

from fund_screener.cache import FileCache
from fund_screener.config import CNFundConfig, RateLimitConfig
from fund_screener.fetchers.base import BaseFetcher, with_retry
from fund_screener.models import Holding, Market, SectorWeight

logger = logging.getLogger(__name__)


class TushareCNProvider(BaseFetcher):
    """
    A股公募基金数据获取器 — tushare Pro provider。

    (原 CNTushareFetcher,2026-04-13 重构时改名并下沉到 providers/ 子包,
    由 CompositeCNFetcher 按路由表组合调度。单独使用仍可,保持 BaseFetcher 契约。)

    与 AkshareCNProvider 接口完全兼容,方法签名和返回类型对齐。
    """

    def __init__(
        self,
        cache: FileCache,
        rate_limit_config: RateLimitConfig,
        cn_config: CNFundConfig,
    ) -> None:
        super().__init__(
            market=Market.CN,
            cache=cache,
            rate_limit_config=rate_limit_config,
        )
        self._cn_config = cn_config
        self._pro = self._init_tushare_api()
        # 懒加载的股票名称映射表（持仓查询时用）
        self._stock_name_map: dict[str, str] | None = None
        # 懒加载的基金列表完整数据（fetch_fund_detail / purchase_limit_map 复用）
        self._fund_basic_df: pd.DataFrame | None = None

    # ------------------------------------------------------------------
    # 初始化 & 工具方法
    # ------------------------------------------------------------------

    def _init_tushare_api(self) -> ts.pro_api:  # type: ignore[name-defined]
        """
        初始化 tushare Pro API 实例。

        token 从环境变量 TUSHARE_TOKEN 读取（.env 文件由 cli.py 入口加载）。
        如果 token 缺失，立刻 fail-fast 抛异常，不要等到第一次 API 调用才报错。
        """
        token = os.getenv("TUSHARE_TOKEN")
        if not token:
            raise ValueError(
                "TUSHARE_TOKEN 环境变量未设置。"
                "请在项目根目录创建 .env 文件并填入 TUSHARE_TOKEN=your_token。"
                "参考 .env.example"
            )
        ts.set_token(token)
        pro = ts.pro_api()
        logger.info("tushare Pro API 初始化成功")
        return pro

    @property
    def _delay_sec(self) -> float:
        """tushare 请求间隔，默认 0.3 秒。"""
        return self.rate_limit_config.tushare_delay_sec

    @staticmethod
    def _to_ts_code(code: str) -> str:
        """
        内部代码 → tushare ts_code。

        005827 → 005827.OF（场外开放式基金）
        如果已经带后缀就原样返回。
        """
        if "." not in code:
            return f"{code}.OF"
        return code

    @staticmethod
    def _from_ts_code(ts_code: str) -> str:
        """
        tushare ts_code → 内部代码。

        005827.OF → 005827
        """
        return ts_code.split(".")[0]

    def _get_fund_basic_df(self) -> pd.DataFrame:
        """
        获取并缓存 fund_basic 完整数据。

        fund_basic 是 tushare 基金模块的"维度表"，包含基金名称、类型、
        成立日期、管理人、状态等全量信息。多个方法共用这份数据：
        - fetch_fund_list: 过滤基金列表
        - fetch_fund_detail: 提取基金详情
        - fetch_purchase_limit_map: 判断申购状态

        所以只拉一次，内存缓存 + FileCache 双层缓存。
        """
        if self._fund_basic_df is not None:
            return self._fund_basic_df

        cache_key = self._cache_key("all", "fund_basic_full")
        cached = self.cache.get(cache_key)
        if cached is not None:
            self._fund_basic_df = pd.DataFrame(cached)
            return self._fund_basic_df

        self._rate_limit()

        try:
            # market='O' 场外基金，status='L' 上市中（排除已摘牌和发行中）
            df = self._pro.fund_basic(market="O", status="L")
        except Exception as e:
            logger.error("获取 fund_basic 失败: %s", e)
            return pd.DataFrame()

        if df is None or df.empty:
            logger.warning("fund_basic 返回空数据")
            return pd.DataFrame()

        self._fund_basic_df = df

        # 缓存为 list[dict]（JSON 序列化友好）
        self.cache.set(cache_key, df.to_dict(orient="records"))
        logger.info("fund_basic 加载完成: %d 只基金", len(df))
        return df

    def _get_stock_name_map(self) -> dict[str, str]:
        """
        懒加载股票代码→名称映射表。

        fund_portfolio 返回的持仓数据只有 symbol（股票代码），没有名称。
        通过 stock_basic 一次性拉取全 A 股名称映射，O(1) 查询。
        """
        if self._stock_name_map is not None:
            return self._stock_name_map

        cache_key = self._cache_key("all", "stock_name_map")
        cached = self.cache.get(cache_key)
        if cached is not None:
            self._stock_name_map = cached
            return self._stock_name_map

        self._rate_limit()

        try:
            df = self._pro.stock_basic(
                exchange="",
                list_status="L",
                fields="ts_code,name",
            )
        except Exception as e:
            logger.warning("获取股票名称映射失败: %s", e)
            self._stock_name_map = {}
            return self._stock_name_map

        name_map: dict[str, str] = {}
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                full_code = str(row["ts_code"])  # 600519.SH
                short_code = full_code.split(".")[0]  # 600519
                name = str(row["name"])
                # 双 key 存储：fund_portfolio.symbol 可能带后缀也可能不带
                name_map[full_code] = name
                name_map[short_code] = name

        self._stock_name_map = name_map
        self.cache.set(cache_key, name_map)
        logger.info("股票名称映射加载完成: %d 只", len(name_map))
        return name_map

    # ------------------------------------------------------------------
    # BaseFetcher 接口实现
    # ------------------------------------------------------------------

    def fetch_fund_list(self) -> list[dict[str, str]]:
        """
        获取 A 股场外公募基金列表。

        调用 fund_basic(market='O', status='L')，按 fund_types 配置过滤。
        tushare fund_type 字段值示例：混合型、股票型、债券型、货币型、QDII型。

        返回格式：[{"code": "005827", "name": "易方达蓝筹精选混合"}, ...]
        """
        cache_key = self._cache_key("all", "fund_list")
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        df = self._get_fund_basic_df()
        if df.empty:
            return []

        # 按 fund_type 过滤（tushare 字段名固定，不像 akshare 会变）
        if self._cn_config.fund_types and "fund_type" in df.columns:
            mask = df["fund_type"].isin(self._cn_config.fund_types)
            df_filtered = df[mask]

            # 如果过滤后为空，记录可用的 fund_type 值帮助调试
            if df_filtered.empty:
                available_types = df["fund_type"].unique().tolist()
                logger.warning(
                    "fund_type 过滤后为空！配置: %s, tushare 可用值: %s",
                    self._cn_config.fund_types,
                    available_types[:20],
                )
                # 回退：不过滤，返回全部
                df_filtered = df
            else:
                logger.info(
                    "fund_type 过滤: %s, 匹配 %d/%d 只",
                    self._cn_config.fund_types,
                    len(df_filtered),
                    len(df),
                )
        else:
            df_filtered = df

        # 限制数量
        if self._cn_config.max_funds > 0:
            df_filtered = df_filtered.head(self._cn_config.max_funds)

        result: list[dict[str, str]] = []
        for _, row in df_filtered.iterrows():
            ts_code = str(row.get("ts_code", "")).strip()
            name = str(row.get("name", "")).strip()
            if ts_code:
                result.append({
                    "code": self._from_ts_code(ts_code),
                    "name": name,
                })

        self.cache.set(cache_key, result)
        logger.info("A 股基金列表获取成功: %d 只", len(result))
        return result

    @with_retry(max_retries=3, backoff_sec=2.0)
    def fetch_nav_history(self, code: str, days: int) -> pd.DataFrame:
        """
        获取单只 A 股基金的净值历史。

        tushare fund_nav 返回字段：
        - nav_date: 净值日期 (YYYYMMDD)
        - unit_nav: 单位净值
        - accum_nav: 累计净值
        - adj_nav: 复权单位净值

        Returns:
            DataFrame columns=["date", "nav", "unit_nav", "cumulative_nav", "adj_nav"]
            与旧版 akshare fetcher 输出格式完全一致
        """
        empty_df = pd.DataFrame(
            columns=["date", "nav", "unit_nav", "cumulative_nav", "adj_nav"],
        )

        cache_key = self._cache_key(code, "nav_history_v2")
        cached = self.cache.get(cache_key)
        if cached is not None:
            df = pd.DataFrame(cached)
            if not df.empty:
                df["date"] = pd.to_datetime(df["date"])
            return df

        self._rate_limit()

        ts_code = self._to_ts_code(code)
        # 计算日期范围：从今天往前推 days 天
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

        try:
            df = self._pro.fund_nav(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception as e:
            logger.warning("获取基金 %s 净值失败: %s", code, e)
            return empty_df

        if df is None or df.empty:
            return empty_df

        # tushare 返回的列：ts_code, ann_date, nav_date, unit_nav, accum_nav,
        # accum_div, net_asset, total_netasset, adj_nav
        result_df = pd.DataFrame({
            "date": pd.to_datetime(df["nav_date"], format="%Y%m%d"),
            "nav": pd.to_numeric(df["unit_nav"], errors="coerce"),
            "unit_nav": pd.to_numeric(df["unit_nav"], errors="coerce"),
            "cumulative_nav": pd.to_numeric(df["accum_nav"], errors="coerce"),
            "adj_nav": pd.to_numeric(
                df["adj_nav"] if "adj_nav" in df.columns else df["accum_nav"],
                errors="coerce",
            ),
        })

        # 清洗 + 排序
        result_df = result_df.dropna(subset=["date", "nav"])
        result_df = result_df.sort_values("date").reset_index(drop=True)

        if result_df.empty:
            return empty_df

        # 缓存（日期转字符串以便 JSON 序列化）
        cache_data = result_df.copy()
        cache_data["date"] = cache_data["date"].dt.strftime("%Y-%m-%d")
        self.cache.set(cache_key, cache_data.to_dict(orient="records"))

        return result_df

    @with_retry(max_retries=3, backoff_sec=2.0)
    def fetch_holdings(self, code: str) -> list[Holding]:
        """
        获取基金持仓明细（季报数据）。

        tushare fund_portfolio 返回字段：
        - symbol: 股票代码（如 600519）
        - mkv: 持有市值（元）
        - amount: 持有数量（股）
        - stk_mkv_ratio: 占股票市值比（%）

        注意：需要 5000 积分。积分不足时 API 会返回错误，
        我们优雅降级返回空列表，不阻塞主流程。
        """
        cache_key = self._cache_key(code, "holdings")
        cached = self.cache.get(cache_key)
        if cached is not None:
            return [Holding(**h) for h in cached]

        self._rate_limit()

        ts_code = self._to_ts_code(code)

        try:
            df = self._pro.fund_portfolio(ts_code=ts_code)
        except Exception as e:
            # 积分不足或其他错误 — 优雅降级
            logger.warning("获取基金 %s 持仓失败（可能积分不足）: %s", code, e)
            return []

        if df is None or df.empty:
            return []

        # 只取最新一期的数据（按 end_date 降序取最大值）
        if "end_date" in df.columns:
            latest_date = df["end_date"].max()
            df = df[df["end_date"] == latest_date]

        # 加载股票名称映射
        name_map = self._get_stock_name_map()

        # 按持仓市值降序，取 Top 10
        if "mkv" in df.columns:
            df = df.sort_values("mkv", ascending=False)

        holdings: list[Holding] = []
        for _, row in df.head(10).iterrows():
            stock_code = str(row.get("symbol", "")).strip()
            stock_name = name_map.get(stock_code, "")
            weight = None
            shares = None

            # stk_mkv_ratio 是占股票市值比，不是占净值比
            # 但这是 tushare 能给到的最接近"持仓权重"的字段
            if "stk_mkv_ratio" in df.columns:
                try:
                    weight = float(row["stk_mkv_ratio"])
                except (ValueError, TypeError):
                    pass

            if "amount" in df.columns:
                try:
                    # tushare 的 amount 单位是股，转换为万股
                    shares = float(row["amount"]) / 10000
                except (ValueError, TypeError):
                    pass

            if stock_code:
                holdings.append(Holding(
                    stock_code=stock_code,
                    stock_name=stock_name,
                    weight_pct=weight,
                    hold_shares=shares,
                ))

        # 缓存
        self.cache.set(cache_key, [h.model_dump() for h in holdings])
        return holdings

    def fetch_sector_exposure(self, code: str) -> list[SectorWeight]:
        """
        获取行业分布。

        tushare 没有直接的行业配置接口。
        未来可以通过持仓 + stock_sector_mapping 表推导，
        当前版本返回空列表（与 akshare 版很多基金拿不到行业数据一样）。
        """
        # TODO: 从 fund_portfolio 持仓 + stock_sector_mapping 推导行业分布
        return []

    @with_retry(max_retries=3, backoff_sec=2.0)
    def fetch_fund_detail(self, code: str) -> dict[str, Any]:
        """
        获取基金详情（成立日期、管理人、规模、基准等）。

        直接从 fund_basic 缓存数据中提取，不需要额外 API 调用。
        """
        cache_key = self._cache_key(code, "fund_detail")
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        df = self._get_fund_basic_df()
        if df.empty:
            return {}

        ts_code = self._to_ts_code(code)
        match = df[df["ts_code"] == ts_code]
        if match.empty:
            return {}

        row = match.iloc[0]
        detail: dict[str, Any] = {}

        # 成立日期：YYYYMMDD → YYYY-MM-DD
        found_date = str(row.get("found_date", "")).strip()
        if found_date and found_date != "nan":
            try:
                detail["establish_date"] = (
                    f"{found_date[:4]}-{found_date[4:6]}-{found_date[6:8]}"
                )
            except (IndexError, ValueError):
                pass

        # 管理人（tushare 是 management 公司名，不是基金经理个人）
        management = str(row.get("management", "")).strip()
        if management and management != "nan":
            detail["manager_name"] = management

        # 业绩比较基准
        benchmark = str(row.get("benchmark", "")).strip()
        if benchmark and benchmark != "nan":
            detail["track_benchmark"] = benchmark

        # 发行份额（亿）→ 基金规模的近似值
        issue_amount = row.get("issue_amount")
        if issue_amount is not None:
            try:
                detail["fund_scale"] = float(issue_amount)
            except (ValueError, TypeError):
                pass

        if detail:
            self.cache.set(cache_key, detail)

        return detail

    def fetch_purchase_limit_map(self) -> dict[str, tuple[float, str]]:
        """
        获取全市场基金申购状态映射表。

        tushare 局限：没有像 akshare fund_purchase_em 那样的
        "日累计限定金额"数据。只能通过 fund_basic.status 做二元判断：
        - status='L'（上市中）→ 视为开放申购，限额设为 1e11（无限制）
        - 其他 → 视为暂停

        如果未来需要精确的申购限额金额，需要补充其他数据源。

        Returns:
            {code: (daily_limit, status_text)}
        """
        cache_key = self._cache_key("all", "purchase_limit_map")
        cached = self.cache.get(cache_key)
        if cached is not None:
            return {
                item["code"]: (item["limit"], item["status"])
                for item in cached
            }

        df = self._get_fund_basic_df()
        if df.empty:
            return {}

        result: dict[str, tuple[float, str]] = {}
        for _, row in df.iterrows():
            ts_code = str(row.get("ts_code", "")).strip()
            if not ts_code:
                continue

            code = self._from_ts_code(ts_code)
            status = str(row.get("status", "")).strip()

            if status == "L":
                # 上市中 → 视为开放申购
                result[code] = (1e11, "开放申购")
            elif status == "D":
                result[code] = (0.0, "已摘牌")
            elif status == "I":
                result[code] = (0.0, "发行中")
            else:
                result[code] = (-1.0, "未知")

        # 缓存
        cache_data = [
            {"code": k, "limit": v[0], "status": v[1]}
            for k, v in result.items()
        ]
        self.cache.set(cache_key, cache_data)

        logger.info("基金申购状态映射加载完成: %d 只基金", len(result))
        return result
