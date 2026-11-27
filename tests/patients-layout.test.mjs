import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const patients = await readFile(new URL('../src/pages/PatientsPage.tsx', import.meta.url), 'utf8')
const styles = await readFile(new URL('../src/styles.css', import.meta.url), 'utf8')
const appShell = await readFile(new URL('../src/components/AppShell.tsx', import.meta.url), 'utf8')

test('Patients page uses the compact tabs-and-action toolbar without the removed heading or import action', () => {
  assert.match(patients, /className="patients-toolbar"[\s\S]*?role="tablist"[\s\S]*?Add new patient/)
  assert.doesNotMatch(patients, /PageHeader|Patient Management|Manage patient records and their imaging cases|Import patient data|Download size=/)
})

test('Patients table spans its own full-width panel and retains real filters, columns, pagination and actions', () => {
  assert.match(patients, /<Panel title=\{`Patients \(\$\{patients\.length\}\)`\} className="patients-table-panel" action=/)
  for (const column of ['Patient reference', 'No. of cases', 'Created on', 'Created By', 'Actions']) assert.match(patients, new RegExp(column))
  assert.match(patients, /aria-label="Search patients"/)
  assert.match(patients, /aria-label="Next page"/)
  assert.match(patients, /onClick=\{\(\) => void openPatient\(patient\.id\)\}/)
  assert.match(patients, /updatePatient\(selectedPatient\.id, payload\)/)
  assert.match(patients, /className="patients-table-panel"/)
})

test('Patients table heading uses a blue rounded header box while retaining black heading text and search placement', () => {
  assert.match(patients, /<Panel title=\{`Patients \(\$\{patients\.length\}\)`\} className="patients-table-panel" action=\{<label className="patient-table-search"/)
  assert.match(styles, /\.patients-table-panel \.panel__heading > h2 \{[\s\S]*?min-height: 48px;[\s\S]*?padding: 0 12px;[\s\S]*?border: 1px solid #8bb8ec;[\s\S]*?border-radius: 9px;[\s\S]*?background: #eff6ff;/)
  assert.doesNotMatch(styles.match(/\.patients-table-panel \.panel__heading > h2 \{([^}]+)\}/)?.[1] ?? '', /color:/)
  assert.match(styles, /html\[data-theme="dark"\] \.patients-table-panel \.panel__heading > h2 \{ border-color: #527ead; background: #233a53; \}/)
})

test('patient detail and associated-case panels share an equal two-column bottom grid', () => {
  assert.match(patients, /className="patients-bottom-grid"[\s\S]*?className="patient-details-panel"[\s\S]*?className="patient-cases-panel"/)
  assert.match(patients, /No patient selected|Select a patient/)
  assert.match(styles, /\.patients-bottom-grid \{ display: grid; grid-template-columns: repeat\(2, minmax\(0, 1fr\)\); gap: 13px; align-items: stretch; \}/)
  assert.match(styles, /\.patients-bottom-grid > \.panel \{ display: flex; min-width: 0; min-height: 190px; flex-direction: column; \}/)
  assert.match(styles, /\.patient-details-panel \{ border-top-color: #79c8b7; \}/)
  assert.match(styles, /\.patient-cases-panel \{ border-top-color: #aaa4e5; \}/)
  assert.match(styles, /@media \(max-width: 640px\)[\s\S]*?\.patients-bottom-grid \{ grid-template-columns: minmax\(0, 1fr\); \}/)
})

test('the empty toolbar box is removed while patient search remains accessible and the case dropdown uses full width', () => {
  assert.match(patients, /className="patient-table-search"[^>]*>[\s\S]*?aria-label="Search patients"/)
  assert.match(patients, /className="list-toolbar patient-case-filter-toolbar">\s*<select aria-label="Filter patients by case association"/)
  assert.doesNotMatch(patients, /patient-case-filter-toolbar">\s*<input/)
  assert.match(styles, /\.patients-table-panel \.patient-case-filter-toolbar \{ display: block; width: 100%; margin-bottom: 10px; \}/)
  assert.match(styles, /\.patients-table-panel \.patient-case-filter-toolbar select \{ display: block; width: 100%; \}/)
})

test('patient columns use explicit shared boundaries and semantic alignment classes', () => {
  assert.match(patients, /<colgroup><col className="patient-col-reference" \/><col className="patient-col-cases" \/><col className="patient-col-created" \/><col className="patient-col-owner" \/><col className="patient-col-actions" \/><\/colgroup>/)
  for (let index = 1; index <= 5; index++) {
    assert.match(patients, new RegExp(`patient-table__cell-${index}`))
  }
  assert.match(styles, /\.patients-table-panel \.patient-table \{ width: 100%; min-width: 600px; table-layout: fixed;/)
  assert.match(styles, /\.patient-table \.patient-table__cell-1 \{ text-align: left; \}/)
  assert.match(styles, /\.patient-table \.patient-table__cell-2 \{ text-align: center; \}/)
  assert.match(styles, /\.patient-table \.patient-table__cell-3,[\s\S]*?\.patient-table \.patient-table__cell-4 \{ text-align: left; \}/)
  assert.match(styles, /\.patient-table \.patient-table__cell-5 \{ text-align: right; \}/)
})

test('Patient Reference values use the table accent blue in both themes', () => {
  assert.match(patients, /className="case-ref-button"/)
  assert.ok(styles.includes('.patients-table-panel .case-ref-button,\n.case-table-panel .case-ref-button { color: #176fd3; }'))
  assert.ok(styles.includes('html[data-theme="dark"] .patients-table-panel .case-ref-button,\nhtml[data-theme="dark"] .case-table-panel .case-ref-button { color: #8bb8ec; }'))
})

test('Patients list scrolls internally with a sticky header and three visible rows; pagination remains outside', () => {
  assert.match(patients, /<div className=\{`data-table-wrap patient-table-wrap[\s\S]*?<\/div>\s*<div className="table-pagination">/)
  assert.match(styles, /\.patients-table-panel \.patient-table-wrap \{ max-height: 169px; overflow: auto;/)
  assert.match(styles, /\.patient-table thead th \{ position: sticky; top: 0;/)
  assert.match(styles, /\.patient-table tbody tr \{ height: 44px; \}/)
  assert.match(styles, /\.patients-table-panel \.patient-table-wrap--message \{ max-height: none; \}/)
})

test('Patients layout fits desktop height, keeps its bottom panels visible, and restores natural scrolling on smaller screens', () => {
  assert.match(styles, /\.app-body:has\(\.patients-page\)[\s\S]*?height: calc\(100dvh - 70px\);[\s\S]*?overflow: hidden;/)
  assert.match(styles, /\.patients-page,[\s\S]*?height: 100%;[\s\S]*?min-height: 0;[\s\S]*?overflow: hidden;/)
  assert.match(styles, /\.patients-table-panel \.patient-table-wrap,[\s\S]*?flex: 1 1 0;[\s\S]*?overflow: auto;/)
  assert.match(styles, /\.patients-bottom-grid,[\s\S]*?flex: 0 0 clamp\(180px, 25vh, 225px\);/)
  assert.match(styles, /@media \(max-width: 880px\)[\s\S]*?\.app-body:has\(\.patients-page\)[\s\S]*?overflow: visible;[\s\S]*?\.patients-page,[\s\S]*?height: auto;/)
})

test('bottom panel headers have matching height, separate tinted content bands, and dark theme colors', () => {
  assert.match(styles, /\.patients-bottom-grid > \.patient-details-panel > \.panel__heading,[\s\S]*?flex: 0 0 48px;[\s\S]*?min-height: 48px;/)
  assert.match(styles, /\.patients-bottom-grid > \.patient-details-panel > \.panel__heading \{ border-color: #d7eee9; background: #f0faf7; \}/)
  assert.match(styles, /\.patients-bottom-grid > \.patient-cases-panel > \.panel__heading \{ border-color: #e6e2f7; background: #f7f5fd; \}/)
  assert.match(styles, /html\[data-theme="dark"\] \.patients-bottom-grid > \.patient-details-panel > \.panel__heading/)
  assert.match(styles, /html\[data-theme="dark"\] \.patients-bottom-grid > \.patient-cases-panel > \.panel__heading/)
})

test('authenticated typography follows the Dashboard DM Sans family while keeping the public login styles separate', () => {
  assert.match(styles, /:root \{\s*font-family: 'DM Sans', Inter, ui-sans-serif/s)
  assert.match(styles, /\.app-frame \{\s*font-family: 'DM Sans', Inter, ui-sans-serif/s)
  assert.match(styles, /\.app-frame :is\([\s\S]*?\.panel__heading h2[\s\S]*?font-family: 'DM Sans', Inter/s)
  assert.match(styles, /\.login-intro h1 \{[^}]*Manrope/s)
})

test('Patients cards keep colored accents and readable dark-theme surfaces', () => {
  assert.match(styles, /\.patients-table-panel,\s*\.patient-details-panel,\s*\.patient-cases-panel \{[\s\S]*?border-top: 2px solid #8bb8ec/)
  assert.match(styles, /\.patient-details-panel \{ border-top-color: #79c8b7; \}/)
  assert.match(styles, /\.patient-cases-panel \{ border-top-color: #aaa4e5; \}/)
  assert.match(styles, /html\[data-theme="dark"\] \.patients-table-panel/)
  assert.match(styles, /html\[data-theme="dark"\] \.patient-details-panel/)
  assert.match(styles, /html\[data-theme="dark"\] \.patient-cases-panel/)
})

test('sidebar starts collapsed when no current preference exists and keeps its responsive toggle behavior', () => {
  assert.match(appShell, /artery-analysis:sidebar-collapsed:v2/)
  assert.match(appShell, /preference === null \? true : preference === 'true'/)
  assert.match(appShell, /function toggleSidebar\(\)[\s\S]*if \(isNarrowViewport\) setIsMobileOpen[\s\S]*setIsCollapsed/)
  assert.match(appShell, /matchMedia\('\(max-width: 880px\)'\)/)
})
