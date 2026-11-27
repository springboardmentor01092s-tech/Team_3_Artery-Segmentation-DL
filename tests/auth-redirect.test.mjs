import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const loginPage = await readFile(new URL('../src/pages/LoginPage.tsx', import.meta.url), 'utf8')
const protectedRoute = await readFile(new URL('../src/auth/ProtectedRoute.tsx', import.meta.url), 'utf8')
const authProvider = await readFile(new URL('../src/auth/AuthProvider.tsx', import.meta.url), 'utf8')

test('successful login uses the landing preference saved for the authenticated account', () => {
  assert.match(loginPage, /const authenticatedUser = await login\(email, password\)/)
  assert.match(loginPage, /readWorkspacePreferences\(authenticatedUser\.id\)\.defaultLandingPage/)
  assert.doesNotMatch(loginPage, /useLocation|location\.state|\.from\?\.pathname/)
  assert.doesNotMatch(loginPage, /navigate\('\/results'/)
  assert.match(authProvider, /Promise<AuthUser>/)
})

test('protected routes still send unauthenticated users to login with their requested location', () => {
  assert.match(protectedRoute, /if \(!user\) return <Navigate to="\/login" replace state=\{\{ from: location \}\} \/>/)
  assert.match(protectedRoute, /if \(isLoading\).*Checking your session/)
})

test('authentication still restores the current user and logout clears the session', () => {
  assert.match(authProvider, /setAccessToken\(result\.access_token\)/)
  assert.match(authProvider, /apiRequest<AuthUser>\('\/auth\/me'\)/)
  assert.match(authProvider, /const logout = useCallback\(\(\) => \{\s*clearAccessToken\(\)\s*setUser\(null\)/)
})
