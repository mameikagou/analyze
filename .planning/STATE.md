# State: Fund Screener v1.0

**Current milestone:** v1.0
**Status:** initialized
**Started:** 2026-04-19
**Stopped at:** —

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-04-19)

**Core value:** 用户能在 1 分钟内获取全市场符合趋势条件的基金/ETF 列表
**Current focus:** Phase 3 回测引擎 — adj_nav 历史回填 + MA 策略回测框架

## Phase Status

| Phase | Name | Status |
|-------|------|--------|
| 0 | Claude 设计系统 | ✅ 初版已交付 — Token 三层体系 + 6 原子组件 + 3 Hook + framer-motion。等主人完成 design-audit 后对照微调 |
| 1 | 后端 API 层 | ✅ COMPLETE — 6 个 endpoint 全部注册并通过验证，CORS 已配置，可直接对接前端 |
| 2 | 前端仪表盘 | ✅ COMPLETE — 5 个 branch 全部完成，所有页面已对接真实 API |
| 3 | 回测引擎 | ⏳ PENDING |
| 4 | 定时任务 | ⏳ PENDING |
| 5 | 回测展示 | ⏳ PENDING |

## Decisions Log

| Date | Decision | Context |
|------|----------|---------|
| 2026-04-19 | 项目从 fund-screener 扩展为 "Claude 风格前端 + 后端 API + 回测 + 自动化" | 主人要求复刻 claude.ai/new 样式 |
| 2026-04-19 | 前端设计系统（Phase 0）作为独立 Phase，阻塞前端页面开发，但后端可并行 | 设计考古由主人异步完成 |
| 2026-04-19 | 工作流模式：Interactive（每步确认） | 主人选择 |
| 2026-04-19 | Phase 1 完成，Phase 2 提前启动 — 不等设计考古 | 主人要求先做能用的前端，样式后续微调 |
| 2026-04-19 | 前端关注点分离架构：功能与样式严格解耦 | 组件粒度样式自包含，页面零样式 |
| 2026-04-19 | Phase 2 拆分为 5 个独立 branch | 主人要求逐个 review/merge |
| 2026-04-19 | API hooks 层统一做 snake_case → camelCase 映射 | 后端保持 Pythonic，前端用 camelCase，边界在 hook 层 |

## Blockers

| Phase | Blocker | Owner | ETA |
|-------|---------|-------|-----|
| 0 | 需要主人完成 `docs/design-audit-result.md` | 主人 | 待定 |

## Todos

### 等主人（设计考古）
- [ ] 主人：用 DevTools 扒 claude.ai/new 样式，填写 `docs/design-audit-result.md`

### Phase 1（已完成 ✅）
- [x] Phase 1：搭建 FastAPI 后端，暴露 REST API — `/health`, `/api/funds`, `/api/funds/{code}`, `/api/screening`, `/api/chart/{code}`, `/api/stats`
- [x] Phase 1：对接 SQLite 数据湖，直接复用 storage.py 查询逻辑

### Phase 2（进行中 🚧）— 按 5 个 branch 拆分
- [x] **Branch 1** `feat/api-hooks`：5 个 API hooks（useFunds/useFundDetail/useScreening/useChartData/useStats）+ barrel export — ✅ COMPLETE (commit a06da8a)
- [x] **Branch 2** `feat/animation-tokens`：animation.tokens.ts + chart tokens CSS + CVA variants — ✅ COMPLETE (已合入 main)
- [x] **Branch 3** `feat/ui-components`：10 个业务组件 + barrel export — ✅ COMPLETE (commit f4e8b7d)
- [x] **Branch 4** `feat/fund-detail-page`：新建 `/funds/$code` 动态路由 + 详情页布局 — ✅ COMPLETE
- [x] **Branch 5** `feat/pages-migrate`：4 个页面迁移（Dashboard/FundList/Screening/Chat），mock → 真数据 — ✅ COMPLETE

### 待开工（后端后续 Phase）
- [ ] Phase 3：adj_nav 历史回填脚本
- [ ] Phase 3：回测引擎框架
- [ ] Phase 3：MA 策略回测（胜率、夏普比率）
- [ ] Phase 4：定时任务自动化（cron/schedule）
- [ ] Phase 4：报告自动生成 + 任务日志监控

## Notes

- 现有前端在 `web/` 目录，技术栈 Vite + React 19 + Tailwind v4 + shadcn/ui + TanStack Router
- 现有后端在 `src/fund_screener/`，技术栈 Python 3.11 + uv + SQLite + tushare/akshare/yfinance
- 前端现有路由：/（仪表盘）, /funds（基金列表）, /screening（筛选结果）, /chat（AI 分析）
- Phase 2 分支拆分（主人逐个 review/merge）：
  - Branch 1 `feat/api-hooks`：5 个 API hooks
  - Branch 2 `feat/animation-tokens`：动画 + 图表 Token
  - Branch 3 `feat/ui-components`：10 个业务组件
  - Branch 4 `feat/fund-detail-page`：/funds/$code 详情页
  - Branch 5 `feat/pages-migrate`：4 页面 mock → 真数据
- 关注点分离：页面零样式，组件样式自包含，Token 集中管理
