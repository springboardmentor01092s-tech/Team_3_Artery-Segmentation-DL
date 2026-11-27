import test from 'node:test'
import assert from 'node:assert/strict'
import {
  buildAnalysisRunRequest,
  caseAnalysisRunsPath,
  getGradCAMDisplayState,
  getPercentageNarrowingDisplayState,
  getAnalysisImageResources,
  toApiRequestPath,
} from '../src/features/analysis/contracts.mjs'

test('analysis request matches the backend case route and image_id payload', () => {
  const request = buildAnalysisRunRequest('case/with space', 'image-uuid')
  assert.equal(request.path, '/cases/case%2Fwith%20space/analysis-runs')
  assert.equal(request.init.method, 'POST')
  assert.deepEqual(JSON.parse(request.init.body), { image_id: 'image-uuid' })
})

test('case run-history path stays under the selected case route', () => {
  assert.equal(caseAnalysisRunsPath('case/with space'), '/cases/case%2Fwith%20space/analysis-runs')
})

test('only artifacts actually returned by a completed run become resources', () => {
  const resources = getAnalysisImageResources({
    run_id: 'run-uuid',
    status: 'completed',
    source_image_url: '/api/v1/images/image-uuid/content',
    artifacts: {
      'artery_mask.png': '/api/v1/analysis-runs/run-uuid/artifacts/artery_mask.png',
      'candidate_overlay.png': '/api/v1/analysis-runs/run-uuid/artifacts/candidate_overlay.png',
      'unknown.png': '/api/v1/analysis-runs/run-uuid/artifacts/unknown.png',
    },
  })
  assert.deepEqual(resources.map(({ key }) => key), ['original_image', 'artery_mask.png', 'candidate_overlay.png'])
})

test('Grad-CAM is exposed only when the backend returns its separate artifact', () => {
  const resources = getAnalysisImageResources({
    run_id: 'run-uuid',
    status: 'completed',
    artifacts: {
      'stenosis_mask.png': '/api/v1/analysis-runs/run-uuid/artifacts/stenosis_mask.png',
      'gradcam.png': '/api/v1/analysis-runs/run-uuid/artifacts/gradcam.png',
    },
  })
  const gradcam = resources.find(({ key }) => key === 'gradcam.png')
  assert.equal(gradcam?.kind, 'image')
  assert.match(gradcam?.label ?? '', /not a confirmed stenosis boundary/i)
  assert.deepEqual(
    getAnalysisImageResources({ run_id: 'run-uuid', status: 'completed', artifacts: { 'stenosis_mask.png': '/mask.png' } }).map(({ key }) => key),
    ['stenosis_mask.png'],
  )
})

test('Grad-CAM Results UI state is accurate when available and unavailable', () => {
  const availableResult = {
    run_id: 'run-uuid',
    status: 'completed',
    metadata: { models: { gradcam_available: true } },
    artifacts: { 'gradcam.png': '/api/v1/analysis-runs/run-uuid/artifacts/gradcam.png' },
  }
  const availableResources = getAnalysisImageResources(availableResult)
  assert.deepEqual(getGradCAMDisplayState(availableResult, availableResources), { status: 'available' })

  const unavailableResult = {
    run_id: 'run-uuid',
    status: 'completed',
    metadata: { models: { gradcam_available: false, gradcam_unavailable_reason: 'Optional explanation failed.' } },
    artifacts: {},
  }
  assert.deepEqual(
    getGradCAMDisplayState(unavailableResult, getAnalysisImageResources(unavailableResult)),
    { status: 'unavailable', reason: 'Optional explanation failed.' },
  )
})

test('percentage narrowing display uses only persisted run metadata and identifies older runs', () => {
  assert.deepEqual(
    getPercentageNarrowingDisplayState({ run_id: 'old-run', status: 'completed', metadata: {} }),
    { status: 'not_calculated' },
  )
  const savedResult = {
    run_id: 'saved-run',
    status: 'completed',
    metadata: {
      percentage_narrowing: {
        algorithm_version: 'predicted-mask-width-v1',
        status: 'available',
        coordinate_system: 'original_image_pixel_grid',
        measurement_unit: 'pixel',
        disclaimer: 'Experimental predicted-mask-based narrowing estimate — not a clinically calibrated lumen measurement.',
        measurements: [{ candidate_id: 1, status: 'available', estimated_narrowing_percent: 25 }],
      },
    },
  }
  assert.deepEqual(getPercentageNarrowingDisplayState(savedResult), {
    status: 'available',
    metadata: savedResult.metadata.percentage_narrowing,
  })
  assert.deepEqual(
    getPercentageNarrowingDisplayState({ run_id: 'invalid', status: 'completed', metadata: { percentage_narrowing: { status: 'available' } } }),
    { status: 'invalid', reason: 'The saved run contains invalid percentage-narrowing metadata.' },
  )
})

test('failed or incomplete runs do not expose result resources', () => {
  assert.deepEqual(getAnalysisImageResources({
    run_id: 'run-uuid',
    status: 'failed',
    source_image_url: '/api/v1/images/image-uuid/content',
    artifacts: { 'artery_mask.png': '/api/v1/private.png' },
  }), [])
})

test('protected result URLs are restricted to same-origin API paths', () => {
  assert.equal(toApiRequestPath('/api/v1/images/id/content', 'http://localhost:5173'), '/images/id/content')
  assert.equal(toApiRequestPath('https://outside.example/api/v1/images/id', 'http://localhost:5173'), null)
  assert.equal(toApiRequestPath('/assets/image.png', 'http://localhost:5173'), null)
})
