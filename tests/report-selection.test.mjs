import test from 'node:test'
import assert from 'node:assert/strict'
import { readReportSelection, saveReportSelection, validateReportBaseSelection, validateReportCaseSelection } from '../src/features/reports/report-selection.mjs'
import { readFile } from 'node:fs/promises'

function memoryStorage(initial = {}) {
  const values = new Map(Object.entries(initial))
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  }
}

test('Reports reads only selection identifiers and restores valid patient and case associations', () => {
  const storage = memoryStorage({ reports: JSON.stringify({ patientId: 'p1', caseId: 'c1', imageId: 'i1', runId: 'r1', notes: 'private note', token: 'secret' }) })
  const saved = readReportSelection(storage, 'reports')
  assert.deepEqual(saved, { patientId: 'p1', caseId: 'c1', imageId: 'i1', runId: 'r1' })
  assert.deepEqual(validateReportBaseSelection(saved, [{ id: 'p1' }], [{ id: 'c1', patient_id: 'p1' }]), saved)
  assert.deepEqual(validateReportBaseSelection(saved, [{ id: 'p2' }], [{ id: 'c1', patient_id: 'p1' }]), { patientId: '', caseId: '', imageId: '', runId: '' })
  assert.deepEqual(validateReportBaseSelection(saved, [{ id: 'p1' }], [{ id: 'c1', patient_id: 'other' }]), { patientId: 'p1', caseId: '', imageId: '', runId: '' })
})

test('Reports restores only images and analysis runs belonging to the selected case and image', () => {
  const selection = { patientId: 'p1', caseId: 'c1', imageId: 'i1', runId: 'r1' }
  const images = [{ id: 'i1', case_id: 'c1' }, { id: 'i2', case_id: 'c2' }]
  const runs = [{ id: 'r1', case_id: 'c1', image_id: 'i1' }, { id: 'r2', case_id: 'c2', image_id: 'i2' }]
  assert.deepEqual(validateReportCaseSelection(selection, images, runs), selection)
  assert.deepEqual(validateReportCaseSelection({ ...selection, imageId: 'missing' }, images, runs), selection)
  assert.deepEqual(validateReportCaseSelection({ ...selection, imageId: 'missing', runId: 'missing' }, images, runs), { ...selection, imageId: '', runId: '' })
  assert.deepEqual(validateReportCaseSelection({ ...selection, runId: 'r2' }, images, runs), { ...selection, runId: '' })
  assert.deepEqual(validateReportCaseSelection({ ...selection, imageId: '', runId: 'r1' }, images, runs), selection)
})

test('Reports selection persistence stores only identifiers and clears empty selections', () => {
  const storage = memoryStorage()
  saveReportSelection(storage, 'reports', { patientId: 'p1', caseId: 'c1', imageId: 'i1', runId: 'r1', notes: 'do not persist' })
  assert.deepEqual(JSON.parse(storage.getItem('reports')), { patientId: 'p1', caseId: 'c1', imageId: 'i1', runId: 'r1' })
  saveReportSelection(storage, 'reports', { patientId: '', caseId: '', imageId: '', runId: '' })
  assert.equal(storage.getItem('reports'), null)
})

test('Reports UI persists an image selector and leaves notes outside browser storage', async () => {
  const source = await readFile(new URL('../src/pages/ReportsPage.tsx', import.meta.url), 'utf8')
  assert.match(source, /label>Image<select/)
  assert.match(source, /saveSessionReportSelection\(selectionKey/)
  assert.match(source, /selectedImageId/)
  assert.doesNotMatch(source, /sessionStorage[^\n]*notes|saveSessionReportSelection[^;]*notes/)
})
