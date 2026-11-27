import { useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import PublicHeader from '../components/PublicHeader'
import { apiRequest } from '../auth/api'

type VerificationState = { status: 'loading' | 'success' | 'error'; message: string }

export default function VerifyEmailChangePage() {
  const location = useLocation()
  const started = useRef(false)
  const [state, setState] = useState<VerificationState>({ status: 'loading', message: 'Verifying your email address…' })

  useEffect(() => {
    if (started.current) return
    started.current = true
    const token = new URLSearchParams(location.hash.replace(/^#/, '')).get('token')
    window.history.replaceState(null, '', `${location.pathname}${location.search}`)
    if (!token) {
      setState({ status: 'error', message: 'This email verification link is missing or invalid.' })
      return
    }

    apiRequest<{ detail: string }>('/auth/verify-email-change', {
      method: 'POST',
      body: JSON.stringify({ token }),
    }).then((result) => {
      setState({ status: 'success', message: result.detail })
    }).catch(() => {
      setState({ status: 'error', message: 'This email verification link is invalid or expired. Request a new link from Settings.' })
    })
  }, [location.hash, location.pathname, location.search])

  return (
    <div className="about-page email-verification-page">
      <header className="login-header"><PublicHeader /></header>
      <main className="about-main">
        <article className="about-card" aria-live="polite">
          <p className="page-eyebrow">EMAIL VERIFICATION</p>
          <h1>{state.status === 'success' ? 'Email address verified' : 'Verify your email address'}</h1>
          <p>{state.message}</p>
          <Link className="about-back-link" to="/login">Back to Login</Link>
        </article>
      </main>
      <footer className="login-footer"><span>CoronAI Medical Imaging Research Workspace</span></footer>
    </div>
  )
}
