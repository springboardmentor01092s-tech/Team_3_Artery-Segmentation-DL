import test from 'node:test'
import assert from 'node:assert/strict'
import {
  clampViewerPan,
  stepViewerScale,
  VIEWER_MAX_SCALE,
  VIEWER_MIN_SCALE,
} from '../src/features/analysis/viewer-controls.mjs'

test('viewer zoom changes in fixed steps and respects minimum and maximum scales', () => {
  assert.equal(stepViewerScale(1, 1), 1.25)
  assert.equal(stepViewerScale(VIEWER_MAX_SCALE, 1), VIEWER_MAX_SCALE)
  assert.equal(stepViewerScale(VIEWER_MIN_SCALE, -1), VIEWER_MIN_SCALE)
})

test('viewer pan stays within the scaled image boundary', () => {
  const geometry = { imageWidth: 400, imageHeight: 300, stageWidth: 500, stageHeight: 400, scale: 2 }
  assert.deepEqual(clampViewerPan({ x: 1000, y: -1000 }, geometry), { x: 150, y: -100 })
  assert.deepEqual(clampViewerPan({ x: 50, y: -50 }, { ...geometry, scale: 1 }), { x: 0, y: 0 })
})
