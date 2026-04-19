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

import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { Loader2, AlertCircle } from 'lucide-react'
import { useScreening } from '@/hooks/api'
import { ScreeningResultItem } from '@/components/views/ScreeningResultItem'
import { StatsCard } from '@/components/views/StatsCard'

export const Route = createFileRoute('/screening/')({
  component: ScreeningPage,
})

function ScreeningPage() {
  const navigate = useNavigate()
  const { data: response, isLoading, error } = useScreening({ limit: 50 })

  const screeningDate = response?.data?.screening_date ?? ''
  const results = response?.data?.results ?? []
  const count = response?.data?.count ?? 0

  // 计算平均分和最高分
  const avgScore = results.length > 0
    ? results.reduce((s, f) => s + (f.score ?? 0), 0) / results.length
    : 0
  const topFund = results[0]

  /* ── 加载中 ────────────────────────────────────────────── */
  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-3">
        <Loader2 className="h-8 w-8 animate-spin text-[var(--text-muted)]" />
        <p className="text-sm text-[var(--text-muted)]">加载筛选结果...</p>
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
          筛选结果
        </h2>
        <p className="text-sm text-[var(--text-muted)]">
          MA 均线多头排列 + 量化打分排名 — {screeningDate || '—'}
        </p>
      </div>

      {/* 统计卡片 */}
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

      {/* 筛选结果列表 */}
      <div className="space-y-2">
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
    </div>
  )
}
