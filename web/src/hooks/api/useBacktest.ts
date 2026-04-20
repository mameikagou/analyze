import { useMutation } from '@tanstack/react-query'
import { apiPost } from '@/api/client'

/* ── Types ─────────────────────────────────────────────── */

export interface BacktestConfig {
  topN: number
  rebalanceFreq: string
  weighting: string
  feeRate: number
  initCash: number
  signalFilter: string | null
}

export interface BacktestStats {
  totalReturn: number
  annualReturn: number
  sharpeRatio: number
  maxDrawdown: number
  winRate: number
  avgWin: number
  avgLoss: number
  profitFactor: number
  totalTrades: number
}

export interface RebalanceEntry {
  date: string
  holdings: Record<string, number>
}

export interface BacktestResult {
  factorName: string
  config: BacktestConfig
  stats: BacktestStats
  equityCurve: Record<string, number>
  drawdown: Record<string, number>
  rebalanceHistory: RebalanceEntry[]
}

export interface BacktestResponse {
  success: boolean
  data: BacktestResult | null
  error?: string
}

export interface BacktestRequest {
  scoreFactor: string
  scoreWeights?: Record<string, number>
  signalFilter?: string | null
  topN: number
  rebalanceFreq: string
  weighting: string
  feeRate: number
  startDate: string
  endDate: string
  market: string
}

/* ── Hook ──────────────────────────────────────────────── */

async function runBacktest(request: BacktestRequest): Promise<BacktestResponse> {
  // Map camelCase frontend types to snake_case API body
  const body = {
    score_factor: request.scoreFactor,
    score_weights: request.scoreWeights,
    signal_filter: request.signalFilter,
    top_n: request.topN,
    rebalance_freq: request.rebalanceFreq,
    weighting: request.weighting,
    fee_rate: request.feeRate,
    start_date: request.startDate,
    end_date: request.endDate,
    market: request.market,
  }
  return apiPost<BacktestResponse>('/api/backtest/run', body)
}

export function useBacktest() {
  return useMutation({
    mutationFn: runBacktest,
  })
}
