# Fund Screener v1.0 — 功能全景图

> 生成时间: 2026-04-19 | 对应代码版本: `feat/ui-components` branch

---

## 一、项目定位

**一句话**: 全市场基金/ETF 趋势筛选器 — 用 MA 均线多头排列做"右侧交易"信号过滤，叠加三因子量化打分，辅助投资决策。

**核心价值**: 用户能在 1 分钟内获取全市场符合趋势条件的基金/ETF 列表。

---

## 二、后端能力 (Python)

### 2.1 REST API (FastAPI)

| Endpoint | 方法 | 功能 | 前端调用者 |
|----------|------|------|-----------|
| `/health` | GET | 健康检查 + DB schema 版本 | — |
| `/api/funds` | GET | 基金列表（分页/市场筛选/排序） | `useFunds` |
| `/api/funds/{code}` | GET | 单只基金详情（基本信息+持仓+最新净值） | `useFundDetail` |
| `/api/screening` | GET | MA 筛选结果（按日期/市场/MA差值过滤） | `useScreening` |
| `/api/chart/{code}` | GET | 净值历史时序（供 TV Charts） | `useChartData` |
| `/api/stats` | GET | 仪表盘统计（总基金数/筛选数/数据量等） | `useStats` |

**技术细节**:
- CORS 全开放（开发阶段）
- 依赖注入: `get_db` yield 模式 + `check_same_thread=False`
- 响应统一包装: `{success, data, error}`

### 2.2 CLI 工具 (`uv run fund-screener`)

| 子命令 | 功能 | 前置条件 |
|--------|------|----------|
| *(默认)* | 全市场 MA 筛选 → Markdown 报告 | 配置 `config.yaml` |
| `scan-momentum` | 横截面动量扫描（多头排列+缩量回踩） | 已入库净值数据 |
| `detect-drift` | 风格漂移检测（季度持仓对比） | 已有两季度持仓快照 |
| `correlation` | 底层相关性矩阵（余弦相似度） | 已有持仓数据 |
| `bulk-fetch` | 异步批量抓取净值+详情 | — |
| `score` | 量化打分排行榜（三因子 Z-Score） | 已入库净值数据 |
| `--db-stats` | 查看数据湖统计信息 | 已有数据库 |
| `--update-sectors` | 更新申万行业映射表 | — |

### 2.3 数据抓取引擎

| 市场 | 数据源 | Fetcher 实现 | 能力 |
|------|--------|-------------|------|
| **CN (A股)** | tushare Pro (主) + akshare (备) | `CompositeCNFetcher` 路由分发 | 基金列表、净值、持仓、行业、申购限额 |
| **US (美股)** | yfinance | `USETFFetcher` | ETF 列表、价格、持仓(部分) |
| **HK (港股)** | yfinance | `HKETFFetcher` | ETF 列表、价格 |

**架构模式**: 抽象中间层 — `CompositeCNFetcher` 按 `config.yaml` 路由表选择 provider，新增数据源只需注册 provider 实例即可。

### 2.4 MA 均线筛选引擎

#### 2.4.1 核心信号：MA 多头排列

筛选逻辑非常简单，但背后有明确的交易哲学支撑：

```
通过条件: MA_short > MA_long
           且 latest_nav > 0（除零保护）
           且数据长度 >= ma_long（数据充足性）
```

| 参数 | 默认值 | 含义 | 可调性 |
|------|--------|------|--------|
| `ma_short` | 20 | 短期均线（MA20，约 1 个月交易日） | `config.yaml` |
| `ma_long` | 60 | 长期均线（MA60，约 1 季度交易日） | `config.yaml` |
| `lookback_days` | 180 | 回看天数（拉取历史净值长度） | `config.yaml` |

**为什么选 MA20/MA60？**

- MA20 捕捉短期趋势，反应灵敏但噪音多
- MA60 过滤噪音，确认中长期方向
- MA20 > MA60 = "短期趋势确认向上，且跑赢了中期基准"，是典型的右侧交易入场信号
- 参数可通过 `config.yaml` 自由调整（如改成 MA10/MA30 做更短周期）

**重要认知纠偏**:

> MA 交叉是**滞后指标**，它确认趋势而非预测趋势。通过筛选 ≠ 一定赚钱。
> 这是过滤器，不是预测器。它的价值是帮你把全市场 10000+ 基金压缩到几十只"当前处于趋势中"的标的，降低研究范围。

#### 2.4.2 多周期涨跌幅统计

对每只通过筛选的基金，额外计算 5 个周期的累计涨跌幅：

| 周期 | 交易日数 | 含义 |
|------|----------|------|
| change_1w | 5 | 近 1 周 |
| change_1m | 22 | 近 1 月 |
| change_3m | 66 | 近 1 季度 |
| change_6m | 132 | 近半年 |
| change_1y | 252 | 近 1 年 |

计算方式: `(latest_nav - nav[N天前]) / nav[N天前] * 100`

**为什么用交易日而非自然日？** 股市周末不开盘，自然日会把周末算进去，导致"1 周"实际跨了 9 天。用交易日保证周期精确。

**数据不足处理**: 某周期数据不够 → 填 `None`。宁可没有，不给误导数字。

#### 2.4.3 当日涨跌幅

从净值序列最近两日直接计算：

```
daily_change = (today_nav - yesterday_nav) / yesterday_nav * 100
```

所有市场统一逻辑，不依赖外部 API（旧版 akshare 需要单独调用全市场涨跌幅接口，新版直接从已有 nav_df 计算，零额外请求）。

#### 2.4.4 申购限额标注（CN 市场专属）

A 股基金有个特殊问题：**限购**。

- 基金经理觉得规模太大了 → 限额申购
- 基金经理不想让你买了 → 暂停申购
- 这些状态每天都在变

**实现方式**:

1. 筛选开始前，一次性预加载全市场申购限额映射表（`fetch_purchase_limit_map()`）
2. 映射表格式: `{code: (limit_amount, status_text)}`
3. 每只基金通过 MA 筛选后，O(1) 查表标注
4. 标注结果随筛选结果一起入库 `screening_results.purchase_limit / purchase_status`

**分组逻辑**（前端/报告展示用）:

| 限额金额 | 状态 | 展示 |
|----------|------|------|
| >= 1亿 或 1e11 | 无限制 | "开放申购" |
| > 0 且 < 1亿 | 限额 | "限购 X 万" |
| = 0 | 暂停 | "暂停申购" |
| None | 未知 | 不显示 |

**默认行为**: 只标注，不过滤。所有通过 MA 的基金都保留，让用户自己判断要不要买限额的。

#### 2.4.5 完整筛选流程（CLI 默认命令）

```
Step 0: 加载配置 config.yaml
   └─ 确定市场范围 (CN/US/HK/all)、MA 参数、数据湖开关

Step 1: 初始化
   ├─ FileCache（TTL 缓存，保护 API 限速）
   ├─ DataStore（SQLite 数据湖，如启用）
   └─ 构建 Fetcher（CN 用 CompositeCNFetcher 路由分发）

Step 2: CN 市场预加载申购限额映射表（如启用）

Step 3: 拉取基金列表
   ├─ US: yfinance 获取 S&P 500 / NASDAQ ETF 列表
   ├─ CN: tushare/akshare 获取公募基金列表
   └─ HK: yfinance 获取港股 ETF 列表
   → 数据湖: 写入 funds 表

Step 4: 逐只基金遍历
   For each fund:
   ├─ 拉净值历史 (lookback_days)
   │   → 数据湖: 写入 nav_records 表（无论是否通过筛选）
   ├─ 拉基金详情（成立日期、经理、规模、基准）
   │   → 数据湖: 写入 funds 详情字段
   ├─ MA 筛选: calculate_ma(nav, 20) vs calculate_ma(nav, 60)
   │   ├─ 数据不足 (< 60 天) → 跳过
   │   ├─ MA20 <= MA60 → 跳过
   │   └─ MA20 > MA60 → 通过！
   ├─ 标注申购限额（CN 市场）
   ├─ 计算多周期涨跌幅 + 当日涨跌幅
   ├─ 拉持仓 + 行业分布
   │   → 数据湖: 写入 holdings + sector_exposure 表
   └─ 组装 FundInfo + 持久化筛选结果
       → 数据湖: 写入 screening_results 表

Step 5: 生成 Markdown 报告
   ├─ 按市场分组
   ├─ CN: 按申购状态分三组展示
   ├─ US/HK: 按 MA 差值降序
   └─ 附加 LLM 分析提示词
```

#### 2.4.6 防御性编程

| 场景 | 处理 |
|------|------|
| 净值数据不足 MA_long 天 | 返回 None，跳过该基金 |
| MA 值为 NaN | 返回 None |
| MA_long = 0（除零） | 返回 None |
| nav 为空 DataFrame | 返回 None |
| 持仓/行业拉取失败 | warning 日志，继续（用空列表） |
| 申购限额加载失败 | warning 日志，继续（无标注） |

---

### 2.5 量化打分引擎

量化打分引擎解决一个核心问题：**MA 筛选通过的几百只基金，谁更值得买？**

#### 2.5.1 设计哲学

- **打分层是纯计算**: 不访问网络、不调 API，输入是 (FundInfo, nav_df) 列表
- **横截面比较**: 所有基金在同一套标准下打分，分数可比
- **多因子融合**: 单个因子都有盲点，组合使用降低误判

#### 2.5.2 三因子定义

| 因子 | 公式 | 方向 | 直觉含义 |
|------|------|------|----------|
| **Momentum（动量）** | `(latest_nav - MA20) / MA20` | 越大越好 | 趋势爆发力。正值 = 价格在均线之上，冲劲足 |
| **Max Drawdown（回撤）** | `min((nav - cummax) / cummax)` | 越接近 0 越好 | 历史上跌得最惨的一次。负数，-0.25 = 最大回撤 25% |
| **Sharpe（夏普比率）** | `(excess_mean / excess_std) * sqrt(252)` | 越大越好 | 每承担 1 单位风险获得的超额收益 |

**细节展开**:

**动量因子**: 不是简单的"涨了多少"，而是"当前价格偏离短期均线的幅度"。偏离越大，短期冲劲越足。但如果偏离太大（如 +15%），也可能意味着短期过热、即将回调。

**回撤因子**: 用 `nav_series.cummax()` 追踪历史最高点，计算每个时间点相对历史高点的跌幅。取最小值（最惨的那次）。这是负值，-0.25 表示"曾经从历史高点跌了 25%"。**打分前会反转方向**（乘 -1），让"回撤小"变成"分数高"。

**夏普比率**: 日收益率 = `pct_change().dropna()`。超额收益 = 日收益率均值 - 日无风险利率（默认 2%/252）。年化 = 乘 `sqrt(252)`。**注意**: 年化的是比值而非收益本身——收益率乘 N 年化，波动率乘 sqrt(N) 年化，比值里 N 消掉变成 sqrt(N)。

#### 2.5.3 Z-Score 标准化

三因子量纲完全不同（动量是百分比、回撤是百分比、夏普是比值），不能直接加权。必须先标准化到同一尺度。

**Z-Score 公式**: `Z = (x - mean) / std`

```
原始池: [基金A, 基金B, 基金C, ...]

Step 1: 提取所有基金的 momentum 值
   momentums = [m_A, m_B, m_C, ...]

Step 2: 计算均值和标准差
   mean = sum(momentums) / N
   std = sqrt(sum((x - mean)^2) / (N-1))   // 样本标准差

Step 3: 每个基金的 Z-Score
   z_momentum_A = (m_A - mean) / std

Step 4: 回撤方向反转
   drawdown 是负数，"大"=跌得多=差
   先乘 -1: inverted = [-d_A, -d_B, ...]  // 现在大=回撤小=好
   再算 Z-Score
```

**边界处理**:

| 场景 | 处理 |
|------|------|
| 全部为 NaN | 返回全 0（该因子不贡献分数） |
| std == 0（所有值相同） | 返回全 0 |
| 单个 NaN | 该位置返回 0（不惩罚不奖励） |
| 候选池 < 2 | 无法算标准差，返回全 0 |

#### 2.5.4 加权求和与排名

```
composite_score = w_momentum * z_momentum
                + w_drawdown * z_drawdown
                + w_sharpe * z_sharpe
```

默认权重（`config.yaml` 可调）:

```yaml
scoring:
  weights:
    momentum: 0.40   # 趋势爆发力占 40%
    drawdown: 0.35   # 风险控制占 35%
    sharpe: 0.25     # 风险收益比占 25%
```

**权重之和不强制 = 1.0**，允许实验性调整。

排名: 按 `composite_score` 降序，取 Top N（默认 30）。

#### 2.5.5 过滤层

在进入打分之前，有三层过滤确保打分池质量：

**过滤 1: QDII 债基排除**

QDII 基金（投资海外市场的基金）名称五花八门，但 QDII 债基几乎都在名称里含"债"字。通过关键词匹配排除：

```python
排除关键词: {"债", "纯债", "利率", "增利", "信用", "收益债", "短债", "中短债", "超短债"}
```

为什么只排除 QDII 债基而非所有债基？因为 A 股债基通常在 `fund_types` 过滤阶段已被剔除（只保留股票型/混合型/指数型）。QDII 基金的类型标注不精确，需要名称二次过滤。

**过滤 2: 数据充足性检查**

```
nav_count >= min_nav_days (默认 60)
```

数据不足的基金直接跳过，不打分。避免"只有 10 天数据却算出漂亮夏普"的误导。

**过滤 3: 三因子完整性检查**

三因子中任一为 NaN → 跳过。NaN 意味着数据有问题（如零波动导致夏普除零、数据不足导致动量无法计算），不应该参与排名。

#### 2.5.6 完整打分流程（CLI `score` 子命令）

```
Step 1: 从 DB 读取基金列表
   └─ SELECT id, market, code, name FROM funds
      （可选按市场过滤）

Step 2: 逐只基金读取全量净值序列
   └─ SELECT date, COALESCE(adj_nav, nav) AS nav
      FROM nav_records WHERE fund_id = ? ORDER BY date ASC
   → 跳过 nav_count < min_nav_days 的基金

Step 3: 组装 (FundInfo, nav_df) 对
   ├─ 从 nav_df 计算多周期涨跌幅 (trend_stats)
   ├─ 从 nav_df 计算当日涨跌幅
   └─ 构造简化 FundInfo（不打分不需要持仓/行业）

Step 4: 打分引擎 score_funds()
   ├─ 过滤 QDII 债基
   ├─ 过滤数据不足基金
   ├─ 对每只基金算三因子 RiskMetrics
   │   ├─ momentum_score(nav, 20)
   │   ├─ max_drawdown(nav)
   │   └─ sharpe_ratio(nav, rf=0.02)
   ├─ 过滤三因子有 NaN 的基金
   ├─ Z-Score 标准化（回撤先反转）
   ├─ 加权求和 → composite_score
   └─ 降序排名 → 截取 Top N

Step 5: 补充 Top 10 持仓（从 DB 读，不调 API）

Step 6: 生成 Markdown 打分报告
```

#### 2.5.7 筛选 vs 打分的关系

| 维度 | MA 筛选 | 量化打分 |
|------|---------|----------|
| **目的** | 过滤"不在趋势中"的基金 | 在趋势基金中排序"谁更好" |
| **输入** | 净值序列 | 净值序列（更长历史） |
| **输出** | 通过/不通过（布尔） | 综合得分 + 排名（连续值） |
| **前置条件** | 无 | 需要先入库净值数据 |
| **调用方式** | CLI 默认命令自动执行 | CLI `score` 子命令单独执行 |
| **结果存储** | screening_results 表 | 报告文件（不入库） |

**一句话**: 筛选是"能不能买"的过滤器，打分是"买哪个"的排序器。两者互补，但不互相依赖——你可以只跑筛选不看打分，也可以直接对全库打分（不先筛选）。

---

### 2.6 OLAP 量化分析

在 MA 筛选和量化打分之外，提供三个独立的深度分析工具，用于特定场景下的辅助决策。

#### 2.6.1 横截面动量扫描 (`scan-momentum`)

**场景**: 你已经知道哪些基金处于多头排列，但你想找"趋势中最强势、且今天刚好回调"的标的 —— 经典右侧回踩买入信号。

**核心逻辑**:

```
条件 1: MA_short > MA_long   (多头排列，趋势向上)
条件 2: daily_return < 0      (当日下跌，缩量回踩)
```

**实现**: SQL Window Function 在数据库层完成 MA 计算，Python 层只做 daily_return 过滤和排序。

```sql
-- CTE 为每只基金的净值标注行号（按日期倒序）
WITH nav_with_rank AS (
    SELECT fund_id, date, COALESCE(adj_nav, nav) AS effective_nav,
           ROW_NUMBER() OVER (PARTITION BY fund_id ORDER BY date DESC) AS rn
    FROM nav_records WHERE date <= ?
),
-- 分组计算 MA_short / MA_long / latest_nav / prev_nav
fund_ma AS (
    SELECT fund_id,
           AVG(CASE WHEN rn <= ? THEN effective_nav END) AS ma_short_val,
           AVG(CASE WHEN rn <= ? THEN effective_nav END) AS ma_long_val,
           MAX(CASE WHEN rn = 1 THEN effective_nav END) AS latest_nav,
           MAX(CASE WHEN rn = 2 THEN effective_nav END) AS prev_nav
    FROM nav_with_rank WHERE rn <= ?
    GROUP BY fund_id HAVING COUNT(*) >= ?
)
SELECT ... FROM fund_ma
WHERE ma_short_val > ma_long_val   -- 多头排列
```

**输出**: 按 MA 差值降序排列的回踩标的列表（差值越大，趋势越强）。

#### 2.6.2 风格漂移检测 (`detect-drift`)

**场景**: 你持有某只主动基金半年，发现它最近表现和预期不符 —— 是不是基金经理偷偷换了赛道？

**核心指标**: 换手率 = `sum(|curr_weight - prev_weight|) / 2`

除以 2 是因为每一份"卖出"都对应一份"买入"，避免双重计算。

**判定**: 换手率 > threshold（默认 20%）→ 判定为风格漂移。

**输出**:
- 总换手率
- 新进持仓列表（上季度没有，这季度新进的）
- 退出持仓列表（上季度有，这季度消失的）
- 大幅调仓明细（单只个股权重变动 > 3%）

#### 2.6.3 底层相关性矩阵 (`correlation`)

**场景**: 你买了 5 只基金，分散投资 —— 但它们底层持仓是否高度重叠？买了 5 只"变种沪深300"没有意义。

**计算方式**: 行业权重向量的余弦相似度。

```
similarity = A·B / (|A| × |B|)

A, B = 两只基金的行业权重向量
维度 = 申万一级行业（食品饮料、电子、医药生物...）
```

**为什么用行业权重而非净值相关性？**

- 净值相关性反映的是"过去走势像不像"，滞后且受市场大环境影响
- 行业权重反映的是"底层持仓像不像"，是结构性的、更稳定的相似度度量
- 两只基金可能净值走势不同（一只涨一只跌），但底层都重仓白酒 —— 这种情况净值相关性发现不了，行业权重能发现

**报警阈值**: 默认 0.3（30% 行业权重相似度）。超阈值的对会被标红报警。

**实现**: SQL 层 JOIN `holdings` + `stock_sector_mapping` 聚合行业权重，Python 层计算余弦相似度（SQLite 无向量运算）。

### 2.7 数据湖 (`storage.py`)

| 表 | 用途 | 关键索引 |
|----|------|----------|
| `funds` | 基金维度表 (code/name/market/详情) | UNIQUE(market, code) |
| `nav_records` | 净值时序 (date/nav/adj_nav) | (fund_id, date) |
| `holdings` | 持仓快照 (stock_code/weight_pct) | (fund_id, stock_code, snapshot_date) |
| `sector_exposure` | 行业分布 | (fund_id, sector, snapshot_date) |
| `screening_results` | 筛选结果快照 (MA指标/评分) | (fund_id, screening_date) |
| `stock_sector_mapping` | 申万行业映射 | UNIQUE(stock_code) |

**Schema 版本管理**: PRAGMA user_version，支持 V1→V2→V3 链式迁移。

### 2.8 基础设施

| 模块 | 功能 |
|------|------|
| `cache.py` | FileCache — 本地文件缓存，TTL 过期，API 限速保护 |
| `async_fetcher.py` | AsyncBulkFetcher — 并发抓取 + 写入数据湖 |
| `error_queue.py` | ErrorQueue — 失败记录持久化 + 重试队列 |
| `reporter.py` | Markdown 报告生成（筛选报告 + 打分报告） |
| `config.py` | `config.yaml` 配置加载 + Pydantic 校验 |

---

## 三、前端能力 (React/TypeScript)

### 3.1 页面路由

| 路由 | 页面 | 数据源 | 状态 |
|------|------|--------|------|
| `/` | 仪表盘 | `useStats` + `useScreening(limit=10)` | ✅ 真数据 |
| `/funds` | 基金列表 | `useFunds(page=1, pageSize=100)` | ✅ 真数据 |
| `/funds/$code` | 基金详情 | `useFundDetail` + `useChartData(days=180)` | ✅ 真数据 |
| `/screening` | 筛选结果 | `useScreening(limit=50)` | ✅ 真数据 |
| `/chat` | AI 分析 | mock 延迟响应 | ⏳ 待接入后端 |

### 3.2 业务组件 (`components/views/`)

| 组件 | 职责 | 复用场景 |
|------|------|----------|
| `StatsCard` | 统计指标卡片（标题+数值+趋势+图标） | 仪表盘 |
| `ScreeningResultItem` | 筛选结果列表项（代码+市场+MA指标+徽章） | 仪表盘+筛选页 |
| `FundTable` | 基金基础信息表格 | 基金列表页 |
| `FundDetailHeader` | 基金详情头部（信息网格+最新净值） | 详情页 |
| `HoldingsList` | 持仓列表（权重排序+进度条） | 详情页 |
| `ChartContainer` | TV Charts 净值走势+MA20/MA60叠加 | 详情页 |
| `MarketBadge` | 市场标识徽章 (CN/US/HK) | 多处 |
| `ScoreBadge` | 量化评分徽章（颜色等级） | 多处 |
| `MADiffIndicator` | MA 差值指示器（箭头+颜色） | 多处 |
| `PurchaseStatusBadge` | 申购状态徽章（开放/限额/暂停） | 多处 |

### 3.3 API Hooks 层 (`hooks/api/`)

| Hook | 端点 | 能力 |
|------|------|------|
| `useFunds` | GET `/api/funds` | 分页/市场筛选/排序 |
| `useFundDetail` | GET `/api/funds/{code}` | 详情+持仓+最新净值 |
| `useScreening` | GET `/api/screening` | 日期/市场/MA差值过滤 |
| `useChartData` | GET `/api/chart/{code}` | 天数范围 (7~730) |
| `useStats` | GET `/api/stats` | 仪表盘全量统计 |

**边界约定**: Hooks 层负责 snake_case → camelCase 映射，页面层零转换。

### 3.4 设计系统

| 层级 | 内容 |
|------|------|
| **Token** | CSS 变量 (--text-primary, --accent-primary, --border-subtle...) |
| **Animation Token** | `tokens.animation.ts` — presence variants + transition presets |
| **CVA Variants** | `lib/variants.ts` — MarketBadge/ScoreBadge/PurchaseStatusBadge/MADiffIndicator |
| **原子组件** | Surface / AutoTextarea / IconButton / TextButton / Prose / Composer |
| **shadcn/ui** | Button / Card / Input / Badge / Table / ScrollArea / Separator / Skeleton |

### 3.5 图表系统

- **库**: TradingView Lightweight Charts
- **功能**: 净值线 + MA20(实线) + MA60(虚线) 叠加
- **市场感知**: CN 市场红涨绿跌（CSS data-market 驱动）
- **MA 计算**: 前端滑动窗口实时计算

### 3.6 状态管理

- **服务端状态**: TanStack Query (staleTime: 5min)
- **客户端状态**: Zustand (`appStore` — sidebarOpen)
- **路由**: TanStack Router (file-based)

---

## 四、技术栈

### 后端

| 层 | 技术 |
|----|------|
| 运行时 | Python 3.11 |
| 包管理 | uv |
| Web 框架 | FastAPI |
| 数据验证 | Pydantic v2 |
| 数据湖 | SQLite (WAL 模式) |
| 数据分析 | pandas |
| CLI | click |
| HTTP 客户端 | httpx / yfinance / tushare / akshare |

### 前端

| 层 | 技术 |
|----|------|
| 构建工具 | Vite 6 |
| 框架 | React 19 |
| 语言 | TypeScript |
| 样式 | Tailwind CSS v4 |
| UI 库 | shadcn/ui |
| 路由 | TanStack Router |
| 数据获取 | TanStack Query |
| 状态管理 | Zustand |
| 图表 | TradingView Lightweight Charts |
| 动画 | framer-motion |
| 包管理 | bun |

---

## 五、已完成 Phase (✅)

| Phase | 名称 | 完成内容 |
|-------|------|----------|
| **0** | Claude 设计系统 | Token 三层体系 + 6 原子组件 + 3 交互 Hook + framer-motion |
| **1** | 后端 API 层 | 6 端点 + CORS + SQLite 依赖注入 + 线程安全修复 |
| **2** | 前端仪表盘 | 5 个页面 + 10 业务组件 + 5 API hooks + 真实数据对接 |

---

## 六、待完成 Phase (⏳)

| Phase | 名称 | 待做内容 | 依赖 |
|-------|------|----------|------|
| **3** | 回测引擎 | adj_nav 历史回填脚本、MA 策略回测（胜率/夏普）、回测框架 | 数据湖已有净值数据 |
| **4** | 定时任务 | cron/schedule 自动化、报告自动生成、任务日志监控 | Phase 3 |
| **5** | 回测展示 | 回测结果可视化页面、策略对比图表 | Phase 3 |
| **—** | AI 聊天 | `/api/chat` 后端端点 + 前端接入 Vercel AI SDK | 可选 |

---

## 七、已知问题 & 修复记录

| 日期 | 问题 | 修复 |
|------|------|------|
| 2026-04-19 | SQLite 跨线程 crash | `check_same_thread=False` + yield 模式释放连接 |
| 2026-04-19 | 前端 `.toFixed()` 空值 crash | 所有数值字段加 `number \| null` 类型 + `?.toFixed() ?? '—'` |

---

## 八、快速启动

```bash
# 后端
uv run uvicorn fund_screener.api.main:app --reload --port 8000

# 前端
cd web && bun dev

# CLI 筛选
uv run fund-screener --market all --verbose

# CLI 打分
uv run fund-screener score --market cn

# 查看数据湖
uv run fund-screener --db-stats
```

浏览器访问: `http://localhost:9473`
API 文档: `http://localhost:8000/docs`
