/**
 * CVA Variants — 业务组件通用样式变体
 *
 * 纯样式定义，零业务逻辑。
 * 所有视图组件共享的 variant 集合集中管理，设计考古后只需改这一处。
 *
 * 命名约定：
 *   - xxxVariants = cva() 返回值（供组件内部使用）
 *   - xxxVariant = TypeScript 联合类型（供组件 Props 使用）
 *
 * @example
 * ```tsx
 * import { marketBadgeVariants, type MarketBadgeVariant } from '@/lib/variants'
 *
 * export function MarketBadge({ market }: { market: MarketBadgeVariant }) {
 *   return <span className={marketBadgeVariants({ market })}>{market}</span>
 * }
 * ```
 */

import { cva, type VariantProps } from 'class-variance-authority'

/* ═══════════════════════════════════════════════════════
   Market Badge — 市场标识
   ═══════════════════════════════════════════════════════ */

export const marketBadgeVariants = cva(
  'inline-flex items-center rounded-md px-1.5 py-0.5 text-xs font-medium uppercase tracking-wide',
  {
    variants: {
      market: {
        CN: 'bg-[var(--accent-error-subtle)] text-[var(--accent-error)]',
        US: 'bg-[var(--accent-info-subtle)] text-[var(--accent-info)]',
        HK: 'bg-[var(--accent-primary-subtle)] text-[var(--accent-primary)]',
      },
    },
    defaultVariants: {
      market: 'CN',
    },
  }
)

export type MarketBadgeVariant = VariantProps<typeof marketBadgeVariants>['market']

/* ═══════════════════════════════════════════════════════
   Score Badge — 量化评分等级
   ═══════════════════════════════════════════════════════ */

export const scoreBadgeVariants = cva(
  'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold',
  {
    variants: {
      level: {
        excellent:
          'bg-[var(--accent-success-subtle)] text-[var(--accent-success)]',
        good:
          'bg-[var(--accent-info-subtle)] text-[var(--accent-info)]',
        average:
          'bg-[var(--accent-primary-subtle)] text-[var(--accent-primary)]',
        poor:
          'bg-[var(--accent-error-subtle)] text-[var(--accent-error)]',
      },
    },
    defaultVariants: {
      level: 'average',
    },
  }
)

export type ScoreBadgeVariant = VariantProps<typeof scoreBadgeVariants>['level']

/**
 * 将数值分数映射到等级
 *   >= 80 → excellent
 *   >= 60 → good
 *   >= 40 → average
 *   <  40 → poor
 */
export function scoreToLevel(score: number): ScoreBadgeVariant {
  if (score >= 80) return 'excellent'
  if (score >= 60) return 'good'
  if (score >= 40) return 'average'
  return 'poor'
}

/* ═══════════════════════════════════════════════════════
   Purchase Status Badge — 申购状态
   ═══════════════════════════════════════════════════════ */

export const purchaseStatusVariants = cva(
  'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
  {
    variants: {
      status: {
        open:
          'bg-[var(--accent-success-subtle)] text-[var(--accent-success)]',
        limit:
          'bg-[var(--accent-primary-subtle)] text-[var(--accent-primary)]',
        closed:
          'bg-[var(--accent-error-subtle)] text-[var(--accent-error)]',
        suspended:
          'bg-[var(--bg-active)] text-[var(--text-muted)]',
      },
    },
    defaultVariants: {
      status: 'open',
    },
  }
)

export type PurchaseStatusVariant = VariantProps<typeof purchaseStatusVariants>['status']

/* ═══════════════════════════════════════════════════════
   MA Diff Indicator — MA 差值强度
   ═══════════════════════════════════════════════════════ */

export const maDiffVariants = cva(
  'inline-flex items-center font-mono text-sm font-medium tabular-nums',
  {
    variants: {
      strength: {
        strong:
          'text-[var(--accent-success)]',
        moderate:
          'text-[var(--accent-info)]',
        weak:
          'text-[var(--accent-primary)]',
        negative:
          'text-[var(--accent-error)]',
      },
    },
    defaultVariants: {
      strength: 'weak',
    },
  }
)

export type MADiffVariant = VariantProps<typeof maDiffVariants>['strength']

/**
 * 将 MA 差值百分比映射到强度等级
 *   >= 5%  → strong    (明显多头排列)
 *   >= 2%  → moderate  (健康多头)
 *   >= 0%  → weak      (多头但微弱)
 *   <  0%  → negative  (空头/跌破)
 */
export function maDiffToStrength(pct: number): MADiffVariant {
  if (pct >= 5) return 'strong'
  if (pct >= 2) return 'moderate'
  if (pct >= 0) return 'weak'
  return 'negative'
}

/* ═══════════════════════════════════════════════════════
   Trend Indicator — 涨跌趋势
   ═══════════════════════════════════════════════════════ */

export const trendVariants = cva('inline-flex items-center gap-1 text-sm font-medium', {
  variants: {
    direction: {
      up: 'text-[var(--accent-success)]',
      down: 'text-[var(--accent-error)]',
      neutral: 'text-[var(--text-muted)]',
    },
  },
  defaultVariants: {
    direction: 'neutral',
  },
})

export type TrendVariant = VariantProps<typeof trendVariants>['direction']

/* ═══════════════════════════════════════════════════════
   Volatility Badge — 波动率等级
   ═══════════════════════════════════════════════════════ */

export const volatilityVariants = cva(
  'inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium',
  {
    variants: {
      level: {
        high: 'bg-[var(--accent-error-subtle)] text-[var(--accent-error)]',
        medium: 'bg-[var(--accent-primary-subtle)] text-[var(--accent-primary)]',
        low: 'bg-[var(--accent-success-subtle)] text-[var(--accent-success)]',
      },
    },
    defaultVariants: {
      level: 'medium',
    },
  }
)

export type VolatilityVariant = VariantProps<typeof volatilityVariants>['level']
