'use client'

import { useRef, useState } from 'react'
import { toast } from 'sonner'
import { analyzeFile, validateFile } from '@/lib/datalens/api'
import type { AnalysisResult, SectionId } from '@/lib/datalens/types'
import { AnalysisNav } from './analysis-nav'
import { ColumnProfile } from './column-profile'
import { DataPreview } from './data-preview'
import { DownloadReport } from './download-report'
import { Header, type AppView } from './header'
import { MetricCards } from './metric-cards'
import { MissingDuplicates } from './missing-duplicates'
import { NumericalStatistics } from './numerical-statistics'
import { ProjectInformation } from './project-information'
import { QualitySummary } from './quality-summary'
import { UploadHero, type UploadStatus } from './upload-hero'
import { Visualizations } from './visualizations'

export function DataLensApp() {
  const [view, setView] = useState<AppView>('analyzer')
  const [file, setFile] = useState<File | null>(null)
  const [status, setStatus] = useState<UploadStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [analyzedFile, setAnalyzedFile] = useState<File | null>(null)
  const [section, setSection] = useState<SectionId>('profile')
  const requestId = useRef(0)
  const dashboardRef = useRef<HTMLDivElement>(null)

  const selectFile = (next: File) => {
    const problem = validateFile(next)

    if (problem) {
      setError(problem)
      setStatus(file ? 'error' : 'idle')
      toast.error('Invalid file', { description: problem })
      return
    }

    // Invalidate any in-flight analysis for the previously selected file.
    requestId.current++
    setFile(next)
    setError(null)
    setStatus('selected')
    setResult(null)
    setAnalyzedFile(null)

    // Every newly selected dataset starts cleanly at Column Profile.
    setSection('profile')
  }

  const removeFile = () => {
    requestId.current++
    setFile(null)
    setError(null)
    setStatus('idle')
    setResult(null)
    setAnalyzedFile(null)
    setSection('profile')
  }

  const analyze = async () => {
    if (!file || status === 'analyzing') return

    const id = ++requestId.current
    setStatus('analyzing')
    setError(null)

    try {
      const data = await analyzeFile(file)

      if (id !== requestId.current) return

      setResult(data)
      setAnalyzedFile(file)
      setSection('profile')
      setStatus('success')

      toast.success('Analysis complete', {
        description: file.name,
      })

      requestAnimationFrame(() =>
        dashboardRef.current?.scrollIntoView({
          behavior: 'smooth',
          block: 'start',
        }),
      )
    } catch (err) {
      if (id !== requestId.current) return

      const message =
        err instanceof Error
          ? err.message
          : 'Unable to analyze the dataset.'

      setError(message)
      setStatus('error')

      toast.error('Analysis failed', {
        description: message,
      })
    }
  }

  const changeSection = (id: SectionId) => {
    setSection(id)

    if (window.innerWidth < 1024) {
      dashboardRef.current?.scrollIntoView({
        behavior: 'smooth',
        block: 'start',
      })
    }
  }

  const columns = result?.columns ?? []
  const columnNames =
    result?.preview?.columns ?? columns.map((c) => c.name)

  return (
    <div className="min-h-dvh">
      <Header
        view={view}
        onViewChange={setView}
        fileName={file?.name}
        analyzed={status === 'success'}
      />

      <main className="mx-auto flex max-w-7xl flex-col gap-6 px-4 pt-6 pb-20 sm:px-6 sm:pt-8 sm:pb-24">
        {view === 'about' ? (
          <ProjectInformation />
        ) : (
          <>
            <UploadHero
              file={file}
              status={status}
              error={error}
              compact={result !== null}
              onSelect={selectFile}
              onRemove={removeFile}
              onAnalyze={analyze}
            />

            {result && analyzedFile ? (
              <div
                ref={dashboardRef}
                className="flex scroll-mt-20 flex-col gap-6"
              >
                <MetricCards summary={result.summary} />

                <div className="flex flex-col gap-6 lg:flex-row lg:items-start">
                  <aside className="lg:w-60 lg:shrink-0">
                    <AnalysisNav
                      active={section}
                      onChange={changeSection}
                      counts={{
                        profile: columns.length,
                        statistics: result.statistics?.length ?? 0,
                        visualizations: result.charts?.length ?? 0,
                        quality: result.quality?.findings?.length ?? 0,
                      }}
                    />
                  </aside>

                  <section
                    key={section}
                    className="min-w-0 flex-1 animate-section-in"
                    aria-live="polite"
                  >
                    {section === 'profile' && (
                      <ColumnProfile columns={columns} />
                    )}

                    {section === 'statistics' && (
                      <NumericalStatistics
                        statistics={result.statistics ?? []}
                      />
                    )}

                    {section === 'visualizations' && (
                      <Visualizations
                        charts={result.charts ?? []}
                      />
                    )}

                    {section === 'missing' && (
                      <MissingDuplicates
                        summary={result.summary}
                        missing={result.missing ?? []}
                        missingRecords={
                          result.issue_records?.missing ?? []
                        }
                        duplicateGroups={
                          result.duplicate_groups ?? []
                        }
                        columns={columnNames}
                      />
                    )}

                    {section === 'preview' && (
                      <DataPreview
                        columns={columnNames}
                        rows={result.preview?.rows ?? []}
                        totalRows={result.summary?.rows}
                      />
                    )}

                    {section === 'quality' && (
                      <QualitySummary data={result} />
                    )}

                    {section === 'download' && (
                      <DownloadReport file={analyzedFile} />
                    )}
                  </section>
                </div>
              </div>
            ) : null}
          </>
        )}
      </main>

      <footer className="border-t">
  <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-6 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between sm:px-6">
    <div className="flex flex-col gap-1">
      <p className="font-medium text-foreground">
        DataLens · Data Quality Analyzer
      </p>
    </div>

  </div>
</footer>
    </div>
  )
}