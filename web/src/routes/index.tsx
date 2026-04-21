/**
 * 仪表盘页 — /
 *
 * 职责：展示全市场基金趋势概览。
 * 数据来自真实 API（useStats + useScreening），零样式页面。
 *
 * 修改说明（2026-04-19）：
 *   - 从全 mock 数据迁移到真实 API。
 *   - StatsCard 组件替换手动 Card，统一动画和样式。
 *   - 新增"今日筛选 Top 10"列表，展示最新筛选结果。
 *   - 移除 mock 净值走势图（无合适默认基金，后续可添加市场指数走势）。
 *   - 潜在副作用：首次加载时会有短暂的 loading 状态（API 请求）。
 */

import { useEffect } from 'react'
import { createFileRoute, Link } from '@tanstack/react-router'
import { Database, Filter, TrendingUp, Activity, Loader2 } from 'lucide-react'
import { useStats, useScreening } from '@/hooks/api'
import { useToast } from '@/hooks/useToast'
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
      <div className="flex flex-col items-center justify-center py-20 gap-3">
        <Loader2 className="h-8 w-8 animate-spin text-[var(--text-muted)]" />
        <p className="text-sm text-[var(--text-muted)]">加载仪表盘数据...</p>
      </div>
    )
  }

  const screeningResults = screeningData?.data?.results ?? []
  const screeningDate = screeningData?.data?.screening_date ?? ''

  return (
    <div className="space-y-6">
      {/* 标题 */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-[var(--text-primary)]">
          仪表盘
        </h2>
        <p className="text-sm text-[var(--text-muted)]">
          全市场基金趋势概览
        </p>
      </div>

      {/* Stats cards */}
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

      {/* 今日筛选 Top 10 */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-[var(--text-primary)]">
              今日筛选 Top 10
            </h3>
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

        <div className="space-y-2">
          {screeningResults.length === 0 ? (
            <p className="text-sm text-[var(--text-muted)] py-8 text-center">
              暂无筛选数据
            </p>
          ) : (
            screeningResults.map((item) => (
              <ScreeningResultItem
                key={item.code}
                item={item}
                onClick={(code) => {
                  // 导航到详情页
                  window.location.href = `/funds/${code}`
                }}
              />
            ))
          )}
        </div>
      </div>
    </div>
  )
}

/** 格式化大数字 */
function formatNumber(n: number): string {
  if (n >= 10000) {
    return `${(n / 10000).toFixed(1)}万`
  }
  return String(n)
}
