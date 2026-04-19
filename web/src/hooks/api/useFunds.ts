import { useQuery } from '@tanstack/react-query'
import { apiGet } from '@/api/client'

/* ── Types ─────────────────────────────────────────────── */

export interface FundSummary {
  code: string
  name: string
  market: string
}

export interface PaginatedFundsResponse {
  success: boolean
  data: FundSummary[]
  total: number
  page: number
  page_size: number
  error?: string
}

export interface UseFundsOptions {
  page?: number
  pageSize?: number
  market?: 'CN' | 'US' | 'HK' | ''
  sortBy?: 'code' | 'name' | 'market' | 'created_at'
  sortOrder?: 'asc' | 'desc'
}

/* ── Hook ──────────────────────────────────────────────── */

function fetchFunds(options: UseFundsOptions): Promise<PaginatedFundsResponse> {
  return apiGet<PaginatedFundsResponse>('/api/funds', {
    page: options.page ?? 1,
    page_size: options.pageSize ?? 20,
    market: options.market || undefined,
    sort_by: options.sortBy ?? 'code',
    sort_order: options.sortOrder ?? 'asc',
  })
}

export function useFunds(options: UseFundsOptions = {}) {
  return useQuery({
    queryKey: ['funds', options],
    queryFn: () => fetchFunds(options),
    staleTime: 1000 * 60 * 5,
  })
}
