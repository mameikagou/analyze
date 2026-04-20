# 回测引擎架构设计原则

> Phase 3 回测引擎的顶层约束。在写任何回测代码之前，必须接受这三条原则，否则后面会反复返工。

---

## 原则一：因子（Factor）和策略（Strategy）必须解耦

**因子**是"给每只基金打分/产生信号的函数"。
**策略**是"拿到信号后怎么交易的规则"。

项目里现有的三因子打分和 MA 筛选，本质已经是因子，但它们和"交易决策"混在一起。新架构里要彻底分开：

```
因子层:   nav_df → [因子A] → signal_df
                  [因子B] → signal_df
                  [因子C] → signal_df

策略层:   signal_df + config → 交易规则（调仓频率、仓位管理、止损逻辑）

回测层:   交易记录 → 绩效指标（收益率、夏普、最大回撤）
```

**违反此原则的后果**：
- 因子一改，策略逻辑跟着改，无法独立回测不同因子组合
- 同一因子无法复用于不同策略（比如 MA 因子既可以用于"满仓持有"策略，也可以用于"动态仓位"策略）

---

## 原则二：信号（Signal）是因子和回测之间的唯一契约

所有因子——不管是 MA 技术面、三因子量化、时政分析、还是别人的持仓导入——最终都必须产出同一种东西：

**一个 `pd.DataFrame`**，其中：
- `index`: 日期（`DatetimeIndex`，日频）
- `columns`: 基金代码
- `values`:
  - `True/False` → 持仓信号（该日是否持有该基金）
  - `float` → 持仓权重（该日该基金占多少仓位，sum(weights) <= 1.0）

**为什么用这种格式？**

```python
# MA 因子 → 信号
ma_signal = (
    df['MA20'] > df['MA60']    # 多头排列信号
).unstack(level=0)              # 转成 (date, fund_code) 的 DataFrame

# 三因子打分 → 信号
score_signal = (
    composite_score.rank(ascending=False) <= top_n  # Top N 入选
).unstack(level=0)

# 时政情感分析 → 信号
sentiment_signal = (
    news_sentiment > threshold   # 情感分超过阈值
).unstack(level=0)
```

**只要所有因子都吐出这种格式，回测引擎就不需要关心因子是怎么算出来的。**

你以后加时政因子，只需要写一个把新闻情感分转成 DataFrame 的函数，回测层一行代码都不用改。

**违反此原则的后果**：
- 每加一个因子，回测引擎要改接口
- 无法做因子组合回测（比如"MA 多头排列 + 三因子 Top 10"的交集策略）

---

## 原则三：回测层只做一件事——把信号矩阵变成收益矩阵

回测层的职责边界：

```
输入:  signal_df  (date × fund_code, values = True/False or float weight)
       nav_df      (date × fund_code, values = 净值)

输出:  performance  (dict of metrics: 总收益率、年化收益率、夏普比率、最大回撤、胜率...)
       equity_curve  (Series: 日期 → 累计净值)
       drawdown_curve (Series: 日期 → 回撤百分比)
```

**回测层不做的事**：
- 不做因子计算（那是因子层的活）
- 不做数据清洗（数据源和 storage.py 负责）
- 不做报告生成（reporter.py 负责）

**回测层做的唯一一件事**：

> 对于每一天，根据信号矩阵决定持仓，根据净值矩阵计算当日收益，累计得到权益曲线，再算出绩效指标。

```python
# 伪代码
for date in signal_df.index:
    holdings = signal_df.loc[date]  # 当日持仓信号
    daily_return = (
        (nav_df.loc[date] - nav_df.loc[prev_date]) / nav_df.loc[prev_date]
        * holdings                      # 只有信号为 True 的基金才有收益贡献
    ).sum()                             # 当日组合收益
    equity *= (1 + daily_return)
```

**违反此原则的后果**：
- 回测引擎变成大泥球，职责边界模糊
- 因子改动导致回测逻辑也要改，测试覆盖困难
- 无法独立验证回测引擎的正确性（回测结果错了，是因子问题还是回测逻辑问题？分不清楚）

---

## 三条原则的关系图

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   数据源     │────▶│   数据清洗   │────▶│   因子层    │
│ (storage.py)│     │ (storage.py)│     │ (factor.py) │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                                               │ signal_df
                                               ▼
                                        ┌─────────────┐
                                        │   策略层    │
                                        │(strategy.py)│
                                        └──────┬──────┘
                                               │
                                               │ 交易规则
                                               ▼
                                        ┌─────────────┐
                                        │   回测层    │
                                        │(backtest.py)│
                                        └──────┬──────┘
                                               │
                                               │ 绩效指标
                                               ▼
                                        ┌─────────────┐
                                        │  报告/展示   │
                                        │(reporter.py)│
                                        └─────────────┘
```

**数据流向**：数据源 → 清洗 → 因子 → 信号 → 策略 → 回测 → 报告

**每层只依赖下一层的输出格式，不关心实现细节。**

---

## 对现有代码的影响

| 现有模块 | 在新架构中的位置 | 需要改动 |
|----------|------------------|----------|
| `screener.py` (MA 筛选) | 因子层：MA 因子 | 输出格式改为 signal_df |
| `scoring.py` (三因子打分) | 因子层：Composite 因子 | 输出格式改为 signal_df |
| `risk_metrics.py` | 因子层内部工具 | 无需改动，继续被因子调用 |
| `analytics.py` | 因子层：动量扫描、相关性 | 输出格式改为 signal_df |
| 新增 `backtest.py` | 回测层 | 全新实现，纯 signal_df → 绩效指标 |
| 新增 `strategy.py` | 策略层 | 全新实现，signal_df + 规则 → 交易记录 |
| `reporter.py` | 报告层 | 接收回测输出，生成报告 |

---

*Created: 2026-04-19 | Applies to: Phase 3 回测引擎及后续所有量化模块*
