/**
 * IconButton — 图标按钮原语
 *
 * Claude 风格特征：
 * - 透明底 + hover 变 surface 色
 * - 极少实心填充
 * - 固定 32px 的方形
 * - rounded-md 圆角
 *
 * @example
 * ```tsx
 * <IconButton
 *   icon={<Settings className="h-5 w-5" />}
 *   aria-label="Settings"
 *   onClick={() => {}}
 * />
 *
 * // Accent 变体（发送按钮等强调场景）
 * <IconButton
 *   icon={<Send className="h-5 w-5" />}
 *   variant="accent"
 *   aria-label="Send"
 * />
 * ```
 */
import { cn } from '@/lib/utils'

export interface IconButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  /** 图标 React 节点 */
  icon: React.ReactNode
  /** 视觉变体 */
  variant?: 'default' | 'accent' | 'danger'
  /** 尺寸 */
  size?: 'sm' | 'md' | 'lg'
  /** 是否激活（按下态） */
  active?: boolean
}

const sizeMap = {
  sm: 'h-7 w-7',
  md: 'h-8 w-8',
  lg: 'h-10 w-10',
}

const iconSizeMap = {
  sm: '[&_svg]:h-4 [&_svg]:w-4',
  md: '[&_svg]:h-5 [&_svg]:w-5',
  lg: '[&_svg]:h-5 [&_svg]:w-5',
}

export function IconButton({
  icon,
  variant = 'default',
  size = 'md',
  active = false,
  className,
  disabled,
  ...props
}: IconButtonProps) {
  return (
    <button
      type="button"
      disabled={disabled}
      className={cn(
        /* 基础 */
        'inline-flex items-center justify-center',
        'shrink-0',
        sizeMap[size],
        'rounded-[var(--button-icon-radius)]',
        'transition-all duration-150 ease-out',

        /* 默认变体：透明底 + hover */
        variant === 'default' && [
          'text-[var(--text-secondary)]',
          !disabled && 'hover:bg-[var(--button-ghost-hover)] hover:text-[var(--text-primary)]',
          active && 'bg-[var(--button-ghost-active)] text-[var(--text-primary)]',
        ],

        /* Accent 变体：橙色 */
        variant === 'accent' && [
          'bg-[var(--accent-primary)] text-white',
          !disabled && 'hover:bg-[var(--accent-primary-hover)]',
          active && 'opacity-90',
        ],

        /* Danger 变体 */
        variant === 'danger' && [
          'text-[var(--accent-error)]',
          !disabled && 'hover:bg-[var(--accent-error-subtle)]',
        ],

        /* 禁用 */
        disabled && 'opacity-40 cursor-not-allowed',

        /* 图标尺寸 */
        iconSizeMap[size],
        '[&_svg]:shrink-0',

        className
      )}
      {...props}
    >
      {icon}
    </button>
  )
}
