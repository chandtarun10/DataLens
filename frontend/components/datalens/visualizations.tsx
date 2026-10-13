'use client'

import dynamic from 'next/dynamic'
import { BarChart3, Maximize2 } from 'lucide-react'
import { Component, useState, type ReactNode } from 'react'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import type { PlotlyChart as ChartSpec } from '@/lib/datalens/types'
import { EmptyState, LoadingState, Panel, SectionHeader } from './primitives'

const PlotlyChart = dynamic(() => import('./plotly-chart'), {
  ssr: false,
  loading: () => <LoadingState label="Rendering chart..." />,
})

class ChartBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() {
    return { failed: true }
  }
  render() {
    if (this.state.failed) {
      return <EmptyState icon={BarChart3} title="Chart could not be rendered" description="The chart data returned by the backend is not in a supported format." />
    }
    return this.props.children
  }
}

function hasData(chart: ChartSpec) {
  return Array.isArray(chart.data) && chart.data.length > 0
}

export function Visualizations({ charts }: { charts: ChartSpec[] }) {
  const [expanded, setExpanded] = useState<ChartSpec | null>(null)

  return (
    <div className="flex flex-col gap-5">
      <SectionHeader
        icon={BarChart3}
        title="Visualizations"
      />
      {charts.length === 0 ? (
        <Panel>
          <EmptyState icon={BarChart3} title="No charts available" description="The backend did not return any chart data for this dataset." />
        </Panel>
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          {charts.map((chart, i) => (
            <Panel
              key={`${chart.title ?? 'chart'}-${i}`}
              className="group flex flex-col overflow-hidden transition-all duration-300 hover:border-primary/40"
            >
              <div className="flex items-center justify-between gap-3 border-b px-4 py-3">
                <h3 className="truncate text-sm font-medium" title={chart.title}>
                  {chart.title || `Chart ${i + 1}`}
                </h3>
                {hasData(chart) ? (
                  <button
                    type="button"
                    onClick={() => setExpanded(chart)}
                    className="flex size-8 items-center justify-center rounded-lg text-muted-foreground transition-all hover:bg-muted hover:text-foreground"
                    aria-label={`Expand ${chart.title || 'chart'}`}
                  >
                    <Maximize2 className="size-4" />
                  </button>
                ) : null}
              </div>
              <div className="px-2 py-2">
                {hasData(chart) ? (
                  <ChartBoundary>
                    <PlotlyChart chart={chart} />
                  </ChartBoundary>
                ) : (
                  <EmptyState icon={BarChart3} title="No data for this chart" />
                )}
              </div>
              {chart.note ? (
                <p className="border-t px-4 py-2 text-xs text-muted-foreground">{chart.note}</p>
              ) : null}
            </Panel>
          ))}
        </div>
      )}

      <Dialog open={expanded !== null} onOpenChange={(open) => !open && setExpanded(null)}>
        <DialogContent className="max-w-[calc(100%-2rem)] gap-3 p-5 sm:max-w-5xl">
          <DialogHeader>
            <DialogTitle>{expanded?.title || 'Chart'}</DialogTitle>
            <DialogDescription>Hover, zoom and pan to explore. Double-click to reset.</DialogDescription>
          </DialogHeader>
          {expanded ? (
            <ChartBoundary>
              <PlotlyChart chart={expanded} height={520} />
            </ChartBoundary>
          ) : null}
          {expanded?.note ? <p className="text-xs text-muted-foreground">{expanded.note}</p> : null}
        </DialogContent>
      </Dialog>
    </div>
  )
}
