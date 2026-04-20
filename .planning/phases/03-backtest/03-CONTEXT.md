# Phase 3: 数据质量 + 回测引擎 — Context

**Gathered:** 2026-04-20
**Status:** Ready for planning
**Source:** BACKTEST_DESIGN.md (design frozen)

---

<domain>
## Phase Boundary

补齐 adj_nav 历史数据，建立回测框架验证 MA 策略有效性。

**In scope:**
- 因子层抽象（BaseFactor + 4 个具体因子）
- 回测引擎（vectorbt v1 集成）
- adj_nav 历史回填脚本
- API 端点（POST /api/backtest/run）
- 前端回测展示页（/backtest）

**Out of scope:**
- Walk-Forward 参数优化
- 多策略对比
- 实时回测
- 交易执行

**Key constraint:** 现有 CLI/API 不受影响。新增模块独立运行，通过兼容层复用现有代码。

</domain>

<decisions>
## Implementation Decisions

### Architecture
- **回测引擎：vectorbt v1** — `Portfolio.from_orders(size_type='targetpercent')` 用 Numba 在 C 级别处理资金管理/再平衡/订单生成
- **nav_panel NaN 处理：ffill + 上市后才开始算** — 保持宽表格式（因子层可矩阵运算），每只基金上市前用 NaN（不参与），上市后缺失用 ffill（limit=5），回测引擎遇到 NaN 跳过
- **adj_nav 回填与回测框架并行推进** — 两者零耦合，框架先用现有 nav 验证，回填完成后切 adj_nav 只需改数据源一行
- **新增因子层 + 兼容层** — 不改现有 `ScreenResult`/`ScoredFund` 返回格式。回测走新 `factors/` 包，现有 CLI/API 不受影响
- **暂不支持 kind='weight' 因子，但预留接口** — 导入公开持仓做跟投回测是未来拓展

### Factor Layer
- **BaseFactor 抽象基类** — 统一输入 `nav_panel: pd.DataFrame`（宽表），统一输出 `FactorOutput(values, kind, name)`
- **MACrossFactor** — kind='signal'，面板级 rolling mean 比较，前 long 天强制 False，NaN 位置置 False
- **MomentumFactor** — kind='score'，`(nav - MA20) / MA20`
- **SharpeFactor** — kind='score'，滚动年化夏普，`lookback=252, rf=0.02`
- **MaxDrawdownFactor** — kind='score'，滚动最大回撤（负数），O(n²) 朴素实现，性能瓶颈后再优化
- **CompositeFactor** — 多 score 因子 Z-Score 标准化（横截面，按日期逐行）+ 加权组合

### Backtest Engine
- **BacktestConfig** — frozen dataclass，参数：top_n, rebalance_freq, weighting, fee_rate, init_cash, signal_filter, benchmark_code, use_adj_nav
- **BacktestEngine.run()** — signal_df × nav_df → target_weights → vbt.Portfolio.from_orders → BacktestResult
- **_build_target_weights** — rebalance_freq 确定调仓日，选 Top N，等权或 score 加权，非调仓日 NaN
- **BacktestResult** — 包装 vbt.Portfolio，提供 stats()/equity_curve()/drawdown_curve()/rebalance_history()/to_api_response()

### Data Loading
- **storage.load_nav_panel()** — 新增方法，SQL → pivot → 宽表，ffill(limit=5)
- **use_adj_nav=False** — Phase 3 先用普通 nav，回填完成后切 True

### API Design
- **POST /api/backtest/run** — 请求含 score_factor, signal_filter, top_n, rebalance_freq, weighting, fee_rate, start_date, end_date, market
- **因子注册表** — 静态字典映射字符串到因子工厂函数
- **响应格式** — factor_name, config, stats, equity_curve, drawdown, rebalance_history

### adj_nav Backfill
- **独立脚本 scripts/backfill_adj_nav.py** — 不阻塞回测框架
- **断点续传** — backfill_log 表记录已完成 fund_id
- **双数据源 fallback** — tushare 优先，akshare 备用

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture
- `.planning/ARCHITECTURE.md` — 回测三层解耦原则（因子/信号/回测）
- `.planning/BACKTEST_DESIGN.md` — 完整设计方案（冻结）

### Existing Code (Must preserve)
- `src/fund_screener/screener.py` — MA 筛选逻辑（不改动）
- `src/fund_screener/scoring.py` — 三因子打分（不改动）
- `src/fund_screener/risk_metrics.py` — 三因子纯函数（复用）
- `src/fund_screener/storage.py` — 数据湖（新增 load_nav_panel）
- `src/fund_screener/api/main.py` — FastAPI 入口（注册新路由）
- `src/fund_screener/models.py` — Pydantic 模型（新增 schema）
- `src/fund_screener/cli.py` — CLI 入口（新增 backtest 子命令）
- `src/fund_screener/config.py` — 配置加载

### Requirements
- `.planning/REQUIREMENTS.md` — DATA-01~03, BACK-01~04
- `.planning/ROADMAP.md` — Phase 3 success criteria

</canonical_refs>

<specifics>
## Specific Ideas

### Performance
- MaxDrawdownFactor 的 O(n²) 实现是已知的性能瓶颈。Phase 3 先用朴素实现，1000基金×2000天面板测试后再优化（numba 或预计算）
- nav_panel 内存估算：1000基金 × 10年 × 250交易日 ≈ 2.5M 数据点 ≈ 20MB pandas DataFrame，内存充足

### Error Handling
- vectorbt v1 安装失败（numba 编译问题）→ 回退到手写回测引擎（~200行 pandas）
- 锁定 vectorbt 版本：`vectorbt==0.26.0` pin 在 pyproject.toml
- API 返回空数据时：BacktestResponse(success=False, error="...")

### Testing Strategy
- 每个因子至少 2 个测试用例（正常 + 边界：NaN / 数据不足 / std=0）
- 回测引擎至少覆盖：等权调仓 / score 加权 / signal 过滤 / 空仓
- 第一个端到端回测：MA过滤 + 三因子打分 + 月度调仓 + Top10，验证输出不为空

</specifics>

<deferred>
## Deferred Ideas

- **kind='weight' 因子** — 导入公开持仓做跟投回测（v1.1）
- **Walk-Forward 参数优化** — 多参数网格搜索（Phase 4/5）
- **多策略对比** — 同时跑多个策略，对比收益曲线（Phase 5）
- **参数扫描** — vectorbt 的 `.params` 功能（Phase 4/5）
- **前端 TV Charts 多 series** — 策略曲线 + 基准曲线叠加（Week 4）

</deferred>

---

*Phase: 03-backtest*
*Context gathered: 2026-04-20 via BACKTEST_DESIGN.md*
