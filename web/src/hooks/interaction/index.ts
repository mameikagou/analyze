/**
 * Claude Design System — 交互 Hook barrel export
 *
 * 规则：
 * - 禁止自己写 useState 管理 composer / artifact / streaming 状态
 * - 必须调用这些 hook
 */

export { useComposerState } from './useComposerState'
export type { ComposerState, ComposerStatus } from './useComposerState'

export { useArtifactPanel } from './useArtifactPanel'
export type { ArtifactPanelState, ArtifactStatus } from './useArtifactPanel'

export { useStreamingMessage } from './useStreamingMessage'
export type { StreamingMessageState } from './useStreamingMessage'
