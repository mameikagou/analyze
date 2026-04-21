/**
 * Root Layout — 全局布局壳
 *
 * 【2026-04-21 重构说明】
 * 新增 ErrorBoundary 包裹 Outlet，防止子路由渲染错误导致整站白屏。
 * 新增 ToastProvider + ToastContainer，为全站提供统一的通知浮层。
 * 新增移动端响应式：小屏幕下 sidebar 变为可折叠的抽屉模式。
 */

import { Outlet, createRootRoute } from '@tanstack/react-router'
import { TanStackRouterDevtools } from '@tanstack/react-router-devtools'
import { Link } from '@tanstack/react-router'
import {
  LayoutDashboard,
  ListFilter,
  BarChart3,
  MessageSquare,
  LineChart,
  Sun,
  Moon,
  Menu,
  X,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useState } from 'react'
import { useAppStore } from '@/stores/appStore'
import { useTheme } from '@/hooks/useTheme'
import { ToastProvider } from '@/hooks/useToast'
import { PageTransition } from '@/components/design-system/PageTransition'
import { ErrorBoundary } from '@/components/design-system/ErrorBoundary'
import { ToastContainer } from '@/components/design-system/Toast'

export const Route = createRootRoute({
  component: RootComponent,
})

const navItems = [
  { to: '/', label: '仪表盘', icon: LayoutDashboard },
  { to: '/funds', label: '基金列表', icon: ListFilter },
  { to: '/screening', label: '筛选结果', icon: BarChart3 },
  { to: '/backtest', label: '策略回测', icon: LineChart },
  { to: '/chat', label: 'AI 分析', icon: MessageSquare },
]

function RootComponent() {
  const sidebarOpen = useAppStore((s) => s.sidebarOpen)
  const { theme, toggleTheme } = useTheme()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  return (
    <ToastProvider>
      <div className="flex h-screen bg-background text-foreground">
        {/* Mobile Overlay */}
        {mobileMenuOpen && (
          <div
            className="fixed inset-0 z-40 bg-[var(--overlay-backdrop)] lg:hidden"
            onClick={() => setMobileMenuOpen(false)}
          />
        )}

        {/* Sidebar — Desktop: collapsible, Mobile: drawer */}
        <aside
          className={cn(
            'flex flex-col border-r border-border bg-card transition-all duration-300 z-50',
            'fixed inset-y-0 left-0 lg:static',
            sidebarOpen ? 'w-64' : 'w-16',
            mobileMenuOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0',
            mobileMenuOpen && 'w-64'
          )}
        >
          <div className="flex h-14 items-center border-b border-border px-4">
            {(sidebarOpen || mobileMenuOpen) && (
              <span className="text-lg font-semibold tracking-tight">
                Fund Screener
              </span>
            )}
            {/* Mobile close button */}
            <button
              onClick={() => setMobileMenuOpen(false)}
              className="ml-auto rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors duration-200 ease-out lg:hidden"
              aria-label="关闭菜单"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <nav className="flex-1 space-y-1 p-2">
            {navItems.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                onClick={() => setMobileMenuOpen(false)}
                className={cn(
                  'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors duration-200 ease-out',
                  'hover:bg-accent hover:text-accent-foreground',
                  '[&.active]:bg-primary/10 [&.active]:text-primary'
                )}
                activeProps={{ className: 'active' }}
              >
                <item.icon className="h-4 w-4 shrink-0" />
                {(sidebarOpen || mobileMenuOpen) && <span>{item.label}</span>}
              </Link>
            ))}
          </nav>
        </aside>

        {/* Main content */}
        <main className="flex flex-1 flex-col overflow-hidden">
          <header className="flex h-14 items-center justify-between border-b border-border bg-card px-4 lg:px-6">
            <div className="flex items-center gap-3">
              {/* Mobile hamburger */}
              <button
                onClick={() => setMobileMenuOpen(true)}
                className="rounded-md p-2 text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors duration-200 ease-out lg:hidden"
                aria-label="打开菜单"
              >
                <Menu className="h-4 w-4" />
              </button>
              <h1 className="text-sm font-medium text-muted-foreground">
                Fund Screener — 全市场基金趋势筛选器
              </h1>
            </div>
            <button
              onClick={toggleTheme}
              className="rounded-md p-2 text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors duration-200 ease-out"
              aria-label={theme === 'dark' ? '切换到浅色模式' : '切换到深色模式'}
            >
              {theme === 'dark' ? (
                <Sun className="h-4 w-4" />
              ) : (
                <Moon className="h-4 w-4" />
              )}
            </button>
          </header>
          <div className="flex-1 overflow-auto p-4 lg:p-6">
            <PageTransition>
              <ErrorBoundary>
                <Outlet />
              </ErrorBoundary>
            </PageTransition>
          </div>
        </main>

        <ToastContainer />
        <TanStackRouterDevtools position="bottom-right" />
      </div>
    </ToastProvider>
  )
}
