import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { Surface } from '@/components/design-system/Surface'

interface ArchiveTableProps {
  children: ReactNode
  className?: string
  contentClassName?: string
}

export function ArchiveTable({ children, className, contentClassName }: ArchiveTableProps) {
  return (
    <Surface variant="surface" bordered rounded="lg" className={cn('overflow-hidden', className)}>
      <div className={cn('overflow-x-auto [&_td]:h-14 [&_th]:h-12 [&_th]:text-xs [&_th]:font-medium', contentClassName)}>
        {children}
      </div>
    </Surface>
  )
}
