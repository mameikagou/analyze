/**
 * Toast — 全局通知浮层
 *
 * 【设计意图】
 * 配合 useToast hook 使用，渲染在视口固定位置（bottom-right）。
 * 支持 success / error / info 三种类型，自动消失 + 手动关闭。
 * 使用 Framer Motion 做进入/退出动画，尊重 reduced-motion。
 */

import { motion, AnimatePresence, useReducedMotion } from 'framer-motion'
import { X, CheckCircle, AlertCircle, Info } from 'lucide-react'
import { useToast } from '@/hooks/useToast'
import { transition } from '@/styles/tokens.animation'

const typeConfig = {
  success: {
    icon: CheckCircle,
    bg: 'bg-[var(--accent-success-subtle)]',
    border: 'border-[var(--accent-success)]/20',
    text: 'text-[var(--accent-success)]',
  },
  error: {
    icon: AlertCircle,
    bg: 'bg-[var(--accent-error-subtle)]',
    border: 'border-[var(--accent-error)]/20',
    text: 'text-[var(--accent-error)]',
  },
  info: {
    icon: Info,
    bg: 'bg-[var(--accent-info-subtle)]',
    border: 'border-[var(--accent-info)]/20',
    text: 'text-[var(--accent-info)]',
  },
}

export function ToastContainer() {
  const { toasts, dismiss } = useToast()
  const shouldReduceMotion = useReducedMotion()

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none"
    >
      <AnimatePresence mode="popLayout">
        {toasts.map((toast) => {
          const config = typeConfig[toast.type]
          const Icon = config.icon

          return (
            <motion.div
              key={toast.id}
              layout
              initial={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, y: 16, scale: 0.96 }}
              animate={shouldReduceMotion ? { opacity: 1 } : { opacity: 1, y: 0, scale: 1 }}
              exit={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, x: 24, scale: 0.96 }}
              transition={shouldReduceMotion ? { duration: 0 } : transition.fast}
              className={`pointer-events-auto flex items-start gap-3 rounded-lg border ${config.border} ${config.bg} p-3 shadow-[var(--shadow-dropdown)]`}
            >
              <Icon className={`h-4 w-4 shrink-0 mt-0.5 ${config.text}`} />
              <p className="flex-1 text-sm text-[var(--text-primary)]">{toast.message}</p>
              <button
                onClick={() => dismiss(toast.id)}
                className="shrink-0 rounded p-0.5 text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] transition-colors"
                aria-label="关闭通知"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </motion.div>
          )
        })}
      </AnimatePresence>
    </div>
  )
}
