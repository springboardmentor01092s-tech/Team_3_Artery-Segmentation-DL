export type AnalysisRunStatus = 'unavailable' | 'queued' | 'processing' | 'completed' | 'failed'

export type AnalysisRunResponse = {
  id: string
  case_id: string
  image_id: string | null
  status: AnalysisRunStatus
  created_at: string
  completed_at?: string | null
  duration_seconds: number | null
  failure_message: string | null
  result_metadata?: AnalysisResultMetadata | null
}

export type AnalysisCandidate = {
  candidate_id: number
  label: string
  bbox: [number, number, number, number]
  centroid: [number, number]
  area_pixels: number
  mean_probability: number
  measurement_grid: string
}

export type PercentageNarrowingMeasurement = {
  candidate_id: number
  label?: string
  status: 'available' | 'unavailable'
  reference_predicted_mask_width_px?: number
  minimum_candidate_predicted_mask_width_px?: number
  estimated_narrowing_percent?: number
  association?: string
  unavailable_reason?: string
}

export type PercentageNarrowingResult = {
  algorithm_version: string
  status: 'available' | 'partial' | 'unavailable'
  coordinate_system: 'original_image_pixel_grid'
  measurement_unit: 'pixel'
  disclaimer: string
  measurements: PercentageNarrowingMeasurement[]
  unavailable_reason?: string | null
  limitations?: string[]
  source_model_ids?: Record<string, string>
  source_thresholds?: Record<string, number>
  quality_parameters?: Record<string, number>
}

export type SeverityAssessmentMeasurement = {
  candidate_id: number
  status: 'available' | 'unavailable' | 'invalid'
  severity?: 'Normal' | 'Mild' | 'Moderate' | 'Critical'
  source_narrowing_percent?: number
  reason?: string
}

export type SeverityAssessmentResult = {
  algorithm_version: string
  threshold_source: 'user_specified_experimental_project_rules'
  status: 'available' | 'partial' | 'unavailable'
  thresholds: Array<{
    severity: 'Normal' | 'Mild' | 'Moderate' | 'Critical'
    minimum: number
    maximum: number
    minimum_inclusive: boolean
    maximum_inclusive: boolean
  }>
  measurements: SeverityAssessmentMeasurement[]
  unavailable_reason?: string | null
  invalid_measurement_count: number
}

export type AnalysisResultMetadata = {
  schema_version: number
  models: {
    attention_unet?: Record<string, unknown>
    unetpp?: Record<string, unknown>
    gradcam_available?: boolean
    gradcam_unavailable_reason?: string
    candidate_count?: number
    clinical_validation?: boolean
    clinical_measurements_generated?: boolean
    [key: string]: unknown
  }
  model_times: Record<string, number>
  original_size: [number, number]
  candidate_label: string
  candidates: AnalysisCandidate[]
  percentage_narrowing?: PercentageNarrowingResult
  severity_assessment?: SeverityAssessmentResult
  clinical_measurements_generated: boolean
  clinical_validation: boolean
}

export type AnalysisResultsResponse = {
  run_id: string
  status: AnalysisRunStatus
  image_id?: string | null
  source_image_url?: string | null
  detail?: string | null
  metadata?: AnalysisResultMetadata
  artifacts?: Record<string, string>
}

export type AnalysisImageResource = {
  key: 'original_image' | 'artery_mask.png' | 'stenosis_mask.png' | 'candidate_overlay.png' | 'combined_visualization.png' | 'gradcam.png' | 'candidates.json'
  label: string
  url: string
  kind: 'image' | 'json'
}

export declare function buildAnalysisRunRequest(caseId: string, imageId: string): {
  path: string
  init: RequestInit
}

export declare function caseAnalysisRunsPath(caseId: string): string
export declare function getAnalysisImageResources(result: AnalysisResultsResponse): AnalysisImageResource[]
export type GradCAMDisplayState = { status: 'not_ready' } | { status: 'available' } | { status: 'unavailable'; reason: string }
export declare function getGradCAMDisplayState(result: AnalysisResultsResponse, resources: AnalysisImageResource[]): GradCAMDisplayState
export type PercentageNarrowingDisplayState =
  | { status: 'not_ready' | 'not_calculated' }
  | { status: 'invalid'; reason: string }
  | { status: 'available' | 'partial' | 'unavailable'; metadata: PercentageNarrowingResult }
export declare function getPercentageNarrowingDisplayState(result: AnalysisResultsResponse): PercentageNarrowingDisplayState
export declare function toApiRequestPath(resourceUrl: string, origin: string): string | null
