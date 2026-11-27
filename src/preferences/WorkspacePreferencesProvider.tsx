import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useState, type ReactNode } from 'react'
import { useLocation } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'
import {
  DEFAULT_WORKSPACE_PREFERENCES,
  readWorkspacePreferences,
  resolveReducedMotion,
  resolveRouteTheme,
  resolveTheme,
  writeWorkspacePreferences,
  type DensityPreference,
  type LandingPagePreference,
  type ThemePreference,
  type WorkspacePreferences,
} from './workspace-preferences.mjs'

type PreferenceContextValue = {
  preferences: WorkspacePreferences
  resolvedTheme: 'light' | 'dark'
  reducedMotionEnabled: boolean
  updatePreferences: (changes: Partial<WorkspacePreferences>) => void
}

const PreferencesContext = createContext<PreferenceContextValue | null>(null)

function useSystemPreference(query: string) {
  const [matches, setMatches] = useState(() => typeof window !== 'undefined' && window.matchMedia(query).matches)
  useEffect(() => {
    if (typeof window === 'undefined') return
    const media = window.matchMedia(query)
    const update = (event: MediaQueryListEvent) => setMatches(event.matches)
    setMatches(media.matches)
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [query])
  return matches
}

export function WorkspacePreferencesProvider({ children }: { children: ReactNode }) {
  const { user, isLoading } = useAuth()
  const location = useLocation()
  const [storedState, setStoredState] = useState<{ userId: string | null; value: WorkspacePreferences }>({
    userId: null,
    value: { ...DEFAULT_WORKSPACE_PREFERENCES },
  })
  const systemPrefersDark = useSystemPreference('(prefers-color-scheme: dark)')
  const systemPrefersReducedMotion = useSystemPreference('(prefers-reduced-motion: reduce)')
  const userId = user?.id ?? null
  const preferences = userId
    ? storedState.userId === userId ? storedState.value : readWorkspacePreferences(userId)
    : DEFAULT_WORKSPACE_PREFERENCES

  useEffect(() => {
    if (isLoading) return
    if (!userId) {
      setStoredState({ userId: null, value: { ...DEFAULT_WORKSPACE_PREFERENCES } })
      return
    }
    setStoredState({ userId, value: readWorkspacePreferences(userId) })
  }, [isLoading, userId])

  const resolvedTheme = resolveTheme(preferences.theme, systemPrefersDark)
  const reducedMotionEnabled = resolveReducedMotion(preferences.reducedMotion, systemPrefersReducedMotion)

  useLayoutEffect(() => {
    const root = document.documentElement
    root.dataset.theme = resolveRouteTheme(location.pathname, resolvedTheme)
    root.dataset.density = preferences.density
    root.dataset.reducedMotion = String(reducedMotionEnabled)
  }, [location.pathname, resolvedTheme, preferences.density, reducedMotionEnabled])

  const updatePreferences = useCallback((changes: Partial<WorkspacePreferences>) => {
    if (!userId) return
    setStoredState((current) => {
      const base = current.userId === userId ? current.value : { ...DEFAULT_WORKSPACE_PREFERENCES }
      const next = { ...base, ...changes }
      writeWorkspacePreferences(userId, next)
      return { userId, value: next }
    })
  }, [userId])

  const value = useMemo(() => ({ preferences, resolvedTheme, reducedMotionEnabled, updatePreferences }), [preferences, resolvedTheme, reducedMotionEnabled, updatePreferences])
  return <PreferencesContext.Provider value={value}>{children}</PreferencesContext.Provider>
}

export function useWorkspacePreferences() {
  const context = useContext(PreferencesContext)
  if (!context) throw new Error('useWorkspacePreferences must be used within WorkspacePreferencesProvider')
  return context
}

export type { DensityPreference, LandingPagePreference, ThemePreference, WorkspacePreferences }
