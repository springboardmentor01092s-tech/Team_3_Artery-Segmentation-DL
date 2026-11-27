import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { dispatchReportDownload } from '../src/features/reports/report-exports.mjs'

test('Reports UI has two full-width workflow panels and a single report-type-driven action', async () => {
  const source = await readFile(new URL('../src/pages/ReportsPage.tsx', import.meta.url), 'utf8')
  const styles = await readFile(new URL('../src/styles.css', import.meta.url), 'utf8')
  const panelTitles = [...source.matchAll(/<Panel title="([^"]+)"/g)].map((match) => match[1])
  assert.deepEqual(panelTitles, ['Select Analysis Run', 'Download Report'])
  assert.match(source, /<fieldset className="report-format-fieldset">[\s\S]*?reportFormats\.map\(\(format\)/)
  assert.match(source, /type="radio" name="report-format"/)
  assert.match(source, /Report notes \(optional\)/)
  assert.match(source, /Add notes for this report \(optional\)\.\.\./)
  assert.match(source, /onClick=\{generateReport\}/)
  assert.match(source, /function generateReport\(\)[\s\S]*?generatePdf\(\)[\s\S]*?generateJson\(\)[\s\S]*?generateCsv\(\)/)
  assert.doesNotMatch(source, /Report preview|Report contents|page-bottom-note|Report Generation|Preview and export a report/)
  assert.match(styles, /\.reports-selection-panel \.report-selectors \{[\s\S]*?grid-template-columns: repeat\(4, minmax\(0, 1fr\)\);/)
  assert.match(styles, /\.reports-download-panel \{ border-top-color: #8b63d1 !important;/)
  assert.match(styles, /\.report-format-options \{[\s\S]*?grid-template-columns: repeat\(3, minmax\(0, 1fr\)\);/)
  assert.match(styles, /\.reports-page \.generate-report-button \{[\s\S]*?margin: 18px auto 2px;/)
  assert.match(styles, /@media \(max-width: 880px\)[\s\S]*?\.reports-selection-panel \.report-selectors \{ grid-template-columns: repeat\(2, minmax\(0, 1fr\)\);/)
})

test('download notification is emitted only after download dispatch returns successfully', () => {
  const events = []
  dispatchReportDownload({
    format: 'CSV', filename: 'report.csv', blob: new Blob(['data']),
    download: (_blob, filename) => events.push(`download:${filename}`),
    notify: ({ format, filename }) => events.push(`notice:${format}:${filename}`),
  })
  assert.deepEqual(events, ['download:report.csv', 'notice:CSV:report.csv'])

  events.length = 0
  assert.throws(() => dispatchReportDownload({
    format: 'PDF', filename: 'report.pdf', blob: new Blob(['data']),
    download: () => { throw new Error('dispatch failed') },
    notify: () => events.push('notice'),
  }), /dispatch failed/)
  assert.deepEqual(events, [])
})
