import { createFileRoute } from '@tanstack/react-router'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { useFunds } from '@/hooks/useFunds'

export const Route = createFileRoute('/funds/')({
  component: FundsPage,
})

function FundsPage() {
  const { data: funds, isLoading } = useFunds()

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">基金列表</h2>
        <p className="text-sm text-muted-foreground">
          全市场基金基础信息一览
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>基金概览</CardTitle>
          <CardDescription>共 {funds?.length ?? 0} 只基金</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>代码</TableHead>
                  <TableHead>名称</TableHead>
                  <TableHead>市场</TableHead>
                  <TableHead>MA20</TableHead>
                  <TableHead>MA60</TableHead>
                  <TableHead>MA差值%</TableHead>
                  <TableHead>评分</TableHead>
                  <TableHead>申购状态</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {funds?.map((fund) => (
                  <TableRow key={fund.id}>
                    <TableCell className="font-mono font-medium">{fund.code}</TableCell>
                    <TableCell>{fund.name}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{fund.market}</Badge>
                    </TableCell>
                    <TableCell>{fund.maShort.toFixed(2)}</TableCell>
                    <TableCell>{fund.maLong.toFixed(2)}</TableCell>
                    <TableCell>
                      <span className={fund.maDiffPct > 0 ? 'text-green-600' : 'text-red-600'}>
                        {fund.maDiffPct > 0 ? '+' : ''}
                        {fund.maDiffPct.toFixed(2)}%
                      </span>
                    </TableCell>
                    <TableCell>
                      {fund.score !== undefined ? (
                        <Badge
                          variant={fund.score >= 80 ? 'default' : 'secondary'}
                        >
                          {fund.score}
                        </Badge>
                      ) : (
                        '-'
                      )}
                    </TableCell>
                    <TableCell>
                      {fund.purchaseStatus ? (
                        <Badge
                          variant={
                            fund.purchaseStatus === 'normal'
                              ? 'default'
                              : fund.purchaseStatus === 'limited'
                                ? 'secondary'
                                : 'destructive'
                          }
                        >
                          {fund.purchaseStatus === 'normal' && '正常'}
                          {fund.purchaseStatus === 'limited' && '限额'}
                          {fund.purchaseStatus === 'suspended' && '暂停'}
                          {fund.purchaseStatus === 'unknown' && '未知'}
                        </Badge>
                      ) : (
                        '-'
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
