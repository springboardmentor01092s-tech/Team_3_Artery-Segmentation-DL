import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { filterCases } from '../src/features/cases/case-filter.mjs'

const cases = await readFile(new URL('../src/pages/CasesPage.tsx', import.meta.url), 'utf8')
const styles = await readFile(new URL('../src/styles.css', import.meta.url), 'utf8')

test('Cases page uses the Patients-style toolbar and keeps the existing create-case action', () => {
  assert.match(cases, /className="patients-toolbar cases-toolbar"[\s\S]*?role="tablist"[\s\S]*?className="module-tab module-tab--active" role="tab" aria-selected="true" to="\/cases"/)
  assert.match(cases, /Create new case/)
  assert.doesNotMatch(cases, /PageHeader|Case Management<\/h|Organize imaging cases and review saved case details/)
})

test('Cases table heading uses a blue rounded header box without moving its search action', () => {
  assert.match(cases, /<Panel title=\{`Cases \(\$\{cases\.length\}\)`\} className="case-table-panel" action=\{<label className="case-table-search"/)
  assert.match(styles, /\.case-table-panel \.panel__heading > h2 \{[\s\S]*?min-height: 48px;[\s\S]*?padding: 0 12px;[\s\S]*?border: 1px solid #c7ddf5;[\s\S]*?border-radius: 9px;[\s\S]*?background: #eff6ff;/)
  assert.match(styles, /html\[data-theme="dark"\] \.case-table-panel \.panel__heading > h2 \{ border-color: #365475; background: #233a53; \}/)
})

test('Cases search stays available in the table heading while the modality dropdown fills its own toolbar', () => {
  assert.match(cases, /className="case-table-search"[\s\S]*?aria-label="Search cases"/)
  assert.match(cases, /className="list-toolbar case-modality-filter-toolbar">\s*<select aria-label="Filter cases by modality"/)
  assert.doesNotMatch(cases, /case-modality-filter-toolbar">\s*<input/)
  assert.match(styles, /\.case-table-panel \.case-modality-filter-toolbar \{ display: block; width: 100%; margin-bottom: 10px; \}/)
  assert.match(styles, /\.case-table-panel \.case-modality-filter-toolbar select \{ display: block; width: 100%; \}/)
})

test('Cases table uses explicit fixed-width columns and consistent header/value alignment', () => {
  assert.match(cases, /<colgroup><col className="case-col-id" \/><col className="case-col-patient" \/><col className="case-col-owner" \/><col className="case-col-images" \/><col className="case-col-status" \/><col className="case-col-created" \/><col className="case-col-actions" \/><\/colgroup>/)
  for (let index = 1; index <= 7; index++) assert.match(cases, new RegExp(`case-table__cell-${index}`))
  assert.match(styles, /\.case-table-panel \.case-table \{ width: 100%; min-width: 860px; table-layout: fixed;/)
  assert.match(styles, /\.case-table \.case-table__cell-1,[\s\S]*?\.case-table \.case-table__cell-6 \{ text-align: left; \}/)
  assert.match(styles, /\.case-table \.case-table__cell-4,[\s\S]*?\.case-table \.case-table__cell-5 \{ text-align: center; \}/)
  assert.match(styles, /\.case-table \.case-table__cell-7 \{ text-align: right; \}/)
})

test('Cases list scrolls internally with a sticky header, shows three rows, and leaves pagination below it', () => {
  assert.match(cases, /case-table-wrap\$\{isLoading \|\| filteredCases\.length === 0 \? ' case-table-wrap--message' : ''\}[\s\S]*?<\/div>\s*<div className="table-pagination">/)
  assert.match(styles, /\.case-table-panel \.case-table-wrap \{ max-height: 169px; overflow: auto;/)
  assert.match(styles, /\.case-table thead th \{ position: sticky; top: 0;/)
  assert.match(styles, /\.case-table tbody tr \{ height: 44px; \}/)
  assert.match(styles, /\.case-table-panel \.case-table-wrap--message \{ max-height: none; \}/)
})

test('Case details and image previews sit in equally sized, colored panels with matching header sections', () => {
  assert.match(cases, /className="patients-bottom-grid cases-bottom-grid"[\s\S]*?className="case-details-panel"[\s\S]*?className="case-images-panel"/)
  assert.match(cases, /title="Images" className="case-images-panel" action=\{<Link className="link-button" to="\/upload">Go to upload/)
  assert.match(styles, /\.patients-bottom-grid \{ display: grid; grid-template-columns: repeat\(2, minmax\(0, 1fr\)\); gap: 13px; align-items: stretch; \}/)
  assert.match(styles, /\.cases-bottom-grid > \.case-details-panel \{ border-top-color: #79c8b7; \}/)
  assert.match(styles, /\.cases-bottom-grid > \.case-images-panel \{ border-top-color: #aaa4e5; \}/)
  assert.match(styles, /\.cases-bottom-grid > \.case-details-panel > \.panel__heading \{ border-color: #d7eee9; background: #f0faf7; \}/)
  assert.match(styles, /\.cases-bottom-grid > \.case-images-panel > \.panel__heading \{ border-color: #e6e2f7; background: #f7f5fd; \}/)
  assert.match(styles, /html\[data-theme="dark"\] \.cases-bottom-grid > \.case-details-panel > \.panel__heading/)
  assert.match(styles, /html\[data-theme="dark"\] \.cases-bottom-grid > \.case-images-panel > \.panel__heading/)
})

test('Cases API-backed selection, modal workflow, previews and upload navigation remain connected', () => {
  assert.match(cases, /const \{ cases, patients, selectedCase,[\s\S]*?openCase, createCase, updateCase \} = useCases\(\)/)
  assert.match(cases, /changeFilters\(search: string, modality: string\)/)
  assert.match(cases, /onClick=\{\(\) => void openCase\(record\.id\)\}/)
  assert.match(cases, /onSubmit=\{submitCase\}/)
  assert.match(cases, /apiRequestBlob\(caseImageContentPath\(image\.id\)\)/)
  assert.match(cases, /to="\/upload">Go to upload/)
})

test('case search matches case IDs and patient references partially and case-insensitively with modality filtering', () => {
  const patientA = { id: 'patient-a', patient_ref: 'PT-Alpha' }
  const patientB = { id: 'patient-b', patient_ref: 'Study-Beta' }
  const patientsById = new Map([[patientA.id, patientA], [patientB.id, patientB]])
  const records = [
    { id: 'a', case_ref: 'CASE-ALPHA-01', patient_id: patientA.id, modality: 'CTA' },
    { id: 'b', case_ref: 'case-beta-02', patient_id: patientB.id, modality: 'DSA' },
    { id: 'c', case_ref: 'CASE-GAMMA-03', patient_id: patientA.id, modality: 'DSA' },
  ]

  assert.deepEqual(filterCases(records, patientsById, 'alpha-0', 'all').map((record) => record.id), ['a'])
  assert.deepEqual(filterCases(records, patientsById, 'study-bet', 'all').map((record) => record.id), ['b'])
  assert.deepEqual(filterCases(records, patientsById, 'case', 'DSA').map((record) => record.id), ['b', 'c'])
  assert.deepEqual(filterCases(records, patientsById, 'PT-alpha', 'DSA').map((record) => record.id), ['c'])
  assert.deepEqual(filterCases(records, patientsById, 'CTA', 'all'), [])
  assert.deepEqual(filterCases(records, patientsById, '', 'CTA').map((record) => record.id), ['a'])
  assert.deepEqual(filterCases(records, patientsById, '', 'all').map((record) => record.id), ['a', 'b', 'c'])
})

test('Case ID values retain their clickable control and use the table accent blue in both themes', () => {
  assert.match(cases, /className="case-ref-button"/)
  assert.ok(styles.includes('.patients-table-panel .case-ref-button,\n.case-table-panel .case-ref-button { color: #176fd3; }'))
  assert.ok(styles.includes('html[data-theme="dark"] .patients-table-panel .case-ref-button,\nhtml[data-theme="dark"] .case-table-panel .case-ref-button { color: #8bb8ec; }'))
})

test('Case details content scrolls inside a fixed-height panel beneath its non-scrolling header', () => {
  assert.match(styles, /\.cases-bottom-grid > \.case-details-panel \{ height: 230px; min-height: 230px; max-height: 230px; overflow: hidden; \}/)
  assert.match(styles, /\.case-details-panel > \.case-detail-list \{ flex: 1 1 0; min-height: 0; overflow-y: auto;/)
  assert.match(styles, /\.cases-bottom-grid > \.case-details-panel > \.panel__heading,[\s\S]*?flex: 0 0 48px;/)
  assert.match(styles, /html\[data-theme="dark"\] \.case-details-panel > \.case-detail-list/)
  assert.match(styles, /\.cases-bottom-grid > \.case-images-panel \{ border-top-color: #aaa4e5; \}/)
})

test('Cases layout fits desktop height, keeps both detail panels visible, and restores natural scrolling on smaller screens', () => {
  assert.match(styles, /\.app-body:has\(\.cases-page\)[\s\S]*?height: calc\(100dvh - 70px\);[\s\S]*?overflow: hidden;/)
  assert.match(styles, /\.cases-page \{[\s\S]*?height: 100%;[\s\S]*?min-height: 0;[\s\S]*?overflow: hidden;/)
  assert.match(styles, /\.case-table-panel \.case-table-wrap \{[\s\S]*?flex: 1 1 0;[\s\S]*?overflow: auto;/)
  assert.match(styles, /\.cases-bottom-grid \{[\s\S]*?flex: 0 0 clamp\(180px, 25vh, 225px\);/)
  assert.match(styles, /\.cases-bottom-grid > \.case-details-panel,[\s\S]*?height: auto;[\s\S]*?min-height: 0;/)
  assert.match(styles, /@media \(max-width: 880px\)[\s\S]*?\.app-body:has\(\.cases-page\)[\s\S]*?overflow: visible;[\s\S]*?\.cases-page \{ height: auto;/)
})
