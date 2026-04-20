---
phase: 03-backtest
plan: 04
subsystem: ui
tags: [react, tanstack-query, tanstack-router, canvas, tailwind]

requires:
  - phase: 03-backtest
    provides: "POST /api/backtest/run endpoint (Plan 03-03)"
provides:
  - "useBacktest hook with useMutation for POST /api/backtest/run"
  - "/backtest route with configuration panel, equity curve chart, performance stats, rebalance history"
  - "Sidebar navigation with '策略回测' item"
affects:
  - 03-backtest

tech-stack:
  added: []
  patterns:
    - "useMutation for POST requests (vs useQuery for GET)"
    - "Canvas-based chart rendering (no external chart lib)"
    - "Expandable table rows for nested data display"

key-files:
  created:
    - web/src/hooks/api/useBacktest.ts
    - web/src/routes/backtest/index.tsx
  modified:
    - web/src/hooks/api/index.ts
    - web/src/routes/__root.tsx
    - web/src/routeTree.gen.ts

key-decisions:
  - "Canvas-based chart instead of external library — keeps bundle small, sufficient for Phase 3"
  - "useMutation (not useQuery) for backtest — POST request that creates/computes results"
  - "All sub-components (EquityCurveChart, RebalanceTable) co-located in page file — simple enough, no need to extract"

patterns-established:
  - "useMutation hook pattern: camelCase types + snake_case API mapping at boundary"
  - "Canvas chart component: useRef + useEffect for imperative drawing"
  - "Expandable table: local state for row expansion, grid layout for holdings detail"

requirements-completed: [BACK-03, BACK-04]

duration: 3min
completed: 2026-04-20T10:32:24Z
---

# Phase 3 Plan 04: 前端回测页 Summary

**前端回测页：配置面板 + Canvas 净值曲线 + 绩效统计卡片 + 可展开调仓历史表，通过 useMutation 调用 POST /api/backtest/run**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-20T10:28:50Z
- **Completed:** 2026-04-20T10:32:24Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments
- useBacktest hook with useMutation, full type definitions, snake_case API mapping
- /backtest page with 8-parameter configuration form, 4 stat cards, canvas equity curve chart, expandable rebalance table
- Sidebar navigation updated with "策略回测" link (LineChart icon)
- Route tree regenerated via TanStack Router CLI

## Task Commits

Each task was committed atomically:

1. **Task 1: Create useBacktest hook + update barrel export** - `95a673f` (feat)
2. **Task 2: Create backtest page component** - `488ecf2` (feat)
3. **Task 3: Update sidebar navigation + regenerate routes** - `3de4f70` (feat)

**Plan metadata:** `TBD` (docs: complete plan)

## Files Created/Modified
- `web/src/hooks/api/useBacktest.ts` - TanStack Query useMutation hook for backtest API, all type definitions
- `web/src/hooks/api/index.ts` - Added useBacktest and type exports to barrel
- `web/src/routes/backtest/index.tsx` - Backtest page: form, stats cards, canvas chart, expandable rebalance table
- `web/src/routes/__root.tsx` - Added "策略回测" nav item with LineChart icon
- `web/src/routeTree.gen.ts` - Auto-regenerated with /backtest route

## Decisions Made
- Canvas-based chart instead of external library — keeps bundle small, sufficient for Phase 3
- useMutation (not useQuery) for backtest — POST request that creates/computes results
- All sub-components co-located in page file — simple enough, no need to extract

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 3 全部完成（4 个 plan：因子层、回测引擎、API 层、前端页）
- 准备进入 Phase 4：定时任务自动化

## Self-Check: PASSED

- [x] `web/src/hooks/api/useBacktest.ts` exists
- [x] `web/src/routes/backtest/index.tsx` exists
- [x] `git log --oneline --all | grep -q "95a673f"` — FOUND
- [x] `git log --oneline --all | grep -q "488ecf2"` — FOUND
- [x] `git log --oneline --all | grep -q "3de4f70"` — FOUND
- [x] `bunx tsc --noEmit` — PASSED (zero errors)

---
*Phase: 03-backtest*
*Completed: 2026-04-20*
