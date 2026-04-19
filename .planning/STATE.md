# State: Fund Screener v1.0

**Current milestone:** v1.0
**Status:** initialized
**Started:** 2026-04-19
**Stopped at:** —

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-04-19)

**Core value:** 用户能在 1 分钟内获取全市场符合趋势条件的基金/ETF 列表
**Current focus:** Phase 1 后端 API 层（FastAPI）— 前端设计系统初版已交付，设计考古异步进行中

## Phase Status

| Phase | Name | Status |
|-------|------|--------|
| 0 | Claude 设计系统 | ✅ 初版已交付 — Token 三层体系 + 6 原子组件 + 3 Hook + framer-motion。等主人完成 design-audit 后对照微调 |
| 1 | 后端 API 层 | 🚧 IN PROGRESS — FastAPI 框架已搭建，6 个 endpoint 全部注册，待 CLI 集成和端到端验证 |
| 2 | 前端仪表盘 | ⏳ PENDING |
| 3 | 回测引擎 | ⏳ PENDING |
| 4 | 定时任务 | ⏳ PENDING |
| 5 | 回测展示 | ⏳ PENDING |

## Decisions Log

| Date | Decision | Context |
|------|----------|---------|
| 2026-04-19 | 项目从 fund-screener 扩展为 "Claude 风格前端 + 后端 API + 回测 + 自动化" | 主人要求复刻 claude.ai/new 样式 |
| 2026-04-19 | 前端设计系统（Phase 0）作为独立 Phase，阻塞前端页面开发，但后端可并行 | 设计考古由主人异步完成 |
| 2026-04-19 | 工作流模式：Interactive（每步确认） | 主人选择 |

## Blockers

| Phase | Blocker | Owner | ETA |
|-------|---------|-------|-----|
| 0 | 需要主人完成 `docs/design-audit-result.md` | 主人 | 待定 |

## Todos

### 等主人（设计考古）
- [ ] 主人：用 DevTools 扒 claude.ai/new 样式，填写 `docs/design-audit-result.md`

### 后端（不依赖前端设计系统，现在就能开工）
- [ ] Phase 1：搭建 FastAPI 后端，暴露 REST API
- [ ] Phase 1：对接 SQLite 数据湖，实现数据查询接口
- [ ] Phase 3：adj_nav 历史回填脚本
- [ ] Phase 3：回测引擎框架
- [ ] Phase 3：MA 策略回测（胜率、夏普比率）
- [ ] Phase 4：定时任务自动化（cron/schedule）
- [ ] Phase 4：报告自动生成 + 任务日志监控

## Notes

- 现有前端在 `web/` 目录，技术栈 Vite + React 19 + Tailwind v4 + shadcn/ui + TanStack Router
- 现有后端在 `src/fund_screener/`，技术栈 Python 3.11 + uv + SQLite + tushare/akshare/yfinance
- 当前前端所有数据为 mock，需要 Phase 1 API 层才能接真数据
- 前端现有路由：/（仪表盘）, /funds（基金列表）, /screening（筛选结果）, /chat（AI 分析）
