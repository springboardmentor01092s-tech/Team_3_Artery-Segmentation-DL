import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const page = await readFile(new URL('../src/pages/ResultsPage.tsx', import.meta.url), 'utf8')
const panels = await readFile(new URL('../src/components/ResultsSummaryPanels.tsx', import.meta.url), 'utf8')
const styles = await readFile(new URL('../src/styles.css', import.meta.url), 'utf8')

test('Results page uses one Select analysis panel with the existing three selectors', () => {
  assert.match(page, /<Panel title="Select analysis" className="results-select-panel">[\s\S]*?<label>Case<select[\s\S]*?<label>Image<select[\s\S]*?<label>Analysis run<select/)
  assert.doesNotMatch(page, /Analysis Results|Review outputs returned for a completed analysis run\.|eyebrow="ANALYSIS"|Back to cases/)
})

test('Results page keeps only the five requested image tabs and removes retired panels', () => {
  const tabBlock = page.match(/const resultViews:[\s\S]*?\n\]/)?.[0] ?? ''
  const labels = [...tabBlock.matchAll(/label: '([^']+)'/g)].map((match) => match[1])
  assert.deepEqual(labels, ['Original image', 'Artery mask', 'Stenosis mask', 'Candidate overlay', 'Grad-CAM visualization'])
  assert.doesNotMatch(page, /Combined visualization|Source image|Returned segmentation artifacts|Candidate localization metadata|Run information|JET heatmap blended over the original image at 45% opacity/)
  assert.match(page, /resource\.key !== 'combined_visualization\.png'/)
})

test('viewer retains returned artifact handling and downloads the existing run artifacts', () => {
  assert.match(page, /apiRequestBlob\(path\)/)
  assert.match(page, /createGradcamOverlay\(originalUrl, rawHeatmapUrl, 0\.45\)/)
  assert.match(page, /href=\{gradcamOverlayUrl\} download="gradcam_overlay\.png"[^>]*>[\s\S]*?Download Grad-CAM PNG/)
  assert.match(page, /href=\{resourceUrls\['candidate_overlay\.png'\]\} download="candidate_overlay\.png"[^>]*>[\s\S]*?Download candidate overlay/)
  assert.match(page, /onPointerDown=\{beginPan\} onPointerMove=\{movePan\} onPointerUp=\{endPan\}/)
  assert.match(page, /aria-label="Zoom in"/)
  assert.match(page, /activeResourceExists/)
  assert.match(page, /Artifact not returned/)
  assert.match(page, /Grad-CAM unavailable/)
})

test('candidate and narrowing panels keep fixed headings and internally scrollable two-card previews', () => {
  assert.match(page, /PredictedStenosisCandidatesPanel className="results-candidates-panel"/)
  assert.match(page, /className="results-narrowing-panel"/)
  assert.match(styles, /\.results-summary-stack \{[\s\S]*?grid-template-rows: minmax\(0, 1fr\) minmax\(0, 1fr\);/)
  assert.match(styles, /\.results-candidates-panel \.candidate-list,[\s\S]*?overflow-y: auto;/)
  assert.match(styles, /\.results-candidates-panel \.candidate-list \{ grid-auto-rows: minmax\(62px, max-content\); max-height: 132px;/)
  assert.match(styles, /\.results-narrowing-panel \.percentage-narrowing-values \{ max-height: 184px;/)
  assert.match(styles, /\.results-narrowing-panel \.percentage-narrowing-value \{[\s\S]*?flex-wrap: nowrap;[\s\S]*?white-space: nowrap;/)
  assert.match(panels, /Predicted stenosis candidate \{item\.candidateId\}/)
  assert.match(panels, /Estimated narrowing:<\/span>/)
})

test('Results layout has desktop viewport sizing, scrollable viewer, responsive stacking, and dark theme accents', () => {
  assert.match(styles, /\.app-body:has\(\.results-page\) \{[\s\S]*?height: calc\(100dvh - 70px\);[\s\S]*?overflow: hidden;/)
  assert.match(styles, /\.viewer-stage \{[\s\S]*?overflow: auto;[\s\S]*?overscroll-behavior: contain;/)
  assert.match(styles, /@media \(max-width: 880px\)[\s\S]*?\.app-body:has\(\.results-page\)[\s\S]*?overflow: visible;[\s\S]*?\.results-workspace \{ flex: none; grid-template-columns: minmax\(0, 1fr\);/)
  assert.match(styles, /html\[data-theme="dark"\] \.results-narrowing-panel > \.panel__heading > h2/)
})
