/**
 * AutoTextarea — 自动撑高的输入框
 *
 * Claude 风格特征：
 * - 大圆角（rounded-2xl / 24px）
 * - 无边框或极淡边框，focus 时只有极淡的 ring
 * - transition-[height] 平滑动画
 * - placeholder 用 muted 色
 * - 自动根据内容撑高，有最大高度限制
 *
 * @example
 * ```tsx
 * const [value, setValue] = useState('')
 * <AutoTextarea
 *   value={value}
 *   onChange={setValue}
 *   placeholder="Ask anything..."
 * />
 * ```
 */
import { useRef, useEffect, useCallback } from 'react'
import { cn } from '@/lib/utils'

export interface AutoTextareaProps
  extends Omit<React.ComponentProps<'textarea'>, 'onChange'> {
  value: string
  onChange: (value: string) => void
  /** placeholder 文字 */
  placeholder?: string
  /** 是否禁用 */
  disabled?: boolean
  /** 额外的 className */
  className?: string
}

export function AutoTextarea({
  value,
  onChange,
  placeholder,
  disabled = false,
  className,
  ...props
}: AutoTextareaProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  /**
   * 自动调整高度：
   * 1. 先重置为 auto 获取 scrollHeight
   * 2. 限制在 min-height 和 max-height 之间
   * 3. 用 CSS transition 实现平滑动画
   */
  const adjustHeight = useCallback(() => {
    const el = textareaRef.current
    if (!el) return

    el.style.height = 'auto'
    const minH = 56  // var(--composer-min-height) ≈ 3.5rem
    const maxH = 192 // var(--composer-max-height) ≈ 12rem
    const scrollH = el.scrollHeight
    const newH = Math.min(Math.max(scrollH, minH), maxH)
    el.style.height = `${newH}px`
  }, [])

  useEffect(() => {
    adjustHeight()
  }, [value, adjustHeight])

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    onChange(e.target.value)
  }

  return (
    <textarea
      ref={textareaRef}
      value={value}
      onChange={handleChange}
      placeholder={placeholder}
      disabled={disabled}
      rows={1}
      className={cn(
        /* 基础 */
        'w-full resize-none',
        'bg-transparent',
        'text-[0.9375rem] leading-relaxed',
        'text-[var(--text-primary)]',
        'placeholder:text-[var(--composer-placeholder)]',

        /* focus — 极淡的 ring，不是粗边框 */
        'focus:outline-none',
        'focus:ring-0',

        /* 高度动画 */
        'transition-[height] duration-200 ease-out',

        /* 禁用 */
        'disabled:opacity-50 disabled:cursor-not-allowed',

        className
      )}
      style={{ minHeight: '3.5rem' }}
      {...props}
    />
  )
}
