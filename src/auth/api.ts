export type ApiError = Error & { status: number }

const TOKEN_KEY = 'access_token'

export function getAccessToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setAccessToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearAccessToken() {
  localStorage.removeItem(TOKEN_KEY)
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const token = getAccessToken()
  if (token && path !== '/auth/login') headers.set('Authorization', `Bearer ${token}`)

  const response = await fetch(`/api/v1${path}`, { ...init, headers })
  const payload = await response.json().catch(() => null)
  if (response.status === 401 && path !== '/auth/login') {
    clearAccessToken()
    window.dispatchEvent(new Event('auth:unauthorized'))
  }
  if (!response.ok) {
    const detail = payload?.detail
    const message = typeof detail === 'string'
      ? detail
      : Array.isArray(detail)
        ? detail.map((item: { msg?: string }) => item.msg ?? 'Invalid input').join(', ')
        : `Request failed (${response.status})`
    const error = new Error(message) as ApiError
    error.status = response.status
    throw error
  }
  return payload as T
}

export async function apiRequestBlob(path: string): Promise<Blob> {
  const headers = new Headers()
  const token = getAccessToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const response = await fetch(`/api/v1${path}`, { headers })
  if (response.status === 401) {
    clearAccessToken()
    window.dispatchEvent(new Event('auth:unauthorized'))
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    const error = new Error(typeof payload?.detail === 'string' ? payload.detail : `Request failed (${response.status})`) as ApiError
    error.status = response.status
    throw error
  }
  return response.blob()
}
