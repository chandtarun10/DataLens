import type { AnalysisResult, ReportFormat } from './types'

export const API_BASE = (
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
).replace(/\/+$/, '')

export const ALLOWED_EXTENSIONS = ['.csv', '.xls', '.xlsx'] as const

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

export function validateFile(file: File): string | null {
  const name = file.name.toLowerCase()
  const ext = name.slice(name.lastIndexOf('.'))

  if (!ALLOWED_EXTENSIONS.includes(ext as (typeof ALLOWED_EXTENSIONS)[number])) {
    return 'Unsupported file type. Please upload a .csv, .xls, or .xlsx file.'
  }

  if (file.size === 0) {
    return 'The selected file is empty.'
  }

  return null
}

async function postFile(path: string, file: File): Promise<Response> {
  const form = new FormData()
  form.append('file', file)

  try {
    return await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      body: form,
    })
  } catch {
    throw new ApiError(
      `Unable to reach the DataLens API at ${API_BASE}. Check that the backend is running and allows this origin (CORS).`,
    )
  }
}

async function errorMessage(
  response: Response,
  fallback: string,
): Promise<string> {
  try {
    const data = await response.json()

    if (typeof data?.detail === 'string') {
      return data.detail
    }
  } catch {}

  return fallback
}

export async function analyzeFile(
  file: File,
): Promise<AnalysisResult> {
  const response = await postFile('/api/analyze', file)

  if (!response.ok) {
    throw new ApiError(
      await errorMessage(
        response,
        'Unable to analyze the dataset. Please try again.',
      ),
      response.status,
    )
  }

  let data: unknown

  try {
    data = await response.json()
  } catch {
    throw new ApiError('The API returned an invalid response.')
  }

  if (
    !data ||
    typeof data !== 'object' ||
    Array.isArray(data)
  ) {
    throw new ApiError('The API returned an invalid response.')
  }

  return data as AnalysisResult
}

const FORMAT_LABEL: Record<ReportFormat, string> = {
  pdf: 'PDF',
  xlsx: 'Excel',
  csv: 'CSV',
}

export async function downloadReport(
  file: File,
  format: ReportFormat,
): Promise<string> {
  const response = await postFile(
    `/api/report/${format}`,
    file,
  )

  if (!response.ok) {
    throw new ApiError(
      await errorMessage(
        response,
        `Unable to generate ${FORMAT_LABEL[format]} report.`,
      ),
      response.status,
    )
  }

  const blob = await response.blob()

  const disposition =
    response.headers.get('Content-Disposition') || ''

  const match = disposition.match(
    /filename="?([^";]+)"?/i,
  )

  const filename =
    match?.[1] || `DataLens_Analysis.${format}`

  const url = URL.createObjectURL(blob)

  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename

  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()

  setTimeout(() => URL.revokeObjectURL(url), 1000)

  return filename
}

export const downloadPdf = (file: File) =>
  downloadReport(file, 'pdf')

export const downloadExcel = (file: File) =>
  downloadReport(file, 'xlsx')

export const downloadCsv = (file: File) =>
  downloadReport(file, 'csv')
