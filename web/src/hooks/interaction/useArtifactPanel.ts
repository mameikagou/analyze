/**
 * useArtifactPanel — 管理 Artifact 面板的三态
 *
 * Artifact 是 Claude 中右侧滑出的代码/图表/预览面板。
 * 有三种状态：
 * - closed:    完全关闭
 * - peek:      边缘露出一点预览（未完全打开）
 * - expanded:  完全展开
 *
 * 同时管理与对话流的宽度联动（Artifact 打开时，对话流变窄）。
 *
 * @example
 * ```tsx
 * const artifact = useArtifactPanel()
 *
 * // 在消息中检测到代码块时 peek
 * useEffect(() => {
 *   if (hasCodeBlock) artifact.peek()
 * }, [hasCodeBlock])
 *
 * // 点击打开
 * <button onClick={artifact.expand}>Open Artifact</button>
 *
 * // 条件渲染
 * {artifact.isOpen && (
 *   <ArtifactPanel width={artifact.width} onClose={artifact.close}>
 *     ...
 *   </ArtifactPanel>
 * )}
 * ```
 */
import { useState, useCallback, useMemo } from 'react'

export type ArtifactStatus = 'closed' | 'peek' | 'expanded'

export interface ArtifactPanelState {
  /** 当前状态 */
  status: ArtifactStatus
  /** 是否打开（peek 或 expanded） */
  isOpen: boolean
  /** 是否完全展开 */
  isExpanded: boolean
  /** 面板宽度 */
  width: number | string
  /** 关闭 */
  close: () => void
  /** 边缘露出 */
  peek: () => void
  /** 完全展开 */
  expand: () => void
  /** 切换 */
  toggle: () => void
}

const PEEK_WIDTH = 60     /* px — 边缘露出的宽度 */
const EXPANDED_WIDTH = 640 /* px — 完全展开的宽度 */

export function useArtifactPanel(): ArtifactPanelState {
  const [status, setStatus] = useState<ArtifactStatus>('closed')

  const isOpen = status !== 'closed'
  const isExpanded = status === 'expanded'

  const width = useMemo(() => {
    switch (status) {
      case 'peek':
        return PEEK_WIDTH
      case 'expanded':
        return EXPANDED_WIDTH
      default:
        return 0
    }
  }, [status])

  const close = useCallback(() => {
    setStatus('closed')
  }, [])

  const peek = useCallback(() => {
    setStatus((prev) => (prev === 'closed' ? 'peek' : prev))
  }, [])

  const expand = useCallback(() => {
    setStatus('expanded')
  }, [])

  const toggle = useCallback(() => {
    setStatus((prev) => {
      if (prev === 'closed') return 'expanded'
      if (prev === 'peek') return 'expanded'
      return 'closed'
    })
  }, [])

  return {
    status,
    isOpen,
    isExpanded,
    width,
    close,
    peek,
    expand,
    toggle,
  }
}
