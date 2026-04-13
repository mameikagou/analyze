# 量化打分引擎 — 架构与公式决策文档

> 创建日期: 2026-04-13
> 决策人: 用户（权重）+ Opus（归一化方案 + 过滤规则）

## 1. 目标

在现有 MA 趋势筛选器之上叠加「多因子量化打分」层，从全市场权益类基金中
按客观公式选出 Top N 候选池，替代人工/廉价 AI 初筛。

## 2. 打分池定义（精细化过滤）

### 2.1 fund_types 一级过滤

config.yaml `cn_fund.fund_types` 控制，保留：

| fund_type 值 | 含义 |
|---|---|
| 股票型 | A 股权益 |
| 混合型 | 股债混合（含偏股/偏债/灵活配置） |
| 指数型 | 被动跟踪指数 |
| QDII型 | 海外投资（含股票/债券/混合子类） |

剔除：货币型、债券型。

### 2.2 QDII 二次过滤（名称关键词排除法）

tushare/akshare 的 `fund_type` 不区分 QDII 下的股票/债券子类。
**排除法**：基金名称包含以下关键词的 QDII 基金剔除：

```python
_QDII_BOND_KEYWORDS: frozenset[str] = frozenset({
    "债", "纯债", "利率", "增利", "信用", "收益债",
    "短债", "中短债", "超短债",
})
```

**为什么用排除法不用包含法？**
QDII 权益基金名称五花八门（纳斯达克/标普/全球/科技/消费/医药...），
穷举关键词不现实且容易漏。而 QDII 债基名称**几乎全含"债"字**，
排除法误杀率低、维护成本低。

已知误杀风险：名称含"收益"但实际是权益型的 QDII（如"全球收益"）。
因为排除列表里没有"收益"，所以**不会被误杀**。

### 2.3 US / HK 市场

US ETF / HK ETF 本身全是权益类，无需额外过滤，直接参与打分。

## 3. 三因子公式

### 3.1 趋势爆发力 (Momentum)

```
momentum = (latest_nav - MA20) / MA20
```

- `latest_nav`: 最新一天的单位净值
- `MA20`: 最近 20 个交易日的简单移动平均
- 物理含义：当前价格偏离短期均线的幅度，正值=上涨势头，值越大势越猛
- 复用：`screener.py:77` 的 `calculate_ma()` 函数

### 3.2 最大回撤 (Max Drawdown)

```
drawdown_series = (nav_series - cummax) / cummax
max_drawdown = min(drawdown_series)           # 返回负数
```

- 区间：使用 DB 中**全量可用净值**（不受 `lookback_days` 限制）
- 物理含义：从历史最高点到最低谷的最大跌幅
- 返回值：负数百分比（如 -0.25 = -25%）

### 3.3 夏普比率 (Sharpe Ratio)

```
daily_returns = nav_series.pct_change().dropna()
excess_mean   = daily_returns.mean() - rf_daily
excess_std    = daily_returns.std(ddof=1)
sharpe        = (excess_mean / excess_std) * sqrt(periods_per_year)
```

- `rf_daily = rf_annual / periods_per_year`，默认 `rf_annual=0.02`（2% 无风险利率）
- `periods_per_year = 252`（交易日）
- 物理含义：每承担 1 单位风险获得的超额收益，值越大性价比越高

## 4. Z-Score 标准化

不同因子量级差异巨大：
- momentum 通常在 [-0.1, 0.3] 范围
- max_drawdown 通常在 [-0.5, 0] 范围
- sharpe 通常在 [-1, 3] 范围

直接加权会让大量级因子主导结果。**Z-Score 标准化**把每个因子拉到 μ=0, σ=1：

```
z_i = (x_i - mean(x)) / std(x)
```

### 4.1 方向处理

- momentum: 值越大越好 → z_momentum 直接用
- max_drawdown: 值越大（越接近 0）越好 → z_drawdown **乘以 -1** 再标准化
  即：先 `drawdown_inverted = -max_drawdown`（正数，回撤小=值大），再 Z-Score
- sharpe: 值越大越好 → z_sharpe 直接用

### 4.2 零标准差兜底

如果某因子所有基金值完全相同（std=0），Z-Score 会除零。
兜底策略：`std == 0` 时，该因子所有基金 Z-Score = 0（不贡献分数）。

## 5. 加权求和

```
composite_score = w_momentum * z_momentum
                + w_drawdown * z_drawdown_inverted
                + w_sharpe   * z_sharpe
```

**权重（用户指定）**：

| 因子 | 权重 | 理由 |
|---|---|---|
| momentum | 0.4 (40%) | 用户核心需求是找上涨趋势 |
| drawdown | 0.3 (30%) | 抗跌能力作为风控约束 |
| sharpe   | 0.3 (30%) | 风险调整后收益作为质量约束 |

权重在 `config.yaml` 的 `scoring.weights` 段配置，可随时调整。

## 6. 数据需求

| 因子 | 最低数据量 | 推荐数据量 |
|---|---|---|
| momentum (MA20) | 20 交易日 | 60 交易日 |
| max_drawdown | 60 交易日 | 252 交易日（1 年） |
| sharpe | 60 交易日 | 252 交易日（1 年） |

`scoring.min_nav_days = 60`：净值不足 60 天的基金不参与打分（数据不足算出来不靠谱）。

数据从 DataStore 的 `nav_records` 表读取（已有全量历史），不受 CLI 的 `lookback_days=150` 限制。

## 7. 已知局限性

1. **信息重叠**：夏普分母是波动率，回撤也反映波动。两者有 ~40% 信息重叠。
   用户知情并接受此权重分配。
2. **动量追涨风险**：40% 动量权重在牛末阶段会选出即将崩盘的标的。
   这是用户的"右侧交易"策略设计意图，不是 bug。
3. **无分散度约束**：Top 30 可能高度同质（如全是新能源）。
   Phase 2+ 迭代可加 `calculate_correlation_matrix` 做去相关。
4. **QDII 名称过滤依赖中文**：极少数 QDII 基金可能纯英文名称，绕过关键词检测。
   可接受的误差率（<1%），后续可加基金投资范围字段辅助判断。
