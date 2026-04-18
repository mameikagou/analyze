import { useRef, useEffect } from 'react'
import {
  createChart,
  LineSeries,
  CandlestickSeries,
  type IChartApi,
  type ISeriesApi,
  type LineData,
  type CandlestickData,
  type Time,
  LineStyle,
  CrosshairMode,
} from 'lightweight-charts'

export type ChartType = 'line' | 'candlestick'

export interface ChartDataPoint {
  time: string // 'YYYY-MM-DD'
  value: number
  open?: number
  high?: number
  low?: number
  close?: number
}

interface LightweightChartProps {
  data: ChartDataPoint[]
  type?: ChartType
  height?: number
  className?: string
}

/**
 * TradingView Lightweight Charts 封装组件
 *
 * 注意：组件卸载时必须调用 chart.remove() 释放 canvas 和事件监听器，
 * 否则会造成内存泄漏（TV 图表在 DOM 之外保留了大量状态）。
 */
export function LightweightChart({
  data,
  type = 'line',
  height = 400,
  className,
}: LightweightChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Line'> | ISeriesApi<'Candlestick'> | null>(null)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const chart = createChart(container, {
      height,
      layout: {
        background: { color: 'transparent' },
        textColor: 'currentColor',
      },
      grid: {
        vertLines: { color: 'hsl(var(--border) / 0.3)' },
        horzLines: { color: 'hsl(var(--border) / 0.3)' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
      },
      rightPriceScale: {
        borderColor: 'hsl(var(--border))',
      },
      timeScale: {
        borderColor: 'hsl(var(--border))',
        timeVisible: false,
      },
    })

    chartRef.current = chart

    if (type === 'candlestick') {
      const candleSeries = chart.addSeries(CandlestickSeries, {
        upColor: '#22c55e',
        downColor: '#ef4444',
        borderUpColor: '#22c55e',
        borderDownColor: '#ef4444',
        wickUpColor: '#22c55e',
        wickDownColor: '#ef4444',
      })
      const cd = data.map(
        (d): CandlestickData<Time> => ({
          time: d.time,
          open: d.open ?? d.value,
          high: d.high ?? d.value,
          low: d.low ?? d.value,
          close: d.close ?? d.value,
        })
      )
      candleSeries.setData(cd)
      seriesRef.current = candleSeries
    } else {
      const lineSeries = chart.addSeries(LineSeries, {
        color: 'hsl(var(--primary))',
        lineWidth: 2,
        lineStyle: LineStyle.Solid,
      })
      const ld = data.map(
        (d): LineData<Time> => ({
          time: d.time,
          value: d.value,
        })
      )
      lineSeries.setData(ld)
      seriesRef.current = lineSeries
    }

    chart.timeScale().fitContent()

    const handleResize = () => {
      chart.applyOptions({ width: container.clientWidth })
    }
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.remove()
      chartRef.current = null
      seriesRef.current = null
    }
  }, [data, type, height])

  return <div ref={containerRef} className={className} style={{ width: '100%' }} />
}
