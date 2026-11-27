const severities = new Set(['Normal', 'Mild', 'Moderate', 'Critical'])
const modelFields = [
  'model_id', 'model_version', 'version', 'architecture', 'encoder', 'device', 'input_size',
  'input_channel_format', 'input_dtype', 'input_normalization', 'resize', 'threshold', 'threshold_is_provisional',
]

export const REPORT_CONTENTS = [
  'Patient and case information',
  'Analysis overview',
  'Candidate-level findings',
  'AI visualizations (Grad-CAM and stenosis bounding-box localization)',
  'Report Notes',
]

function formatDate(value) {
  if (!value) return 'Unavailable'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Unavailable'
  return new Intl.DateTimeFormat('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC',
  }).format(date)
}

function availablePercentage(measurement) {
  const value = measurement?.estimated_narrowing_percent
  return measurement?.status === 'available' && typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 100
    ? value
    : null
}

function safeModelDetails(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  const details = {}
  for (const field of modelFields) {
    const item = value[field]
    if (typeof item === 'string' || typeof item === 'boolean' || (typeof item === 'number' && Number.isFinite(item))) {
      details[field] = item
    } else if (field === 'input_size' && Array.isArray(item) && item.every((part) => Number.isFinite(part))) {
      details[field] = item.slice(0, 2)
    }
  }
  return Object.keys(details).length ? details : null
}

function formatModelLine(title, details) {
  if (!details) return null
  const modelName = details.model_id ?? details.architecture
  const encoder = details.encoder ? `, encoder ${details.encoder}` : ''
  const inputSize = Array.isArray(details.input_size) ? `, input ${details.input_size.join('x')}` : ''
  const threshold = typeof details.threshold === 'number' ? `, threshold ${details.threshold}` : ''
  const device = details.device ? `, device ${details.device}` : ''
  return `${title}: ${modelName ?? 'configured model'}${encoder}${inputSize}${threshold}${device}`
}

export function buildReportViewModel({ patient, caseRecord, run, results }) {
  const sameRun = Boolean(run && results && results.run_id === run.id
    && (results.status !== 'completed' || results.image_id === run.image_id))
  const metadata = sameRun && results.status === 'completed' ? results.metadata : null
  const candidates = Array.isArray(metadata?.candidates) ? metadata.candidates : null
  const narrowingMeasurements = Array.isArray(metadata?.percentage_narrowing?.measurements)
    ? metadata.percentage_narrowing.measurements
    : []
  const severityMeasurements = Array.isArray(metadata?.severity_assessment?.measurements)
    ? metadata.severity_assessment.measurements
    : []

  const candidateRows = (candidates ?? []).map((candidate) => {
    const narrowing = narrowingMeasurements.filter((item) => item?.candidate_id === candidate?.candidate_id)
    const severity = severityMeasurements.filter((item) => item?.candidate_id === candidate?.candidate_id)
    const narrowingMeasurement = narrowing.length === 1 ? narrowing[0] : null
    const severityMeasurement = severity.length === 1 ? severity[0] : null
    const percentage = availablePercentage(narrowingMeasurement)
    const severityLabel = severityMeasurement?.status === 'available'
      && severities.has(severityMeasurement.severity)
      && severityMeasurement.source_narrowing_percent === percentage
      ? severityMeasurement.severity
      : null
    const [x, y, width, height] = Array.isArray(candidate?.bbox) ? candidate.bbox : []
    const bbox = [x, y, width, height].every((value) => typeof value === 'number' && Number.isFinite(value))
      ? [x, y, width, height]
      : null
    const areaPixels = typeof candidate?.area_pixels === 'number' && Number.isFinite(candidate.area_pixels) ? candidate.area_pixels : null
    const meanProbability = typeof candidate?.mean_probability === 'number' && Number.isFinite(candidate.mean_probability) ? candidate.mean_probability : null

    return {
      candidateId: Number.isInteger(candidate?.candidate_id) ? candidate.candidate_id : null,
      candidate: Number.isInteger(candidate?.candidate_id) ? `Candidate ${String(candidate.candidate_id).padStart(2, '0')}` : 'Unavailable',
      location: bbox ? `x ${x}, y ${y}; ${width}x${height} px` : 'Unavailable',
      bbox,
      areaPixels,
      meanProbability,
      narrowing: percentage === null ? 'Unavailable' : `${percentage.toFixed(1)}%`,
      estimatedNarrowingPercent: percentage,
      severity: severityLabel ?? 'Unavailable',
      severityValue: severityLabel,
      status: percentage === null ? 'Unavailable' : 'Experimental estimate',
      percentage,
    }
  })

  const singleCandidateValue = (field) => {
    if (candidateRows.length === 1) return candidateRows[0][field]
    if (candidateRows.length > 1) return 'See candidate findings'
    return 'Unavailable'
  }

  const caseMatchesRun = Boolean(run && caseRecord && caseRecord.id === run.case_id)
  const patientMatchesCase = Boolean(patient && caseMatchesRun && patient.id === caseRecord.patient_id)
  const gradcamUrl = sameRun && metadata?.models?.gradcam_available === true
    ? results?.artifacts?.['gradcam.png'] ?? null
    : null
  const localizationUrl = sameRun ? results?.artifacts?.['candidate_overlay.png'] ?? null : null
  const sourceModels = metadata?.models && typeof metadata.models === 'object' ? metadata.models : {}
  const models = {
    artery_segmentation: safeModelDetails(sourceModels.attention_unet),
    stenosis_segmentation: safeModelDetails(sourceModels.unetpp),
  }
  const modelInformation = [
    formatModelLine('Artery segmentation', models.artery_segmentation),
    formatModelLine('Stenosis segmentation', models.stenosis_segmentation),
  ].filter(Boolean)
  const modelTimes = metadata?.model_times && typeof metadata.model_times === 'object'
    ? Object.fromEntries(Object.entries(metadata.model_times).filter(([, value]) => typeof value === 'number' && Number.isFinite(value)))
    : {}

  const rawStatus = run?.status ? String(run.status).replaceAll('_', ' ') : 'Unavailable'
  const runStatus = rawStatus.charAt(0).toUpperCase() + rawStatus.slice(1)

  return {
    runId: run?.id ?? '',
    patientId: patientMatchesCase ? patient.patient_ref : 'Unavailable',
    caseId: caseMatchesRun ? caseRecord.case_ref : 'Unavailable',
    imageId: sameRun && typeof run?.image_id === 'string' ? run.image_id : 'Unavailable',
    analysisDate: formatDate(run?.completed_at ?? run?.created_at),
    analysisDateIso: run?.completed_at ?? run?.created_at ?? null,
    runStatus,
    runStatusValue: run?.status ?? null,
    predictedCandidates: candidates ? String(candidates.length) : 'Unavailable',
    predictedCandidateCount: candidates ? candidates.length : null,
    estimatedNarrowing: singleCandidateValue('narrowing'),
    severity: singleCandidateValue('severity'),
    candidateRows,
    hasCandidateRecords: candidates !== null,
    models,
    modelInformation,
    modelTimes,
    gradcamUrl,
    localizationUrl,
    gradcamAvailable: Boolean(gradcamUrl),
    localizationAvailable: Boolean(localizationUrl),
  }
}

