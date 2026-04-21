/**
 * 回测页 — /backtest
 *
 * 【2026-04-21 重构说明】
 * 本次重构将原本 4 列网格表单改造为 4 步 Stepper 向导，降低用户认知负荷。
 * 同时将 Canvas 自绘净值曲线替换为 LightweightChart AreaSeries，获得：
 *   - 交互式缩放/平移
 *   - 暗色模式自动适配
 *   - 十字光标与 tooltip
 *   - 不再需要手动处理 DPR 和 resize
 *
 * 副作用：
 *   - 新增 framer-motion 依赖做步骤切换动画
 *   - 新增 LightweightChart 依赖（已存在）
 *   - 步骤间数据全部保存在组件 state，无持久化需求
 */

import { createFileRoute } from '@tanstack/react-router'
import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Loader2,
  Play,
  TrendingUp,
  TrendingDown,
  Activity,
  BarChart3,
  ChevronRight,
  ChevronLeft,
  Check,
  SlidersHorizontal,
  Wallet,
  CalendarRange,
  Rocket,
} from 'lucide-react'
import { useBacktest, type RebalanceEntry } from '@/hooks/api'
import { useToast } from '@/hooks/useToast'
import { StatsCard } from '@/components/views/StatsCard'
import { LightweightChart } from '@/components/chart/LightweightChart'
import { presence, transition } from '@/styles/tokens.animation'

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

const MARKET_OPTIONS = [
  { value: 'cn', label: 'A股' },
  { value: 'hk', label: '港股' },
  { value: 'us', label: '美股' },
]

/* ── Stepper Steps Config ──────────────────────────────── */

const STEPS = [
  { id: 1, title: '策略选择', icon: SlidersHorizontal },
  { id: 2, title: '持仓配置', icon: Wallet },
  { id: 3, title: '费用与周期', icon: CalendarRange },
  { id: 4, title: '确认运行', icon: Rocket },
]

/* ── Page Component ────────────────────────────────────── */

function BacktestPage() {
  const { mutate: runBacktest, data: result, isPending, error } = useBacktest()
  const { toast } = useToast()

  // 回测错误通过 Toast 通知，替代内联红色 div
  useEffect(() => {
    if (error) {
      toast({
        type: 'error',
        message: `回测失败: ${error instanceof Error ? error.message : '未知错误'}`,
      })
    }
  }, [error, toast])

  // Stepper state
  const [currentStep, setCurrentStep] = useState(1)

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
  const [dateError, setDateError] = useState<string | null>(null)

  const canGoNext = () => {
    if (currentStep === 3) {
      if (startDate >= endDate) {
        setDateError('开始日期必须早于结束日期')
        return false
      }
      setDateError(null)
    }
    return true
  }

  const handleNext = () => {
    if (canGoNext() && currentStep < 4) {
      setCurrentStep((s) => s + 1)
    }
  }

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep((s) => s - 1)
      setDateError(null)
    }
  }

  const handleSubmit = () => {
    if (startDate >= endDate) {
      setDateError('开始日期必须早于结束日期')
      return
    }
    setDateError(null)
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
  const rebalanceHistory = result?.data?.rebalanceHistory

  const equityChartData = equityCurve
    ? Object.entries(equityCurve)
        .map(([time, value]) => ({ time, value }))
        .sort((a, b) => a.time.localeCompare(b.time))
    : []

  const factorLabel = FACTOR_OPTIONS.find((o) => o.value === scoreFactor)?.label ?? scoreFactor
  const signalLabel = SIGNAL_FILTER_OPTIONS.find((o) => o.value === signalFilter)?.label ?? '无过滤'
  const rebalanceLabel = REBALANCE_OPTIONS.find((o) => o.value === rebalanceFreq)?.label ?? rebalanceFreq
  const weightingLabel = WEIGHTING_OPTIONS.find((o) => o.value === weighting)?.label ?? weighting
  const marketLabel = MARKET_OPTIONS.find((o) => o.value === market)?.label ?? market

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Title */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-[var(--text-primary)]">
          策略回测
        </h2>
        <p className="text-sm text-[var(--text-muted)]">
          配置参数并运行回测，验证策略历史表现
        </p>
      </div>

      {/* Stepper Header */}
      <div className="flex items-center gap-2">
        {STEPS.map((step, idx) => {
          const isActive = step.id === currentStep
          const isCompleted = step.id < currentStep
          const isLast = idx === STEPS.length - 1

          return (
            <div key={step.id} className="flex items-center gap-2 flex-1">
              <button
                onClick={() => {
                  if (step.id < currentStep) setCurrentStep(step.id)
                }}
                disabled={step.id >= currentStep}
                className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors duration-200 ${
                  isActive
                    ? 'bg-[var(--accent-primary)] text-[var(--text-inverse)]'
                    : isCompleted
                      ? 'bg-[var(--accent-primary-subtle)] text-[var(--accent-primary)]'
                      : 'bg-[var(--bg-surface)] text-[var(--text-muted)] border border-[var(--border-subtle)]'
                } ${step.id < currentStep ? 'cursor-pointer' : 'cursor-default'}`}
              >
                <span
                  className={`flex h-5 w-5 items-center justify-center rounded-full text-xs ${
                    isActive
                      ? 'bg-[var(--highlight-on-accent)]'
                      : isCompleted
                        ? 'bg-[var(--accent-primary)] text-[var(--text-inverse)]'
                        : 'bg-[var(--bg-hover)]'
                  }`}
                >
                  {isCompleted ? <Check className="h-3 w-3" /> : step.id}
                </span>
                <span className="hidden sm:inline">{step.title}</span>
              </button>
              {!isLast && (
                <ChevronRight className="h-4 w-4 shrink-0 text-[var(--text-faint)]" />
              )}
            </div>
          )
        })}
      </div>

      {/* Step Content */}
      <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-5">
        <AnimatePresence mode="wait">
          <motion.div
            key={currentStep}
            initial={presence.slideUp.initial}
            animate={presence.slideUp.animate}
            exit={presence.slideUp.exit}
            transition={transition.fade}
          >
            {/* Step 1: 策略选择 */}
            {currentStep === 1 && (
              <div className="space-y-4">
                <h3 className="text-sm font-semibold text-[var(--text-primary)]">
                  选择打分因子与信号过滤
                </h3>
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-[var(--text-muted)]">打分因子</label>
                    <select
                      value={scoreFactor}
                      onChange={(e) => setScoreFactor(e.target.value)}
                      className="w-full rounded-md border border-[var(--border-subtle)] bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring-focus)]"
                    >
                      {FACTOR_OPTIONS.map((o) => (
                        <option key={o.value} value={o.value}>{o.label}</option>
                      ))}
                    </select>
                    <p className="text-xs text-[var(--text-faint)]">
                      决定如何对基金进行评分排序
                    </p>
                  </div>

                  <div className="space-y-1">
                    <label className="text-xs font-medium text-[var(--text-muted)]">信号过滤</label>
                    <select
                      value={signalFilter}
                      onChange={(e) => setSignalFilter(e.target.value)}
                      className="w-full rounded-md border border-[var(--border-subtle)] bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring-focus)]"
                    >
                      {SIGNAL_FILTER_OPTIONS.map((o) => (
                        <option key={o.value} value={o.value}>{o.label}</option>
                      ))}
                    </select>
                    <p className="text-xs text-[var(--text-faint)]">
                      仅在满足技术信号时开仓
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Step 2: 持仓配置 */}
            {currentStep === 2 && (
              <div className="space-y-4">
                <h3 className="text-sm font-semibold text-[var(--text-primary)]">
                  配置持仓与调仓规则
                </h3>
                <div className="grid gap-4 md:grid-cols-3">
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-[var(--text-muted)]">持仓数量</label>
                    <input
                      type="number"
                      min={1}
                      max={50}
                      value={topN}
                      onChange={(e) => setTopN(Number(e.target.value))}
                      className="w-full rounded-md border border-[var(--border-subtle)] bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring-focus)]"
                    />
                    <p className="text-xs text-[var(--text-faint)]">
                      每次调仓后保留的前 N 只基金
                    </p>
                  </div>

                  <div className="space-y-1">
                    <label className="text-xs font-medium text-[var(--text-muted)]">调仓频率</label>
                    <select
                      value={rebalanceFreq}
                      onChange={(e) => setRebalanceFreq(e.target.value)}
                      className="w-full rounded-md border border-[var(--border-subtle)] bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring-focus)]"
                    >
                      {REBALANCE_OPTIONS.map((o) => (
                        <option key={o.value} value={o.value}>{o.label}</option>
                      ))}
                    </select>
                  </div>

                  <div className="space-y-1">
                    <label className="text-xs font-medium text-[var(--text-muted)]">权重分配</label>
                    <select
                      value={weighting}
                      onChange={(e) => setWeighting(e.target.value)}
                      className="w-full rounded-md border border-[var(--border-subtle)] bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring-focus)]"
                    >
                      {WEIGHTING_OPTIONS.map((o) => (
                        <option key={o.value} value={o.value}>{o.label}</option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>
            )}

            {/* Step 3: 费用与周期 */}
            {currentStep === 3 && (
              <div className="space-y-4">
                <h3 className="text-sm font-semibold text-[var(--text-primary)]">
                  设置费率与回测区间
                </h3>
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-[var(--text-muted)]">申购费率</label>
                    <input
                      type="number"
                      step={0.0001}
                      min={0}
                      max={0.1}
                      value={feeRate}
                      onChange={(e) => setFeeRate(Number(e.target.value))}
                      className="w-full rounded-md border border-[var(--border-subtle)] bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring-focus)]"
                    />
                    <p className="text-xs text-[var(--text-faint)]">
                      每次调仓的单边费率
                    </p>
                  </div>

                  <div className="space-y-1">
                    <label className="text-xs font-medium text-[var(--text-muted)]">市场</label>
                    <select
                      value={market}
                      onChange={(e) => setMarket(e.target.value)}
                      className="w-full rounded-md border border-[var(--border-subtle)] bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring-focus)]"
                    >
                      {MARKET_OPTIONS.map((o) => (
                        <option key={o.value} value={o.value}>{o.label}</option>
                      ))}
                    </select>
                  </div>

                  <div className="space-y-1">
                    <label className="text-xs font-medium text-[var(--text-muted)]">开始日期</label>
                    <input
                      type="date"
                      value={startDate}
                      onChange={(e) => {
                        setStartDate(e.target.value)
                        setDateError(null)
                      }}
                      className="w-full rounded-md border border-[var(--border-subtle)] bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring-focus)]"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="text-xs font-medium text-[var(--text-muted)]">结束日期</label>
                    <input
                      type="date"
                      value={endDate}
                      onChange={(e) => {
                        setEndDate(e.target.value)
                        setDateError(null)
                      }}
                      className="w-full rounded-md border border-[var(--border-subtle)] bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--ring-focus)]"
                    />
                  </div>
                </div>

                {dateError && (
                  <div className="rounded-md border border-[var(--accent-error)]/20 bg-[var(--accent-error-subtle)] p-3 text-sm text-[var(--accent-error)]">
                    {dateError}
                  </div>
                )}
              </div>
            )}

            {/* Step 4: 确认运行 */}
            {currentStep === 4 && (
              <div className="space-y-4">
                <h3 className="text-sm font-semibold text-[var(--text-primary)]">
                  确认配置并运行回测
                </h3>

                <div className="grid gap-3 md:grid-cols-2">
                  <SummaryItem label="打分因子" value={factorLabel} />
                  <SummaryItem label="信号过滤" value={signalLabel} />
                  <SummaryItem label="持仓数量" value={`${topN} 只`} />
                  <SummaryItem label="调仓频率" value={rebalanceLabel} />
                  <SummaryItem label="权重分配" value={weightingLabel} />
                  <SummaryItem label="申购费率" value={`${(feeRate * 100).toFixed(2)}%`} />
                  <SummaryItem label="回测市场" value={marketLabel} />
                  <SummaryItem label="回测区间" value={`${startDate} ~ ${endDate}`} />
                </div>

                {dateError && (
                  <div className="rounded-md border border-[var(--accent-error)]/20 bg-[var(--accent-error-subtle)] p-3 text-sm text-[var(--accent-error)]">
                    {dateError}
                  </div>
                )}

                <div className="pt-2">
                  <button
                    onClick={handleSubmit}
                    disabled={isPending}
                    className="inline-flex items-center gap-2 rounded-md bg-[var(--accent-primary)] px-6 py-2.5 text-sm font-medium text-[var(--text-inverse)] hover:opacity-90 disabled:opacity-50 transition-opacity duration-200"
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
              </div>
            )}
          </motion.div>
        </AnimatePresence>

        {/* Navigation Buttons (for steps 1-3) */}
        {currentStep < 4 && (
          <div className="mt-6 flex items-center justify-between border-t border-[var(--border-subtle)] pt-4">
            <button
              onClick={handleBack}
              disabled={currentStep === 1}
              className="inline-flex items-center gap-1 rounded-md px-3 py-2 text-sm font-medium text-[var(--text-muted)] hover:bg-[var(--bg-hover)] disabled:opacity-30 transition-colors duration-200"
            >
              <ChevronLeft className="h-4 w-4" />
              上一步
            </button>
            <button
              onClick={handleNext}
              className="inline-flex items-center gap-1 rounded-md bg-[var(--accent-primary)] px-4 py-2 text-sm font-medium text-[var(--text-inverse)] hover:opacity-90 transition-opacity duration-200"
            >
              下一步
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>

      {/* Results */}
      {result && result.data && (
        <div className="space-y-6">
          {/* Stats Cards */}
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <StatsCard
              title="总收益率"
              value={`${stats?.totalReturn != null ? stats.totalReturn.toFixed(2) : '—'}%`}
              trend={stats && stats.totalReturn > 0 ? 'up' : stats && stats.totalReturn < 0 ? 'down' : 'neutral'}
              icon={TrendingUp}
            />
            <StatsCard
              title="年化收益率"
              value={`${stats?.annualReturn != null ? stats.annualReturn.toFixed(2) : '—'}%`}
              trend={stats && stats.annualReturn > 0 ? 'up' : stats && stats.annualReturn < 0 ? 'down' : 'neutral'}
              icon={Activity}
            />
            <StatsCard
              title="最大回撤"
              value={`${stats?.maxDrawdown != null ? stats.maxDrawdown.toFixed(2) : '—'}%`}
              trend="down"
              icon={TrendingDown}
            />
            <StatsCard
              title="夏普比率"
              value={stats?.sharpeRatio != null ? stats.sharpeRatio.toFixed(2) : '—'}
              icon={BarChart3}
            />
          </div>

          {/* Equity Curve Chart */}
          <div className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-5">
            <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-4">
              净值曲线
            </h3>
            {equityChartData.length > 0 ? (
              <LightweightChart
                data={equityChartData}
                type="area"
                height={320}
              />
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

function SummaryItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded-md bg-[var(--bg-hover)] px-3 py-2">
      <span className="text-xs text-[var(--text-muted)]">{label}</span>
      <span className="text-sm font-medium text-[var(--text-primary)]">{value}</span>
    </div>
  )
}

function RebalanceTable({ data }: { data: RebalanceEntry[] }) {
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
                  key={`row-${entry.date}-${idx}`}
                  className="border-b border-[var(--border-subtle)] cursor-pointer hover:bg-[var(--bg-hover)] transition-colors duration-200"
                  onClick={() => setExpandedRow(isExpanded ? null : idx)}
                >
                  <td className="px-3 py-2 text-[var(--text-primary)]">{entry.date}</td>
                  <td className="px-3 py-2 text-[var(--text-muted)]">{holdings.length} 只</td>
                  <td className="px-3 py-2 text-[var(--accent-primary)]">
                    {isExpanded ? '收起' : '展开'}
                  </td>
                </tr>
                {isExpanded && (
                  <tr key={`expand-${entry.date}-${idx}`}>
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
