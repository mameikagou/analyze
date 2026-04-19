/**
 * ChartContainer — 基金净值走势图（带 MA 均线叠加）
 *
 * 职责：展示单只基金的净值历史走势，叠加 MA20（短期）和 MA60（长期）均线。
 * 支持 Market-aware 涨跌色切换（CN 市场红涨绿跌，其他绿涨红跌）。
 *
 * 实现说明：
 *   - 直接使用 TradingView Lightweight Charts API（不依赖 LightweightChart 组件），
 *     因为需要叠加多个 series（净值线 + MA20 + MA60）。
 *   - MA 均线在前端实时计算（滑动窗口平均），不依赖后端预计算。
 *   - 卸载时必须 chart.remove() 释放资源，防止内存泄漏。
 *
 * 关注点分离：
 *   - 接收 ChartPoint[] 数据，不直接调用 useChartData
 *   - market 属性用于设置 data-market，驱动 CSS 变量切换涨跌色
 *   - 样式全部从 CSS 变量读取（tokens.chart.css）
 */

import { useRef, useEffect } from 'react'
import {
  createChart,
  LineSeries,
  type IChartApi,
  type ISeriesApi,
  type LineData,
  type Time,
  LineStyle,
  CrosshairMode,
} from 'lightweight-charts'
import type { ChartPoint } from '@/hooks/api'

interface ChartContainerProps {
  /** 净值历史数据 */
  data: ChartPoint[]
  /** 市场代码，用于涨跌色切换 */
  market?: string
  /** 图表高度 */
  height?: number
}

/**
 * 计算滑动窗口均线。
 * 前 (period-1) 个点不足窗口大小，跳过（TV Charts 会自动留空）。
 */
function calcMA(data: ChartPoint[], period: number): LineData<Time>[] {
  const result: LineData<Time>[] = []
  for (let i = period - 1; i < data.length; i++) {
    let sum = 0
    let validCount = 0
    for (let j = 0; j < period; j++) {
      const v = data[i - j].value
      if (v != null) {
        sum += v
        validCount++
      }
    }
    if (validCount > 0) {
      result.push({ time: data[i].time, value: sum / validCount })
    }
  }
  return result
}

export function ChartContainer({
  data,
  market,
  height = 400,
}: ChartContainerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const navSeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const ma20SeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const ma60SeriesRef = useRef<ISeriesApi<'Line'> | null>(null)

  useEffect(() => {
    const container = containerRef.current
    if (!container || data.length === 0) return

    /* ── 从 CSS 变量读取颜色 ─────────────────────────────── */
    const style = getComputedStyle(container)
    const readColor = (name: string, fallback: string): string =>
      style.getPropertyValue(name).trim() || fallback

    const chartUp = readColor('--chart-up', '#22c55e')
    const chartDown = readColor('--chart-down', '#ef4444')
    const chartGrid = readColor('--chart-grid', '#e7e5e4')
    const chartCrosshair = readColor('--chart-crosshair', '#78716c')
    const maShortColor = readColor('--chart-ma-short', '#f97316')
    const maMediumColor = readColor('--chart-ma-medium', '#3b82f6')

    /* ── 创建图表 ─────────────────────────────────────────── */
    const chart = createChart(container, {
      height,
      layout: {
        background: { color: 'transparent' },
        textColor: 'currentColor',
      },
      grid: {
        vertLines: { color: chartGrid + '4d' },
        horzLines: { color: chartGrid + '4d' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: {
          color: chartCrosshair,
          labelBackgroundColor: chartCrosshair,
        },
        horzLine: {
          color: chartCrosshair,
          labelBackgroundColor: chartCrosshair,
        },
      },
      rightPriceScale: { borderColor: chartGrid },
      timeScale: {
        borderColor: chartGrid,
        timeVisible: false,
      },
    })
    chartRef.current = chart

    /* ── 净值线（主系列）──────────────────────────────────── */
    const navSeries = chart.addSeries(LineSeries, {
      color: market?.toUpperCase() === 'CN' ? chartUp : chartUp,
      lineWidth: 2,
      lineStyle: LineStyle.Solid,
      title: '净值',
    })
    const navData: LineData<Time>[] = data.map((d) => ({
      time: d.time,
      value: d.value,
    }))
    navSeries.setData(navData)
    navSeriesRef.current = navSeries

    /* ── MA20 均线（短期）─────────────────────────────────── */
    const ma20Data = calcMA(data, 20)
    if (ma20Data.length > 0) {
      const ma20Series = chart.addSeries(LineSeries, {
        color: maShortColor,
        lineWidth: 1.5,
        lineStyle: LineStyle.Solid,
        title: 'MA20',
      })
      ma20Series.setData(ma20Data)
      ma20SeriesRef.current = ma20Series
    }

    /* ── MA60 均线（长期）─────────────────────────────────── */
    const ma60Data = calcMA(data, 60)
    if (ma60Data.length > 0) {
      const ma60Series = chart.addSeries(LineSeries, {
        color: maMediumColor,
        lineWidth: 1.5,
        lineStyle: LineStyle.Dashed,
        title: 'MA60',
      })
      ma60Series.setData(ma60Data)
      ma60SeriesRef.current = ma60Series
    }

    /* ── 自适应时间范围 ───────────────────────────────────── */
    chart.timeScale().fitContent()

    /* ── 响应式宽度 ───────────────────────────────────────── */
    const handleResize = () => {
      chart.applyOptions({ width: container.clientWidth })
    }
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.remove()
      chartRef.current = null
      navSeriesRef.current = null
      ma20SeriesRef.current = null
      ma60SeriesRef.current = null
    }
  }, [data, market, height])

  if (data.length === 0) {
    return (
      <div
        className="flex items-center justify-center rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)]"
        style={{ height }}
      >
        <p className="text-sm text-[var(--text-muted)]">暂无图表数据</p>
      </div>
    )
  }

  return (
    <div
      ref={containerRef}
      className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)]"
      data-market={market?.toLowerCase() === 'cn' ? 'cn' : undefined}
      style={{ width: '100%' }}
    />
  )
}
