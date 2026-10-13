import { Columns3, CopyX, Rows3, SquareDashed, type LucideIcon } from 'lucide-react'
import { formatInt, formatPercent } from '@/lib/datalens/format'
import type { Summary } from '@/lib/datalens/types'
import { cn } from '@/lib/utils'

interface Metric {
  label: string
  value: string
  detail?: string
  icon: LucideIcon
  tone: string
}

export function MetricCards({ summary }: { summary?: Summary }) {
  const metrics: Metric[] = [
    {
      label: 'Total Rows',
      value: formatInt(summary?.rows),
      icon: Rows3,
      tone: 'bg-primary/12 text-primary',
    },
    {
      label: 'Total Columns',
      value: formatInt(summary?.columns),
      icon: Columns3,
      tone: 'bg-info/12 text-info',
    },
    {
      label: 'Missing Values',
      value: formatInt(summary?.missing_cells),
      detail: `${formatPercent(summary?.missing_percent)} of cells`,
      icon: SquareDashed,
      tone: 'bg-warning/15 text-warning',
    },
    {
      label: 'Exact Duplicate Rows',
      value: formatInt(summary?.duplicate_rows),
      detail: `${formatPercent(summary?.duplicate_percent)} exact · ${formatInt(summary?.duplicate_rows_ignoring_identifiers ?? summary?.duplicate_rows)} duplicate occurrences · ${formatInt(summary?.duplicate_groups_total)} groups ignoring IDs`,
      icon: CopyX,
      tone: 'bg-destructive/12 text-destructive',
    },
  ]

  return (
    <section aria-label="Dataset summary" className="grid grid-cols-2 gap-3 lg:grid-cols-4 lg:gap-4">
      {metrics.map(({ label, value, detail, icon: Icon, tone }, i) => (
        <div
          key={label}
          style={{ animationDelay: `${i * 60}ms` }}
          className="group animate-section-in rounded-2xl border bg-card p-4 shadow-sm transition-all duration-300 hover:-translate-y-0.5 hover:border-primary/40 hover:glow-primary sm:p-5"
        >
          <div className="flex items-center justify-between gap-2">
            <p className="text-sm text-muted-foreground">{label}</p>
            <span
              className={cn(
                'flex size-9 items-center justify-center rounded-xl transition-transform duration-300 group-hover:scale-110',
                tone,
              )}
            >
              <Icon className="size-4.5" aria-hidden />
            </span>
          </div>
          <p className="mt-3 text-2xl font-semibold tabular-nums tracking-tight sm:text-3xl">{value}</p>
          {detail ? <p className="mt-1 text-xs tabular-nums text-muted-foreground">{detail}</p> : null}
        </div>
      ))}
    </section>
  )
}
