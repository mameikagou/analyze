/**
 * PurchaseStatusBadge — 申购状态徽章
 *
 * 职责：将基金申购状态渲染为带颜色等级的徽章。
 * 后端返回中文状态字符串，组件内部映射为 CVA variant。
 *
 * 映射规则（基于 A 股市场常见状态）：
 *   "开放申购" / null（默认） → open（绿色）
 *   "限制申购" / "限额申购" / "限购" → limit（橙色）
 *   "暂停申购" / "暂停" → closed（红色）
 *   "封闭期" / "认购期" → suspended（灰色）
 *
 * 关注点分离：
 *   - 中文 → 英文 variant 的映射封装在此组件内
 *   - 外部只传原始字符串，不需要了解 CVA 体系
 */

import { purchaseStatusVariants, type PurchaseStatusVariant } from '@/lib/variants'

interface PurchaseStatusBadgeProps {
  /** 申购状态字符串（后端原始值） */
  status: string | null
  /** 限购金额（元），仅当 status 为 limit 时显示 */
  limit?: number | null
}

function mapStatus(raw: string | null): PurchaseStatusVariant {
  if (!raw) return 'open'

  const normalized = raw.trim()

  if (normalized.includes('开放') || normalized.includes('正常')) return 'open'
  if (normalized.includes('限制') || normalized.includes('限额') || normalized.includes('限购')) return 'limit'
  if (normalized.includes('暂停')) return 'closed'
  if (normalized.includes('封闭') || normalized.includes('认购')) return 'suspended'

  return 'open'
}

function formatStatus(raw: string | null, limitAmount: number | null): string {
  if (!raw) return '开放申购'

  const variant = mapStatus(raw)

  if (variant === 'limit' && limitAmount !== null && limitAmount !== undefined && limitAmount > 0) {
    if (limitAmount >= 10000) {
      return `限购 ${(limitAmount / 10000).toFixed(0)}万`
    }
    return `限购 ${limitAmount}元`
  }

  return raw
}

export function PurchaseStatusBadge({ status, limit }: PurchaseStatusBadgeProps) {
  const variant = mapStatus(status)
  const display = formatStatus(status, limit ?? null)

  return (
    <span className={purchaseStatusVariants({ status: variant })}>
      {display}
    </span>
  )
}
