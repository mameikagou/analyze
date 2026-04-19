/**
 * FundTable — 基金列表表格
 *
 * 职责：以表格形式展示基金基础信息列表，支持行点击跳转。
 * 使用 shadcn/ui Table 组件作为底层，上层包裹业务样式。
 *
 * 关注点分离：
 *   - 数据从父组件传入（funds: FundSummary[]）
 *   - 排序/分页逻辑在页面层或 hook 层处理，表格只展示
 *   - 行点击回调透出到父组件（通常用于路由跳转）
 */

import { motion } from 'framer-motion'
import { ExternalLink } from 'lucide-react'
import {
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
  TableCell,
} from '@/components/ui/table'
import { MarketBadge } from './MarketBadge'
import { stagger, presence, transition } from '@/styles/tokens.animation'
import type { FundSummary } from '@/hooks/api'

interface FundTableProps {
  funds: FundSummary[]
  onRowClick?: (code: string) => void
}

export function FundTable({ funds, onRowClick }: FundTableProps) {
  if (funds.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)]">
        <p className="text-sm text-[var(--text-muted)]">暂无数据</p>
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead className="w-[120px] text-[var(--text-muted)]">基金代码</TableHead>
            <TableHead className="text-[var(--text-muted)]">基金名称</TableHead>
            <TableHead className="w-[80px] text-[var(--text-muted)]">市场</TableHead>
            <TableHead className="w-[60px] text-right text-[var(--text-muted)]">操作</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {funds.map((fund, index) => (
            <TableRow
              key={fund.code}
              className="cursor-pointer group"
              onClick={() => onRowClick?.(fund.code)}
            >
              <TableCell className="font-mono text-sm text-[var(--text-primary)]">
                {fund.code}
              </TableCell>
              <TableCell className="text-sm text-[var(--text-secondary)] max-w-[300px] truncate">
                {fund.name}
              </TableCell>
              <TableCell>
                <MarketBadge market={fund.market} />
              </TableCell>
              <TableCell className="text-right">
                <ExternalLink className="inline-block h-3.5 w-3.5 text-[var(--text-muted)] opacity-0 group-hover:opacity-100 transition-opacity" />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
