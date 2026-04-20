# Phase 3 回测引擎 — 详细设计方案

> 创建日期: 2026-04-20
> 对应架构原则: `.planning/ARCHITECTURE.md`（因子/策略/回测三层解耦）
> 状态: 设计冻结，等待执行

---

## 一、设计决策摘要

以下 5 个关键问题已在讨论中确认，本方案据此展开。

| # | 问题 | 选择 | 理由 |
|---|------|------|------|
| 1 | 回测引擎：手写 vs vectorbt | **vectorbt v1** | `Portfolio.from_orders(size_type='targetpercent')` 用 Numba 在 C 级别处理资金管理、再平衡、订单生成，消灭手算资金分配最易出错的环节 |
| 2 | nav_panel NaN 处理 | **方案 C** — ffill + 上市后才开始算 | 保持宽表格式（因子层可矩阵运算），每只基金上市前用 NaN（不参与），上市后缺失用 ffill，回测引擎遇到 NaN 跳过 |
| 3 | adj_nav 回填 vs 回测框架 | **并行推进** | 框架逻辑和回填逻辑零耦合，框架先用现有 nav 验证，回填跑完后切 adj_nav 只需改数据源一行 |
| 4 | 现有 screener/scoring 处理 | **方案 B** — 新增因子层 + 兼容层 | 前端 API 已稳定运行，不改现有 `ScreenResult`/`ScoredFund` 返回格式。回测引擎走新因子层，现有 CLI/API 不受影响 |
| 5 | kind='weight' 第一阶段支持 | **不支持，预留接口** | 导入公开持仓做跟投回测是未来拓展，Phase 3 核心是验证 MA + 三因子的有效性 |

---

## 二、目录结构

```
fund_screener/
│
├── __init__.py
├── cache.py                  # 已有 — 文件缓存
├── cli.py                    # 已有 — CLI 入口（新增 backtest 子命令）
├── config.py                 # 已有 — 配置加载
├── models.py                 # 已有 — Pydantic 模型
├── reporter.py               # 已有 — Markdown 报告
├── risk_metrics.py           # 已有 — 三因子纯函数（不动）
├── screener.py               # 已有 — MA 筛选（保留，兼容层）
├── scoring.py                # 已有 — 三因子打分（保留，兼容层）
├── storage.py                # 已有 — 数据湖（新增 load_nav_panel 方法）
│
├── factors/                  # 【新增】因子层
│   ├── __init__.py
│   ├── base.py               # BaseFactor + FactorOutput 抽象契约
│   ├── technical.py          # MACrossFactor（MA 多头排列信号）
│   ├── quant.py              # MomentumFactor / SharpeFactor / DrawdownFactor
│   └── composite.py          # CompositeFactor（多因子加权，Z-Score 标准化）
│
├── backtest/                 # 【新增】回测层
│   ├── __init__.py
│   ├── engine.py             # BacktestEngine：signal_df × nav_df → 绩效
│   ├── config.py             # BacktestConfig（dataclass）
│   └── result.py             # BacktestResult（净值曲线、回撤、指标、序列化）
│
├── api/
│   ├── main.py               # 已有 — FastAPI 入口（注册 backtest 路由）
│   ├── deps.py               # 已有 — 依赖注入
│   ├── schemas.py            # 已有 — Pydantic schemas（新增回测相关）
│   └── routes/
│       ├── __init__.py
│       ├── backtest.py       # 【新增】POST /api/backtest/run
│       ├── chart.py          # 已有
│       ├── funds.py          # 已有
│       ├── health.py         # 已有
│       ├── screening.py      # 已有
│       └── stats.py          # 已有
│
└── scripts/                  # 【新增】独立运行脚本
    └── backfill_adj_nav.py   # adj_nav 历史回填脚本（独立进程，可断点续传）
```

---

## 三、核心抽象层：factors/base.py

### 3.1 设计意图（修改前必须输出）

**为什么引入 BaseFactor 抽象基类？**

现有 `screener.py` 和 `scoring.py` 的计算逻辑是面向"单只基金"的：输入一个 nav_df，输出一个 ScreenResult 或 RiskMetrics。这很好，因为 CLI 筛选就是逐只基金处理的。

但回测需要"全量基金面板"视角：给定一个日期范围，同时观察几百只基金的净值变化。如果每个因子都自己从 DB 读数据、自己做对齐，代码会重复、慢、且容易出错。

**BaseFactor 的职责**：
- 统一输入：所有因子接受同一种 `nav_panel: pd.DataFrame`（宽表，index=date, columns=fund_code）
- 统一输出：所有因子吐出同一种 `FactorOutput`（values DataFrame + kind + 元信息）
- 隔离实现：因子内部怎么算（rolling mean / pct_change / 读外部数据）不关心，只要最终格式对就行

### 3.2 代码定义

```python
# factors/base.py
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

import pandas as pd


@dataclass(frozen=True)
class FactorOutput:
    """
    所有因子的统一输出格式 —— 因子层和回测层之间的唯一契约。

    对应 ARCHITECTURE.md 原则二：信号（Signal）是因子和回测之间的唯一契约。
    """
    # 核心：宽表 DataFrame，index=date, columns=fund_code
    values: pd.DataFrame

    # 因子的性质，决定它在回测里怎么被使用
    # - 'signal': 布尔值，True=持有，False=空仓（如 MA 多头排列）
    # - 'score':  连续值，越大越好（如夏普比率，用于排序选 Top N）
    # - 'weight': 权重值，sum<=1（如别人的持仓表，直接作为持仓权重）
    kind: Literal["signal", "score", "weight"]

    # 元信息
    name: str
    description: str = ""


class BaseFactor(ABC):
    """
    所有因子的抽象基类。

    子类必须实现 compute() 方法。因子层不做任何 I/O（不读 DB、不调 API），
    所有外部数据通过 nav_panel 和 **context 传入。
    """

    @abstractmethod
    def compute(
        self,
        nav_panel: pd.DataFrame,  # index=date, columns=fund_code
        **context,                # 预留给需要额外数据的因子（如新闻、持仓）
    ) -> FactorOutput:
        """
        核心方法：输入净值面板，输出因子值。

        Args:
            nav_panel: 宽表 DataFrame，index 为日期（DatetimeIndex，日频），
                       columns 为基金代码，values 为净值（已处理 NaN，见 §5）
            **context: 额外上下文数据。例如：
                       - context['news_df']: 新闻情感分面板（后期时政因子用）
                       - context['holdings_df']: 持仓权重面板（后期 weight 因子用）

        Returns:
            FactorOutput，values 的 shape 必须与 nav_panel 完全一致
            （相同的 index 和 columns，允许 values 中有 NaN）
        """
        ...

    def __add__(self, other: "BaseFactor") -> "CompositeFactor":
        """
        语法糖：factor_a + factor_b → CompositeFactor

        注意：只有 kind='score' 的因子可以用 + 组合。
        CompositeFactor 的实现见 factors/composite.py。
        """
        from .composite import CompositeFactor
        return CompositeFactor([self, other])
```

### 3.3 关键约束

| 约束 | 说明 |
|------|------|
| `values.shape == nav_panel.shape` | 输出 DataFrame 的 index/columns 必须与输入完全一致 |
| NaN 允许 | 输出中可以有 NaN（某基金某天无数据），回测层会跳过 |
| 不做 I/O | 因子类不读 DB、不调 API，纯矩阵运算 |
| kind 决定用途 | `signal` 用于过滤候选池，`score` 用于排序选 Top N，`weight` 用于直接权重（预留） |

---

## 四、具体因子实现

### 4.1 MACrossFactor — 技术面信号因子（kind='signal'）

```python
# factors/technical.py
import pandas as pd
from .base import BaseFactor, FactorOutput


class MACrossFactor(BaseFactor):
    """
    MA 短期均线 > 长期均线时产生持有信号。

    对应现有 screener.py:screen_fund() 的核心逻辑，但改为面板级运算。
    """

    def __init__(self, short: int = 20, long: int = 60):
        self.short = short
        self.long = long
        self.name = f"ma_cross_{short}_{long}"

    def compute(self, nav_panel: pd.DataFrame, **context) -> FactorOutput:
        # 宽表矩阵运算：一次性算完所有基金的 MA
        fast = nav_panel.rolling(window=self.short, min_periods=self.short).mean()
        slow = nav_panel.rolling(window=self.long, min_periods=self.long).mean()

        # 信号矩阵：True = MA_short > MA_long（多头排列）
        signal = fast > slow

        # 前 `long` 天数据不足，强制置 False（不可交易）
        signal.iloc[: self.long] = False

        # NaN 位置（基金未上市或数据缺失）置 False
        signal = signal.where(nav_panel.notna(), False)

        return FactorOutput(
            values=signal,
            kind="signal",
            name=self.name,
            description=f"MA{self.short} 上穿 MA{self.long} 多头排列信号",
        )
```

**与现有代码的关系**：
- 现有 `screener.py:calculate_ma()` 和 `screen_fund()` 保留不动，继续给 CLI 和 API 用
- `MACrossFactor` 是同一逻辑的面板级重写，面向回测场景

### 4.2 量化因子 — kind='score'

```python
# factors/quant.py
import numpy as np
import pandas as pd
from .base import BaseFactor, FactorOutput


class MomentumFactor(BaseFactor):
    """趋势爆发力 = (latest_nav - MA20) / MA20，滚动计算。"""

    def __init__(self, ma_period: int = 20):
        self.ma_period = ma_period
        self.name = f"momentum_ma{ma_period}"

    def compute(self, nav_panel: pd.DataFrame, **context) -> FactorOutput:
        ma = nav_panel.rolling(window=self.ma_period, min_periods=self.ma_period).mean()
        momentum = (nav_panel - ma) / ma
        return FactorOutput(
            values=momentum,
            kind="score",
            name=self.name,
            description=f"偏离 MA{self.ma_period} 的幅度（越大 = 冲劲越足）",
        )


class SharpeFactor(BaseFactor):
    """滚动年化夏普比率。"""

    def __init__(self, lookback: int = 252, rf_annual: float = 0.02):
        self.lookback = lookback
        self.rf = rf_annual / 252  # 日无风险利率
        self.name = f"sharpe_{lookback}"

    def compute(self, nav_panel: pd.DataFrame, **context) -> FactorOutput:
        returns = nav_panel.pct_change()
        excess = returns - self.rf

        rolling_mean = excess.rolling(window=self.lookback, min_periods=self.lookback).mean()
        rolling_std = excess.rolling(window=self.lookback, min_periods=self.lookback).std(ddof=1)

        sharpe = (rolling_mean / rolling_std) * np.sqrt(252)

        return FactorOutput(
            values=sharpe,
            kind="score",
            name=self.name,
            description=f"{self.lookback} 日滚动年化夏普比率",
        )


class MaxDrawdownFactor(BaseFactor):
    """
    滚动最大回撤（负数）。

    注意：返回的是负值，越接近 0 越好。
    CompositeFactor 在组合时会反转方向（乘 -1 后标准化）。
    """

    def __init__(self, lookback: int = 252):
        self.lookback = lookback
        self.name = f"max_dd_{lookback}"

    def compute(self, nav_panel: pd.DataFrame, **context) -> FactorOutput:
        # 滚动窗口计算最大回撤
        # pandas 没有直接 rolling().apply() 支持 cummax，需要逐列处理
        def _rolling_max_dd(series: pd.Series) -> pd.Series:
            """对单只基金计算滚动最大回撤。"""
            result = pd.Series(index=series.index, dtype=float)
            for i in range(len(series)):
                if i < 2:
                    result.iloc[i] = np.nan
                    continue
                window = series.iloc[: i + 1]
                cummax = window.cummax()
                dd = (window - cummax) / cummax
                result.iloc[i] = dd.min()
            return result

        # 对每列（每只基金）应用
        dd_df = nav_panel.apply(_rolling_max_dd, axis=0)
        return FactorOutput(
            values=dd_df,
            kind="score",
            name=self.name,
            description=f"{self.lookback} 日滚动最大回撤（负数，越接近 0 越好）",
        )
```

**性能注意事项**：
- `MaxDrawdownFactor` 的滚动实现是 O(n²) 的，对于 1000 只基金 × 2000 天的面板，可能较慢
- 优化方案：用 `expanding().apply()` + `numba` 加速，或预计算全区间回撤后截断
- Phase 3 先用朴素实现，性能瓶颈出现后再优化

### 4.3 CompositeFactor — 多因子组合器

```python
# factors/composite.py
from typing import List, Optional
import pandas as pd
import numpy as np
from .base import BaseFactor, FactorOutput


class CompositeFactor(BaseFactor):
    """
    把多个 score 因子加权组合成一个综合分。

    对应现有 scoring.py:score_funds() 的 Z-Score 标准化 + 加权逻辑，
    但改为面板级运算（一次性处理所有基金、所有日期）。
    """

    def __init__(
        self,
        factors: List[BaseFactor],
        weights: Optional[List[float]] = None,
        name: str = "composite",
    ):
        assert all(f.kind == "score" for f in factors), "只有 kind='score' 的因子可以组合"
        self.factors = factors
        self.weights = weights or [1.0 / len(factors)] * len(factors)
        self.name = name

    def compute(self, nav_panel: pd.DataFrame, **context) -> FactorOutput:
        combined: Optional[pd.DataFrame] = None

        for factor, weight in zip(self.factors, self.weights):
            output = factor.compute(nav_panel, **context)
            scores = output.values

            # 横截面 Z-Score 标准化（按日期分组，每行独立标准化）
            # axis=1: 对每行（每个日期）计算 mean/std
            mean = scores.mean(axis=1)
            std = scores.std(axis=1, ddof=1)

            # std == 0 的日期 → Z-Score 全 0（该日因子不贡献分数）
            z = scores.sub(mean, axis=0).div(std.replace(0, np.nan), axis=0).fillna(0)

            if combined is None:
                combined = z * weight
            else:
                combined = combined + z * weight

        return FactorOutput(
            values=combined,
            kind="score",
            name=self.name,
            description=f"{len(self.factors)} 因子加权组合（权重: {self.weights}）",
        )
```

**与现有代码的关系**：
- 现有 `scoring.py:_compute_z_scores()` 是"列表级"Z-Score（对一组数值）
- `CompositeFactor` 是"面板级"Z-Score（对 DataFrame 的每行），语义一致但维度升级

---

## 五、nav_panel 宽表加载策略

### 5.1 为什么宽表有 NaN

```
              fund_A   fund_B   fund_C   fund_D
2015-01-05    1.000    NaN      NaN      NaN     ← fund_B/C/D 还未上市
2015-01-06    1.001    NaN      NaN      NaN
...
2020-03-02    1.523    1.100    NaN      NaN     ← fund_C 还未上市
2020-03-03    1.520    1.102    NaN      NaN
...
2023-06-01    1.800    1.500    1.200    NaN     ← fund_D 还未上市
2023-06-02    NaN      1.502    1.205    NaN     ← fund_A 停牌一天
2023-06-05    1.805    1.501    1.203    1.000   ← fund_D 上市
```

### 5.2 处理策略（方案 C：ffill + 上市后才开始算）

**Step 1: 从数据湖加载**

```python
# storage.py 新增方法
def load_nav_panel(
    self,
    market: str,
    start_date: str,
    end_date: str,
    use_adj_nav: bool = False,  # Phase 3 先 False，回填完成后切 True
) -> pd.DataFrame:
    """
    加载指定市场的净值宽表。

    Returns:
        DataFrame: index=date(DatetimeIndex), columns=fund_code, values=净值
    """
    nav_col = "adj_nav" if use_adj_nav else "nav"

    query = f"""
    SELECT f.code, nr.date, COALESCE(nr.{nav_col}, nr.nav) as effective_nav
    FROM nav_records nr
    JOIN funds f ON nr.fund_id = f.id
    WHERE f.market = ?
      AND nr.date BETWEEN ? AND ?
    ORDER BY nr.date ASC
    """

    df = pd.read_sql_query(
        query, self._conn, params=(market, start_date, end_date)
    )

    # 转成宽表：index=date, columns=fund_code
    df["date"] = pd.to_datetime(df["date"])
    panel = df.pivot(index="date", columns="code", values="effective_nav")

    # ffill：填充停牌等短期缺失（最多连续 5 天）
    panel = panel.ffill(limit=5)

    return panel
```

**Step 2: 因子层处理 NaN**

- `MACrossFactor`：NaN 位置置 False（不可交易）
- `MomentumFactor` / `SharpeFactor`：rolling 运算天然跳过 NaN
- `CompositeFactor`：Z-Score 计算时 NaN 不参与 mean/std

**Step 3: 回测层处理 NaN**

```python
# backtest/engine.py
# vectorbt 的 from_orders 会自动处理 close 中的 NaN（不下单）
# 但我们显式确保 target_weights 中 NaN = 不下单
```

### 5.3 基准加载

回测需要基准对比（如沪深300）。基准也走同样的 `load_nav_panel` 逻辑，只是 market 传特殊值或单独方法。

```python
def load_benchmark(
    self,
    benchmark_code: str,  # e.g., "000300.SH"
    start_date: str,
    end_date: str,
) -> pd.Series:
    """加载单只基准指数的净值序列。"""
```

---

## 六、回测引擎设计（vectorbt v1 集成）

### 6.1 设计意图（修改前必须输出）

回测引擎的职责只有一个：把信号矩阵变成收益矩阵。对应 ARCHITECTURE.md 原则三。

**为什么用 vectorbt v1 的 `Portfolio.from_orders(size_type='targetpercent')`？**

组合回测中最容易出错的环节不是"算收益率"，而是"资金管理"：
- 今天信号说买 A 和 B，各 50% 权重
- 但昨天 A 涨了 10%，B 跌了 5%，实际仓位已经偏了
- 再平衡时怎么算？卖掉一部分 A、买一部分 B，还是只调差额？
- 如果现金不够买齐怎么办？如果某只基金停牌怎么办？

`from_orders(size_type='targetpercent')` 在底层用 Numba 写了完整的资金分配逻辑：
- 每天检查目标权重 vs 实际权重
- 计算需要买卖的份额
- 处理现金不足、停牌、价格缺失等边界
- 自动扣除手续费

**我们只用 vectorbt 的这一件事**：生成组合净值曲线和绩效指标。因子计算全用 pandas。

### 6.2 BacktestConfig

```python
# backtest/config.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from fund_screener.factors.base import BaseFactor


@dataclass(frozen=True)
class BacktestConfig:
    """
    回测配置 —— 所有可调整参数的集中定义。

     frozen=True 保证配置对象不可变，避免回测过程中被意外修改。
    """

    # 组合构建规则
    top_n: int = 10
    rebalance_freq: str = "ME"  # pandas offset alias: ME=月末, W-FRI=周五, QE=季末
    weighting: Literal["equal", "score"] = "equal"

    # 交易成本
    fee_rate: float = 0.0015  # 申购费率（一折后约 0.15%）

    # 初始资金
    init_cash: float = 1_000_000.0

    # 信号过滤（可选）— 必须是 kind='signal' 的因子
    # 例如：MACrossFactor(20, 60) 表示"只在 MA 多头排列的基金中选"
    signal_filter: Optional[BaseFactor] = None

    # 基准
    benchmark_code: Optional[str] = "000300.SH"

    # 数据列选择
    use_adj_nav: bool = False  # Phase 3 先 False，回填完成后切 True
```

### 6.3 BacktestEngine

```python
# backtest/engine.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
import vectorbt as vbt

from fund_screener.factors.base import BaseFactor, FactorOutput
from .config import BacktestConfig


class BacktestEngine:
    """
    基于 vectorbt v1 的回测引擎。

    职责边界（ARCHITECTURE.md 原则三）：
    - 做：signal_df × nav_df → 组合净值 → 绩效指标
    - 不做：因子计算（因子层）、数据清洗（storage.py）、报告生成（reporter.py）
    """

    def __init__(self, nav_panel: pd.DataFrame, config: BacktestConfig):
        self.nav_panel = nav_panel
        self.config = config

    def run(self, score_factor: BaseFactor, context: Optional[dict] = None) -> "BacktestResult":
        """
        执行回测。

        Args:
            score_factor: 用于打分选 Top N 的因子（kind='score'）
            context: 额外数据，传给因子的 compute()

        Returns:
            BacktestResult，包含净值曲线、回撤、绩效指标、调仓历史
        """
        context = context or {}

        # Step 1: 计算打分因子（面板级运算，一次性算完所有日期、所有基金）
        score_output = score_factor.compute(self.nav_panel, **context)
        scores = score_output.values  # DataFrame: date × fund_code

        # Step 2: 应用 signal 过滤（如 MA 多头排列）
        if self.config.signal_filter:
            filter_output = self.config.signal_filter.compute(self.nav_panel, **context)
            # 被过滤掉的基金：分数设为 -inf（永远选不上）
            scores = scores.where(filter_output.values, other=-np.inf)

        # Step 3: 构建目标持仓权重矩阵
        target_weights = self._build_target_weights(scores)

        # Step 4: 用 vectorbt 跑回测
        # size_type='targetpercent' 是关键：每天按目标权重百分比调整持仓
        pf = vbt.Portfolio.from_orders(
            close=self.nav_panel,
            size=target_weights,
            size_type="targetpercent",
            fees=self.config.fee_rate,
            init_cash=self.config.init_cash,
            cash_sharing=True,   # 所有基金共享一个现金池
            group_by=True,       # 作为一个组合整体回测
            freq="1D",
        )

        return BacktestResult(
            portfolio=pf,
            target_weights=target_weights,
            score_factor_name=score_factor.name,
            config=self.config,
        )

    def _build_target_weights(self, scores: pd.DataFrame) -> pd.DataFrame:
        """
        把打分矩阵变成目标持仓权重矩阵。

        核心逻辑：
        1. 确定调仓日（按 rebalance_freq）
        2. 每个调仓日，选当前分数最高的 Top N
        3. 根据 weighting 策略分配权重
        4. 非调仓日：NaN（vbt 会忽略，保持当前持仓不变）
        5. 被 signal 过滤掉的：从候选池剔除

        Returns:
            DataFrame: index=date, columns=fund_code, values=目标权重(0~1) 或 NaN
        """
        # 生成调仓日（每月最后一个交易日）
        rebalance_dates = scores.resample(self.config.rebalance_freq).last().index
        rebalance_dates = rebalance_dates.intersection(scores.index)

        # 初始化权重矩阵（全 NaN = 不下单 = 保持当前持仓）
        weights = pd.DataFrame(np.nan, index=scores.index, columns=scores.columns)

        for dt in rebalance_dates:
            row = scores.loc[dt]

            # 选 Top N（排除 -inf）
            valid_scores = row[row > -np.inf]
            top_funds = valid_scores.nlargest(self.config.top_n)

            if len(top_funds) == 0:
                # 空仓：所有基金权重设为 0
                weights.loc[dt] = 0.0
                continue

            if self.config.weighting == "equal":
                # 等权
                w = 1.0 / len(top_funds)
                weights.loc[dt, top_funds.index] = w
                # 其他基金显式设为 0（触发卖出）
                others = weights.columns.difference(top_funds.index)
                weights.loc[dt, others] = 0.0

            elif self.config.weighting == "score":
                # 按分数加权
                # 先处理负数：shift 到全正（min-max 归一化后加权）
                min_score = top_funds.min()
                shifted = top_funds - min_score + 1e-6  # 避免全 0
                normalized = shifted / shifted.sum()
                weights.loc[dt, normalized.index] = normalized.values
                others = weights.columns.difference(normalized.index)
                weights.loc[dt, others] = 0.0

        return weights
```

### 6.4 BacktestResult

```python
# backtest/result.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import vectorbt as vbt

from .config import BacktestConfig


@dataclass
class BacktestResult:
    """
    回测结果 —— 包含 vectorbt Portfolio 对象和衍生数据。

    注意：Portfolio 对象不可 JSON 序列化，to_api_response() 负责提取可序列化的数据。
    """

    portfolio: vbt.Portfolio
    target_weights: pd.DataFrame
    score_factor_name: str
    config: BacktestConfig

    # ------------------------------------------------------------------
    # 核心指标（直接委托给 vectorbt）
    # ------------------------------------------------------------------

    def stats(self) -> pd.Series:
        """标准绩效指标（总收益、年化收益、夏普、最大回撤、胜率等）。"""
        return self.portfolio.stats()

    def equity_curve(self) -> pd.Series:
        """组合净值曲线（每日组合总价值）。"""
        return self.portfolio.value()

    def drawdown_curve(self) -> pd.Series:
        """回撤曲线（每日相对历史高点的跌幅）。"""
        return self.portfolio.drawdown()

    def returns(self) -> pd.Series:
        """日收益率序列。"""
        return self.portfolio.returns()

    # ------------------------------------------------------------------
    # 调仓历史（供前端展示）
    # ------------------------------------------------------------------

    def rebalance_history(self) -> list[dict[str, Any]]:
        """
        历次调仓的持仓明细。

        Returns:
            [{'date': '2020-01-31', 'holdings': {'510300': 0.1, '510500': 0.1, ...}}, ...]
        """
        rebal = self.target_weights.dropna(how="all")
        return [
            {"date": str(idx.date()), "holdings": row[row > 0].round(4).to_dict()}
            for idx, row in rebal.iterrows()
        ]

    # ------------------------------------------------------------------
    # 序列化（供 API 返回）
    # ------------------------------------------------------------------

    def to_api_response(self) -> dict[str, Any]:
        """
        序列化为前端可用的字典。

        注意：
        - equity_curve 和 drawdown 可能很长（几千个点），前端可能只需要抽样
        - 这里返回全量，前端按自己的抽样策略处理
        """
        stats = self.stats()

        # equity_curve: { '2020-01-02': 1000000.0, '2020-01-03': 1001200.0, ... }
        equity = self.equity_curve()
        equity_dict = {
            str(k.date()): round(v, 2)
            for k, v in equity.items()
            if pd.notna(v)
        }

        # drawdown: 同上格式
        dd = self.drawdown_curve()
        dd_dict = {
            str(k.date()): round(v * 100, 4)  # 转百分比
            for k, v in dd.items()
            if pd.notna(v)
        }

        return {
            "factor_name": self.score_factor_name,
            "config": {
                "top_n": self.config.top_n,
                "rebalance_freq": self.config.rebalance_freq,
                "weighting": self.config.weighting,
                "fee_rate": self.config.fee_rate,
                "init_cash": self.config.init_cash,
                "signal_filter": self.config.signal_filter.name if self.config.signal_filter else None,
            },
            "stats": {
                "total_return": float(stats.get("Total Return [%]", 0)),
                "annual_return": float(stats.get("Annual Return [%]", 0)),
                "sharpe_ratio": float(stats.get("Sharpe Ratio", 0)),
                "max_drawdown": float(stats.get("Max Drawdown [%]", 0)),
                "win_rate": float(stats.get("Win Rate [%]", 0)),
                "avg_win": float(stats.get("Avg Winning Trade [%]", 0)),
                "avg_loss": float(stats.get("Avg Losing Trade [%]", 0)),
                "profit_factor": float(stats.get("Profit Factor", 0)),
                "total_trades": int(stats.get("Total Trades", 0)),
            },
            "equity_curve": equity_dict,
            "drawdown": dd_dict,
            "rebalance_history": self.rebalance_history(),
        }
```

### 6.5 vectorbt v1 依赖说明

```bash
# 安装
uv add vectorbt

# 注意：vectorbt 依赖 numba，第一次安装可能编译几分钟
# 如果编译失败，尝试先装 llvmlite：uv add llvmlite
```

**我们只用 vectorbt 的以下 API**：
- `vbt.Portfolio.from_orders()` — 核心回测
- `portfolio.stats()` — 绩效指标
- `portfolio.value()` — 净值曲线
- `portfolio.drawdown()` — 回撤曲线
- `portfolio.returns()` — 日收益率

**不用的功能**：
- Plotly 图表（我们用 TradingView Lightweight Charts）
- 参数扫描（`vbt.Portfolio.from_orders().params`）— Phase 3 不做
- Walk-Forward 优化 — Phase 3 不做，Phase 4/5 考虑

---

## 七、与现有代码的兼容策略

### 7.1 现有模块不受影响

| 模块 | 处理方式 | 理由 |
|------|----------|------|
| `screener.py` | **不改动** | CLI 默认命令和 `/api/screening` 继续用 `ScreenResult` |
| `scoring.py` | **不改动** | CLI `score` 子命令和前端打分展示继续用 `ScoredFund` |
| `risk_metrics.py` | **不改动** | 三因子纯函数被 `factors/quant.py` 和 `scoring.py` 同时复用 |
| `models.py` | **新增模型，不改现有** | 新增 `BacktestRequest` / `BacktestResponse` schemas |
| `api/routes/*.py` | **不改动** | 现有 5 个端点不受影响 |

### 7.2 新增模块独立运行

```
新模块（factors/ + backtest/） ←── 完全独立 ──→ 现有模块（screener/ + scoring/）
              │                                      │
              └─────── 共用 ─────┬─────── 共用 ─────┘
                                 │
                    risk_metrics.py（三因子纯函数）
                    storage.py（数据湖，新增 load_nav_panel）
                    models.py（新增 schema）
```

### 7.3 未来迁移路径

当新因子层稳定后，可以考虑让 `screener.py` 和 `scoring.py` 内部调用 `factors/` 的类，消除代码重复。但这不是 Phase 3 的目标。

---

## 八、API 层设计

### 8.1 新增端点

```python
# api/routes/backtest.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from fund_screener.api.deps import get_db
from fund_screener.backtest.config import BacktestConfig
from fund_screener.backtest.engine import BacktestEngine
from fund_screener.factors.composite import CompositeFactor
from fund_screener.factors.quant import DrawdownFactor, MomentumFactor, SharpeFactor
from fund_screener.factors.technical import MACrossFactor
from fund_screener.storage import DataStore

router = APIRouter(prefix="/api/backtest")


class BacktestRequest(BaseModel):
    """回测请求参数"""

    # 因子选择
    score_factor: str = Field(default="three_factor", description="打分因子: three_factor | momentum | sharpe | drawdown")
    score_weights: dict[str, float] | None = Field(default=None, description="组合因子的权重覆盖")
    signal_filter: str | None = Field(default="ma_cross_20_60", description="信号过滤: ma_cross_20_60 | null")

    # 回测参数
    top_n: int = Field(default=10, ge=1, le=50)
    rebalance_freq: str = Field(default="ME", description="调仓频率: ME=月末, W-FRI=周五, QE=季末")
    weighting: str = Field(default="equal", description="权重分配: equal | score")
    fee_rate: float = Field(default=0.0015, ge=0, le=0.1)

    # 时间范围
    start_date: str = Field(..., description="回测开始日期 YYYY-MM-DD")
    end_date: str = Field(..., description="回测结束日期 YYYY-MM-DD")
    market: str = Field(default="cn", description="市场: cn | us | hk")


class BacktestResponse(BaseModel):
    """回测响应"""

    success: bool = True
    data: dict | None = None
    error: str | None = None


# 因子注册表（静态配置，后期可扩展为动态注册）
_FACTOR_REGISTRY: dict[str, type] = {
    "ma_cross_20_60": lambda: MACrossFactor(20, 60),
    "momentum": lambda: MomentumFactor(20),
    "sharpe": lambda: SharpeFactor(252),
    "drawdown": lambda: MaxDrawdownFactor(252),
    "three_factor": lambda: CompositeFactor(
        factors=[MomentumFactor(), SharpeFactor(), MaxDrawdownFactor()],
        weights=[0.4, 0.25, 0.35],
        name="three_factor",
    ),
}


@router.post("/run", response_model=BacktestResponse)
def run_backtest(req: BacktestRequest, store: DataStore = Depends(get_db)):
    """
    执行回测并返回结果。

    流程：
    1. 从因子注册表查找因子实例
    2. 从数据湖加载净值面板
    3. 构建 BacktestConfig 和 BacktestEngine
    4. 执行回测 → 序列化 → 返回
    """
    # 1. 查找打分因子
    if req.score_factor not in _FACTOR_REGISTRY:
        raise HTTPException(status_code=400, detail=f"未知因子: {req.score_factor}")
    score_factor = _FACTOR_REGISTRY[req.score_factor]()

    # 2. 查找信号过滤因子
    signal_filter = None
    if req.signal_filter and req.signal_filter in _FACTOR_REGISTRY:
        signal_filter = _FACTOR_REGISTRY[req.signal_filter]()

    # 3. 加载数据
    nav_panel = store.load_nav_panel(
        market=req.market,
        start_date=req.start_date,
        end_date=req.end_date,
        use_adj_nav=False,  # Phase 3 先用普通 nav
    )

    if nav_panel.empty:
        return BacktestResponse(success=False, error="指定时间范围内无数据")

    # 4. 构建配置和引擎
    config = BacktestConfig(
        top_n=req.top_n,
        rebalance_freq=req.rebalance_freq,
        weighting=req.weighting,  # type: ignore
        fee_rate=req.fee_rate,
        signal_filter=signal_filter,
    )
    engine = BacktestEngine(nav_panel, config)

    # 5. 执行回测
    result = engine.run(score_factor)

    # 6. 返回
    return BacktestResponse(data=result.to_api_response())
```

### 8.2 请求示例

```bash
curl -X POST http://localhost:8000/api/backtest/run \
  -H "Content-Type: application/json" \
  -d '{
    "score_factor": "three_factor",
    "signal_filter": "ma_cross_20_60",
    "top_n": 10,
    "rebalance_freq": "ME",
    "weighting": "equal",
    "fee_rate": 0.0015,
    "start_date": "2020-01-01",
    "end_date": "2025-12-31",
    "market": "cn"
  }'
```

### 8.3 响应示例

```json
{
  "success": true,
  "data": {
    "factor_name": "three_factor",
    "config": {
      "top_n": 10,
      "rebalance_freq": "ME",
      "weighting": "equal",
      "fee_rate": 0.0015,
      "init_cash": 1000000,
      "signal_filter": "ma_cross_20_60"
    },
    "stats": {
      "total_return": 45.23,
      "annual_return": 7.68,
      "sharpe_ratio": 0.82,
      "max_drawdown": -18.45,
      "win_rate": 58.3,
      "total_trades": 72
    },
    "equity_curve": {
      "2020-01-02": 1000000.0,
      "2020-01-03": 1000150.5,
      "...": "..."
    },
    "drawdown": {
      "2020-01-02": 0.0,
      "2020-03-18": -12.34,
      "...": "..."
    },
    "rebalance_history": [
      {
        "date": "2020-01-31",
        "holdings": { "510300": 0.1, "510500": 0.1, "...": "..." }
      }
    ]
  }
}
```

---

## 九、CLI 子命令设计

```python
# cli.py 新增子命令

@click.command()
@click.option("--strategy", default="three_factor", help="打分因子")
@click.option("--signal", default="ma_cross_20_60", help="信号过滤因子")
@click.option("--start-date", required=True, help="开始日期 YYYY-MM-DD")
@click.option("--end-date", required=True, help="结束日期 YYYY-MM-DD")
@click.option("--market", default="cn", help="市场: cn/us/hk")
@click.option("--top-n", default=10, help="持仓数量")
@click.option("--rebalance", default="ME", help="调仓频率")
@click.option("--output", help="输出文件路径（默认 stdout）")
def backtest(strategy, signal, start_date, end_date, market, top_n, rebalance, output):
    """执行回测并输出报告。"""
    ...
```

用法：
```bash
# 基础回测
uv run fund-screener backtest \
  --start-date 2020-01-01 \
  --end-date 2025-12-31 \
  --market cn

# 对比不同参数
uv run fund-screener backtest \
  --strategy three_factor \
  --signal ma_cross_20_60 \
  --top-n 20 \
  --rebalance QE \
  --output reports/backtest_2020_2025.md
```

---

## 十、adj_nav 历史回填脚本

### 10.1 设计意图

Schema v2 迁移时新增了 `adj_nav` 列，但旧数据的 `adj_nav` 是 NULL。回测需要用复权净值（考虑分红、拆分），否则收益率会被分红干扰。

回填脚本独立运行，不阻塞回测框架开发。

### 10.2 核心逻辑

```python
# scripts/backfill_adj_nav.py
"""
adj_nav 历史回填脚本。

策略：
1. 遍历所有基金，找出 adj_nav 为 NULL 的记录
2. 按基金分批，调 tushare/akshare 接口拉取历史复权净值
3. 用 fund_id + date 作为 key，UPDATE nav_records SET adj_nav = ?
4. 进度持久化到 SQLite（已完成的 fund_id 记录到 backfill_log 表）
5. 支持断点续传：中断后重新运行，跳过已完成的基金

限流保护：
- tushare Pro 有积分限速，需要控制并发
- akshare 无硬性限速，但礼貌性地 sleep(0.5)
"""

import sqlite3
import time
from pathlib import Path

import pandas as pd

from fund_screener.config import load_config
from fund_screener.fetchers.cn_composite import CompositeCNFetcher


def backfill_adj_nav(db_path: str, batch_size: int = 50):
    conn = sqlite3.connect(db_path)

    # 1. 找出需要回填的基金
    cursor = conn.execute("""
        SELECT DISTINCT f.id, f.market, f.code, f.name
        FROM funds f
        JOIN nav_records nr ON f.id = nr.fund_id
        WHERE nr.adj_nav IS NULL
        ORDER BY f.id
    """)
    funds_to_backfill = cursor.fetchall()

    if not funds_to_backfill:
        print("所有记录的 adj_nav 已填充，无需回填。")
        return

    print(f"需要回填 {len(funds_to_backfill)} 只基金的 adj_nav")

    # 2. 创建回填日志表（如不存在）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS backfill_log (
            fund_id INTEGER PRIMARY KEY,
            completed_at TEXT DEFAULT (datetime('now')),
            records_updated INTEGER
        )
    """)

    # 3. 逐基金回填
    fetcher = CompositeCNFetcher(load_config())

    for fund_id, market, code, name in funds_to_backfill:
        # 检查是否已完成
        done = conn.execute(
            "SELECT 1 FROM backfill_log WHERE fund_id = ?", (fund_id,)
        ).fetchone()
        if done:
            continue

        print(f"回填: {code} {name}")

        try:
            # 拉取历史复权净值（优先 tushare，fallback akshare）
            nav_df = fetcher.fetch_nav_history(code, lookback_days=9999)
            if nav_df is None or nav_df.empty:
                print(f"  跳过: 无数据")
                continue

            # 更新 adj_nav
            updated = 0
            for _, row in nav_df.iterrows():
                conn.execute(
                    "UPDATE nav_records SET adj_nav = ? WHERE fund_id = ? AND date = ?",
                    (row.get("adj_nav", row["nav"]), fund_id, row["date"]),
                )
                updated += 1

            conn.execute(
                "INSERT INTO backfill_log (fund_id, records_updated) VALUES (?, ?)",
                (fund_id, updated),
            )
            conn.commit()
            print(f"  完成: 更新 {updated} 条记录")

            time.sleep(0.5)  # 礼貌限速

        except Exception as e:
            print(f"  失败: {e}")
            conn.rollback()
            continue

    conn.close()
    print("回填完成")


if __name__ == "__main__":
    backfill_adj_nav("data/fund_data.db")
```

### 10.3 执行计划

回填脚本和回测框架**并行开发**：
- Week 1-2：写脚本，在本地小规模测试（10只基金）
- Week 2-3：全量跑回填（可能持续几天，取决于 API 限速）
- Week 3：回填完成后，回测引擎切到 `use_adj_nav=True`

---

## 十一、执行计划（4 周）

### Week 1：因子层 + 数据加载

| 任务 | 文件 | 验收标准 |
|------|------|----------|
| BaseFactor + FactorOutput 抽象 | `factors/base.py` | 能被具体因子继承，输出格式正确 |
| MACrossFactor | `factors/technical.py` | 对宽表输出布尔矩阵，前60天全 False |
| MomentumFactor / SharpeFactor / DrawdownFactor | `factors/quant.py` | 输出分数矩阵，NaN 处理正确 |
| CompositeFactor | `factors/composite.py` | 三因子组合输出与 scoring.py 结果一致（抽样验证） |
| load_nav_panel | `storage.py` | 从 CN 市场加载宽表，形状正确，ffill 生效 |
| 单元测试 | `tests/test_factors*.py` | 每个因子至少 2 个测试用例（正常 + 边界） |

### Week 2：回测引擎核心

| 任务 | 文件 | 验收标准 |
|------|------|----------|
| BacktestConfig | `backtest/config.py` | dataclass frozen=True，参数可序列化 |
| BacktestEngine | `backtest/engine.py` | 跑通第一个端到端回测（MA过滤+三因子打分+月度调仓+Top10） |
| BacktestResult | `backtest/result.py` | stats/equity_curve/drawdown 返回正确，to_api_response 可 JSON 序列化 |
| 基准对比 | `backtest/engine.py` | 同期持有沪深300的收益 vs 策略收益 |
| 单元测试 | `tests/test_backtest*.py` | 至少覆盖：等权调仓、score 加权、signal 过滤、空仓处理 |

### Week 3：API 层 + adj_nav 回填

| 任务 | 文件 | 验收标准 |
|------|------|----------|
| /api/backtest/run | `api/routes/backtest.py` | POST 请求返回完整回测结果 |
| 注册路由 | `api/main.py` | 新端点出现在 /docs |
| adj_nav 回填脚本 | `scripts/backfill_adj_nav.py` | 小规模测试通过（10只基金） |
| 全量回填 | 后台运行 | 记录进度，支持断点续传 |
| 前端对接准备 | API schema 确认 | 前端开发者（如果有）能看懂响应格式 |

### Week 4：前端回测页 + 打磨

| 任务 | 文件 | 验收标准 |
|------|------|----------|
| /backtest 路由 | `web/src/routes/backtest.tsx` | 页面可访问 |
| 配置面板 | 左侧边栏 | 可选因子、参数、时间范围 |
| 净值曲线图 | TV Charts | 策略曲线 + 基准曲线叠加 |
| 绩效卡片 | 4 个 StatsCard | 总收益、年化收益、最大回撤、夏普 |
| 调仓历史表 | 底部表格 | 每次调仓的持仓明细，可展开 |

---

## 十二、风险点与回退方案

| 风险 | 概率 | 影响 | 回退方案 |
|------|------|------|----------|
| vectorbt v1 安装失败（numba 编译问题） | 中 | 高 | 回退到手写回测引擎（~200行 pandas，risk_metrics.py 已有夏普/回撤计算） |
| vectorbt v1 API 与文档不符 | 低 | 高 | 锁定一个已知可用版本（如 `vectorbt==0.26.0`），pin 在 pyproject.toml |
| nav_panel 太大导致内存不足（1000基金×10年≈2.5M数据点，pandas 约 20MB） | 低 | 中 | 按年份分段回测，或缩减候选池（只选成立5年以上的基金） |
| akshare/tushare API 变动导致回填脚本失效 | 中 | 中 | 回填脚本独立运行，失败只记录日志不阻塞主流程；同时维护双数据源 fallback |
| 回测结果与预期差距大（策略无效） | 高 | 低 | 这不是技术风险，是策略本身的问题。通过回测发现策略无效，本身就是回测的价值 |
| 前端 TV Charts 无法同时画策略+基准两条线 | 低 | 中 | TV Charts 支持多 series，如果不行改用 ECharts 或分开两个图 |

---

## 十三、与 ARCHITECTURE.md 的对照

| 架构原则 | 本方案如何落实 |
|----------|---------------|
| **原则一：因子和策略解耦** | `factors/` 包只管算信号（`MACrossFactor` / `CompositeFactor`），`backtest/` 只管交易规则（调仓频率、Top N 选择、权重分配）。两者通过 `FactorOutput` 交互 |
| **原则二：信号是唯一契约** | 所有因子输出 `FactorOutput(values=DataFrame, kind=...)`。回测引擎不 care 因子怎么算的，只 care `values` 的 shape 和 kind |
| **原则三：回测层只做一件事** | `BacktestEngine.run()` 的输入只有 `nav_panel + score_factor + config`，输出只有 `BacktestResult`。不做因子计算、不做数据清洗、不做报告生成 |

---

*设计冻结日期: 2026-04-20*
*冻结后修改需重新走 discuss → plan → execute 流程*
