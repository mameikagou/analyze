# State: Fund Screener v1.0

**Current milestone:** v1.0
**Status:** initialized
**Started:** 2026-04-19
**Stopped at:** 2026-04-21 — Phase 4 UI Renovation 全部完成（3 个 plan：Token/DarkMode/Animation + Component Unification/Backtest Renovation + Global Experience/Mobile Responsive）

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-04-19)

**Core value:** 用户能在 1 分钟内获取全市场符合趋势条件的基金/ETF 列表
**Current focus:** Phase 4 全部完成，前端视觉体系统一、暗色模式、动画体系、移动端适配、全局 Toast + ErrorBoundary 已就绪

## Phase Status

| Phase | Name | Status |
|-------|------|--------|
| 0 | Claude 设计系统 | ✅ 初版已交付 — Token 三层体系 + 6 原子组件 + 3 Hook + framer-motion。等主人完成 design-audit 后对照微调 |
| 1 | 后端 API 层 | ✅ COMPLETE — 6 个 endpoint 全部注册并通过验证，CORS 已配置，可直接对接前端 |
| 2 | 前端仪表盘 | ✅ COMPLETE — 5 个 branch 全部完成，所有页面已对接真实 API |
| 3 | 回测引擎 | ✅ COMPLETE — 4 个 plan 全部完成（因子层 + 回测引擎 + API 层 + 前端页） |
| 4 | UI 翻新 (UI Renovation) | ✅ COMPLETE — 3 个 plan 全部完成：Token 修复/暗色模式/动画体系 + 组件统一/回测页翻新 + 全局体验/移动端适配 |
| 5 | 定时任务 | ⏳ PENDING |
| 6 | 回测展示增强 | ⏳ PENDING |

## Decisions Log

| Date | Decision | Context |
|------|----------|---------|
| 2026-04-21 | Phase 4 新增 `--highlight-on-accent` 语义 Token | stepper 激活态圆圈需要 accent 背景上的半透明高亮，使用 `rgba(255,255,255,0.2)` 在 light/dark 下保持一致 |
| 2026-04-21 | 前端所有 API 错误统一走 Toast，不再全页阻塞 | 用户体验决策：网络抖动不应阻断页面其他功能 |
| 2026-04-21 | ESLint 强制颜色纪律：`no-restricted-syntax` 禁止所有硬编码 Tailwind 颜色类 | 维护设计系统一致性，所有颜色必须走语义 Token |
| 2026-04-19 | 项目从 fund-screener 扩展为 "Claude 风格前端 + 后端 API + 回测 + 自动化" | 主人要求复刻 claude.ai/new 样式 |
| 2026-04-20 | Phase 3 回测引擎引入 vectorbt v1（而非手写） | `Portfolio.from_orders(size_type='targetpercent')` 用 Numba 在 C 级别处理资金管理/再平衡/订单生成，消灭手算资金分配最易出错的环节 |
| 2026-04-20 | nav_panel NaN 处理策略：ffill + 上市后才开始算 | 保持宽表格式（因子层可矩阵运算），每只基金上市前用 NaN（不参与），上市后缺失用 ffill，回测引擎遇到 NaN 跳过 |
| 2026-04-20 | Phase 3 回测框架与 adj_nav 回填并行推进 | 两者零耦合，框架先用现有 nav 验证，回填完成后切 adj_nav 只需改数据源一行 |
| 2026-04-20 | Phase 3 采用"新增因子层 + 兼容层"策略 | 前端 API 已稳定，不改现有 `ScreenResult`/`ScoredFund` 返回格式。回测走新 `factors/` 包，现有 CLI/API 不受影响 |
| 2026-04-20 | Phase 3 暂不支持 kind='weight' 因子，但预留接口 | 导入公开持仓做跟投回测是未来拓展，Phase 3 核心是验证 MA + 三因子的有效性 |
| 2026-04-20 | 前端回测页使用 Canvas 绘制净值曲线（非外部图表库） | 保持 bundle 体积可控，Phase 3 够用；后续如需多 series 叠加再引入专业图表库 |
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

### Phase 2（已完成 ✅）— 按 5 个 branch 拆分
- [x] **Branch 1** `feat/api-hooks`：5 个 API hooks（useFunds/useFundDetail/useScreening/useChartData/useStats）+ barrel export — ✅ COMPLETE (commit a06da8a)
- [x] **Branch 2** `feat/animation-tokens`：animation.tokens.ts + chart tokens CSS + CVA variants — ✅ COMPLETE (已合入 main)
- [x] **Branch 3** `feat/ui-components`：10 个业务组件 + barrel export — ✅ COMPLETE (commit f4e8b7d)
- [x] **Branch 4** `feat/fund-detail-page`：新建 `/funds/$code` 动态路由 + 详情页布局 — ✅ COMPLETE
- [x] **Branch 5** `feat/pages-migrate`：4 个页面迁移（Dashboard/FundList/Screening/Chat），mock → 真数据 — ✅ COMPLETE

### Phase 3（已完成 ✅）— 回测引擎
详见 `.planning/phases/03-backtest/`

**Plan 03-01（Wave 1）：因子层 + 数据加载** — requirements: BACK-01, BACK-02 ✅ COMPLETE
- [x] `factors/base.py` — BaseFactor + FactorOutput 抽象契约
- [x] `factors/technical.py` — MACrossFactor（MA 多头排列信号）
- [x] `factors/quant.py` — MomentumFactor / SharpeFactor / DrawdownFactor
- [x] `factors/composite.py` — CompositeFactor（Z-Score 标准化 + 加权）
- [x] `storage.py` — 新增 `load_nav_panel()` 宽表加载方法
- [x] 单元测试 — 30 个 test cases, 全部通过

**Plan 03-02（Wave 2）：回测引擎核心** — requirements: BACK-01~04 ✅ COMPLETE
- [x] `backtest/config.py` — BacktestConfig（frozen dataclass）
- [x] `backtest/engine.py` — BacktestEngine（vectorbt v1 `from_orders` 集成）
- [x] `backtest/result.py` — BacktestResult（指标 + 净值曲线 + 回撤 + 序列化）
- [x] 单元测试 — 24 个测试覆盖等权调仓 / score 加权 / signal 过滤 / 空仓

**Plan 03-03（Wave 3）：API 层 + adj_nav 回填** — requirements: DATA-01~03, BACK-01~04 ✅ COMPLETE
- [x] `api/routes/backtest.py` — POST `/api/backtest/run`
- [x] `api/main.py` — 注册回测路由
- [x] `scripts/backfill_adj_nav.py` — adj_nav 历史回填脚本（断点续传）
- [x] 全量回填 — 后台运行，记录进度

**Plan 03-04（Wave 4）：前端回测页** — requirements: BACK-03, BACK-04 ✅ COMPLETE
- [x] `/backtest` 路由 — 配置面板 + 净值曲线 + 绩效卡片 + 调仓历史表
- [x] `useBacktest` hook — POST `/api/backtest/run`
- [x] 侧边栏导航更新

### Phase 4（已完成 ✅）— UI 翻新 (UI Renovation)
详见 `.planning/phases/04-ui-renovation/`

**Plan 04-01（Wave 1~2）：Token 修复 + 暗色模式 + 动画体系** ✅ COMPLETE
- [x] `tokens.semantic.css` — 修复 `--bg-surface` 为 `#ffffff`，确保卡片白底
- [x] `tokens.chart.css` — 新增 chart 语义 Token（涨跌色/均线色/网格色）
- [x] `index.css` — shadcn HSL 桥接，映射到 Stone 色系
- [x] `useTheme.ts` / `ThemeProvider` — localStorage 持久化 + class 切换
- [x] `PageTransition` — `AnimatePresence mode="wait"` + reduced-motion 支持
- [x] `tokens.animation.ts` — 统一 presence / transition / stagger Token

**Plan 04-02（Wave 3~4）：组件层统一 + 回测页翻新** ✅ COMPLETE
- [x] `Surface` / `IconButton` / `TextButton` — 语义 Token 化
- [x] `FundTable` — Surface 容器化 + `overflow-x-auto` 移动端适配
- [x] `backtest/index.tsx` — 4 步 Stepper 向导 + LightweightChart 替换 Canvas
- [x] `StatsCard` / `MarketBadge` / `FundDetailHeader` — Token 统一

**Plan 04-03（Wave 5）：全局体验优化 + 移动端适配 + 质量门禁** ✅ COMPLETE
- [x] `ErrorBoundary` — 全局渲染错误捕获，防白屏
- [x] `Toast` 系统 — useToast hook + ToastProvider + 自动消失 + 动画
- [x] 5 个页面 API 错误处理改造 — 全页错误 → Toast 通知
- [x] 移动端响应式 — 侧边栏抽屉、汉堡菜单、横向滚动、响应式 padding
- [x] Reduced motion 支持 — Toast / PageTransition / 列表动画
- [x] ESLint 颜色纪律规则 — 禁止硬编码 Tailwind 颜色类
- [x] 关键 Bug 修复 — `React.useState` 未导入、`useToast.ts` 扩展名错误

### 待开工（后续 Phase）
- [ ] Phase 5：定时任务自动化（cron/schedule）
- [ ] Phase 6：报告自动生成 + 任务日志监控
- [ ] Phase 7：回测结果前端展示增强（收益曲线、回撤图、策略对比）

## Issues Log

| Date | Issue | Root Cause | Fix |
|------|-------|------------|-----|
| 2026-04-21 | `useToast.ts` ESLint 解析失败 `'>' expected` | 文件含 JSX 但扩展名为 `.ts`，ESLint ts parser 将其当 TS 处理 | 重命名为 `useToast.tsx` |
| 2026-04-21 | `__root.tsx` `React.useState is not a function` | 使用 `React.useState` 但未导入 React（仅导入 hooks） | 改为 `import { useState }` + `useState(false)` |
| 2026-04-21 | ESLint 颜色纪律违规 16 处 | 新增 `no-restricted-syntax` 规则后，历史代码中的 `text-white` / `bg-black/50` / `bg-white/20` 被检测 | 全部替换为语义 Token：`text-[var(--text-inverse)]`、`bg-[var(--overlay-backdrop)]`、`bg-[var(--highlight-on-accent)]`、`text-destructive-foreground` |
| 2026-04-19 | SQLite `ProgrammingError: SQLite objects created in a thread can only be used in that same thread` | FastAPI 同步依赖 `get_db` 在线程池执行 → 创建连接；async 路由在事件循环线程执行 → 使用连接；SQLite 默认 `check_same_thread=True` 触发跨线程检查 | (1) `storage.py` `_init_db`: `sqlite3.connect(..., check_same_thread=False)`；(2) `deps.py` `get_db`: `return` → `yield` + `store.close()` 确保请求级连接释放 |
| 2026-04-19 | 前端 `Cannot read properties of undefined (reading 'toFixed')` | 后端 SQLite 返回 NULL 的数值字段（nav/maShort/maLong/weightPct 等），前端 TypeScript 类型声明为非可选 `number`，组件直接调用 `.toFixed()` 触发 crash | 双管齐下：(1) 更新类型定义为 `number \| null`（useScreening.ts / useFundDetail.ts）；(2) 所有组件加 `?.toFixed() ?? '—'` 防御（ScreeningResultItem/FundDetailHeader/HoldingsList/ChartContainer 等） |

## Notes

- 现有前端在 `web/` 目录，技术栈 Vite + React 19 + Tailwind v4 + shadcn/ui + TanStack Router
- 现有后端在 `src/fund_screener/`，技术栈 Python 3.11 + uv + SQLite + tushare/akshare/yfinance
- 前端现有路由：/（仪表盘）, /funds（基金列表）, /screening（筛选结果）, /chat（AI 分析）, /backtest（策略回测）, /funds/$code（基金详情）
- Phase 2 全部完成，当前分支 `feat/ui-components`，5 个 branch 已逐个 review/merge
- Phase 3 全部完成，回测引擎已可运行
- Phase 4 全部完成，前端视觉体系统一、暗色模式、动画体系、移动端适配就绪
- 关键修复已入版本库：
  - commit `43e1d32`：前端组件 null/undefined 防御 — 所有 `.toFixed()` 调用加保护
  - commit `be873f0`：Branch 4+5 — 基金详情页 + 全页面 mock→真数据迁移
- 关注点分离：页面零样式，组件样式自包含，Token 集中管理
- Phase 3 设计已冻结：`.planning/BACKTEST_DESIGN.md` — 因子/策略/回测三层解耦，vectorbt v1 集成，5 个关键设计决策已记录
- 回测架构三条原则：`.planning/ARCHITECTURE.md` — 因子策略解耦 / 信号是唯一契约 / 回测层只做一件事
