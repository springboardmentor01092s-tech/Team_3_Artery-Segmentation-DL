export const DEFAULT_WORKSPACE_PREFERENCES = Object.freeze({
  theme: 'system',
  density: 'comfortable',
  reducedMotion: null,
  defaultLandingPage: '/dashboard',
})

const themes = new Set(['light', 'dark', 'system'])
const densities = new Set(['comfortable', 'compact'])
const landingPages = new Set(['/dashboard', '/patients', '/cases'])

export function workspacePreferenceKey(userId) {
  return `artery-analysis:preferences:v1:${userId}`
}

export function normalizeWorkspacePreferences(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return { ...DEFAULT_WORKSPACE_PREFERENCES }
  return {
    theme: themes.has(value.theme) ? value.theme : DEFAULT_WORKSPACE_PREFERENCES.theme,
    density: densities.has(value.density) ? value.density : DEFAULT_WORKSPACE_PREFERENCES.density,
    reducedMotion: typeof value.reducedMotion === 'boolean' ? value.reducedMotion : null,
    defaultLandingPage: landingPages.has(value.defaultLandingPage) ? value.defaultLandingPage : DEFAULT_WORKSPACE_PREFERENCES.defaultLandingPage,
  }
}

export function readWorkspacePreferences(userId, storage = globalThis.localStorage) {
  if (!userId || !storage) return { ...DEFAULT_WORKSPACE_PREFERENCES }
  try {
    const serialized = storage.getItem(workspacePreferenceKey(userId))
    return serialized ? normalizeWorkspacePreferences(JSON.parse(serialized)) : { ...DEFAULT_WORKSPACE_PREFERENCES }
  } catch {
    return { ...DEFAULT_WORKSPACE_PREFERENCES }
  }
}

export function writeWorkspacePreferences(userId, preferences, storage = globalThis.localStorage) {
  if (!userId || !storage) return false
  try {
    storage.setItem(workspacePreferenceKey(userId), JSON.stringify(normalizeWorkspacePreferences(preferences)))
    return true
  } catch {
    return false
  }
}

export function resolveTheme(theme, systemPrefersDark) {
  return theme === 'system' ? (systemPrefersDark ? 'dark' : 'light') : theme
}

export function resolveRouteTheme(pathname, resolvedTheme) {
  const route = pathname.replace(/\/+$/, '') || '/'
  return route === '/login' || route === '/about' || route === '/verify-email-change' ? 'light' : resolvedTheme
}

export function resolveReducedMotion(preference, systemPrefersReducedMotion) {
  return preference === null ? Boolean(systemPrefersReducedMotion) : preference
}

export function validatePasswordChange(currentPassword, newPassword, confirmation) {
  if (!currentPassword) return 'Enter your current password.'
  if (newPassword.length < 12 || newPassword.length > 128) return 'New password must be between 12 and 128 characters.'
  if (newPassword !== confirmation) return 'New password and confirmation do not match.'
  if (currentPassword === newPassword) return 'New password must be different from your current password.'
  return ''
}
