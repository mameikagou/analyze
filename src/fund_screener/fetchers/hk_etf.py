"""
港股基金数据获取器。

数据源：akshare（东方财富港股基金 API）
核心 API：
- ak.fund_hk_rank_em() — 港股基金排名列表（含日增长率、多周期涨跌幅）
- ak.fund_hk_fund_hist_em(code=...) — 单只港股基金净值历史

重要修复记录（2026-03-20）：
- 原代码用 fund_hk_fund_hist_em() 无参调用来获取列表，但该函数无参时返回的是
  默认基金的净值历史，不是基金列表。已改为 fund_hk_rank_em()。
- fund_hk_rank_em 返回的 "基金代码" 是短 ID（如 968113），但
  fund_hk_fund_hist_em 需要 "香港基金代码"（长 ID 如 1002580340）。
  现在在 fetch_fund_list 中同时保存两个 code 的映射关系。
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import pandas as pd

from fund_screener.cache import FileCache
from fund_screener.config import HKETFConfig, RateLimitConfig
from fund_screener.fetchers.base import BaseFetcher, with_retry
from fund_screener.models import Holding, Market, SectorWeight

logger = logging.getLogger(__name__)


class HKETFFetcher(BaseFetcher):
    """港股基金数据获取器（akshare）。"""

    def __init__(
        self,
        cache: FileCache,
        rate_limit_config: RateLimitConfig,
        hk_config: HKETFConfig,
    ) -> None:
        super().__init__(
            market=Market.HK,
            cache=cache,
            rate_limit_config=rate_limit_config,
        )
        self._hk_config = hk_config
        # 短 ID → 长 ID 的映射，fetch_nav_history 要用长 ID
        self._hk_code_map: dict[str, str] = {}

    @property
    def _delay_sec(self) -> float:
        return self.rate_limit_config.akshare_delay_sec

    def fetch_fund_list(self) -> list[dict[str, str]]:
        """
        获取港股基金排名列表。

        使用 fund_hk_rank_em() 而非 fund_hk_fund_hist_em()，
        后者无参数调用时返回的是默认基金的净值历史，不是基金列表。
        """
        import akshare as ak

        cache_key = self._cache_key("all", "fund_list")
        cached = self.cache.get(cache_key)
        if cached is not None:
            # 从缓存重建 code 映射
            for item in cached:
                if "hk_code" in item:
                    self._hk_code_map[item["code"]] = item["hk_code"]
            return cached

        self._rate_limit()

        try:
            df = ak.fund_hk_rank_em()
        except Exception as e:
            logger.error("获取港股基金列表失败: %s", e)
            return []

        if df is None or df.empty:
            logger.warning("港股基金列表为空")
            return []

        # fund_hk_rank_em 的列名：
        # ['序号', '基金代码', '基金简称', '币种', '日期', '单位净值',
        #  '日增长率', '近1周', ..., '香港基金代码']
        code_col: str | None = None
        name_col: str | None = None
        hk_code_col: str | None = None
        for col in df.columns:
            col_str = str(col)
            if col_str == "基金代码":
                code_col = col
            elif "简称" in col_str or "名称" in col_str:
                name_col = col
            elif "香港基金代码" in col_str:
                hk_code_col = col

        if code_col is None or name_col is None:
            logger.error("港股基金列表列名不匹配: %s", list(df.columns))
            return []

        # 限制数量
        if self._hk_config.max_funds > 0:
            df = df.head(self._hk_config.max_funds)

        result: list[dict[str, str]] = []
        for _, row in df.iterrows():
            short_code = str(row[code_col]).strip()
            name = str(row[name_col]).strip()
            hk_code = str(row[hk_code_col]).strip() if hk_code_col else ""

            # 建立短 ID → 长 ID 映射
            if hk_code:
                self._hk_code_map[short_code] = hk_code

            result.append({
                "code": short_code,
                "name": name,
                "hk_code": hk_code,
            })

        self.cache.set(cache_key, result)
        logger.info("港股基金列表获取成功: %d 只", len(result))
        return result

    @with_retry(max_retries=3, backoff_sec=2.0)
    def fetch_nav_history(self, code: str, days: int) -> pd.DataFrame:
        """
        获取港股基金的净值历史。

        关键：fund_hk_fund_hist_em 需要的是"香港基金代码"（长 ID），
        不是 fund_hk_rank_em 返回的"基金代码"（短 ID）。
        通过 _hk_code_map 做转换。
        """
        import akshare as ak

        cache_key = self._cache_key(code, "nav_history")
        cached = self.cache.get(cache_key)
        if cached is not None:
            return pd.DataFrame(cached)

        # 短 ID → 长 ID
        hk_code = self._hk_code_map.get(code, code)

        self._rate_limit()

        df: pd.DataFrame | None = None

        # 方案 1：fund_hk_fund_hist_em(code=长ID)
        try:
            df = ak.fund_hk_fund_hist_em(code=hk_code)
        except Exception as e:
            logger.debug("fund_hk_fund_hist_em(%s) 失败: %s", hk_code, e)

        # 方案 2：用短 ID 试 fund_open_fund_info_em
        if df is None or df.empty:
            try:
                self._rate_limit()
                df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
            except Exception:
                pass

        if df is None or df.empty:
            logger.debug("港股基金 %s 无净值数据", code)
            return pd.DataFrame(columns=["date", "nav"])

        # 标准化列名
        df.columns = [str(c).lower().strip() for c in df.columns]

        date_col: str | None = None
        nav_col: str | None = None
        for col in df.columns:
            if "日期" in col or "date" in col:
                date_col = col
            elif "净值" in col or "nav" in col or "价格" in col or "close" in col:
                nav_col = col

        if date_col is None and len(df.columns) >= 2:
            date_col = df.columns[0]
        if nav_col is None and len(df.columns) >= 2:
            nav_col = df.columns[1]

        if date_col is None or nav_col is None:
            return pd.DataFrame(columns=["date", "nav"])

        result_df = pd.DataFrame({
            "date": pd.to_datetime(df[date_col]),
            "nav": pd.to_numeric(df[nav_col], errors="coerce"),
        })
        result_df = result_df.dropna().sort_values("date").reset_index(drop=True)

        if days > 0 and len(result_df) > 0:
            cutoff = datetime.now() - timedelta(days=days)
            result_df = result_df[result_df["date"] >= cutoff]

        # 缓存
        cache_data = result_df.copy()
        cache_data["date"] = cache_data["date"].dt.strftime("%Y-%m-%d")
        self.cache.set(cache_key, cache_data.to_dict(orient="records"))

        return result_df

    def fetch_holdings(self, code: str) -> list[Holding]:
        """
        港股基金持仓。

        akshare 对港股基金的持仓支持有限，
        大部分情况下无法获取，返回空列表是正常的。
        """
        cache_key = self._cache_key(code, "holdings")
        cached = self.cache.get(cache_key)
        if cached is not None:
            return [Holding(**h) for h in cached]

        logger.debug("港股基金 %s 持仓数据不可用（akshare 限制）", code)
        return []

    def fetch_sector_exposure(self, code: str) -> list[SectorWeight]:
        """港股基金行业分布。通常不可用。"""
        return []
