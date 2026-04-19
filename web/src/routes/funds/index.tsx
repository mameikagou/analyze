/**
 * 基金列表页 — /funds/
 *
 * 职责：展示全市场基金基础信息列表，支持行点击跳转详情页。
 * 零样式页面，只负责数据获取和组件组合。
 *
 * 修改说明（2026-04-19）：
 *   - 从 legacy hooks/useFunds（mock 数据）迁移到 hooks/api/useFunds（真实 API）。
 *   - 数据契约变化：Fund[]（含 MA 指标）→ PaginatedFundsResponse（FundSummary[]，仅 code/name/market）。
 *   - MA 指标移至筛选页（/screening）展示，列表页保持简洁。
 *   - 使用 FundTable 组件（已适配 FundSummary[]），添加 onRowClick 跳转详情。
 *   - 保留分页结构（当前展示全部，分页 UI 后续补充）。
 *   - 潜在副作用：legacy hooks/useFunds.ts 不再被引用，后续可安全删除。
 */

import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { Loader2, AlertCircle } from 'lucide-react'
import { useFunds } from '@/hooks/api'
import { FundTable } from '@/components/views/FundTable'

export const Route = createFileRoute('/funds/')({
  component: FundsPage,
})

function FundsPage() {
  const navigate = useNavigate()
  const { data: response, isLoading, error } = useFunds({ page: 1, pageSize: 100 })

  const funds = response?.data ?? []

  /* ── 加载中 ────────────────────────────────────────────── */
  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-3">
        <Loader2 className="h-8 w-8 animate-spin text-[var(--text-muted)]" />
        <p className="text-sm text-[var(--text-muted)]">加载基金列表...</p>
      </div>
    )
  }

  /* ── 错误 ──────────────────────────────────────────────── */
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-3">
        <AlertCircle className="h-8 w-8 text-[var(--red-600)]" />
        <p className="text-sm text-[var(--text-muted)]">加载失败，请稍后重试</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* 标题 */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-[var(--text-primary)]">
          基金列表
        </h2>
        <p className="text-sm text-[var(--text-muted)]">
          全市场基金基础信息一览 — 共 {funds.length} 只
        </p>
      </div>

      {/* 基金表格 */}
      <FundTable
        funds={funds}
        onRowClick={(code) => {
          navigate({ to: '/funds/$code', params: { code } })
        }}
      />
    </div>
  )
}
