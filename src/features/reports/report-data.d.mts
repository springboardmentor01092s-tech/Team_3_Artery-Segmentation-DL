export type ReportCandidateRow = {
  candidateId: number | null
  candidate: string
  location: string
  bbox: [number, number, number, number] | null
  areaPixels: number | null
  meanProbability: number | null
  narrowing: string
  estimatedNarrowingPercent: number | null
  severity: string
  severityValue: string | null
  status: string
  percentage: number | null
}

export type ReportViewModel = {
  runId: string
  patientId: string
  caseId: string
  imageId: string
  analysisDate: string
  analysisDateIso: string | null
  runStatus: string
  runStatusValue: string | null
  predictedCandidates: string
  predictedCandidateCount: number | null
  estimatedNarrowing: string
  severity: string
  candidateRows: ReportCandidateRow[]
  hasCandidateRecords: boolean
  models: {
    artery_segmentation: Record<string, string | number | boolean | number[]> | null
    stenosis_segmentation: Record<string, string | number | boolean | number[]> | null
  }
  modelInformation: string[]
  modelTimes: Record<string, number>
  gradcamUrl: string | null
  localizationUrl: string | null
  gradcamAvailable: boolean
  localizationAvailable: boolean
}

export declare const REPORT_CONTENTS: readonly string[]

export declare function buildReportViewModel(input: {
  patient: { id: string; patient_ref: string } | null
  caseRecord: { id: string; case_ref: string; patient_id: string } | null
  run: { id: string; case_id: string; image_id: string | null; status: string; created_at: string; completed_at?: string | null } | null
  results: {
    run_id: string
    status: string
    image_id?: string | null
    metadata?: {
      candidates?: Array<{ candidate_id: number; bbox: number[] }>
      percentage_narrowing?: { measurements?: Array<{ candidate_id: number; status: string; estimated_narrowing_percent?: number }> }
      severity_assessment?: { measurements?: Array<{ candidate_id: number; status: string; severity?: string; source_narrowing_percent?: number }> }
      models?: { gradcam_available?: boolean }
    }
    artifacts?: Record<string, string>
  } | null
}): ReportViewModel
