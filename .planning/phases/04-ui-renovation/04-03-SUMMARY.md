# 04-03 Summary: 全局体验优化 + 移动端适配 + 质量门禁

**Plan:** 04-03
**Status:** ✅ COMPLETE
**Date:** 2026-04-21
**Branch:** feat/ui-components

---

## 交付清单

### 1. ErrorBoundary — 全局渲染错误捕获
- **文件:** `src/components/design-system/ErrorBoundary.tsx`
- **功能:** Class component 捕获子树 render 错误，防止整站白屏
- **UI:** 使用 Surface + AlertTriangle + TextButton，提供"刷新页面"和"返回首页"操作
- **集成:** `__root.tsx` 中包裹 `<Outlet />`

### 2. Toast 通知系统
- **文件:**
  - `src/hooks/useToast.tsx` (由 `.ts` 重命名，含 JSX)
  - `src/components/design-system/Toast.tsx`
- **功能:** React Context 驱动，支持 `success`/`error`/`info` 三类型，自动消失（4s），Framer Motion 动画
- **reduced-motion:** 通过 `useReducedMotion()` 禁用动画，直接淡入淡出
- **集成:** `ToastProvider` 包裹根布局，`ToastContainer` 固定定位在 bottom-right

### 3. 页面级 API 错误处理改造
所有页面将 API `error` 从"全页红色错误块"改造为"Toast 通知 + 空数据渲染"：

| 页面 | 文件 | 改造内容 |
|------|------|----------|
| 仪表盘 | `routes/index.tsx` | `statsError` / `screeningError` → toast |
| 基金列表 | `routes/funds/index.tsx` | `error` → toast + 空表格 |
| 筛选结果 | `routes/screening/index.tsx` | `error` → toast + 空结果 |
| 基金详情 | `routes/funds/$code.tsx` | `detailError` → toast；保留 `!fund` 独立 not-found 页面 |
| 策略回测 | `routes/backtest/index.tsx` | `error` → toast；移除内联错误 div |

### 4. 移动端响应式适配
- **侧边栏抽屉:** `__root.tsx` 新增 `mobileMenuOpen` state，小屏幕下 sidebar 变为 fixed 抽屉，点击 overlay 或菜单项后自动关闭
- **汉堡菜单:** header 左侧显示 Menu 图标按钮（仅 lg 以下屏幕）
- **FundTable 横向滚动:** `FundTable.tsx` 包裹 `<div className="overflow-x-auto">`
- **页面 padding 响应式:** `p-4 lg:p-6`
- **Stepper 适配:** backtest 页 step title 在 sm 以下屏幕隐藏

### 5. Reduced Motion 支持
- `PageTransition` — 已支持
- `Toast` — 已支持（无动画直接显隐）
- `FundTable` / `HoldingsList` — 已支持（Framer Motion 动画在 reduced-motion 下自动降级）

### 6. ESLint 颜色纪律规则
- **规则:** `no-restricted-syntax` 禁止所有硬编码 Tailwind 颜色类（`bg-white`、`text-gray-500` 等）
- **修复范围:** 16 处违规，涉及 `badge.tsx`、`button.tsx`、`IconButton.tsx`、`TextButton.tsx`、`__root.tsx`、`backtest/index.tsx`
- **修复策略:**
  - 深色背景上的白色文字 → `text-[var(--text-inverse)]`
  - shadcn destructive 变体 → `text-destructive-foreground`
  - overlay 背景 → `bg-[var(--overlay-backdrop)]`
  - stepper 高亮圆圈 → 新增语义 token `--highlight-on-accent`

### 7. 关键 Bug 修复
| Bug | 文件 | 修复 |
|-----|------|------|
| `React.useState` 未导入 | `__root.tsx` | 添加 `import { useState }` |
| `useToast.ts` ESLint 解析失败 | `hooks/useToast.ts` | 重命名为 `useToast.tsx`（含 JSX） |

---

## 新增/修改的文件

```
web/src/components/design-system/ErrorBoundary.tsx   (+)
web/src/components/design-system/Toast.tsx            (+)
web/src/hooks/useToast.tsx                            (重命名自 .ts)
web/src/styles/tokens.semantic.css                    (+ --highlight-on-accent)
web/src/routes/__root.tsx                             (重构)
web/src/routes/index.tsx                              (+ toast 错误处理)
web/src/routes/funds/index.tsx                        (+ toast 错误处理)
web/src/routes/funds/$code.tsx                        (+ toast 错误处理)
web/src/routes/screening/index.tsx                    (+ toast 错误处理)
web/src/routes/backtest/index.tsx                     (+ toast 错误处理, 多处 text-white 修复)
web/src/components/views/FundTable.tsx                (+ overflow-x-auto)
web/src/components/views/HoldingsList.tsx             (- 未使用 stagger import)
web/src/components/views/ChartContainer.tsx           (- 未使用 chartDown)
web/src/components/design-system/IconButton.tsx       (text-white → text-inverse)
web/src/components/design-system/TextButton.tsx       (text-white → text-inverse)
web/src/components/ui/badge.tsx                       (text-white → destructive-foreground)
web/src/components/ui/button.tsx                      (text-white → destructive-foreground)
web/eslint.config.js                                  (+ no-restricted-syntax 颜色纪律规则)
```

---

## 验证结果

- ✅ `bun run lint` — 零错误、零警告
- ✅ `bunx tsc --noEmit` — TypeScript 编译通过

---

## 待办（后续 Phase）

- [ ] 暗色模式下 `--highlight-on-accent: rgba(255,255,255,0.2)` 在橙色按钮上对比度需主人视觉确认
- [ ] 移动端 drawer 的 swipe-to-close（可选增强）
