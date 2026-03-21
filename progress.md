# Fund Screener 开发进度记录

> 最后更新: 2026-03-20

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
  - [x] test_all_tables_exist
  - [x] test_schema_version_set
  - [x] test_insert_and_upsert (fund_list)
  - [x] test_insert_and_upsert (nav_records)
  - [x] test_empty_df_no_op
  - [x] test_holdings_and_sectors
  - [x] test_screening_result
  - [x] test_persist_with_closed_connection
  - [x] test_persist_with_corrupted_store
- [x] `.gitignore` 新增 `*.db`
- [x] `README.md` 详细使用文档

**测试状态**: 20/20 全部通过 (`uv run pytest -v`)

---

## 待验证

- [ ] `uv run fund-screener --market us` 端到端验证数据湖写入
  - 验证 `SELECT COUNT(*) FROM funds;` 有 85 只美股 ETF
  - 验证 `SELECT COUNT(*) FROM nav_records;` 有 ~8500 条
  - 验证 `SELECT COUNT(*) FROM screening_results;` 有通过筛选的基金数
- [ ] `uv run fund-screener --market us --no-store` 验证不写 DB
- [ ] `uv run fund-screener --db-stats` 验证统计输出

---

## 未来可扩展方向（未开始）

- [ ] 数据湖查询 API（按日期范围导出净值、跨市场对比）
- [ ] 定时任务支持（cron / schedule 每日自动跑）
- [ ] 数据清理/归档策略（DB 长期只增不删，需要考虑磁盘）
- [ ] 基于历史数据的回测模块
- [ ] Web UI 仪表盘（展示趋势、持仓变化）
