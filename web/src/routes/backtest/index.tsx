/**
 * 回测页 — /backtest
 *
 * 职责：配置回测参数、执行回测、展示结果。
 * 零样式页面，所有样式在子组件和 Tailwind utility classes 中。
 */

import { createFileRoute } from '@tanstack/react-router'
import { useState, useRef, useEffect } from 'react'
import { Loader2, Play, TrendingUp, TrendingDown, Activity, BarChart3 } from 'lucide-react'
import { useBacktest } from '@/hooks/api'
import { StatsCard } from '@/components/views/StatsCard'

export const Route = createFileRoute('/backtest/')({
  component: BacktestPage,
})

// Factor options matching backend _FACTOR_REGISTRY
const FACTOR_OPTIONS = [
  { value: 'three_factor', label: '三因子组合 (动量+夏普+回撤)' },
  { value: 'momentum', label: '动量因子' },
  { value: 'sharpe', label: '夏普因子' },
  { value: 'drawdown', label: '回撤因子' },
]

const SIGNAL_FILTER_OPTIONS = [
  { value: 'ma_cross_20_60', label: 'MA20 > MA60 多头排列' },
  { value: '', label: '无过滤' },
]

const REBALANCE_OPTIONS = [
  { value: 'ME', label: '月末' },
  { value: 'W-FRI', label: '周五' },
  { value: 'QE', label: '季末' },
]

const WEIGHTING_OPTIONS = [
  { value: 'equal', label: '等权' },
  { value: 'score', label: '按分数加权' },
]

function BacktestPage() {
  const { mutate: runBacktest, data: result, isPending, error } = useBacktest()

  // Form state
  const [scoreFactor, setScoreFactor] = useState('three_factor')
  const [signalFilter, setSignalFilter] = useState('ma_cross_20_60')
  const [topN, setTopN] = useState(10)
  const [rebalanceFreq, setRebalanceFreq] = useState('ME')
  const [weighting, setWeighting] = useState('equal')
  const [feeRate, setFeeRate] = useState(0.0015)
  const [startDate, setStartDate] = useState('2020-01-01')
  const [endDate, setEndDate] = useState('2024-12-31')
  const [market, setMarket] = useState('cn')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    runBacktest({
      scoreFactor,
      signalFilter: signalFilter || null,
      topN,
      rebalanceFreq,
      weighting,
      feeRate,
      startDate,
      endDate,
      market,
    })
  }

  const stats = result?.data?.stats
  const equityCurve = result?.data?.equityCurve
  const drawdown = result?.data?.drawdown
  const rebalanceHistory = result?.data?.rebalanceHistory

  return (
    <div className="space-y-6">
      {/* Title */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-[var(--text-primary)]">
          策略回测
        </h2>
        <p className="text-sm text-[var(--text-muted)]">
          配置参数并运行回测，验证策略历史表现
        </p>
      </div>

      {/* Configuration Panel */}
      <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-5">
        <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-4">
          回测配置
        </h3>
        <form onSubmit={handleSubmit} className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {/* Score Factor */}
          <div className="space-y-1">
            <label className="text-xs font-medium text-[var(--text-muted)]">打分因子</label>
            <select
              value={scoreFactor}
              onChange={(e) => setScoreFactor(e.target.value)}
              className="w-full rounded-md border border-[var(--border-subtle)] bg-background px-3 py-2 text-sm"
            >
              {FACTOR_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          {/* Signal Filter */}
          <div className="space-y-1">
            <label className="text-xs font-medium text-[var(--text-muted)]">信号过滤</label>
            <select
              value={signalFilter}
              onChange={(e) => setSignalFilter(e.target.value)}
              className="w-full rounded-md border border-[var(--border-subtle)] bg-background px-3 py-2 text-sm"
            >
              {SIGNAL_FILTER_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          {/* Top N */}
          <div className="space-y-1">
            <label className="text-xs font-medium text-[var(--text-muted)]">持仓数量</label>
            <input
              type="number"
              min={1}
              max={50}
              value={topN}
              onChange={(e) => setTopN(Number(e.target.value))}
              className="w-full rounded-md border border-[var(--border-subtle)] bg-background px-3 py-2 text-sm"
            />
          </div>

          {/* Rebalance Frequency */}
          <div className="space-y-1">
            <label className="text-xs font-medium text-[var(--text-muted)]">调仓频率</label>
            <select
              value={rebalanceFreq}
              onChange={(e) => setRebalanceFreq(e.target.value)}
              className="w-full rounded-md border border-[var(--border-subtle)] bg-background px-3 py-2 text-sm"
            >
              {REBALANCE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          {/* Weighting */}
          <div className="space-y-1">
            <label className="text-xs font-medium text-[var(--text-muted)]">权重分配</label>
            <select
              value={weighting}
              onChange={(e) => setWeighting(e.target.value)}
              className="w-full rounded-md border border-[var(--border-subtle)] bg-background px-3 py-2 text-sm"
            >
              {WEIGHTING_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          {/* Fee Rate */}
          <div className="space-y-1">
            <label className="text-xs font-medium text-[var(--text-muted)]">申购费率</label>
            <input
              type="number"
              step={0.0001}
              min={0}
              max={0.1}
              value={feeRate}
              onChange={(e) => setFeeRate(Number(e.target.value))}
              className="w-full rounded-md border border-[var(--border-subtle)] bg-background px-3 py-2 text-sm"
            />
          </div>

          {/* Start Date */}
          <div className="space-y-1">
            <label className="text-xs font-medium text-[var(--text-muted)]">开始日期</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full rounded-md border border-[var(--border-subtle)] bg-background px-3 py-2 text-sm"
            />
          </div>

          {/* End Date */}
          <div className="space-y-1">
            <label className="text-xs font-medium text-[var(--text-muted)]">结束日期</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full rounded-md border border-[var(--border-subtle)] bg-background px-3 py-2 text-sm"
            />
          </div>

          {/* Submit Button */}
          <div className="md:col-span-2 lg:col-span-4">
            <button
              type="submit"
              disabled={isPending}
              className="inline-flex items-center gap-2 rounded-md bg-[var(--accent-primary)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
            >
              {isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  回测运行中...
                </>
              ) : (
                <>
                  <Play className="h-4 w-4" />
                  运行回测
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          回测失败: {error instanceof Error ? error.message : '未知错误'}
        </div>
      )}

      {/* Results */}
      {result && result.data && (
        <div className="space-y-6">
          {/* Stats Cards */}
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <StatsCard
              title="总收益率"
              value={`${stats?.totalReturn?.toFixed(2) ?? '—'}%`}
              trend={stats && stats.totalReturn > 0 ? 'up' : stats && stats.totalReturn < 0 ? 'down' : 'neutral'}
              icon={TrendingUp}
            />
            <StatsCard
              title="年化收益率"
              value={`${stats?.annualReturn?.toFixed(2) ?? '—'}%`}
              trend={stats && stats.annualReturn > 0 ? 'up' : stats && stats.annualReturn < 0 ? 'down' : 'neutral'}
              icon={Activity}
            />
            <StatsCard
              title="最大回撤"
              value={`${stats?.maxDrawdown?.toFixed(2) ?? '—'}%`}
              trend="down"
              icon={TrendingDown}
            />
            <StatsCard
              title="夏普比率"
              value={stats?.sharpeRatio?.toFixed(2) ?? '—'}
              icon={BarChart3}
            />
          </div>

          {/* Equity Curve Chart */}
          <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-5">
            <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-4">
              净值曲线
            </h3>
            {equityCurve && Object.keys(equityCurve).length > 0 ? (
              <EquityCurveChart data={equityCurve} drawdown={drawdown} />
            ) : (
              <p className="text-sm text-[var(--text-muted)]">无净值数据</p>
            )}
          </div>

          {/* Rebalance History */}
          <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-5">
            <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-4">
              调仓历史
            </h3>
            {rebalanceHistory && rebalanceHistory.length > 0 ? (
              <RebalanceTable data={rebalanceHistory} />
            ) : (
              <p className="text-sm text-[var(--text-muted)]">无调仓记录</p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

/* ── Sub-components ────────────────────────────────────── */

function EquityCurveChart({
  data,
  drawdown,
}: {
  data: Record<string, number>
  drawdown?: Record<string, number> | null
}) {
  // Simple canvas-based chart (no external chart lib dependency)
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const dates = Object.keys(data).sort()
    const values = dates.map((d) => data[d])
    const ddValues = drawdown ? dates.map((d) => drawdown[d] ?? 0) : null

    const width = canvas.width
    const height = canvas.height
    const padding = { top: 20, right: 20, bottom: 30, left: 60 }

    const chartW = width - padding.left - padding.right
    const chartH = height - padding.top - padding.bottom

    const minVal = Math.min(...values)
    const maxVal = Math.max(...values)
    const valRange = maxVal - minVal || 1

    // Clear
    ctx.clearRect(0, 0, width, height)

    // Grid lines
    ctx.strokeStyle = 'var(--border-subtle)'
    ctx.lineWidth = 0.5
    for (let i = 0; i <= 4; i++) {
      const y = padding.top + (chartH * i) / 4
      ctx.beginPath()
      ctx.moveTo(padding.left, y)
      ctx.lineTo(width - padding.right, y)
      ctx.stroke()

      // Y-axis labels
      const labelVal = maxVal - (valRange * i) / 4
      ctx.fillStyle = 'var(--text-muted)'
      ctx.font = '10px sans-serif'
      ctx.textAlign = 'right'
      ctx.fillText(labelVal.toFixed(0), padding.left - 8, y + 3)
    }

    // Equity curve line
    ctx.strokeStyle = 'var(--accent-primary)'
    ctx.lineWidth = 2
    ctx.beginPath()
    dates.forEach((date, i) => {
      const x = padding.left + (chartW * i) / (dates.length - 1)
      const y = padding.top + chartH * (1 - (values[i] - minVal) / valRange)
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    })
    ctx.stroke()

    // Drawdown area (if available)
    if (ddValues) {
      const ddMin = Math.min(...ddValues)
      const ddMax = Math.max(...ddValues)
      const ddRange = ddMax - ddMin || 1

      ctx.fillStyle = 'rgba(239, 68, 68, 0.15)'
      ctx.beginPath()
      dates.forEach((date, i) => {
        const x = padding.left + (chartW * i) / (dates.length - 1)
        const y = padding.top + chartH * (1 - (ddValues[i] - ddMin) / ddRange)
        if (i === 0) ctx.moveTo(x, y)
        else ctx.lineTo(x, y)
      })
      ctx.lineTo(padding.left + chartW, padding.top + chartH)
      ctx.lineTo(padding.left, padding.top + chartH)
      ctx.closePath()
      ctx.fill()
    }

    // X-axis labels (first, middle, last)
    ctx.fillStyle = 'var(--text-muted)'
    ctx.font = '10px sans-serif'
    ctx.textAlign = 'center'
    const labelIndices = [0, Math.floor(dates.length / 2), dates.length - 1]
    labelIndices.forEach((i) => {
      const x = padding.left + (chartW * i) / (dates.length - 1)
      ctx.fillText(dates[i].slice(0, 7), x, height - 8)
    })
  }, [data, drawdown])

  return (
    <canvas
      ref={canvasRef}
      width={800}
      height={300}
      className="w-full"
      style={{ maxWidth: '100%' }}
    />
  )
}

function RebalanceTable({ data }: { data: Array<{ date: string; holdings: Record<string, number> }> }) {
  const [expandedRow, setExpandedRow] = useState<number | null>(null)

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--border-subtle)]">
            <th className="px-3 py-2 text-left font-medium text-[var(--text-muted)]">日期</th>
            <th className="px-3 py-2 text-left font-medium text-[var(--text-muted)]">持仓数量</th>
            <th className="px-3 py-2 text-left font-medium text-[var(--text-muted)]">操作</th>
          </tr>
        </thead>
        <tbody>
          {data.map((entry, idx) => {
            const holdings = Object.entries(entry.holdings)
            const isExpanded = expandedRow === idx
            return (
              <>
                <tr
                  key={entry.date}
                  className="border-b border-[var(--border-subtle)] cursor-pointer hover:bg-[var(--bg-hover)]"
                  onClick={() => setExpandedRow(isExpanded ? null : idx)}
                >
                  <td className="px-3 py-2 text-[var(--text-primary)]">{entry.date}</td>
                  <td className="px-3 py-2 text-[var(--text-muted)]">{holdings.length} 只</td>
                  <td className="px-3 py-2 text-[var(--accent-primary)]">
                    {isExpanded ? '收起' : '展开'}
                  </td>
                </tr>
                {isExpanded && (
                  <tr>
                    <td colSpan={3} className="px-3 py-2">
                      <div className="grid gap-1 md:grid-cols-2 lg:grid-cols-4">
                        {holdings.map(([code, weight]) => (
                          <div
                            key={code}
                            className="flex items-center justify-between rounded-md bg-[var(--bg-elevated)] px-3 py-1.5"
                          >
                            <span className="text-xs text-[var(--text-primary)]">{code}</span>
                            <span className="text-xs text-[var(--text-muted)]">
                              {(weight * 100).toFixed(1)}%
                            </span>
                          </div>
                        ))}
                      </div>
                    </td>
                  </tr>
                )}
              </>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
