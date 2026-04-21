"""
A股基金净值历史回填脚本 — 从 tushare Pro 拉取完整历史写入数据湖。

为什么需要单独脚本？
- 现有 CLI 流程（fund-screener --market cn）会跑完整的 MA 筛选 + 持仓拉取，
  对于 500+ 只基金 × 3 年数据，这套流程太重、太慢。
- 本脚本只做一件事：拉净值 → 写 DB。零筛选、零持仓、零行业分布。
- 支持断点续传：中断后重新运行，自动跳过已完成的基金。

用法:
    uv run python src/fund_screener/scripts/backfill_nav_history.py --years 3
    uv run python src/fund_screener/scripts/backfill_nav_history.py --years 3 --resume

数据源:
    tushare Pro fund_nav 接口（与 config.yaml 路由一致）。
    单次 limit 5000，3 年约 750 个交易日，无需分页。
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import tushare as ts
from dotenv import load_dotenv

# 项目根目录加入路径
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from fund_screener.storage import DataStore

logger = logging.getLogger("backfill_nav")

# ---------------------------------------------------------------------------
# 进度持久化 — 断点续传
# ---------------------------------------------------------------------------

_PROGRESS_FILE = Path("data/backfill_nav_progress.json")


def _load_progress() -> dict[str, Any]:
    """加载已完成的基金代码集合。"""
    if _PROGRESS_FILE.exists():
        with open(_PROGRESS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"completed": [], "errors": [], "total": 0, "started_at": None}


def _save_progress(progress: dict[str, Any]) -> None:
    """持久化进度到 JSON 文件。"""
    _PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# tushare 封装
# ---------------------------------------------------------------------------

class TushareNavBackfiller:
    """tushare Pro fund_nav 回填器。"""

    def __init__(self, token: str, delay_sec: float = 0.3) -> None:
        ts.set_token(token)
        self._pro = ts.pro_api()
        self._delay_sec = delay_sec
        self._last_request_time = 0.0

    def _rate_limit(self) -> None:
        """两次请求间限速。"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._delay_sec:
            time.sleep(self._delay_sec - elapsed)
        self._last_request_time = time.time()

    def fetch_full_nav(
        self,
        code: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """
        拉取单只基金的完整净值历史。

        Args:
            code: 基金代码（纯数字，如 005827）
            start_date: YYYYMMDD
            end_date: YYYYMMDD

        Returns:
            DataFrame columns=[date, nav, unit_nav, cumulative_nav, adj_nav]
            空 DataFrame 表示无数据或失败。
        """
        ts_code = f"{code}.OF"
        self._rate_limit()

        try:
            # limit=5000 足够覆盖 3 年（约 750 个交易日）
            df = self._pro.fund_nav(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
                limit=5000,
            )
        except Exception as e:
            logger.warning("tushare fund_nav(%s) 失败: %s", code, e)
            return pd.DataFrame(
                columns=["date", "nav", "unit_nav", "cumulative_nav", "adj_nav"],
            )

        if df is None or df.empty:
            return pd.DataFrame(
                columns=["date", "nav", "unit_nav", "cumulative_nav", "adj_nav"],
            )

        # 统一列名（与 storage.persist_nav_records 期望的格式一致）
        result = pd.DataFrame({
            "date": pd.to_datetime(df["nav_date"], format="%Y%m%d"),
            "nav": pd.to_numeric(df["unit_nav"], errors="coerce"),
            "unit_nav": pd.to_numeric(df["unit_nav"], errors="coerce"),
            "cumulative_nav": pd.to_numeric(df["accum_nav"], errors="coerce"),
            "adj_nav": pd.to_numeric(
                df["adj_nav"] if "adj_nav" in df.columns else df["accum_nav"],
                errors="coerce",
            ),
        })

        result = result.dropna(subset=["date", "nav"])
        result = result.sort_values("date").reset_index(drop=True)
        return result


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def run_backfill(
    db_path: str,
    years: int,
    delay_sec: float,
    token: str,
    resume: bool = True,
) -> dict[str, Any]:
    """
    执行净值历史回填。

    Returns:
        统计字典：{"total", "success", "failed", "skipped", "records_inserted"}
    """
    # 计算日期范围
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=years * 365)
    end_date = end_dt.strftime("%Y%m%d")
    start_date = start_dt.strftime("%Y%m%d")

    logger.info("回填范围: %s → %s (约 %d 年)", start_date, end_date, years)

    # 加载进度
    progress = _load_progress()
    completed: set[str] = set(progress.get("completed", []))
    errors: list[dict[str, str]] = list(progress.get("errors", []))

    if not resume:
        logger.info("--resume 未指定，清空进度从头开始")
        completed = set()
        errors = []

    # 连接数据库，获取 CN 市场所有基金
    store = DataStore(db_path)
    conn = store.get_connection()

    cursor = conn.execute(
        "SELECT code, name FROM funds WHERE market = 'CN' ORDER BY code",
    )
    all_funds = [(row[0], row[1]) for row in cursor.fetchall()]

    if not all_funds:
        logger.error("数据库中无 CN 市场基金，请先运行一次数据采集建立基金列表")
        store.close()
        return {"total": 0, "success": 0, "failed": 0, "skipped": 0, "records_inserted": 0}

    # 初始化回填器
    backfiller = TushareNavBackfiller(token=token, delay_sec=delay_sec)

    total = len(all_funds)
    success = 0
    failed = 0
    skipped = 0
    records_inserted = 0

    logger.info("共 %d 只 CN 基金待回填，已完成 %d 只", total, len(completed))

    try:
        for idx, (code, name) in enumerate(all_funds, 1):
            if code in completed:
                skipped += 1
                continue

            if idx % 10 == 1 or idx == total:
                logger.info(
                    "进度: %d/%d (%s) — 成功 %d | 失败 %d | 跳过 %d",
                    idx, total, code, success, failed, skipped,
                )

            # 拉取净值历史
            nav_df = backfiller.fetch_full_nav(code, start_date, end_date)

            if nav_df.empty:
                logger.warning("  %s (%s) 无数据", code, name)
                errors.append({"code": code, "name": name, "reason": "no_data"})
                failed += 1
                _save_progress({
                    "completed": sorted(completed),
                    "errors": errors,
                    "total": total,
                    "started_at": progress.get("started_at") or datetime.now().isoformat(),
                })
                continue

            # 写入数据库
            store.persist_nav_records("CN", code, nav_df)

            completed.add(code)
            success += 1
            records_inserted += len(nav_df)

            # 每 10 只保存一次进度
            if success % 10 == 0:
                _save_progress({
                    "completed": sorted(completed),
                    "errors": errors,
                    "total": total,
                    "started_at": progress.get("started_at") or datetime.now().isoformat(),
                })

    except KeyboardInterrupt:
        logger.warning("用户中断，保存进度...")
    finally:
        store.close()
        _save_progress({
            "completed": sorted(completed),
            "errors": errors,
            "total": total,
            "started_at": progress.get("started_at") or datetime.now().isoformat(),
        })

    return {
        "total": total,
        "success": success,
        "failed": failed,
        "skipped": skipped,
        "records_inserted": records_inserted,
    }


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="A股基金净值历史回填 — 从 tushare Pro 拉取完整历史写入 SQLite",
    )
    parser.add_argument(
        "--db", default="./data/fund_data.db", help="SQLite 数据库路径",
    )
    parser.add_argument(
        "--years", type=int, default=3, help="回填年数 (默认 3)",
    )
    parser.add_argument(
        "--delay", type=float, default=0.3, help="请求间隔秒数 (默认 0.3)",
    )
    parser.add_argument(
        "--token", default=None, help="tushare token (默认从 TUSHARE_TOKEN 环境变量读取)",
    )
    parser.add_argument(
        "--resume", action="store_true", default=True,
        help="断点续传 (默认开启)",
    )
    parser.add_argument(
        "--no-resume", action="store_true", help="从头开始，忽略已有进度",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="详细日志",
    )

    args = parser.parse_args()

    # 日志
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # 加载 .env
    load_dotenv()

    token = args.token or os.getenv("TUSHARE_TOKEN")
    if not token:
        logger.error("TUSHARE_TOKEN 未设置。请：\n  1. 在 .env 文件写入 TUSHARE_TOKEN=your_token\n  2. 或传 --token 参数")
        sys.exit(1)

    resume = not args.no_resume

    logger.info("=" * 55)
    logger.info("A股基金净值历史回填开始")
    logger.info("数据库: %s", args.db)
    logger.info("回填年数: %d", args.years)
    logger.info("请求间隔: %.1f 秒", args.delay)
    logger.info("断点续传: %s", "开启" if resume else "关闭")
    logger.info("=" * 55)

    stats = run_backfill(
        db_path=args.db,
        years=args.years,
        delay_sec=args.delay,
        token=token,
        resume=resume,
    )

    logger.info("=" * 55)
    logger.info("回填完成")
    logger.info("  总计: %d 只基金", stats["total"])
    logger.info("  成功: %d", stats["success"])
    logger.info("  失败: %d", stats["failed"])
    logger.info("  跳过(已完成): %d", stats["skipped"])
    logger.info("  写入记录: %d 条", stats["records_inserted"])
    logger.info("=" * 55)

    # 打印数据库最新统计
    store = DataStore(args.db)
    db_stats = store.get_stats()
    store.close()

    logger.info("数据库现状:")
    logger.info("  基金数: %d", db_stats.get("funds_count", 0))
    logger.info("  净值记录: %d", db_stats.get("nav_records_count", 0))
    date_min, date_max = db_stats.get("nav_date_range", (None, None))
    if date_min:
        logger.info("  净值时间范围: %s → %s", date_min, date_max)


if __name__ == "__main__":
    main()
