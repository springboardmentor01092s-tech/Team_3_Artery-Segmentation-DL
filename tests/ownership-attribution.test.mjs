import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

test('Patients table displays saved owner name in Created By after Created On', async () => {
  const page = await readFile(new URL('../src/pages/PatientsPage.tsx', import.meta.url), 'utf8')
  assert.match(page, /'Created on', 'Created By', 'Actions'/)
  assert.match(page, /patient\.owner_name\?\.trim\(\) \|\| 'Not available'/)
})

test('Cases table replaces modality column with saved owner attribution', async () => {
  const page = await readFile(new URL('../src/pages/CasesPage.tsx', import.meta.url), 'utf8')
  assert.match(page, /'Patient reference', 'Created By', 'Images'/)
  assert.match(page, /record\.owner_name\?\.trim\(\) \|\| 'Not available'/)
  assert.doesNotMatch(page, /<td>\{record\.modality \|\| '—'\}<\/td>/)
})
