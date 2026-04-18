import { Outlet, createRootRoute } from '@tanstack/react-router'
import { TanStackRouterDevtools } from '@tanstack/react-router-devtools'
import { Link } from '@tanstack/react-router'
import { LayoutDashboard, ListFilter, BarChart3, MessageSquare } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAppStore } from '@/stores/appStore'

export const Route = createRootRoute({
  component: RootComponent,
})

const navItems = [
  { to: '/', label: '仪表盘', icon: LayoutDashboard },
  { to: '/funds', label: '基金列表', icon: ListFilter },
  { to: '/screening', label: '筛选结果', icon: BarChart3 },
  { to: '/chat', label: 'AI 分析', icon: MessageSquare },
]

function RootComponent() {
  const sidebarOpen = useAppStore((s) => s.sidebarOpen)

  return (
    <div className="flex h-screen bg-background text-foreground">
      {/* Sidebar */}
      <aside
        className={cn(
          'flex flex-col border-r border-border bg-card transition-all duration-300',
          sidebarOpen ? 'w-64' : 'w-16'
        )}
      >
        <div className="flex h-14 items-center border-b border-border px-4">
          {sidebarOpen && (
            <span className="text-lg font-semibold tracking-tight">
              Fund Screener
            </span>
          )}
        </div>

        <nav className="flex-1 space-y-1 p-2">
          {navItems.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className={cn(
                'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                'hover:bg-accent hover:text-accent-foreground',
                '[&.active]:bg-primary/10 [&.active]:text-primary'
              )}
              activeProps={{ className: 'active' }}
            >
              <item.icon className="h-4 w-4 shrink-0" />
              {sidebarOpen && <span>{item.label}</span>}
            </Link>
          ))}
        </nav>
      </aside>

      {/* Main content */}
      <main className="flex flex-1 flex-col overflow-hidden">
        <header className="flex h-14 items-center border-b border-border bg-card px-6">
          <h1 className="text-sm font-medium text-muted-foreground">
            Fund Screener — 全市场基金趋势筛选器
          </h1>
        </header>
        <div className="flex-1 overflow-auto p-6">
          <Outlet />
        </div>
      </main>

      <TanStackRouterDevtools position="bottom-right" />
    </div>
  )
}
