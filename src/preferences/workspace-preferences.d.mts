export type ThemePreference = 'light' | 'dark' | 'system'
export type DensityPreference = 'comfortable' | 'compact'
export type LandingPagePreference = '/dashboard' | '/patients' | '/cases'
export type WorkspacePreferences = {
  theme: ThemePreference
  density: DensityPreference
  reducedMotion: boolean | null
  defaultLandingPage: LandingPagePreference
}

export const DEFAULT_WORKSPACE_PREFERENCES: Readonly<WorkspacePreferences>
export function workspacePreferenceKey(userId: string): string
export function normalizeWorkspacePreferences(value: unknown): WorkspacePreferences
export function readWorkspacePreferences(userId: string | null, storage?: Storage): WorkspacePreferences
export function writeWorkspacePreferences(userId: string | null, preferences: WorkspacePreferences, storage?: Storage): boolean
export function resolveTheme(theme: ThemePreference, systemPrefersDark: boolean): 'light' | 'dark'
export function resolveRouteTheme(pathname: string, resolvedTheme: 'light' | 'dark'): 'light' | 'dark'
export function resolveReducedMotion(preference: boolean | null, systemPrefersReducedMotion: boolean): boolean
export function validatePasswordChange(currentPassword: string, newPassword: string, confirmation: string): string
