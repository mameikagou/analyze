/**
 * TextButton — 文字按钮原语
 *
 * Claude 风格特征：
 * - 以文字为主，可带图标
 * - 默认透明底 + hover 变 surface 色
 * - accent 变体用于主行动点（CTA）
 * - subtle 变体用于次要操作
 *
 * @example
 * ```tsx
 * <TextButton onClick={() => {}}>取消</TextButton>
 *
 * <TextButton variant="accent" onClick={() => {}}>
 *   确认
 * </TextButton>
 *
 * <TextButton variant="subtle" size="sm" icon={<ArrowLeft className="h-4 w-4" />}>
 *   返回
 * </TextButton>
 * ```
 */
import { cn } from '@/lib/utils'

export interface TextButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  /** 视觉变体 */
  variant?: 'default' | 'accent' | 'subtle' | 'danger'
  /** 尺寸 */
  size?: 'sm' | 'md' | 'lg'
  /** 左侧图标 */
  icon?: React.ReactNode
  /** 图标位置 */
  iconPosition?: 'left' | 'right'
}

const sizeMap = {
  sm: 'px-3 py-1.5 text-xs',
  md: 'px-4 py-2 text-sm',
  lg: 'px-5 py-2.5 text-sm',
}

export function TextButton({
  variant = 'default',
  size = 'md',
  icon,
  iconPosition = 'left',
  className,
  disabled,
  children,
  ...props
}: TextButtonProps) {
  const content = (
    <>
      {icon && iconPosition === 'left' && (
        <span className="inline-flex items-center">{icon}</span>
      )}
      <span>{children}</span>
      {icon && iconPosition === 'right' && (
        <span className="inline-flex items-center">{icon}</span>
      )}
    </>
  )

  return (
    <button
      type="button"
      disabled={disabled}
      className={cn(
        /* 基础 */
        'inline-flex items-center justify-center gap-2',
        'shrink-0',
        'rounded-[var(--radius-md)]',
        'font-medium',
        'transition-all duration-150 ease-out',
        'focus:outline-none focus:ring-2 focus:ring-[var(--ring-focus)]',

        /* 尺寸 */
        sizeMap[size],

        /* 默认变体：透明底 + hover */
        variant === 'default' && [
          'text-[var(--text-secondary)]',
          !disabled && 'hover:bg-[var(--button-ghost-hover)] hover:text-[var(--text-primary)]',
        ],

        /* Accent 变体：主行动点 */
        variant === 'accent' && [
          'bg-[var(--accent-primary)] text-[var(--text-inverse)]',
          !disabled && 'hover:opacity-90',
        ],

        /* Subtle 变体：次要操作 */
        variant === 'subtle' && [
          'bg-[var(--bg-hover)] text-[var(--text-secondary)]',
          !disabled && 'hover:bg-[var(--bg-active)] hover:text-[var(--text-primary)]',
        ],

        /* Danger 变体 */
        variant === 'danger' && [
          'text-[var(--accent-error)]',
          !disabled && 'hover:bg-[var(--accent-error-subtle)]',
        ],

        /* 禁用 */
        disabled && 'opacity-40 cursor-not-allowed',

        className
      )}
      {...props}
    >
      {content}
    </button>
  )
}
