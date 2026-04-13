# Tushare Pro API Skill — 实战经验手册

> 边写代码边维护。记录实际使用过的 API、字段映射、踩坑经验。
> 最后更新：2026-04-13

---

## 基础配置

```python
import tushare as ts

# Token 从 .env 文件加载
ts.set_token(os.getenv("TUSHARE_TOKEN"))
pro = ts.pro_api()
```

- Token 获取：https://tushare.pro/user/token
- 积分制度：接口有积分门槛（不消耗），积分越高频率越高
- 日期格式：统一 **YYYYMMDD** 字符串（不是 YYYY-MM-DD）

---

## 已使用的 API

### 1. fund_basic — 公募基金列表（维度表）

```python
df = pro.fund_basic(market='O', status='L')
```

| 参数 | 值 | 说明 |
|------|------|------|
| market | `'O'` 场外 / `'E'` 场内 | 公募基金用 O |
| status | `'L'` 上市 / `'D'` 摘牌 / `'I'` 发行 | 通常只要 L |

**关键输出字段：**

| 字段 | 类型 | 说明 | 实测备注 |
|------|------|------|----------|
| ts_code | str | 基金代码，如 `005827.OF` | 场外带 `.OF` 后缀 |
| name | str | 基金简称 | |
| fund_type | str | 投资类型 | `股票型`、`混合型`、`债券型`、`货币型`、`QDII型` 等 |
| found_date | str | 成立日期 YYYYMMDD | |
| management | str | 管理人（公司名） | 注意：不是基金经理个人姓名 |
| benchmark | str | 业绩比较基准 | |
| status | str | 存续状态 D/I/L | |
| purc_startdate | str | 申购起始日 | |
| issue_amount | float | 发行份额（亿） | |
| m_fee | float | 管理费率 | |
| c_fee | float | 托管费率 | |

**积分要求：** 2000

**踩坑：**
- `fund_type` 的值跟 akshare 的"基金类型"基本一致（股票型、混合型、指数型），可以直接用 config.yaml 的 fund_types 过滤
- `management` 是公司名不是基金经理名，没有单独的基金经理字段
- 无申购限额金额数据，只能靠 status 做二元判断

---

### 2. fund_nav — 公募基金净值

```python
df = pro.fund_nav(
    ts_code='005827.OF',
    start_date='20260301',
    end_date='20260413',
)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| ts_code | str | 基金代码（必须带 .OF） |
| start_date | str | 起始日期 YYYYMMDD |
| end_date | str | 结束日期 YYYYMMDD |
| nav_date | str | 精确查某一天 |
| market | str | E/O 可选 |

**关键输出字段：**

| 字段 | 类型 | 说明 | 实测备注 |
|------|------|------|----------|
| nav_date | str | 净值日期 YYYYMMDD | 需要 pd.to_datetime 转换 |
| unit_nav | float | 单位净值 | 对应我们的 `nav` 字段 |
| accum_nav | float | 累计净值 | 含分红再投资 |
| adj_nav | float | 复权单位净值 | 有时为空，可用 accum_nav 代替 |
| accum_div | float | 累计分红 | |
| net_asset | float | 资产净值 | |
| total_netasset | float | 合计资产净值 | |

**积分要求：** 2000

**踩坑：**
- 单次最大 2000 行，单基金 150 天够用
- `adj_nav` 字段有时为空，代码中做了 fallback 到 `accum_nav`
- 返回数据默认**降序**（最新在前），需要 `.sort_values("date")` 升序排列
- 当日净值通常要等晚上 8-9 点才更新

---

### 3. fund_portfolio — 公募基金持仓

```python
df = pro.fund_portfolio(ts_code='005827.OF')
```

| 参数 | 类型 | 说明 |
|------|------|------|
| ts_code | str | 基金代码 |
| ann_date | str | 公告日期 |
| period | str | 季度（如 20251231 表示 Q4） |
| start_date | str | 报告期起始 |
| end_date | str | 报告期结束 |

**关键输出字段：**

| 字段 | 类型 | 说明 | 实测备注 |
|------|------|------|----------|
| symbol | str | 股票代码 | **带后缀**如 `600519.SH`、`0700.HK` |
| mkv | float | 持有市值（元） | |
| amount | float | 持有数量（股） | 注意单位是股，不是万股 |
| stk_mkv_ratio | float | 占股票市值比（%） | 不是占基金净值比，但可作为权重近似 |
| stk_float_ratio | float | 占流通股本比（%） | |
| end_date | str | 持仓截止日期 | 用于取最新一期 |

**积分要求：** 5000

**踩坑：**
- **symbol 字段带后缀**（600519.SH），不是纯 6 位码
- 包含港股持仓（如 0700.HK），stock_basic 查不到港股名称
- `stk_mkv_ratio` 是占"股票市值"比，不是占"基金净值"比，但勉强可用
- amount 单位是"股"，我们的 Holding 模型用"万股"，需要 /10000
- 多期数据混在一起，要按 `end_date` 取最新期

---

### 4. stock_basic — A 股股票列表（辅助）

```python
df = pro.stock_basic(exchange='', list_status='L', fields='ts_code,name')
```

用于给 fund_portfolio 的持仓补充股票名称。

**踩坑：**
- 只有 A 股数据，港股（0700.HK 等）查不到名称
- 返回约 5500 只 A 股（11000 个 key 因为双存 600519 和 600519.SH）

---

## 未使用但已知的 API

| API | 说明 | 积分 | 备注 |
|-----|------|------|------|
| fund_daily | ETF 场内日线行情 | 5000 | 只有场内 ETF，场外基金无此数据 |
| fund_share | 基金份额/规模 | 2000 | 可查 ETF 申赎规模变化 |
| fund_adj | 基金复权因子 | 2000 | 可用于计算精确复权净值 |
| fund_company | 基金管理人列表 | 1500 | |

---

## tushare vs akshare 对照

| 维度 | tushare Pro | akshare |
|------|-------------|---------|
| 数据源 | 付费 API（规范 SLA） | 爬东方财富（免费但不稳定） |
| 基金代码格式 | `005827.OF` | `005827` |
| 日期格式 | `YYYYMMDD` 字符串 | 混乱（有 datetime 有字符串） |
| 列名稳定性 | 固定英文字段名 | 中文列名，版本间可能变 |
| 申购限额 | 无（只有 status 字段） | 有 fund_purchase_em 完整数据 |
| 基金经理 | 无（只有 management 公司名） | 有个人姓名 |
| 行业配置 | 无直接接口 | fund_portfolio_industry_allocation_em |
| 当日涨跌幅 | 从 fund_nav 计算 | fund_open_fund_daily_em 批量获取 |
| 限速 | 积分制，按分钟控频 | 爬虫式，太快封 IP |

---

## 代码格式转换

```python
# 内部代码 → tushare ts_code
def _to_ts_code(code: str) -> str:
    return f"{code}.OF" if "." not in code else code

# tushare ts_code → 内部代码
def _from_ts_code(ts_code: str) -> str:
    return ts_code.split(".")[0]
```
