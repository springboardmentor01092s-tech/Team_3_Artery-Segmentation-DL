import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { apiRequest, clearAccessToken, getAccessToken, setAccessToken } from './api'

export type AuthUser = {
  id: string
  email: string
  role: 'admin' | 'user'
  is_active: boolean
  created_at: string
}

type LoginResponse = { access_token: string; token_type: string; expires_in: number }
type AuthContextValue = {
  user: AuthUser | null
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isLoading, setIsLoading] = useState(Boolean(getAccessToken()))

  const logout = useCallback(() => {
    clearAccessToken()
    setUser(null)
    setIsLoading(false)
  }, [])

  useEffect(() => {
    const handleUnauthorized = () => {
      setUser(null)
      setIsLoading(false)
    }
    window.addEventListener('auth:unauthorized', handleUnauthorized)
    if (getAccessToken()) {
      apiRequest<AuthUser>('/auth/me')
        .then(setUser)
        .catch(() => {
          clearAccessToken()
          setUser(null)
        })
        .finally(() => setIsLoading(false))
    }
    return () => window.removeEventListener('auth:unauthorized', handleUnauthorized)
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const result = await apiRequest<LoginResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })
    if (!result.access_token) throw new Error('The server response did not include an access token.')
    setAccessToken(result.access_token)
    try {
      const authenticatedUser = await apiRequest<AuthUser>('/auth/me')
      setUser(authenticatedUser)
    } catch (error) {
      clearAccessToken()
      setUser(null)
      throw error
    }
  }, [])

  const value = useMemo(() => ({ user, isLoading, login, logout }), [user, isLoading, login, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within AuthProvider')
  return context
}
