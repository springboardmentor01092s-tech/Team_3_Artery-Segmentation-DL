import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import {
  getComparisonDifferences,
  getComparisonRunOptions,
  getRunComparisonSummary,
  validateComparisonSelection,
} from '../src/features/analysis/run-comparison.mjs'

const runs = [
  { id: 'run-a', image_id: 'image-one', case_id: 'case-one', status: 'completed', created_at: '2026-11-01T10:00:00Z', duration_seconds: 12 },
  { id: 'run-b', image_id: 'image-one', case_id: 'case-one', status: 'failed', created_at: '2026-11-02T10:00:00Z', duration_seconds: null },
  { id: 'run-c', image_id: 'image-two', case_id: 'case-one', status: 'completed', created_at: '2026-11-03T10:00:00Z', duration_seconds: 14 },
  { id: 'run-no-image', image_id: null, case_id: 'case-one', status: 'completed', created_at: '2026-11-04T10:00:00Z', duration_seconds: null },
]

test('comparison options use persisted image IDs and exclude the selected run itself', () => {
  assert.deepEqual(getComparisonRunOptions(runs).map((run) => run.id), ['run-a', 'run-b', 'run-c'])
  assert.deepEqual(getComparisonRunOptions(runs, 'run-a').map((run) => run.id), ['run-b'])
  assert.deepEqual(getComparisonRunOptions(runs, 'run-c'), [])
})

test('comparison validates the exact saved source image ID and prevents duplicate runs', () => {
  assert.deepEqual(validateComparisonSelection(runs[0], runs[1]), { valid: true, reason: '' })
  assert.match(validateComparisonSelection(runs[0], runs[0]).reason, /different analysis runs/)
  assert.match(validateComparisonSelection(runs[0], runs[2]).reason, /persisted image IDs match/)
  assert.match(validateComparisonSelection(runs[0], runs[3]).reason, /saved source image/)
  assert.match(validateComparisonSelection(undefined, runs[1]).reason, /Select two/)
})

test('comparison summary uses only persisted metadata and marks missing values unavailable', () => {
  const summary = getRunComparisonSummary(runs[0], {
    run_id: 'run-a',
    image_id: 'image-one',
    status: 'completed',
    metadata: {
      models: {
        candidate_count: 1,
        attention_unet: { model_id: 'attention_unet', threshold: 0.5 },
        unetpp: { model_id: 'unetpp_resnet34_stenosis', architecture: 'UnetPlusPlus', threshold: 0.2 },
      },
      candidates: [{ candidate_id: 1 }],
      percentage_narrowing: { measurements: [{ candidate_id: 1, status: 'available', estimated_narrowing_percent: 45.1 }] },
      severity_assessment: { measurements: [{ candidate_id: 1, status: 'available', severity: 'Mild' }] },
    },
  })
  assert.equal(summary.candidateCount, 1)
  assert.match(summary.narrowing, /45\.1% \(experimental\)/)
  assert.match(summary.severity, /Mild \(experimental\)/)
  assert.match(summary.models, /threshold 0\.2/)

  const missing = getRunComparisonSummary(runs[1], { run_id: 'run-b', image_id: 'image-one', status: 'failed' })
  assert.equal(missing.candidateCount, null)
  assert.equal(missing.narrowing, 'Not available')
  assert.equal(missing.severity, 'Not available')
  assert.equal(missing.models, 'Not available')
  assert.equal(missing.duration, 'Not available')
})

test('numeric differences are shown only when both saved values exist', () => {
  const summaryA = getRunComparisonSummary(runs[0], { run_id: 'run-a', status: 'completed', metadata: { candidates: [{}, {}] } })
  const summaryB = getRunComparisonSummary({ ...runs[1], duration_seconds: 9 }, { run_id: 'run-b', status: 'completed', metadata: { candidates: [{}] } })
  assert.deepEqual(getComparisonDifferences(summaryA, summaryB), {
    duration: '-3.00 s (Run B − Run A)',
    candidateCount: '-1 (Run B − Run A)',
  })
  const missing = getComparisonDifferences(summaryA, getRunComparisonSummary(runs[1], { run_id: 'run-b', status: 'failed' }))
  assert.equal(missing.duration, 'Not available')
  assert.equal(missing.candidateCount, 'Not available')
})

test('Results page does not render unavailable segmentation metrics or duplicate export section', async () => {
  const source = await readFile(new URL('../src/pages/ResultsPage.tsx', import.meta.url), 'utf8')
  assert.doesNotMatch(source, /Panel title="Segmentation metrics"/)
  assert.doesNotMatch(source, /Panel title="Download and export"/)
  assert.match(source, /<AnalysisRunComparison runs=\{visibleRuns\} \/>/)
})
