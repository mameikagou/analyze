# fund-screener 本地 API Skill — 项目功能速查册

> **用途:** 让任意新 Claude 实例零考古上手项目内部 API。
> **范围:** 仅列签名和字段,不展开业务逻辑。业务细节以源码 docstring 为准。
> **维护纪律:** 边写代码边改本文。新增/删除/改签名 → 同步更新。文档滞后视为 bug。
> **姊妹篇:** 外部数据源接入见 `skills/tushare_api.md`。
> 最后更新: 2026-04-13

---

## 1. 入口层 (CLI)

### 1.1 根命令 & 全局选项

```bash
fund-screener [OPTIONS] [SUBCOMMAND]
# 或等价地
python -m fund_screener [OPTIONS] [SUBCOMMAND]
```

| 选项 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `--config PATH` | str | `config.yaml` | 配置文件路径 |
| `--market` | cn\|us\|hk\|all | `all` | 目标市场(可多次使用) |
| `--output PATH` | str | `output/fund_report.md` | 报告输出路径 |
| `--no-cache` | flag | false | 忽略缓存,强制重拉 |
| `--no-store` | flag | false | 禁用 SQLite 持久化 |
| `--db-stats` | flag | false | 仅打印数据湖统计(不跑筛选) |
| `--update-sectors` | flag | false | 更新申万行业映射表 |
| `--purchase-filter` | flag | false | 启用 A股申购限额过滤 |
| `--purchase-min-limit` | float | 1000.0 | 过滤阈值(元) |
| `--verbose`, `-v` | flag | false | DEBUG 日志 |

**无子命令时默认行为:** 拉列表 → MA 筛选 → 持久化 → 生成报告。

### 1.2 子命令速查

| 子命令 | 入口函数 | 定义位置 | 作用 |
|--------|---------|---------|------|
| `scan-momentum` | `cmd_scan_momentum` | `cli.py:574` | 横截面动量扫描(多头排列+回踩) |
| `detect-drift` | `cmd_detect_drift` | `cli.py:628` | 季度持仓风格漂移检测 |
| `correlation` | `cmd_correlation` | `cli.py:686` | 多基金行业相关性矩阵 |
| `bulk-fetch` | `cmd_bulk_fetch` | `cli.py:766` | 异步批量抓取净值/详情 |
| `score` | `cmd_score` | `cli.py:856` | 三因子复合打分 Top N |

**子命令参数**(挑关键的):
- `scan-momentum --date YYYY-MM-DD --ma-short 20 --ma-long 60`
- `detect-drift --fund-code 005827 --current-quarter YYYY-MM-DD --prev-quarter YYYY-MM-DD --threshold 20.0`
- `correlation --funds 005827,007119,... --threshold 0.3`
- `bulk-fetch --market cn --concurrency 10`
- `score --market all --top-n N`(不填读 `config.yaml`)

---

## 2. 数据模型 (`src/fund_screener/models.py`)

全部基于 `pydantic.BaseModel`。

### 2.1 基础枚举

```python
class Market(str, Enum):
    CN = "CN"   # A股公募
    US = "US"   # 美股 ETF
    HK = "HK"   # 港股 ETF
```

### 2.2 持仓与净值原子模型

| 模型 | 关键字段 |
|------|---------|
| `NAVRecord` | `date: date`, `nav: float` |
| `Holding` | `stock_code`, `stock_name`, `weight_pct: float\|None`, `hold_shares: float\|None`(万股) |
| `SectorWeight` | `sector: str`, `weight_pct: float` |
| `TrendStats` | `change_1w/1m/3m/6m/1y: float\|None` |

### 2.3 `FundInfo` — 报告核心数据结构

```python
code: str                          # 基金代码
name: str
market: Market
nav: float                         # 最新单位净值/收盘价
ma_short: float                    # 短期均线
ma_long: float                     # 长期均线
ma_diff_pct: float                 # (ma_short - ma_long) / ma_long * 100
top_holdings: list[Holding]        # Top 10
sector_exposure: list[SectorWeight]
daily_change_pct: float | None
trend_stats: TrendStats | None
purchase_limit: float | None       # 日申购限额(元); None=未知, 0=暂停, 1e11=无限
purchase_status_text: str | None   # "开放申购" / "暂停申购" / ...
data_date: date
holdings_date: str | None          # 报告期如 "2025Q4"
```

### 2.4 筛选 & 汇总

```python
ScreenResult:  ma_short, ma_long, ma_diff_pct: float, passed: bool
ScreeningSummary: market, total_scanned, total_passed, pass_rate
```

### 2.5 OLAP 量化分析(v2)

| 模型 | 关键字段 |
|------|---------|
| `StockSectorMapping` | `stock_code`, `stock_name`, `sw_sector_l1`, `is_hard_tech`, `is_resource` |
| `MomentumScanResult` | `fund_code`, `scan_date`, `ma_short/long`, `ma_diff_pct`, `daily_return`, `latest_nav` |
| `StyleDriftResult` | `fund_code`, `current_quarter`, `prev_quarter`, `total_turnover`, `is_drifted`, `threshold`, `new_entries`, `exits`, `major_changes: list[dict]` |
| `CorrelationPair` | `fund_a`, `fund_b`, `similarity: float[0,1]`, `is_alert: bool` |

### 2.6 量化打分(v4)

```python
class RiskMetrics:
    momentum: float       # (latest_nav - MA20) / MA20
    max_drawdown: float   # 负值,-0.25 = -25%
    sharpe: float         # 年化夏普
    nav_count: int        # 参与计算的净值条数

class ScoredFund:
    fund: FundInfo
    risk_metrics: RiskMetrics
    z_momentum / z_drawdown / z_sharpe: float   # Z-Score(回撤已反转)
    composite_score: float
    rank: int             # 1 = 第一名
```

---

## 3. 配置模式 (`src/fund_screener/config.py` + `config.yaml`)

### 3.1 加载入口

```python
from fund_screener.config import load_config, AppConfig
config: AppConfig = load_config("config.yaml")
# 文件缺失 → 走全部默认值,不报错(首次运行友好)
# 会自动创建 output_dir / cache_dir / db_path 父目录
```

### 3.2 `AppConfig` 顶层字段

| 字段 | 类型 | 默认 |
|------|------|------|
| `ma_short / ma_long` | int | 20 / 60 |
| `lookback_days` | int | 150 |
| `output_dir / cache_dir` | str | `./output` / `./.cache` |
| `cache_ttl_hours` | int | 12 |
| `db_path` | str | `./data/fund_data.db` |
| `store_enabled` | bool | true |
| `cn_fund` | `CNFundConfig` | 见 3.3 |
| `us_etf / hk_etf` | `USETFConfig / HKETFConfig` | 见下 |
| `rate_limit` | `RateLimitConfig` | 见下 |
| `scoring` | `ScoringConfig` | 见下 |

### 3.3 `CNFundConfig` — A股专用

```yaml
cn_fund:
  enabled: true
  fund_types: ["股票型", "混合型", "指数型"]
  max_funds: 500
  annotate_purchase: true           # 仅标注不过滤
  filter_purchase: false            # 搭配 --purchase-filter
  purchase_min_limit: 1000.0
  data_source:                      # ★ 组合 fetcher 路由表
    primary: akshare                # 未命中 route 时的兜底
    route:
      fetch_fund_list: akshare
      fetch_nav_history: tushare    # tushare 补:规范 SLA 净值
      fetch_holdings: akshare
      fetch_sector_exposure: akshare
      fetch_fund_detail: akshare
      fetch_purchase_limit_map: akshare
```

**route 的 key 白名单** = BaseFetcher 所有方法名(见 §4.1)。写错 key 启动即 `ValueError`。

### 3.4 其他子配置

```python
USETFConfig:     enabled, ticker_source, extra_tickers: list[str]
HKETFConfig:     enabled, max_funds
RateLimitConfig: tushare_delay_sec=0.3, akshare_delay_sec=0.5,
                 yfinance_delay_sec=0.3, etfdb_delay_sec=1.0,
                 max_retries=3, retry_backoff_sec=2.0
ScoringWeights:  momentum=0.4, drawdown=0.3, sharpe=0.3
ScoringConfig:   enabled=true, weights: ScoringWeights,
                 top_n=30, min_nav_days=60
```

---

## 4. 基础设施 (Cache / ErrorQueue / Retry)

### 4.1 `cache.py — FileCache`

```python
class FileCache:
    def __init__(self, cache_dir: str, ttl_hours: int = 12): ...
    def get(self, key: str) -> Any | None           # 命中返回反序列化对象,过期/缺失返回 None
    def set(self, key: str, data: Any, ttl_hours: int | None = None) -> None
    def invalidate(self, key: str) -> None           # 手动删除缓存条目
```

所有 Fetcher 的 `__init__` 都接收 `FileCache` 实例,`--no-cache` 模式下 CLI 会传入禁用缓存的实例。

### 4.2 `error_queue.py — ErrorQueue`

```python
class ErrorQueue:
    def __init__(self, error_log_path: str | Path): ...
    def load(self) -> None                           # 从磁盘加载历史错误
    def log_error(self, fund_code: str, error_type: str, message: str) -> None
    def get_retry_queue(self) -> list[str]           # 返回可重试的基金代码列表
    def mark_resolved(self, fund_code: str) -> None
    def flush(self) -> None                          # 写盘
    def entries(self) -> list[dict[str, Any]]        # 所有条目
```

搭配 `AsyncBulkFetcher` 使用,批量抓取时记录失败项。

### 4.3 `with_retry` 装饰器 (`fetchers/base.py:140`)

```python
def with_retry(max_retries: int = 3, backoff_sec: float = 2.0) -> Any:
    """指数退避重试装饰器,所有 fetch_* 方法可用"""
```

---

## 5. Fetcher 层 (`src/fund_screener/fetchers/`)

### 5.1 `BaseFetcher` 抽象契约 (`fetchers/base.py`)

```python
class BaseFetcher(ABC):
    def __init__(self, cache: FileCache, rate_limit_config: RateLimitConfig): ...

    # --- 必选(4 个 @abstractmethod) ---
    @abstractmethod
    def fetch_fund_list(self) -> list[dict[str, str]]:
        """返回 [{"code": "005827", "name": "..."}]"""

    @abstractmethod
    def fetch_nav_history(self, code: str, days: int) -> pd.DataFrame:
        """DataFrame 列: ['date', 'nav'] 升序"""

    @abstractmethod
    def fetch_holdings(self, code: str) -> list[Holding]:
        """按 weight_pct 降序"""

    @abstractmethod
    def fetch_sector_exposure(self, code: str) -> list[SectorWeight]: ...

    # --- 可选(有默认空实现) ---
    def fetch_fund_detail(self, code: str) -> dict[str, Any]:
        """默认返回 {}。子类可选择性覆盖"""
```

**扩展方法** (不在抽象契约里): `fetch_purchase_limit_map() -> dict[str, tuple[float, str]]`
→ 仅 `AkshareCNProvider` / `CompositeCNFetcher` 实现。调用方需 `hasattr` 兜底。

### 5.2 具体实现

| 类 | 文件 | 作用 |
|----|------|------|
| `CompositeCNFetcher` | `fetchers/cn_composite.py` | ★ CN 默认入口,按 route 分发 |
| `AkshareCNProvider` | `fetchers/providers/akshare_cn.py` | akshare 数据源 |
| `TushareCNProvider` | `fetchers/providers/tushare_cn.py` | tushare Pro 数据源(详见 `tushare_api.md`) |
| `USETFFetcher` | `fetchers/us_etf.py` | yfinance 驱动 |
| `HKETFFetcher` | `fetchers/hk_etf.py` | 港股 ETF |

**兼容 shim:** `fetchers/cn_fund.py` / `cn_tushare.py` 仍在,一行 re-export 老类名(`CNFundFetcher` / `CNTushareFetcher`),仅为兼容旧测试,新代码别用。

**CompositeCNFetcher 构造:**

```python
CompositeCNFetcher(
    cache: FileCache,
    rate_limit_config: RateLimitConfig,
    cn_config: CNFundConfig,          # 含 data_source
    providers: dict[str, BaseFetcher],  # {"akshare": ..., "tushare": ...}
)
# 构造时会 _validate_routing(): 路由到未注册的 provider / 未知方法名 → ValueError
```

**推荐用工厂** `cli.py:62 _build_cn_fetcher(config, cache) -> BaseFetcher`。

### 5.3 异步批量层 (`async_fetcher.py`)

```python
class AsyncBulkFetcher:
    def __init__(
        fetcher: BaseFetcher,
        store: DataStore,
        error_queue: ErrorQueue,
        concurrency: int = 10,
        batch_size: int = 50,
    ): ...

    async def bulk_fetch(
        fund_codes: list[str],
        fetch_detail: bool = True,
    ) -> dict[str, int]:
        # {"success": N, "failed": M, "total": len(fund_codes)}
```

---

## 6. 筛选与分析

### 6.1 `screener.py` — MA 筛选

```python
screen_fund(
    nav_history: pd.DataFrame,
    ma_short_period: int = 20,
    ma_long_period: int = 60,
) -> ScreenResult | None

calculate_trend_stats(nav_history: pd.DataFrame) -> TrendStats
calculate_ma(nav_series: pd.Series, period: int) -> pd.Series
```

### 6.2 `analytics.py` — OLAP (只读 SQLite)

```python
scan_cross_sectional_momentum(
    conn: sqlite3.Connection, scan_date: str,
    ma_short: int = 20, ma_long: int = 60,
) -> list[MomentumScanResult]

detect_style_drift(
    conn: sqlite3.Connection, fund_code: str,
    current_quarter: str, prev_quarter: str,
    threshold: float = 20.0,
) -> StyleDriftResult

calculate_correlation_matrix(
    conn: sqlite3.Connection,
    fund_code_list: list[str],
    threshold: float = 0.3,
) -> dict[str, Any]
# -> {"matrix": {...}, "alerts": list[CorrelationPair]}
```

### 6.3 `risk_metrics.py` — 三因子(纯函数)

```python
momentum_score(nav_series: pd.Series, ma_period: int = 20) -> float
max_drawdown(nav_series: pd.Series) -> float
sharpe_ratio(
    nav_series: pd.Series,
    rf_annual: float = 0.02,
    periods_per_year: int = 252,
) -> float
```

### 6.4 `scoring.py` — 复合打分

```python
score_funds(
    funds_with_nav: list[tuple[FundInfo, pd.DataFrame]],
    weights: ScoringWeights,
    top_n: int = 30,
    min_nav_days: int = 60,
    filter_qdii_bonds: bool = True,
) -> list[ScoredFund]
# 流程: QDII/债基过滤 → Z-Score 归一 → 加权合成 → 排序取 Top N
```

---

## 7. 存储与报告

### 7.1 `storage.py — DataStore` (SQLite)

支持 context manager。

```python
with DataStore(db_path) as store:
    store.persist_fund_list(market, funds: list[dict])
    store.persist_nav_records(market, code, nav_df: pd.DataFrame)
    store.persist_holdings(market, code, holdings, sectors)
    store.persist_screening_result(fund: FundInfo)
    store.persist_fund_detail(...)
    store.persist_sector_mapping(...)
    conn = store.get_connection()      # for analytics
    stats = store.get_stats()          # dict[str, Any]
```

### 7.2 `reporter.py` — Markdown 报告

```python
generate_report(
    funds: list[FundInfo],
    summaries: list[ScreeningSummary],
    ma_short_period: int = 20,
    ma_long_period: int = 60,
    output_path: str | Path = "output/fund_report.md",
) -> Path

generate_scored_report(
    scored_funds: list[ScoredFund],
    weights_desc: str,
    output_path: str | Path = "output/scored_report.md",
) -> Path
```

### 7.3 其他辅助

- `sector_fetcher.fetch_and_persist_sector_mapping(store) -> int` — 更新申万映射,返回写入行数。
- `fetchers/us_holdings.fetch_etf_holdings_from_web(...)` — 美股 ETF 持仓网页补抓。

---

## 8. 编程式调用示例

### 8.1 最小可跑:直接算风险指标

```python
from fund_screener.config import load_config
from fund_screener.storage import DataStore
from fund_screener.risk_metrics import momentum_score, max_drawdown, sharpe_ratio
import pandas as pd

config = load_config()
with DataStore(config.db_path) as store:
    conn = store.get_connection()
    df = pd.read_sql(
        "SELECT nav_date, nav FROM nav_records "
        "WHERE fund_code=? ORDER BY nav_date",
        conn, params=("005827",),
    )
    nav = df["nav"]
    print(momentum_score(nav), max_drawdown(nav), sharpe_ratio(nav))
```

### 8.2 自建 Composite Fetcher(不走 CLI)

```python
from fund_screener.cache import FileCache
from fund_screener.fetchers.providers import AkshareCNProvider, TushareCNProvider
from fund_screener.fetchers.cn_composite import CompositeCNFetcher

config = load_config()
cache = FileCache(config.cache_dir, config.cache_ttl_hours)
providers = {
    "akshare": AkshareCNProvider(cache, config.rate_limit),
    "tushare": TushareCNProvider(cache, config.rate_limit),
}
fetcher = CompositeCNFetcher(cache, config.rate_limit, config.cn_fund, providers)
nav_df = fetcher.fetch_nav_history("005827", days=150)   # 走 tushare
holdings = fetcher.fetch_holdings("005827")              # 走 akshare
```

> Tushare provider 会在 `__init__` 立刻读 `TUSHARE_TOKEN`。
> 独立脚本里记得 `from dotenv import load_dotenv; load_dotenv()`,否则初始化崩。

---

## 9. 维护纪律

| 动作 | 同步本文件? |
|------|------------|
| 新增公共函数 / CLI 子命令 | ✅ 必须加条目 |
| 改函数签名 / 模型字段 | ✅ 改表格 |
| 删公共 API | ✅ 删条目,不要残留 |
| 改内部私有 `_xxx` 实现 | ❌ 无需 |
| 改业务逻辑(含义变化) | ⚠️ 只改 docstring,本文不展开逻辑 |

**边界:** 本 skill 仅列**本项目自身** API。外部数据源(tushare 字段、akshare 坑点)归 `skills/tushare_api.md`。
