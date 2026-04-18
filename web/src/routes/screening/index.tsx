import { createFileRoute } from '@tanstack/react-router'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { useFunds } from '@/hooks/useFunds'

export const Route = createFileRoute('/screening/')({
  component: ScreeningPage,
})

function ScreeningPage() {
  const { data: funds } = useFunds()

  const passed = funds?.filter((f) => f.maDiffPct > 0) ?? []
  const top = [...passed].sort((a, b) => (b.score ?? 0) - (a.score ?? 0)).slice(0, 10)

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">筛选结果</h2>
        <p className="text-sm text-muted-foreground">
          MA 均线多头排列 + 量化打分排名
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">通过 MA 筛选</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{passed.length}</div>
            <p className="text-xs text-muted-foreground">MA20 {'>'} MA60</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">平均分</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {passed.length > 0
                ? (passed.reduce((s, f) => s + (f.score ?? 0), 0) / passed.length).toFixed(1)
                : '-'}
            </div>
            <p className="text-xs text-muted-foreground">综合评分</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">最高分</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {top[0]?.score ?? '-'}
            </div>
            <p className="text-xs text-muted-foreground">{top[0]?.name ?? ''}</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Top 10 排名</CardTitle>
          <CardDescription>按综合评分降序排列</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {top.map((fund, idx) => (
            <div key={fund.id}>
              <div className="flex items-center justify-between py-2">
                <div className="flex items-center gap-3">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
                    {idx + 1}
                  </span>
                  <div>
                    <p className="text-sm font-medium">{fund.name}</p>
                    <p className="text-xs text-muted-foreground font-mono">{fund.code}</p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <Badge variant="outline">{fund.market}</Badge>
                  <span className="text-sm font-mono font-semibold">{fund.score}</span>
                  <span className="text-xs text-green-600 font-mono">+{fund.maDiffPct.toFixed(2)}%</span>
                </div>
              </div>
              {idx < top.length - 1 && <Separator />}
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
