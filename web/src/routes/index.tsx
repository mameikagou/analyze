/**
 * 仪表盘页 — /
 *
 * 职责：展示全市场基金趋势概览。
 * 数据来自真实 API（useStats + useScreening），零样式页面。
 *
 * 【2026-04-26 重构说明】
 * 按 Phase 4.5 Style Contract 翻新为 Research Dashboard Page archetype：
 *   - 使用 PageShell + PageHeader 替换裸写标题区
 *   - StatsCard 行作为 InsightStrip，保留现有 4 张统计卡片
 *   - ScreeningResultItem 列表作为 MainSurface，统一 Surface 容器
 *   - 保持数据流不变（useStats + useScreening）
 *
 * 副作用：
 *   - 引入 PageShell / PageHeader 依赖（04.5-01 已创建）
 *   - 无行为变更，纯视觉层统一
 */

import { useEffect } from 'react'
import { createFileRoute, Link } from '@tanstack/react-router'
import { Database, Filter, TrendingUp, Activity, Loader2, ArrowRight } from 'lucide-react'
import { useStats, useScreening } from '@/hooks/api'
import { useToast } from '@/hooks/useToast'
import { PageShell } from '@/components/ui/page-shell'
import { PageHeader } from '@/components/ui/page-header'
import { Surface } from '@/components/design-system/Surface'
import { StatsCard } from '@/components/views/StatsCard'
import { ScreeningResultItem } from '@/components/views/ScreeningResultItem'

export const Route = createFileRoute('/')({
  component: DashboardPage,
})

function DashboardPage() {
  const { data: stats, isLoading: statsLoading, error: statsError } = useStats()
  const { data: screeningData, isLoading: screeningLoading, error: screeningError } = useScreening({ limit: 10 })
  const { toast } = useToast()

  // API 错误通过 Toast 通知，页面继续渲染空数据
  useEffect(() => {
    if (statsError) {
      toast({ type: 'error', message: `加载统计数据失败: ${statsError.message}` })
    }
    if (screeningError) {
      toast({ type: 'error', message: `加载筛选数据失败: ${screeningError.message}` })
    }
  }, [statsError, screeningError, toast])

  const isLoading = statsLoading || screeningLoading

  if (isLoading) {
    return (
      <PageShell>
        <div className="flex flex-col items-center justify-center py-20 gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-[var(--text-muted)]" />
          <p className="text-sm text-[var(--text-muted)]">加载仪表盘数据...</p>
        </div>
      </PageShell>
    )
  }

  const screeningResults = screeningData?.data?.results ?? []
  const screeningDate = screeningData?.data?.screening_date ?? ''

  return (
    <PageShell>
      <PageHeader
        eyebrow="FUND SCREENER"
        title="全市场趋势筛选"
        description="今天有哪些基金通过趋势筛选，以及数据湖当前状态。"
        actions={
          <Link
            to="/screening"
            className="inline-flex items-center gap-1.5 text-sm text-[var(--accent-primary)] hover:underline"
          >
            查看全部
            <ArrowRight className="h-4 w-4" />
          </Link>
        }
      />

      {/* InsightStrip — 统计卡片 */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatsCard
          title="总基金数"
          value={stats?.totalFunds ?? 0}
          subtitle={`CN: ${stats?.fundsByMarket?.CN ?? 0} / US: ${stats?.fundsByMarket?.US ?? 0} / HK: ${stats?.fundsByMarket?.HK ?? 0}`}
          icon={Database}
        />
        <StatsCard
          title="今日通过 MA"
          value={stats?.latestScreeningCount ?? 0}
          subtitle={stats?.latestScreeningDate ?? '—'}
          icon={Filter}
          trend={stats?.latestScreeningAvgMaDiff && stats.latestScreeningAvgMaDiff > 0 ? 'up' : 'neutral'}
          trendValue={stats?.latestScreeningAvgMaDiff ? `avg +${stats.latestScreeningAvgMaDiff}%` : undefined}
        />
        <StatsCard
          title="数据湖记录"
          value={formatNumber(stats?.totalNavRecords ?? 0)}
          subtitle={stats?.navDateRange?.[0] && stats?.navDateRange?.[1]
            ? `${stats.navDateRange[0]} ~ ${stats.navDateRange[1]}`
            : '—'}
          icon={Activity}
        />
        <StatsCard
          title="数据库大小"
          value={`${(stats?.dbSizeMb ?? 0).toFixed(1)} MB`}
          subtitle="SQLite 本地数据湖"
          icon={TrendingUp}
        />
      </div>

      {/* MainSurface — 今日筛选 Top 10 */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--text-muted)]">
              今日筛选 Top 10
            </h2>
            <p className="text-sm text-[var(--text-muted)]">
              MA 均线多头排列 — {screeningDate}
            </p>
          </div>
          <Link
            to="/screening"
            className="text-sm text-[var(--accent-primary)] hover:underline"
          >
            查看全部 →
          </Link>
        </div>

        <Surface variant="surface" bordered rounded="lg" className="divide-y divide-[var(--border-subtle)]">
          {screeningResults.length === 0 ? (
            <div className="py-8 text-center">
              <p className="text-sm text-[var(--text-muted)]">暂无筛选数据</p>
            </div>
          ) : (
            screeningResults.map((item) => (
              <ScreeningResultItem
                key={item.code}
                item={item}
                onClick={(code) => {
                  window.location.href = `/funds/${code}`
                }}
              />
            ))
          )}
        </Surface>
      </div>
    </PageShell>
  )
}

/** 格式化大数字 */
function formatNumber(n: number): string {
  if (n >= 10000) {
    return `${(n / 10000).toFixed(1)}万`
  }
  return String(n)
}
