# Fund Screener — 全市场基金/ETF 趋势筛选器

抓取 A股/美股/港股 基金与 ETF 数据，用 MA 均线筛选右侧趋势标的，生成结构化 Markdown 报告供 LLM（Claude / Gemini）深度分析。

---

## 目录

- [快速开始](#快速开始)
- [安装](#安装)
- [CLI 命令参考](#cli-命令参考)
- [配置文件详解](#配置文件详解)
- [数据湖（SQLite DataStore）](#数据湖sqlite-datastore)
- [项目结构](#项目结构)
- [开发指南](#开发指南)

---

## 快速开始

```bash
# 1. 安装依赖
uv sync

# 2. 筛选美股 ETF（最常用）
uv run fund-screener --market us

# 3. 查看报告
cat output/fund_report.md

# 4. 查看数据湖统计
uv run fund-screener --db-stats
```

---

## 安装

**前置要求**: Python >= 3.11, [uv](https://docs.astral.sh/uv/) 包管理器

```bash
# 克隆项目
git clone <repo-url> && cd analyze

# 安装所有依赖（含开发依赖）
uv sync --dev
```

---

## CLI 命令参考

```bash
uv run fund-screener [OPTIONS]
```

### 选项一览

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--market` | `cn/us/hk/all` | `all` | 筛选哪个市场 |
| `--config` | 文件路径 | `config.yaml` | 配置文件路径 |
| `--output` | 文件路径 | `output/fund_report.md` | 输出报告路径 |
| `--no-cache` | flag | - | 忽略缓存，强制重新拉取 API 数据 |
| `--no-store` | flag | - | 本次运行不写入 SQLite 数据湖 |
| `--db-stats` | flag | - | 查看数据湖统计信息（不执行筛选） |
| `--verbose / -v` | flag | - | 输出 DEBUG 级别详细日志 |

### 使用示例

```bash
# --- 基本筛选 ---

# 筛选美股 ETF
uv run fund-screener --market us

# 筛选 A 股公募基金
uv run fund-screener --market cn

# 筛选港股 ETF
uv run fund-screener --market hk

# 全市场一起跑（A股 + 美股 + 港股）
uv run fund-screener --market all

# --- 缓存控制 ---

# 忽略缓存，强制重新请求所有 API
uv run fund-screener --market us --no-cache

# --- 数据湖控制 ---

# 本次不写入数据湖（只跑筛选 + 报告）
uv run fund-screener --market us --no-store

# 查看数据湖统计仪表盘
uv run fund-screener --db-stats

# --- 输出控制 ---

# 指定输出路径
uv run fund-screener --market us --output ./my_report.md

# 详细日志（调试用）
uv run fund-screener --market us -v

# --- 组合使用 ---

# 全市场 + 无缓存 + 详细日志
uv run fund-screener --market all --no-cache -v
```

### `--db-stats` 输出示例

```
=======================================================
=================  数据湖统计  =================
=======================================================
  数据库路径: ./data/fund_data.db
  文件大小:   1.23 MB

--- 表记录数 ---
  基金维度表 (funds)                        85 条
  净值时序 (nav_records)                 8,500 条
  持仓快照 (holdings)                      340 条
  行业分布 (sector_exposure)               170 条
  筛选结果 (screening_results)              23 条

--- 按市场统计 ---
  市场           基金数     净值记录数
  ----         ------     ----------
  US               85        8,500

--- 净值数据时间范围 ---
  最早: 2025-10-01
  最新: 2026-03-20

--- 最近 5 次筛选 ---
  日期               通过数量
  ----             ------
  2026-03-20           23 只

=======================================================
```

---

## 配置文件详解

配置文件为项目根目录下的 `config.yaml`，所有字段都有默认值，首次运行不需要手动创建。

```yaml
# ==========================================
# 基金/ETF 趋势筛选器 — 配置文件
# ==========================================

# ---- 均线参数 ----
ma_short: 20          # 短期均线周期（天）
ma_long: 60           # 长期均线周期（天）
lookback_days: 150    # 拉取历史数据天数（建议 >= ma_long * 2.5）

# ---- 输出配置 ----
output_dir: "./output"

# ---- 缓存配置 ----
cache_dir: "./.cache"
cache_ttl_hours: 12   # 缓存有效期（小时），CLI --no-cache 可跳过

# ---- 数据湖配置 ----
db_path: "./data/fund_data.db"    # SQLite 数据库文件路径
store_enabled: true               # 是否启用，CLI --no-store 可临时关闭

# ---- A股公募基金 ----
cn_fund:
  enabled: true
  fund_types:             # 筛选哪些类型
    - "股票型"
    - "混合型"
    - "指数型"
  max_funds: 500          # 最多处理数量（设 0 不限制）

# ---- 美股 ETF ----
us_etf:
  enabled: true
  ticker_source: "data/us_etf_universe.json"   # ETF 列表文件
  extra_tickers: []       # 手动追加的 ticker

# ---- 港股 ETF ----
hk_etf:
  enabled: true
  max_funds: 200

# ---- 限速配置 ----
rate_limit:
  akshare_delay_sec: 0.5      # akshare 请求间隔（爬东财，太快被封）
  yfinance_delay_sec: 0.3     # yfinance 请求间隔
  etfdb_delay_sec: 1.0        # etfdb 爬虫间隔（更保守）
  max_retries: 3              # 最大重试次数
  retry_backoff_sec: 2.0      # 重试退避基数（指数退避）
```

### 关键参数调优建议

| 参数 | 调大 | 调小 |
|------|------|------|
| `ma_short` | 减少噪音，信号滞后 | 更敏感，假信号增多 |
| `ma_long` | 只抓大趋势，错过早期 | 更容易触发，准确率降低 |
| `lookback_days` | 数据更充分，请求更慢 | 请求更快，可能数据不足 |
| `cache_ttl_hours` | 减少 API 请求 | 数据更新更及时 |
| `max_funds` | 覆盖更全 | 跑得更快 |

---

## 数据湖（SQLite DataStore）

### 是什么

一个基于 SQLite 的**永久数据仓库**，自动把每次运行时拉取的 API 数据（基金列表、净值历史、持仓、行业分布、筛选结果）全部保存下来。

### 与缓存的区别

| | FileCache（缓存） | DataStore（数据湖） |
|---|---|---|
| 目的 | API 限速保护 | 永久数据积累 |
| 过期 | 12 小时 TTL | 永不过期 |
| 存储格式 | JSON 文件 | SQLite 数据库 |
| 写入失败 | 不影响主流程 | 不影响主流程 |
| 关闭方式 | `--no-cache` | `--no-store` |

### 数据库结构（5 张表）

```
funds                  基金维度表        UNIQUE(market, code)
nav_records            净值时序数据      UNIQUE(fund_id, date)
holdings               持仓快照          UNIQUE(fund_id, stock_code, snapshot_date)
sector_exposure        行业分布快照      UNIQUE(fund_id, sector, snapshot_date)
screening_results      筛选结果快照      UNIQUE(fund_id, screening_date)
```

### 直接查询数据库

```bash
# 打开数据库
sqlite3 data/fund_data.db

# 查看有多少只基金
SELECT market, COUNT(*) FROM funds GROUP BY market;

# 查看某只 ETF 的净值历史
SELECT n.date, n.nav
FROM nav_records n
JOIN funds f ON n.fund_id = f.id
WHERE f.code = 'SPY'
ORDER BY n.date DESC
LIMIT 20;

# 查看某只 ETF 的持仓
SELECT h.stock_code, h.stock_name, h.weight_pct
FROM holdings h
JOIN funds f ON h.fund_id = f.id
WHERE f.code = 'QQQ'
ORDER BY h.weight_pct DESC;

# 查看最近一次筛选通过了哪些基金
SELECT f.code, f.name, s.nav, s.ma_diff_pct, s.daily_change_pct
FROM screening_results s
JOIN funds f ON s.fund_id = f.id
WHERE s.screening_date = (SELECT MAX(screening_date) FROM screening_results)
ORDER BY s.ma_diff_pct DESC;

# 导出净值数据为 CSV（供 Python/Excel 分析）
.headers on
.mode csv
.output nav_export.csv
SELECT f.market, f.code, f.name, n.date, n.nav
FROM nav_records n JOIN funds f ON n.fund_id = f.id
ORDER BY f.code, n.date;
.output stdout
```

### 可视化工具推荐

- **[DB Browser for SQLite](https://sqlitebrowser.org/)** — 免费 GUI，直接打开 `data/fund_data.db` 浏览表、画图表
- **[DBeaver](https://dbeaver.io/)** — 更专业的数据库客户端，支持 SQL 编辑器 + 图表
- **Python pandas** — `pd.read_sql("SELECT ...", sqlite3.connect("data/fund_data.db"))` 直接读取分析

---

## 项目结构

```
analyze/
  config.yaml                  # 配置文件
  pyproject.toml               # 项目元数据 + 依赖
  data/
    us_etf_universe.json       # 美股 ETF 列表
    fund_data.db               # SQLite 数据湖（自动生成，已 gitignore）
  output/
    fund_report.md             # 筛选报告（自动生成）
  src/fund_screener/
    cli.py                     # CLI 入口，编排全流程
    config.py                  # 配置加载与校验
    models.py                  # 数据模型（FundInfo, Market 等）
    cache.py                   # 文件缓存层
    storage.py                 # SQLite 数据湖（DataStore）
    screener.py                # MA 均线筛选逻辑
    reporter.py                # Markdown 报告生成
    fetchers/
      base.py                  # Fetcher 抽象基类
      cn_fund.py               # A 股公募基金数据源
      us_etf.py                # 美股 ETF 数据源
      hk_etf.py                # 港股 ETF 数据源
  tests/
    test_screener.py           # 筛选逻辑测试
    test_reporter.py           # 报告生成测试
    test_storage.py            # 数据湖测试
```

---

## 开发指南

### 运行测试

```bash
# 全部测试
uv run pytest

# 带详细输出
uv run pytest -v

# 只跑某个测试文件
uv run pytest tests/test_storage.py -v
```

### 执行流程

```
CLI 启动
  |
  v
加载 config.yaml
  |
  v
初始化 FileCache + DataStore
  |
  v
按市场遍历:
  |-- 获取基金列表 -------> DataStore.persist_fund_list()
  |-- 遍历每只基金:
  |     |-- 拉净值历史 ---> DataStore.persist_nav_records()  (全量存，不管是否通过筛选)
  |     |-- MA 筛选
  |     |-- 如果通过:
  |     |     |-- 拉持仓 -> DataStore.persist_holdings()
  |     |     |-- 构建 FundInfo -> DataStore.persist_screening_result()
  |
  v
生成 Markdown 报告
```

### 添加新市场

1. 在 `models.py` 的 `Market` 枚举中添加新值
2. 在 `fetchers/` 下创建新的 Fetcher 类（继承 `BaseFetcher`）
3. 在 `config.py` 添加对应的配置子模型
4. 在 `cli.py` 的 `_create_fetchers()` 中注册
5. 数据湖无需任何改动（market 字段自动区分）
