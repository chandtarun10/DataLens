'use client'

import { Copy, SquareDashed } from 'lucide-react'
import { useMemo, useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { cellText, formatInt } from '@/lib/datalens/format'
import type { DuplicateGroup, IssueRecord } from '@/lib/datalens/types'
import { usePagination } from '@/lib/datalens/use-pagination'
import {
  Cell,
  EmptyState,
  PaginationBar,
  SearchInput,
  Tag,
  tableClass,
  tdClass,
  thClass,
  trClass,
} from './primitives'

function recordMatches(record: IssueRecord, q: string) {
  if (!q) return true

  if (String(record.row_number).includes(q)) return true

  return Object.values(record.values ?? {}).some((v) =>
    cellText(v).toLowerCase().includes(q),
  )
}

// The table itself never scrolls. The modal body is the ONE scroll container
// (both axes), so the horizontal scrollbar stays at the bottom of the visible
// area, sticky headers work, and the Row # column stays visible while
// scrolling sideways.
function RecordsTable({
  records,
  columns,
  highlightMissing,
  markColumns,
}: {
  records: IssueRecord[]
  columns: string[]
  highlightMissing?: boolean
  markColumns?: Set<string>
}) {
  return (
    <table className={`${tableClass} min-w-max`}>
      <thead>
        <tr>
          <th className={`${thClass} left-0 z-30`}>Row #</th>

          {highlightMissing ? (
            <th className={thClass}>Missing in</th>
          ) : null}

          {columns.map((c) => (
            <th key={c} className={thClass}>
              {c}
            </th>
          ))}
        </tr>
      </thead>

      <tbody>
        {records.map((r) => {
          const missingSet = new Set(r.missing_columns ?? [])

          return (
            <tr key={r.row_number} className={trClass}>
              <td
                className={`${tdClass} sticky left-0 z-10 bg-card font-mono text-xs font-medium text-primary`}
              >
                {r.row_number}
              </td>

              {highlightMissing ? (
                <td className={tdClass}>
                  <div className="flex max-w-64 flex-wrap gap-1">
                    {(r.missing_columns ?? []).map((m) => (
                      <Tag key={m} tone="danger">
                        <span className="normal-case">{m}</span>
                      </Tag>
                    ))}
                  </div>
                </td>
              ) : null}

              {columns.map((c) => (
                <td
                  key={c}
                  className={`${tdClass} ${
                    markColumns?.has(c) ? 'bg-warning/10' : ''
                  }`}
                >
                  <Cell
                    value={r.values?.[c]}
                    highlight={highlightMissing && missingSet.has(c)}
                  />
                </td>
              ))}
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

export function MissingRecordsModal({
  open,
  onOpenChange,
  records,
  columns,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  records: IssueRecord[]
  columns: string[]
}) {
  const [query, setQuery] = useState('')
  const [column, setColumn] = useState('all')

  const missingColumns = useMemo(
    () =>
      Array.from(
        new Set(
          records.flatMap((r) => r.missing_columns ?? []),
        ),
      ),
    [records],
  )

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()

    return records.filter(
      (r) =>
        (column === 'all' ||
          (r.missing_columns ?? []).includes(column)) &&
        recordMatches(r, q),
    )
  }, [records, query, column])

  const pagination = usePagination(filtered, 10)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex h-[80vh] max-h-[90vh] w-[calc(100%-2rem)] max-w-[90vw] flex-col gap-0 overflow-hidden p-0 sm:max-w-[90vw]">
        <DialogHeader className="shrink-0 border-b p-5 pr-14">
          <DialogTitle className="flex items-center gap-2">
            <SquareDashed
              className="size-4 text-warning"
              aria-hidden
            />
            Records with missing values
          </DialogTitle>

          <DialogDescription>
            {formatInt(records.length)} record(s) contain at least one
            missing value. Row numbers refer to the original dataset.
          </DialogDescription>
        </DialogHeader>

        <div className="flex shrink-0 flex-col gap-2 border-b p-4 sm:flex-row">
          <SearchInput
            value={query}
            onChange={(v) => {
              setQuery(v)
              pagination.setPage(1)
            }}
            placeholder="Search row # or values..."
            label="Search missing records"
          />

          <select
            value={column}
            onChange={(e) => {
              setColumn(e.target.value)
              pagination.setPage(1)
            }}
            aria-label="Filter by missing column"
            className="h-9 rounded-lg border bg-background px-3 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/50 sm:ml-auto"
          >
            <option value="all">All columns</option>

            {missingColumns.map((c) => (
              <option key={c} value={c}>
                Missing in: {c}
              </option>
            ))}
          </select>
        </div>

        <div
          className="modal-scroll min-h-0 flex-1 overflow-auto"
          data-testid="records-scroll"
        >
          {filtered.length === 0 ? (
            <EmptyState title="No matching records" />
          ) : (
            <RecordsTable
              records={pagination.pageItems}
              columns={columns}
              highlightMissing
            />
          )}
        </div>

        <div className="shrink-0">
          <PaginationBar
            state={pagination}
            noun="records"
          />
        </div>
      </DialogContent>
    </Dialog>
  )
}

export function DuplicateGroupsModal({
  open,
  onOpenChange,
  groups,
  columns,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  groups: DuplicateGroup[]
  columns: string[]
}) {
  const [query, setQuery] = useState('')

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()

    return groups.filter(
      (g) =>
        !q ||
        (g.rows ?? []).some((r) =>
          recordMatches(r, q),
        ),
    )
  }, [groups, query])

  const pagination = usePagination(filtered, 5)

  const hasIdentifierGroups = groups.some(
    (g) => g.match_type === 'identifier_excluded',
  )

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex h-[80vh] max-h-[90vh] w-[calc(100%-2rem)] max-w-[90vw] flex-col gap-0 overflow-hidden p-0 sm:max-w-[90vw]">
        <DialogHeader className="shrink-0 border-b p-5 pr-14">
          <DialogTitle className="flex items-center gap-2">
            <Copy
              className="size-4 text-destructive"
              aria-hidden
            />
            Duplicate record groups
          </DialogTitle>

          <DialogDescription>
            {formatInt(groups.length)} group(s) of duplicate records.
            The first row in each group is the original.
            {hasIdentifierGroups
              ? ' Groups marked "Identifiers differ" match in every non-identifier column; the differing identifier columns are shaded.'
              : ''}
          </DialogDescription>
        </DialogHeader>

        <div className="shrink-0 border-b p-4">
          <SearchInput
            value={query}
            onChange={(v) => {
              setQuery(v)
              pagination.setPage(1)
            }}
            placeholder="Search row # or values..."
            label="Search duplicate groups"
          />
        </div>

        <div
          className="modal-scroll flex min-h-0 flex-1 flex-col gap-4 overflow-auto p-4"
          data-testid="duplicates-scroll"
        >
          {filtered.length === 0 ? (
            <EmptyState title="No matching groups" />
          ) : (
            pagination.pageItems.map((g) => (
              <div
                key={g.group_id}
                className="animate-section-in w-max min-w-full shrink-0 overflow-clip rounded-xl border"
              >
                <div className="border-b bg-surface">
                  <div className="sticky left-0 flex w-fit max-w-[calc(90vw-4.5rem)] flex-wrap items-center gap-2 px-4 py-2.5 text-sm">
                    <span className="font-medium">
                      Group {g.group_id}
                    </span>

                    <Tag tone="danger">
                      {formatInt(g.duplicate_count)} duplicate(s)
                    </Tag>

                    {g.match_type ? (
                      <Tag
                        tone={
                          g.match_type === 'exact'
                            ? 'danger'
                            : 'warning'
                        }
                      >
                        {g.match_type === 'exact'
                          ? 'Exact match'
                          : 'Identifiers differ'}
                      </Tag>
                    ) : null}

                    <span className="text-muted-foreground">
                      Rows:{' '}
                      <span className="font-mono text-xs">
                        {(g.row_numbers ?? []).join(', ')}
                      </span>
                    </span>

                    {g.differing_identifier_columns?.length ? (
                      <span className="text-muted-foreground">
                        Differs in:{' '}
                        <span className="font-mono text-xs">
                          {g.differing_identifier_columns.join(', ')}
                        </span>
                      </span>
                    ) : null}
                  </div>
                </div>

                <RecordsTable
                  records={g.rows ?? []}
                  columns={columns}
                  markColumns={
                    new Set(g.differing_identifier_columns ?? [])
                  }
                />
              </div>
            ))
          )}
        </div>

        <div className="shrink-0">
          <PaginationBar
            state={pagination}
            noun="groups"
            sizes={[5, 10, 25]}
          />
        </div>
      </DialogContent>
    </Dialog>
  )
}
