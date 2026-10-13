'use client'

import { ArrowDownUp, TableProperties } from 'lucide-react'
import { useMemo, useState } from 'react'
import { formatInt, formatPercent, humanize } from '@/lib/datalens/format'
import type { ColumnInfo } from '@/lib/datalens/types'
import { usePagination } from '@/lib/datalens/use-pagination'
import {
  EmptyState,
  PaginationBar,
  Panel,
  SearchInput,
  SectionHeader,
  Tag,
  tableClass,
  tdClass,
  thClass,
  trClass,
} from './primitives'

const ROLE_TONE: Record<string, 'primary' | 'info' | 'success' | 'warning' | 'neutral'> = {
  measure: 'primary',
  category: 'info',
  temporal: 'success',
  identifier: 'warning',
  text: 'neutral',
}

type SortKey = 'original' | 'name' | 'missing' | 'unique'

export function ColumnProfile({ columns }: { columns: ColumnInfo[] }) {
  const [query, setQuery] = useState('')
  const [role, setRole] = useState('all')
  const [sort, setSort] = useState<SortKey>('original')

  const roles = useMemo(
    () => Array.from(new Set(columns.map((c) => c.role).filter(Boolean))),
    [columns],
  )

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    const list = columns.filter(
      (c) =>
        (role === 'all' || c.role === role) &&
        (!q || String(c.name).toLowerCase().includes(q)),
    )
    if (sort === 'name') return [...list].sort((a, b) => String(a.name).localeCompare(String(b.name)))
    if (sort === 'missing') return [...list].sort((a, b) => (b.missing ?? 0) - (a.missing ?? 0))
    if (sort === 'unique') return [...list].sort((a, b) => (b.unique ?? 0) - (a.unique ?? 0))
    return list
  }, [columns, query, role, sort])

  const pagination = usePagination(filtered, 10)

  return (
    <div className="flex flex-col gap-5">
      <SectionHeader
        icon={TableProperties}
        title="Column Profile"
      />
      <Panel className="overflow-hidden">
        <div className="flex flex-col gap-2 border-b p-4 sm:flex-row sm:items-center">
          <SearchInput
            value={query}
            onChange={(v) => {
              setQuery(v)
              pagination.setPage(1)
            }}
            placeholder="Search columns..."
            label="Search columns"
          />
          <div className="flex gap-2 sm:ml-auto">
            <select
              value={role}
              onChange={(e) => {
                setRole(e.target.value)
                pagination.setPage(1)
              }}
              aria-label="Filter by role"
              className="h-9 rounded-lg border bg-background px-3 text-sm capitalize outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
            >
              <option value="all">All roles</option>
              {roles.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
            <label className="relative flex items-center">
              <ArrowDownUp className="pointer-events-none absolute left-3 size-3.5 text-muted-foreground" aria-hidden />
              <span className="sr-only">Sort columns</span>
              <select
                value={sort}
                onChange={(e) => setSort(e.target.value as SortKey)}
                className="h-9 rounded-lg border bg-background pl-8 pr-3 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
              >
                <option value="original">Original order</option>
                <option value="name">Name A–Z</option>
                <option value="missing">Most missing</option>
                <option value="unique">Most unique</option>
              </select>
            </label>
          </div>
        </div>

        {filtered.length === 0 ? (
          <EmptyState title="No columns match" description="Try a different search or role filter." />
        ) : (
          <div className="max-h-[560px] overflow-auto">
            <table className={tableClass}>
              <thead>
                <tr>
                  <th className={thClass}>Column</th>
                  <th className={thClass}>Semantic type</th>
                  <th className={thClass}>Role</th>
                  <th className={thClass}>Dtype</th>
                  <th className={`${thClass} text-right`}>Non-null</th>
                  <th className={`${thClass} text-right`}>Missing</th>
                  <th className={`${thClass} text-right`}>Unique</th>
                </tr>
              </thead>
              <tbody>
                {pagination.pageItems.map((c) => (
                  <tr key={c.name} className={trClass}>
                    <td className={`${tdClass} font-medium`}>{c.name}</td>
                    <td className={`${tdClass} capitalize text-muted-foreground`}>{humanize(c.semantic_type)}</td>
                    <td className={tdClass}>
                      <Tag tone={ROLE_TONE[c.role] ?? 'neutral'}>{c.role || '—'}</Tag>
                    </td>
                    <td className={`${tdClass} font-mono text-xs text-muted-foreground`}>{c.dtype}</td>
                    <td className={`${tdClass} text-right tabular-nums`}>{formatInt(c.non_null)}</td>
                    <td className={`${tdClass} text-right tabular-nums`}>
                      <span className={c.missing ? 'text-warning' : 'text-muted-foreground'}>
                        {formatInt(c.missing)}
                      </span>
                      <span className="ml-1.5 text-xs text-muted-foreground">
                        ({formatPercent(c.missing_percent)})
                      </span>
                    </td>
                    <td className={`${tdClass} text-right tabular-nums`}>{formatInt(c.unique)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <PaginationBar state={pagination} noun="columns" />
      </Panel>
    </div>
  )
}
