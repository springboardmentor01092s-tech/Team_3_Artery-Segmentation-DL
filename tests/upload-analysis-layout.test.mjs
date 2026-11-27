import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const page = await readFile(new URL('../src/pages/UploadAnalysisPage.tsx', import.meta.url), 'utf8')
const styles = await readFile(new URL('../src/styles.css', import.meta.url), 'utf8')

test('Upload & Analysis has the requested two-column panel hierarchy without removed sections', () => {
  assert.match(page, /className="upload-layout"[\s\S]*?className="upload-left-column"[\s\S]*?title="Select case"[\s\S]*?title="Upload images"[\s\S]*?title="Analysis"[\s\S]*?title="Images"/)
  assert.doesNotMatch(page, /PageHeader|WORKSPACE|Image Upload and Analysis|Case details|Model-specific preprocessing|Analysis progress|Activity log|page-bottom-note|Images in selected case|\d\. (?:Select case|Upload images|Analysis settings)/)
  assert.match(page, /title="Images" className="uploaded-list-panel"/)
})

test('Upload instructions remove the duplicate limit line and include the server limit guidance', () => {
  assert.doesNotMatch(page, /PNG, JPG, and JPEG · Server-enforced size limit/)
  assert.match(page, /Server-enforced size limit is 10 MB by default\./)
  assert.match(page, /Choose files/)
  assert.match(page, /Upload selected images/)
})

test('Case selection, authenticated upload, image selection, preprocessing, and explicit analysis remain connected', () => {
  assert.match(page, /useCases\(\)/)
  assert.match(page, /apiRequest<ImageRecord>\(`\/cases\/\$\{caseId\}\/images`, \{ method: 'POST', body: form \}\)/)
  assert.match(page, /apiRequest<PreprocessingStatus>\(`\/images\/\$\{image\.id\}\/preprocess`, \{ method: 'POST' \}\)/)
  assert.match(page, /name="analysis-image-selection"/)
  assert.match(page, /disabled=\{!selectedCase \|\| !selectedImage \|\| isAnalyzing \|\| isUploading\}/)
  assert.match(page, /buildAnalysisRunRequest\(selectedCase\.id, selectedImage\.id\)/)
  assert.match(page, /onClick=\{\(\) => void startAnalysis\(\)\}/)
})

test('Image list fills the right panel and scrolls internally while panel headings stay fixed', () => {
  assert.match(styles, /\.upload-layout \{[\s\S]*?grid-template-columns: repeat\(2, minmax\(0, 1fr\)\);[\s\S]*?min-height: 0;/)
  assert.match(styles, /\.upload-left-column \{[\s\S]*?grid-template-rows: auto minmax\(0, 1fr\) auto;/)
  assert.match(styles, /\.uploaded-list-panel \{ display: flex; flex-direction: column; overflow: hidden; \}/)
  assert.match(styles, /\.uploaded-list-panel > \.panel__heading \{ flex: 0 0 48px; \}/)
  assert.match(styles, /\.uploaded-list-panel > \.uploaded-image-list \{ flex: 1 1 auto; min-height: 0; max-height: none; overflow: auto;/)
  assert.match(styles, /@media \(max-width: 880px\)[\s\S]*?\.upload-layout \{ grid-template-columns: minmax\(0, 1fr\); height: auto; \}/)
})

test('Upload panels use matching tinted header and top-border accents in Light and Dark themes', () => {
  for (const panel of ['upload-case-panel', 'upload-drop-panel', 'analysis-settings-panel', 'uploaded-list-panel']) {
    assert.match(styles, new RegExp(`\\.upload-page \\.${panel} \\{ --upload-panel-accent: #[0-9a-f]+; --upload-heading-border: #[0-9a-f]+; --upload-heading-bg: #[0-9a-f]+; \\}`))
    assert.match(styles, new RegExp(`html\\[data-theme="dark"\\] \\.upload-page \\.${panel} \\{ --upload-panel-accent: #[0-9a-f]+; --upload-heading-border: #[0-9a-f]+; --upload-heading-bg: #[0-9a-f]+; \\}`))
  }
})
