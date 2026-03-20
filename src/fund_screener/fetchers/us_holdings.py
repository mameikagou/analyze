"""
美股 ETF 持仓爬虫 — 从 etfdb.com 获取 Top Holdings。

为什么需要这个模块？
yfinance 拿不到 ETF 的持仓明细，而持仓信息对 LLM 做交叉分析至关重要。
etfdb.com 是一个免费的 ETF 信息聚合站，提供大部分美股 ETF 的持仓数据。

踩坑警告：
1. etfdb.com 有反爬机制，必须设置合理的 User-Agent 和请求间隔
2. 部分小众 ETF 在 etfdb.com 上没有持仓数据
3. 网页结构可能变化，爬虫方案长期不稳定，所以静态 JSON 兜底很重要
"""

from __future__ import annotations

import logging
import time

import requests
from bs4 import BeautifulSoup

from fund_screener.models import Holding

logger = logging.getLogger(__name__)

# 模拟正常浏览器请求，降低被反爬检测的概率
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def fetch_etf_holdings_from_web(
    ticker: str,
    delay_sec: float = 1.0,
    timeout_sec: int = 15,
) -> list[Holding]:
    """
    从 etfdb.com 爬取 ETF 的 Top 10 Holdings。

    爬虫逻辑：
    1. 请求 https://etfdb.com/etf/{TICKER}/#holdings
    2. 解析 HTML 表格中的持仓数据
    3. 提取股票名称和权重

    Args:
        ticker: ETF 代码，如 "SPY"
        delay_sec: 请求前的等待时间（限速）
        timeout_sec: HTTP 请求超时

    Returns:
        持仓列表（可能为空，如果爬取失败）
    """
    time.sleep(delay_sec)

    url = f"https://etfdb.com/etf/{ticker}/#holdings"

    try:
        resp = requests.get(url, headers=_HEADERS, timeout=timeout_sec)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning("爬取 ETF %s 持仓失败 (HTTP): %s", ticker, e)
        return []

    try:
        return _parse_holdings_page(resp.text, ticker)
    except Exception as e:
        logger.warning("解析 ETF %s 持仓页面失败: %s", ticker, e)
        return []


def _parse_holdings_page(html: str, ticker: str) -> list[Holding]:
    """
    解析 etfdb.com 的 holdings 表格。

    页面结构（2024 年版本）：
    - 持仓表格在 id="holding-table" 或 class 包含 "holdings" 的 table 里
    - 每行包含：股票名称 / 股票代码 / 权重百分比

    注意：网页结构可能随时变化，这里做了多种选择器的容错处理。
    """
    soup = BeautifulSoup(html, "html.parser")

    # 尝试多种选择器找到持仓表格
    table = (
        soup.find("table", {"id": "holding-table"})
        or soup.find("table", class_=lambda c: c and "holdings" in str(c).lower())
        or soup.find("table", {"data-hash": "holding"})
    )

    if not table:
        # 尝试在整个页面中查找包含 "Holding" 标题的表格
        for t in soup.find_all("table"):
            headers = t.find_all("th")
            header_text = " ".join(th.get_text() for th in headers).lower()
            if "holding" in header_text or "weight" in header_text:
                table = t
                break

    if not table:
        logger.debug("ETF %s 在 etfdb.com 上未找到持仓表格", ticker)
        return []

    holdings: list[Holding] = []
    rows = table.find_all("tr")[1:]  # 跳过表头

    for row in rows[:10]:  # 只取 Top 10
        cells = row.find_all("td")
        if len(cells) < 2:
            continue

        # 通常第一列是股票名称/代码，最后一列或倒数第二列是权重
        stock_name = cells[0].get_text(strip=True)
        stock_code = ""
        weight: float | None = None

        # 尝试从链接中提取股票代码
        link = cells[0].find("a")
        if link:
            stock_name = link.get_text(strip=True)
            href = link.get("href", "")
            # etfdb 链接格式通常是 /stock/AAPL/
            parts = [p for p in href.split("/") if p]
            if parts:
                stock_code = parts[-1].upper()

        # 如果有第二列且看起来像代码
        if len(cells) >= 2 and not stock_code:
            potential_code = cells[1].get_text(strip=True)
            if potential_code.isalpha() and len(potential_code) <= 5:
                stock_code = potential_code.upper()

        # 查找权重列（百分比格式）
        for cell in cells[1:]:
            text = cell.get_text(strip=True).replace("%", "").replace(",", "")
            try:
                val = float(text)
                if 0 < val <= 100:
                    weight = val
                    break
            except ValueError:
                continue

        if stock_name:
            holdings.append(Holding(
                stock_code=stock_code or stock_name[:6],
                stock_name=stock_name,
                weight_pct=weight,
            ))

    if holdings:
        logger.debug("ETF %s 爬取到 %d 只持仓", ticker, len(holdings))

    return holdings
