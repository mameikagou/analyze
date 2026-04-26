import { cn } from '@/lib/utils'

type MetricTone = 'positive' | 'negative' | 'neutral' | 'warning'

interface MetricValueProps {
  value: string | number
  tone?: MetricTone
  className?: string
}

const toneClass: Record<MetricTone, string> = {
  positive: 'text-[var(--signal-positive)]',
  negative: 'text-[var(--signal-negative)]',
  neutral: 'text-[var(--text-primary)]',
  warning: 'text-[var(--signal-warning)]',
}

export function MetricValue({ value, tone = 'neutral', className }: MetricValueProps) {
  return (
    <span className={cn('font-mono tabular-nums tracking-tight', toneClass[tone], className)}>
      {value}
    </span>
  )
}
