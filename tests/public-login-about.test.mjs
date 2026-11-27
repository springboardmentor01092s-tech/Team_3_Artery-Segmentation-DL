import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { resolveRouteTheme } from '../src/preferences/workspace-preferences.mjs'

const login = await readFile(new URL('../src/pages/LoginPage.tsx', import.meta.url), 'utf8')
const illustration = await readFile(new URL('../src/components/DecorativeArt.tsx', import.meta.url), 'utf8')
const publicHeader = await readFile(new URL('../src/components/PublicHeader.tsx', import.meta.url), 'utf8')
const about = await readFile(new URL('../src/pages/AboutPage.tsx', import.meta.url), 'utf8')
const app = await readFile(new URL('../src/App.tsx', import.meta.url), 'utf8')
const preferences = await readFile(new URL('../src/preferences/WorkspacePreferencesProvider.tsx', import.meta.url), 'utf8')

test('login omits the retired hero labels and keeps the artery illustration', () => {
  assert.doesNotMatch(login, /ARTERY IMAGING WORKSPACE|Secure image workspace|Research preview/)
  assert.doesNotMatch(illustration, /IMAGE WORKSPACE|ANALYSIS PREVIEW|NOT CONFIGURED/)
  assert.match(illustration, /Decorative abstract artery illustration/)
  assert.match(illustration, /<svg viewBox="0 0 520 260"/)
})

test('login card ends after institution sign-in and retains its login controls', () => {
  assert.doesNotMatch(login, /Preview the dashboard|Frontend layout only|Secure access is available/)
  assert.match(login, /id="email" name="email" type="email"/)
  assert.match(login, /id="password"/)
  assert.match(login, /Show password|Hide password/)
  assert.match(login, /name="remember"/)
  assert.match(login, /Forgot password\?/)
  assert.match(login, /Sign in with an institution/)
  assert.match(login, /<\/button>\s*<\/section>/)
})

test('public navigation removes Home, links About, and keeps Contact visibly disabled', () => {
  assert.doesNotMatch(publicHeader, />Home</)
  assert.match(publicHeader, /to="\/about"/)
  assert.match(publicHeader, /<Info size=\{16\}/)
  assert.match(publicHeader, /aria-disabled="true"/)
  assert.match(publicHeader, /<Mail size=\{16\}/)
  assert.doesNotMatch(publicHeader, /href="mailto:|to="\/contact"/)
})

test('About is a public route with requested description, prototype disclaimer, and login return link', () => {
  assert.match(app, /<Route path="\/about" element=\{<AboutPage \/>\} \/>/)
  assert.match(about, /Artery Analysis System/)
  assert.match(about, /research-oriented web application/)
  assert.match(about, /AI-assisted research and decision-support prototype/)
  assert.match(about, /not an autonomous diagnostic system/)
  assert.match(about, /not been clinically validated/)
  assert.match(about, /to="\/login">[\s\S]*Back to Login/)
})

test('login remains light without changing the saved workspace theme', () => {
  assert.equal(resolveRouteTheme('/login', 'dark'), 'light')
  assert.equal(resolveRouteTheme('/login', 'light'), 'light')
  assert.match(preferences, /root\.dataset\.theme = resolveRouteTheme\(location\.pathname, resolvedTheme\)/)
  assert.match(preferences, /writeWorkspacePreferences\(userId, next\)/)
})
