# OLAP 量化中枢升级 — 任务清单

> 最后更新: 2026-03-21

## Phase 1: 基础层（Schema 迁移 + 数据模型 + 错误队列）

- [x] **T1.1** models.py 新增 4 个 OLAP 数据模型 + hold_shares 字段
- [x] **T1.2** storage.py Schema v1→v2 迁移脚本
- [x] **T1.3** storage.py 新增 persist 方法（fund_detail, sector_mapping, get_connection）
- [x] **T1.4** error_queue.py 全新模块
- [x] **T1.5** Phase 1 测试（迁移 + persist + error_queue）

## Phase 2: 分析核心（三个 OLAP 函数）

- [x] **T2.1** analytics.py — scan_cross_sectional_momentum
- [x] **T2.2** analytics.py — detect_style_drift
- [x] **T2.3** analytics.py — calculate_correlation_matrix
- [x] **T2.4** Phase 2 测试（12 个分析函数测试）

## Phase 3: 数据充实（Fetcher 增强）

- [x] **T3.1** fetchers/base.py 扩展 fetch_fund_detail
- [x] **T3.2** fetchers/cn_fund.py 增强（复权净值 + 基金详情 + 持股数）
- [x] **T3.3** sector_fetcher.py 申万行业映射获取
- [x] **T3.4** cli.py 集成数据充实（--update-sectors + db-stats 更新）

## Phase 4: 异步批量抓取

- [x] **T4.1** async_fetcher.py 核心实现
- [x] **T4.2** cli.py 新增 bulk-fetch 命令
- [x] **T4.3** Phase 4 测试（并发控制 + 错误队列集成）

## Phase 5: CLI OLAP 子命令

- [x] **T5.1** cli.py 重构为 click.Group（向后兼容）
- [x] **T5.2** 三个分析子命令（scan-momentum, detect-drift, correlation）
- [ ] **T5.3** 端到端集成验证（需实际运行验证）

## 验证状态

- [x] `uv run pytest -v` — 52 个测试全部通过
- [ ] 端到端数据采集验证
- [ ] 端到端分析命令验证
