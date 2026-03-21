# Fund Screener 开发进度记录

> 最后更新: 2026-03-21

---

## 已完成

### v0.1.0 — 初版核心功能 (commit: a962a36)

- [x] 项目骨架搭建（pyproject.toml, config.yaml）
- [x] 数据模型定义（models.py: Market, FundInfo, Holding, SectorWeight 等）
- [x] 配置加载模块（config.py: Pydantic BaseModel + YAML）
- [x] 文件缓存层（cache.py: FileCache, TTL 12 小时）
- [x] A 股公募基金数据源（fetchers/cn_fund.py）
- [x] 美股 ETF 数据源（fetchers/us_etf.py）
- [x] 港股 ETF 数据源（fetchers/hk_etf.py）
- [x] MA 均线筛选逻辑（screener.py）
- [x] 多周期涨跌幅计算（screener.py: calculate_trend_stats）
- [x] Markdown 报告生成（reporter.py）
- [x] CLI 入口编排（cli.py: click 命令行）
- [x] 单元测试 11 个（test_screener.py + test_reporter.py）

### SQLite 数据湖功能 (2026-03-20)

- [x] `config.py` 新增 `db_path` + `store_enabled` 配置字段
- [x] `config.yaml` 新增数据湖配置项
- [x] `storage.py` — DataStore 类完整实现
  - [x] 5 张表建表（funds, nav_records, holdings, sector_exposure, screening_results）
  - [x] PRAGMA WAL + NORMAL 同步模式
  - [x] PRAGMA user_version schema 版本管理
  - [x] `persist_fund_list()` — 批量 UPSERT 基金维度表
  - [x] `persist_nav_records()` — 批量 UPSERT 净值时序数据
  - [x] `persist_holdings()` — 持仓 + 行业一起存
  - [x] `persist_screening_result()` — 筛选结果快照
  - [x] `get_stats()` — 数据湖统计查询 API
  - [x] `_fund_id_cache` 内存映射优化性能
  - [x] `_normalize_date()` 统一日期格式防 UNIQUE 冲突
  - [x] 所有写入 try-except 包裹，失败只 warning 不 crash
  - [x] Context manager 支持（`with DataStore(...) as store:`）
- [x] `cli.py` 集成
  - [x] `--no-store` CLI flag
  - [x] `--db-stats` CLI flag（数据湖统计仪表盘）
  - [x] 4 个注入点（fund_list / nav_records / holdings / screening_result）
  - [x] 注入点 2 放在 MA 筛选之前（全量数据湖核心需求）
- [x] `tests/test_storage.py` — 9 个测试用例全部通过
- [x] `.gitignore` 新增 `*.db`
- [x] `README.md` 详细使用文档

### OLAP 量化中枢升级 v0.2.0 (2026-03-21)

#### Phase 1: 基础层 — Schema 迁移 + 数据模型 + 错误队列

- [x] `models.py` 新增 4 个 OLAP 数据模型
  - [x] `StockSectorMapping` — 股票申万行业映射
  - [x] `MomentumScanResult` — 横截面动量扫描结果
  - [x] `StyleDriftResult` — 风格漂移检测结果
  - [x] `CorrelationPair` — 基金对相关性
  - [x] `Holding` 新增 `hold_shares` 可选字段
- [x] `storage.py` Schema v1→v2 迁移
  - [x] `_SCHEMA_VERSION` 从 1 升到 2
  - [x] `_MIGRATION_V1_TO_V2` 增量迁移脚本（ALTER TABLE x3 + CREATE TABLE + CREATE INDEX x3）
  - [x] `_CREATE_TABLES_SQL` V2 全量建表（新 DB 直接用）
  - [x] `_init_db()` 三路分支：version=0 全量建表 / version=1 增量迁移 / version=2 跳过
- [x] `storage.py` 新增 persist 方法
  - [x] `persist_fund_detail()` — UPSERT funds 增强字段
  - [x] `persist_sector_mapping()` — 批量 UPSERT stock_sector_mapping
  - [x] `get_connection()` — 暴露只读连接给 analytics 层
  - [x] `persist_nav_records()` 增强 — 支持 unit_nav / cumulative_nav / adj_nav 新列
  - [x] `persist_holdings()` 增强 — 支持 hold_shares 新列
  - [x] `get_stats()` 增强 — 新增 stock_sector_mapping 统计
- [x] `error_queue.py` 全新模块
  - [x] `ErrorQueue` 类：load / save `data/error_log.json`
  - [x] `log_error()` — 记录错误（去重合并）
  - [x] `get_retry_queue()` — 返回未解决的 fund_code 列表
  - [x] `mark_resolved()` — 重试成功后移除
  - [x] `flush()` — 写盘（自动清除已解决记录）

#### Phase 2: 分析核心 — 三个 OLAP 函数

- [x] `analytics.py` 全新模块
  - [x] `scan_cross_sectional_momentum()` — 横截面动量扫描
    - SQL Window Function 计算 MA20/MA60
    - COALESCE(adj_nav, nav) 兼容旧数据
    - 筛选 MA20 > MA60 AND daily_return < 0
  - [x] `detect_style_drift()` — 风格漂移检测
    - 两季度持仓 Python dict merge
    - total_turnover = sum(|delta|) / 2
    - 标记新进/退出/大幅调仓
  - [x] `calculate_correlation_matrix()` — 底层相关性矩阵
    - JOIN holdings + stock_sector_mapping 聚合行业权重
    - Python 层余弦相似度
    - 超阈值报警对
  - [x] `_cosine_similarity()` — 稀疏向量余弦相似度

#### Phase 3: 数据充实 — Fetcher 增强

- [x] `fetchers/base.py` 新增 `fetch_fund_detail()` 可选方法（默认空 dict，不破坏 US/HK）
- [x] `fetchers/cn_fund.py` 增强
  - [x] `fetch_fund_detail()` — 调 `ak.fund_individual_info_em()` 获取规模/成立日期/经理
  - [x] `fetch_nav_history()` V2 增强 — 同时获取累计净值走势，返回 5 列 DataFrame
  - [x] `_parse_nav_dataframe()` — 抽取净值解析为独立方法（复用）
  - [x] `fetch_holdings()` 增强 — 解析"持股数"列
- [x] `sector_fetcher.py` 全新模块
  - [x] `fetch_and_persist_sector_mapping()` — 全量获取申万分类 + 规则引擎标注
  - [x] `HARD_TECH_SECTORS` / `RESOURCE_SECTORS` 关键词集合

#### Phase 4: 异步批量抓取

- [x] `async_fetcher.py` 全新模块
  - [x] `AsyncBulkFetcher` 类
  - [x] `asyncio.to_thread()` 包装同步 fetcher
  - [x] `asyncio.Semaphore(concurrency)` 并发控制
  - [x] 每 batch 间随机 sleep（0.5~1.5s）
  - [x] 集成 ErrorQueue：失败自动入队
  - [x] 显式设置 ThreadPoolExecutor 避免线程池瓶颈

#### Phase 5: CLI OLAP 子命令

- [x] `cli.py` 重构为 `@click.group(invoke_without_command=True)`（100% 向后兼容）
- [x] `--update-sectors` flag — 执行申万行业映射全量更新
- [x] `--db-stats` 增强 — 展示 stock_sector_mapping 统计
- [x] `_process_market()` 注入 fund_detail 持久化点
- [x] 4 个子命令
  - [x] `scan-momentum --date --ma-short --ma-long` — 横截面动量扫描
  - [x] `detect-drift --fund-code --current-quarter --prev-quarter --threshold` — 风格漂移检测
  - [x] `correlation --funds --threshold` — 底层相关性矩阵
  - [x] `bulk-fetch --market --concurrency` — 异步批量抓取

#### 测试

- [x] `tests/test_analytics.py` — 12 个测试
  - [x] TestMomentumScan: 多头回踩检出、数据不足排除、adj_nav NULL fallback、下跌趋势排除
  - [x] TestStyleDrift: 高换手漂移判定、微调正常判定
  - [x] TestCorrelation: 相同持仓高相似、不同行业低相似、超阈值报警
  - [x] TestCosineSimilarity: 相同向量、正交向量、空向量
- [x] `tests/test_error_queue.py` — 8 个测试（全生命周期）
- [x] `tests/test_async_fetcher.py` — 3 个测试（成功/失败/并发控制）
- [x] `tests/test_storage.py` 新增 9 个 V2 测试
  - [x] TestMigrationV1ToV2: 版本升级、新列存在、旧数据保留、新表可写
  - [x] TestPersistFundDetail: 基金详情 UPSERT
  - [x] TestPersistSectorMapping: 批量 UPSERT
  - [x] TestPersistNavV2: adj_nav 写入 + 旧格式兼容
  - [x] TestGetConnection: 连接暴露

**测试状态**: 52/52 全部通过 (`uv run pytest -v`, 0.90s)

### 申购限额标注 v0.3.0 (2026-03-21)

> 核心理念：默认只标注不过滤，所有通过 MA 的基金都保留。报告按申购状态分组展示，用户可用 `--purchase-filter` 主动开启过滤。

#### 数据模型 + 配置

- [x] `models.py` — FundInfo 新增 2 个字段
  - [x] `purchase_limit: float | None` — 日累计限定金额（元），None=未知
  - [x] `purchase_status_text: str | None` — 申购状态原始文本
- [x] `config.py` — CNFundConfig 新增 3 个配置项
  - [x] `annotate_purchase: bool = True` — 是否标注（默认开启）
  - [x] `filter_purchase: bool = False` — 是否过滤（默认关闭）
  - [x] `purchase_min_limit: float = 1000` — 过滤阈值（元）
- [x] `config.yaml` — 新增 3 行配置

#### 数据获取层

- [x] `fetchers/cn_fund.py` — 新增 `fetch_purchase_limit_map()` 方法
  - [x] 调用 `ak.fund_purchase_em()` 获取全市场申购限额数据（~2.6 万条）
  - [x] 返回 `{code: (daily_limit, status_text)}` 映射表
  - [x] 走 FileCache 缓存（共享 TTL）
  - [x] 列名动态识别（防 akshare 版本间变动）
  - [x] NaN 值替换为 -1.0 标记为"未知"
  - [x] 失败返回空 dict，不阻塞主流程

#### Schema 迁移

- [x] `storage.py` — Schema v2→v3 迁移
  - [x] `_SCHEMA_VERSION` 从 2 升到 3
  - [x] `_MIGRATION_V2_TO_V3` — screening_results 新增 purchase_limit + purchase_status 两列
  - [x] `_CREATE_TABLES_SQL` V3 全量建表更新
  - [x] `_init_db()` 新增 v2→v3 迁移路径 + v1→v3 链式迁移
  - [x] `persist_screening_result()` — INSERT/UPSERT 新增 purchase_limit + purchase_status

#### CLI 编排

- [x] `cli.py` — 核心编排逻辑
  - [x] `_process_market()` 新增 `filter_purchase` / `purchase_min_limit` 参数
  - [x] Step 0.5: A 股市场循环外预加载申购限额映射表
  - [x] MA 通过后：O(1) 查映射表标注限额信息
  - [x] 可选过滤：仅当 `--purchase-filter` 开启时剔除限额不足的基金
  - [x] FundInfo 构建时传入 purchase_limit + purchase_status_text
  - [x] `--purchase-filter` CLI flag（默认不过滤）
  - [x] `--purchase-min-limit N` CLI flag（过滤阈值，默认 1000）
  - [x] CLI flag 优先级覆盖 config.yaml 配置

#### 报告展示

- [x] `reporter.py` — 报告按申购状态分组展示（最大改动）
  - [x] `_classify_by_purchase()` — 四组分类（正常/限额/暂停/未知）
  - [x] `_format_purchase_limit()` — 金额格式化（无限制/X亿/X万/X元/暂停/未知）
  - [x] `_render_fund_detail()` — 抽取单基金渲染为独立函数（消除重复代码）
  - [x] CN 市场报告三（四）组展示：可正常申购 → 限额申购 → 暂停申购 → 状态未知
  - [x] 筛选概览新增 A 股申购状态分布统计
  - [x] 每只基金新增"申购状态 + 日限额"标注行
  - [x] US/HK 市场保持原有 MA 差值降序排列

#### 测试

- [x] `tests/test_purchase_filter.py` — 24 个新测试
  - [x] TestFetchPurchaseLimitMap: 正常解析、NaN 处理、API 失败兜底、缓存命中、列名缺失
  - [x] TestClassifyByPurchase: 正常/限额/暂停/未知/NaN/边界 1e8/混合
  - [x] TestFormatPurchaseLimit: 无限制/亿/万/元/暂停/未知
  - [x] TestMigrationV2ToV3: 版本升级、新列存在、旧数据保留、含申购字段写入
- [x] `tests/test_storage.py` — schema 版本号从 2 更新到 3

**测试状态**: 76/76 全部通过 (`uv run pytest -v`, 1.08s)

---

## 端到端验证 (2026-03-21)

- [x] `sqlite3 data/fund_data.db "PRAGMA user_version;"` — 返回 2 ✅ (v0.2.0)
- [x] `uv run fund-screener --db-stats` — V1→V2 自动迁移 + 6 张表统计正常 ✅
- [x] Schema 验证: funds 新增 establish_date/manager_name/fund_scale/track_benchmark ✅
- [x] Schema 验证: nav_records 新增 unit_nav/cumulative_nav/adj_nav ✅
- [x] Schema 验证: stock_sector_mapping 表创建成功 ✅
- [x] `uv run fund-screener --market cn` — 数据流正常（净值V2+复权净值获取+持久化）✅
- [x] fund_detail API 修复: `fund_individual_basic_info_xq` 替代不存在的 `fund_individual_info_em` ✅
- [x] fund_detail 验证: 005827 → 张坤/310.21亿/2018-09-05/沪深300 ✅
- [x] `uv run fund-screener scan-momentum --date 2026-03-20` — 检出 529 只回踩信号 ✅
- [x] `uv run fund-screener detect-drift` — 命令正常运行 ✅
- [x] `uv run fund-screener correlation` — 命令正常运行 ✅
- [x] `uv run pytest -v` — 52/52 全部通过 (0.88s) ✅
- [ ] `uv run fund-screener --update-sectors` — 待验证（需跑全量申万数据，耗时较长）
- [ ] `uv run fund-screener bulk-fetch --market cn --concurrency 5` — 待验证（需跑全量数据）

### v0.3.0 端到端验证（待执行）

- [ ] `sqlite3 data/fund_data.db "PRAGMA user_version;"` — 应返回 3（v2→v3 自动迁移）
- [ ] `uv run fund-screener --market cn -v` — 确认日志显示"基金申购限额数据加载完成"
- [ ] 检查 `output/fund_report.md` — 确认 CN 市场按三组分组展示（正常/限额/暂停）
- [ ] `uv run fund-screener --market cn --purchase-filter --purchase-min-limit 1000` — 验证过滤生效
- [ ] `uv run pytest -v` — 76/76 全部通过 ✅

---

## 未来可扩展方向（未开始）

- [ ] 定时任务支持（cron / schedule 每日自动跑）
- [ ] 数据清理/归档策略（DB 长期只增不删，需要考虑磁盘）
- [ ] 基于历史数据的回测模块
- [ ] Web UI 仪表盘（展示趋势、持仓变化）
- [ ] adj_nav 历史回填（迁移后旧数据 adj_nav 为 NULL，需跑一次 bulk-fetch 补齐）
