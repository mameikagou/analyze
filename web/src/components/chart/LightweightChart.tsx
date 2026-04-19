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
 * 样式全部从 CSS 变量读取（tokens.chart.css），禁止硬编码 HEX。
 * Market-aware 涨跌色通过父容器的 data-market="cn" 自动切换。
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

    /* 从计算样式读取 CSS 变量 — 自动响应 data-market 和 .dark */
    const style = getComputedStyle(container)
    const chartUp = style.getPropertyValue('--chart-up').trim() || '#22c55e'
    const chartDown = style.getPropertyValue('--chart-down').trim() || '#ef4444'
    const chartGrid = style.getPropertyValue('--chart-grid').trim() || '#e7e5e4'
    const chartCrosshair = style.getPropertyValue('--chart-crosshair').trim() || '#78716c'

    const chart = createChart(container, {
      height,
      layout: {
        background: { color: 'transparent' },
        textColor: 'currentColor',
      },
      grid: {
        vertLines: { color: chartGrid + '4d' }, /* 30% opacity = 0x4d */
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
      rightPriceScale: {
        borderColor: chartGrid,
      },
      timeScale: {
        borderColor: chartGrid,
        timeVisible: false,
      },
    })

    chartRef.current = chart

    if (type === 'candlestick') {
      const candleSeries = chart.addSeries(CandlestickSeries, {
        upColor: chartUp,
        downColor: chartDown,
        borderUpColor: chartUp,
        borderDownColor: chartDown,
        wickUpColor: chartUp,
        wickDownColor: chartDown,
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
        color: style.getPropertyValue('--chart-ma-short').trim() || '#f97316',
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
