/**
 * 基金列表页 — /funds/
 *
 * 职责：展示全市场基金基础信息列表，支持行点击跳转详情页。
 * 零样式页面，只负责数据获取和组件组合。
 *
 * 【2026-04-26 重构说明】
 * 按 Phase 4.5 Style Contract 翻新为 Archive List Page archetype：
 *   - 使用 PageShell + PageHeader 替换裸写标题区
 *   - FundTable 包在 ArchiveTable 内，统一档案列表容器
 *   - 保持数据流不变（useFunds hook、分页参数、跳转行为）
 *
 * 副作用：
 *   - 引入 PageShell / PageHeader / ArchiveTable 依赖（04.5-01 已创建）
 *   - 无行为变更，纯视觉层统一
 */

import { useEffect } from 'react'
import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { Loader2 } from 'lucide-react'
import { useFunds } from '@/hooks/api'
import { useToast } from '@/hooks/useToast'
import { FundTable } from '@/components/views/FundTable'
import { ArchiveTable } from '@/components/ui/archive-table'
import { PageHeader } from '@/components/ui/page-header'
import { PageShell } from '@/components/ui/page-shell'

export const Route = createFileRoute('/funds/')({
  component: FundsPage,
})

function FundsPage() {
  const navigate = useNavigate()
  const { data: response, isLoading, error } = useFunds({ page: 1, pageSize: 100 })
  const { toast } = useToast()

  const funds = response?.data ?? []

  // API 错误通过 Toast 通知，页面继续渲染空数据
  useEffect(() => {
    if (error) {
      toast({ type: 'error', message: `加载基金列表失败: ${error.message}` })
    }
  }, [error, toast])

  /* ── 加载中 ────────────────────────────────────────────── */
  if (isLoading) {
    return (
      <PageShell>
        <div className="flex flex-col items-center justify-center py-20 gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-[var(--text-muted)]" />
          <p className="text-sm text-[var(--text-muted)]">加载基金列表...</p>
        </div>
      </PageShell>
    )
  }

  return (
    <PageShell>
      <PageHeader
        eyebrow="FUND ARCHIVE"
        title="基金档案馆"
        description="浏览全市场基金与 ETF，按市场、趋势和申购状态筛选候选标的。"
        statusSummary={`共 ${funds.length} 只基金`}
      />

      <ArchiveTable>
        <FundTable
          funds={funds}
          unstyled
          onRowClick={(code) => {
            navigate({ to: '/funds/$code', params: { code } })
          }}
        />
      </ArchiveTable>
    </PageShell>
  )
}
