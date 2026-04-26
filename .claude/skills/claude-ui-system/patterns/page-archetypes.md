# Page Archetypes

## Research Dashboard Page

用于 `/`。

```text
PageShell
  PageHeader
    eyebrow: FUND SCREENER
    title: 全市场趋势筛选
    description: 一句话解释今天市场筛选状态
    actions: primary refresh / secondary view screening
  InsightStrip
    3-4 MetricCard
  MainSurface
    TopCandidatesList or ArchiveTable preview
  SecondaryGrid
    DataQualityCard
    MarketStatusCard
    RecentBacktestCard
```

Rules:
- 首页不是营销 landing，也不是后台 dashboard。
- 首屏必须说明“今天有什么值得看”。
- MetricCard 不得超过 4 个。
- 主视觉焦点只能是 Top candidates 或 market summary 二选一。

## Archive List Page

用于 `/funds`、`/screening`、future blogger archive。

```text
PageShell
  PageHeader
    eyebrow
    title
    description
    status summary
  FilterBar
    tabs
    compact controls
    sort indicator
  ArchiveSurface
    ArchiveTable
      mono code column
      tabular numeric columns
      subtle hover
      right-edge action affordance
  Pagination or LoadMore
```

Rules:
- 表格必须包在 ArchiveSurface 内，不能直接铺在页面 canvas 上。
- 行高默认 52-56px。
- 代码、百分比、金额、排名必须使用 mono + tabular nums。
- 表头 12px、regular/medium，不要 bold 大标题感。
- hover 只能用 `--bg-hover`，不能加阴影。
- 涨跌/强弱只能用 signal token，不能用 `text-red-*` / `text-green-*`。

## Fund Dossier Page

用于 `/funds/$code`。

```text
DossierPage
  DossierHeader
    identity: code + name + market
    diagnosis summary
    action group
  DiagnosisGrid
    3-4 SignalCard
  EvidenceLayout
    left: chart / exposure / timeline
    right: holdings / explanation / risk notes
  TimelineSurface optional
```

Rules:
- 这是产品核心页，不允许 AI 自由发挥。
- 页面必须像“研究档案”，不是“详情表单”。
- 首屏必须给出诊断摘要，而不是只展示基本信息。
- 持仓、行业、净值走势属于 evidence，不是 decoration。
- 行业色只能出现在 exposure chart、holding tags、legend，不得染页面背景。

## Chat/Composer Page

用于 `/chat`。

```text
ChatShell
  ConversationSurface
  ArtifactPanel optional
  Composer
```

Rules:
- 这是最接近 `claude.ai/new` 的页面。
- Composer 必须使用已有 composer tokens。
- AI 输出里的金融解释应复用 Dossier / Archive 的展示组件，不要在 chat 内另造一套卡片。
