'use client'

import { FileSpreadsheet, Info, LayoutDashboard, Moon, Sun } from 'lucide-react'
import { useTheme } from 'next-themes'
import { useSyncExternalStore } from 'react'
import { cn } from '@/lib/utils'
import Image from 'next/image'

export type AppView = 'analyzer' | 'about'

const subscribe = () => () => {}

function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme()
  const mounted = useSyncExternalStore(subscribe, () => true, () => false)
  const isDark = mounted ? resolvedTheme === 'dark' : true

  
const toggle = () => {
  setTheme(isDark ? 'light' : 'dark')
}


  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
      title={isDark ? 'Light theme' : 'Dark theme'}
      
className="relative flex size-9 items-center justify-center overflow-hidden rounded-lg border bg-card text-muted-foreground transition-colors duration-150 hover:text-foreground"

    >
      <Sun className={cn('absolute size-4 transition-all duration-300', isDark ? 'rotate-90 scale-0' : 'rotate-0 scale-100')} />
      <Moon className={cn('absolute size-4 transition-all duration-300', isDark ? 'rotate-0 scale-100' : '-rotate-90 scale-0')} />
    </button>
  )
}

export function Header({
  view,
  onViewChange,
  fileName,
  analyzed,
}: {
  view: AppView
  onViewChange: (view: AppView) => void
  fileName?: string
  analyzed: boolean
}) {
  const tabs = [
    { id: 'analyzer' as const, label: 'Analyzer', icon: LayoutDashboard },
    { id: 'about' as const, label: 'About', icon: Info },
  ]

  return (
    <header className="sticky top-0 z-40 border-b bg-background/80 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-4 px-4 sm:px-6">
        <button
          type="button"
          onClick={() => onViewChange('analyzer')}
          className="flex items-center gap-2.5 rounded-lg outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
          aria-label="DataLens home"
        >

<span className="relative flex size-11 shrink-0 items-center justify-center overflow-hidden rounded-xl">
  <Image
    src="/data-lens-logo.png"
    alt="DataLens logo"
    width={44}
    height={44}
    priority
    className="size-full object-contain"
  />
</span>

          <span className="flex flex-col items-start leading-none">
            <span className="text-base font-semibold tracking-tight">DataLens</span>
            <span className="mt-1 hidden text-xs text-muted-foreground sm:block">Data Quality Analyzer</span>
          </span>
        </button>

        <nav aria-label="Primary" className="ml-2 flex items-center gap-1 rounded-xl border bg-card p-1">
          {tabs.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              onClick={() => onViewChange(id)}
              aria-current={view === id ? 'page' : undefined}
              className={cn(
                'flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-all',
                view === id
                  ? 'bg-primary text-primary-foreground shadow-sm'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground',
              )}
            >
              <Icon className="size-4" aria-hidden />
              <span className="hidden sm:inline">{label}</span>
            </button>
          ))}
        </nav>

        <div className="ml-auto flex min-w-0 items-center gap-3">
          {fileName ? (
            <div className="hidden min-w-0 items-center gap-2 rounded-lg border bg-card px-3 py-1.5 text-sm md:flex">
              <FileSpreadsheet className="size-4 shrink-0 text-primary" aria-hidden />
              <span className="truncate max-w-48" title={fileName}>
                {fileName}
              </span>
              <span
                className={cn(
                  'ml-1 size-2 shrink-0 rounded-full',
                  analyzed ? 'bg-success' : 'bg-warning',
                )}
                aria-hidden
              />
              <span className="sr-only">{analyzed ? 'Analyzed' : 'Not analyzed yet'}</span>
            </div>
          ) : null}
          <ThemeToggle />
        </div>
      </div>
    </header>
  )
}
