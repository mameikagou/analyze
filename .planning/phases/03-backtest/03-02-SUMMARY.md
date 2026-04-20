---
phase: 03-backtest
plan: 02
subsystem: backtest
tags: [vectorbt, pandas, backtest, portfolio, dataclass, frozen]

requires:
  - phase: 03-01
    provides: "BaseFactor + FactorOutput 抽象契约、MACrossFactor、MomentumFactor、SharpeFactor、CompositeFactor"
provides:
  - "BacktestConfig frozen dataclass — 所有回测参数的集中定义"
  - "BacktestEngine — signal_df × nav_df → target_weights → vbt → metrics"
  - "BacktestResult — 封装 vbt.Portfolio 并提供 JSON 序列化"
  - "backtest/ 包 barrel export — 统一导入接口"
  - "tests/test_backtest.py — 24 个单元测试覆盖 config、weights、filter、serialization、E2E"
affects:
  - "03-03: API 路由层（将调用 BacktestEngine.run()）"
  - "03-04: CLI backtest 子命令"
  - "04-01: 前端回测页面（消费 to_api_response() 输出）"

tech-stack:
  added: ["vectorbt==0.26.0 (已存在)", "numpy==1.26.4 (降级兼容)"]
  patterns:
    - "frozen dataclass 做配置对象，防止回测过程中被意外修改"
    - "TYPE_CHECKING 避免循环导入（config.py ↔ base.py）"
    - "vectorbt 导入做 try/except 容错，安装失败时给出清晰提示"
    - "NaN = 保持持仓（vbt 忽略），0.0 = 清仓，正数 = 目标权重"
    - "to_api_response() 显式提取可序列化字段，绝不泄漏内部对象"

key-files:
  created:
    - "src/fund_screener/backtest/__init__.py — barrel export"
    - "src/fund_screener/backtest/config.py — BacktestConfig frozen dataclass"
    - "src/fund_screener/backtest/engine.py — BacktestEngine 核心引擎"
    - "src/fund_screener/backtest/result.py — BacktestResult 序列化"
    - "tests/test_backtest.py — 24 个单元测试"
  modified:
    - "pyproject.toml — numpy 降级 2.4.3 → 1.26.4，plotly 降级 6.7.0 → 5.18.0"

key-decisions:
  - "numpy 降级到 1.26.4：vectorbt 0.26.0 与 numpy 2.x 不兼容（_broadcast_shape API 变更）"
  - "plotly 降级到 5.18.0：vectorbt 0.26.0 依赖的 heatmapgl 模板在新版 plotly 中已移除"
  - "_build_target_weights 中 NaN 分数用 dropna() 排除：避免 NaN 参与 nlargest 排序导致不可预测结果"
  - "score 加权用 min-shift + 1e-6 归一化：处理负分数场景，保证权重为正且和为 1.0"

patterns-established:
  - "回测层只做 signal_df × nav_df → 绩效指标（ARCHITECTURE.md 原则三）"
  - "vectorbt from_orders(size_type='targetpercent') 处理资金管理，不手写资金分配"
  - "to_api_response() 是 API 边界，必须完全 JSON 序列化"

requirements-completed: [BACK-01, BACK-02, BACK-03, BACK-04]

duration: 35min
completed: 2026-04-20
---

# Phase 3 Plan 2: Backtest Engine Core Summary

**Backtest engine with vectorbt v1 Portfolio.from_orders, frozen BacktestConfig, equal/score weighting, signal filtering, and fully JSON-serializable BacktestResult.to_api_response()**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-04-20
- **Completed:** 2026-04-20
- **Tasks:** 2
- **Files modified:** 5 (4 created + 1 pyproject.toml modified)

## Accomplishments

- Created `backtest/` package with 4 files: config, engine, result, __init__
- `BacktestConfig` frozen dataclass with all tunable parameters (top_n, rebalance_freq, weighting, fee_rate, init_cash, signal_filter, benchmark_code, use_adj_nav)
- `BacktestEngine.run()` executes full pipeline: score_factor.compute() → signal_filter.apply() → _build_target_weights() → vbt.Portfolio.from_orders()
- `_build_target_weights()` supports equal weighting (1/N) and score weighting (min-max normalized), handles empty portfolio (all cash), NaN exclusion, and -inf filtering
- `BacktestResult.to_api_response()` returns fully JSON-serializable dict with stats, equity_curve, drawdown, rebalance_history
- 24 unit tests covering: frozen config, equal/score weighting, signal filter, empty portfolio, JSON serialization, rebalance history format, end-to-end with synthetic data

## Task Commits

_Note: Per user instruction, commits were not made — the orchestrator will handle git operations._

## Files Created/Modified

- `src/fund_screener/backtest/__init__.py` — Barrel export: BacktestConfig, BacktestEngine, BacktestResult
- `src/fund_screener/backtest/config.py` — Frozen dataclass with all backtest parameters, TYPE_CHECKING guard for BaseFactor to avoid circular import
- `src/fund_screener/backtest/engine.py` — Core engine: run() orchestrates factor computation → filter → weights → vectorbt; _build_target_weights() generates rebalance schedule with Top N selection
- `src/fund_screener/backtest/result.py` — Wraps vbt.Portfolio, provides stats()/equity_curve()/drawdown_curve()/returns()/rebalance_history()/to_api_response()
- `tests/test_backtest.py` — 24 tests across 5 classes: TestBacktestConfig, TestBuildTargetWeights, TestBacktestResult, TestEndToEnd, TestImports
- `pyproject.toml` — numpy 1.26.4 + plotly 5.18.0 (dependency downgrades for vectorbt compatibility)

## Decisions Made

- **numpy 降级 2.4.3 → 1.26.4**: vectorbt 0.26.0 依赖 numpy 1.x 的内部 API `_broadcast_shape`，numpy 2.x 已移除该符号。这是 BACKTEST_DESIGN.md §12 中列出的已知风险。
- **plotly 降级 6.7.0 → 5.18.0**: vectorbt 0.26.0 初始化时注册 plotly 模板用了 `heatmapgl`，plotly 6.x 已移除该 trace 类型。降级到 5.18.0 解决。
- **NaN 分数排除策略**: `_build_target_weights` 中先用 `row > -np.inf` 排除 signal_filter 过滤的，再用 `dropna()` 排除数据缺失的。避免 NaN 参与 `nlargest()` 排序产生不可预测结果。
- **score 加权归一化**: 用 `top_funds - min_score + 1e-6` 处理负分数场景，保证所有权重为正且总和严格为 1.0。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] numpy/plotly 版本兼容性修复**
- **Found during:** Task 1 (import verification)
- **Issue:** vectorbt 0.26.0 导入失败 —— numpy 2.4.3 的 `_broadcast_shape` API 变更 + plotly 6.7.0 移除 `heatmapgl`
- **Fix:** 降级 numpy 到 1.26.4，降级 plotly 到 5.18.0
- **Files modified:** `pyproject.toml`
- **Verification:** `uv run python -c "import vectorbt; print(vectorbt.__version__)"` 输出 `0.26.0`

**2. [Rule 1 - Bug] test_frozen_instance_error_specific 测试用例错误**
- **Found during:** Task 2 (test execution)
- **Issue:** 测试用 `object.__setattr__()` 绕过 frozen dataclass 限制，没有抛出 AttributeError
- **Fix:** 改为正常的属性赋值 `config.top_n = 99`，正确触发 FrozenInstanceError
- **Files modified:** `tests/test_backtest.py`
- **Verification:** 24/24 测试通过

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** 依赖降级是已知风险（BACKTEST_DESIGN.md §12），测试修复是测试代码本身的问题。无架构变更。

## Issues Encountered

- **vectorbt 兼容性问题**: numpy 2.x + plotly 6.x 与 vectorbt 0.26.0 不兼容。已按 BACKTEST_DESIGN.md §12 的风险回退方案处理（降级依赖）。未来升级 vectorbt 到支持 numpy 2.x 的版本后可恢复。

## Known Stubs

None — 所有功能均完整实现，无占位符或硬编码空值。

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: serialization | `src/fund_screener/backtest/result.py` | `to_api_response()` 显式提取 9 个 stats 字段，round 浮点数，转字符串日期。已按 T-03-05 缓解。 |
| threat_flag: weight_sum | `src/fund_screener/backtest/engine.py` | `_build_target_weights` 等权路径保证 sum=1.0（1/N × N），score 路径保证 sum=1.0（shifted/sum）。已按 T-03-06 缓解。 |

## Self-Check

- [x] `src/fund_screener/backtest/__init__.py` exists
- [x] `src/fund_screener/backtest/config.py` exists
- [x] `src/fund_screener/backtest/engine.py` exists
- [x] `src/fund_screener/backtest/result.py` exists
- [x] `tests/test_backtest.py` exists
- [x] All imports succeed: `from fund_screener.backtest import BacktestConfig, BacktestEngine, BacktestResult`
- [x] BacktestConfig frozen: mutation raises FrozenInstanceError
- [x] `uv run pytest tests/test_backtest.py -v` — 24/24 passed
- [x] `grep "size_type.*targetpercent"` confirms vectorbt integration

**Self-Check: PASSED**

## Next Phase Readiness

- backtest/ 包已完成，可独立运行回测
- 下一步（03-03）: API 路由层 `POST /api/backtest/run`，将调用 `BacktestEngine.run()` 和 `to_api_response()`
- 下一步（03-04）: CLI `backtest` 子命令
- 无阻塞项

---
*Phase: 03-backtest*
*Completed: 2026-04-20*
