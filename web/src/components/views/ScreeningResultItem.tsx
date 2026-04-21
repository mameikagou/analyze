/**
 * ScreeningResultItem — 筛选结果列表项
 *
 * 【2026-04-21 重构说明】
 * 将裸写的 bg-[var(--bg-surface)]/border-[var(--border-subtle)] 替换为
 * design-system/Surface 组件，统一容器层级管理。
 * 涨跌色从 Primitive Token（--green-600/--red-600）迁移到 Semantic Token
 *（--accent-success/--accent-error），确保暗色模式下颜色映射正确。
 *
 * 副作用：
 *   - 引入 Surface 组件依赖（已存在）
 *   - hover 态通过 Surface 的 className 透传，行为不变
 */

import { motion } from 'framer-motion'
import { ChevronRight } from 'lucide-react'
import { Surface } from '@/components/design-system/Surface'
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
      variants={presence.slideUp}
      initial="initial"
      animate="animate"
      transition={transition.fade}
    >
      <Surface
        variant="surface"
        bordered
        rounded="lg"
        className="flex items-center gap-4 p-4 cursor-pointer transition-colors duration-200 hover:border-[var(--border-hover)] hover:bg-[var(--bg-elevated)] group"
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
            <span>净值: {item.nav != null ? item.nav.toFixed(4) : '—'}</span>
            <span>MA20: {item.maShort != null ? item.maShort.toFixed(4) : '—'}</span>
            <span>MA60: {item.maLong != null ? item.maLong.toFixed(4) : '—'}</span>
          </div>
        </div>

        {/* 右侧：指标徽章 */}
        <div className="flex items-center gap-3 shrink-0">
          {item.maDiffPct != null && (
            <MADiffIndicator maDiffPct={item.maDiffPct} />
          )}

          {item.dailyChangePct != null && (
            <span
              className={`text-xs font-mono tabular-nums ${
                item.dailyChangePct >= 0
                  ? 'text-[var(--accent-success)]'
                  : 'text-[var(--accent-error)]'
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

          <ChevronRight className="h-4 w-4 text-[var(--text-muted)] opacity-0 group-hover:opacity-100 transition-opacity duration-200" />
        </div>
      </Surface>
    </motion.div>
  )
}
