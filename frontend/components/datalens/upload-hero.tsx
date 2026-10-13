'use client'

import {
  AlertCircle,
  CheckCircle2,
  FileSpreadsheet,
  Loader2,
  RefreshCw,
  Sparkles,
  UploadCloud,
  X,
} from 'lucide-react'
import { useRef, useState, type DragEvent } from 'react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export type UploadStatus = 'idle' | 'selected' | 'analyzing' | 'success' | 'error'

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

export function UploadHero({
  file,
  status,
  error,
  compact,
  onSelect,
  onRemove,
  onAnalyze,
}: {
  file: File | null
  status: UploadStatus
  error: string | null
  compact: boolean
  onSelect: (file: File) => void
  onRemove: () => void
  onAnalyze: () => void
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const analyzing = status === 'analyzing'

  const handleDrop = (event: DragEvent) => {
    event.preventDefault()
    setDragging(false)
    if (analyzing) return
    const dropped = event.dataTransfer.files?.[0]
    if (dropped) onSelect(dropped)
  }

  const openPicker = () => inputRef.current?.click()

  const dropzone = (
    <div
      onDragOver={(e) => {
        e.preventDefault()
        if (!analyzing) setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      className={cn(
        'relative rounded-2xl border-2 border-dashed bg-card/60 p-6 transition-all duration-300 sm:p-8',
        dragging
          ? 'scale-[1.01] border-primary bg-accent/50 glow-primary'
          : 'border-border hover:border-primary/50',
        status === 'error' && !dragging && 'border-destructive/50',
        status === 'success' && !dragging && 'border-success/50',
      )}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".csv,.xls,.xlsx"
        className="sr-only"
        aria-label="Choose dataset file"
        onChange={(e) => {
          const picked = e.target.files?.[0]
          if (picked) onSelect(picked)
          e.target.value = ''
        }}
      />

      {!file ? (
        <div className="flex flex-col items-center gap-4 text-center">
          <span
            className={cn(
              'flex size-14 items-center justify-center rounded-2xl bg-accent text-accent-foreground transition-transform duration-300',
              dragging && '-translate-y-1 scale-110',
            )}
          >
            <UploadCloud className="size-7" aria-hidden />
          </span>
          <div>
            <p className="font-medium">
              {dragging ? 'Drop your dataset here' : 'Drag & drop your dataset here'}
            </p>
            <p className="mt-1 text-sm text-muted-foreground">or browse from your device</p>
          </div>
          <Button onClick={openPicker} size="lg" className="transition-all hover:-translate-y-px hover:glow-primary">
            Choose File
          </Button>
          <p className="text-xs text-muted-foreground">
            Supported formats: .csv, .xls, .xlsx &middot; Maximum size: 10MB
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-5">
          <div className="flex items-center gap-4 rounded-xl border bg-background/60 p-3 sm:p-4">
            <span
              className={cn(
                'flex size-11 shrink-0 items-center justify-center rounded-xl',
                status === 'success'
                  ? 'bg-success/15 text-success'
                  : status === 'error'
                    ? 'bg-destructive/15 text-destructive'
                    : 'bg-accent text-accent-foreground',
              )}
            >
              {status === 'success' ? (
                <CheckCircle2 className="size-5 animate-in zoom-in-50 duration-300" aria-hidden />
              ) : status === 'error' ? (
                <AlertCircle className="size-5" aria-hidden />
              ) : (
                <FileSpreadsheet className="size-5" aria-hidden />
              )}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium" title={file.name}>
                {file.name}
              </p>
              <p className="text-xs text-muted-foreground">
                {formatBytes(file.size)}
                {status === 'success' ? ' · Analysis complete' : null}
                {status === 'selected' ? ' · Ready to analyze' : null}
                {analyzing ? ' · Uploading & analyzing…' : null}
              </p>
            </div>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="icon"
                onClick={openPicker}
                disabled={analyzing}
                aria-label="Replace file"
                title="Replace file"
              >
                <RefreshCw />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                onClick={onRemove}
                disabled={analyzing}
                aria-label="Remove file"
                title="Remove file"
              >
                <X />
              </Button>
            </div>
          </div>

          {analyzing ? (
            <div className="h-1 overflow-hidden rounded-full bg-muted" aria-hidden>
              <div className="h-full w-1/3 animate-[progress_1.2s_ease-in-out_infinite] rounded-full bg-gradient-to-r from-primary to-info" />
            </div>
          ) : null}

          <Button
            size="lg"
            onClick={onAnalyze}
            disabled={analyzing}
            className="h-11 w-full text-sm transition-all hover:-translate-y-px hover:glow-primary active:translate-y-0"
          >
            {analyzing ? (
              <>
                <Loader2 className="animate-spin" aria-hidden />
                Analyzing your dataset...
              </>
            ) : (
              <>
                <Sparkles aria-hidden />
                {status === 'success' ? 'Re-analyze Dataset' : 'Analyze Dataset'}
              </>
            )}
          </Button>
        </div>
      )}

      {error ? (
        <p
          role="alert"
          className="mt-4 flex items-start gap-2 rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive animate-in fade-in slide-in-from-top-1"
        >
          <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
          {error}
        </p>
      ) : null}
    </div>
  )

  if (compact) {
    return <section aria-label="Dataset upload">{dropzone}</section>
  }

  return (
    <section
      aria-labelledby="hero-title"
      className="relative overflow-hidden rounded-3xl border bg-surface"
    >
      <div className="bg-grid absolute inset-0 [mask-image:radial-gradient(ellipse_at_top,black,transparent_70%)]" aria-hidden />
      <div
        className="absolute -top-32 left-1/2 h-64 w-[36rem] -translate-x-1/2 rounded-full bg-primary/20 blur-3xl"
        aria-hidden
      />
      <div className="relative grid gap-10 px-6 py-12 sm:px-10 lg:grid-cols-2 lg:items-center lg:py-16">
        <div className="flex flex-col gap-5">
          <span className="inline-flex w-fit items-center gap-2 rounded-full border bg-card px-3 py-1 text-xs font-medium text-muted-foreground">
            <span className="size-1.5 rounded-full bg-primary" aria-hidden />
            Automated data quality analysis
          </span>
          <h1 id="hero-title" className="text-balance text-4xl font-semibold tracking-tight sm:text-5xl">
            Upload. Analyze.{' '}
            <span className="bg-gradient-to-r from-primary to-info bg-clip-text text-transparent">
              Visualize.
            </span>
          </h1>
          <p className="max-w-md text-pretty leading-relaxed text-muted-foreground">
            Drop in a CSV or Excel dataset and DataLens profiles every column, surfaces missing values,
            duplicates, outliers and type issues, and builds downloadable reports.
          </p>
          <ul className="flex flex-wrap gap-2 text-xs text-muted-foreground">
            {['Column profiling', 'Missing & duplicates', 'Outliers', 'PDF · Excel · CSV reports'].map(
              (item) => (
                <li key={item} className="rounded-md border bg-card px-2.5 py-1">
                  {item}
                </li>
              ),
            )}
          </ul>
        </div>
        <div className="relative top-2">
  {dropzone}
</div>
      </div>
    </section>
  )
}
