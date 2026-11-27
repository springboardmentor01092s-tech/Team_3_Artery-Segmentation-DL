
import { useState, type FormEvent } from 'react'
import { ArrowRight, Eye, EyeOff, LockKeyhole, Mail, UsersRound } from 'lucide-react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import PublicHeader from '../components/PublicHeader'
import Brand from '../components/Brand'
import { CoronaryHeartArtwork } from '../components/DecorativeArt'
import { useAuth } from '../auth/AuthProvider'
import { readWorkspacePreferences } from '../preferences/workspace-preferences.mjs'

export default function LoginPage() {
  const [showPassword, setShowPassword] = useState(false)
  const [searchParams] = useSearchParams()
  const passwordChanged = searchParams.get('passwordChanged') === '1'
  const [message, setMessage] = useState(passwordChanged ? 'Password updated. Sign in using your new password.' : '')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const { login } = useAuth()

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setMessage('')
    setLoading(true)

    const formData = new FormData(event.currentTarget)
    const email = String(formData.get('email') ?? '').trim()
    const password = String(formData.get('password') ?? '')

    try {
      const authenticatedUser = await login(email, password)
      navigate(readWorkspacePreferences(authenticatedUser.id).defaultLandingPage, { replace: true })
    } catch (error) {
      if (error instanceof Error && 'status' in error && error.status === 401) {
        setMessage('Invalid email or password.')
      } else if (error instanceof TypeError) {
        setMessage('Cannot reach the server. Please check that the backend is running.')
      } else {
        setMessage(error instanceof Error ? error.message : 'Unable to sign in. Please try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page">
      <section className="login-hero" aria-label="CoronAI medical imaging">
        <Link to="/login" className="login-hero__brand" aria-label="CoronAI login"><Brand /></Link>
        <div className="login-hero__copy">
          <p className="login-hero__eyebrow">MEDICAL IMAGING <span>•</span> ARTIFICIAL INTELLIGENCE</p>
          <h1>Advanced Artery<br /><span>Intelligence</span></h1>
          <p className="login-hero__description">AI-powered artery segmentation and stenosis analysis for intelligent medical image review.</p>
        </div>
        <CoronaryHeartArtwork />
      </section>

      <section className="login-stage">
        <header className="login-header login-stage__header">
          <PublicHeader showBrand={false} />
        </header>

        <main className="login-main">
          <section className="login-card" aria-labelledby="login-title">
          <div className="login-card__heading">
            <span className="login-card__icon"><LockKeyhole size={20} aria-hidden="true" /></span>
            <h2 id="login-title">Welcome back</h2>
            <p>Sign in to access your workspace</p>
          </div>

          <form className="login-form" onSubmit={handleSubmit}>
            <label className="field-label" htmlFor="email">Email address</label>
            <div className="input-wrap">
              <Mail size={18} aria-hidden="true" />
              <input id="email" name="email" type="email" placeholder="you@institution.org" autoComplete="username" required />
            </div>

            <div className="field-label-row">
              <label className="field-label" htmlFor="password">Password</label>
              <button
                className="text-button"
                type="button"
                onClick={() => setMessage('Password recovery is not configured yet. Contact your administrator.')}
              >
                Forgot password?
              </button>
            </div>

            <div className="input-wrap">
              <LockKeyhole size={18} aria-hidden="true" />
              <input
                id="password"
                name="password"
                type={showPassword ? 'text' : 'password'}
                placeholder="Enter your password"
                autoComplete="current-password"
                required
              />
              <button
                className="input-action"
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>

            <label className="remember-row">
              <input type="checkbox" name="remember" />
              <span>Remember me</span>
            </label>

            <button className="button button--primary login-submit" type="submit" disabled={loading}>
              {loading ? 'Signing in…' : 'Sign in'} <ArrowRight size={17} aria-hidden="true" />
            </button>

            {message && <p className="form-message" role="status">{message}</p>}
          </form>

          <div className="login-divider"><span /> <small>OR</small> <span /></div>
          <button
            className="button button--secondary institution-button"
            type="button"
            onClick={() => setMessage('Institutional sign-in is not configured yet.')}
          >
            <UsersRound size={18} aria-hidden="true" /> Sign in with an institution
          </button>
          </section>
        </main>

        <footer className="login-footer">
          <span>CoronAI Medical Imaging Research Workspace</span>
        </footer>
      </section>
    </div>
  )
}
