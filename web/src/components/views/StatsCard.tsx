/**
 * StatsCard — 仪表盘统计卡片
 *
 * 职责：展示一个统计指标（标题 + 主值 + 副标题），支持趋势指示。
 * 用于首页的四个统计卡片：总基金数、今日通过 MA、平均分、数据湖记录数。
 *
 * 关注点分离：
 *   - 数据从父组件传入（title/value/subtitle/trend）
 *   - 内部动画使用 animation tokens
 *   - 样式自包含，零外部样式依赖
 */

import { motion } from 'framer-motion'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { presence, transition } from '@/styles/tokens.animation'

interface StatsCardProps {
  /** 指标标题 */
  title: string
  /** 主数值 */
  value: string | number
  /** 副标题/说明 */
  subtitle?: string
  /** 趋势方向 */
  trend?: 'up' | 'down' | 'neutral'
  /** 趋势百分比或描述 */
  trendValue?: string
}

export function StatsCard({
  title,
  value,
  subtitle,
  trend = 'neutral',
  trendValue,
}: StatsCardProps) {
  const TrendIcon = trend === 'up'
    ? TrendingUp
    : trend === 'down'
      ? TrendingDown
      : Minus

  const trendColor = trend === 'up'
    ? 'text-[var(--green-600)]'
    : trend === 'down'
      ? 'text-[var(--red-600)]'
      : 'text-[var(--text-muted)]'

  return (
    <motion.div
      className="rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-5"
      variants={presence.slideUp}
      initial="initial"
      animate="animate"
      transition={transition.fade}
    >
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <p className="text-sm font-medium text-[var(--text-muted)]">
            {title}
          </p>
          <p className="text-2xl font-bold tabular-nums tracking-tight text-[var(--text-primary)]">
            {value}
          </p>
        </div>

        {trendValue && (
          <div className={`flex items-center gap-1 text-xs font-medium ${trendColor}`}>
            <TrendIcon className="h-3.5 w-3.5" />
            <span>{trendValue}</span>
          </div>
        )}
      </div>

      {subtitle && (
        <p className="mt-2 text-xs text-[var(--text-faint)]">
          {subtitle}
        </p>
      )}
    </motion.div>
  )
}
