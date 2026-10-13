import {
  BarChart3,
  CalendarRange,
  Copy,
  FileDown,
  Fingerprint,
  ScanSearch,
  SquareDashed,
  type LucideIcon,
} from 'lucide-react'
import { Panel } from './primitives'

const FEATURES: { icon: LucideIcon; title: string; text: string }[] = [
  { icon: Fingerprint, title: 'Semantic column profiling', text: 'Detects measures, categories, identifiers, dates and free text, not just raw dtypes.' },
  { icon: SquareDashed, title: 'Missing value analysis', text: 'Per-column missing counts plus the exact records affected, with original row numbers.' },
  { icon: Copy, title: 'Duplicate detection', text: 'Groups identical records together so you can see the original and every copy.' },
  { icon: CalendarRange, title: 'Date & type checks', text: 'Validates date ranges and flags columns whose values do not match their inferred type.' },
  { icon: BarChart3, title: 'Interactive charts', text: 'Distributions, box plots, category frequencies and time trends rendered with Plotly.' },
  { icon: FileDown, title: 'Exportable reports', text: 'Download the full analysis as a formatted PDF, a multi-sheet Excel workbook or CSV.' },
]

const STEPS = ['Upload a .csv, .xls or .xlsx file (up to 10MB).', 'The FastAPI backend parses and profiles every column.', 'Explore metrics, charts and quality findings.', 'Download a report in your preferred format.']

export function ProjectInformation() {
  return (
    <div className="flex flex-col gap-8 animate-section-in">
      <section className="relative overflow-hidden rounded-3xl border bg-surface px-6 py-12 sm:px-10">
        <div className="bg-grid absolute inset-0 [mask-image:radial-gradient(ellipse_at_top_left,black,transparent_70%)]" aria-hidden />
        <div className="relative flex max-w-2xl flex-col gap-4">
          <span className="flex size-12 items-center justify-center rounded-2xl bg-gradient-to-br from-primary to-info text-primary-foreground shadow-lg shadow-primary/25">
            <ScanSearch className="size-6" aria-hidden />
          </span>
          <h1 className="text-balance text-3xl font-semibold tracking-tight sm:text-4xl">About DataLens</h1>
          <p className="text-pretty leading-relaxed text-muted-foreground">
            DataLens is an automated data quality analyzer. It turns a raw spreadsheet into a clear picture of
            structure, completeness and consistency, so you can trust your data before you build on it.
          </p>
        </div>
      </section>

      <section aria-labelledby="features-title" className="flex flex-col gap-4">
        <h2 id="features-title" className="text-xl font-semibold tracking-tight">What it checks</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(({ icon: Icon, title, text }) => (
            <Panel key={title} className="p-5 transition-all duration-300 hover:-translate-y-0.5 hover:border-primary/40">
              <span className="flex size-10 items-center justify-center rounded-xl bg-accent text-accent-foreground">
                <Icon className="size-5" aria-hidden />
              </span>
              <h3 className="mt-4 font-medium">{title}</h3>
              <p className="mt-1 text-pretty text-sm leading-relaxed text-muted-foreground">{text}</p>
            </Panel>
          ))}
        </div>
      </section>

      <div className="grid gap-4">
        <Panel className="p-6">
          <h2 className="font-semibold">How it works</h2>
          <ol className="mt-4 flex flex-col gap-3">
            {STEPS.map((step, i) => (
              <li key={step} className="flex items-start gap-3 text-sm">
                <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
                  {i + 1}
                </span>
                <span className="pt-0.5 text-muted-foreground">{step}</span>
              </li>
            ))}
          </ol>
        </Panel>
      </div>

      <section aria-labelledby="developer-title" className="flex flex-col gap-4">
        <h2 id="developer-title" className="text-xl font-semibold tracking-tight">Developer</h2>
        <Panel className="flex flex-col gap-3 p-6">
          <p className="font-medium">Tarun Chand</p>
          <div className="flex flex-wrap gap-x-4 gap-y-2 text-sm">
            <a href="mailto:chandtarun1234@gmail.com" className="text-primary underline-offset-4 hover:underline">Email</a>
            <a href="https://www.linkedin.com/in/chand-tarun" target="_blank" rel="noreferrer" className="text-primary underline-offset-4 hover:underline">LinkedIn</a>
            <a href="https://github.com/chandtarun10" target="_blank" rel="noreferrer" className="text-primary underline-offset-4 hover:underline">GitHub</a>
          </div>
        </Panel>
      </section>

    </div>
  )
}
