const activeStatuses = new Set(['queued', 'processing', 'running'])

function timestamp(value) {
  const result = value ? new Date(value).getTime() : Number.NaN
  return Number.isFinite(result) ? result : 0
}

export function caseAnalysisStatus(runs = []) {
  if (runs.some((run) => run.status === 'completed')) return 'completed'
  if (runs.some((run) => activeStatuses.has(run.status))) return 'in_progress'
  if (runs.some((run) => run.status === 'failed')) return 'failed'
  return 'pending'
}

export function buildDashboardData({ cases, patients, imagesByCase, runsByCase }) {
  const patientById = new Map(patients.map((patient) => [patient.id, patient]))
  const allImages = Object.values(imagesByCase).flat()
  const allRuns = Object.entries(runsByCase).flatMap(([caseId, runs]) => {
    const caseRecord = cases.find((item) => item.id === caseId)
    return runs.map((run) => ({ ...run, case_id: caseId, case_ref: caseRecord?.case_ref ?? 'Case reference unavailable' }))
  })
  const caseStatuses = cases.map((record) => ({
    case: record,
    status: caseAnalysisStatus(runsByCase[record.id] ?? []),
  }))
  const statusCounts = {
    completed: caseStatuses.filter((item) => item.status === 'completed').length,
    in_progress: caseStatuses.filter((item) => item.status === 'in_progress').length,
    failed: caseStatuses.filter((item) => item.status === 'failed').length,
    pending: caseStatuses.filter((item) => item.status === 'pending').length,
  }
  const caseRefById = new Map(cases.map((record) => [record.id, record.case_ref]))
  const recentCases = [...cases]
    .sort((a, b) => timestamp(b.created_at) - timestamp(a.created_at))
    .slice(0, 5)
    .map((record) => ({ ...record, patient_ref: patientById.get(record.patient_id)?.patient_ref ?? 'Patient reference unavailable' }))
  const recentAnalyses = [...allRuns]
    .sort((a, b) => timestamp(b.created_at) - timestamp(a.created_at))
    .slice(0, 5)
    .map((run) => ({ ...run, case_ref: caseRefById.get(run.case_id) ?? run.case_ref }))
  const recentActivity = [
    ...cases.map((record) => ({
      id: `case-${record.id}`, kind: 'case', title: 'Case created', detail: record.case_ref,
      created_at: record.created_at,
    })),
    ...allImages.map((image) => ({
      id: `image-${image.id}`, kind: 'image', title: 'Image uploaded',
      detail: `${image.original_filename} · ${caseRefById.get(image.case_id) ?? 'Case reference unavailable'}`,
      created_at: image.created_at,
    })),
    ...allRuns.map((run) => ({
      id: `run-${run.id}`, kind: 'analysis', title: `Analysis ${run.status.replaceAll('_', ' ')}`,
      detail: `${run.case_ref} · ${run.image_id ? `Image ${run.image_id.slice(0, 8)}` : 'Image unavailable'}`,
      created_at: run.completed_at ?? run.started_at ?? run.created_at,
    })),
  ].sort((a, b) => timestamp(b.created_at) - timestamp(a.created_at)).slice(0, 6)

  return {
    summary: {
      cases: cases.length,
      images: allImages.length,
      analysesCompleted: allRuns.filter((run) => run.status === 'completed').length,
      analysesInProgress: allRuns.filter((run) => activeStatuses.has(run.status)).length,
    },
    statusCounts,
    recentCases,
    recentAnalyses,
    recentActivity,
  }
}

export async function loadDashboardData(request) {
  const [cases, patients] = await Promise.all([
    request('/cases'),
    request('/patients'),
  ])
  const imagesByCase = {}
  const runsByCase = {}
  let nextIndex = 0
  const worker = async () => {
    while (nextIndex < cases.length) {
      const record = cases[nextIndex++]
      const encoded = encodeURIComponent(record.id)
      const [images, runs] = await Promise.all([
        request(`/cases/${encoded}/images`),
        request(`/cases/${encoded}/analysis-runs`),
      ])
      imagesByCase[record.id] = images
      runsByCase[record.id] = runs
    }
  }
  await Promise.all(Array.from({ length: Math.min(6, cases.length) }, worker))
  return buildDashboardData({ cases, patients, imagesByCase, runsByCase })
}
