/**
 * useStreamingMessage — 流式消息渲染 Hook
 *
 * 封装流式追加、节流渲染、中断恢复。
 * Claude 的流式消息有几个特征：
 * - 文字逐字/逐词出现，不是整段闪现
 * - 底部有脉冲光标（streaming 时）
 * - 光标在 streaming 结束时淡出
 * - 支持中断（用户可以随时停止生成）
 *
 * @example
 * ```tsx
 * const streaming = useStreamingMessage()
 *
 * // 开始接收流
 * useEffect(() => {
 *   const eventSource = new EventSource('/api/stream')
 *   eventSource.onmessage = (e) => {
 *     streaming.append(e.data)
 *   }
 *   eventSource.onopen = () => streaming.start()
 *   eventSource.onerror = () => streaming.stop()
 *   return () => {
 *     eventSource.close()
 *     streaming.stop()
 *   }
 * }, [])
 *
 * // 渲染
 * <div>
 *   {streaming.displayText}
 *   {streaming.isStreaming && <span className="animate-pulse">▌</span>}
 * </div>
 * ```
 */
import { useState, useCallback, useRef, useEffect } from 'react'

export interface StreamingMessageState {
  /** 当前已渲染的文字 */
  displayText: string
  /** 原始完整文字（包含未渲染的部分） */
  fullText: string
  /** 是否正在流式接收 */
  isStreaming: boolean
  /** 追加内容 */
  append: (chunk: string) => void
  /** 开始流式接收 */
  start: () => void
  /** 停止流式接收 */
  stop: () => void
  /** 中断（清空） */
  abort: () => void
  /** 重置 */
  reset: () => void
}

/**
 * 节流渲染：每隔一定间隔才更新显示文本，避免每收到一个 chunk 就重渲染。
 */
const THROTTLE_MS = 30

export function useStreamingMessage(): StreamingMessageState {
  const [displayText, setDisplayText] = useState('')
  const [fullText, setFullText] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)

  const bufferRef = useRef('')
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  /**
   * 将 buffer 中的内容 flush 到 display
   */
  const flush = useCallback(() => {
    if (bufferRef.current) {
      setDisplayText((prev) => prev + bufferRef.current)
      bufferRef.current = ''
    }
  }, [])

  /**
   * 开始流式接收
   */
  const start = useCallback(() => {
    setIsStreaming(true)
  }, [])

  /**
   * 追加内容到 buffer
   */
  const append = useCallback(
    (chunk: string) => {
      bufferRef.current += chunk
      setFullText((prev) => prev + chunk)

      // 节流：如果定时器不存在，创建一个
      if (!timerRef.current) {
        timerRef.current = setTimeout(() => {
          flush()
          timerRef.current = null
        }, THROTTLE_MS)
      }
    },
    [flush]
  )

  /**
   * 停止流式接收，flush 剩余内容
   */
  const stop = useCallback(() => {
    flush()
    setIsStreaming(false)
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }, [flush])

  /**
   * 中断：立即停止，清空所有内容
   */
  const abort = useCallback(() => {
    setIsStreaming(false)
    setDisplayText('')
    setFullText('')
    bufferRef.current = ''
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }, [])

  /**
   * 重置
   */
  const reset = useCallback(() => {
    setIsStreaming(false)
    setDisplayText('')
    setFullText('')
    bufferRef.current = ''
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }, [])

  // 清理定时器
  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current)
      }
    }
  }, [])

  return {
    displayText,
    fullText,
    isStreaming,
    append,
    start,
    stop,
    abort,
    reset,
  }
}
