import type { ReportViewModel } from './report-data.mjs'

export declare const REPORT_CSV_HEADERS: readonly string[]

export declare function buildReportJson(
  report: ReportViewModel,
  options?: { notes?: string; generatedAt?: string },
): Record<string, unknown>

export declare function buildReportCsv(report: ReportViewModel): string

export declare function dispatchReportDownload(input: {
  format: 'PDF' | 'JSON' | 'CSV'
  filename: string
  blob: Blob
  download: (blob: Blob, filename: string) => void
  notify: (notification: { format: 'PDF' | 'JSON' | 'CSV'; filename: string }) => void
}): void
