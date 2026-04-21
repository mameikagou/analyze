# Review: Frontend Backtest Page

## Summary
- **文件数**: 5 (4 个手写的 + 1 个生成的)
- **问题总数**: 9 (Critical: 1, High: 1, Medium: 3, Low: 2, Info: 2)
- **总体评价**: flag — 存在 1 个 Critical Bug 会导致运行时 crash，以及若干类型安全和代码质量问题，必须在合并前修复。

---

## Findings

### [critical] [bug] — `EquityCurveChart` canvas 尺寸在 Retina/HiDPI 屏上模糊且可能绘制异常
- **文件**: `web/src/routes/backtest/index.tsx:386-393`
- **问题**: Canvas 固定写死 `width={800} height={300}`，没有处理 `devicePixelRatio`。在 Retina 屏（DPR=2）上，canvas 实际像素只有 CSS 尺寸的一半，导致图表模糊。更严重的是，如果父容器宽度小于 800px，`className="w-full"` 会让 CSS 宽度缩小，但 canvas 内部坐标系仍是 800px，绘制内容会被截断或变形。
- **建议**:
  ```tsx
  // 在 useEffect 中动态设置 canvas 尺寸
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const rect = canvas.getBoundingClientRect()
    const dpr = window.devicePixelRatio || 1
    canvas.width = rect.width * dpr
    canvas.height = rect.height * dpr
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.scale(dpr, dpr)
    // ... 后续绘制代码使用 CSS 像素坐标
  }, [])
  ```
  或者改用响应式 chart 库（如 recharts）替代手写 canvas。
- **原因**: Canvas 的 `width/height` 属性控制内部像素缓冲区，CSS 的 `width/height` 控制显示尺寸。两者不一致时，浏览器会自动缩放，导致模糊和变形。这是 canvas 使用的经典陷阱。

---

### [high] [type-safety] — `useBacktest` 未做 API 响应的 `success` 字段校验，与 `useFundDetail` 模式不一致
- **文件**: `web/src/hooks/api/useBacktest.ts:62-77`
- **问题**: `runBacktest` 直接 `return apiPost<BacktestResponse>(...)`，没有对 `res.success` 做校验。对比 `useFundDetail`（`if (!res.success) return null`），这里如果后端返回 `success: false`，页面层会把它当成成功数据处理，导致 `result.data` 为 `null` 时下游的 `stats?.totalReturn?.toFixed(2)` 全部显示为 `"—"`，但用户看不到任何错误提示。
- **建议**:
  ```ts
  async function runBacktest(request: BacktestRequest): Promise<BacktestResult> {
    const body = { /* ... */ }
    const res = await apiPost<BacktestResponse>('/api/backtest/run', body)
    if (!res.success || !res.data) {
      throw new Error(res.error || '回测执行失败')
    }
    return res.data
  }

  export function useBacktest() {
    return useMutation({
      mutationFn: runBacktest,
    })
  }
  ```
  同时调整 hook 返回类型，让 `data` 直接是 `BacktestResult | undefined`，省去页面层到处 `result?.data?.stats` 的繁琐。
- **原因**: 与 Phase 2 建立的 hook 模式不一致。`useFundDetail` 和 `useFunds` 都校验了 `success` 字段并做了错误转换。`useBacktest` 跳过这一步会让错误处理链断裂。

---

### [medium] [bug] — `EquityCurveChart` 中 `dates.length === 1` 时除以零导致 `NaN` 坐标
- **文件**: `web/src/routes/backtest/index.tsx:347, 363, 380`
- **问题**: 多处使用 `dates.length - 1` 作为除数：
  ```ts
  const x = padding.left + (chartW * i) / (dates.length - 1)
  ```
  如果 `dates` 只有一条数据（`length === 1`），除数为 0，所有 x 坐标变成 `NaN`，canvas 绘制失败。
- **建议**:
  ```ts
  const xCount = Math.max(dates.length - 1, 1)
  const x = padding.left + (chartW * i) / xCount
  ```
  或者提前处理 `dates.length <= 1` 的情况，直接显示 "数据点不足"。
- **原因**: 边界条件防御缺失。虽然回测通常返回大量数据点，但如果用户选择极短日期范围或后端异常，单点数据是可能的。

---

### [medium] [type-safety] — `RebalanceTable` 的 `data` prop 类型与 `BacktestResult` 中的 `RebalanceEntry` 不一致
- **文件**: `web/src/routes/backtest/index.tsx:396`
- **问题**: `RebalanceTable` 声明的 prop 类型是：
  ```ts
  { data: Array<{ date: string; holdings: Record<string, number> }> }
  ```
  但 `useBacktest.ts` 中定义的 `RebalanceEntry` 是：
  ```ts
  interface RebalanceEntry {
    date: string
    holdings: Record<string, number>
  }
  ```
  虽然结构碰巧一样，但组件内联定义了匿名类型，没有引用 `RebalanceEntry`。这违反了 DRY 原则，且如果后端改了字段名，只有 hook 里的类型会更新，组件里的不会。
- **建议**:
  ```ts
  import type { RebalanceEntry } from '@/hooks/api'

  function RebalanceTable({ data }: { data: RebalanceEntry[] }) { ... }
  ```
- **原因**: 类型定义应该单一来源。内联匿名类型是技术债务，维护成本随项目规模指数增长。

---

### [medium] [react] — `RebalanceTable` 中 `tbody` 内的 Fragment 缺少 `key`
- **文件**: `web/src/routes/backtest/index.tsx:414-445`
- **问题**:
  ```tsx
  {data.map((entry, idx) => {
    // ...
    return (
      <>
        <tr key={entry.date}>...</tr>
        {isExpanded && <tr>...</tr>}
      </>
    )
  })}
  ```
  外层 `<>` 没有 `key`，React 会报 `Each child in a list should have a unique "key" prop` warning。虽然内部 `tr` 有 key，但 Fragment 作为 map 的直接返回值时，React 的 reconciliation 会出问题。
- **建议**:
  ```tsx
  return (
    <Fragment key={entry.date}>
      <tr>...</tr>
      {isExpanded && <tr>...</tr>}
    </Fragment>
  )
  ```
  或者改用 `<tbody>` 嵌套结构（HTML5 允许一个 table 多个 tbody）。
- **原因**: React list rendering 的基本规则。虽然不会 crash，但会导致不必要的 DOM 重排和 console warning。

---

### [low] [ux] — 回测表单缺少日期合法性校验（startDate > endDate）
- **文件**: `web/src/routes/backtest/index.tsx:56-69`
- **问题**: `handleSubmit` 直接提交，没有校验 `startDate` 是否晚于 `endDate`。如果用户选错，后端会报错，但用户体验差。
- **建议**:
  ```ts
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (new Date(startDate) >= new Date(endDate)) {
      // 可以用一个本地 error state 显示，或者 toast
      alert('开始日期必须早于结束日期')
      return
    }
    runBacktest({ ... })
  }
  ```
- **原因**: 前端表单的基础 UX 防御。不要让明显错误的请求打到后端。

---

### [low] [code-quality] — `useBacktest` 的 `BacktestResponse` 类型设计冗余
- **文件**: `web/src/hooks/api/useBacktest.ts:41-45`
- **问题**:
  ```ts
  export interface BacktestResponse {
    success: boolean
    data: BacktestResult | null
    error?: string
  }
  ```
  这个类型和 `useFundDetail` 中的 `RawFundDetailResponse` 模式类似，但 `useBacktest` 没有走 "raw response → mapper → clean type" 的转换流程。实际上，如果 `success === false`，`data` 为 `null`，页面层还要额外判断。不如让 hook 内部消化掉这个 wrapper，直接返回 `BacktestResult` 或 throw。
- **建议**: 参考 `useFundDetail` 的模式，在 `runBacktest` 内部 unwrap response，hook 返回干净的业务类型。
- **原因**: 页面层不应该关心 API 的 wrapper 结构。`success/data/error` 是传输层细节，不是业务层语义。

---

### [info] [pattern] — `useBacktest` 使用 `useMutation` 但页面层没有处理 `onSuccess`/`onError` 回调
- **文件**: `web/src/hooks/api/useBacktest.ts:79-83`
- **问题**: Hook 只暴露了最基本的 `useMutation` 返回，没有封装 `onSuccess` toast 或 `onError` 统一处理。对比 `useScreening` 等 read-only query，mutation 更需要统一的成功/失败反馈。
- **建议**: 考虑在 hook 层或页面层增加 toast/notification 反馈。这不是 bug，是体验优化。
- **原因**: Mutation 操作（运行回测可能需要几秒）没有反馈会让用户以为点击没生效。

---

### [info] [code-quality] — `__root.tsx` 的 `navItems` 中 backtest 路由已添加，但缺少 `active` 状态的精确匹配处理
- **文件**: `web/src/routes/__root.tsx:12-18`
- **问题**: 导航项使用了 TanStack Router 的 `activeProps={{ className: 'active' }}` 和 CSS `[&.active]` 选择器，这是正确的。但注意 `to: '/backtest'` 和路由文件路径 `/backtest/` 的匹配行为——TanStack Router 的 `Link` 组件默认做前缀匹配，`/backtest` 和 `/backtest/` 在 `to` 属性上可能需要确认是否完全匹配。当前代码看起来工作正常，但这是一个容易出问题的点。
- **建议**: 确认 TanStack Router 版本的行为。如果升级到 v1 正式版，`activeOptions={{ exact: true }}` 可能需要显式设置。
- **原因**: 防御性检查，确保导航高亮行为在所有路由下一致。

---

## 正面评价

1. **hook 模式基本正确**: `useBacktest` 遵循了 "hooks/api/ 统一封装，页面层不直接调 client" 的架构约束，camelCase/snake_case 转换也做了。
2. **零样式页面**: `backtest/index.tsx` 确实没有写 CSS 文件，全部用 Tailwind utility classes，符合项目规范。
3. **类型导出完整**: `index.ts` barrel export 把 `useBacktest` 的所有相关类型都导出了，方便其他模块复用。
4. **表单可用性**: 所有 input 都有 `label` 关联，select/options 结构清晰，loading 状态有视觉反馈。
5. **Canvas 图表自包含**: 不引入外部 chart 库，减少了依赖体积，适合 MVP 阶段。

---

## 修复优先级

| 优先级 | 问题 | 文件 |
|--------|------|------|
| P0 | Canvas 模糊/变形 (Critical) | `backtest/index.tsx` |
| P1 | API success 校验缺失 (High) | `hooks/api/useBacktest.ts` |
| P2 | dates.length === 1 除以零 | `backtest/index.tsx` |
| P2 | RebalanceTable 类型内联 | `backtest/index.tsx` |
| P2 | Fragment 缺少 key | `backtest/index.tsx` |
| P3 | 日期合法性校验 | `backtest/index.tsx` |
| P3 | Response wrapper 冗余 | `hooks/api/useBacktest.ts` |
