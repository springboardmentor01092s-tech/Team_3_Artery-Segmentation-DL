import test, { after, before } from 'node:test'
import assert from 'node:assert/strict'
import { readdir, readFile } from 'node:fs/promises'
import path from 'node:path'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { createServer } from 'vite'
import { getPercentageNarrowingDisplayState } from '../src/features/analysis/contracts.mjs'

const noticeA = 'Model outputs are predictions for review, not clinically validated findings. Any percentage narrowing estimate is experimental, based on predicted-mask widths in pixels, and is not clinically calibrated. No stenosis severity is provided.'
const noticeB = 'Application status — patient, case, image upload, and analysis are connected to backend services. Model outputs are not clinically validated. Report generation is not integrated.'

let vite
let PercentageNarrowingPanel
let PredictedStenosisCandidatesPanel

before(async () => {
  vite = await createServer({
    logLevel: 'silent',
    optimizeDeps: { noDiscovery: true, include: [] },
    server: { middlewareMode: true },
    appType: 'custom',
  })
  ;({ PercentageNarrowingPanel, PredictedStenosisCandidatesPanel } = await vite.ssrLoadModule('/src/components/ResultsSummaryPanels.tsx'))
})

after(async () => {
  if (vite) await vite.close()
})

function panelContent(html, className) {
  return html.match(new RegExp(`<div class="${className}"[^>]*>(.*?)</div></section>`))?.[1] ?? ''
}

test('percentage narrowing card renders only the saved Estimated narrowing value', () => {
  const state = getPercentageNarrowingDisplayState({
    run_id: 'saved-run',
    status: 'completed',
    metadata: {
      percentage_narrowing: {
        algorithm_version: 'predicted-mask-width-v1',
        status: 'available',
        measurements: [{
          candidate_id: 1,
          label: 'Predicted stenosis candidate 1',
          status: 'available',
          estimated_narrowing_percent: 45.1,
          reference_predicted_mask_width_px: 12,
          minimum_candidate_predicted_mask_width_px: 6,
        }],
      },
    },
  })
  const html = renderToStaticMarkup(createElement(PercentageNarrowingPanel, {
    state,
    candidates: [{ candidate_id: 1, label: 'Predicted stenosis candidate 1', bbox: [1, 2, 3, 4], centroid: [2, 3], area_pixels: 5, mean_probability: 0.7, measurement_grid: '512x512 model pixels' }],
    severityAssessment: {
      algorithm_version: 'task5-user-specified-thresholds-v1',
      threshold_source: 'user_specified_experimental_project_rules',
      status: 'available',
      thresholds: [],
      invalid_measurement_count: 0,
      measurements: [{ candidate_id: 1, status: 'available', severity: 'Mild', source_narrowing_percent: 45.1 }],
    },
  }))
  const content = panelContent(html, 'percentage-narrowing-values')

  assert.match(html, /<h2>Experimental percentage narrowing<\/h2>/)
  assert.match(content, /Predicted stenosis candidate 1/)
  assert.match(content, /Estimated narrowing:<\/span> <strong>45\.1%<\/strong>/)
  assert.match(content, /Severity:<\/span> <strong>Mild<\/strong>/)
  assert.equal((content.match(/<p class="percentage-narrowing-value"/g) ?? []).length, 2)
  for (const removedText of [
    'Reference predicted-mask width',
    'Minimum candidate predicted-mask width',
    'not a clinically calibrated lumen measurement',
    'thresholded predicted-mask foreground',
  ]) assert.equal(content.includes(removedText), false)
})

test('percentage narrowing card keeps a simple unavailable state without a fabricated value', () => {
  const state = getPercentageNarrowingDisplayState({ run_id: 'old-run', status: 'completed', metadata: {} })
  const html = renderToStaticMarkup(createElement(PercentageNarrowingPanel, {
    state,
    candidates: [{ candidate_id: 3, label: 'Predicted stenosis candidate 3', bbox: [1, 2, 3, 4], centroid: [2, 3], area_pixels: 5, mean_probability: 0.7, measurement_grid: '512x512 model pixels' }],
    severityAssessment: {
      algorithm_version: 'task5-user-specified-thresholds-v1',
      threshold_source: 'user_specified_experimental_project_rules',
      status: 'unavailable',
      thresholds: [],
      invalid_measurement_count: 0,
      measurements: [],
    },
  }))
  const content = panelContent(html, 'percentage-narrowing-values')

  assert.match(content, /Estimated narrowing:<\/span> <strong>Unavailable<\/strong>/)
  assert.match(content, /Severity:<\/span> <strong>Unavailable<\/strong>/)
  assert.equal(content.includes('%'), false)
})

test('percentage narrowing explains when candidate mask width is not smaller and leaves severity unavailable', () => {
  const state = getPercentageNarrowingDisplayState({
    run_id: 'width-not-smaller-run',
    status: 'completed',
    metadata: {
      percentage_narrowing: {
        algorithm_version: 'candidate-dilated-predicted-mask-width-v2',
        status: 'unavailable',
        measurements: [{
          candidate_id: 1,
          status: 'unavailable',
          unavailable_reason: 'candidate_predicted_mask_width_not_smaller_than_reference',
        }],
      },
      severity_assessment: {
        algorithm_version: 'task5-user-specified-thresholds-v1',
        threshold_source: 'user_specified_experimental_project_rules',
        status: 'unavailable',
        thresholds: [],
        invalid_measurement_count: 0,
        measurements: [{ candidate_id: 1, status: 'unavailable', reason: 'saved_narrowing_estimate_unavailable' }],
      },
    },
  })
  const html = renderToStaticMarkup(createElement(PercentageNarrowingPanel, {
    state,
    candidates: [{ candidate_id: 1, label: 'Predicted stenosis candidate 1', bbox: [1, 2, 3, 4], centroid: [2, 3], area_pixels: 5, mean_probability: 0.7, measurement_grid: '512x512 model pixels' }],
  }))
  const content = panelContent(html, 'percentage-narrowing-values')

  assert.match(content, /Estimated narrowing:<\/span> <strong>Unavailable<\/strong>/)
  assert.match(content, /Severity:<\/span> <strong>Unavailable<\/strong>/)
  assert.match(content, /predicted stenosis-mask width was not smaller than the reference artery-mask width/)
  assert.match(content, /No narrowing estimate or severity was assigned/)
  assert.equal(content.includes('%'), false)
})

test('severity is matched by candidate ID and missing historical severity remains unavailable', () => {
  const state = getPercentageNarrowingDisplayState({
    run_id: 'saved-run',
    status: 'completed',
    metadata: {
      percentage_narrowing: {
        algorithm_version: 'predicted-mask-width-v1',
        status: 'available',
        measurements: [
          { candidate_id: 1, status: 'available', estimated_narrowing_percent: 25.1 },
          { candidate_id: 2, status: 'available', estimated_narrowing_percent: 70 },
        ],
      },
    },
  })
  const html = renderToStaticMarkup(createElement(PercentageNarrowingPanel, {
    state,
    candidates: [
      { candidate_id: 1, label: 'Predicted stenosis candidate 1', bbox: [1, 2, 3, 4], centroid: [2, 3], area_pixels: 5, mean_probability: 0.7, measurement_grid: '512x512 model pixels' },
      { candidate_id: 2, label: 'Predicted stenosis candidate 2', bbox: [4, 5, 6, 7], centroid: [5, 6], area_pixels: 8, mean_probability: 0.8, measurement_grid: '512x512 model pixels' },
    ],
    severityAssessment: {
      algorithm_version: 'task5-user-specified-thresholds-v1',
      threshold_source: 'user_specified_experimental_project_rules',
      status: 'partial',
      thresholds: [],
      invalid_measurement_count: 0,
      measurements: [
        { candidate_id: 2, status: 'available', severity: 'Critical', source_narrowing_percent: 70 },
      ],
    },
  }))
  const content = panelContent(html, 'percentage-narrowing-values')

  assert.match(content, /Estimated narrowing:<\/span> <strong>25\.1%<\/strong><\/p><p class="percentage-narrowing-value"><span>Severity:<\/span> <strong>Unavailable<\/strong>/)
  assert.match(content, /Estimated narrowing:<\/span> <strong>70\.0%<\/strong><\/p><p class="percentage-narrowing-value"><span>Severity:<\/span> <strong>Critical<\/strong>/)
  assert.equal(content.includes('Mild / Outside configured classes'), false)
})

test('candidate-wise narrowing rows follow candidate IDs and retain unavailable entries without shifting values', () => {
  const candidates = [1, 2, 3, 4].map((candidate_id) => ({
    candidate_id,
    label: `Predicted stenosis candidate ${candidate_id}`,
    bbox: [candidate_id, 2, 3, 4],
    centroid: [candidate_id + 1, 3],
    area_pixels: 5,
    mean_probability: 0.7,
    measurement_grid: '512x512 model pixels',
  }))
  const state = getPercentageNarrowingDisplayState({
    run_id: 'saved-run',
    status: 'completed',
    metadata: {
      percentage_narrowing: {
        algorithm_version: 'candidate-dilated-predicted-mask-width-v2',
        status: 'partial',
        measurements: [
          { candidate_id: 4, status: 'available', estimated_narrowing_percent: 61.2 },
          { candidate_id: 1, status: 'available', estimated_narrowing_percent: 25.1 },
          { candidate_id: 3, status: 'available', estimated_narrowing_percent: 42.8 },
        ],
      },
    },
  })
  const html = renderToStaticMarkup(createElement(PercentageNarrowingPanel, {
    candidates,
    state,
    severityAssessment: {
      algorithm_version: 'task5-user-specified-thresholds-v1',
      threshold_source: 'user_specified_experimental_project_rules',
      status: 'partial',
      thresholds: [],
      invalid_measurement_count: 0,
      measurements: [
        { candidate_id: 4, status: 'available', severity: 'Moderate', source_narrowing_percent: 61.2 },
        { candidate_id: 1, status: 'available', severity: 'Normal', source_narrowing_percent: 25.1 },
        { candidate_id: 3, status: 'available', severity: 'Mild', source_narrowing_percent: 42.8 },
      ],
    },
  }))
  const content = panelContent(html, 'percentage-narrowing-values')

  assert.equal((content.match(/class="percentage-narrowing-result"/g) ?? []).length, 4)
  const candidateRows = [...content.matchAll(/Predicted stenosis candidate (\d+).*?Estimated narrowing:<\/span> <strong>(.*?)<\/strong><\/p><p class="percentage-narrowing-value"><span>Severity:<\/span> <strong>(.*?)<\/strong>/gs)]
  assert.deepEqual(candidateRows.map(([, candidate, narrowing, severity]) => [candidate, narrowing, severity]), [
    ['1', '25.1%', 'Normal'],
    ['2', 'Unavailable', 'Unavailable'],
    ['3', '42.8%', 'Mild'],
    ['4', '61.2%', 'Moderate'],
  ])
})

test('predicted candidate panel has no removed subtitle and retains saved candidate fields', () => {
  const html = renderToStaticMarkup(createElement(PredictedStenosisCandidatesPanel, {
    completed: true,
    candidates: [{
      candidate_id: 2,
      label: 'Predicted stenosis candidate 2',
      bbox: [10, 20, 30, 40],
      centroid: [20, 30],
      area_pixels: 15,
      mean_probability: 0.8,
      measurement_grid: '512x512 model pixels',
    }],
  }))

  assert.match(html, /<h2>Predicted stenosis candidates<\/h2>/)
  assert.equal(html.includes('Predicted regions only; these are not confirmed stenoses or clinical measurements.'), false)
  assert.match(html, /Predicted stenosis candidate 2/)
  assert.match(html, /Bounding box \(original image\): 10, 20, 30, 40/)
  assert.match(html, /Area: 15 pixels on 512x512 model pixels/)
})

test('both specified long notices are absent from frontend source and the obsolete notice component is unused', async () => {
  async function sourceFiles(directory) {
    const entries = await readdir(directory, { withFileTypes: true })
    const nested = await Promise.all(entries.map((entry) => {
      const target = path.join(directory, entry.name)
      return entry.isDirectory() ? sourceFiles(target) : /\.(tsx?|jsx?|mjs)$/.test(entry.name) ? [target] : []
    }))
    return nested.flat()
  }
  const files = await sourceFiles(path.resolve('src'))
  const source = (await Promise.all(files.map((file) => readFile(file, 'utf8')))).join('\n')

  assert.equal(source.includes(noticeA), false)
  assert.equal(source.includes(noticeB), false)
  assert.equal(source.includes('WorkspaceNotice'), false)
})
