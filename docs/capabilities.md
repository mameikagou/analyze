# Fund Screener v1.0 — 功能全景图

> 生成时间: 2026-04-20 | 对应代码版本: `main` branch (Phase 3 完成)

---

## 一、项目定位

**一句话**: 全市场基金/ETF 趋势筛选器 — 用 MA 均线多头排列做"右侧交易"信号过滤，叠加三因子量化打分，辅助投资决策。

**核心价值**: 用户能在 1 分钟内获取全市场符合趋势条件的基金/ETF 列表。

---

## 二、后端能力 (Python)

### 2.1 REST API

| Endpoint | 方法 | 功能 | 前端调用者 |
|----------|------|------|-----------|
| `/health` | GET | 健康检查 | — |
| `/api/funds` | GET | 基金列表（分页/市场筛选） | `useFunds` |
| `/api/funds/{code}` | GET | 基金详情（基本信息+持仓+净值） | `useFundDetail` |
| `/api/screening` | GET | MA 筛选结果 | `useScreening` |
| `/api/chart/{code}` | GET | 净值历史时序 | `useChartData` |
| `/api/stats` | GET | 仪表盘统计 | `useStats` |
| `/api/backtest/run` | POST | 策略回测（因子+配置→绩效） | `useBacktest` |

响应统一包装: `{success, data, error}`。

### 2.2 CLI 工具

| 子命令 | 功能 |
|--------|------|
| *(默认)* | MA 筛选 → Markdown 报告 |
| `score` | 三因子 Z-Score 排行榜 |
| `backtest` | 策略回测（等权/score 加权） |
| `scan-momentum` | 横截面动量扫描 |
| `detect-drift` | 风格漂移检测 |
| `correlation` | 底层持仓相关性矩阵 |
| `bulk-fetch` | 异步批量抓取 |

### 2.3 数据与计算层

| 模块 | 职责 |
|------|------|
| `factors/` | 因子层 — 5 个因子（MA 交叉/动量/夏普/回撤/三因子组合），面板级矩阵运算 |
| `backtest/` | 回测引擎 — vectorbt v1 `Portfolio.from_orders(size_type='targetpercent')` |
| `storage.py` | SQLite 数据湖 — funds/nav_records/holdings/screening_results |
| `fetchers/` | 数据抓取 — CN(tushare+akshare) / US(yfinance) / HK(yfinance) |

---

## 三、前端现状 (React/TypeScript)

### 3.1 页面全景

| 路由 | 页面 | 数据来源 | 核心功能 |
|------|------|----------|----------|
| `/` | **仪表盘** | `useStats` + `useScreening(limit=10)` | 统计卡片 + 最新筛选结果预览 |
| `/funds` | **基金列表** | `useFunds` | 分页表格，市场筛选 |
| `/funds/$code` | **基金详情** | `useFundDetail` + `useChartData` | 信息网格 + TV Charts 净值图 + 持仓列表 |
| `/screening` | **筛选结果** | `useScreening` | 筛选结果列表（代码+MA指标+徽章） |
| `/backtest` | **策略回测** | `useBacktest` (POST) | 配置面板 + Canvas 净值曲线 + 绩效卡片 + 调仓历史 |
| `/chat` | AI 分析 | mock | 占位页 |

### 3.2 设计系统现状

#### Token 体系

```
CSS 变量层（globals.css）
├── 颜色: --text-primary, --text-muted, --text-inverse
├── 背景: --bg-base, --bg-surface, --bg-elevated, --bg-hover
├── 边框: --border-subtle, --border-active
├── 强调: --accent-primary, --accent-secondary
└── 状态: --status-success, --status-error, --status-warning
```

**问题**: Token 命名偏"功能语义"（text-primary），缺少"用途语义"（如 heading/label/caption）。颜色只有一套，暗色模式未接入。

#### Animation Token

- `tokens.animation.ts` — presence variants（enter/exit/visible）
- `tokens.transition.ts` — 预设过渡（fast=150ms, normal=300ms, slow=500ms）
- framer-motion 驱动所有组件动画

**问题**: 动画 token 只覆盖了 presence（挂载/卸载），缺少 hover/focus/loading 状态动画。没有全局的 `prefers-reduced-motion` 降级。

#### CVA Variants

`lib/variants.ts` 定义了 4 个变体系统：

| Variant | 用途 | 状态 |
|---------|------|------|
| `MarketBadge` | CN/US/HK 标识 | 3 色 + outline |
| `ScoreBadge` | 量化评分等级 | 5 档颜色（优/良/中/差/无） |
| `PurchaseStatusBadge` | 申购状态 | 开放/限额/暂停 |
| `MADiffIndicator` | MA 差值方向 | 箭头+颜色（涨绿跌红） |

**问题**: 只有这 4 个 CVA variant，shadcn/ui 组件（Button/Card/Badge 等）没有统一 variant 系统，样式散落在各个组件里。

### 3.3 业务组件 (`components/views/`)

| 组件 | 职责 | 当前问题 |
|------|------|----------|
| `StatsCard` | 统计卡片（标题+数值+趋势箭头+图标） | 只有 1 种尺寸，缺少 compact/large 变体；趋势颜色硬编码 |
| `ScreeningResultItem` | 筛选结果列表项 | 信息密度过高，移动端未适配 |
| `FundTable` | 基金基础信息表格 | 纯数据展示，缺少排序/过滤交互 |
| `FundDetailHeader` | 基金详情头部 | 信息网格布局固定，响应式 breakpoints 过少 |
| `HoldingsList` | 持仓列表 | 权重用进度条展示，但缺少 tooltip |
| `ChartContainer` | TV Charts 包装 | 仅详情页使用，MA 计算在前端重复（后端已算过） |
| `MarketBadge` / `ScoreBadge` / `PurchaseStatusBadge` / `MADiffIndicator` | 各类徽章 | 尺寸固定，缺少 size variant |

### 3.4 回测页 (`/backtest`) — Phase 3 新增

**配置面板**:
- 8 个参数表单：select × 4 + number × 1 + date × 2 + submit
- 原生 HTML `<input>` / `<select>` + Tailwind utility classes
- 无表单校验库（手动校验 startDate < endDate）

**结果展示**:
- 4 张 `StatsCard`（总收益/年化/回撤/夏普）
- Canvas 绘制净值曲线 + 回撤阴影
- 可展开调仓历史表

**问题**: 配置面板和结果展示在同一页，无步骤引导。Canvas 图表功能极简（只有单线+填充），缺少 zoom/pan、多 series 叠加、tooltip。

### 3.5 图表系统

| 页面 | 实现 | 能力 | 限制 |
|------|------|------|------|
| 基金详情 | TradingView Lightweight Charts | 净值线 + MA20/MA60 叠加、zoom、tooltip | 仅单基金，无对比 |
| 回测结果 | Canvas（手写） | 净值曲线 + 回撤阴影 | 无交互（无 zoom/pan/tooltip）、单 series |

**问题**: 两套图表系统并存，视觉风格不一致（TV Charts 有自己的主题系统，Canvas 用 CSS 变量）。回测页 Canvas 功能太弱，未来多策略对比时需要升级。

### 3.6 状态与数据流

```
TanStack Router (file-based routing)
    │
    ├─ 页面组件（零样式，纯布局）
    │   └─ 业务组件（自包含样式）
    │       └─ Hooks 层（snake_case → camelCase 映射）
    │           └─ api/client.ts（axios-like 封装）
    │               └─ FastAPI Backend
    │
    └─ Zustand (appStore — 只有 sidebarOpen)
```

**问题**:
- Zustand store 几乎是空的（只有 sidebar 开关），全局状态管理未实际使用
- 页面间数据不共享（每次切路由重新请求）
- 没有 optimistic updates / 本地缓存策略

### 3.7 前端技术栈

| 层 | 技术 | 版本 |
|----|------|------|
| 构建 | Vite | 6 |
| 框架 | React | 19 |
| 语言 | TypeScript | 5.6 |
| 样式 | Tailwind CSS | v4 |
| UI 库 | shadcn/ui | — |
| 路由 | TanStack Router | — |
| 数据 | TanStack Query | — |
| 状态 | Zustand | — |
| 图表 | TradingView Lightweight Charts + Canvas | — |
| 动画 | framer-motion | — |
| 包管理 | bun | — |

---

## 四、设计升级待办清单

基于前端现状，以下是设计升级的明确方向：

### 4.1 Token 体系扩充

- [ ] 暗色模式 token（`dark:` 前缀或 CSS `color-scheme`）
- [ ] 字号阶梯（xs/sm/base/lg/xl/2xl/3xl + line-height 配套）
- [ ] 间距阶梯（4px/8px/12px/16px/24px/32px/48px）
- [ ] 圆角阶梯（sm/md/lg/xl/full）
- [ ] shadow 阶梯（subtle/medium/elevated）

### 4.2 动画体系完善

- [ ] hover/focus/loading 状态动画 token
- [ ] `prefers-reduced-motion` 全局降级
- [ ] 页面切换过渡（TanStack Router  outlet 动画）

### 4.3 组件库扩展

- [ ] shadcn/ui 组件统一 theme variant（primary/secondary/ghost/destructive）
- [ ] 表单组件统一（目前混用原生 input 和 shadcn Input）
- [ ] 图表组件统一（TV Charts vs Canvas 风格对齐，或统一用一套库）
- [ ] 数据表格增强（排序、过滤、列选择）
- [ ] 空状态/加载状态/错误状态统一组件

### 4.4 回测页升级

- [ ] 配置向导（步骤引导，而非 8 个字段平铺）
- [ ] 图表库升级（支持 zoom/pan/tooltip/多 series）
- [ ] 策略对比（同时跑多个配置，并排展示结果）
- [ ] 参数敏感性分析（滑动条实时重算）

### 4.5 全局体验

- [ ] 页面切换 loading 状态（骨架屏 vs spinner 统一）
- [ ] 错误边界（目前只有 hook error 的红色提示框）
- [ ] 移动端适配（当前表格和详情页在小屏上体验差）

---

## 五、已完成 Phase

| Phase | 名称 | 状态 |
|-------|------|------|
| **0** | Claude 设计系统 | 初版交付，Token + 6 原子组件 + framer-motion |
| **1** | 后端 API 层 | 7 个 endpoint，CORS，SQLite 依赖注入 |
| **2** | 前端仪表盘 | 5 页面 + 10 业务组件 + 6 API hooks，全部真数据 |
| **3** | 回测引擎 | 因子层 + 回测引擎 + API/CLI + 前端回测页 + adj_nav 回填 |

---

## 六、待完成 Phase

| Phase | 名称 | 内容 |
|-------|------|------|
| **4** | 前端设计升级 | Token 完善 + 暗色模式 + 组件库扩展 + 回测页增强 |
| **5** | 定时任务自动化 | cron/schedule + 报告自动生成 |
| **6** | 回测展示增强 | 多策略对比、Walk-Forward 验证 |

---

## 七、快速启动

```bash
# 后端
uv run uvicorn fund_screener.api.main:app --reload --port 8000

# 前端
cd web && bun dev

# CLI 回测
uv run fund-screener backtest --start-date 2020-01-01 --end-date 2024-12-31

# adj_nav 回填
uv run python -m fund_screener.scripts.backfill_adj_nav
```

浏览器: `http://localhost:9473`
API 文档: `http://localhost:8000/docs`
