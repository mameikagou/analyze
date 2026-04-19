/**
 * MADiffIndicator — MA 均线差值指示器
 *
 * 职责：展示 MA 短期均线相对长期均线的偏离百分比，
 * 用颜色标识趋势强度（strong/moderate/weak/negative）。
 *
 * 关注点分离：
 *   - 数值 → 强度的映射封装在 maDiffToStrength（lib/variants.ts）
 *   - 正负号、百分比格式化在组件内处理
 */

import { ArrowUp, ArrowDown, Minus } from 'lucide-react'
import { maDiffVariants, maDiffToStrength } from '@/lib/variants'

interface MADiffIndicatorProps {
  /** MA 差值百分比（如 3.5 表示 +3.5%） */
  maDiffPct: number
  /** 是否显示箭头图标 */
  showIcon?: boolean
}

export function MADiffIndicator({ maDiffPct, showIcon = true }: MADiffIndicatorProps) {
  const strength = maDiffToStrength(maDiffPct)
  const isPositive = maDiffPct >= 0

  const Icon = isPositive
    ? ArrowUp
    : maDiffPct < 0
      ? ArrowDown
      : Minus

  return (
    <span className={maDiffVariants({ strength })}>
      {showIcon && (
        <Icon className="h-3 w-3" aria-hidden="true" />
      )}
      <span>
        {isPositive ? '+' : ''}
        {maDiffPct.toFixed(2)}%
      </span>
    </span>
  )
}
