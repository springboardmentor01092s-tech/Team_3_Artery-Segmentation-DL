import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const topBar = await readFile(new URL('../src/components/TopBar.tsx', import.meta.url), 'utf8')
const sidebar = await readFile(new URL('../src/components/Sidebar.tsx', import.meta.url), 'utf8')
const styles = await readFile(new URL('../src/styles.css', import.meta.url), 'utf8')

test('shared header keeps notifications and sign-out identity while removing search and dropdown affordance', () => {
  assert.doesNotMatch(topBar, /global-search|Search size|placeholder="Search cases|<kbd>/)
  assert.doesNotMatch(topBar, /ChevronDown/)
  assert.match(topBar, /aria-label="Notifications"/)
  assert.match(topBar, /onClick=\{handleLogout\}[\s\S]*aria-label="Sign out"/)
  assert.match(topBar, /user\?\.email/)
  assert.match(topBar, /Administrator|Regular user/)
  assert.match(styles, /\.profile-button__text small \{ font-size: 8px; white-space: nowrap; \}/)
})

test('sidebar no longer renders the workspace status footer', () => {
  assert.doesNotMatch(sidebar, /sidebar__footer|Private workspace|Backend connected|BellRing/)
  assert.match(sidebar, /aria-label="Main navigation"/)
  assert.doesNotMatch(styles, /\.sidebar__footer|\.sidebar__security-icon/)
})

test('shared header styles do not reserve space for the removed global search', () => {
  assert.match(styles, /\.topbar__brand \{ display: flex; align-items: center; width: auto;/)
  assert.doesNotMatch(styles, /\.global-search/)
})
