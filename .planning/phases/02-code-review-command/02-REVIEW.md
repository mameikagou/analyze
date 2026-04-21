---
phase: 02-code-review-command
reviewed: 2026-04-20T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - src/fund_screener/api/routes/backtest.py
  - src/fund_screener/api/main.py
  - src/fund_screener/api/schemas.py
  - src/fund_screener/api/deps.py
  - src/fund_screener/cli.py
  - src/fund_screener/scripts/backfill_adj_nav.py
  - src/fund_screener/scripts/__init__.py
  - src/fund_screener/storage.py
  - src/fund_screener/backtest/result.py
findings:
  critical: 1
  warning: 5
  info: 3
  total: 9
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-04-20
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

本次审查覆盖 API 路由层、CLI 入口、回填脚本、数据存储层及回测结果序列化模块。整体架构设计清晰，职责分离合理，但发现 1 个 Critical 安全问题（SQL 注入风险）、5 个 Warning 级别问题（重复代码、错误处理缺陷、边界条件）和 3 个 Info 级别问题（代码风格、可维护性）。

总体评价：**flag** — 需要修复 Critical 和大部分 Warning 后才能合并。

---

## Critical Issues

### CR-01: SQL 注入风险 — `load_nav_panel` 使用 f-string 拼接 SQL 列名

**File:** `src/fund_screener/storage.py:808`
**Issue:** `load_nav_panel` 方法使用 f-string 拼接 `nav_col` 到 SQL 查询中：

```python
nav_col = "adj_nav" if use_adj_nav else "nav"
query = f"""
SELECT f.code, nr.date, COALESCE(nr.{nav_col}, nr.nav) as effective_nav
...
"""
```

虽然 `nav_col` 当前是受控字面量（只有两个合法值），但 `use_adj_nav` 参数是公开的 API 参数。如果未来有人修改这个逻辑（比如允许传入任意列名），就会直接暴露 SQL 注入漏洞。根据 PYTHON_STANDARDS.md §10 的要求，f-string 仅用于受控字面量，但这里的防御依赖于调用方不传入非法值，属于"信任边界"设计缺陷。

**Fix:**
```python
def load_nav_panel(self, market: str, start_date: str, end_date: str, use_adj_nav: bool = False) -> pd.DataFrame:
    # 严格白名单校验，防御未来代码变更引入的注入风险
    nav_col = "adj_nav" if use_adj_nav else "nav"
    allowed_cols = {"nav", "adj_nav"}
    if nav_col not in allowed_cols:
        raise ValueError(f"Invalid nav_col: {nav_col}")
    # ... 后续逻辑不变
```

**原因:** 安全防御不能依赖"当前调用方是善意的"。公开 API 的参数校验必须在最靠近用户输入的位置完成，不能假设中间层不会传恶意值。

---

## Warnings

### WR-01: Factor Registry 重复定义 — API 和 CLI 维护两份相同代码

**File:** `src/fund_screener/api/routes/backtest.py:87-97` 和 `src/fund_screener/cli.py:1129-1139`
**Issue:** `_FACTOR_REGISTRY` 在 API 路由和 CLI 子命令中各定义了一份，内容完全一致。这是明确的代码重复（Code Duplication）。当需要新增因子或修改默认权重时，必须修改两个地方，极易遗漏导致 API 和 CLI 行为不一致。

**Fix:** 将 Factor Registry 提取到 `fund_screener/factors/registry.py`（或 `fund_screener/backtest/registry.py`）：

```python
# fund_screener/backtest/registry.py
from fund_screener.factors.composite import CompositeFactor
from fund_screener.factors.quant import MaxDrawdownFactor, MomentumFactor, SharpeFactor
from fund_screener.factors.technical import MACrossFactor

_FACTOR_REGISTRY: dict[str, Callable[[], BaseFactor]] = {
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

def get_factor(name: str) -> BaseFactor:
    if name not in _FACTOR_REGISTRY:
        raise ValueError(f"Unknown factor: {name}. Available: {list(_FACTOR_REGISTRY.keys())}")
    return _FACTOR_REGISTRY[name]()

def list_factors() -> list[str]:
    return list(_FACTOR_REGISTRY.keys())
```

然后 API 和 CLI 统一导入使用。

**原因:** DRY 原则。重复代码是 bug 的温床，尤其是配置类代码。

---

### WR-02: `score_weights` 覆盖逻辑未校验权重和

**File:** `src/fund_screener/api/routes/backtest.py:132-143`
**Issue:** 当 `req.score_weights` 提供时，代码直接取三个字段的默认值拼接权重列表，但没有校验：
1. 权重之和是否为 1.0（或接近 1.0）
2. 是否传入了非法的键名
3. 权重是否为负数

这会导致 CompositeFactor 内部计算时产生非预期的结果（如权重和不为 1 时 Z-Score 加权后的分数没有可比性）。

**Fix:**
```python
if req.score_weights is not None and req.score_factor == "three_factor":
    # 校验键名
    allowed_keys = {"momentum", "sharpe", "drawdown"}
    extra_keys = set(req.score_weights.keys()) - allowed_keys
    if extra_keys:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid score_weights keys: {extra_keys}. Allowed: {allowed_keys}",
        )
    
    weights_list = [
        req.score_weights.get("momentum", 0.4),
        req.score_weights.get("sharpe", 0.25),
        req.score_weights.get("drawdown", 0.35),
    ]
    
    # 校验非负
    if any(w < 0 for w in weights_list):
        raise HTTPException(status_code=400, detail="score_weights must be non-negative")
    
    # 校验和接近 1.0（允许浮点误差）
    total = sum(weights_list)
    if not (0.99 <= total <= 1.01):
        raise HTTPException(
            status_code=400,
            detail=f"score_weights must sum to ~1.0, got {total}",
        )
    
    score_factor = CompositeFactor(...)
```

**原因:** 用户输入的权重如果不校验，会导致回测结果无意义，且问题难以排查（用户以为是策略问题，其实是参数问题）。

---

### WR-03: CLI backtest 子命令缺少 `--weighting` 参数

**File:** `src/fund_screener/cli.py:1083-1092`
**Issue:** CLI 的 `backtest` 子命令没有暴露 `--weighting` 参数，硬编码为 `"equal"`：

```python
bt_config = BacktestConfig(
    top_n=top_n,
    rebalance_freq=rebalance,
    weighting="equal",  # 硬编码，无法选择 score 加权
    ...
)
```

而 API 的 `BacktestRequest` 支持 `weighting: str = Field(default="equal", description="equal | score")`。CLI 和 API 的能力不一致，用户无法通过 CLI 测试 score 加权策略。

**Fix:** 添加 `--weighting` 选项：
```python
@click.option("--weighting", default="equal", type=click.Choice(["equal", "score"]), help="权重分配策略")
```

并传入 `BacktestConfig`。

**原因:** CLI 和 API 应该提供等价的功能集，否则用户会在两个入口间感到困惑。

---

### WR-04: `backfill_adj_nav.py` 的 `CompositeCNFetcher` 初始化方式错误

**File:** `src/fund_screener/scripts/backfill_adj_nav.py:165-166`
**Issue:** 脚本中初始化 `CompositeCNFetcher` 的方式与 CLI 中的 `_build_cn_fetcher` 不一致：

```python
# backfill_adj_nav.py:165-166
config = load_config()
fetcher = CompositeCNFetcher(config)
```

而 CLI 中 `_build_cn_fetcher` 需要传入 `cache` 和 `rate_limit_config` 等参数：
```python
providers = {"akshare": AkshareCNProvider(cache=cache, rate_limit_config=config.rate_limit, ...), ...}
return CompositeCNFetcher(cache=cache, rate_limit_config=config.rate_limit, cn_config=config.cn_fund, providers=providers)
```

`CompositeCNFetcher` 的构造函数签名（从 CLI 推断）需要 `cache` 和 `providers` 等参数，但脚本直接传 `config` 一个参数。这会导致：
1. 如果 `CompositeCNFetcher.__init__` 签名不匹配，直接运行时错误
2. 缺少 cache 层，每次请求都走网络，效率极低
3. 缺少 rate limiting 配置，可能触发 API 封禁

**Fix:**
```python
def backfill_adj_nav(db_path: str, batch_size: int = 50) -> None:
    # ...
    config = load_config()
    cache = FileCache(config.cache_dir, default_ttl_hours=config.cache_ttl_hours)
    
    # 复用 CLI 中的构建逻辑，或提取公共函数
    from fund_screener.cli import _build_cn_fetcher
    fetcher = _build_cn_fetcher(config, cache)
    # ...
```

**原因:** 脚本的 fetcher 初始化与主流程不一致，可能导致运行时错误或 API 限速问题。

---

### WR-05: `backfill_adj_nav.py` 的 `fetch_nav_history` 调用签名不匹配

**File:** `src/fund_screener/scripts/backfill_adj_nav.py:113`
**Issue:** 脚本调用 `fetcher.fetch_nav_history(code, lookback_days=9999)`，但 CLI 中调用的是 `fetcher.fetch_nav_history(code, days=config.lookback_days)`：

```python
# backfill_adj_nav.py:113
nav_df = fetcher.fetch_nav_history(code, lookback_days=9999)

# cli.py:191
nav_df = fetcher.fetch_nav_history(code, days=config.lookback_days)
```

参数名 `lookback_days` vs `days` 不一致。如果 `BaseFetcher` 接口定义的是 `days`，则脚本会抛出 `TypeError`。

**Fix:** 确认 `BaseFetcher.fetch_nav_history` 的签名，统一使用正确的参数名。如果设计文档中定义的是 `days`：
```python
nav_df = fetcher.fetch_nav_history(code, days=9999)
```

**原因:** 参数名不一致会导致运行时 TypeError，且说明接口契约没有被严格遵守。

---

## Info

### IN-01: `BacktestResponse` 与全局 `APIResponse` 重复

**File:** `src/fund_screener/api/routes/backtest.py:77-83`
**Issue:** `BacktestResponse` 的定义与 `schemas.py` 中的 `APIResponse` 完全一致：

```python
# backtest.py:77-83
class BacktestResponse(BaseModel):
    success: bool = True
    data: dict | None = None
    error: str | None = None

# schemas.py:17-22
class APIResponse(BaseModel):
    success: bool = True
    data: Any | None = None
    error: str | None = None
```

虽然文件头注释解释了为什么把 schema 放在路由文件里（自包含、降低耦合），但 `BacktestResponse` 完全可以复用 `APIResponse`，或者至少让 `BacktestResponse` 继承 `APIResponse` 并收窄 `data` 类型。

**Fix:**
```python
from fund_screener.api.schemas import APIResponse

class BacktestResponse(APIResponse):
    """Backtest 响应 —— data 字段收窄为 dict（回测结果）。"""
    data: dict | None = None
```

**原因:** 减少重复定义，同时保留类型收窄的好处。

---

### IN-02: `DataStore.from_connection()` 绕过 `__init__` 可能引入状态不一致

**File:** `src/fund_screener/storage.py:250-271`
**Issue:** `from_connection` 使用 `cls.__new__(cls)` 绕过 `__init__`，手动设置实例属性。虽然当前实现正确，但这种模式有几个隐患：

1. 如果 `__init__` 未来增加了新的实例属性（如 `_transaction_count`），`from_connection` 不会自动同步
2. `_db_path = Path(":memory:")` 的语义不准确 —— 这不是内存数据库，只是标记
3. `get_stats()` 方法中检查 `self._db_path.exists()` 对 `from_connection` 创建的实例永远返回 `False`，导致 `db_size_mb` 不会被填充

**Fix:** 在 `from_connection` 的 docstring 中明确标注 "db_size_mb 不适用于 from_connection 创建的实例"，或在 `get_stats()` 中处理这种情况：

```python
# get_stats() 中
if self._db_path.exists() and str(self._db_path) != ":memory:":
    size_bytes = self._db_path.stat().st_size
    stats["db_size_mb"] = round(size_bytes / (1024 * 1024), 2)
else:
    stats["db_size_mb"] = None  # 或从 PRAGMA page_count * page_size 计算
```

**原因:** 工厂方法绕过构造函数是常见模式，但需要确保所有方法都能正确处理这种构造方式。

---

### IN-03: `backtest.py` 路由缺少 `date` 格式校验

**File:** `src/fund_screener/api/routes/backtest.py:72-73`
**Issue:** `start_date` 和 `end_date` 只标注了 `description="YYYY-MM-DD"`，但没有实际的格式校验：

```python
start_date: str = Field(..., description="回测开始日期 YYYY-MM-DD")
end_date: str = Field(..., description="回测结束日期 YYYY-MM-DD")
```

如果用户传入 `"2020/01/01"` 或 `"not-a-date"`，Pydantic 不会报错，错误会延迟到 SQL 查询阶段才暴露（`BETWEEN` 对非法字符串的行为不确定）。

**Fix:** 使用 Pydantic 的 `field_validator` 或 regex pattern：

```python
from pydantic import BaseModel, Field, field_validator
import re

_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

class BacktestRequest(BaseModel):
    # ...
    
    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        if not _DATE_PATTERN.match(v):
            raise ValueError(f"Date must be YYYY-MM-DD format, got: {v}")
        return v
    
    @field_validator("end_date")
    @classmethod
    def validate_date_range(cls, v: str, info) -> str:
        start = info.data.get("start_date")
        if start and v < start:
            raise ValueError(f"end_date ({v}) must be after start_date ({start})")
        return v
```

**原因:** 输入校验越早越好，在 Pydantic 层拦截非法输入比让错误传播到 SQL 层更干净。

---

_Reviewed: 2026-04-20_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
