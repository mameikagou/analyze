/**
 * Claude Design System — 原子组件 barrel export
 *
 * 导入方式：
 *   import { Surface, Prose, AutoTextarea, Composer, IconButton, TextButton } from '@/components/design-system'
 *
 * 规则：
 * - 所有新 UI 必须使用这些组件，禁止裸写 bg-white / text-gray-700 等
 * - 颜色从 CSS 变量查表：var(--bg-canvas), var(--text-primary) 等
 * - 禁止写 HEX / rgb / hsl 字面量
 */

export { Surface } from './Surface'
export type { SurfaceProps, SurfaceVariant } from './Surface'

export { Prose } from './Prose'
export type { ProseProps } from './Prose'

export { AutoTextarea } from './AutoTextarea'
export type { AutoTextareaProps } from './AutoTextarea'

export { Composer } from './Composer'
export type { ComposerProps } from './Composer'

export { IconButton } from './IconButton'
export type { IconButtonProps } from './IconButton'

export { TextButton } from './TextButton'
export type { TextButtonProps } from './TextButton'

export { PageTransition } from './PageTransition'

export { ErrorBoundary } from './ErrorBoundary'

export { ToastContainer } from './Toast'
