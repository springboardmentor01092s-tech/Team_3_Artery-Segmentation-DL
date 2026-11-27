import test from 'node:test'
import assert from 'node:assert/strict'
import { blendHeatmapPixel, jetColor } from '../src/features/analysis/gradcam-overlay.mjs'

test('JET-style mapping produces blue, green-centered and red endpoints', () => {
  assert.deepEqual(jetColor(0), [0, 0, 128])
  assert.deepEqual(jetColor(0.5), [128, 255, 128])
  assert.deepEqual(jetColor(1), [128, 0, 0])
})

test('heatmap blend uses the configured alpha while preserving source pixels at zero alpha', () => {
  assert.deepEqual(blendHeatmapPixel([100, 100, 100], [200, 0, 0], 0.45), [145, 55, 55])
  assert.deepEqual(blendHeatmapPixel([17, 23, 41], [255, 0, 0], 0), [17, 23, 41])
})
