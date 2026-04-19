# Fund Screener — 全市场基金/ETF 趋势筛选器

## What This Is

一个覆盖 A股/美股/港股的基金与 ETF 趋势筛选系统。后端用 Python 抓取全市场数据，通过 MA 均线筛选右侧趋势标的，结合三因子量化打分引擎生成结构化报告。前端基于 Vite + React 19 + TV Charts 提供可视化仪表盘。

目标用户：需要系统化趋势筛选能力的个人投资者和量化研究者。

## Core Value

用户能在 1 分钟内获取全市场符合趋势条件的基金/ETF 列表，并看到每只标的的量化评分、持仓结构、申购状态和可视化走势。

## Requirements

### Validated

- ✓ 多市场数据抓取（A股公募基金 via tushare/akshare，美股 ETF via yfinance，港股 ETF） — 现有
- ✓ MA 均线趋势筛选（MA20 > MA60 右侧判定） — 现有
- ✓ SQLite 数据湖（6 张表，Schema v3，自动迁移） — 现有
- ✓ 量化打分引擎（三因子 Z-Score 标准化 + 加权排名） — 现有
- ✓ OLAP 量化中枢（动量扫描、风格漂移检测、相关性矩阵） — 现有
- ✓ 申购限额标注与过滤（A 股按申购状态分组展示） — 现有
- ✓ 异步批量抓取（并发控制 + ErrorQueue 失败重试） — 现有
- ✓ Markdown 报告生成（结构化输出供 LLM 分析） — 现有
- ✓ CLI 命令行入口（全市场筛选 + 4 个 OLAP 子命令） — 现有
- ✓ 前端骨架（Vite + React 19 + shadcn/ui + TanStack Router + TV Charts） — 现有
- ✓ CompositeCNFetcher 多数据源中间层（按方法路由到 tushare/akshare） — 现有
- ✓ 76 个单元测试全部通过 — 现有

### Active

#### 前端设计系统（Phase 0 — 阻塞项，等主人设计考古）

- [ ] Token 三层体系（Primitive → Semantic → Component），CSS 变量驱动，Tailwind 配置零硬编码
- [ ] 核心原子组件（Surface, Prose, AutoTextarea, CenteredComposer/DockedComposer, IconButton, TextButton）
- [ ] 交互 Hook（useComposerState, useArtifactPanel, useStreamingMessage）
- [ ] Skill 编写（.claude/skills/claude-ui-system/，含查表规则 + 反例 + checklist）
- [ ] 工程护栏（ESLint 禁止裸 HEX、Stylelint 强制 var(--xxx)）

#### 后端功能

- [ ] 前端可视化仪表盘 — 绑定后端数据到 React + TV Charts，实现趋势图表、筛选结果展示、基金详情页
- [ ] adj_nav 历史回填 — 补齐 Schema v2 迁移后旧数据的 adj_nav 空值，为回测做准备
- [ ] 回测模块 — 基于历史数据验证 MA 筛选策略的有效性，输出胜率、夏普比率等指标
- [ ] 定时任务自动化 — cron/schedule 每日自动跑筛选，生成报告并推送

### Out of Scope

- 交易执行（只提供筛选信号，不提供下单/交易功能）
- 实时行情（基于日频数据，不做 Tick/分钟级实时推送）
- 多用户/权限系统（当前为单机 CLI + 本地前端，不做用户管理）
- 付费数据源集成（只用免费/低成本的 tushare/akshare/yfinance）
- 移动端 App（Web 优先，响应式适配即可）

## Context

- 技术栈：Python 3.11+ (uv) + TypeScript/React 19 (bun)
- 数据存储：SQLite（数据湖）+ JSON 文件缓存
- 前端图表：TradingView Lightweight Charts
- 数据源：tushare Pro (A股) / akshare (A股备选) / yfinance (美股)
- 现有代码质量：Pydantic 数据模型、完整类型注解、76 个单元测试覆盖核心逻辑
- 已知问题：旧数据 adj_nav 为 NULL（v2 迁移引入的新列），需要回填

## Constraints

### 后端
- **Tech stack**: Python 3.11 + uv 锁定，不动底层框架
- **Data sources**: 免费/低成本 API 为主，tushare Pro 有限额
- **Timeline**: 个人项目，按可用时间推进
- **Dependencies**: akshare 列名可能随版本变动，需防御式解析

### 前端（硬性约束）
- **构建工具**: Vite — 锁定
- **框架**: React 19 — 锁定
- **样式**: Tailwind CSS v4 — **唯一允许的 CSS 方案**。禁止 CSS Modules / styled-components / emotion / 其他 CSS-in-JS
- **UI 组件库**: shadcn/ui — 基础组件来源，上层用自定义 Token 覆盖其默认主题
- **状态管理（服务端）**: TanStack Query — 服务器数据唯一来源
- **状态管理（客户端 UI）**: Zustand — UI 状态唯一来源
- **路由**: TanStack Router — 锁定
- **图表**: TradingView Lightweight Charts — 金融图表唯一方案
- **动画**: framer-motion — 复杂交互动画（Composer 位态切换、Artifact 面板、消息出现）
- **包管理器**: bun — 锁定（`bun install` / `bun dev` / `bun build`）
- **Token 体系**: CSS 变量驱动，Tailwind @theme inline 注册。禁止任何 HEX / rgb / hsl 字面量出现在 className 中

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| SQLite 作为数据湖 | 单机项目，不需要分布式数据库 | ✓ Good |
| 默认只标注申购限额不过滤 | 避免漏掉优质限购基金 | ✓ Good |
| tushare Pro 替代 akshare 为主数据源 | 更稳定的 A 股数据 | ✓ Good |
| CompositeCNFetcher 按方法路由 | 兼顾 tushare 稳定性和 akshare 覆盖度 | — Pending |
| TV Charts 作为前端图表库 | 专业金融图表，轻量且免费 | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-19 after initialization*
