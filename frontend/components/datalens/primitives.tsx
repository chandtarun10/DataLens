'use client'

import type { LucideIcon } from 'lucide-react'
import { ChevronLeft, ChevronRight, Inbox, Loader2, Search, X } from 'lucide-react'
import type { ReactNode } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { formatInt, isMissing } from '@/lib/datalens/format'
import type { CellValue } from '@/lib/datalens/types'
import type { PaginationState } from '@/lib/datalens/use-pagination'

export function SectionHeader({
  icon: Icon,
  title,
  description,
  actions,
}: {
  icon: LucideIcon
  title: string
  description?: ReactNode
  actions?: ReactNode
}) {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 flex size-10 shrink-0 items-center justify-center rounded-xl bg-accent text-accent-foreground">
          <Icon className="size-5" aria-hidden />
        </span>
        <div>
          <h2 className="text-balance text-xl font-semibold tracking-tight">{title}</h2>
          {description ? (
            <p className="mt-1 text-pretty text-sm text-muted-foreground">{description}</p>
          ) : null}
        </div>
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  )
}

export function Panel({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div className={cn('rounded-2xl border bg-card text-card-foreground shadow-sm', className)}>
      {children}
    </div>
  )
}

export function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
}: {
  icon?: LucideIcon
  title: string
  description?: string
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 px-6 py-14 text-center">
      <span className="flex size-12 items-center justify-center rounded-2xl bg-muted text-muted-foreground">
        <Icon className="size-6" aria-hidden />
      </span>
      <p className="font-medium">{title}</p>
      {description ? (
        <p className="max-w-sm text-pretty text-sm text-muted-foreground">{description}</p>
      ) : null}
    </div>
  )
}

export function LoadingState({ label = 'Analyzing your dataset...' }: { label?: string }) {
  return (
    <div role="status" className="flex items-center justify-center gap-3 py-14 text-muted-foreground">
      <Loader2 className="size-5 animate-spin text-primary" aria-hidden />
      <span className="text-sm">{label}</span>
    </div>
  )
}

export function SearchInput({
  value,
  onChange,
  placeholder,
  label,
  className,
}: {
  value: string
  onChange: (value: string) => void
  placeholder: string
  label: string
  className?: string
}) {
  return (
    <div className={cn('relative w-full sm:w-64', className)}>
      <Search
        className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
        aria-hidden
      />
      <Input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        aria-label={label}
        className="h-9 rounded-lg pl-9 pr-8"
      />
      {value ? (
        <button
          type="button"
          onClick={() => onChange('')}
          className="absolute right-2 top-1/2 flex size-6 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          aria-label="Clear search"
        >
          <X className="size-3.5" />
        </button>
      ) : null}
    </div>
  )
}

const PAGE_SIZES = [10, 25, 50]

export function PaginationBar({
  state,
  noun = 'rows',
  sizes = PAGE_SIZES,
}: {
  state: PaginationState
  noun?: string
  sizes?: number[]
}) {
  const { page, pageCount, pageSize, total, start, setPage, setPageSize } = state
  if (total === 0) return null
  const end = Math.min(start + pageSize, total)

  return (
    <nav
      aria-label={`${noun} pagination`}
      className="flex flex-col gap-3 border-t px-4 py-3 text-sm sm:flex-row sm:items-center sm:justify-between"
    >
      <p className="text-muted-foreground">
        Showing <span className="font-medium text-foreground">{formatInt(start + 1)}</span>–
        <span className="font-medium text-foreground">{formatInt(end)}</span> of{' '}
        <span className="font-medium text-foreground">{formatInt(total)}</span> {noun}
      </p>
      <div className="flex items-center gap-2">
        <label className="flex items-center gap-2 text-muted-foreground">
          <span className="sr-only sm:not-sr-only">Per page</span>
          <select
            value={pageSize}
            onChange={(e) => setPageSize(Number(e.target.value))}
            className="h-8 rounded-lg border bg-background px-2 text-foreground outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
          >
            {sizes.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </label>
        <Button
          variant="outline"
          size="icon-sm"
          onClick={() => setPage(page - 1)}
          disabled={page <= 1}
          aria-label="Previous page"
        >
          <ChevronLeft />
        </Button>
        <span className="min-w-16 text-center tabular-nums text-muted-foreground">
          {page} / {pageCount}
        </span>
        <Button
          variant="outline"
          size="icon-sm"
          onClick={() => setPage(page + 1)}
          disabled={page >= pageCount}
          aria-label="Next page"
        >
          <ChevronRight />
        </Button>
      </div>
    </nav>
  )
}

export function Cell({ value, highlight }: { value: CellValue | undefined; highlight?: boolean }) {
  if (isMissing(value)) {
    return (
      <span
        className={cn(
          'inline-flex items-center rounded-md px-1.5 py-0.5 font-mono text-[11px] uppercase tracking-wide',
          highlight
            ? 'bg-destructive/15 text-destructive ring-1 ring-destructive/30'
            : 'bg-muted text-muted-foreground',
        )}
      >
        missing
      </span>
    )
  }
  return <span className="whitespace-pre">{String(value)}</span>
}

export const tableClass = 'w-full border-collapse text-left text-sm'
export const thClass =
  'sticky top-0 z-10 whitespace-nowrap border-b bg-surface px-4 py-3 text-xs font-medium uppercase tracking-wide text-muted-foreground'
export const tdClass = 'whitespace-nowrap border-b px-4 py-3 align-middle'
export const trClass = 'transition-colors hover:bg-accent/40'

export function Tag({
  children,
  tone = 'neutral',
}: {
  children: ReactNode
  tone?: 'neutral' | 'primary' | 'info' | 'success' | 'warning' | 'danger'
}) {
  const tones = {
    neutral: 'bg-muted text-muted-foreground',
    primary: 'bg-primary/12 text-primary ring-primary/25',
    info: 'bg-info/12 text-info ring-info/25',
    success: 'bg-success/12 text-success ring-success/25',
    warning: 'bg-warning/15 text-warning ring-warning/30',
    danger: 'bg-destructive/12 text-destructive ring-destructive/25',
  }
  return (
    <span
      className={cn(
        'inline-flex items-center whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-medium capitalize ring-1 ring-transparent',
        tones[tone],
      )}
    >
      {children}
    </span>
  )
}
