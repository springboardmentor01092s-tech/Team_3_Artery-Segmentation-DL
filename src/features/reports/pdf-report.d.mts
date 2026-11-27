import type { ReportViewModel } from './report-data.mjs'

export type ReportJpegAsset = { jpeg: Uint8Array; width: number; height: number }
export declare function createReportPdf(report: ReportViewModel & { notes?: string }, assets?: {
  gradcam?: ReportJpegAsset
  localization?: ReportJpegAsset
}): Uint8Array
export declare function blobToJpegAsset(blob: Blob, quality?: number): Promise<ReportJpegAsset>
