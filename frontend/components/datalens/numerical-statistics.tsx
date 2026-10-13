'use client'

import { Sigma } from 'lucide-react'
import { useMemo, useState } from 'react'
import { formatStat } from '@/lib/datalens/format'
import type { StatisticRow } from '@/lib/datalens/types'
import { usePagination } from '@/lib/datalens/use-pagination'
import {
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

const METRICS = ['min', 'max', 'mean', 'median', 'std'] as const
const METRIC_LABEL = { min: 'Min', max: 'Max', mean: 'Mean', median: 'Median', std: 'Std Dev' }

export function NumericalStatistics({ statistics }: { statistics: StatisticRow[] }) {
  const [query, setQuery] = useState('')
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return q ? statistics.filter((s) => String(s.name).toLowerCase().includes(q)) : statistics
  }, [statistics, query])
  const pagination = usePagination(filtered, 10)

  return (
    <div className="flex flex-col gap-5">
      <SectionHeader
        icon={Sigma}
        title="Numerical Statistics"
      />
      <Panel className="overflow-hidden">
        {statistics.length === 0 ? (
          <EmptyState
            icon={Sigma}
            title="No numerical measure columns"
            description="The backend did not detect any suitable numerical measure columns in this dataset."
          />
        ) : (
          <>
            <div className="border-b p-4">
              <SearchInput
                value={query}
                onChange={(v) => {
                  setQuery(v)
                  pagination.setPage(1)
                }}
                placeholder="Search columns..."
                label="Search numerical columns"
              />
            </div>
            {filtered.length === 0 ? (
              <EmptyState title="No columns match" description="Try a different search term." />
            ) : (
              <div className="max-h-[560px] overflow-auto">
                <table className={tableClass}>
                  <thead>
                    <tr>
                      <th className={thClass}>Column</th>
                      {METRICS.map((m) => (
                        <th key={m} className={`${thClass} text-right`}>
                          {METRIC_LABEL[m]}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {pagination.pageItems.map((row) => (
                      <tr key={row.name} className={trClass}>
                        <td className={`${tdClass} font-medium`}>{row.name}</td>
                        {METRICS.map((m) => (
                          <td key={m} className={`${tdClass} text-right font-mono text-xs tabular-nums`}>
                            {formatStat(row[m])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <PaginationBar state={pagination} noun="columns" />
          </>
        )}
      </Panel>
    </div>
  )
}
