import type { AnalysisRunResponse, AnalysisResultsResponse } from './contracts.mjs'

export function getComparisonRunOptions(runs: AnalysisRunResponse[], runAId?: string): AnalysisRunResponse[]
export function validateComparisonSelection(
  runA: AnalysisRunResponse | undefined,
  runB: AnalysisRunResponse | undefined,
): { valid: boolean; reason: string }
export function getRunComparisonSummary(
  run: AnalysisRunResponse,
  result: AnalysisResultsResponse | null,
): {
  status: string
  date: string
  duration: string
  durationSeconds: number | null
  candidateCount: number | null
  narrowing: string
  severity: string
  models: string
}
export function getComparisonDifferences(
  summaryA: ReturnType<typeof getRunComparisonSummary>,
  summaryB: ReturnType<typeof getRunComparisonSummary>,
): { duration: string; candidateCount: string }
