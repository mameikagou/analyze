import { useQuery } from '@tanstack/react-query'
import { apiGet } from '@/api/client'

/* ── Types ─────────────────────────────────────────────── */

export interface DashboardStats {
  totalFunds: number
  fundsByMarket: Record<string, number>
  totalNavRecords: number
  navDateRange: [string | null, string | null]
  latestScreeningDate: string | null
  latestScreeningCount: number
  latestScreeningAvgMaDiff: number | null
  dbSizeMb: number
}

interface RawStatsResponse {
  success: boolean
  data: {
    total_funds: number
    funds_by_market: Record<string, number>
    total_nav_records: number
    nav_date_range: [string | null, string | null]
    latest_screening_date: string | null
    latest_screening_count: number
    latest_screening_avg_ma_diff: number | null
    db_size_mb: number
  } | null
  error?: string
}

/* ── Mapper ────────────────────────────────────────────── */

function mapStats(raw: RawStatsResponse['data']): DashboardStats | null {
  if (!raw) return null
  return {
    totalFunds: raw.total_funds,
    fundsByMarket: raw.funds_by_market,
    totalNavRecords: raw.total_nav_records,
    navDateRange: raw.nav_date_range,
    latestScreeningDate: raw.latest_screening_date,
    latestScreeningCount: raw.latest_screening_count,
    latestScreeningAvgMaDiff: raw.latest_screening_avg_ma_diff,
    dbSizeMb: raw.db_size_mb,
  }
}

/* ── Hook ──────────────────────────────────────────────── */

async function fetchStats(): Promise<DashboardStats | null> {
  const res = await apiGet<RawStatsResponse>('/api/stats')
  if (!res.success) return null
  return mapStats(res.data)
}

export function useStats() {
  return useQuery({
    queryKey: ['stats'],
    queryFn: fetchStats,
    staleTime: 1000 * 60 * 5,
  })
}
