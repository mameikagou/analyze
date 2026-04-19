/**
 * ScreeningResultItem — 筛选结果列表项
 *
 * 职责：展示一只通过 MA 筛选的基金的完整指标卡片。
 * 组合使用多个 Badge 组件（MarketBadge、ScoreBadge、PurchaseStatusBadge、MADiffIndicator）。
 *
 * 关注点分离：
 *   - 接收 ScreeningResultItem 数据，内部组合子组件展示
 *   - 点击整行可跳转详情页（通过 onClick 回调）
 */

import { motion } from 'framer-motion'
import { ChevronRight } from 'lucide-react'
import { MarketBadge } from './MarketBadge'
import { ScoreBadge } from './ScoreBadge'
import { PurchaseStatusBadge } from './PurchaseStatusBadge'
import { MADiffIndicator } from './MADiffIndicator'
import { presence, transition } from '@/styles/tokens.animation'
import type { ScreeningResultItem as ScreeningResultItemType } from '@/hooks/api'

interface ScreeningResultItemProps {
  item: ScreeningResultItemType
  onClick?: (code: string) => void
}

export function ScreeningResultItem({ item, onClick }: ScreeningResultItemProps) {
  return (
    <motion.div
      className="group flex items-center gap-4 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 cursor-pointer transition-colors hover:border-[var(--border-hover)] hover:bg-[var(--bg-elevated)]"
      variants={presence.slideUp}
      initial="initial"
      animate="animate"
      transition={transition.fade}
      onClick={() => onClick?.(item.code)}
    >
      {/* 左侧：基本信息 */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="font-mono text-sm font-medium text-[var(--text-primary)]">
            {item.code}
          </span>
          <MarketBadge market={item.market} />
          <span className="text-sm text-[var(--text-secondary)] truncate">
            {item.name}
          </span>
        </div>

        <div className="flex items-center gap-4 text-xs text-[var(--text-muted)]">
          <span>净值: {item.nav?.toFixed(4) ?? '—'}</span>
          <span>MA20: {item.maShort?.toFixed(4) ?? '—'}</span>
          <span>MA60: {item.maLong?.toFixed(4) ?? '—'}</span>
        </div>
      </div>

      {/* 右侧：指标徽章 */}
      <div className="flex items-center gap-3 shrink-0">
        {item.maDiffPct !== null && item.maDiffPct !== undefined && (
          <MADiffIndicator maDiffPct={item.maDiffPct} />
        )}

        {item.dailyChangePct !== null && item.dailyChangePct !== undefined && (
          <span
            className={`text-xs font-mono tabular-nums ${
              item.dailyChangePct >= 0
                ? 'text-[var(--green-600)]'
                : 'text-[var(--red-600)]'
            }`}
          >
            {item.dailyChangePct >= 0 ? '+' : ''}
            {item.dailyChangePct.toFixed(2)}%
          </span>
        )}

        <ScoreBadge score={item.score} />

        <PurchaseStatusBadge
          status={item.purchaseStatus}
          limit={item.purchaseLimit}
        />

        <ChevronRight className="h-4 w-4 text-[var(--text-muted)] opacity-0 group-hover:opacity-100 transition-opacity" />
      </div>
    </motion.div>
  )
}
