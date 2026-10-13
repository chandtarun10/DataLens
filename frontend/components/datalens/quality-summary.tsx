import {
  AlertTriangle,
  CalendarRange,
  CheckCircle2,
  ClipboardCheck,
  Info,
  OctagonAlert,
  type LucideIcon,
} from 'lucide-react'
import { formatInt } from '@/lib/datalens/format'
import type { AnalysisResult } from '@/lib/datalens/types'
import { cn } from '@/lib/utils'
import { EmptyState, Panel, SectionHeader, Tag } from './primitives'

function formatDate(value?: string | null): string {
  if (!value) return '—'

  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)

  const date = dateOnly
    ? new Date(
        Number(dateOnly[1]),
        Number(dateOnly[2]) - 1,
        Number(dateOnly[3]),
      )
    : new Date(value)

  if (Number.isNaN(date.getTime())) return '—'

  return new Intl.DateTimeFormat('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  }).format(date)
}

const SEVERITY: Record<string, { label: string; icon: LucideIcon; className: string }> = {
  good: { label: 'Good', icon: CheckCircle2, className: 'bg-success/12 text-success' },
  info: { label: 'Info', icon: Info, className: 'bg-info/12 text-info' },
  warn: { label: 'Warning', icon: AlertTriangle, className: 'bg-warning/15 text-warning' },
  critical: { label: 'Critical', icon: OctagonAlert, className: 'bg-destructive/12 text-destructive' },
}
SEVERITY.warning = SEVERITY.warn
SEVERITY.error = SEVERITY.critical

const PROFILE_GROUPS: Array<[keyof NonNullable<AnalysisResult['profile']>, string]> = [
  ['numerical_columns', 'Numerical'],
  ['categorical_columns', 'Categorical'],
  ['date_columns', 'Date / time'],
  ['identifier_columns', 'Identifier'],
  ['text_columns', 'Free text'],
  ['constant_columns', 'Constant'],
  ['high_cardinality_columns', 'High cardinality'],
]

export function QualitySummary({ data }: { data: AnalysisResult }) {
  const findings = data.quality?.findings ?? []
  const counts = findings.reduce<Record<string, number>>((acc, f) => {
    const key = SEVERITY[f.type] ? (f.type === 'warning' ? 'warn' : f.type === 'error' ? 'critical' : f.type) : 'info'
    acc[key] = (acc[key] ?? 0) + 1
    return acc
  }, {})
  const outliers = data.report?.outliers ?? []
  const inconsistencies = data.type_inconsistencies ?? []
  const dates = data.date_analysis ?? []
  const profile = data.profile ?? {}

  return (
    <div className="flex flex-col gap-5">
      <SectionHeader
        icon={ClipboardCheck}
        title="Quality Summary"
        actions={
          typeof data.quality?.major_issues === 'number' ? (
            <Tag tone={data.quality.major_issues > 0 ? 'warning' : 'success'}>
              {formatInt(data.quality.major_issues)} Issues Detected
            </Tag>
          ) : null
        }
      />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {(['good', 'info', 'warn', 'critical'] as const).map((key) => {
          const s = SEVERITY[key]
          return (
            <Panel key={key} className="flex items-center gap-3 p-4">
              <span className={cn('flex size-9 items-center justify-center rounded-xl', s.className)}>
                <s.icon className="size-4" aria-hidden />
              </span>
              <div>
                <p className="text-xl font-semibold tabular-nums">{counts[key] ?? 0}</p>
                <p className="text-xs text-muted-foreground">{s.label}</p>
              </div>
            </Panel>
          )
        })}
      </div>

      <Panel className="overflow-hidden">
        <div className="border-b px-5 py-4">
          <h3 className="font-medium">Findings</h3>
        </div>
        {findings.length === 0 ? (
          <EmptyState title="No findings returned" />
        ) : (
          <ul className="divide-y">
            {findings.map((f, i) => {
              const s = SEVERITY[f.type] ?? SEVERITY.info
              return (
                <li
                  key={i}
                  style={{ animationDelay: `${Math.min(i, 12) * 30}ms` }}
                  className="flex animate-section-in items-start gap-3 px-5 py-3.5 transition-colors hover:bg-accent/30"
                >
                  <span className={cn('mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-lg', s.className)}>
                    <s.icon className="size-3.5" aria-hidden />
                    <span className="sr-only">{s.label}</span>
                  </span>
                  <p className="text-pretty text-sm leading-relaxed">{f.text}</p>
                </li>
              )
            })}
          </ul>
        )}
      </Panel>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel className="p-5">
          <h3 className="font-medium">Column groups</h3>
          <dl className="mt-4 flex flex-col gap-3">
            {PROFILE_GROUPS.map(([key, label]) => {
              const list = profile[key] ?? []
              return (
                <div key={key} className="flex flex-col gap-1.5 sm:flex-row sm:gap-4">
                  <dt className="w-32 shrink-0 text-sm text-muted-foreground">
                    {label} <span className="tabular-nums">({list.length})</span>
                  </dt>
                  <dd className="flex flex-wrap gap-1.5">
                    {list.length ? list.map((c) => <Tag key={c}><span className="normal-case">{c}</span></Tag>) : <span className="text-sm text-muted-foreground">—</span>}
                  </dd>
                </div>
              )
            })}
          </dl>
        </Panel>

        <div className="flex flex-col gap-4">
          <Panel className="p-5">
            <h3 className="font-medium">Potential outliers (IQR)</h3>
            {outliers.length === 0 ? (
              <p className="mt-2 text-sm text-muted-foreground">None reported.</p>
            ) : (
              <ul className="mt-3 flex flex-wrap gap-2">
                {outliers.map((o) => (
                  <li key={o.name}>
                    <Tag tone="warning">
                      <span className="normal-case">{o.name}</span>&nbsp;·&nbsp;{formatInt(o.count)}
                    </Tag>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel className="p-5">
            <h3 className="font-medium">Type inconsistencies</h3>
            {inconsistencies.length === 0 ? (
              <p className="mt-2 text-sm text-muted-foreground">None reported.</p>
            ) : (
              <ul className="mt-3 flex flex-col gap-3">
                {inconsistencies.map((t) => (
                  <li key={t.name} className="rounded-xl border bg-surface p-3 text-sm">
                    <p className="font-medium">{t.name}</p>
                    <p className="mt-1 text-muted-foreground">{t.message || t.summary}</p>
                    {t.invalid_examples?.length ? (
                      <p className="mt-2 font-mono text-xs text-muted-foreground">
                        Examples: {t.invalid_examples.map((e) => JSON.stringify(e)).join(', ')}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      </div>

      {dates.length > 0 ? (
        <Panel className="p-5">
          <h3 className="flex items-center gap-2 font-medium">
            <CalendarRange className="size-4 text-primary" aria-hidden /> Date / time columns
          </h3>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {dates.map((d) => (
              <div key={d.name} className="rounded-xl border bg-surface p-4 text-sm">
                <p className="font-medium">{d.name}</p>
                <p className="mt-2 font-mono text-xs text-muted-foreground">
                  {formatDate(d.min)} → {formatDate(d.max)}
                </p>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  <Tag tone="success">{formatInt(d.valid_count)} valid</Tag>
                  <Tag tone={d.invalid_count ? 'danger' : undefined}>{formatInt(d.invalid_count)} invalid</Tag>
                  <Tag>{formatInt(d.missing_count)} missing</Tag>
                  {d.granularity ? <Tag>{d.granularity}</Tag> : null}
                </div>
              </div>
            ))}
          </div>
        </Panel>
      ) : null}
    </div>
  )
}
