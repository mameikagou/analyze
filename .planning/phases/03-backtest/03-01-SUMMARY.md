---
phase: 03-backtest
plan: 01
subsystem: quant
tags: [pandas, numpy, vectorbt, factor, backtest, z-score, dataclass]

requires:
  - phase: 02-data
    provides: "DataStore SQLite schema v3 with nav_records, funds tables"
provides:
  - "BaseFactor abstract class + FactorOutput frozen dataclass contract"
  - "MACrossFactor panel-level MA signal computation"
  - "MomentumFactor / SharpeFactor / MaxDrawdownFactor quant score factors"
  - "CompositeFactor with cross-sectional Z-Score normalization"
  - "DataStore.load_nav_panel() wide-format DataFrame loader"
  - "DataStore.load_benchmark() single benchmark series loader"
  - "30 factor unit tests covering normal + boundary cases"
affects:
  - "03-02: BacktestEngine (consumes FactorOutput)"
  - "03-03: API routes (consumes load_nav_panel)"
  - "04-frontend: Backtest page (displays factor results)"

tech-stack:
  added: ["vectorbt==0.26.0"]
  patterns:
    - "Frozen dataclass for immutable factor output contracts"
    - "Abstract base class with __add__ syntax sugar for composition"
    - "Panel-level matrix operations (date x fund_code DataFrame)"
    - "Cross-sectional Z-Score per date row for multi-factor combination"
    - "NaN → False for signal positions (untradeable)"
    - "math.sqrt() for scalar operations (consistent with risk_metrics.py)"

key-files:
  created:
    - src/fund_screener/factors/__init__.py
    - src/fund_screener/factors/base.py
    - src/fund_screener/factors/technical.py
    - src/fund_screener/factors/quant.py
    - src/fund_screener/factors/composite.py
    - tests/test_factors.py
  modified:
    - src/fund_screener/storage.py
    - pyproject.toml

key-decisions:
  - "FactorOutput frozen=True prevents accidental mutation of signal matrices"
  - "CompositeFactor validates kind=='score' at compute time (not init) because kind is output property, not factor property"
  - "MaxDrawdownFactor uses O(n^2) naive implementation with documented optimization path"
  - "load_nav_panel uses f-string only for column name (controlled literal), parameters use ? placeholders for SQL injection prevention"
  - "ffill(limit=5) per D-02 decision: fill short gaps (suspension) but don't bridge long gaps (pre-IPO)"

patterns-established:
  - "All factors accept nav_panel (date x fund_code DataFrame) and output FactorOutput with consistent shape"
  - "Signal factors (kind='signal') output boolean matrices; score factors (kind='score') output float matrices"
  - "NaN positions in nav_panel → False for signals, naturally skipped by rolling for scores"
  - "Cross-sectional Z-Score: per-date mean/std across funds, std=0 → fillna(0)"

requirements-completed: [BACK-01, BACK-02]

duration: 25min
completed: 2026-04-20
---

# Phase 3 Plan 1: Factor Layer + Data Loading Summary

**Factor layer abstraction with BaseFactor/FactorOutput contract, 4 concrete factor implementations (MA cross, momentum, Sharpe, max drawdown), CompositeFactor with Z-Score normalization, and DataStore.load_nav_panel() wide-format loader — establishing the factor/strategy decoupling architecture per ARCHITECTURE.md principles #1 and #2**

## Performance

- **Duration:** 25 min
- **Started:** 2026-04-20T08:30:00Z
- **Completed:** 2026-04-20T08:55:00Z
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments

- Created `factors/` package with 5 files: base abstraction + 4 factor implementations
- `FactorOutput` frozen dataclass ensures immutable signal contracts
- `MACrossFactor` produces boolean signal matrix with first `long` days forced False and NaN positions mapped to False
- `SharpeFactor` uses `math.sqrt(252)` consistent with `risk_metrics.py` pattern, handles std==0 → NaN
- `MaxDrawdownFactor` O(n²) naive rolling implementation with documented optimization path
- `CompositeFactor` performs cross-sectional Z-Score per date row, gracefully handles std=0
- `DataStore.load_nav_panel()` returns wide-format DataFrame with `ffill(limit=5)` and `COALESCE` fallback
- `DataStore.load_benchmark()` loads single benchmark series
- Added `vectorbt==0.26.0` pinned dependency
- 30 unit tests across 7 test classes, all passing

## Task Commits

_Note: Per orchestrator instruction, git commits were not performed during execution. The orchestrator will handle git operations._

1. **Task 1: Create factor layer package** — `src/fund_screener/factors/` (5 files created)
2. **Task 2: Add load_nav_panel() + vectorbt dep** — `src/fund_screener/storage.py`, `pyproject.toml` (modified)
3. **Task 3: Write factor unit tests** — `tests/test_factors.py` (created)

## Files Created/Modified

- `src/fund_screener/factors/__init__.py` — Barrel export of all public symbols
- `src/fund_screener/factors/base.py` — `BaseFactor` ABC + `FactorOutput` frozen dataclass + `__add__` syntax sugar
- `src/fund_screener/factors/technical.py` — `MACrossFactor` panel-level MA crossover signal
- `src/fund_screener/factors/quant.py` — `MomentumFactor`, `SharpeFactor`, `MaxDrawdownFactor`
- `src/fund_screener/factors/composite.py` — `CompositeFactor` with Z-Score normalization and weighted sum
- `src/fund_screener/storage.py` — Added `load_nav_panel()` and `load_benchmark()` methods to `DataStore`
- `pyproject.toml` — Added `"vectorbt==0.26.0"` to dependencies
- `tests/test_factors.py` — 30 tests across 7 classes covering all factors

## Decisions Made

- **CompositeFactor kind validation at compute time, not init**: `kind` is a property of `FactorOutput` (the result of `compute()`), not `BaseFactor` itself. Validating at `compute()` time is the only correct place because a factor's output kind depends on its implementation, not its class identity.
- **MaxDrawdownFactor O(n²) accepted with documentation**: The design doc explicitly calls this out as a known performance issue. The docstring documents the complexity and lists 3 optimization paths (numba, precompute, expanding.apply). Phase 3 prioritizes correctness over performance.
- **f-string for column name in SQL query**: The f-string is only used for `"nav"` vs `"adj_nav"` column selection — a controlled literal, not user input. Actual user-provided parameters (`market`, `start_date`, `end_date`) use `?` parameterized placeholders.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed np.False_ identity comparison in test assertions**
- **Found during:** Task 3 (test execution)
- **Issue:** `assert value is False` fails when `value` is `np.False_` (numpy boolean scalar), because `np.False_ is False` evaluates to `False` in Python identity comparison
- **Fix:** Changed `is False` to `== False` with `# noqa: E712` for pandas boolean matrix elements
- **Files modified:** `tests/test_factors.py`
- **Verification:** `test_nan_positions_are_false` passes

**2. [Rule 1 - Bug] Fixed SharpeFactor math.sqrt verification test**
- **Found during:** Task 3 (test execution)
- **Issue:** Test compared `output.values.iloc[:, 0]` (DataFrame column extraction) against `expected` (Series from `.dropna()`), causing length mismatch (30 vs 29 rows)
- **Fix:** Aligned both sides to use `pct_change()` without `dropna()`, extracted Series from both DataFrames with `.iloc[:, 0]`, filtered by valid mask before comparison
- **Files modified:** `tests/test_factors.py`
- **Verification:** `test_uses_math_sqrt` passes

**3. [Rule 1 - Bug] Fixed np.isfinite DataFrame assertion**
- **Found during:** Task 3 (test execution)
- **Issue:** `np.isfinite(df).all()` on a DataFrame returns a Series (one bool per column), causing "truth value ambiguous" error when used in `assert`
- **Fix:** Changed to `np.isfinite(df).all().all()` to collapse both dimensions
- **Files modified:** `tests/test_factors.py`
- **Verification:** `test_combines_two_score_factors` passes

---

**Total deviations:** 3 auto-fixed (all Rule 1 - test assertion bugs)
**Impact on plan:** All fixes were test-level issues, not implementation bugs. No scope creep.

## Issues Encountered

- **vectorbt installation**: Successfully installed with all dependencies (numba, scipy, scikit-learn, plotly) via `uv`. No compilation issues on macOS Darwin 25.3.0.
- **No other issues** — plan executed smoothly after test assertion fixes.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Factor layer is complete and fully tested — ready for Plan 02 (BacktestEngine with vectorbt integration)
- `load_nav_panel()` provides the exact wide-format DataFrame that `BacktestEngine` needs
- `FactorOutput` contract is stable — any new factor (e.g., sentiment factor) only needs to inherit `BaseFactor` and implement `compute()`
- No blockers for next phase

---
*Phase: 03-backtest*
*Completed: 2026-04-20*
