/**
 * FundTable — 基金列表表格
 *
 * 【2026-04-21 重构说明】
 * 将裸写的 bg-[var(--bg-surface)]/border-[var(--border-subtle)] 替换为
 * design-system/Surface 组件，统一容器层级管理。
 * 空状态容器同样使用 Surface，确保视觉一致性。
 *
 * 副作用：
 *   - 引入 Surface 组件依赖（已存在）
 *   - 无行为变更，纯视觉层统一
 */

import { Surface } from '@/components/design-system/Surface'
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
import type { FundSummary } from '@/hooks/api'

interface FundTableProps {
  funds: FundSummary[]
  onRowClick?: (code: string) => void
  /**
   * 为 true 时不渲染 Surface 外壳，用于被 ArchiveTable 等外层容器包裹的场景。
   * @default false
   */
  unstyled?: boolean
}

function TableContent({ funds, onRowClick }: FundTableProps) {
  if (funds.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center">
        <p className="text-sm text-[var(--text-muted)]">暂无数据</p>
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
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
          {funds.map((fund) => (
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

export function FundTable({ funds, onRowClick, unstyled }: FundTableProps) {
  if (unstyled) {
    return <TableContent funds={funds} onRowClick={onRowClick} />
  }

  return (
    <Surface variant="surface" bordered rounded="lg" className="overflow-hidden">
      <TableContent funds={funds} onRowClick={onRowClick} />
    </Surface>
  )
}
