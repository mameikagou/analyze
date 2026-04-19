/**
 * Surface — 所有带背景色块的基础容器
 *
 * 核心武器：用 Surface 替代所有裸写的 `<div className="bg-white">`。
 * 通过 variant 控制背景层级，确保页面上的色块关系始终符合设计系统的
 * canvas → surface → elevated 梯度。
 *
 * @example
 * ```tsx
 * // ✅ 正确
 * <Surface variant="canvas" className="min-h-screen">
 *   <Surface variant="surface" className="rounded-xl p-6">
 *     卡片内容
 *   </Surface>
 * </Surface>
 *
 * // ❌ 错误 — 裸写 bg-white，绕过设计系统
 * <div className="bg-white rounded-xl p-6">
 *   卡片内容
 * </div>
 * ```
 */
import { cn } from '@/lib/utils'

export type SurfaceVariant =
  | 'canvas'      /* 页面最底层底色 */
  | 'surface'     /* 卡片、面板、消息区 */
  | 'elevated'    /* 弹层、下拉、Artifact 面板 */
  | 'hover'       /* hover 态预览 */
  | 'active'      /* active/pressed 态预览 */
  | 'selected'    /* 选中态预览 */

const variantToClass: Record<SurfaceVariant, string> = {
  canvas:   'bg-[var(--bg-canvas)]',
  surface:  'bg-[var(--bg-surface)]',
  elevated: 'bg-[var(--bg-elevated)]',
  hover:    'bg-[var(--bg-hover)]',
  active:   'bg-[var(--bg-active)]',
  selected: 'bg-[var(--bg-selected)]',
}

export interface SurfaceProps extends React.ComponentProps<'div'> {
  /**
   * 背景层级 variant
   * @default 'surface'
   */
  variant?: SurfaceVariant
  /**
   * 是否添加边框。Claude 风格中大多数 surface 有极淡的 hairline 边框。
   * @default false（需要时显式开启）
   */
  bordered?: boolean
  /**
   * 圆角大小。默认不给圆角，由使用者决定（Claude 中不同组件圆角不同）。
   * 常用值：rounded-xl(16px) 用于卡片，rounded-2xl(24px) 用于输入框。
   * @default undefined
   */
  rounded?: 'sm' | 'md' | 'lg' | 'xl' | '2xl' | '3xl' | 'full'
  /**
   * 是否添加阴影。Claude 极少用阴影，基本只有 elevated 面板需要。
   * @default false
   */
  shadow?: boolean
}

export function Surface({
  variant = 'surface',
  bordered = false,
  rounded,
  shadow = false,
  className,
  children,
  ...props
}: SurfaceProps) {
  const roundedClass = rounded ? `rounded-${rounded}` : undefined

  return (
    <div
      className={cn(
        variantToClass[variant],
        bordered && 'border border-[var(--border-subtle)]',
        roundedClass,
        shadow && 'shadow-[var(--shadow-elevated)]',
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}
