import { cn } from '@/lib/utils'

type SignalTone = 'positive' | 'negative' | 'neutral' | 'warning'

interface SignalBadgeProps {
  children: React.ReactNode
  tone?: SignalTone
  className?: string
}

const toneClass: Record<SignalTone, string> = {
  positive: 'border-[var(--signal-positive)] bg-[var(--signal-positive-subtle)] text-[var(--signal-positive)]',
  negative: 'border-[var(--signal-negative)] bg-[var(--signal-negative-subtle)] text-[var(--signal-negative)]',
  neutral: 'border-[var(--border-subtle)] bg-[var(--signal-neutral-subtle)] text-[var(--signal-neutral)]',
  warning: 'border-[var(--signal-warning)] bg-[var(--signal-warning-subtle)] text-[var(--signal-warning)]',
}

export function SignalBadge({ children, tone = 'neutral', className }: SignalBadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium',
        toneClass[tone],
        className
      )}
    >
      {children}
    </span>
  )
}
