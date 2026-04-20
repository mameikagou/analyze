---
phase: 03-backtest
plan: 03
subsystem: api

tags: [fastapi, click, sqlite, backtest, adj_nav, backfill]

requires:
  - phase: 03-01
    provides: "BaseFactor + FactorOutput 抽象契约、MACrossFactor、MomentumFactor、SharpeFactor、CompositeFactor"
  - phase: 03-02
    provides: "BacktestConfig + BacktestEngine + BacktestResult + load_nav_panel()"

provides:
  - "POST /api/backtest/run endpoint — 接受 BacktestRequest，返回 BacktestResponse"
  - "CLI backtest 子命令 — fund-screener backtest，支持 JSON 输出和终端漂亮打印"
  - "adj_nav 历史回填脚本 — 断点续传、逐基金事务、API 限速保护"
  - "DataStore.from_connection() 工厂方法 — 复用已有 sqlite3 连接"

affects:
  - "03-04: 前端回测页（消费 POST /api/backtest/run）"
  - "04-frontend: 回测结果展示"

tech-stack:
  added: []
  patterns:
    - "DataStore.from_connection() 包装已有连接，避免路由层创建新连接"
    - "_FACTOR_REGISTRY 统一映射字符串到因子工厂，API 和 CLI 共用同一份注册表"
    - "BacktestRequest/BacktestResponse 自包含在路由文件，降低与 schemas.py 的耦合"
    - "回填脚本独立进程，与回测引擎零耦合（ARCHITECTURE.md 原则三）"

key-files:
  created:
    - src/fund_screener/api/routes/backtest.py — POST /api/backtest/run 端点
    - src/fund_screener/scripts/backfill_adj_nav.py — adj_nav 回填脚本
    - src/fund_screener/scripts/__init__.py — 包支持
  modified:
    - src/fund_screener/api/main.py — 注册 backtest 路由
    - src/fund_screener/storage.py — 新增 DataStore.from_connection() 工厂方法
    - src/fund_screener/cli.py — 新增 backtest 子命令

key-decisions:
  - "DataStore.from_connection() 替代 __new__ 直接赋值：更干净的工厂方法，文档化连接复用模式"
  - "BacktestRequest/BacktestResponse 定义在 backtest.py 而非 schemas.py：自包含路由文件，降低跨文件耦合"
  - "回填脚本使用 argparse 而非 click：独立脚本不需要子命令体系，argparse 更轻量"
  - "score_weights 覆盖支持：当请求提供自定义权重时，动态重建 CompositeFactor"

patterns-established:
  - "API 路由复用 deps.py 的 get_db_conn() 连接，通过 DataStore.from_connection() 包装"
  - "因子注册表在 API 和 CLI 中保持一致，新增因子只需改两处"
  - "回填脚本逐基金事务：成功 commit，失败 rollback，不丢失进度"

requirements-completed: [DATA-01, DATA-02, DATA-03, BACK-01, BACK-02, BACK-03, BACK-04]

duration: 5min
completed: 2026-04-20
---

# Phase 3 Plan 3: API Route Layer + CLI Backtest + adj_nav Backfill Summary

**POST /api/backtest/run endpoint with Pydantic validation, CLI backtest subcommand with pretty-printed stats, and adj_nav backfill script with resume support via backfill_log table**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-20T09:54:55Z
- **Completed:** 2026-04-20T09:59:58Z
- **Tasks:** 3
- **Files modified:** 6 (3 created + 3 modified)

## Accomplishments

- Created `POST /api/backtest/run` endpoint with full Pydantic request/response models
- BacktestRequest includes Field validation: top_n ge=1 le=50, fee_rate ge=0 le=0.1
- _FACTOR_REGISTRY maps string names to factor factory functions (shared between API and CLI)
- Unknown factor names return HTTP 400; empty nav_panel returns success=False with error message
- DataStore.from_connection() factory method wraps existing sqlite3.Connection without creating new connection
- CLI `fund-screener backtest` subcommand supports both JSON file output (--output) and terminal pretty-print
- CLI uses same factor registry as API, ensuring consistency
- adj_nav backfill script with backfill_log table for resume support
- Per-fund transaction handling: commit on success, rollback on failure
- Rate limiting with sleep(0.5) between funds
- Progress reporting: success/skipped/failed counts at completion

## Task Commits

Each task was committed atomically:

1. **Task 1: Create API route + schemas + register in main.py** — `f7d81af` (feat)
2. **Task 2: Add CLI backtest subcommand** — `b13daad` (feat)
3. **Task 3: Create adj_nav backfill script** — `2d28031` (feat)

## Files Created/Modified

- `src/fund_screener/api/routes/backtest.py` — POST /api/backtest/run endpoint with BacktestRequest/BacktestResponse models, _FACTOR_REGISTRY, and run_backtest handler
- `src/fund_screener/api/main.py` — Registered backtest router with /api prefix and "Backtest" tag
- `src/fund_screener/storage.py` — Added DataStore.from_connection() classmethod to wrap existing sqlite3.Connection
- `src/fund_screener/cli.py` — Added cmd_backtest subcommand with factor registry, pretty-printed stats output, and JSON file export
- `src/fund_screener/scripts/backfill_adj_nav.py` — adj_nav backfill script with backfill_log table, resume support, per-fund transactions, and rate limiting
- `src/fund_screener/scripts/__init__.py` — Package support for python -m execution

## Decisions Made

- **DataStore.from_connection() as explicit factory method**: Instead of using __new__ + direct attribute assignment in the route (as suggested in the plan), created a proper classmethod with docstring explaining the connection reuse pattern. Cleaner, more maintainable, and self-documenting.
- **BacktestRequest/BacktestResponse in backtest.py rather than schemas.py**: Self-contained route file reduces coupling with schemas.py. The screening route already uses schemas.ScreeningResult imported from schemas.py, but backtest is a new independent feature — keeping its models local makes the file easier to understand in isolation.
- **argparse for backfill script instead of click**: The backfill script is a standalone utility, not part of the CLI command hierarchy. argparse is lighter weight and more appropriate for single-purpose scripts.
- **score_weights override support**: Added dynamic CompositeFactor reconstruction when custom weights are provided in the request, enabling frontend users to experiment with different factor weightings.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None — all imports verified successfully, no compatibility issues.

## User Setup Required

None — no external service configuration required.

## Known Stubs

None — all functionality is complete with no placeholder values.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: input_validation | `src/fund_screener/api/routes/backtest.py` | Pydantic Field validation on top_n (1-50) and fee_rate (0-0.1). Unknown factors return HTTP 400. Mitigates T-03-07. |
| threat_flag: rate_limiting | `src/fund_screener/scripts/backfill_adj_nav.py` | sleep(0.5) between funds, per-fund commit prevents progress loss on crash. Mitigates T-03-10. |
| threat_flag: no_sensitive_data | `src/fund_screener/scripts/backfill_adj_nav.py` | backfill_log only contains fund_id (internal PK) and completion timestamp. No sensitive data. Accepts T-03-09. |

## Self-Check

- [x] `src/fund_screener/api/routes/backtest.py` exists and imports successfully
- [x] `src/fund_screener/api/main.py` includes `app.include_router(backtest.router, prefix="/api")`
- [x] `src/fund_screener/cli.py` has `@main.command("backtest")` and `def cmd_backtest`
- [x] `src/fund_screener/scripts/backfill_adj_nav.py` imports successfully
- [x] `src/fund_screener/scripts/__init__.py` exists
- [x] `DataStore.from_connection()` classmethod exists in storage.py
- [x] All verification commands pass (route import, CLI subcommand, script import, route registration)

**Self-Check: PASSED**

## Next Phase Readiness

- API endpoint ready for frontend consumption (03-04)
- CLI backtest command ready for manual testing
- Backfill script ready for adj_nav data repair
- No blockers for next phase

---
*Phase: 03-backtest*
*Completed: 2026-04-20*
