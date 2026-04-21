# Roadmap: Fund Screener v1.0

**Milestone:** v1.0 — Claude 风格前端 + 后端 API + 回测 + 自动化
**Created:** 2026-04-19
**Phases:** 5

---

## Phase 0: Claude 设计系统（预留 — 异步等主人设计考古完成）

**Goal:** 复刻 claude.ai/new 的视觉语言和交互范式，建立可复用的 Token + 组件 + Skill 体系。

**Status:** 🕐 WAITING — 等主人完成 `docs/design-audit-result.md`

**Depends on:** 主人用 DevTools 扒 claude.ai/new 样式（见 `docs/design-audit-template.md`）

**Success Criteria:**
1. `docs/design-audit-result.md` 完成（主人做）
2. Token 三层体系落地（Primitive → Semantic → Component）
3. 核心原子组件封装完成（Surface, Prose, AutoTextarea, Composer, IconButton, TextButton）
4. 交互 Hook 固化（useComposerState, useArtifactPanel, useStreamingMessage）
5. `.claude/skills/claude-ui-system/` Skill 编写完成
6. ESLint/Stylelint 规则配置完成（禁止裸 HEX、强制用 Semantic Token）
7. 一个真实页面用 Skill 生成的代码验证通过

**Requirements mapped:** FRONT-01 ~ FRONT-06（视觉基础层）

**UI hint:** yes — 强 UI，必须用 Phase 0 的 Token/组件

---

## Phase 1: 后端 API 层

**Goal:** 把现有 Python CLI 能力包装为 REST API，供前端调用。

**Depends on:** 无（可与 Phase 0 并行）

**Success Criteria:**
1. FastAPI / 轻量框架搭建 API 服务
2. `/api/funds` — 基金列表（分页、筛选、排序）
3. `/api/funds/{code}` — 单只基金详情
4. `/api/screening` — 筛选结果（MA 通过列表 + 评分）
5. `/api/chart/{code}` — 净值历史时序数据（供 TV Charts）
6. `/api/stats` — 仪表盘统计数字
7. CORS 配置，前端可跨域调用
8. API 响应格式统一（JSON，含 error 结构）

**Requirements mapped:** FRONT-06（API 对接前置）

**UI hint:** no — 纯后端

---

## Phase 2: 前端仪表盘（依赖 Phase 0 设计系统）

**Goal:** 用 Phase 0 的设计系统，把 fund-screener 的数据可视化出来。

**Depends on:** Phase 0（设计系统）+ Phase 1（API）

**Success Criteria:**
1. 首页：总览统计卡片（总基金数、今日通过 MA、平均分、数据湖记录数）
2. 基金列表页：表格展示，支持按 MA 差值/打分/申购状态排序
3. 基金详情页：净值走势图（TV Charts + MA 均线叠加）、基本信息卡片、持仓结构
4. 筛选结果页：通过 MA 的基金列表 + Top 10 排名
5. 前端路由体系完整（/ → 首页, /funds → 列表, /funds/:code → 详情, /screening → 筛选）
6. 对接 Phase 1 的 API，替换所有 mock 数据
7. 响应式适配（桌面 + 平板）

**Requirements mapped:** FRONT-01 ~ FRONT-06

**UI hint:** yes — 强 UI，必须用 Phase 0 的 Token/组件

---

## Phase 3: 数据质量 + 回测引擎

**Goal:** 补齐 adj_nav 历史数据，建立回测框架验证 MA 策略有效性。

**Depends on:** Phase 1（API 和数据层已就绪）

**Success Criteria:**
1. adj_nav 历史回填脚本（遍历所有基金，补齐旧数据的 adj_nav NULL）
2. 回填进度监控 + 断点续传
3. 回测引擎框架（策略信号 → 模拟持仓 → 收益计算）
4. MA 筛选策略回测（胜率、平均盈亏、最大回撤、夏普比率）
5. 回测结果可视化（收益曲线、回撤图）
6. 回测报告生成（Markdown）
7. CLI 子命令：`fund-screener backtest --strategy ma --start-date --end-date`

**Requirements mapped:** DATA-01 ~ DATA-03, BACK-01 ~ BACK-04

**UI hint:** no — 纯后端，回测结果未来可在前端 Phase 展示

**Plans:**
- [x] `03-01-PLAN.md` — 因子层 (factors/base.py + technical.py + quant.py + composite.py) + storage.load_nav_panel() + 单元测试
- [x] `03-02-PLAN.md` — 回测引擎核心 (backtest/config.py + engine.py + result.py) + vectorbt 集成 + 单元测试
- [x] `03-03-PLAN.md` — API 层 (api/routes/backtest.py) + CLI 子命令 (cli.py backtest) + adj_nav 回填脚本 (scripts/backfill_adj_nav.py)
- [x] `03-04-PLAN.md` — 前端回测页 (web/src/routes/backtest/index.tsx + useBacktest hook + 导航更新)

**Status:** ✅ COMPLETE — 58/58 tests pass, all 4 waves delivered

---

## Phase 4: 前端设计升级（UI Renovation）

**Goal:** 修复 Token 冲突，统一暗色模式，翻新回测页，提升全局视觉体验。

**Depends on:** Phase 2（前端框架）+ Phase 3（回测页已就绪）

**Key Decisions:**
- 图表方案：回测页用 LightweightChart（交互图表），其他简单图表保留 Canvas
- 动画库：引入 Framer Motion（页面过渡 + 交互动画）
- 翻新顺序：从回测页开始（最不满意）→ 筛选页 → 基金详情 → 基金列表 → 首页 → 聊天页

**Success Criteria:**
1. Token 体系统一：shadcn HSL 和 Stone hex Token 不再打架，暗色模式一键切换
2. 动画体系：页面切换淡入淡出，hover 统一过渡，loading 状态一致
3. 回测页翻新：LightweightChart 净值曲线 + 交互式配置向导 + 增强 StatsCard（sparkline）
4. 组件层统一：消除硬编码颜色（bg-white / bg-gray-*），全部走 Semantic Token
5. 全局体验：Error Boundary、Toast 统一、移动端适配、reduced-motion 支持

**Requirements mapped:** DSGN-01 ~ DSGN-08, FRONT-01 ~ FRONT-06, BACK-03

**UI hint:** yes — 强 UI，核心目标

**Plans:**
- [x] `04-01-PLAN.md` — Wave 1+2：Token 修复 + 暗色模式 + 动画体系 ✅ COMPLETE
- [x] `04-02-PLAN.md` — Wave 3+4：组件层统一 + 回测页翻新 ✅ COMPLETE
- [x] `04-03-PLAN.md` — Wave 5：全局体验优化（Error Boundary + 移动端 + Toast） ✅ COMPLETE

---

## Phase 5: 定时任务 + 自动化

**Goal:** 每日自动跑筛选，自动生成报告。

**Depends on:** Phase 1 + Phase 3（数据完整 + 回测框架就绪）

**Success Criteria:**
1. 定时任务编排（cron / schedule / APScheduler）
2. 每日固定时间自动跑全市场筛选
3. 报告自动生成和持久化（保存到 output/ 目录，带时间戳）
4. 任务日志和监控（运行状态、耗时、异常告警）
5. 可配置调度时间、市场范围、输出目录
6. 失败重试 + 告警（日志记录，可选邮件/飞书通知）

**Requirements mapped:** AUTO-01 ~ AUTO-03

**UI hint:** no — 纯后端自动化

---

## Phase 6: 回测结果前端展示（可选，v1.1 或 v1.0 收尾）

**Goal:** 在前端展示回测结果和自动化任务状态。

**Depends on:** Phase 2（前端框架）+ Phase 3（回测有数据）+ Phase 5（自动化有日志）

**Success Criteria:**
1. 回测结果页：收益曲线、回撤图、关键指标卡片
2. 任务状态页：最近运行记录、成功/失败状态、耗时
3. 定时任务配置 UI（可选，先只做展示）

**Requirements mapped:** BACK-03（可视化）, AUTO-03（监控展示）

**UI hint:** yes

---

## Dependency Graph

```
Phase 0 (设计系统) ─────────────────────────────┐
        │                                        │
        ▼                                        │
Phase 1 (后端 API) ───┬──► Phase 2 (前端仪表盘) ──┘
        │             │
        │             └──► Phase 3 (回测引擎)
        │                      │
        │                      ▼
        │             Phase 4 (UI 设计升级)
        │                      │
        │                      ▼
        │             Phase 5 (定时任务)
        │                      │
        │                      ▼
        │             Phase 6 (回测展示)
        │
        └── 可与 Phase 0 并行推进
```

---

## Execution Strategy

1. **立即开始：** Phase 1（后端 API）+ 主人并行做设计考古
2. **设计考古完成后：** Phase 0（设计系统）→ 然后 Phase 2（前端仪表盘）
3. **Phase 1 完成后：** Phase 3（回测引擎）可与 Phase 0/2 并行
4. **Phase 3 完成后：** Phase 4（UI 设计升级）
5. **Phase 4 完成后：** Phase 5（定时任务）
6. **收尾：** Phase 6（回测展示）

---

## Progress Tracking

| Phase | Status | Plans | Summaries | UAT |
|-------|--------|-------|-----------|-----|
| 0 | ✅ DELIVERED | 1 | 1 | — |
| 1 | ✅ COMPLETE | 1 | 1 | — |
| 2 | ✅ COMPLETE | 0 | 0 | — |
| 3 | ✅ COMPLETE | 4 | 4 | — |
| 4 | ✅ COMPLETE | 3 | 3 | — |
| 5 | 📐 NEXT | 0 | 0 | — |
| 6 | ⏳ PENDING | 0 | 0 | — |

---
*Last updated: 2026-04-21 after Phase 4 execution complete*
