import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { Surface } from '@/components/design-system/Surface'

interface PageShellProps {
  children: ReactNode
  className?: string
}

export function PageShell({ children, className }: PageShellProps) {
  return (
    <Surface variant="canvas" className={cn('min-h-full px-4 py-6 sm:px-6 lg:px-8', className)}>
      <div className="mx-auto w-full max-w-6xl space-y-6">{children}</div>
    </Surface>
  )
}
