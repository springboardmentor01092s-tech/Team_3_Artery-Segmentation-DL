import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from './AuthProvider'
import ForcedPasswordChange from './ForcedPasswordChange'

export default function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) return <div className="auth-loading" role="status">Checking your session…</div>
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />
  if (user.must_change_password) return <ForcedPasswordChange />
  return <>{children}</>
}
