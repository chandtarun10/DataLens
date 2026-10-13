'use client'

import { ArrowRight, CheckCircle2, Copy, SearchCheck, SquareDashed } from 'lucide-react'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { formatInt, formatPercent } from '@/lib/datalens/format'
import type { DuplicateGroup, IssueRecord, MissingInfo, Summary } from '@/lib/datalens/types'
import { EmptyState, Panel, SectionHeader } from './primitives'
import { DuplicateGroupsModal, MissingRecordsModal } from './records-modals'

export function MissingDuplicates({
  summary,
  missing,
  missingRecords,
  duplicateGroups,
  columns,
}: {
  summary?: Summary
  missing: MissingInfo[]
  missingRecords: IssueRecord[]
  duplicateGroups: DuplicateGroup[]
  columns: string[]
}) {
  const [openMissing, setOpenMissing] = useState(false)
  const [openDuplicates, setOpenDuplicates] = useState(false)
  const withMissing = missing.filter((m) => m.count > 0).sort((a, b) => b.count - a.count)
  const maxPercent = Math.max(...withMissing.map((m) => m.percent), 1)
  const exactDuplicates = summary?.duplicate_rows ?? 0
  const duplicatesIgnoringIds = summary?.duplicate_rows_ignoring_identifiers ?? exactDuplicates
  const extraDuplicates = Math.max(duplicatesIgnoringIds - exactDuplicates, 0)
  const ignoredIdentifiers = summary?.duplicate_ignored_identifier_columns ?? []

  return (
    <div className="flex flex-col gap-5">
      <SectionHeader
        icon={SearchCheck}
        title="Missing & Duplicates"
      />

      <div className="grid gap-4 md:grid-cols-2">
        <Panel className="flex flex-col gap-4 p-5">
          <div className="flex items-center gap-3">
            <span className="flex size-10 items-center justify-center rounded-xl bg-warning/15 text-warning">
              <SquareDashed className="size-5" aria-hidden />
            </span>
            <div>
              <p className="text-sm text-muted-foreground">Missing cells</p>
              <p className="text-2xl font-semibold tabular-nums">
                {formatInt(summary?.missing_cells)}
                <span className="ml-2 text-sm font-normal text-muted-foreground">
                  {formatPercent(summary?.missing_percent)}
                </span>
              </p>
            </div>
          </div>
          <p className="text-sm text-muted-foreground">
            {formatInt(missingRecords.length)} record(s) contain at least one missing value.
          </p>
          <Button
            variant="outline"
            onClick={() => setOpenMissing(true)}
            disabled={missingRecords.length === 0}
            className="mt-auto w-fit transition-all hover:-translate-y-px"
          >
            View missing records <ArrowRight />
          </Button>
        </Panel>

        <Panel className="flex flex-col gap-4 p-5">
          <div className="flex items-center gap-3">
            <span className="flex size-10 items-center justify-center rounded-xl bg-destructive/12 text-destructive">
              <Copy className="size-5" aria-hidden />
            </span>
            <div>
              <p className="text-sm text-muted-foreground">Duplicate rows (exact)</p>
              <p className="text-2xl font-semibold tabular-nums">
                {formatInt(summary?.duplicate_rows)}
                <span className="ml-2 text-sm font-normal text-muted-foreground">
                  {formatPercent(summary?.duplicate_percent)}
                </span>
              </p>
            </div>
          </div>
          <p className="text-sm text-muted-foreground">
            {formatInt(duplicateGroups.length)} duplicate group(s) detected across exact and identifier-ignored comparisons.
            {extraDuplicates > 0
              ? ` ${formatInt(extraDuplicates)} more record(s) match when identifier column(s) (${ignoredIdentifiers.join(', ')}) are ignored.`
              : ''}
          </p>
          <Button
            variant="outline"
            onClick={() => setOpenDuplicates(true)}
            disabled={duplicateGroups.length === 0}
            className="mt-auto w-fit transition-all hover:-translate-y-px"
          >
            View duplicate groups <ArrowRight />
          </Button>
        </Panel>
      </div>

      <Panel className="overflow-hidden">
        <div className="border-b px-5 py-4">
          <h3 className="font-medium">Missing values by column</h3>
          <p className="text-sm text-muted-foreground">Only columns with at least one missing value are shown.</p>
        </div>
        {withMissing.length === 0 ? (
          <EmptyState icon={CheckCircle2} title="No missing values" description="Every column in this dataset is fully populated." />
        ) : (
          <ul className="divide-y">
            {withMissing.map((m) => (
              <li key={m.name} className="flex flex-col gap-2 px-5 py-3 transition-colors hover:bg-accent/30 sm:flex-row sm:items-center sm:gap-4">
                <span className="truncate font-medium sm:w-48" title={m.name}>
                  {m.name}
                </span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted" aria-hidden>
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-warning to-destructive transition-all duration-700"
                    style={{ width: `${Math.max((m.percent / maxPercent) * 100, 2)}%` }}
                  />
                </div>
                <span className="text-sm tabular-nums text-muted-foreground sm:w-36 sm:text-right">
                  <span className="font-medium text-foreground">{formatInt(m.count)}</span> · {formatPercent(m.percent)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <MissingRecordsModal open={openMissing} onOpenChange={setOpenMissing} records={missingRecords} columns={columns} />
      <DuplicateGroupsModal open={openDuplicates} onOpenChange={setOpenDuplicates} groups={duplicateGroups} columns={columns} />
    </div>
  )
}
