/**
 * 筛选结果页 — /screening/
 *
 * 职责：展示 MA 均线多头排列的基金筛选结果，按综合评分排名。
 * 零样式页面，只负责数据获取和组件组合。
 *
 * 修改说明（2026-04-19）：
 *   - 从 legacy hooks/useFunds（mock 数据，前端过滤）迁移到 hooks/api/useScreening（真实 API，后端已过滤）。
 *   - ScreeningResultItem 组件替换手动列表渲染，统一样式和交互。
 *   - 统计卡片从手动计算改为直接读取 screening API 返回的 count 和结果。
 *   - 潜在副作用：筛选结果依赖后端 screening_results 表数据，如果表空则显示"暂无筛选数据"。
 */

import { useEffect } from 'react'
import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { Loader2 } from 'lucide-react'
import { useScreening } from '@/hooks/api'
import { useToast } from '@/hooks/useToast'
import { ScreeningResultItem } from '@/components/views/ScreeningResultItem'
import { StatsCard } from '@/components/views/StatsCard'
import { ArchiveTable } from '@/components/ui/archive-table'
import { PageHeader } from '@/components/ui/page-header'
import { PageShell } from '@/components/ui/page-shell'

export const Route = createFileRoute('/screening/')({
  component: ScreeningPage,
})

function ScreeningPage() {
  const navigate = useNavigate()
  const { data: response, isLoading, error } = useScreening({ limit: 50 })
  const { toast } = useToast()

  const screeningDate = response?.data?.screening_date ?? ''
  const results = response?.data?.results ?? []
  const count = response?.data?.count ?? 0

  // 计算平均分和最高分
  const avgScore = results.length > 0
    ? results.reduce((s, f) => s + (f.score ?? 0), 0) / results.length
    : 0
  const topFund = results[0]

  // API 错误通过 Toast 通知，页面继续渲染空数据
  useEffect(() => {
    if (error) {
      toast({ type: 'error', message: `加载筛选结果失败: ${error.message}` })
    }
  }, [error, toast])

  /* ── 加载中 ────────────────────────────────────────────── */
  if (isLoading) {
    return (
      <PageShell>
        <div className="flex flex-col items-center justify-center py-20 gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-[var(--text-muted)]" />
          <p className="text-sm text-[var(--text-muted)]">加载筛选结果...</p>
        </div>
      </PageShell>
    )
  }

  return (
    <PageShell>
      <PageHeader
        eyebrow="Archive List"
        title="筛选结果"
        description={`MA 均线多头排列 + 量化打分排名 — ${screeningDate || '—'}`}
        statusSummary={`当前命中 ${count} 只基金，平均分 ${avgScore > 0 ? avgScore.toFixed(1) : '—'}`}
      />

      <div className="grid gap-4 md:grid-cols-3">
        <StatsCard
          title="通过 MA 筛选"
          value={count}
          subtitle="MA20 > MA60"
          trend="up"
        />
        <StatsCard
          title="平均分"
          value={avgScore > 0 ? avgScore.toFixed(1) : '-'}
          subtitle="综合评分"
          trend="neutral"
        />
        <StatsCard
          title="最高分"
          value={topFund?.score ?? '-'}
          subtitle={topFund?.name ?? ''}
          trend="up"
        />
      </div>

      <ArchiveTable>
        <div className="space-y-2 p-3">
          {results.length === 0 ? (
            <p className="text-sm text-[var(--text-muted)] py-8 text-center">
              暂无筛选数据
            </p>
          ) : (
            results.map((item) => (
              <ScreeningResultItem
                key={item.code}
                item={item}
                onClick={(code) => {
                  navigate({ to: '/funds/$code', params: { code } })
                }}
              />
            ))
          )}
        </div>
      </ArchiveTable>
    </PageShell>
  )
}
