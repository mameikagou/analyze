import { useQuery } from '@tanstack/react-query'
import { apiGet } from '@/api/client'

/* ── Types ─────────────────────────────────────────────── */

export interface ScreeningResultItem {
  code: string
  name: string
  market: string
  nav: number
  maShort: number
  maLong: number
  maDiffPct: number
  dailyChangePct: number | null
  score: number | null
  purchaseStatus: string | null
  purchaseLimit: number | null
  screeningDate: string
}

export interface ScreeningResponse {
  success: boolean
  data: {
    screening_date: string
    count: number
    results: ScreeningResultItem[]
  }
  error?: string
}

export interface UseScreeningOptions {
  date?: string
  market?: 'CN' | 'US' | 'HK' | ''
  minMaDiff?: number
  limit?: number
}

/* ── Hook ──────────────────────────────────────────────── */

function fetchScreening(options: UseScreeningOptions): Promise<ScreeningResponse> {
  return apiGet<ScreeningResponse>('/api/screening', {
    date: options.date || undefined,
    market: options.market || undefined,
    min_ma_diff: options.minMaDiff,
    limit: options.limit ?? 50,
  })
}

export function useScreening(options: UseScreeningOptions = {}) {
  return useQuery({
    queryKey: ['screening', options],
    queryFn: () => fetchScreening(options),
    staleTime: 1000 * 60 * 5,
  })
}
