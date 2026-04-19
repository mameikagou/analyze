/**
 * useComposerState — 管理输入框的五态状态机
 *
 * Claude 的输入框有五种状态：
 * - idle:      空态，等待输入
 * - typing:    正在输入
 * - submitting: 已提交，等待响应
 * - streaming:  正在接收流式响应
 * - error:      发生错误
 *
 * 暴露派生状态供页面组件消费，禁止页面组件自己判断 messages.length === 0。
 *
 * @example
 * ```tsx
 * const composer = useComposerState()
 *
 * // 消费派生状态
 * <Composer
 *   isCentered={composer.shouldCenterComposer}
 *   value={composer.input}
 *   onChange={composer.setInput}
 *   onSubmit={composer.submit}
 *   isLoading={composer.isSubmitting}
 * />
 * ```
 */
import { useState, useCallback, useMemo } from 'react'

export type ComposerStatus =
  | 'idle'
  | 'typing'
  | 'submitting'
  | 'streaming'
  | 'error'

export interface ComposerState {
  /** 当前状态 */
  status: ComposerStatus
  /** 输入框内容 */
  input: string
  /** 设置输入框内容 */
  setInput: (value: string) => void
  /** 是否显示居中输入框（空态） */
  shouldCenterComposer: boolean
  /** 是否可以提交 */
  canSubmit: boolean
  /** 是否正在提交 */
  isSubmitting: boolean
  /** 是否正在流式接收 */
  isStreaming: boolean
  /** 是否禁用输入 */
  isInputDisabled: boolean
  /** 提交操作 */
  submit: () => void
  /** 开始流式接收 */
  startStreaming: () => void
  /** 结束流式接收 */
  stopStreaming: () => void
  /** 设置错误状态 */
  setError: (error: string) => void
  /** 重置到 idle */
  reset: () => void
  /** 错误信息 */
  error: string | null
}

export function useComposerState(): ComposerState {
  const [status, setStatus] = useState<ComposerStatus>('idle')
  const [input, setInput] = useState('')
  const [error, setErrorMsg] = useState<string | null>(null)

  /**
   * 派生状态：是否显示居中输入框
   * 规则：只有当状态为 idle 且输入为空时，才居中显示
   */
  const shouldCenterComposer = useMemo(() => {
    return status === 'idle' && input.trim() === ''
  }, [status, input])

  /**
   * 派生状态：是否可以提交
   * 规则：输入非空且不在 submitting/streaming 状态
   */
  const canSubmit = useMemo(() => {
    return input.trim().length > 0 && !['submitting', 'streaming'].includes(status)
  }, [input, status])

  /**
   * 派生状态：是否正在提交
   */
  const isSubmitting = status === 'submitting'

  /**
   * 派生状态：是否正在流式接收
   */
  const isStreaming = status === 'streaming'

  /**
   * 派生状态：是否禁用输入
   * 规则：submitting 和 streaming 时禁用
   */
  const isInputDisabled = useMemo(() => {
    return ['submitting', 'streaming'].includes(status)
  }, [status])

  /**
   * 提交操作
   * 从 idle/typing → submitting
   */
  const submit = useCallback(() => {
    if (!canSubmit) return
    setStatus('submitting')
    setErrorMsg(null)
  }, [canSubmit])

  /**
   * 开始流式接收
   * 从 submitting → streaming
   */
  const startStreaming = useCallback(() => {
    setStatus('streaming')
  }, [])

  /**
   * 结束流式接收
   * 从 streaming → idle，同时清空输入
   */
  const stopStreaming = useCallback(() => {
    setStatus('idle')
    setInput('')
  }, [])

  /**
   * 设置错误状态
   */
  const setError = useCallback((msg: string) => {
    setStatus('error')
    setErrorMsg(msg)
  }, [])

  /**
   * 重置到 idle
   */
  const reset = useCallback(() => {
    setStatus('idle')
    setInput('')
    setErrorMsg(null)
  }, [])

  /**
   * 输入变化时自动切换 idle/typing
   */
  const handleSetInput = useCallback((value: string) => {
    setInput(value)
    if (value.trim().length > 0 && status === 'idle') {
      setStatus('typing')
    }
    if (value.trim().length === 0 && status === 'typing') {
      setStatus('idle')
    }
  }, [status])

  return {
    status,
    input,
    setInput: handleSetInput,
    shouldCenterComposer,
    canSubmit,
    isSubmitting,
    isStreaming,
    isInputDisabled,
    submit,
    startStreaming,
    stopStreaming,
    setError,
    reset,
    error,
  }
}
