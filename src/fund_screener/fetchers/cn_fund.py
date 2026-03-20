"""
A股公募基金数据获取器。

数据源：akshare（底层爬东方财富）
核心 API：
- ak.fund_open_fund_rank_em() — 开放式基金排名列表
- ak.fund_open_fund_info_em() — 单只基金净值历史
- ak.fund_portfolio_hold_em() — 基金持仓明细（季报数据，滞后约 1 个季度）

踩坑警告：
1. akshare 的函数名和参数在不同版本间经常变动，所以每个调用都 try-except 包裹
2. 底层爬东财，高频调用会被临时封 IP，必须加 time.sleep
3. 持仓数据是季报级别的，最新数据可能是 3 个月前的
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import pandas as pd

from fund_screener.cache import FileCache
from fund_screener.config import CNFundConfig, RateLimitConfig
from fund_screener.fetchers.base import BaseFetcher, with_retry
from fund_screener.models import Holding, Market, SectorWeight

logger = logging.getLogger(__name__)


class CNFundFetcher(BaseFetcher):
    """A股公募基金数据获取器（akshare）。"""

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

    @property
    def _delay_sec(self) -> float:
        return self.rate_limit_config.akshare_delay_sec

    def fetch_fund_list(self) -> list[dict[str, str]]:
        """
        获取开放式基金排名列表，按 fund_types 过滤。

        返回格式：[{"code": "005827", "name": "易方达蓝筹精选混合"}, ...]
        """
        import akshare as ak

        cache_key = self._cache_key("all", "fund_list")
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        self._rate_limit()

        try:
            # akshare 获取全部开放式基金排名
            df = ak.fund_open_fund_rank_em(symbol="全部")
        except Exception as e:
            logger.error("获取 A 股基金列表失败: %s", e)
            return []

        if df is None or df.empty:
            logger.warning("A 股基金列表为空")
            return []

        # 标准化列名（akshare 不同版本列名可能不同）
        # 通常列名包含 "基金代码" 和 "基金简称"
        code_col = None
        name_col = None
        type_col = None

        for col in df.columns:
            if "代码" in col:
                code_col = col
            elif "简称" in col or "名称" in col:
                name_col = col
            elif "类型" in col:
                type_col = col

        if code_col is None or name_col is None:
            logger.error("A 股基金列表列名不匹配，实际列: %s", list(df.columns))
            return []

        # 按基金类型过滤
        if type_col and self._cn_config.fund_types:
            mask = df[type_col].isin(self._cn_config.fund_types)
            df = df[mask]

        # 限制数量
        if self._cn_config.max_funds > 0:
            df = df.head(self._cn_config.max_funds)

        result = [
            {"code": str(row[code_col]).strip(), "name": str(row[name_col]).strip()}
            for _, row in df.iterrows()
        ]

        self.cache.set(cache_key, result)
        logger.info("A 股基金列表获取成功: %d 只", len(result))
        return result

    @with_retry(max_retries=3, backoff_sec=2.0)
    def fetch_nav_history(self, code: str, days: int) -> pd.DataFrame:
        """
        获取单只 A 股基金的单位净值历史。

        注意：用"单位净值走势"而非"累计净值走势"，
        因为 MA 计算应该基于可交易的实际净值。

        Returns:
            DataFrame columns=["date", "nav"]，按日期升序
        """
        import akshare as ak

        cache_key = self._cache_key(code, "nav_history")
        cached = self.cache.get(cache_key)
        if cached is not None:
            return pd.DataFrame(cached)

        self._rate_limit()

        try:
            # akshare >= 1.14 参数名从 fund 改成了 symbol
            df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
        except Exception as e:
            logger.warning("获取基金 %s 净值历史失败: %s", code, e)
            return pd.DataFrame(columns=["date", "nav"])

        if df is None or df.empty:
            return pd.DataFrame(columns=["date", "nav"])

        # 标准化列名
        df.columns = [c.lower().strip() for c in df.columns]

        # 尝试识别日期列和净值列
        date_col = None
        nav_col = None
        for col in df.columns:
            col_str = str(col)
            if "日期" in col_str or "date" in col_str or "净值日期" in col_str:
                date_col = col
            elif "净值" in col_str or "nav" in col_str or "单位净值" in col_str:
                nav_col = col

        # 如果找不到，按位置猜（第一列日期，第二列净值）
        if date_col is None and len(df.columns) >= 2:
            date_col = df.columns[0]
        if nav_col is None and len(df.columns) >= 2:
            nav_col = df.columns[1]

        if date_col is None or nav_col is None:
            logger.warning("基金 %s 净值数据列名无法识别: %s", code, list(df.columns))
            return pd.DataFrame(columns=["date", "nav"])

        result_df = pd.DataFrame({
            "date": pd.to_datetime(df[date_col]),
            "nav": pd.to_numeric(df[nav_col], errors="coerce"),
        })
        result_df = result_df.dropna().sort_values("date").reset_index(drop=True)

        # 只保留最近 N 天
        if days > 0 and len(result_df) > 0:
            cutoff = datetime.now() - timedelta(days=days)
            result_df = result_df[result_df["date"] >= cutoff]

        # 缓存（转为可序列化格式）
        cache_data = result_df.copy()
        cache_data["date"] = cache_data["date"].dt.strftime("%Y-%m-%d")
        self.cache.set(cache_key, cache_data.to_dict(orient="records"))

        return result_df

    @with_retry(max_retries=3, backoff_sec=2.0)
    def fetch_holdings(self, code: str) -> list[Holding]:
        """
        获取 A 股基金的持仓明细（季报数据）。

        akshare 的 fund_portfolio_hold_em 返回最近一期报告的持仓。
        数据可能滞后 1-3 个月，这是正常的。
        """
        import akshare as ak

        cache_key = self._cache_key(code, "holdings")
        cached = self.cache.get(cache_key)
        if cached is not None:
            return [Holding(**h) for h in cached]

        self._rate_limit()

        try:
            # 获取最近一年的持仓数据
            year = str(datetime.now().year)
            df = ak.fund_portfolio_hold_em(symbol=code, date=year)
        except Exception as e:
            logger.warning("获取基金 %s 持仓失败: %s", code, e)
            return []

        if df is None or df.empty:
            return []

        # 只取最新一期的数据（通常按季度排列）
        if "季度" in str(df.columns.tolist()):
            quarters = df["季度"].unique()
            if len(quarters) > 0:
                latest_quarter = sorted(quarters)[-1]
                df = df[df["季度"] == latest_quarter]

        holdings: list[Holding] = []
        for _, row in df.head(10).iterrows():
            stock_code = ""
            stock_name = ""
            weight = None

            for col in df.columns:
                col_str = str(col)
                if "股票代码" in col_str or "代码" in col_str:
                    stock_code = str(row[col]).strip()
                elif "股票名称" in col_str or "名称" in col_str:
                    stock_name = str(row[col]).strip()
                elif "占净值比例" in col_str or "占比" in col_str or "比例" in col_str:
                    try:
                        weight = float(row[col])
                    except (ValueError, TypeError):
                        pass

            if stock_code or stock_name:
                holdings.append(Holding(
                    stock_code=stock_code,
                    stock_name=stock_name,
                    weight_pct=weight,
                ))

        # 缓存
        self.cache.set(cache_key, [h.model_dump() for h in holdings])
        return holdings

    def fetch_sector_exposure(self, code: str) -> list[SectorWeight]:
        """
        获取 A 股基金的行业分布。

        尝试使用 akshare 的行业配置接口，如果失败则从持仓中推断。
        """
        import akshare as ak

        cache_key = self._cache_key(code, "sectors")
        cached = self.cache.get(cache_key)
        if cached is not None:
            return [SectorWeight(**s) for s in cached]

        self._rate_limit()

        try:
            df = ak.fund_portfolio_industry_allocation_em(symbol=code)
        except Exception:
            # 很多基金没有行业配置数据，这是正常的
            logger.debug("基金 %s 无行业配置数据", code)
            return []

        if df is None or df.empty:
            return []

        sectors: list[SectorWeight] = []
        for _, row in df.iterrows():
            sector_name = ""
            weight = 0.0

            for col in df.columns:
                col_str = str(col)
                if "行业" in col_str or "类别" in col_str:
                    sector_name = str(row[col]).strip()
                elif "占比" in col_str or "比例" in col_str or "市值" in col_str:
                    try:
                        weight = float(row[col])
                    except (ValueError, TypeError):
                        pass

            if sector_name and weight > 0:
                sectors.append(SectorWeight(sector=sector_name, weight_pct=weight))

        # 按权重降序，取前 10
        sectors.sort(key=lambda s: s.weight_pct, reverse=True)
        sectors = sectors[:10]

        self.cache.set(cache_key, [s.model_dump() for s in sectors])
        return sectors
