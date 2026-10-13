// Mirrors the response of `analyze_dataframe` in the DataLens FastAPI backend
// (backend/app/analysis.py). Every field is treated as optional at render time.

export type CellValue = string | number | boolean | null

export interface Summary {
  rows: number
  columns: number
  missing_cells: number
  missing_percent: number
  /** Exact duplicates: every column identical. */
  duplicate_rows: number
  duplicate_percent: number
  exact_duplicate_groups?: number
  /** Repeated records when identifier columns are ignored (includes the exact ones). */
  duplicate_rows_ignoring_identifiers?: number
  duplicate_percent_ignoring_identifiers?: number
  duplicate_groups_total?: number
  duplicate_ignored_identifier_columns?: string[]
}

export interface ColumnInfo {
  name: string
  dtype: string
  kind: string
  semantic_type: string
  role: string
  missing: number
  missing_percent: number
  unique: number
  unique_ratio: number
  non_null: number
  identifier_score?: number
  numeric_ratio?: number
  date_ratio?: number
}

export interface StatisticRow {
  name: string
  min: CellValue
  max: CellValue
  mean: CellValue
  median: CellValue
  std: CellValue
}

export interface MissingInfo {
  name: string
  count: number
  percent: number
}

export interface PlotlyChart {
  title?: string
  /** Explanatory note, e.g. extreme values stretching a histogram. */
  note?: string
  data?: Array<Record<string, unknown>>
  layout?: Record<string, unknown>
}

export interface IssueRecord {
  row_number: number
  values: Record<string, CellValue>
  missing_columns?: string[]
}

export interface DuplicateGroup {
  group_id: number
  count: number
  duplicate_count: number
  row_numbers: number[]
  rows: IssueRecord[]
  /** 'exact': all columns identical; 'identifier_excluded': only identifier columns differ. */
  match_type?: 'exact' | 'identifier_excluded'
  original_row?: number
  differing_identifier_columns?: string[]
}

export interface DateAnalysisItem {
  name: string
  min: string | null
  max: string | null
  valid_count: number
  invalid_count: number
  missing_count?: number
  granularity?: string
}

export interface TypeInconsistency {
  name: string
  type: string
  summary?: string
  message?: string
  invalid_count?: number
  invalid_examples?: string[]
  [key: string]: unknown
}

export interface IdentifierDuplicate {
  column: string
  duplicate_values: Array<{ value: CellValue; count: number; row_numbers: number[] }>
  duplicate_occurrences: number
  unique_ratio?: number
}

export interface IdentifierAnomaly {
  type: string
  column: string
  message: string
  examples?: Array<CellValue>
  row_numbers?: number[]
}

export interface TextInconsistency {
  column: string
  message: string
  variant_count: number
  variant_groups: Array<{ variants: string[]; [key: string]: unknown }>
}

export interface PlaceholderValue {
  column: string
  count: number
  percent_of_column: number
  values: Array<{ value: string; count: number }>
  row_numbers: number[]
  message: string
}

export interface Finding {
  type: string
  text: string
}

export interface AnalysisResult {
  summary?: Summary
  columns?: ColumnInfo[]
  statistics?: StatisticRow[]
  missing?: MissingInfo[]
  charts?: PlotlyChart[]
  preview?: {
    columns?: string[]
    rows?: Array<Record<string, CellValue>>
  }
  issue_records?: {
    missing?: IssueRecord[]
    duplicates?: IssueRecord[]
  }
  duplicate_groups?: DuplicateGroup[]
  identifier_duplicates?: IdentifierDuplicate[]
  identifier_anomalies?: IdentifierAnomaly[]
  text_inconsistencies?: TextInconsistency[]
  placeholder_values?: PlaceholderValue[]
  profile?: {
    numerical_columns?: string[]
    categorical_columns?: string[]
    text_columns?: string[]
    date_columns?: string[]
    identifier_columns?: string[]
    constant_columns?: string[]
    high_cardinality_columns?: string[]
  }
  date_analysis?: DateAnalysisItem[]
  type_inconsistencies?: TypeInconsistency[]
  quality?: {
    major_issues?: number
    findings?: Finding[]
  }
  report?: {
    outliers?: Array<{ name: string; count: number }>
    inconsistent_columns?: string[]
    [key: string]: unknown
  }
}

export type ReportFormat = 'pdf' | 'xlsx' | 'csv'

export type SectionId =
  | 'profile'
  | 'statistics'
  | 'visualizations'
  | 'missing'
  | 'preview'
  | 'quality'
  | 'download'
