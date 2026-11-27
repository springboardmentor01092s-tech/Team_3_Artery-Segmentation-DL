import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const appSource = await readFile(new URL('../src/App.tsx', import.meta.url), 'utf8')
const verifyPage = await readFile(new URL('../src/pages/VerifyEmailChangePage.tsx', import.meta.url), 'utf8')
const settingsPage = await readFile(new URL('../src/pages/SettingsPage.tsx', import.meta.url), 'utf8')

test('email verification has a public route and clears the fragment before submitting the token', () => {
  assert.match(appSource, /path="\/verify-email-change"\s+element=\{<VerifyEmailChangePage \/>\}/)
  const clearFragment = verifyPage.indexOf("window.history.replaceState(null, '', `${location.pathname}${location.search}`)")
  const sendRequest = verifyPage.indexOf("apiRequest<{ detail: string }>('/auth/verify-email-change'")
  assert.ok(clearFragment >= 0)
  assert.ok(sendRequest > clearFragment)
  assert.match(verifyPage, /body:\s*JSON\.stringify\(\{ token \}\)/)
  assert.doesNotMatch(verifyPage, /console\.(log|warn|error)\s*\(/)
})

test('Settings reports a pending verification instead of claiming the email changed immediately', () => {
  assert.match(settingsPage, /email_verification_sent\?: boolean/)
  assert.match(settingsPage, /Verify the new email address to finish updating it/)
})
