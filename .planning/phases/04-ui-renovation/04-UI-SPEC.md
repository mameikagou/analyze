# Phase 4: UI Design Contract — UI Renovation

**Phase:** 04-ui-renovation
**Date:** 2026-04-21
**Source:** User directive + capabilities.md analysis

---

## 1. Design Philosophy

**Claude.ai 风格：** 暖灰底色（Stone）+ 多层级的表面（Surface）+ 极细的边框（Subtle Border）+ 极其克制的投影。

**核心原则：**
- 颜色全部走 Token，禁止硬编码
- 动画克制但流畅，尊重 reduced-motion
- 组件统一走 Surface / shadcn，禁止裸 div 做卡片

---

## 2. Color System

### 2.1 Token 三层架构（已存在，需修复）

**Primitive:** `tokens.primitive.css` — Stone 调色板 + 强调色
**Semantic:** `tokens.semantic.css` — 背景/文字/边框梯度，暗色模式映射
**Component:** `tokens.component.css` — 组件级特例

### 2.2 修复目标

shadcn HSL Token（冷灰调）与 Stone hex Token（暖灰调）在暗色模式下值不一致：
- shadcn dark `--background` → `#020617`（深蓝灰）
- Claude dark `--bg-canvas` → `#0c0a09`（暖灰 Stone-950）

**修复方案：** 让 shadcn HSL 变量映射到 Stone 的 HSL 值，统一为暖灰调。

### 2.3 颜色纪律（强制执行）

| 禁止 | 替代 |
|------|------|
| `bg-white` | `bg-[var(--bg-surface)]` |
| `bg-gray-*` | `bg-[var(--bg-canvas)]` 或 Semantic Token |
| `text-gray-*` | `text-[var(--text-primary/secondary/muted)]` |
| `#FFF`, `#fff` | `var(--bg-surface)` |
| `rgb(...)`, `hsl(...)` | 对应 Semantic Token |

---

## 3. Typography

| Token | 值 | 用途 |
|-------|-----|------|
| `--font-size-2xs` | 11px | 极小标签 |
| `--font-size-xs` | 12px | 标签、辅助文字 |
| `--font-size-sm` | 14px | 次要正文 |
| `--font-size-base` | 15px | 默认正文（Claude 正文） |
| `--font-size-lg` | 18px | 小标题 |
| `--font-size-xl` | 20px | 卡片标题 |
| `--font-size-2xl` | 24px | 页面标题 |

---

## 4. Spacing

| Token | 值 | 用途 |
|-------|-----|------|
| `--space-4` | 16px | 卡片内边距基础 |
| `--space-5` | 20px | 卡片内边距宽松 |
| `--space-6` | 24px | 板块间距 |
| `--space-8` | 32px | 大板块间距 |

---

## 5. Border Radius

| Token | 值 | 用途 |
|-------|-----|------|
| `--radius-md` | 8px | 按钮、小卡片 |
| `--radius-lg` | 12px | 中等卡片 |
| `--radius-xl` | 16px | 大卡片、面板 |
| `--radius-2xl` | 24px | 输入框（Claude 风格） |
| `--radius-full` | 9999px | 按钮 pill 形状 |

**规范：**
- 大卡片优先 `rounded-xl`
- 按钮和 badge 用 `rounded-full` 或 `rounded-md`

---

## 6. Shadow

Claude 极少用阴影，基本只有 elevated 面板需要：

| Token | 值（Light） | 值（Dark） | 用途 |
|-------|-------------|------------|------|
| `--shadow-elevated` | `0 4px 24px rgba(0,0,0,0.08)` | `0 4px 24px rgba(0,0,0,0.4)` | 弹层面板 |
| `--shadow-dropdown` | `0 8px 32px rgba(0,0,0,0.12)` | `0 8px 32px rgba(0,0,0,0.5)` | 下拉菜单 |

---

## 7. Animation

### 7.1 页面切换
- **库：** Framer Motion
- **效果：** `opacity 0→1` + `y: 8→0`，duration 200ms，ease-out
- **包裹：** `<Outlet>` 顶级布局

### 7.2 Hover 过渡
- **所有可交互元素：** `transition-colors duration-200 ease-out`
- **Sidebar nav：** hover 背景色过渡
- **Link：** hover 颜色过渡

### 7.3 Loading
- **统一：** `Loader2` spinner + skeleton 骨架屏
- **所有页面**必须有 loading 状态，不能白屏

### 7.4 Reduced Motion
```css
@media (prefers-reduced-motion: reduce) {
  * { transition: none !important; animation: none !important; }
}
```

---

## 8. Component Patterns

### 8.1 Surface（容器唯一入口）

```tsx
// ✅ 正确
<Surface variant="surface" bordered rounded="xl" className="p-5">
  卡片内容
</Surface>

// ❌ 错误
<div className="bg-white rounded-xl p-5">...</div>
```

**variant 层级：**
- `canvas` → 页面最底层底色
- `surface` → 卡片、面板（默认）
- `elevated` → 弹层、下拉（带阴影）

### 8.2 StatsCard

```tsx
<StatsCard
  title="总收益率"
  value={`${stats?.totalReturn?.toFixed(2) ?? '—'}%`}
  trend="up" | "down" | "neutral"
  icon={TrendingUp}
  sparkline={sparklineData} // 新增：迷你走势图
/>
```

### 8.3 Form Controls

回测页配置表单从 4 列网格改成交互式 stepper/wizard：
- 步骤 1：策略选择（因子 + 信号过滤）
- 步骤 2：持仓配置（topN + 调仓频率 + 权重）
- 步骤 3：回测参数（费率 + 日期范围 + 市场）
- 步骤 4：确认运行

---

## 9. Chart Design

### 9.1 回测页 — LightweightChart

| 元素 | 规范 |
|------|------|
| 净值曲线 | 主色线（orange-500），2px |
| 回撤区域 | 红色填充，透明度 15% |
| 网格线 | 极淡，border-subtle |
| 十字线 | 细线，显示具体数值 |
| Tooltip | 深色背景，白色文字，圆角 |

### 9.2 其他页面 — Canvas（保留）

保持现有 Canvas 实现，暗色模式下调整颜色。

---

## 10. Dark Mode

### 10.1 切换机制
- Toggle 位置：`__root.tsx` header 右侧
- 图标：Sun / Moon（lucide-react）
- 持久化：`localStorage.theme`
- 初始化：检测 `prefers-color-scheme`

### 10.2 切换方式
```ts
document.documentElement.classList.toggle('dark')
```

### 10.3 暗色模式值映射（关键）

| Light | Dark |
|-------|------|
| `--bg-canvas: #fafaf9` | `--bg-canvas: #0c0a09` |
| `--bg-surface: #ffffff` | `--bg-surface: #1c1917` |
| `--bg-elevated: #ffffff` | `--bg-elevated: #292524` |
| `--text-primary: #1c1917` | `--text-primary: #fafaf9` |
| `--text-secondary: #57534e` | `--text-secondary: #d6d3d1` |
| `--text-muted: #78716c` | `--text-muted: #a8a29e` |
| `--border-subtle: #e7e5e4` | `--border-subtle: #292524` |

---

## 11. Responsive Breakpoints

| 断点 | 范围 | 布局调整 |
|------|------|---------|
| Mobile | < 768px | Sidebar 隐藏 → hamburger menu；表格横向滚动；单列布局 |
| Tablet | 768px ~ 1024px | Sidebar 可折叠；2列网格 |
| Desktop | > 1024px | Sidebar 展开；4列网格 |

---

## 12. Accessibility

- 所有交互元素有 focus ring（`--ring-focus`）
- 颜色对比度符合 WCAG AA
- `prefers-reduced-motion` 支持
- 表单有 label 关联

---

*UI-SPEC: 04-ui-renovation*
*Created: 2026-04-21*
