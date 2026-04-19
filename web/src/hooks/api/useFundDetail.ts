import { useQuery } from '@tanstack/react-query'
import { apiGet } from '@/api/client'

/* ── Types ─────────────────────────────────────────────── */

export interface Holding {
  stockCode: string
  stockName: string
  weightPct: number | null
}

export interface LatestNav {
  date: string
  nav: number | null
  adjNav: number | null
}

export interface FundDetail {
  code: string
  name: string
  market: string
  establishDate: string | null
  managerName: string | null
  fundScale: number | null
  trackBenchmark: string | null
  holdings: Holding[]
  latestNav: LatestNav | null
}

interface RawHolding {
  stock_code: string
  stock_name: string
  weight_pct: number
}

interface RawLatestNav {
  date: string
  nav: number
  adj_nav: number | null
}

interface RawFundDetailResponse {
  success: boolean
  data: {
    code: string
    name: string
    market: string
    establish_date: string | null
    manager_name: string | null
    fund_scale: number | null
    track_benchmark: string | null
    holdings: RawHolding[]
    latest_nav: RawLatestNav | null
  } | null
  error?: string
}

/* ── Mapper ────────────────────────────────────────────── */

function mapHolding(raw: RawHolding): Holding {
  return {
    stockCode: raw.stock_code,
    stockName: raw.stock_name,
    weightPct: raw.weight_pct,
  }
}

function mapLatestNav(raw: RawLatestNav | null): LatestNav | null {
  if (!raw) return null
  return {
    date: raw.date,
    nav: raw.nav,
    adjNav: raw.adj_nav,
  }
}

function mapFundDetail(raw: RawFundDetailResponse['data']): FundDetail | null {
  if (!raw) return null
  return {
    code: raw.code,
    name: raw.name,
    market: raw.market,
    establishDate: raw.establish_date,
    managerName: raw.manager_name,
    fundScale: raw.fund_scale,
    trackBenchmark: raw.track_benchmark,
    holdings: (raw.holdings ?? []).map(mapHolding),
    latestNav: mapLatestNav(raw.latest_nav),
  }
}

/* ── Hook ──────────────────────────────────────────────── */

async function fetchFundDetail(code: string): Promise<FundDetail | null> {
  const res = await apiGet<RawFundDetailResponse>(`/api/funds/${encodeURIComponent(code)}`)
  if (!res.success) return null
  return mapFundDetail(res.data)
}

export function useFundDetail(code: string) {
  return useQuery({
    queryKey: ['fund', code],
    queryFn: () => fetchFundDetail(code),
    enabled: !!code,
    staleTime: 1000 * 60 * 5,
  })
}
