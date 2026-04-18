import { createFileRoute } from '@tanstack/react-router'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { TrendingUp, Database, Filter, Activity } from 'lucide-react'
import { LightweightChart } from '@/components/chart/LightweightChart'

export const Route = createFileRoute('/')({
  component: DashboardPage,
})

const mockChartData = Array.from({ length: 30 }, (_, i) => {
  const date = new Date()
  date.setDate(date.getDate() - (29 - i))
  return {
    time: date.toISOString().split('T')[0],
    value: 100 + Math.sin(i * 0.3) * 10 + i * 0.5,
  }
})

const stats = [
  { label: '总基金数', value: '1,284', icon: Database, delta: '+12' },
  { label: '今日通过 MA', value: '86', icon: Filter, delta: '+5' },
  { label: '平均动量分', value: '72.4', icon: TrendingUp, delta: '+1.2' },
  { label: '数据湖记录', value: '45.2K', icon: Activity, delta: '+2.1K' },
]

function DashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">仪表盘</h2>
        <p className="text-sm text-muted-foreground">
          全市场基金趋势概览
        </p>
      </div>

      {/* Stats cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <Card key={stat.label}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">{stat.label}</CardTitle>
              <stat.icon className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stat.value}</div>
              <Badge variant="secondary" className="mt-1">
                {stat.delta}
              </Badge>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Chart */}
      <Card>
        <CardHeader>
          <CardTitle>净值走势（示例）</CardTitle>
          <CardDescription>模拟数据，后续对接真实净值时序</CardDescription>
        </CardHeader>
        <CardContent>
          <LightweightChart data={mockChartData} type="line" height={350} />
        </CardContent>
      </Card>
    </div>
  )
}
