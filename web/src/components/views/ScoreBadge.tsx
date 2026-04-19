/**
 * ScoreBadge — 量化评分徽章
 *
 * 职责：将 0-100 的量化打分渲染为带颜色等级的徽章。
 * 等级映射：>=80 excellent / >=60 good / >=40 average / <40 poor
 *
 * 关注点分离：
 *   - 数值 → 等级的映射逻辑封装在 scoreToLevel（lib/variants.ts）
 *   - 组件只负责渲染 + 格式化显示
 */

import { scoreBadgeVariants, scoreToLevel } from '@/lib/variants'

interface ScoreBadgeProps {
  /** 量化评分（0-100），null 表示无评分 */
  score: number | null
}

export function ScoreBadge({ score }: ScoreBadgeProps) {
  if (score === null || score === undefined) {
    return (
      <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium text-[var(--text-muted)] bg-[var(--bg-elevated)]">
        —
      </span>
    )
  }

  const level = scoreToLevel(score)

  return (
    <span className={scoreBadgeVariants({ level })}>
      {score.toFixed(1)}
    </span>
  )
}
