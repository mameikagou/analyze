# Milestone v1.0 — Project Summary

**Generated:** 2026-04-24
**Purpose:** Team onboarding and project review

---

## 1. Project Overview

Fund Screener 是一个覆盖 A股/美股/港股的基金与 ETF 趋势筛选系统。后端用 Python 抓取全市场数据，通过 MA 均线筛选右侧趋势标的，结合三因子量化打分引擎生成结构化报告。前端基于 Vite + React 19 + TV Charts 提供可视化仪表盘。

**目标用户：** 需要系统化趋势筛选能力的个人投资者和量化研究者。

**核心价值：** 用户能在 1 分钟内获取全市场符合趋势条件的基金/ETF 列表，并看到每只标的的量化评分、持仓结构、申购状态和可视化走势。

**Milestone 状态：** v1.0 进行中 — 5 个 Phase 已交付（Phase 0~4），Phase 5（定时任务自动化）为 NEXT，Phase 6（回测展示增强）为 PENDING。

---

## 2. Architecture & Technical Decisions

- **决策：** 后端数据湖使用 SQLite
  - **Why：** 单机项目，不需要分布式数据库
  - **Phase：** PROJECT.md 基线决策

- **决策：** A股双数据源架构 — akshare primary + tushare 补充净值历史
  - **Why：** akshare 字段丰富（申购限额、持仓），tushare SLA 稳定（净值历史）
  - **Phase：** PROJECT.md 基线决策

- **决策：** 前端关注点分离架构（组件粒度样式自包含）
  - **Why：** 样式与逻辑解耦，页面零样式，后续设计考古只改组件
  - **Phase：** Phase 2

- **决策：** API hooks 层统一做 snake_case → camelCase 映射
  - **Why：** 后端保持 Pythonic，前端用 camelCase，边界在 hook 层
  - **Phase：** Phase 2

- **决策：** Phase 3 回测引擎引入 vectorbt v1（而非手写）
  - **Why：** `Portfolio.from_orders(size_type='targetpercent')` 用 Numba 在 C 级别处理资金管理/再平衡/订单生成，消灭手算资金分配最易出错的环节
  - **Phase：** Phase 3 (03-02)

- **决策：** nav_panel NaN 处理策略 — ffill + 上市后才开始算
  - **Why：** 保持宽表格式（因子层可矩阵运算），每只基金上市前用 NaN（不参与），上市后缺失用 ffill，回测引擎遇到 NaN 跳过
  - **Phase：** Phase 3 (03-CONTEXT)

- **决策：** Phase 3 采用"新增因子层 + 兼容层"策略
  - **Why：** 前端 API 已稳定，不改现有 `ScreenResult`/`ScoredFund` 返回格式。回测走新 `factors/` 包，现有 CLI/API 不受影响
  - **Phase：** Phase 3 (03-CONTEXT)

- **决策：** 前端 Token 体系保留 Stone 品牌色，shadcn HSL Token 桥接到 Stone 调色板
  - **Why：** 页面已有大量代码使用 `--bg-canvas` 等 Semantic Token，改动成本更低
  - **Phase：** Phase 4 (04-CONTEXT)

- **决策：** 回测页用 LightweightChart（交互图表），其他简单图表保留 Canvas
  - **Why：** 回测页需要交互（tooltip、缩放、crosshair），LightweightChart 原生支持；其他页面图表简单，Canvas 够用
  - **Phase：** Phase 4 (04-CONTEXT)

- **决策：** 前端所有 API 错误统一走 Toast，不再全页阻塞
  - **Why：** 用户体验决策：网络抖动不应阻断页面其他功能
  - **Phase：** Phase 4 (04-03)

- **决策：** ESLint 强制颜色纪律 — 禁止所有硬编码 Tailwind 颜色类
  - **Why：** 维护设计系统一致性，所有颜色必须走语义 Token
  - **Phase：** Phase 4 (04-03)

---

## 3. Phases Delivered

| Phase | Name | Status | One-Liner |
|-------|------|--------|-----------|
| 0 | Claude 设计系统 | ✅ 初版已交付 | Token 三层体系 + 6 原子组件 + 3 Hook + framer-motion |
| 1 | 后端 API 层 | ✅ COMPLETE | 6 个 endpoint 全部注册并通过验证，CORS 已配置 |
| 2 | 前端仪表盘 | ✅ COMPLETE | 5 个 branch 全部完成，所有页面已对接真实 API |
| 3 | 回测引擎 | ✅ COMPLETE | 4 个 plan 全部完成（因子层 + 回测引擎 + API 层 + 前端页），58/58 测试通过 |
| 4 | UI 翻新 (UI Renovation) | ✅ COMPLETE | 3 个 plan 全部完成：Token 修复/暗色模式/动画体系 + 组件统一/回测页翻新 + 全局体验/移动端适配 |
| 5 | 定时任务 | ⏳ PENDING | 每日自动跑筛选，自动生成报告 |
| 6 | 回测展示增强 | ⏳ PENDING | 前端展示回测结果和自动化任务状态 |

---

## 4. Requirements Coverage

### Design System (Claude UI)
- ✅ DSGN-01: Token 三层体系 — Primitive → Semantic → Component，CSS 变量驱动
- ✅ DSGN-02: Tailwind 配置零硬编码 — 所有 colors/fontFamily/borderRadius 指向 CSS 变量
- ✅ DSGN-03: 原子组件封装 — Surface, Prose, AutoTextarea
- ✅ DSGN-04: Composer 组件 — CenteredComposer / DockedComposer
- ✅ DSGN-05: 按钮原语 — IconButton / TextButton
- ✅ DSGN-06: 交互 Hook — useComposerState, useArtifactPanel, useStreamingMessage
- ⚠️ DSGN-07: Skill 体系 — `.claude/skills/claude-ui-system/` 尚未编写，等主人完成 design-audit
- ✅ DSGN-08: 工程护栏 — ESLint 禁止裸 HEX/rgb，禁止硬编码 Tailwind 颜色类

### Frontend Dashboard
- ✅ FRONT-01: 首页展示全市场筛选结果总览
- ✅ FRONT-02: 筛选结果列表页（表格展示，支持排序）
- ✅ FRONT-03: 单只基金详情页（净值走势图、MA 均线、基本信息、持仓结构）
- ✅ FRONT-04: TV Charts 集成（K 线图 + MA 均线叠加）
- ✅ FRONT-05: 前端路由体系（/ → 首页, /funds → 列表, /funds/:code → 详情, /screening → 筛选, /backtest → 回测）
- ✅ FRONT-06: 前端与后端 API 对接（REST API，数据序列化）

### Data Quality
- ✅ DATA-01: adj_nav 历史回填脚本（断点续传）
- ✅ DATA-02: 回填进度监控（backfill_log 表记录进度）
- ✅ DATA-03: 回填断点续传（中断后从断点继续）

### Backtest Engine
- ✅ BACK-01: 回测引擎框架（策略信号 → 模拟持仓 → 收益计算）
- ✅ BACK-02: MA 筛选策略回测（胜率、平均盈亏、最大回撤、夏普比率）
- ✅ BACK-03: 回测结果可视化（收益曲线、回撤图）
- ✅ BACK-04: 回测报告生成（Markdown 格式）

### Automation
- ❌ AUTO-01: 定时任务编排 — Phase 5 待开工
- ❌ AUTO-02: 报告自动生成和持久化 — Phase 5 待开工
- ❌ AUTO-03: 任务日志和监控 — Phase 5 待开工

---

## 5. Key Decisions Log

| Date | Decision | Phase | Rationale |
|------|----------|-------|-----------|
| 2026-04-19 | 项目扩展为 "Claude 风格前端 + 后端 API + 回测 + 自动化" | 基线 | 主人要求复刻 claude.ai/new 样式 |
| 2026-04-19 | 前端关注点分离架构 | Phase 2 | 组件粒度样式自包含，页面零样式 |
| 2026-04-19 | Phase 2 拆分为 5 个独立 branch | Phase 2 | 主人要求逐个 review/merge |
| 2026-04-19 | API hooks 层统一做 snake_case → camelCase 映射 | Phase 2 | 后端保持 Pythonic，前端用 camelCase |
| 2026-04-20 | Phase 3 回测引擎引入 vectorbt v1 | Phase 3 | Numba C 级别资金管理，消灭手算错误 |
| 2026-04-20 | nav_panel NaN 处理：ffill + 上市后才开始算 | Phase 3 | 保持宽表格式，上市前 NaN 不参与 |
| 2026-04-20 | 新增因子层 + 兼容层策略 | Phase 3 | 不改现有 CLI/API，回测走新 factors/ 包 |
| 2026-04-20 | 前端回测页使用 Canvas 绘制净值曲线 | Phase 3 | 保持 bundle 体积可控，Phase 3 够用 |
| 2026-04-21 | Phase 4 保留 Stone 品牌色，shadcn HSL 桥接 Stone | Phase 4 | 已有 Semantic Token 代码改动成本更低 |
| 2026-04-21 | 回测页用 LightweightChart 替换 Canvas | Phase 4 | 需要交互（tooltip、缩放、crosshair） |
| 2026-04-21 | 引入 Framer Motion 动画体系 | Phase 4 | 页面过渡 + hover 动画 + loading 统一 |
| 2026-04-21 | 前端所有 API 错误统一走 Toast | Phase 4 | 网络抖动不应阻断页面其他功能 |
| 2026-04-21 | ESLint 强制颜色纪律规则 | Phase 4 | 维护设计系统一致性 |
| 2026-04-21 | 新增 `--highlight-on-accent` 语义 Token | Phase 4 | stepper 激活态圆圈需要 accent 背景上的半透明高亮 |

---

## 6. Tech Debt & Deferred Items

### 来自 VERIFICATION.md / 已知问题
- adj_nav 历史回填已完成，但全量回填进度需主人确认是否 100% 完成
- MaxDrawdownFactor O(n²) 朴素实现是已知性能瓶颈，1000基金×2000天面板测试后需优化（numba 或预计算）
- vectorbt 0.26.0 锁定 numpy 1.26.4 + plotly 5.18.0，未来需升级 vectorbt 以支持 numpy 2.x

### 来自 RETROSPECTIVE / Issues Log
- Phase 0 设计考古：主人需完成 `docs/design-audit-result.md`（DevTools 扒 claude.ai/new 样式）
- DSGN-07 Skill 体系尚未编写（`.claude/skills/claude-ui-system/`）
- 暗色模式下 `--highlight-on-accent: rgba(255,255,255,0.2)` 在橙色按钮上对比度需主人视觉确认
- 移动端 drawer 的 swipe-to-close（可选增强）

### 来自 CONTEXT.md <deferred> 段落
- **kind='weight' 因子** — 导入公开持仓做跟投回测（v1.1）
- **Walk-Forward 参数优化** — 多参数网格搜索（Phase 5/6）
- **多策略对比** — 同时跑多个策略，对比收益曲线（Phase 5/6）
- **参数扫描** — vectorbt 的 `.params` 功能（Phase 5/6）
- **前端 TV Charts 多 series** — 策略曲线 + 基准曲线叠加（v1.1）
- **策略对比功能** — 多策略同时回测对比（v1.1）
- **回测报告导出 PDF** — v1.1
- **暗色模式下的图表配色优化** — LightweightChart 主题适配

---

## 7. Getting Started

- **Run the project:**
  - 后端：`uv run python -m fund_screener.api.main`（FastAPI 服务）
  - 前端：`cd web && bun dev`（Vite 开发服务器）
  - CLI：`uv run fund-screener --help`

- **Key directories:**
  - `src/fund_screener/` — Python 后端（API、回测引擎、因子层、数据湖）
  - `web/src/` — React 前端（页面、组件、hooks、Token 体系）
  - `tests/` — 单元测试（factor 30 个 + backtest 24 个 + 原有 76 个）
  - `.planning/` — GSD 规划文档（ROADMAP、STATE、Phase 计划与总结）

- **Tests:**
  - 后端：`uv run pytest`（全部 130+ 测试）
  - 前端：`bunx tsc --noEmit`（TypeScript 编译检查）+ `bun run lint`（ESLint）

- **Where to look first:**
  - 后端入口：`src/fund_screener/api/main.py`（FastAPI 应用注册所有路由）
  - 前端入口：`web/src/routes/__root.tsx`（根布局 + 导航 + 主题切换）
  - 回测引擎：`src/fund_screener/backtest/engine.py`
  - 因子层：`src/fund_screener/factors/base.py`（抽象契约）
  - 数据湖：`src/fund_screener/storage.py`

---

## Stats

- **Timeline:** 2026-04-19 → 2026-04-21 (3 days)
- **Phases:** 5 / 7 complete (71%)
- **Commits:** 43
- **Files changed:** 105 (+19,868 / -937 lines)
- **Contributors:** mrlonely
