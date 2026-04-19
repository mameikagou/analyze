# Requirements: Fund Screener

**Defined:** 2026-04-19
**Core Value:** 用户能在 1 分钟内获取全市场符合趋势条件的基金/ETF 列表，并看到每只标的的量化评分、持仓结构、申购状态和可视化走势

## v1 Requirements

### Design System (Claude UI)

- [ ] **DSGN-01**: Token 三层体系 — Primitive（调色板原始值）、Semantic（语义映射，支持 dark mode）、Component（组件级特例）
- [ ] **DSGN-02**: Tailwind 配置零硬编码 — 所有 colors/fontFamily/borderRadius/boxShadow 指向 CSS 变量
- [ ] **DSGN-03**: 原子组件封装 — Surface（背景容器）、Prose（Markdown 正文）、AutoTextarea（自动撑高输入框）
- [ ] **DSGN-04**: Composer 组件 — CenteredComposer（空态居中）/ DockedComposer（对话底部），含 useComposerPosition hook
- [ ] **DSGN-05**: 按钮原语 — IconButton / TextButton（透明底 + hover 变 surface，无实心填充）
- [ ] **DSGN-06**: 交互 Hook — useComposerState（idle/typing/submitting/streaming/error）、useArtifactPanel（closed/peek/expanded）、useStreamingMessage
- [ ] **DSGN-07**: Skill 体系 — .claude/skills/claude-ui-system/ 含 tokens.reference.md、components.reference.md、patterns/、anti-patterns.md、checklist.md
- [ ] **DSGN-08**: 工程护栏 — ESLint 禁止裸 HEX/rgb、禁止 bg-white/bg-black/text-gray-*；Stylelint 强制 var(--xxx)

### Frontend Dashboard

- [ ] **FRONT-01**: 首页展示全市场筛选结果总览（通过数量、市场分布、趋势概览）
- [ ] **FRONT-02**: 筛选结果列表页（表格展示，支持按 MA 差值/打分/申购状态排序）
- [ ] **FRONT-03**: 单只基金详情页（净值走势图、MA 均线叠加、基本信息卡片、持仓结构）
- [ ] **FRONT-04**: TV Charts 集成（K 线图 + MA 均线叠加，支持多时间周期切换）
- [ ] **FRONT-05**: 前端路由体系（首页 / 列表 / 详情 / 回测结果）
- [ ] **FRONT-06**: 前端与后端 API 对接（REST API 设计，数据序列化）

### Data Quality

- [ ] **DATA-01**: adj_nav 历史回填脚本（补齐 Schema v2 迁移后旧数据的 adj_nav NULL 值）
- [ ] **DATA-02**: 回填进度监控（批次进度、已处理/剩余数量、预计完成时间）
- [ ] **DATA-03**: 回填断点续传（中断后从断点继续，不重复处理）

### Backtest Engine

- [ ] **BACK-01**: 回测引擎框架（策略信号 → 模拟持仓 → 收益计算，支持参数化配置）
- [ ] **BACK-02**: MA 筛选策略回测（历史信号胜率、平均盈亏、最大回撤、夏普比率）
- [ ] **BACK-03**: 回测结果可视化（收益曲线、回撤图、月度收益热力图）
- [ ] **BACK-04**: 回测报告生成（Markdown 格式，含关键指标摘要）

### Automation

- [ ] **AUTO-01**: 定时任务编排（每日固定时间自动跑全市场筛选）
- [ ] **AUTO-02**: 报告自动生成和持久化（筛选报告 + 回测报告自动保存到指定目录）
- [ ] **AUTO-03**: 任务日志和监控（运行状态、耗时、异常告警）

## v2 Requirements

### Data Management

- **DATM-01**: 数据清理/归档策略（长期历史数据压缩归档，释放磁盘空间）
- **DATM-02**: 增量数据校验（每日数据完整性检查，缺失检测）

### Advanced Analytics

- **ANLT-01**: 组合分析（多基金持仓去重，计算真实行业暴露）
- **ANLT-02**: 择时信号增强（结合成交量、波动率等多因子择时）

### Notifications

- **NOTF-01**: 筛选结果推送（邮件/飞书/钉钉，可配置触发条件）

## Out of Scope

| Feature | Reason |
|---------|--------|
| 交易执行（下单/撤单） | 仅提供筛选信号，交易由用户自主决策，避免合规风险 |
| 实时行情（Tick/分钟级） | 日频数据已满足趋势筛选需求，实时数据成本高 |
| 多用户/权限系统 | 当前为单机 CLI + 本地前端，用户管理增加不必要的复杂度 |
| 付费数据源（Wind/彭博） | 项目定位为低成本个人工具，只用免费/低成本 API |
| 移动端原生 App | Web 优先，响应式适配即可覆盖移动端需求 |
| 社交/分享功能 | 与核心筛选价值无关，增加维护负担 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DSGN-01 | Phase 0 | Pending |
| DSGN-02 | Phase 0 | Pending |
| DSGN-03 | Phase 0 | Pending |
| DSGN-04 | Phase 0 | Pending |
| DSGN-05 | Phase 0 | Pending |
| DSGN-06 | Phase 0 | Pending |
| DSGN-07 | Phase 0 | Pending |
| DSGN-08 | Phase 0 | Pending |
| FRONT-01 | Phase 2 | Pending |
| FRONT-02 | Phase 2 | Pending |
| FRONT-03 | Phase 2 | Pending |
| FRONT-04 | Phase 2 | Pending |
| FRONT-05 | Phase 2 | Pending |
| FRONT-06 | Phase 1 | Pending |
| DATA-01 | Phase 3 | Pending |
| DATA-02 | Phase 3 | Pending |
| DATA-03 | Phase 3 | Pending |
| BACK-01 | Phase 3 | Pending |
| BACK-02 | Phase 3 | Pending |
| BACK-03 | Phase 3 | Pending |
| BACK-04 | Phase 3 | Pending |
| AUTO-01 | Phase 4 | Pending |
| AUTO-02 | Phase 4 | Pending |
| AUTO-03 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 24 total
- Mapped to phases: 24
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-19*
*Last updated: 2026-04-19 after initial definition*
