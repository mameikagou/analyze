/**
 * useToast — 全局 Toast 通知系统
 *
 * 【设计意图】
 * 提供一处集中的轻量级通知机制，替代各页面内联的 error/success div。
 * 支持自动消失、多类型（success/error/info）、堆叠展示。
 *
 * 使用方式：
 *   const { toast } = useToast()
 *   toast({ type: 'error', message: '回测失败' })
 *
 * 需要在根组件包裹 ToastProvider：
 *   <ToastProvider><App /></ToastProvider>
 */

import { createContext, useContext, useState, useCallback, useRef } from 'react'

export type ToastType = 'success' | 'error' | 'info'

export interface ToastItem {
  id: string
  type: ToastType
  message: string
}

interface ToastContextValue {
  toasts: ToastItem[]
  toast: (options: { type?: ToastType; message: string; duration?: number }) => void
  dismiss: (id: string) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

let globalId = 0
function generateId(): string {
  return `toast-${++globalId}-${Date.now()}`
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const timersRef = useRef<Map<string, number>>(new Map())

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
    const timer = timersRef.current.get(id)
    if (timer) {
      window.clearTimeout(timer)
      timersRef.current.delete(id)
    }
  }, [])

  const toast = useCallback(
    ({
      type = 'info',
      message,
      duration = 4000,
    }: {
      type?: ToastType
      message: string
      duration?: number
    }) => {
      const id = generateId()
      const item: ToastItem = { id, type, message }
      setToasts((prev) => [...prev, item])

      const timer = window.setTimeout(() => {
        dismiss(id)
      }, duration)
      timersRef.current.set(id, timer)
    },
    [dismiss]
  )

  return (
    <ToastContext.Provider value={{ toasts, toast, dismiss }}>
      {children}
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) {
    throw new Error('useToast must be used within a ToastProvider')
  }
  return ctx
}
