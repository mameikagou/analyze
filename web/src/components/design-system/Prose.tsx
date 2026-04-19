/**
 * Prose — Markdown 正文容器
 *
 * 固定 max-w-[768px]、font-serif 标题、font-sans 正文、预设好行高和段落间距。
 * Claude 对话流里的每一条 assistant 消息都应该被它包裹。
 *
 * @example
 * ```tsx
 * <Prose>
 *   <h2>标题</h2>
 *   <p>正文段落...</p>
 *   <ul>
 *     <li>列表项</li>
 *   </ul>
 * </Prose>
 * ```
 */
import { cn } from '@/lib/utils'

export interface ProseProps extends React.ComponentProps<'div'> {
  /**
   * 内容尺寸。Claude 中正文是 15px(base)，小字是 14px(sm)。
   * @default 'base'
   */
  size?: 'sm' | 'base'
  /**
   * 最大宽度。Claude 消息区固定 768px 阅读宽度。
   * @default 'prose'
   */
  maxWidth?: 'prose' | 'full'
}

export function Prose({
  size = 'base',
  maxWidth = 'prose',
  className,
  children,
  ...props
}: ProseProps) {
  return (
    <div
      className={cn(
        /* 容器 */
        maxWidth === 'prose' && 'max-w-[768px]',
        'mx-auto',

        /* 基础文字样式 */
        size === 'sm' ? 'text-sm leading-relaxed' : 'text-[0.9375rem] leading-relaxed',
        'text-[var(--text-primary)]',

        /* 标题：Claude 用 sans-serif 标题，但字重稍轻 */
        '[&_h1]:text-2xl [&_h1]:font-semibold [&_h1]:tracking-tight [&_h1]:mb-4 [&_h1]:mt-6 [&_h1]:text-[var(--text-primary)]',
        '[&_h2]:text-xl [&_h2]:font-semibold [&_h2]:tracking-tight [&_h2]:mb-3 [&_h2]:mt-5 [&_h2]:text-[var(--text-primary)]',
        '[&_h3]:text-lg [&_h3]:font-medium [&_h3]:tracking-tight [&_h3]:mb-2 [&_h3]:mt-4 [&_h3]:text-[var(--text-primary)]',
        '[&_h4]:text-base [&_h4]:font-medium [&_h4]:mb-2 [&_h4]:mt-3 [&_h4]:text-[var(--text-primary)]',

        /* 段落 */
        '[&_p]:mb-4 [&_p]:text-[var(--text-primary)]',

        /* 链接 */
        '[&_a]:text-[var(--text-link)] [&_a]:underline-offset-2 [&_a]:hover:text-[var(--text-link-hover)] [&_a]:hover:underline',

        /* 列表 */
        '[&_ul]:mb-4 [&_ul]:list-disc [&_ul]:pl-5',
        '[&_ol]:mb-4 [&_ol]:list-decimal [&_ol]:pl-5',
        '[&_li]:mb-1 [&_li]:text-[var(--text-primary)]',

        /* 引用块 */
        '[&_blockquote]:border-l-2 [&_blockquote]:border-[var(--border-subtle)] [&_blockquote]:pl-4 [&_blockquote]:italic [&_blockquote]:text-[var(--text-secondary)] [&_blockquote]:mb-4',

        /* 代码（行内） */
        '[&_code:not(pre_code)]:bg-[var(--code-bg)] [&_code:not(pre_code)]:px-1.5 [&_code:not(pre_code)]:py-0.5 [&_code:not(pre_code)]:rounded-md [&_code:not(pre_code)]:text-sm [&_code:not(pre_code)]:font-mono [&_code:not(pre_code)]:text-[var(--code-text)]',

        /* 水平线 */
        '[&_hr]:border-[var(--border-subtle)] [&_hr]:my-6',

        /* 粗体 */
        '[&_strong]:font-semibold [&_strong]:text-[var(--text-primary)]',

        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}
