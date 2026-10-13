import type { CellValue } from './types'

const integer = new Intl.NumberFormat('en-US')

export function formatInt(value: unknown) {
  return typeof value === 'number' && Number.isFinite(value) ? integer.format(value) : '—'
}

export function formatPercent(value: unknown) {
  return typeof value === 'number' && Number.isFinite(value) ? `${value.toFixed(2)}%` : '—'
}

export function formatStat(value: CellValue | undefined) {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'number') {
    return value.toLocaleString('en-US', { maximumFractionDigits: 4 })
  }
  return String(value)
}

export function isMissing(value: CellValue | undefined) {
  return value === null || value === undefined
}

export function cellText(value: CellValue | undefined) {
  if (isMissing(value)) return ''
  return String(value)
}

export function humanize(value: string | undefined) {
  if (!value) return '—'
  return value.replace(/_/g, ' ')
}
