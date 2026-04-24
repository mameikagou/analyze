# Fund Screener v1.0 — 项目审查报告

> 生成时间: 2026-04-24
> 审查范围: 全量代码 + .planning 文档 + 运行态验证
> 用途: 供下游模型评估 Phase 5/6 开发方向

---

## 一、项目概览

**项目名称**: Fund Screener — 全市场基金/ETF 趋势筛选器
**核心目标**: 用户能在 1 分钟内获取全市场符合趋势条件（MA 多头排列）的基金/ETF 列表，并看到每只标的的量化评分、持仓结构、申购状态和可视化走势
**当前状态**: Phase 0~4 已完成（设计系统、后端 API、前端仪表盘、回测引擎、UI 翻新），Phase 5（定时任务自动化）为 NEXT

---

## 二、技术栈总览

### 后端
| 层级 | 技术 | 说明 |
|------|------|------|
| 语言 | Python 3.11 | 完整类型注解 |
| 包管理 | uv | 锁定依赖 |
| Web 框架 | FastAPI | 6 个 REST endpoint |
| 数据存储 | SQLite | 数据湖，6 张表，Schema v3，自动迁移 |
| 数据源 | akshare + tushare + yfinance | A股双数据源，美股 yfinance，港股 |
| 回测引擎 | vectorbt v1 | `Portfolio.from_orders(size_type='targetpercent')` |
| CLI | click | `fund-screener` 命令行入口 |
| 测试 | pytest | 后端 76+ 单元测试全部通过 |
| 配置 | Pydantic + yaml | `config.yaml` + `AppConfig` |

### 前端
| 层级 | 技术 | 说明 |
|------|------|------|
| 构建工具 | Vite | 锁定 |
| 框架 | React 19 | 锁定 |
| 样式 | Tailwind CSS v4 | 唯一 CSS 方案，禁止 CSS-in-JS |
| UI 组件库 | shadcn/ui | 基础组件，上层 Token 覆盖 |
| 路由 | TanStack Router | 文件系统路由 |
| 状态管理 | Zustand（UI）+ TanStack Query（服务端） | 严格分离 |
| 图表 | TradingView Lightweight Charts | 金融图表唯一方案 |
| 动画 | framer-motion | 复杂交互 |
| 包管理 | bun | 锁定 |
| Token 体系 | CSS 变量驱动 | 禁止 HEX/rgb/hsl 字面量 |

---

## 三、已实现模块详解

### 3.1 后端模块

#### 数据抓取层 (`fetchers/`)
- `base.py` — `BaseFetcher` 抽象基类
- `cn_composite.py` — `CompositeCNFetcher`，按方法路由到 akshare/tushare
- `cn_tushare.py` / `cn_fund.py` — A股数据源
- `us_etf.py` / `us_holdings.py` — 美股 ETF 数据
- `hk_etf.py` — 港股 ETF 数据
- `async_fetcher.py` — 异步批量抓取，并发控制 + `ErrorQueue` 失败重试

#### 数据存储层 (`storage.py`)
- SQLite 数据湖，6 张表
- Schema v3，自动迁移
- `load_nav_panel()` 宽表加载方法（date × fund_code，供回测引擎使用）
- `check_same_thread=False` 解决 FastAPI 多线程问题

#### 筛选与打分 (`screener.py` / `scoring.py`)
- MA 均线趋势筛选（MA20 > MA60 多头排列）
- 三因子量化打分引擎（动量 + 夏普 + 最大回撤，Z-Score 标准化 + 加权排名）

#### OLAP 量化中枢 (`analytics.py`)
- 动量扫描
- 风格漂移检测
- 相关性矩阵

#### 因子层 (`factors/`) — Phase 3 新增
- `base.py` — `BaseFactor` + `FactorOutput` 抽象契约
- `technical.py` — `MACrossFactor`（MA 多头排列信号）
- `quant.py` — `MomentumFactor` / `SharpeFactor` / `DrawdownFactor`
- `composite.py` — `CompositeFactor`（Z-Score 标准化 + 加权）

#### 回测引擎 (`backtest/`) — Phase 3 新增
- `config.py` — `BacktestConfig`（frozen dataclass）
- `engine.py` — `BacktestEngine`（vectorbt v1 `from_orders` 集成）
- `result.py` — `BacktestResult`（指标 + 净值曲线 + 回撤 + 序列化）

#### API 层 (`api/`)
- `main.py` — FastAPI 应用入口，CORS 已配置
- `deps.py` — `get_db_conn()` 依赖注入
- `schemas.py` — Pydantic 模型
- 路由:
  - `health.py` — `/health`
  - `funds.py` — `/api/funds`, `/api/funds/{code}`
  - `screening.py` — `/api/screening`
  - `chart.py` — `/api/chart/{code}`
  - `stats.py` — `/api/stats`
  - `backtest.py` — `/api/backtest/run`

#### CLI (`cli.py`)
- `fund-screener` 主命令（全市场筛选）
- 子命令: `scan-momentum`, `detect-drift`, `correlation`, `bulk-fetch`, `api`, `backtest`

#### 其他
- `models.py` — Pydantic 数据模型
- `reporter.py` — Markdown 报告生成
- `risk_metrics.py` — 风险指标计算
- `cache.py` — JSON 文件缓存
- `error_queue.py` — 失败重试队列
- `config.py` — 应用配置
- `scripts/backfill_adj_nav.py` — adj_nav 历史回填（断点续传）

### 3.2 前端模块

#### 设计系统 (`components/design-system/`)
- `Surface.tsx` — 背景容器（canvas/surface/elevated/hover/active/selected 六级）
- `Prose.tsx` — Markdown 正文渲染
- `AutoTextarea.tsx` — 自动撑高输入框
- `IconButton.tsx` / `TextButton.tsx` — 按钮原语
- `PageTransition.tsx` — Framer Motion 页面过渡（`AnimatePresence mode="wait"`）
- `ErrorBoundary.tsx` — 全局错误边界

#### Token 体系 (`styles/`)
- `tokens.primitive.css` — 调色板原始值（Stone 色系 + Orange/Green/Red/Blue）
- `tokens.semantic.css` — 语义映射（背景/文字/边框/强调色/阴影），支持 dark mode
- `tokens.component.css` — 组件级特例
- `tokens.chart.css` — 图表语义 Token（涨跌色/均线色/网格色）
- `tokens.animation.ts` — 动画参数集中管理（duration/easing/transition/stagger/presence）

#### 业务组件 (`components/views/`)
- `StatsCard.tsx` — 统计卡片（支持 trend 指示 + sparkline）
- `FundTable.tsx` — 基金列表表格（响应式横向滚动）
- `FundDetailHeader.tsx` — 基金详情头部
- `HoldingsList.tsx` — 持仓结构展示
- `MarketBadge.tsx` — 市场标识徽章
- `MADiffIndicator.tsx` — MA 差值指示器
- `PurchaseStatusBadge.tsx` — 申购状态徽章
- `ScoreBadge.tsx` — 量化评分徽章
- `ScreeningResultItem.tsx` — 筛选结果项
- `ChartContainer.tsx` — 图表容器

#### 图表组件 (`components/chart/`)
- `LightweightChart.tsx` — TradingView Lightweight Charts 封装（AreaSeries，支持暗色模式自动适配）

#### API Hooks (`hooks/api/`)
- `useFunds.ts` — 基金列表（分页/筛选/排序）
- `useFundDetail.ts` — 单只基金详情
- `useScreening.ts` — 筛选结果
- `useChartData.ts` — 净值历史时序数据
- `useStats.ts` — 仪表盘统计数字
- `useBacktest.ts` — 回测执行（mutation）

#### 全局 Hooks
- `useTheme.ts` — 暗色模式（localStorage 持久化 + class 切换）
- `useToast.tsx` — Toast 通知系统

#### 状态管理
- `stores/appStore.ts` — Zustand，仅 UI 状态（sidebarOpen）

#### 页面路由 (`routes/`)
| 路由 | 页面 | 说明 |
|------|------|------|
| `/` | 仪表盘 | 统计卡片 + 今日筛选 Top 10 |
| `/funds` | 基金列表 | 表格展示，支持排序 |
| `/funds/$code` | 基金详情 | 净值走势图 + 基本信息 + 持仓结构 |
| `/screening` | 筛选结果 | 通过 MA 的基金列表 + 排名 |
| `/backtest` | 策略回测 | 4 步 Stepper 向导 + 净值曲线 + 绩效卡片 + 调仓历史 |
| `/chat` | AI 分析 | 聊天界面（Composer 模式） |

---

## 四、前端设计风格

### 4.1 视觉语言（Claude.ai/new 复刻）
- **色系**: Stone 中性色为主（50~950），Orange 作为唯一强调色
- **背景梯度**: canvas → surface → elevated，三层分明
- **文字梯度**: primary → secondary → muted → faint
- **边框**: 极淡的 hairline（--border-subtle），几乎不可见但提供结构感
- **阴影**: 极少使用，仅 elevated 面板和 dropdown 有微弱阴影
- **圆角**: 卡片 rounded-xl(16px)，输入框 rounded-2xl(24px)

### 4.2 暗色模式
- `.dark` class 切换，localStorage 持久化
- 语义 Token 自动映射，组件无需感知
- shadcn HSL 桥接到 Stone 色系
- 图表（LightweightChart）自动适配暗色主题

### 4.3 动画体系
- **页面过渡**: `slideUp + fade`，`AnimatePresence mode="wait"`
- **列表/网格**: stagger 依次出现（list 0.03s / table 0.015s / grid 0.04s / stats 0.06s）
- **微交互**: hover/active 统一 150ms ease-out
- **布局变化**: 300ms ease-in-out（Composer 位态切换）
- **弹簧效果**: 按钮、chip、提示
- **Reduced motion**: 全链路支持 `prefers-reduced-motion`

### 4.4 组件规范
- **页面零样式**: 所有样式在组件层自包含，页面只负责布局结构
- **Surface 替代裸 div**: 禁止 `bg-white` / `bg-gray-*`，全部走语义 Token
- **ESLint 颜色纪律**: `no-restricted-syntax` 禁止硬编码 Tailwind 颜色类
- **关注点分离**: 功能与样式严格解耦

### 4.5 交互模式
- **导航**: 左侧 Sidebar（桌面可折叠，移动端抽屉）
- **回测配置**: 4 步 Stepper 向导（策略选择 → 持仓配置 → 费用与周期 → 确认运行）
- **错误处理**: API 错误统一走 Toast 通知，不阻塞页面
- **加载状态**: Skeleton 骨架屏 + Loader 旋转图标
- **数据展示**: StatsCard（指标卡片）+ 表格（可展开行）+ 图表（交互式缩放/平移）

---

## 五、架构设计原则

### 5.1 回测引擎三条原则（ARCHITECTURE.md）
1. **因子和策略解耦**: 因子负责打分/信号，策略负责交易规则，回测层只做收益计算
2. **信号是唯一契约**: 所有因子必须产出 `(date × fund_code)` 的 DataFrame
3. **回测层只做一件事**: signal_df × nav_df → 绩效指标，不做因子计算/数据清洗/报告生成

### 5.2 数据流向
```
数据源(akshare/tushare/yfinance) → 清洗(storage.py) → 因子(factors/) → 信号(signal_df)
                                                                    ↓
前端 ← API(main.py) ← 回测结果(BacktestResult) ← 回测层(backtest/engine.py) ← 策略层(config.py)
```

### 5.3 前端数据流
```
页面(routes/) → API Hooks(hooks/api/) → api/client.ts → 后端 REST API
     ↓
Zustand(appStore.ts) — 仅 UI 状态
```

---

## 六、关键决策记录

| 日期 | 决策 | 影响 |
|------|------|------|
| 2026-04-21 | 新增 `--highlight-on-accent` 语义 Token | stepper 激活态圆圈需要 accent 背景上的半透明高亮 |
| 2026-04-21 | 前端 API 错误统一走 Toast，不再全页阻塞 | 网络抖动不阻断页面其他功能 |
| 2026-04-21 | ESLint 强制颜色纪律规则 | 维护设计系统一致性 |
| 2026-04-20 | 回测引擎引入 vectorbt v1 | `Portfolio.from_orders` 用 Numba 处理资金管理，消灭手算错误 |
| 2026-04-20 | nav_panel NaN 处理: ffill + 上市后才开始算 | 保持宽表格式，每只基金上市前 NaN 不参与 |
| 2026-04-20 | Phase 3 采用"新增因子层 + 兼容层"策略 | 前端 API 格式不变，回测走新 factors/ 包 |
| 2026-04-19 | 前端关注点分离架构 | 页面零样式，组件样式自包含，后续设计考古只改组件 |
| 2026-04-19 | API hooks 层统一做 snake_case → camelCase 映射 | 后端保持 Pythonic，前端用 camelCase |

---

## 七、已知问题与债务

### 7.1 技术债务
| 问题 | 严重程度 | 说明 |
|------|----------|------|
| adj_nav 回填 | 中 | Schema v2 迁移后旧数据 adj_nav 为 NULL，回填脚本已存在但可能未跑完 |
| 设计考古未完成 | 低 | Phase 0 初版已交付，等主人完成 `docs/design-audit-result.md` 后对照微调 |
| Skill 体系未编写 | 低 | `.claude/skills/claude-ui-system/` 未编写 |
| 工程护栏未配置 | 低 | ESLint 颜色纪律已配，但 Stylelint 未配置 |
| 回测页图表仅 Area | 低 | 只有净值曲线，无回撤图、月度收益热力图 |

### 7.2 已修复的关键 Bug
- `useToast.ts` 扩展名错误（含 JSX 但为 `.ts`）→ 重命名为 `.tsx`
- `__root.tsx` `React.useState` 未导入 → 改为 `import { useState }`
- SQLite 跨线程错误 → `check_same_thread=False` + `yield` 连接释放
- 前端 `.toFixed()` crash → 所有数值字段加 `?.toFixed() ?? '—'` 防御

---

## 八、测试覆盖

- 后端: 11 个测试文件，76+ 测试用例全部通过
  - `test_screener.py`, `test_scoring.py`, `test_storage.py`, `test_analytics.py`
  - `test_factors.py`, `test_backtest.py`, `test_reporter.py`
  - `test_async_fetcher.py`, `test_error_queue.py`, `test_purchase_filter.py`
- 前端: 无显式测试文件（项目中未配置 vitest/jest）

---

## 九、下一步开发方向评估（Phase 5/6）

### Phase 5: 定时任务 + 自动化
**目标**: 每日自动跑筛选，自动生成报告
**依赖**: Phase 1（API）+ Phase 3（回测框架）
**核心工作**:
1. 定时任务编排（APScheduler / schedule / cron）
2. 每日固定时间自动跑全市场筛选
3. 报告自动生成和持久化（`output/` 目录，带时间戳）
4. 任务日志和监控（运行状态、耗时、异常告警）
5. 失败重试 + 告警（日志记录，可选邮件/飞书通知）
**技术选型建议**: APScheduler（Python 生态最成熟，支持 cron 表达式、持久化作业存储、并发控制）
**风险**: 单机部署，APScheduler 的持久化需要 SQLite/Redis 作为作业存储

### Phase 6: 回测结果前端展示增强
**目标**: 在前端展示回测结果和自动化任务状态
**依赖**: Phase 2（前端框架）+ Phase 3（回测有数据）+ Phase 5（自动化有日志）
**核心工作**:
1. 回测结果页增强: 收益曲线 + 回撤图 + 月度收益热力图
2. 任务状态页: 最近运行记录、成功/失败状态、耗时
3. 定时任务配置 UI（可选，先只做展示）
**技术选型建议**:
- 回撤图: LightweightChart LineSeries（已集成）
- 热力图: 需要新图表库（如 `react-heatmap-grid` 或自研 Canvas）
- 任务状态: 新增 API endpoint `GET /api/tasks/recent`

### 可选方向（v1.1）
- 数据清理/归档策略（DATM-01/02）
- 组合分析（多基金持仓去重，行业暴露计算）
- 择时信号增强（结合成交量、波动率等多因子）
- 筛选结果推送（邮件/飞书/钉钉）

---

## 十、给下游模型的关键上下文

1. **前端是 Claude 风格**: 不是 Material Design，不是 Ant Design，是 claude.ai/new 的极简、低饱和度、大留白风格。任何新增页面必须遵循 Token 三层体系。
2. **状态管理已严格分离**: Zustand 只放 UI 状态，服务器数据全走 TanStack Query。不要引入 Redux / Context 做服务端状态。
3. **回测引擎基于 vectorbt**: 不要手写回测逻辑，factor → signal_df → vectorbt 的链路已经跑通。
4. **暗色模式是 first-class**: 所有新增组件必须同时支持 light/dark，测试时两个模式都要看。
5. **API 错误走 Toast**: 不要全页阻塞，网络抖动时不应该让用户什么都点不了。
6. **uv / bun 锁定**: 后端用 uv，前端用 bun，不要引入 pip / npm / yarn / pnpm。
7. **关注点分离**: 页面零样式，组件样式自包含。新增页面时，样式工作在组件层完成。
