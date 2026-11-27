import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import {
  DEFAULT_WORKSPACE_PREFERENCES,
  normalizeWorkspacePreferences,
  readWorkspacePreferences,
  resolveReducedMotion,
  resolveRouteTheme,
  resolveTheme,
  validatePasswordChange,
  workspacePreferenceKey,
  writeWorkspacePreferences,
} from '../src/preferences/workspace-preferences.mjs'

const settingsPage = await readFile(new URL('../src/pages/SettingsPage.tsx', import.meta.url), 'utf8')
const provider = await readFile(new URL('../src/preferences/WorkspacePreferencesProvider.tsx', import.meta.url), 'utf8')
const styles = await readFile(new URL('../src/styles.css', import.meta.url), 'utf8')
const authProvider = await readFile(new URL('../src/auth/AuthProvider.tsx', import.meta.url), 'utf8')

function createMemoryStorage() {
  const values = new Map()
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
  }
}

test('workspace preferences persist independently for each authenticated user', () => {
  const storage = createMemoryStorage()
  const alice = { ...DEFAULT_WORKSPACE_PREFERENCES, theme: 'dark', density: 'compact', defaultLandingPage: '/cases' }
  const bob = { ...DEFAULT_WORKSPACE_PREFERENCES, theme: 'light', defaultLandingPage: '/patients' }
  assert.notEqual(workspacePreferenceKey('user-a'), workspacePreferenceKey('user-b'))
  assert.equal(writeWorkspacePreferences('user-a', alice, storage), true)
  assert.equal(writeWorkspacePreferences('user-b', bob, storage), true)
  assert.deepEqual(readWorkspacePreferences('user-a', storage), alice)
  assert.deepEqual(readWorkspacePreferences('user-b', storage), bob)
  assert.deepEqual(readWorkspacePreferences(null, storage), DEFAULT_WORKSPACE_PREFERENCES)
})

test('invalid or stale local preferences fall back to safe defaults and allowed landing pages', () => {
  const storage = createMemoryStorage()
  storage.setItem(workspacePreferenceKey('user-a'), JSON.stringify({ theme: 'neon', density: 'tiny', defaultLandingPage: '/users', reducedMotion: 'yes' }))
  assert.deepEqual(readWorkspacePreferences('user-a', storage), DEFAULT_WORKSPACE_PREFERENCES)
  assert.deepEqual(normalizeWorkspacePreferences({ theme: 'dark', density: 'compact', defaultLandingPage: '/cases' }), {
    theme: 'dark', density: 'compact', reducedMotion: null, defaultLandingPage: '/cases',
  })
})

test('system theme and reduced-motion settings resolve from operating-system values until overridden', () => {
  assert.equal(resolveTheme('system', true), 'dark')
  assert.equal(resolveTheme('system', false), 'light')
  assert.equal(resolveTheme('light', true), 'light')
  assert.equal(resolveReducedMotion(null, true), true)
  assert.equal(resolveReducedMotion(null, false), false)
  assert.equal(resolveReducedMotion(false, true), false)
  assert.match(provider, /addEventListener\('change', update\)/)
  assert.match(provider, /root\.dataset\.theme = resolveRouteTheme\(location\.pathname, resolvedTheme\)/)
  assert.match(provider, /root\.dataset\.density = preferences\.density/)
  assert.match(provider, /root\.dataset\.reducedMotion = String\(reducedMotionEnabled\)/)
})

test('login route always uses light mode while workspace theme resumes on other routes', () => {
  assert.equal(resolveRouteTheme('/login', 'dark'), 'light')
  assert.equal(resolveRouteTheme('/login', 'light'), 'light')
  assert.equal(resolveRouteTheme('/dashboard', 'dark'), 'dark')
  assert.equal(resolveRouteTheme('/results', 'light'), 'light')
  assert.match(provider, /useLocation\(\)/)
  assert.match(provider, /useLayoutEffect\(/)
  assert.match(provider, /readWorkspacePreferences\(userId\)/)
  assert.match(provider, /root\.dataset\.theme = resolveRouteTheme\(location\.pathname, resolvedTheme\)/)
})

test('password validation enforces backend length, confirmation, and current-password distinction', () => {
  assert.equal(validatePasswordChange('', 'a-new-long-password', 'a-new-long-password'), 'Enter your current password.')
  assert.match(validatePasswordChange('old-password', 'short', 'short'), /12 and 128 characters/)
  assert.match(validatePasswordChange('old-password', 'a-new-long-password', 'different'), /do not match/)
  assert.match(validatePasswordChange('same-long-password', 'same-long-password', 'same-long-password'), /different from your current/)
  assert.equal(validatePasswordChange('old-password', 'a-new-long-password', 'a-new-long-password'), '')
})

test('Settings exposes working profile, password, theme, density, motion, and landing controls', () => {
  assert.match(settingsPage, /apiRequest<AuthUser>\('\/auth\/me\/profile'/)
  assert.match(settingsPage, /apiRequest<AuthUser>\('\/auth\/change-password'/)
  assert.match(settingsPage, /aria-label="Full name"/)
  assert.match(settingsPage, /aria-label="Email address \(read only\)"/)
  assert.match(settingsPage, /aria-label="Color theme"/)
  assert.match(settingsPage, /aria-label="Display density"/)
  assert.match(settingsPage, /aria-label="Reduced motion"/)
  assert.match(settingsPage, /aria-label="Default landing page"/)
  assert.match(settingsPage, /backend notification retrieval is not connected to the bell/)
  assert.doesNotMatch(settingsPage, /Analysis status updates|Account activity.*checkbox/)
  assert.match(authProvider, /setUser\(null\)/)
  assert.match(styles, /html\[data-theme="dark"\]/)
  assert.match(styles, /html\[data-density="compact"\]/)
  assert.match(styles, /html\[data-reduced-motion="true"\]/)
})
