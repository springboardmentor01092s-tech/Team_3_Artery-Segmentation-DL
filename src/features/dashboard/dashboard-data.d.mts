export type DashboardRun = {
  id: string
  case_id?: string
  image_id: string | null
  status: string
  created_at: string
  started_at?: string | null
  completed_at?: string | null
}

export declare function caseAnalysisStatus(runs?: DashboardRun[]): 'completed' | 'in_progress' | 'failed' | 'pending'
export declare function buildDashboardData(input: {
  cases: Array<{ id: string; case_ref: string; patient_id: string; created_at: string }>
  patients: Array<{ id: string; patient_ref: string }>
  imagesByCase: Record<string, Array<{ id: string; case_id: string; original_filename: string; created_at: string }>>
  runsByCase: Record<string, DashboardRun[]>
}): {
  summary: { cases: number; images: number; analysesCompleted: number; analysesInProgress: number }
  statusCounts: { completed: number; in_progress: number; failed: number; pending: number }
  recentCases: Array<{ id: string; case_ref: string; patient_ref: string; created_at: string }>
  recentAnalyses: Array<DashboardRun & { case_ref: string }>
  recentActivity: Array<{ id: string; kind: string; title: string; detail: string; created_at: string }>
}

export type DashboardData = ReturnType<typeof buildDashboardData>
export declare function loadDashboardData(request: <T>(path: string) => Promise<T>): Promise<DashboardData>
