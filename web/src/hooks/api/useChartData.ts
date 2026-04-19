import { useQuery } from '@tanstack/react-query'
import { apiGet } from '@/api/client'

/* ── Types ─────────────────────────────────────────────── */

export interface ChartPoint {
  time: string // YYYY-MM-DD
  value: number
  adjValue: number | null
}

export interface ChartDataResponse {
  success: boolean
  data: {
    code: string
    points: number
    history: ChartPoint[]
  }
  error?: string
}

export interface UseChartDataOptions {
  days?: number
}

/* ── Hook ──────────────────────────────────────────────── */

function fetchChartData(
  code: string,
  options: UseChartDataOptions,
): Promise<ChartDataResponse> {
  return apiGet<ChartDataResponse>(`/api/chart/${encodeURIComponent(code)}`, {
    days: options.days ?? 90,
  })
}

export function useChartData(code: string, options: UseChartDataOptions = {}) {
  return useQuery({
    queryKey: ['chart', code, options.days],
    queryFn: () => fetchChartData(code, options),
    enabled: !!code,
    staleTime: 1000 * 60 * 5,
  })
}
