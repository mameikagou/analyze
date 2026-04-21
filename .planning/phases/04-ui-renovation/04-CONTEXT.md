# Phase 4: 前端设计升级（UI Renovation）— Context

**Gathered:** 2026-04-21
**Status:** Ready for planning
**Source:** User directive + capabilities.md analysis

---

<domain>
## Phase Boundary

本 Phase 聚焦前端视觉体验升级，不涉及后端逻辑修改。

**交付物：**
1. 统一的 Token 体系（消除 shadcn HSL 与 Stone hex 冲突）
2. 暗色模式切换机制（含持久化）
3. Framer Motion 动画体系（页面过渡 + hover 过渡 + loading 统一）
4. 回测页全面翻新（LightweightChart 净值曲线 + 交互式配置向导）
5. 全局组件层统一（消除硬编码颜色）
6. Error Boundary + Toast + 移动端适配

**范围外：**
- 后端 API 修改
- 数据库 schema 变更
- 新增业务功能（如策略对比、参数优化）
- 新的筛选算法

</domain>

<decisions>
## Implementation Decisions

### Token 体系
- **决策：** 保留 Stone 品牌色（暖灰基调），让 shadcn HSL Token 桥接到 Stone 调色板
- **理由：** 页面已有大量代码使用 `--bg-canvas` 等 Semantic Token，改动成本更低
- **实现：** `index.css` 中 shadcn 的 `--background` / `--card` / `--foreground` 等映射到 Stone HSL 值

### 暗色模式
- **决策：** 在 `__root.tsx` header 加 sun/moon toggle
- **持久化：** `localStorage` + `prefers-color-scheme` 初始化
- **实现：** `document.documentElement.classList.toggle('dark')`

### 图表方案
- **决策 C（已锁定）：** 回测页用 LightweightChart（已有组件），其他简单图表保留 Canvas
- **理由：** 回测页需要交互（tooltip、缩放、crosshair），LightweightChart 原生支持；其他页面图表简单，Canvas 够用

### 动画库
- **决策：** 引入 Framer Motion
- **用途：** 页面切换过渡（`<Outlet>` 包裹）、hover 状态动画、loading 骨架屏

### 翻新顺序
- **决策：** 从回测页开始（最不满意）→ 筛选页 → 基金详情 → 基金列表 → 首页 → 聊天页
- **理由：** 回测页改动最大、最粗糙，先解决最痛点的

### 组件规范
- **Surface 为容器唯一入口：** 禁止裸写 `<div className="bg-white">`
- **颜色纪律：** 禁止 `bg-white` / `bg-black` / `bg-gray-*` / `#FFF` / `rgb(...)`
- **圆角：** 大卡片 `rounded-xl` 或 `rounded-2xl`，按钮/badge `rounded-full` 或 `rounded-md`
- **Hover：** 必须带 `transition-colors duration-200 ease-out`

### 响应式
- **移动端：** Sidebar 变 hamburger / bottom nav，表格横向滚动，页面 padding 响应式

### Accessibility
- **reduced-motion：** 尊重 `prefers-reduced-motion: reduce`

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 设计系统
- `web/src/styles/tokens.primitive.css` — Primitive Token（Stone 调色板）
- `web/src/styles/tokens.semantic.css` — Semantic Token（暗色模式映射）
- `web/src/styles/tokens.component.css` — Component Token
- `web/src/index.css` — Tailwind v4 主题配置 + shadcn HSL Token
- `web/src/components/design-system/Surface.tsx` — 基础容器组件

### 现有页面（翻新目标）
- `web/src/routes/backtest/index.tsx` — 回测页（最优先翻新）
- `web/src/routes/__root.tsx` — 根布局（加暗色 toggle + PageTransition）
- `web/src/routes/index.tsx` — 首页
- `web/src/routes/funds/index.tsx` — 基金列表
- `web/src/routes/funds/$code.tsx` — 基金详情
- `web/src/routes/screening/index.tsx` — 筛选页
- `web/src/routes/chat/index.tsx` — 聊天页

### 组件
- `web/src/components/views/StatsCard.tsx`
- `web/src/components/views/ScreeningResultItem.tsx`
- `web/src/components/views/FundTable.tsx`
- `web/src/components/views/FundDetailHeader.tsx`
- `web/src/components/chart/LightweightChart.tsx` — 已有图表组件
- `web/src/components/ui/*.tsx` — shadcn 组件

### Hooks
- `web/src/hooks/api/useBacktest.ts` — 回测 API hook

### 项目规范
- `CLAUDE.md` — 前端约束（bun only，英文开发/中文文档）
- `.planning/REQUIREMENTS.md` — DSGN-01~08, FRONT-01~06, BACK-03

</canonical_refs>

<specifics>
## Specific Ideas

### Wave 1: Token 修复 + 暗色模式
- 统一 shadcn HSL（冷灰调）和 Stone hex（暖灰调）的暗色模式值
- 新增 `web/src/hooks/useTheme.ts` — 管理 dark/light + localStorage
- `__root.tsx` header 右侧加 theme toggle 按钮

### Wave 2: 动画体系
- 新增 `PageTransition.tsx` — Framer Motion 包裹 `<Outlet>`
- 统一所有 hover 过渡
- 统一 loading 状态（spinner + skeleton）

### Wave 3: 组件层统一
- 全局搜索 `bg-white` / `bg-gray` / `#FFF` / `rgb(` 并替换
- 确保所有卡片用 `<Surface>` 或 shadcn `<Card>`
- shadcn Button/Card/Input/Badge 暗色模式验证

### Wave 4: 回测页翻新（核心）
- 净值曲线：Canvas → LightweightChart
- 配置表单：4列网格 → 交互式 stepper/wizard
- StatsCard：加 sparkline 迷你图
- 调仓历史表：增强交互（展开动画、排序）

### Wave 5: 全局体验
- Error Boundary + 友好错误页面
- Toast 通知统一（API 错误、操作成功）
- 移动端 sidebar 适配
- reduced-motion 支持

</specifics>

<deferred>
## Deferred Ideas

- 策略对比功能（多策略同时回测对比）— v1.1
- 参数优化（网格搜索最佳参数组合）— v1.1
- 回测报告导出 PDF — v1.1
- 暗色模式下的图表配色优化（LightweightChart 主题）— 可在 Wave 4 中顺带处理

</deferred>

---

*Phase: 04-ui-renovation*
*Context gathered: 2026-04-21 via User Directive*
