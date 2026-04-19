/**
 * TextButton — 文字按钮原语
 *
 * Claude 风格特征：
 * - 透明底 + hover 变 surface 色
 * - 无实心填充，无粗边框
 * - 文字色随变体变化
 *
 * @example
 * ```tsx
 * <TextButton onClick={() => {}}>Cancel</TextButton>
 * <TextButton variant="accent">Send</TextButton>
 * <TextButton variant="danger">Delete</TextButton>
 * <TextButton size="sm">Small action</TextButton>
 * ```
 */
import { cn } from '@/lib/utils'

export interface TextButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  /** 视觉变体 */
  variant?: 'default' | 'accent' | 'danger' | 'muted'
  /** 尺寸 */
  size?: 'sm' | 'md'
  /** 是否激活 */
  active?: boolean
  /** 子节点 */
  children: React.ReactNode
}

const sizeMap = {
  sm: 'h-7 px-2.5 text-sm',
  md: 'h-8 px-3 text-[0.9375rem]',
}

export function TextButton({
  variant = 'default',
  size = 'md',
  active = false,
  children,
  className,
  disabled,
  ...props
}: TextButtonProps) {
  return (
    <button
      type="button"
      disabled={disabled}
      className={cn(
        /* 基础 */
        'inline-flex items-center justify-center',
        'shrink-0 gap-1.5',
        'rounded-[var(--radius-md)]',
        'font-medium',
        'transition-all duration-150 ease-out',
        'whitespace-nowrap',

        sizeMap[size],

        /* 默认变体 */
        variant === 'default' && [
          'text-[var(--text-secondary)]',
          !disabled && 'hover:bg-[var(--button-ghost-hover)] hover:text-[var(--text-primary)]',
          active && 'bg-[var(--button-ghost-active)] text-[var(--text-primary)]',
        ],

        /* Accent 变体 */
        variant === 'accent' && [
          'text-[var(--accent-primary)]',
          !disabled && 'hover:bg-[var(--accent-primary-subtle)]',
          active && 'bg-[var(--accent-primary-subtle)]',
        ],

        /* Danger 变体 */
        variant === 'danger' && [
          'text-[var(--accent-error)]',
          !disabled && 'hover:bg-[var(--accent-error-subtle)]',
          active && 'bg-[var(--accent-error-subtle)]',
        ],

        /* Muted 变体 */
        variant === 'muted' && [
          'text-[var(--text-muted)]',
          !disabled && 'hover:text-[var(--text-secondary)]',
        ],

        /* 禁用 */
        disabled && 'opacity-40 cursor-not-allowed',

        className
      )}
      {...props}
    >
      {children}
    </button>
  )
}
