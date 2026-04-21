/**
 * StatsCard — 仪表盘统计卡片
 *
 * 【2026-04-21 重构说明】
 * 本次重构将裸写的 bg-[var(--bg-surface)] 替换为 design-system/Surface 组件，
 * 确保卡片背景层级受设计系统统一管理。
 * 新增 sparkline 属性支持迷你折线图，用于展示趋势微缩预览。
 * 将趋势色从 Primitive Token（--green-600/--red-600）迁移到 Semantic Token
 *（--accent-success/--accent-error），保证暗色模式下色值正确映射。
 *
 * 副作用：
 *   - 引入 Surface 组件依赖（已存在）
 *   - sparkline 为可选属性，不传时行为与之前完全一致
 */

import { motion } from 'framer-motion'
import { TrendingUp, TrendingDown, Minus, type LucideIcon } from 'lucide-react'
import { Surface } from '@/components/design-system/Surface'
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
  /** 左侧图标（Lucide icon component） */
  icon?: LucideIcon
  /** 迷你折线图数据（可选） */
  sparkline?: number[]
}

const MotionSurface = motion(Surface)

function SparklineSVG({
  data,
  trend,
}: {
  data: number[]
  trend?: 'up' | 'down' | 'neutral'
}) {
  if (data.length < 2) return null

  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1

  const width = 120
  const height = 32
  const padding = 2

  const points = data
    .map((v, i) => {
      const x = padding + (i / (data.length - 1)) * (width - padding * 2)
      const y = padding + (1 - (v - min) / range) * (height - padding * 2)
      return `${x},${y}`
    })
    .join(' ')

  const strokeColor =
    trend === 'up'
      ? 'var(--accent-success)'
      : trend === 'down'
        ? 'var(--accent-error)'
        : 'var(--text-muted)'

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className="overflow-visible opacity-60"
    >
      <polyline
        fill="none"
        stroke={strokeColor}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
      />
    </svg>
  )
}

export function StatsCard({
  title,
  value,
  subtitle,
  trend = 'neutral',
  trendValue,
  icon: Icon,
  sparkline,
}: StatsCardProps) {
  const TrendIcon =
    trend === 'up' ? TrendingUp : trend === 'down' ? TrendingDown : Minus

  const trendColor =
    trend === 'up'
      ? 'text-[var(--accent-success)]'
      : trend === 'down'
        ? 'text-[var(--accent-error)]'
        : 'text-[var(--text-muted)]'

  return (
    <MotionSurface
      variant="surface"
      bordered
      rounded="xl"
      className="p-5"
      variants={presence.slideUp}
      initial="initial"
      animate="animate"
      transition={transition.fade}
    >
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            {Icon && <Icon className="h-4 w-4 text-[var(--text-muted)]" />}
            <p className="text-sm font-medium text-[var(--text-muted)]">{title}</p>
          </div>
          <p className="text-2xl font-bold tabular-nums tracking-tight text-[var(--text-primary)]">
            {value}
          </p>
        </div>

        <div className="flex flex-col items-end gap-2">
          {trendValue && (
            <div
              className={`flex items-center gap-1 text-xs font-medium ${trendColor}`}
            >
              <TrendIcon className="h-3.5 w-3.5" />
              <span>{trendValue}</span>
            </div>
          )}
          {sparkline && <SparklineSVG data={sparkline} trend={trend} />}
        </div>
      </div>

      {subtitle && (
        <p className="mt-2 text-xs text-[var(--text-faint)]">{subtitle}</p>
      )}
    </MotionSurface>
  )
}
