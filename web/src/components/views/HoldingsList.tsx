/**
 * HoldingsList — 基金持仓列表
 *
 * 职责：展示基金的前十大重仓股（或全部持仓）。
 * 以进度条形式展示每只持仓的权重占比。
 *
 * 关注点分离：
 *   - 接收 Holding[] 数据，内部按权重排序
 *   - 样式自包含（进度条颜色用 CSS 变量）
 */

import { motion } from 'framer-motion'
import { stagger, presence, transition } from '@/styles/tokens.animation'
import type { Holding } from '@/hooks/api'

interface HoldingsListProps {
  holdings: Holding[]
}

export function HoldingsList({ holdings }: HoldingsListProps) {
  if (holdings.length === 0) {
    return (
      <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-6 text-center">
        <p className="text-sm text-[var(--text-muted)]">暂无持仓数据</p>
      </div>
    )
  }

  // 按权重降序排列（null 权重放最后）
  const sorted = [...holdings].sort((a, b) => {
    const wa = a.weightPct ?? 0
    const wb = b.weightPct ?? 0
    return wb - wa
  })
  const maxWeight = sorted[0]?.weightPct ?? 1

  return (
    <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] overflow-hidden">
      <div className="px-4 py-3 border-b border-[var(--border-subtle)]">
        <h3 className="text-sm font-semibold text-[var(--text-primary)]">
          持仓明细（{holdings.length} 只）
        </h3>
      </div>

      <div className="divide-y divide-[var(--border-subtle)]">
        {sorted.map((holding, index) => (
          <motion.div
            key={holding.stockCode}
            className="px-4 py-3"
            variants={presence.slideUp}
            initial="initial"
            animate="animate"
            transition={{
              ...transition.fade,
              delay: index * 0.03,
            }}
          >
            <div className="flex items-center justify-between mb-1.5">
              <div className="flex items-center gap-2 min-w-0">
                <span className="text-xs text-[var(--text-muted)] tabular-nums w-5 text-right">
                  {index + 1}
                </span>
                <span className="text-sm font-medium text-[var(--text-primary)] truncate">
                  {holding.stockName}
                </span>
                <span className="font-mono text-xs text-[var(--text-muted)]">
                  {holding.stockCode}
                </span>
              </div>
              <span className="text-sm font-mono font-medium tabular-nums text-[var(--text-secondary)] shrink-0 ml-2">
                {holding.weightPct?.toFixed(2) ?? '—'}%
              </span>
            </div>

            {/* 权重进度条 */}
            <div className="ml-7 h-1.5 rounded-full bg-[var(--bg-elevated)] overflow-hidden">
              <motion.div
                className="h-full rounded-full bg-[var(--accent-primary)]"
                initial={{ width: 0 }}
                animate={{ width: `${((holding.weightPct ?? 0) / maxWeight) * 100}%` }}
                transition={{ duration: 0.5, ease: [0, 0, 0.2, 1] }}
              />
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  )
}
