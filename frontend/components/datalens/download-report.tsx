'use client'

import { Check, Download, FileSpreadsheet, FileText, Loader2, Sheet, type LucideIcon } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { downloadReport } from '@/lib/datalens/api'
import type { ReportFormat } from '@/lib/datalens/types'
import { cn } from '@/lib/utils'
import { SectionHeader } from './primitives'

const OPTIONS: { format: ReportFormat; title: string; description: string; icon: LucideIcon }[] = [
  { format: 'pdf', title: 'PDF Report', description: 'Formatted report with summary, findings and charts.', icon: FileText },
  { format: 'xlsx', title: 'Excel Report', description: 'Multi-sheet workbook with profiles and statistics.', icon: FileSpreadsheet },
  { format: 'csv', title: 'CSV Report', description: 'Plain-text tabular export of the analysis.', icon: Sheet },
]

type State = 'idle' | 'loading' | 'done'

export function DownloadReport({ file }: { file: File }) {
  const [states, setStates] = useState<Record<ReportFormat, State>>({ pdf: 'idle', xlsx: 'idle', csv: 'idle' })

  const run = async (format: ReportFormat, title: string) => {
    if (states[format] === 'loading') return
    setStates((s) => ({ ...s, [format]: 'loading' }))
    try {
      const filename = await downloadReport(file, format)
      setStates((s) => ({ ...s, [format]: 'done' }))
      toast.success(`${title} downloaded`, { description: filename })
      window.setTimeout(() => setStates((s) => ({ ...s, [format]: 'idle' })), 2500)
    } catch (error) {
      setStates((s) => ({ ...s, [format]: 'idle' }))
      toast.error(`${title} failed`, {
        description: error instanceof Error ? error.message : 'Unable to download report.',
      })
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <SectionHeader
        icon={Download}
        title="Download Report"
      />
      <div className="grid gap-4 md:grid-cols-3">
        {OPTIONS.map(({ format, title, description, icon: Icon }) => {
          const state = states[format]
          return (
            <button
              key={format}
              type="button"
              onClick={() => run(format, title)}
              disabled={state === 'loading'}
              aria-busy={state === 'loading'}
              className={cn(
                'group flex flex-col items-start gap-4 rounded-2xl border bg-card p-5 text-left shadow-sm transition-all duration-300',
                'hover:-translate-y-1 hover:border-primary/40 hover:glow-primary active:translate-y-0 active:scale-[0.99]',
                'disabled:cursor-wait disabled:opacity-80',
                state === 'done' && 'border-success/50',
              )}
            >
              <span
                className={cn(
                  'flex size-11 items-center justify-center rounded-xl transition-all duration-300 group-hover:scale-110',
                  state === 'done' ? 'bg-success/15 text-success' : 'bg-accent text-accent-foreground',
                )}
              >
                {state === 'loading' ? (
                  <Loader2 className="size-5 animate-spin" aria-hidden />
                ) : state === 'done' ? (
                  <Check className="size-5 animate-in zoom-in-50" aria-hidden />
                ) : (
                  <Icon className="size-5" aria-hidden />
                )}
              </span>
              <div>
                <p className="font-medium">{title}</p>
                <p className="mt-1 text-pretty text-sm text-muted-foreground">{description}</p>
              </div>
              <span className="mt-auto inline-flex items-center gap-1.5 text-sm font-medium text-primary">
                {state === 'loading' ? 'Generating…' : state === 'done' ? 'Downloaded' : (
                  <>
                    Download <Download className="size-3.5 transition-transform group-hover:translate-y-0.5" aria-hidden />
                  </>
                )}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
