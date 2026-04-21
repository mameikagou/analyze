/**
 * 基金详情页 — /funds/$code
 *
 * 职责：展示单只基金的完整信息（基本信息、净值走势、持仓明细）。
 * 零样式页面，只负责数据获取和组件组合。
 *
 * 数据流：
 *   - URL 参数 code → useFundDetail + useChartData
 *   - 详情数据 → FundDetailHeader + HoldingsList
 *   - 图表数据 → ChartContainer
 */

import { useEffect } from 'react'
import { useParams, Link } from '@tanstack/react-router'
import { createFileRoute } from '@tanstack/react-router'
import { ArrowLeft, Loader2, AlertCircle } from 'lucide-react'
import { useFundDetail, useChartData } from '@/hooks/api'
import { useToast } from '@/hooks/useToast'
import { FundDetailHeader } from '@/components/views/FundDetailHeader'
import { ChartContainer } from '@/components/views/ChartContainer'
import { HoldingsList } from '@/components/views/HoldingsList'

export const Route = createFileRoute('/funds/$code')({
  component: FundDetailPage,
})

function FundDetailPage() {
  const { code } = useParams({ from: '/funds/$code' })
  const { data: fund, isLoading: detailLoading, error: detailError } = useFundDetail(code)
  const { data: chartResponse, isLoading: chartLoading } = useChartData(code, { days: 180 })
  const { toast } = useToast()

  const isLoading = detailLoading || chartLoading

  // API 错误通过 Toast 通知
  useEffect(() => {
    if (detailError) {
      toast({ type: 'error', message: `加载基金数据失败: ${detailError.message}` })
    }
  }, [detailError, toast])

  /* ── 加载中 ────────────────────────────────────────────── */
  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-3">
        <Loader2 className="h-8 w-8 animate-spin text-[var(--text-muted)]" />
        <p className="text-sm text-[var(--text-muted)]">加载基金数据中...</p>
      </div>
    )
  }

  /* ── 基金不存在 ────────────────────────────────────────── */
  if (!fund) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-3">
        <AlertCircle className="h-8 w-8 text-[var(--accent-error)]" />
        <p className="text-sm text-[var(--text-muted)]">基金不存在</p>
        <BackLink />
      </div>
    )
  }

  const chartPoints = chartResponse?.data?.history ?? []

  return (
    <div className="space-y-6">
      {/* 返回导航 */}
      <BackLink />

      {/* 基金基本信息 */}
      <FundDetailHeader fund={fund} />

      {/* 净值走势图 */}
      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">
          净值走势
        </h2>
        <ChartContainer data={chartPoints} market={fund.market} height={400} />
      </section>

      {/* 持仓明细 */}
      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">
          重仓持股
        </h2>
        <HoldingsList holdings={fund.holdings} />
      </section>
    </div>
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
