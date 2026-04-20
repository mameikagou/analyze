# Python 编码规范 — Fund Screener

> 从已有代码中提炼的硬约束，新增模块必须遵守。

---

## 1. 文件头

```python
from __future__ import annotations
```

每份 `.py` 文件第一行必须是这个，启用 PEP 563 延迟注解求值，避免前向引用写字符串。

---

## 2. 类型注解 — 强制

所有函数参数和返回值必须写类型注解。不接受 `Any` 偷懒。

```python
# ✅
def compute(self, nav_panel: pd.DataFrame, **context) -> FactorOutput:

# ❌
def compute(self, nav_panel, **context):
```

复杂类型从 `typing` 导入：`Optional`, `Literal`, `Callable`, `Annotated` 等。

---

## 3. 不可变对象 — 默认 frozen

配置对象、契约对象、输出对象一律 `frozen=True`。

```python
@dataclass(frozen=True)
class BacktestConfig:
    top_n: int = 10
```

防止回测过程中被意外修改。mutable 是显式选择，必须写注释说明为什么。

---

## 4. 抽象基类 — 契约层

可扩展的组件（因子、策略、数据源）必须走 ABC。

```python
class BaseFactor(ABC):
    @abstractmethod
    def compute(self, nav_panel: pd.DataFrame, **context) -> FactorOutput: ...
```

**不许**用鸭子类型替代。ABC 是文档，是编译期检查，是 IDE 补全。

---

## 5. 面板级运算 — 禁止逐行循环

处理多基金时间序列时，必须用矩阵/面板运算，禁止 `for date in dates` 逐日循环。

```python
# ✅ 面板级 — 一次性算完所有日期、所有基金
ma = nav_panel.rolling(window=20).mean()

# ❌ 逐行 — 慢 100~1000 倍，且无法做 cross-sectional Z-Score
for code in nav_panel.columns:
    for i in range(len(nav_panel)):
        ...
```

唯一例外：`MaxDrawdownFactor` 的 O(n²) 实现，但必须在 docstring 里标注性能风险和优化路径。

---

## 6. NaN 语义 — 统一

| 场景 | NaN 的含义 | 处理方式 |
|------|-----------|----------|
| signal 因子 | 该基金该日不可交易 | `→ False`（显式） |
| score 因子 | 数据不足 | `→ NaN`（rolling 自动处理） |
| 权重矩阵 | 非调仓日 | `→ NaN`（vbt 忽略 = 保持持仓） |
| 空仓 | 全部清仓 | `→ 0.0`（vbt 卖出） |

---

## 7. 标量运算 — `math` 优先于 `np`

标量开方、对数等用 `math` 模块，与 `risk_metrics.py` 保持一致。

```python
import math

# ✅
sharpe = (mean / std) * math.sqrt(252)

# ❌
sharpe = (mean / std) * np.sqrt(252)
```

`np.sqrt` 留给数组运算。标量用 `math` 更快、类型更干净。

---

## 8. 导入容错 — 可选依赖

外部库（如 vectorbt）导入必须包 `try/except`，失败时给清晰提示。

```python
try:
    import vectorbt as vbt
except ImportError as e:
    raise ImportError(
        "vectorbt is required. Please run: uv add vectorbt==0.26.0\n"
        f"Original error: {e}"
    ) from e
```

---

## 9. 文档语言

- 模块/类/函数的 docstring：**中文**
- 代码注释：**中文**
- 变量名/函数名：**英文 snake_case**

```python
class BacktestEngine:
    """基于 vectorbt v1 的回测引擎。核心流程：..."""
```

---

## 10. SQL 参数化 — 防注入

SQL 查询中，用户输入的参数必须用 `?` 占位符。只允许 f-string 用于**受控字面量**（如 `"nav"` vs `"adj_nav"` 列名选择）。

```python
# ✅ 参数用 ?
cursor.execute("SELECT * FROM funds WHERE market = ?", (market,))

# ✅ f-string 仅用于受控字面量（非用户输入）
nav_col = "adj_nav" if use_adj_nav else "nav"
query = f"SELECT {nav_col} FROM nav_records WHERE ..."

# ❌ 永远不要这样
cursor.execute(f"SELECT * FROM funds WHERE market = '{market}'")
```

---

*Created: 2026-04-20 | Applies to: `src/fund_screener/` 下所有 Python 代码*
