export function buildReportJson(report, { notes = '', generatedAt = new Date().toISOString() } = {}) {
  const runId = report.runId || null
  const artifactRef = (available, filename) => ({
    available: Boolean(available),
    artifact_name: filename,
    api_endpoint: available && runId
      ? `/api/v1/analysis-runs/${encodeURIComponent(runId)}/artifacts/${filename}`
      : null,
  })

  return {
    report_metadata: {
      format: 'artery-analysis-report',
      schema_version: 1,
      generated_at: generatedAt,
      title: 'Coronary Angiography Analysis Report',
    },
    patient: { subject_id: report.patientId === 'Unavailable' ? null : report.patientId },
    case: { case_id: report.caseId === 'Unavailable' ? null : report.caseId },
    image: { image_id: report.imageId === 'Unavailable' ? null : report.imageId },
    analysis: {
      run_id: runId,
      analysis_date: report.analysisDateIso,
      run_status: report.runStatusValue,
      predicted_candidate_count: report.predictedCandidateCount,
      estimated_narrowing_percent: report.candidateRows.length === 1 ? report.candidateRows[0].estimatedNarrowingPercent : null,
      severity: report.candidateRows.length === 1 ? report.candidateRows[0].severityValue : null,
      models: report.models,
      model_inference_times_seconds: report.modelTimes,
    },
    candidates: report.candidateRows.map((candidate) => ({
      candidate_id: candidate.candidateId,
      location: candidate.bbox ? {
        coordinate_system: 'original_image_pixel_grid',
        x: candidate.bbox[0],
        y: candidate.bbox[1],
        width: candidate.bbox[2],
        height: candidate.bbox[3],
      } : null,
      bounding_box_xywh: candidate.bbox,
      area_pixels: candidate.areaPixels,
      mean_probability: candidate.meanProbability,
      estimated_narrowing_percent: candidate.estimatedNarrowingPercent,
      severity: candidate.severityValue,
      status: candidate.status,
    })),
    visualizations: {
      // The protected backend artifact is the raw Grad-CAM map. The PDF's
      // colored overlay is generated client-side and is not a persisted file.
      gradcam_raw_map: artifactRef(report.gradcamAvailable, 'gradcam.png'),
      stenosis_candidate_localization: artifactRef(report.localizationAvailable, 'candidate_overlay.png'),
    },
    report_notes: notes.trim() ? notes : null,
  }
}

export const REPORT_CSV_HEADERS = [
  'Patient ID', 'Case ID', 'Image ID', 'Analysis Run ID', 'Analysis Date', 'Candidate ID',
  'Candidate Location', 'Bounding Box (x,y,width,height)', 'Candidate Area (pixels)',
  'Mean Probability', 'Estimated Narrowing (%)', 'Severity', 'Candidate Status',
]

function csvField(value) {
  if (value === null || value === undefined) return ''
  const text = String(value)
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text
}

export function buildReportCsv(report) {
  const rows = report.candidateRows.map((candidate) => [
    report.patientId === 'Unavailable' ? '' : report.patientId,
    report.caseId === 'Unavailable' ? '' : report.caseId,
    report.imageId === 'Unavailable' ? '' : report.imageId,
    report.runId,
    report.analysisDateIso,
    candidate.candidateId,
    candidate.location === 'Unavailable' ? '' : candidate.location,
    candidate.bbox ? candidate.bbox.join(',') : '',
    candidate.areaPixels,
    candidate.meanProbability,
    candidate.estimatedNarrowingPercent,
    candidate.severityValue,
    candidate.status === 'Unavailable' ? '' : candidate.status,
  ])
  return [REPORT_CSV_HEADERS, ...rows].map((row) => row.map(csvField).join(',')).join('\r\n') + '\r\n'
}

/** Notify only after the browser download dispatch succeeds. */
export function dispatchReportDownload({ format, filename, blob, download, notify }) {
  download(blob, filename)
  notify({ format, filename })
}
