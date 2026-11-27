import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { caseImageContentPath, getCasePreviewImages } from '../src/features/cases/case-preview.mjs'

test('case thumbnail data is limited to six records and preserves protected content route encoding', () => {
  const images = Array.from({ length: 8 }, (_, index) => ({ id: `image-${index}` }))
  assert.equal(getCasePreviewImages(images).length, 6)
  assert.equal(getCasePreviewImages(images)[0].id, 'image-0')
  assert.equal(caseImageContentPath('image/id'), '/images/image%2Fid/content')
})

test('Cases page uses authenticated case-scoped image and analysis APIs and has loading, empty and failure states', async () => {
  const source = await readFile(new URL('../src/pages/CasesPage.tsx', import.meta.url), 'utf8')
  assert.match(source, /apiRequest<CaseImageSummary\[]>\(`\/cases\/\$\{encodedId\}\/images`\)/)
  assert.match(source, /apiRequest<CaseAnalysisRun\[]>\(`\/cases\/\$\{encodedId\}\/analysis-runs`\)/)
  assert.match(source, /apiRequestBlob\(caseImageContentPath\(image\.id\)\)/)
  assert.match(source, /Unable to load images/)
  assert.match(source, /No images uploaded/)
  assert.match(source, /Loading case image previews/)
  const css = await readFile(new URL('../src/styles.css', import.meta.url), 'utf8')
  assert.match(css, /\.case-image-preview img\s*\{[^}]*object-fit:\s*contain/s)
})

test('case-scoped protected APIs retain server-side owner authorization', async () => {
  const imageApi = await readFile(new URL('../backend/app/api/v1/endpoints/images.py', import.meta.url), 'utf8')
  const analysisApi = await readFile(new URL('../backend/app/api/v1/endpoints/analysis.py', import.meta.url), 'utf8')
  assert.match(imageApi, /def accessible_case[\s\S]*?owned_or_admin\(select\(Case\), Case, current_user\)/)
  assert.match(imageApi, /@router\.get\("\/images\/\{image_id\}\/content"\)[\s\S]*?if current_user\.role != "admin":[\s\S]*?Case\.owner_id == current_user\.id/)
  assert.match(analysisApi, /def list_case_analysis_runs\([\s\S]*?owned_or_admin\(select\(Case\), Case, current_user\)/)
})
