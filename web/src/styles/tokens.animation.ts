/**
 * Animation Tokens — 动画参数集中管理
 *
 * 所有组件的动画参数从这里 import，禁止在组件中手写 magic numbers。
 * 与 CSS Primitive Token 对齐（tokens.primitive.css 中的 duration/easing）。
 *
 * @example
 * ```tsx
 * import { transition, presence, stagger } from '@/styles/tokens.animation'
 *
 * <motion.div
 *   initial={presence.slideUp.initial}
 *   animate={presence.slideUp.animate}
 *   transition={transition.layout}
 * />
 *
 * <motion.ul variants={stagger.list}>
 *   {items.map(i => <motion.li key={i} variants={presence.fade} />)}
 * </motion.ul>
 * ```
 */

import type { Transition, Variants } from 'framer-motion'

/* ── Duration（单位：秒，与 CSS --duration-* 对齐）──────── */

export const duration = {
  /** 0ms — 瞬时，用于状态重置 */
  instant: 0,
  /** 150ms — 快速反馈（hover、active、微交互） */
  fast: 0.15,
  /** 200ms — 默认过渡（淡入淡出、颜色变化） */
  normal: 0.2,
  /** 300ms — 慢速过渡（布局变化、面板展开） */
  slow: 0.3,
  /** 500ms — 更慢（重要元素出现、页面级过渡） */
  slower: 0.5,
} as const

/* ── Easing（framer-motion 格式：[x1, y1, x2, y2]）──────── */

export const easing = {
  /** linear — 匀速，用于透明度渐变 */
  linear: [0, 0, 1, 1] as [number, number, number, number],
  /** ease-out — 快速开始、缓慢结束（最常用） */
  out: [0, 0, 0.2, 1] as [number, number, number, number],
  /** ease-in-out — 对称缓动（布局变化） */
  inOut: [0.4, 0, 0.2, 1] as [number, number, number, number],
  /** spring-like — 弹性回弹（按钮、chip、提示） */
  spring: [0.34, 1.56, 0.64, 1] as [number, number, number, number],
} as const

/* ── Transition Presets — 常用组合 ─────────────────────── */

export const transition = {
  /** 默认淡入淡出 — 大多数元素的默认出现方式 */
  fade: {
    duration: duration.normal,
    ease: easing.out,
  } satisfies Transition,

  /** 快速反馈 — hover、active、微交互 */
  fast: {
    duration: duration.fast,
    ease: easing.out,
  } satisfies Transition,

  /** 布局变化 — Composer 位态切换、面板展开 */
  layout: {
    duration: duration.slow,
    ease: easing.inOut,
    layout: true,
  } satisfies Transition,

  /** 弹簧效果 — 按钮、chip、小规模元素的活泼反馈 */
  spring: {
    type: 'spring' as const,
    stiffness: 300,
    damping: 30,
  } satisfies Transition,

  /** 弹窗/面板出现 — 需要明显存在感 */
  popover: {
    duration: duration.slow,
    ease: easing.spring,
  } satisfies Transition,

  /** 页面级过渡 — 路由切换、大面板 */
  page: {
    duration: duration.slower,
    ease: easing.out,
  } satisfies Transition,
} as const

/* ── Stagger — 列表/网格的依次出现 ──────────────────────── */

export const stagger = {
  /** 通用列表 — 消息列表、菜单项 */
  list: {
    staggerChildren: 0.03,
    delayChildren: 0.05,
  } satisfies Variants,

  /** 表格行 — 更紧凑，避免视觉拖沓 */
  table: {
    staggerChildren: 0.015,
    delayChildren: 0.02,
  } satisfies Variants,

  /** 卡片网格 — 稍慢，让每个卡片有独立感 */
  grid: {
    staggerChildren: 0.04,
    delayChildren: 0.1,
  } satisfies Variants,

  /** 仪表盘统计卡片 — 依次亮相 */
  stats: {
    staggerChildren: 0.06,
    delayChildren: 0.08,
  } satisfies Variants,
} as const

/* ── Presence — AnimatePresence 的 enter/exit 模式 ──────── */

export const presence = {
  /** 纯淡入淡出 — 最保守，不会引起布局抖动 */
  fade: {
    initial: { opacity: 0 },
    animate: { opacity: 1 },
    exit: { opacity: 0 },
  } satisfies Variants,

  /** 从下方滑入 — 列表项、卡片、消息气泡 */
  slideUp: {
    initial: { opacity: 0, y: 8 },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: 4 },
  } satisfies Variants,

  /** 从上方滑入 — 下拉菜单、tooltip */
  slideDown: {
    initial: { opacity: 0, y: -4, scale: 0.98 },
    animate: { opacity: 1, y: 0, scale: 1 },
    exit: { opacity: 0, y: -4, scale: 0.98 },
  } satisfies Variants,

  /** 缩放弹出 — tooltip、toast、小面板 */
  scale: {
    initial: { opacity: 0, scale: 0.96 },
    animate: { opacity: 1, scale: 1 },
    exit: { opacity: 0, scale: 0.96 },
  } satisfies Variants,

  /** 从右侧滑入 — 侧边面板、Artifact 面板 */
  slideRight: {
    initial: { opacity: 0, x: 24 },
    animate: { opacity: 1, x: 0 },
    exit: { opacity: 0, x: 16 },
  } satisfies Variants,

  /** 从左侧滑入 — 返回导航、面包屑 */
  slideLeft: {
    initial: { opacity: 0, x: -16 },
    animate: { opacity: 1, x: 0 },
    exit: { opacity: 0, x: -8 },
  } satisfies Variants,

  /** 高度展开 — 折叠面板、手风琴 */
  height: {
    initial: { opacity: 0, height: 0 },
    animate: { opacity: 1, height: 'auto' },
    exit: { opacity: 0, height: 0 },
  } satisfies Variants,
} as const

/* ── Composer 专用 — 位态切换动画（匹配现有行为）────────── */

export const composerTransition = {
  /** 标题出现/消失 */
  title: {
    initial: { opacity: 0, y: 10 },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: -10 },
    transition: { duration: duration.normal, ease: easing.out },
  } satisfies Record<string, unknown>,

  /** 输入框位态切换（居中 → 底部停靠） */
  dock: {
    layout: true,
    transition: { duration: duration.slow, ease: easing.inOut },
  } satisfies Record<string, unknown>,
} as const

/* ── Skeleton 专用 — 加载骨架屏 shimmer ────────────────── */

export const skeletonTransition = {
  /** shimmer 扫光动画 */
  shimmer: {
    initial: { x: '-100%' },
    animate: { x: '100%' },
    transition: {
      repeat: Infinity,
      duration: 1.5,
      ease: 'linear',
    },
  } satisfies Record<string, unknown>,
} as const
