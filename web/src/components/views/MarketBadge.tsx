/**
 * MarketBadge — 市场标识徽章
 *
 * 职责：将市场代码（CN/US/HK）渲染为带颜色的徽章标签。
 * 样式委托给 CVA variants（lib/variants.ts），设计考古后只需改一处。
 *
 * 关注点分离：
 *   - 零业务逻辑（只有展示映射）
 *   - 零外部依赖（不调用 hooks）
 *   - 样式自包含（通过 CVA variants）
 */

import { marketBadgeVariants } from '@/lib/variants'

interface MarketBadgeProps {
  /** 市场代码：CN（A股）/ US（美股）/ HK（港股） */
  market: string
}

export function MarketBadge({ market }: MarketBadgeProps) {
  return (
    <span className={marketBadgeVariants({ market: market as 'CN' | 'US' | 'HK' })}>
      {market}
    </span>
  )
}
