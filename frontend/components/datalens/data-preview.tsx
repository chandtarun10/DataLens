'use client'

import { Rows4 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { cellText, isMissing } from '@/lib/datalens/format'
import type { CellValue } from '@/lib/datalens/types'
import { usePagination } from '@/lib/datalens/use-pagination'
import {
  Cell,
  EmptyState,
  PaginationBar,
  Panel,
  SearchInput,
  SectionHeader,
  tableClass,
  tdClass,
  thClass,
  trClass,
} from './primitives'

type Filter = 'all' | 'missing' | 'complete'

type SortDirection = 'asc' | 'desc'

type SortConfig = {
  column: string
  direction: SortDirection
}

const SOURCE_ROW_KEY = '__source_row_number'

export function DataPreview({
  columns,
  rows,
  totalRows,
}: {
  columns: string[]
  rows: Array<Record<string, CellValue>>
  totalRows?: number
}) {
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<Filter>('all')
  const [sortConfig, setSortConfig] = useState<SortConfig | null>(null)
  const [sortColumn, setSortColumn] = useState('')
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc')

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()

    return rows.filter((row) => {
      const values = columns.map((c) => row[c])
      const hasMissing = values.some((v) => isMissing(v))

      if (filter === 'missing' && !hasMissing) return false
      if (filter === 'complete' && hasMissing) return false

      return (
        !q ||
        values.some((v) =>
          cellText(v).toLowerCase().includes(q),
        )
      )
    })
  }, [rows, columns, query, filter])

const sortedRows = useMemo(() => {
  if (!sortConfig) return filtered

  const { column, direction } = sortConfig

  return [...filtered].sort((a, b) => {
    const aValue = a[column]
    const bValue = b[column]

    const aMissing = isMissing(aValue)
    const bMissing = isMissing(bValue)

    // Keep missing values at the end in both directions.
    if (aMissing && bMissing) return 0
    if (aMissing) return 1
    if (bMissing) return -1

    const aText = cellText(aValue)
    const bText = cellText(bValue)

    const aNumber =
      typeof aValue === 'number'
        ? aValue
        : aText.trim() !== ''
          ? Number(aText)
          : Number.NaN

    const bNumber =
      typeof bValue === 'number'
        ? bValue
        : bText.trim() !== ''
          ? Number(bText)
          : Number.NaN

    let comparison: number

    if (
      Number.isFinite(aNumber) &&
      Number.isFinite(bNumber)
    ) {
      comparison = aNumber - bNumber
    } else {
      comparison = aText.localeCompare(bText, undefined, {
        numeric: true,
        sensitivity: 'base',
      })
    }

    return direction === 'asc' ? comparison : -comparison
  })
}, [filtered, sortConfig])

  const pagination = usePagination(sortedRows, 25)

  const handleSort = () => {
  if (!sortColumn) return

  setSortConfig({
    column: sortColumn,
    direction: sortDirection,
  })

  pagination.setPage(1)
}

const handleClearSort = () => {
  setSortConfig(null)
  setSortColumn('')
  setSortDirection('asc')
  pagination.setPage(1)
}

  return (
    <div className="flex flex-col gap-5">
      <SectionHeader
        icon={Rows4}
        title="Data Preview"
      />

      <Panel className="overflow-hidden">
        <div className="flex flex-col gap-2 border-b p-4 sm:flex-row sm:items-center">
          <SearchInput
            value={query}
            onChange={(v) => {
              setQuery(v)
              pagination.setPage(1)
            }}
            placeholder="Search values..."
            label="Search preview"
          />

          <div className="flex flex-wrap items-center gap-2">
  <select
    value={sortColumn}
    onChange={(e) => setSortColumn(e.target.value)}
    aria-label="Sort by column"
    className="rounded-lg border bg-background px-3 py-2 text-sm"
  >
    <option value="">Sort by column</option>
    {columns.map((column) => (
      <option key={column} value={column}>
        {column}
      </option>
    ))}
  </select>

  <select
    value={sortDirection}
    onChange={(e) =>
      setSortDirection(e.target.value as SortDirection)
    }
    aria-label="Sort direction"
    className="rounded-lg border bg-background px-3 py-2 text-sm"
  >
    <option value="asc">Ascending</option>
    <option value="desc">Descending</option>
  </select>

  <button
    type="button"
    onClick={handleSort}
    disabled={!sortColumn}
    className="rounded-lg bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50"
  >
    Apply Sort
  </button>

  <button
    type="button"
    onClick={handleClearSort}
    disabled={!sortConfig}
    className="rounded-lg border px-3 py-2 text-sm disabled:opacity-50"
  >
    Clear Sort
  </button>
</div>

          <div
            role="radiogroup"
            aria-label="Row filter"
            className="flex rounded-lg border bg-background p-0.5 sm:ml-auto"
          >
            {(
              [
                ['all', 'All rows'],
                ['missing', 'With missing'],
                ['complete', 'Complete'],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                role="radio"
                aria-checked={filter === id}
                onClick={() => {
                  setFilter(id)
                  pagination.setPage(1)
                }}
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition-all ${
                  filter === id
                    ? 'bg-primary text-primary-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {rows.length === 0 || columns.length === 0 ? (
          <EmptyState
            icon={Rows4}
            title="No preview data"
            description="The backend did not return any preview rows."
          />
        ) : filtered.length === 0 ? (
          <EmptyState
            title="No rows match"
            description="Try a different search or filter."
          />
        ) : (
          <div className="max-h-[600px] overflow-auto">
            <table className={tableClass}>
              <thead>
  <tr>
    <th className={thClass}>Source Row</th>

    {columns.map((c) => (
      <th key={c} className={thClass}>
        {c}
      </th>
    ))}

                </tr>
              </thead>

              <tbody>
                {pagination.pageItems.map((row, i) => {
                  const sourceRow = row[SOURCE_ROW_KEY]

                  return (
                    <tr
                      key={
                        typeof sourceRow === 'number'
                          ? sourceRow
                          : `${pagination.start + i}-${i}`
                      }
                      className={trClass}
                    >
                      <td
                        className={`${tdClass} whitespace-nowrap font-mono text-xs text-muted-foreground`}
                      >
                        {typeof sourceRow === 'number'
                          ? sourceRow
                          : '—'}
                      </td>

                      {columns.map((c) => (
                        <td key={c} className={tdClass}>
                          <Cell value={row[c]} highlight />
                        </td>
                      ))}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}

        <PaginationBar
          state={pagination}
          noun="rows"
          sizes={[10, 25, 50, 100]}
        />
      </Panel>
    </div>
  )
}