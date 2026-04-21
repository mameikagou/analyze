/**
 * PageTransition — Framer Motion 页面过渡包装器
 *
 * 包裹 <Outlet>，在路由切换时触发 slideUp + fade 动画。
 * 尊重 prefers-reduced-motion：系统设置减少动画时跳过所有动画。
 */

import { motion, AnimatePresence, useReducedMotion } from 'framer-motion'
import { useLocation } from '@tanstack/react-router'
import { presence, transition } from '@/styles/tokens.animation'

export function PageTransition({ children }: { children: React.ReactNode }) {
  const shouldReduceMotion = useReducedMotion()
  const location = useLocation()

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={location.pathname}
        initial={shouldReduceMotion ? {} : presence.slideUp.initial}
        animate={shouldReduceMotion ? {} : presence.slideUp.animate}
        exit={shouldReduceMotion ? {} : presence.slideUp.exit}
        transition={shouldReduceMotion ? { duration: 0 } : transition.fade}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  )
}
