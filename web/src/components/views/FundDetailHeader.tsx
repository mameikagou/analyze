/**
 * FundDetailHeader — 基金详情页头部
 *
 * 职责：展示单只基金的核心基本信息（名称、代码、市场、经理、规模等）。
 * 用于 /funds/$code 页面的顶部区域。
 *
 * 关注点分离：
 *   - 接收 FundDetail 数据，内部做格式化展示
 *   - 不处理数据获取（由页面层的 useFundDetail 负责）
 */

import { Calendar, User, Scale, BarChart3 } from 'lucide-react'
import { MarketBadge } from './MarketBadge'
import { ScoreBadge } from './ScoreBadge'
import type { FundDetail as FundDetailType } from '@/hooks/api'

interface FundDetailHeaderProps {
  fund: FundDetailType
  /** 可选：量化评分（来自筛选结果，详情 API 不返回评分） */
  score?: number | null
}

export function FundDetailHeader({ fund, score }: FundDetailHeaderProps) {
  const infoItems = [
    {
      icon: User,
      label: '基金经理',
      value: fund.managerName ?? '—',
    },
    {
      icon: Scale,
      label: '基金规模',
      value: fund.fundScale !== null
        ? `${(fund.fundScale / 100000000).toFixed(2)}亿`
        : '—',
    },
    {
      icon: Calendar,
      label: '成立日期',
      value: fund.establishDate ?? '—',
    },
    {
      icon: BarChart3,
      label: '跟踪基准',
      value: fund.trackBenchmark ?? '—',
    },
  ]

  return (
    <div className="space-y-4">
      {/* 标题行 */}
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-lg font-semibold text-[var(--text-primary)]">
              {fund.code}
            </span>
            <MarketBadge market={fund.market} />
            {score !== undefined && score !== null && <ScoreBadge score={score} />}
          </div>
          <h1 className="text-xl font-bold text-[var(--text-primary)] truncate">
            {fund.name}
          </h1>
        </div>
      </div>

      {/* 信息网格 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {infoItems.map(({ icon: Icon, label, value }) => (
          <div
            key={label}
            className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-3"
          >
            <div className="flex items-center gap-1.5 mb-1">
              <Icon className="h-3.5 w-3.5 text-[var(--text-muted)]" />
              <span className="text-xs text-[var(--text-muted)]">{label}</span>
            </div>
            <span className="text-sm font-medium text-[var(--text-secondary)]">
              {value}
            </span>
          </div>
        ))}
      </div>

      {/* 最新净值 */}
      {fund.latestNav && (
        <div className="flex items-center gap-4 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-3">
          <div>
            <span className="text-xs text-[var(--text-muted)]">最新净值</span>
            <div className="text-lg font-bold tabular-nums text-[var(--text-primary)]">
              {fund.latestNav.nav?.toFixed(4) ?? '—'}
            </div>
          </div>
          <div className="w-px h-8 bg-[var(--border-subtle)]" />
          <div>
            <span className="text-xs text-[var(--text-muted)]">日期</span>
            <div className="text-sm font-medium tabular-nums text-[var(--text-secondary)]">
              {fund.latestNav.date ?? '—'}
            </div>
          </div>
          {fund.latestNav.adjNav !== null && fund.latestNav.adjNav !== undefined && (
            <>
              <div className="w-px h-8 bg-[var(--border-subtle)]" />
              <div>
                <span className="text-xs text-[var(--text-muted)]">复权净值</span>
                <div className="text-sm font-medium tabular-nums text-[var(--text-secondary)]">
                  {fund.latestNav.adjNav.toFixed(4)}
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
