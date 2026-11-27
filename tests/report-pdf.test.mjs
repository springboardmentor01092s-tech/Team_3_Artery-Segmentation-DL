import test from 'node:test'
import assert from 'node:assert/strict'
import { buildReportViewModel } from '../src/features/reports/report-data.mjs'
import { createReportPdf } from '../src/features/reports/pdf-report.mjs'
import { buildReportCsv, buildReportJson } from '../src/features/reports/report-exports.mjs'

function completedRun(overrides = {}) {
  const run = {
    id: 'run-1', case_id: 'case-1', image_id: 'image-1', status: 'completed',
    created_at: '2026-11-14T12:00:00Z', completed_at: '2026-11-14T12:01:00Z',
    ...overrides,
  }
  const results = {
    run_id: run.id, image_id: run.image_id, status: 'completed',
    metadata: {
      models: { gradcam_available: true },
      candidates: [{ candidate_id: 1, bbox: [10, 20, 30, 40] }],
      percentage_narrowing: { measurements: [{ candidate_id: 1, status: 'available', estimated_narrowing_percent: 45.1 }] },
      severity_assessment: { measurements: [{ candidate_id: 1, status: 'available', severity: 'Mild', source_narrowing_percent: 45.1 }] },
    },
    artifacts: {
      'gradcam.png': '/api/v1/analysis-runs/run-1/artifacts/gradcam.png',
      'candidate_overlay.png': '/api/v1/analysis-runs/run-1/artifacts/candidate_overlay.png',
    },
  }
  return { run, results }
}

test('empty initial Reports state renders unavailable values without throwing', () => {
  const report = buildReportViewModel({ patient: null, caseRecord: null, run: null, results: null })

  assert.equal(report.patientId, 'Unavailable')
  assert.equal(report.caseId, 'Unavailable')
  assert.equal(report.imageId, 'Unavailable')
  assert.equal(report.runStatus, 'Unavailable')
  assert.equal(report.predictedCandidates, 'Unavailable')
  assert.equal(report.gradcamAvailable, false)
  assert.equal(report.localizationAvailable, false)
})

test('report data uses saved candidate findings and same-run visualization artifacts', () => {
  const { run, results } = completedRun()
  const report = buildReportViewModel({
    patient: { id: 'patient-1', patient_ref: 'SUBJECT-1' },
    caseRecord: { id: 'case-1', case_ref: 'CASE-1', patient_id: 'patient-1' },
    run,
    results,
  })

  assert.equal(report.patientId, 'SUBJECT-1')
  assert.equal(report.caseId, 'CASE-1')
  assert.equal(report.imageId, 'image-1')
  assert.equal(report.predictedCandidates, '1')
  assert.equal(report.estimatedNarrowing, '45.1%')
  assert.equal(report.severity, 'Mild')
  assert.equal(report.candidateRows[0].location, 'x 10, y 20; 30x40 px')
  assert.equal(report.gradcamAvailable, true)
  assert.equal(report.localizationAvailable, true)
})

test('missing results and artifacts stay explicitly unavailable in the generated PDF', () => {
  const { run, results } = completedRun()
  const missing = {
    ...results,
    metadata: { models: { gradcam_available: false }, candidates: [] },
    artifacts: {},
  }
  const report = buildReportViewModel({
    patient: { id: 'patient-1', patient_ref: 'SUBJECT-1' },
    caseRecord: { id: 'case-1', case_ref: 'CASE-1', patient_id: 'patient-1' },
    run,
    results: missing,
  })
  assert.equal(report.gradcamAvailable, false)
  assert.equal(report.localizationAvailable, false)
  assert.equal(report.predictedCandidates, '0')
  assert.equal(report.estimatedNarrowing, 'Unavailable')
  assert.equal(report.severity, 'Unavailable')

  const pdf = createReportPdf(report)
  const output = new TextDecoder().decode(pdf)
  assert.ok(output.startsWith('%PDF-1.4'))
  assert.match(output, /Coronary Angiography/)
  assert.match(output, /3\. AI visualizations/)
  assert.match(output, /Unavailable/)
  assert.match(output, /Grad-CAM overlay/)
  assert.match(output, /Stenosis candidate bounding box/)
  assert.match(output, /\/Count 1/)
  assert.match(output, /startxref\n\d+\n%%EOF/)
})

test('saved candidate narrowing and severity are associated by candidate ID', () => {
  const { run, results } = completedRun()
  const report = buildReportViewModel({
    patient: { id: 'patient-1', patient_ref: 'SUBJECT-1' },
    caseRecord: { id: 'case-1', case_ref: 'CASE-1', patient_id: 'patient-1' },
    run,
    results: {
      ...results,
      metadata: {
        ...results.metadata,
        candidates: [
          { candidate_id: 2, bbox: [1, 2, 3, 4] },
          { candidate_id: 1, bbox: [5, 6, 7, 8] },
        ],
      },
    },
  })
  assert.equal(report.candidateRows[0].narrowing, 'Unavailable')
  assert.equal(report.candidateRows[0].severity, 'Unavailable')
  assert.equal(report.candidateRows[1].narrowing, '45.1%')
  assert.equal(report.candidateRows[1].severity, 'Mild')
})

test('candidate findings paginate instead of being dropped from the report', () => {
  const { run, results } = completedRun()
  const candidates = Array.from({ length: 9 }, (_, index) => ({ candidate_id: index + 1, bbox: [1, 2, 3, 4] }))
  const report = buildReportViewModel({
    patient: { id: 'patient-1', patient_ref: 'SUBJECT-1' },
    caseRecord: { id: 'case-1', case_ref: 'CASE-1', patient_id: 'patient-1' },
    run,
    results: { ...results, metadata: { ...results.metadata, candidates } },
  })
  const pdf = new TextDecoder().decode(createReportPdf(report))
  assert.match(pdf, /\/Count 2/)
  assert.match(pdf, /Candidate 09/)
})

test('PDF includes current notes after the visualizations section', () => {
  const { run, results } = completedRun()
  const report = buildReportViewModel({ patient: null, caseRecord: null, run, results })
  const pdf = new TextDecoder().decode(createReportPdf({ ...report, notes: 'Review for follow-up.\nSecond note line.' }))
  assert.ok(pdf.indexOf('3. AI visualizations') < pdf.indexOf('4. Report Notes'))
  assert.doesNotMatch(pdf, /Model and analysis information|Artery segmentation:|Stenosis segmentation:|ResNet34|threshold|device/i)
  assert.match(pdf, /Review for follow-up\./)
  assert.match(pdf, /Second note line\./)
})

test('empty, null, and whitespace-only notes omit the section and add no page', () => {
  const { run, results } = completedRun()
  const report = buildReportViewModel({ patient: null, caseRecord: null, run, results })
  const twoPageReport = { ...report, candidateRows: Array.from({ length: 9 }, (_, index) => ({
    candidate: `Candidate ${index + 1}`,
    location: 'Unavailable', narrowing: 'Unavailable', severity: 'Unavailable', status: 'Unavailable',
  })) }

  for (const notes of ['', null, ' \n\t  ']) {
    const pdf = new TextDecoder().decode(createReportPdf({ ...twoPageReport, notes }))
    assert.match(pdf, /\/Count 2/)
    assert.doesNotMatch(pdf, /4\. Report Notes/)
    assert.match(pdf, /Page 1 of 2/)
    assert.match(pdf, /Page 2 of 2/)
    assert.doesNotMatch(pdf, /Page 3 of/)
  }
})

test('footer numbering uses the document-wide page index and computed total', () => {
  const { run, results } = completedRun()
  const report = buildReportViewModel({ patient: null, caseRecord: null, run, results })
  const candidateRows = Array.from({ length: 9 }, (_, index) => ({
    candidate: `Candidate ${index + 1}`,
    location: 'Unavailable', narrowing: 'Unavailable', severity: 'Unavailable', status: 'Unavailable',
  }))
  const notes = Array.from({ length: 70 }, (_, index) => `Note line ${index + 1}`).join('\n')
  const pdf = new TextDecoder().decode(createReportPdf({ ...report, candidateRows, notes }))

  assert.match(pdf, /\/Count 3/)
  assert.match(pdf, /Page 1 of 3/)
  assert.match(pdf, /Page 2 of 3/)
  assert.match(pdf, /Page 3 of 3/)
  assert.doesNotMatch(pdf, /Page 1 of 2|Page 2 of 2/)
})

test('JSON export contains selected saved run data and safe API artifact references', () => {
  const { run, results } = completedRun()
  const report = buildReportViewModel({
    patient: { id: 'p-1', patient_ref: 'SUBJECT-1' },
    caseRecord: { id: 'case-1', case_ref: 'CASE-1', patient_id: 'p-1' },
    run,
    results: {
      ...results,
      metadata: { ...results.metadata, models: {
        gradcam_available: true,
        attention_unet: { model_id: 'Attention U-Net', input_size: [256, 256], threshold: 0.5, device: 'cpu' },
      } },
    },
  })
  const json = buildReportJson(report, { notes: 'Review note', generatedAt: '2026-11-14T12:02:00Z' })
  assert.equal(json.analysis.run_id, 'run-1')
  assert.equal(json.analysis.predicted_candidate_count, 1)
  assert.equal(json.candidates[0].estimated_narrowing_percent, 45.1)
  assert.equal(json.analysis.models.artery_segmentation.model_id, 'Attention U-Net')
  assert.equal(json.report_notes, 'Review note')
  assert.equal(json.visualizations.gradcam_raw_map.api_endpoint, '/api/v1/analysis-runs/run-1/artifacts/gradcam.png')
  assert.equal(json.visualizations.stenosis_candidate_localization.available, true)
  assert.doesNotMatch(JSON.stringify(json), /[A-Z]:\\|checkpoint|password|secret/i)
})

test('CSV export includes headers when empty and escapes delimiter, quote and newline fields', () => {
  const { run, results } = completedRun()
  const emptyReport = buildReportViewModel({ patient: null, caseRecord: null, run, results: {
    ...results, metadata: { ...results.metadata, candidates: [] },
  } })
  const emptyCsv = buildReportCsv(emptyReport)
  assert.match(emptyCsv, /^Patient ID,Case ID,Image ID/)
  assert.equal(emptyCsv.trimEnd().split('\r\n').length, 1)

  const report = { ...emptyReport, patientId: 'SUBJECT,"one"\nsecond', candidateRows: [{
    candidateId: 3, location: 'x 1, y 2; 3x4 px', bbox: [1, 2, 3, 4], areaPixels: 12,
    meanProbability: 0.7, estimatedNarrowingPercent: null, severityValue: null, status: 'Unavailable',
  }] }
  const csv = buildReportCsv(report)
  assert.match(csv, /"SUBJECT,""one""\nsecond"/)
  assert.match(csv, /"1,2,3,4"/)
})
