'use client'

import {
  BarChart3,
  ClipboardCheck,
  Download,
  Rows4,
  SearchCheck,
  Sigma,
  TableProperties,
  type LucideIcon,
} from 'lucide-react'
import type { SectionId } from '@/lib/datalens/types'
import { cn } from '@/lib/utils'

export const SECTIONS: { id: SectionId; label: string; icon: LucideIcon }[] = [
  { id: 'profile', label: 'Column Profile', icon: TableProperties },
  { id: 'statistics', label: 'Numerical Statistics', icon: Sigma },
  { id: 'visualizations', label: 'Visualizations', icon: BarChart3 },
  { id: 'missing', label: 'Missing & Duplicates', icon: SearchCheck },
  { id: 'preview', label: 'Data Preview', icon: Rows4 },
  { id: 'quality', label: 'Quality Summary', icon: ClipboardCheck },
  { id: 'download', label: 'Download Report', icon: Download },
]

export function AnalysisNav({
  active,
  onChange,
  counts,
}: {
  active: SectionId
  onChange: (id: SectionId) => void
  counts: Partial<Record<SectionId, number>>
}) {
  return (
    <nav aria-label="Analysis sections" className="lg:sticky lg:top-24">
      <p className="mb-2 hidden px-3 text-xs font-medium uppercase tracking-wider text-muted-foreground lg:block">
        Analysis
      </p>
      <ul className="-mx-4 flex gap-1.5 overflow-x-auto px-4 pb-1 lg:mx-0 lg:flex-col lg:overflow-visible lg:px-0 lg:pb-0">
        {SECTIONS.map(({ id, label, icon: Icon }) => {
          const isActive = active === id
          const count = counts[id]
          return (
            <li key={id} className="shrink-0">
              <button
                type="button"
                onClick={() => onChange(id)}
                aria-current={isActive ? 'true' : undefined}
                className={cn(
                  'group relative flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-sm font-medium transition-all duration-200',
                  isActive
                    ? 'bg-primary text-primary-foreground shadow-md shadow-primary/20'
                    : 'border bg-card text-muted-foreground hover:text-foreground lg:border-transparent lg:bg-transparent lg:hover:bg-accent/60',
                )}
              >
                <Icon
                  className={cn('size-4 shrink-0 transition-transform group-hover:scale-110')}
                  aria-hidden
                />
                <span className="whitespace-nowrap">{label}</span>
                {typeof count === 'number' ? (
                  <span
                    className={cn(
                      'ml-auto rounded-md px-1.5 text-xs tabular-nums',
                      isActive ? 'bg-primary-foreground/20' : 'bg-muted',
                    )}
                  >
                    {count}
                  </span>
                ) : null}
              </button>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
