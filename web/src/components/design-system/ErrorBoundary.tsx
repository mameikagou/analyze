/**
 * ErrorBoundary — React 错误边界
 *
 * 【设计意图】
 * 捕获子组件树中的渲染错误，防止整个应用白屏崩溃。
 * 展示友好的错误恢复界面，提供「重试」和「返回首页」两个出口。
 *
 * 使用方式：包裹在路由 Outlet 或关键业务组件外部。
 *   <ErrorBoundary><MyComponent /></ErrorBoundary>
 *
 * 注意：ErrorBoundary 必须是 class component（React 限制）。
 */

import { Component, type ReactNode } from 'react'
import { AlertTriangle, RotateCcw, Home } from 'lucide-react'
import { Surface } from './Surface'
import { TextButton } from './TextButton'

interface Props {
  children: ReactNode
  /** 自定义兜底 UI，不传则使用默认 */
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error?: Error
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    // 生产环境应接入 Sentry / LogRocket 等监控服务
    console.error('[ErrorBoundary] 捕获到渲染错误:', error)
    console.error('[ErrorBoundary] 组件栈:', errorInfo.componentStack)
  }

  handleReset = () => {
    this.setState({ hasError: false, error: undefined })
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <div className="flex min-h-[60vh] items-center justify-center p-6">
          <Surface
            variant="surface"
            bordered
            rounded="xl"
            className="max-w-md w-full p-8 text-center space-y-5"
          >
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-[var(--accent-error-subtle)]">
              <AlertTriangle className="h-7 w-7 text-[var(--accent-error)]" />
            </div>

            <div className="space-y-2">
              <h2 className="text-lg font-semibold text-[var(--text-primary)]">
                页面出了点问题
              </h2>
              <p className="text-sm text-[var(--text-muted)]">
                我们在渲染这个区域时遇到了意外错误。你可以尝试重新加载，或者返回首页。
              </p>
            </div>

            {this.state.error && process.env.NODE_ENV === 'development' && (
              <pre className="rounded-md bg-[var(--bg-hover)] p-3 text-left text-xs text-[var(--text-secondary)] overflow-auto max-h-40">
                {this.state.error.message}
              </pre>
            )}

            <div className="flex items-center justify-center gap-3">
              <TextButton
                variant="subtle"
                icon={<Home className="h-4 w-4" />}
                onClick={() => {
                  window.location.href = '/'
                }}
              >
                返回首页
              </TextButton>
              <TextButton
                variant="accent"
                icon={<RotateCcw className="h-4 w-4" />}
                onClick={this.handleReset}
              >
                重新加载
              </TextButton>
            </div>
          </Surface>
        </div>
      )
    }

    return this.props.children
  }
}
