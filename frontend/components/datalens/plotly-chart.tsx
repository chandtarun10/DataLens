'use client'

import Plotly from 'plotly.js-dist-min'
import createPlotlyComponent from 'react-plotly.js/factory'
import { useTheme } from 'next-themes'
import { useMemo } from 'react'
import type { PlotlyChart as ChartSpec } from '@/lib/datalens/types'

const Plot = createPlotlyComponent(Plotly)

type Axis = Record<string, unknown>

// Plotly v3 dropped string axis titles; wrap them so backend layouts still render.
function normalizeAxis(axis: unknown, gridColor: string): Axis {
  const a = (axis && typeof axis === 'object' ? axis : {}) as Axis
  const title = typeof a.title === 'string' ? { text: a.title } : a.title
  return { gridcolor: gridColor, zerolinecolor: gridColor, automargin: true, ...a, title }
}

export default function PlotlyChart({ chart, height = 340 }: { chart: ChartSpec; height?: number }) {
  const { resolvedTheme } = useTheme()
  const dark = resolvedTheme !== 'light'

  const layout = useMemo(() => {
    const base = (chart.layout ?? {}) as Record<string, unknown>
    const fg = dark ? '#c9c6e0' : '#3d3a5c'
    const grid = dark ? 'rgba(255,255,255,0.08)' : 'rgba(20,20,60,0.08)'
    return {
      ...base,
      title: undefined,
      showlegend: false,
      autosize: true,
      height,
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { family: 'Inter, ui-sans-serif, system-ui', size: 12, color: fg },
      margin: { t: 16, r: 16, b: 48, l: 56 },
      hoverlabel: { font: { family: 'Inter, ui-sans-serif' } },
      xaxis: normalizeAxis(base.xaxis, grid),
      yaxis: normalizeAxis(base.yaxis, grid),
    }
  }, [chart.layout, dark, height])

  return (
    <Plot
      data={(chart.data ?? []).map((trace) => ({ ...trace, name: trace.name === 'trace 0' ? '' : trace.name })) as Plotly.Data[]}
      layout={layout as Partial<Plotly.Layout>}
      config={{ responsive: true, displaylogo: false, modeBarButtonsToRemove: ['lasso2d', 'select2d'] }}
      useResizeHandler
      style={{ width: '100%', height }}
    />
  )
}
