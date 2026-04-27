/**
 * 基金详情页 — /funds/$code
 *
 * 职责：展示单只基金的完整信息（基本信息、净值走势、持仓明细）。
 * 零样式页面，只负责数据获取和组件组合。
 *
 * 【2026-04-26 重构说明】
 * 按 Phase 4.5 Style Contract 翻新为 Fund Dossier v0.5 archetype：
 *   - 使用 PageShell + PageHeader 替换裸写布局
 *   - 新增 DiagnosisGrid：从现有数据计算集中度、规模、持仓数等诊断指标
 *   - 新增 EvidenceLayout：左列净值走势，右列持仓证据
 *   - 所有卡片走 Surface 容器，数字走 MetricValue，状态走 SignalBadge
 *   - 保持数据流不变（useFundDetail + useChartData）
 *
 * 副作用：
 *   - 引入 PageShell / PageHeader / Surface / MetricValue / SignalBadge 依赖
 *   - 无行为变更，纯视觉层统一
 */

import { useEffect, useMemo } from 'react'
import { useParams, Link } from '@tanstack/react-router'
import { createFileRoute } from '@tanstack/react-router'
import { ArrowLeft, Loader2, AlertCircle } from 'lucide-react'
import { useFundDetail, useChartData } from '@/hooks/api'
import { useToast } from '@/hooks/useToast'
import { PageShell } from '@/components/ui/page-shell'
import { PageHeader } from '@/components/ui/page-header'
import { Surface } from '@/components/design-system/Surface'
import { MetricValue } from '@/components/ui/metric-value'
import { SignalBadge } from '@/components/ui/signal-badge'
import { ChartContainer } from '@/components/views/ChartContainer'
import { HoldingsList } from '@/components/views/HoldingsList'

export const Route = createFileRoute('/funds/$code')({
  component: FundDetailPage,
})

function FundDetailPage() {
  const { code } = useParams({ from: '/funds/$code' })
  const { data: fund, isLoading: detailLoading, error: detailError } = useFundDetail(code)
  const { data: chartResponse, isLoading: chartLoading, error: chartError } = useChartData(code, { days: 180 })
  const { toast } = useToast()

  const isLoading = detailLoading || chartLoading
  const chartPoints = chartResponse?.data?.history ?? []

  // API 错误通过 Toast 通知
  useEffect(() => {
    if (detailError) {
      toast({ type: 'error', message: `加载基金数据失败: ${detailError.message}` })
    }
    if (chartError) {
      toast({ type: 'error', message: `加载净值走势失败: ${chartError.message}` })
    }
  }, [detailError, chartError, toast])

  /* ── 从现有数据计算诊断指标 ──────────────────────────────── */
  const diagnosis = useMemo(() => {
    if (!fund) return null

    const holdings = fund.holdings ?? []
    const sorted = [...holdings].sort((a, b) => (b.weightPct ?? 0) - (a.weightPct ?? 0))
    const top3Weight = sorted.slice(0, 3).reduce((sum, h) => sum + (h.weightPct ?? 0), 0)
    const top3Names = sorted.slice(0, 3).map((h) => h.stockName)

    // 自然语言摘要
    let summary = ''
    if (holdings.length > 0) {
      summary = `前三大重仓为${top3Names.join('、')}，合计占比 ${top3Weight.toFixed(1)}%。`
    } else {
      summary = '暂无持仓数据。'
    }

    return {
      holdingsCount: holdings.length,
      top3Concentration: top3Weight,
      fundScale: fund.fundScale,
      establishDate: fund.establishDate,
      summary,
    }
  }, [fund])

  /* ── 加载中 ────────────────────────────────────────────── */
  if (isLoading) {
    return (
      <PageShell>
        <div className="flex flex-col items-center justify-center py-20 gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-[var(--text-muted)]" />
          <p className="text-sm text-[var(--text-muted)]">加载基金数据中...</p>
        </div>
      </PageShell>
    )
  }

  /* ── 基金不存在 ────────────────────────────────────────── */
  if (!fund) {
    return (
      <PageShell>
        <div className="flex flex-col items-center justify-center py-20 gap-3">
          <AlertCircle className="h-8 w-8 text-[var(--accent-error)]" />
          <p className="text-sm text-[var(--text-muted)]">基金不存在</p>
          <BackLink />
        </div>
      </PageShell>
    )
  }

  return (
    <PageShell>
      {/* 返回导航 */}
      <BackLink />

      {/* Dossier Header */}
      <PageHeader
        eyebrow={fund.code}
        title={fund.name}
        description={
          <div className="space-y-1">
            <div className="flex items-center gap-2 flex-wrap">
              <SignalBadge tone="neutral">{fund.market}</SignalBadge>
              {fund.managerName && (
                <span className="text-xs text-[var(--text-muted)]">
                  基金经理：{fund.managerName}
                </span>
              )}
            </div>
            {diagnosis?.summary && (
              <p className="text-sm text-[var(--text-secondary)]">{diagnosis.summary}</p>
            )}
          </div>
        }
        statusSummary={
          fund.latestNav && (
            <div className="flex items-center gap-4">
              <div>
                <span className="text-xs text-[var(--text-muted)]">最新净值</span>
                <div className="text-lg font-semibold tabular-nums">
                  <MetricValue value={fund.latestNav.nav?.toFixed(4) ?? '—'} />
                </div>
              </div>
              <div className="w-px h-8 bg-[var(--border-subtle)]" />
              <div>
                <span className="text-xs text-[var(--text-muted)]">日期</span>
                <div className="text-sm font-medium tabular-nums text-[var(--text-secondary)]">
                  {fund.latestNav.date ?? '—'}
                </div>
              </div>
            </div>
          )
        }
      />

      {/* Diagnosis Grid */}
      {diagnosis && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Surface bordered rounded="lg" className="p-4">
            <div className="text-xs text-[var(--text-muted)] mb-1">持仓集中度（Top3）</div>
            <MetricValue
              value={`${diagnosis.top3Concentration.toFixed(1)}%`}
              tone={diagnosis.top3Concentration > 50 ? 'warning' : 'neutral'}
            />
          </Surface>
          <Surface bordered rounded="lg" className="p-4">
            <div className="text-xs text-[var(--text-muted)] mb-1">重仓股数量</div>
            <MetricValue value={diagnosis.holdingsCount} />
          </Surface>
          <Surface bordered rounded="lg" className="p-4">
            <div className="text-xs text-[var(--text-muted)] mb-1">基金规模</div>
            <MetricValue
              value={
                fund.fundScale !== null
                  ? `${(fund.fundScale / 100000000).toFixed(2)}亿`
                  : '—'
              }
            />
          </Surface>
          <Surface bordered rounded="lg" className="p-4">
            <div className="text-xs text-[var(--text-muted)] mb-1">成立日期</div>
            <MetricValue value={fund.establishDate ?? '—'} />
          </Surface>
        </div>
      )}

      {/* Evidence Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧：净值走势 */}
        <div className="lg:col-span-2 space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--text-muted)]">
            净值证据
          </h2>
          <ChartContainer data={chartPoints} market={fund.market} height={400} />
        </div>

        {/* 右侧：持仓证据 */}
        <div className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--text-muted)]">
            持仓证据
          </h2>
          <HoldingsList holdings={fund.holdings} />
        </div>
      </div>
    </PageShell>
  )
}

/** 返回基金列表链接 */
function BackLink() {
  return (
    <Link
      to="/funds"
      className="inline-flex items-center gap-1.5 text-sm text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors"
    >
      <ArrowLeft className="h-4 w-4" />
      返回基金列表
    </Link>
  )
}
