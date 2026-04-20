/**
 * API Hooks barrel export
 *
 * 所有对接后端 REST API 的 TanStack Query hooks 统一从此入口导出。
 * 页面层只 import from '@/hooks/api'，不直接依赖底层 api/client。
 */

export { useFunds } from './useFunds'
export type { FundSummary, PaginatedFundsResponse, UseFundsOptions } from './useFunds'

export { useFundDetail } from './useFundDetail'
export type { FundDetail, Holding, LatestNav } from './useFundDetail'

export { useScreening } from './useScreening'
export type { ScreeningResultItem, ScreeningResponse, UseScreeningOptions } from './useScreening'

export { useChartData } from './useChartData'
export type { ChartPoint, ChartDataResponse, UseChartDataOptions } from './useChartData'

export { useStats } from './useStats'
export type { DashboardStats } from './useStats'

export { useBacktest } from './useBacktest'
export type {
  BacktestRequest,
  BacktestResponse,
  BacktestResult,
  BacktestStats,
  BacktestConfig,
  RebalanceEntry,
} from './useBacktest'
