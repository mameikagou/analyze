import { useQuery } from '@tanstack/react-query'

/**
 * 基金列表数据查询 Hook（TanStack Query）
 *
 * 目前用 mock 数据占位，后续对接后端 API 或本地 SQLite。
 */
export interface Fund {
  id: string
  code: string
  name: string
  market: 'CN' | 'US' | 'HK'
  maShort: number
  maLong: number
  maDiffPct: number
  score?: number
  purchaseStatus?: 'normal' | 'limited' | 'suspended' | 'unknown'
  purchaseLimit?: number
}

const MOCK_FUNDS: Fund[] = [
  {
    id: '1',
    code: 'SPY',
    name: 'SPDR S&P 500 ETF',
    market: 'US',
    maShort: 580.2,
    maLong: 565.8,
    maDiffPct: 2.54,
    score: 85,
  },
  {
    id: '2',
    code: 'QQQ',
    name: 'Invesco QQQ Trust',
    market: 'US',
    maShort: 495.1,
    maLong: 480.3,
    maDiffPct: 3.08,
    score: 92,
  },
  {
    id: '3',
    code: '000001',
    name: '华夏成长混合',
    market: 'CN',
    maShort: 1.52,
    maLong: 1.48,
    maDiffPct: 2.7,
    score: 78,
    purchaseStatus: 'normal',
    purchaseLimit: 100000000,
  },
  {
    id: '4',
    code: '02800',
    name: '盈富基金',
    market: 'HK',
    maShort: 18.5,
    maLong: 18.2,
    maDiffPct: 1.65,
    score: 70,
  },
]

async function fetchFunds(): Promise<Fund[]> {
  // TODO: 对接后端 API / 本地 SQLite
  return new Promise((resolve) => {
    setTimeout(() => resolve(MOCK_FUNDS), 600)
  })
}

export function useFunds() {
  return useQuery({
    queryKey: ['funds'],
    queryFn: fetchFunds,
  })
}
