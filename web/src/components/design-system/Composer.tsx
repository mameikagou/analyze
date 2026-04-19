/**
 * Composer — 输入框的两种位态
 *
 * Claude 的输入框有两种位置状态：
 * 1. Centered（居中）— 空态首页，输入框在屏幕中央
 * 2. Docked（底部停靠）— 对话中，输入框固定在底部
 *
 * 通过一个 isCentered 属性切换，内部处理过渡动画。
 *
 * @example
 * ```tsx
 * const composer = useComposerState()
 *
 * <Composer
 *   isCentered={composer.shouldCenterComposer}
 *   value={composer.input}
 *   onChange={composer.setInput}
 *   onSubmit={composer.submit}
 *   isLoading={composer.isSubmitting}
 * />
 * ```
 */
import { cn } from '@/lib/utils'
import { AutoTextarea } from './AutoTextarea'
import { IconButton } from './IconButton'
import { Send, Paperclip } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

export interface ComposerProps {
  /** 当前是否居中（空态） */
  isCentered: boolean
  /** 输入值 */
  value: string
  /** 输入变化回调 */
  onChange: (value: string) => void
  /** 提交回调 */
  onSubmit: () => void
  /** 是否正在提交 */
  isLoading?: boolean
  /** 是否禁用 */
  disabled?: boolean
  /** placeholder 文字 */
  placeholder?: string
}

export function Composer({
  isCentered,
  value,
  onChange,
  onSubmit,
  isLoading = false,
  disabled = false,
  placeholder = 'Ask anything...',
}: ComposerProps) {
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!value.trim() || isLoading) return
    onSubmit()
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (!value.trim() || isLoading) return
      onSubmit()
    }
  }

  return (
    <div
      className={cn(
        'flex w-full flex-col items-center',
        isCentered ? 'justify-center' : 'justify-end'
      )}
    >
      {/* 居中态的标题提示 — AnimatePresence 进出动画 */}
      <AnimatePresence>
        {isCentered && (
          <motion.h1
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.25, ease: [0, 0, 0.2, 1] }}
            className={cn(
              'mb-8 text-center text-3xl font-semibold tracking-tight',
              'text-[var(--text-primary)]'
            )}
          >
            What can I help you with?
          </motion.h1>
        )}
      </AnimatePresence>

      {/* 输入框容器 — 位态切换动画 */}
      <motion.form
        onSubmit={handleSubmit}
        layout
        transition={{ type: 'spring', stiffness: 300, damping: 30 }}
        className={cn(
          'relative flex w-full items-end gap-2',
          'rounded-[var(--composer-radius)]',
          'border border-[var(--composer-border)]',
          'bg-[var(--composer-bg)]',
          'shadow-[var(--composer-shadow)]',
          'px-[var(--composer-padding-x)] py-[var(--composer-padding-y)]',
          'transition-colors duration-200 ease-out',
          'focus-within:border-[var(--composer-border-focus)]',
          'focus-within:shadow-[var(--composer-shadow-focus)]',
          'hover:border-[var(--composer-border-hover)]',
          isCentered ? 'max-w-2xl' : 'max-w-3xl'
        )}
      >
        {/* 附件按钮 */}
        <IconButton
          type="button"
          icon={<Paperclip className="h-5 w-5" />}
          aria-label="Attach file"
          disabled={disabled || isLoading}
        />

        {/* 自动撑高输入框 */}
        <AutoTextarea
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          disabled={disabled || isLoading}
          onKeyDown={handleKeyDown}
          className="flex-1"
        />

        {/* 发送按钮 — 变体切换动画 */}
        <motion.div layout transition={{ duration: 0.15 }}>
          <IconButton
            type="submit"
            icon={<Send className="h-5 w-5" />}
            aria-label="Send message"
            disabled={disabled || isLoading || !value.trim()}
            variant={value.trim() ? 'accent' : 'default'}
          />
        </motion.div>
      </motion.form>

      {/* 底部快捷按钮（仅居中态） */}
      <AnimatePresence>
        {isCentered && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2, ease: [0, 0, 0.2, 1], delay: 0.05 }}
            className="mt-4 flex flex-wrap justify-center gap-2"
          >
            {['Analyze trends', 'Screen funds', 'Compare ETFs'].map((label) => (
              <button
                key={label}
                type="button"
                onClick={() => onChange(label)}
                className={cn(
                  'rounded-lg px-3 py-1.5 text-sm',
                  'border border-[var(--border-subtle)]',
                  'text-[var(--text-secondary)]',
                  'transition-colors duration-150 ease-out',
                  'hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]'
                )}
              >
                {label}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
