"""reporter 模块单元测试。"""

import tempfile
from datetime import date
from pathlib import Path

from fund_screener.models import (
    FundInfo,
    Holding,
    Market,
    ScreeningSummary,
    SectorWeight,
    TrendStats,
)
from fund_screener.reporter import generate_report


class TestGenerateReport:
    """测试报告生成。"""

    def test_basic_report_generation(self) -> None:
        """基本报告生成：验证文件创建和关键内容。"""
        funds = [
            FundInfo(
                code="SPY",
                name="SPDR S&P 500 ETF",
                market=Market.US,
                nav=450.0,
                ma_short=448.0,
                ma_long=440.0,
                ma_diff_pct=1.82,
                top_holdings=[
                    Holding(stock_code="AAPL", stock_name="Apple Inc", weight_pct=7.1),
                    Holding(stock_code="MSFT", stock_name="Microsoft Corp", weight_pct=6.5),
                ],
                sector_exposure=[
                    SectorWeight(sector="Technology", weight_pct=32.0),
                ],
                daily_change_pct=1.25,
                trend_stats=TrendStats(
                    change_1w=2.30,
                    change_1m=5.10,
                    change_3m=8.70,
                    change_6m=12.40,
                    change_1y=18.60,
                ),
                data_date=date(2026, 3, 20),
            ),
        ]
        summaries = [
            ScreeningSummary(
                market=Market.US,
                total_scanned=100,
                total_passed=1,
                pass_rate=1.0,
            ),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_report.md"
            result = generate_report(
                funds=funds,
                summaries=summaries,
                output_path=output_path,
            )

            assert result.exists()
            content = result.read_text(encoding="utf-8")

            # 验证关键内容存在
            assert "趋势筛选报告" in content
            assert "SPY" in content
            assert "SPDR S&P 500 ETF" in content
            assert "AAPL" in content
            assert "Apple Inc" in content
            assert "Technology" in content
            assert "MA20" in content
            assert "+1.82%" in content
            assert "+1.25%" in content  # 当日涨跌
            assert "走势" in content
            assert "1周 +2.30%" in content
            assert "1年 +18.60%" in content
            assert "LLM" in content

    def test_empty_funds_report(self) -> None:
        """空基金列表也能生成报告（只有概览和 LLM 提示词）。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "empty_report.md"
            result = generate_report(
                funds=[],
                summaries=[],
                output_path=output_path,
            )

            assert result.exists()
            content = result.read_text(encoding="utf-8")
            assert "筛选报告" in content
