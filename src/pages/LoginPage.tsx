
import { useState, type FormEvent } from 'react'
import { ArrowRight, Eye, EyeOff, LockKeyhole, Mail, UsersRound } from 'lucide-react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import Brand from '../components/Brand'
import { ArteryIllustration } from '../components/DecorativeArt'
import { useAuth } from '../auth/AuthProvider'

export default function LoginPage() {
  const [showPassword, setShowPassword] = useState(false)
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const { login } = useAuth()

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setMessage('')
    setLoading(true)

    const formData = new FormData(event.currentTarget)
    const email = String(formData.get('email') ?? '').trim()
    const password = String(formData.get('password') ?? '')

    try {
      await login(email, password)
      const from = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname
      navigate(from && from !== '/login' ? from : '/dashboard', { replace: true })
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
      <header className="login-header">
        <Link to="/login" className="login-header__brand"><Brand /></Link>
        <nav aria-label="Public navigation">
          <a href="#home">Home</a>
          <a href="#about">About</a>
          <a href="mailto:support@example.org">Contact</a>
        </nav>
      </header>

      <main className="login-main" id="home">
        <section className="login-intro" id="about">
          <div className="eyebrow"><span className="eyebrow__dot" /> ARTERY IMAGING WORKSPACE</div>
          <h1>Artery segmentation<br />and stenosis detection</h1>
          <p className="login-intro__lead">
            A focused workspace for organizing angiography images and reviewing analysis when a validated model is available.
          </p>
          <ArteryIllustration />
          <div className="login-intro__caption">
            <span className="caption-dot" /> Secure image workspace <span className="caption-divider">·</span> Research preview
          </div>
        </section>

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
          <div className="login-preview">
            <Link to="/dashboard">Preview the dashboard <ArrowRight size={14} aria-hidden="true" /></Link>
            <span>Frontend layout only</span>
          </div>
          <p className="login-card__privacy">
            <LockKeyhole size={13} aria-hidden="true" /> Secure access is available to administrator-created accounts.
          </p>
        </section>
      </main>

      <footer className="login-footer">
        <span>© 2026 Artery Analysis System</span>
        <div><a href="#privacy">Privacy</a><span /> <a href="#terms">Terms</a><span /> <a href="mailto:support@example.org">Help</a></div>
      </footer>
    </div>
  )
}
