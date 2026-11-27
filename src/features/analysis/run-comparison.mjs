const isFiniteNumber = (value) => typeof value === 'number' && Number.isFinite(value)

export function getComparisonRunOptions(runs, runAId = '') {
  const eligible = runs.filter((run) => typeof run.image_id === 'string' && run.image_id)
  if (!runAId) return eligible
  const runA = eligible.find((run) => run.id === runAId)
  if (!runA) return []
  return eligible.filter((run) => run.id !== runA.id && run.image_id === runA.image_id)
}

export function validateComparisonSelection(runA, runB) {
  if (!runA || !runB) return { valid: false, reason: 'Select two saved analysis runs to compare.' }
  if (runA.id === runB.id) return { valid: false, reason: 'Select two different analysis runs.' }
  if (!runA.image_id || !runB.image_id) return { valid: false, reason: 'Both runs must have a saved source image.' }
  if (runA.image_id !== runB.image_id) return { valid: false, reason: 'Runs can only be compared when their persisted image IDs match.' }
  return { valid: true, reason: '' }
}

function formatTimestamp(value) {
  if (typeof value !== 'string' || !value) return 'Not available'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Not available' : date.toLocaleString()
}

function formatCandidateMetadata(metadata, key, formatValue) {
  const measurements = metadata?.[key]?.measurements
  if (!Array.isArray(measurements)) return 'Not available'
  const available = measurements.filter((item) => item?.status === 'available' && formatValue(item) !== null)
  if (!available.length) return 'Not available'
  return available.map((item) => `Predicted candidate ${item.candidate_id}: ${formatValue(item)}`).join('; ')
}

function formatModels(metadata) {
  const models = metadata?.models
  if (!models || typeof models !== 'object') return 'Not available'
  const entries = ['attention_unet', 'unetpp'].flatMap((key) => {
    const model = models[key]
    if (!model || typeof model !== 'object') return []
    const name = [model.model_id, model.architecture, model.encoder].filter((value) => typeof value === 'string' && value).join(' · ')
    const threshold = isFiniteNumber(model.threshold) ? `threshold ${model.threshold}` : ''
    const checkpoint = typeof model.checkpoint === 'string' && model.checkpoint ? `checkpoint ${model.checkpoint}` : ''
    const details = [name || key, checkpoint, threshold].filter(Boolean).join(' · ')
    return [details]
  })
  return entries.length ? entries.join('; ') : 'Not available'
}

export function getRunComparisonSummary(run, result) {
  const metadata = result?.metadata ?? run?.result_metadata ?? null
  const candidates = metadata?.candidates
  const candidateCount = Array.isArray(candidates)
    ? candidates.length
    : isFiniteNumber(metadata?.models?.candidate_count) ? metadata.models.candidate_count : null
  const duration = isFiniteNumber(run?.duration_seconds) ? `${run.duration_seconds.toFixed(2)} s` : 'Not available'
  const narrowing = formatCandidateMetadata(metadata, 'percentage_narrowing', (item) =>
    isFiniteNumber(item.estimated_narrowing_percent) ? `${item.estimated_narrowing_percent.toFixed(1)}% (experimental)` : null)
  const severity = formatCandidateMetadata(metadata, 'severity_assessment', (item) =>
    typeof item.severity === 'string' && item.severity ? `${item.severity} (experimental)` : null)

  return {
    status: run?.status ?? 'Not available',
    date: formatTimestamp(run?.created_at),
    duration,
    durationSeconds: isFiniteNumber(run?.duration_seconds) ? run.duration_seconds : null,
    candidateCount,
    narrowing,
    severity,
    models: formatModels(metadata),
  }
}

export function getComparisonDifferences(summaryA, summaryB) {
  const durationDelta = summaryA.durationSeconds !== null && summaryB.durationSeconds !== null
    ? `${(summaryB.durationSeconds - summaryA.durationSeconds >= 0 ? '+' : '')}${(summaryB.durationSeconds - summaryA.durationSeconds).toFixed(2)} s (Run B − Run A)`
    : 'Not available'
  const countDelta = summaryA.candidateCount !== null && summaryB.candidateCount !== null
    ? `${summaryB.candidateCount - summaryA.candidateCount >= 0 ? '+' : ''}${summaryB.candidateCount - summaryA.candidateCount} (Run B − Run A)`
    : 'Not available'
  return { duration: durationDelta, candidateCount: countDelta }
}
