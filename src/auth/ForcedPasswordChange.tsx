import { useState, type FormEvent } from 'react'
import { ArrowRight, LockKeyhole } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { apiRequest } from './api'
import { useAuth, type AuthUser } from './AuthProvider'

export default function ForcedPasswordChange() {
  const { logout } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const [isSaving, setIsSaving] = useState(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    const form = new FormData(event.currentTarget)
    const currentPassword = String(form.get('current_password') ?? '')
    const newPassword = String(form.get('new_password') ?? '')
    const confirmation = String(form.get('confirm_password') ?? '')
    if (newPassword !== confirmation) {
      setError('The new passwords do not match.')
      return
    }
    setIsSaving(true)
    try {
      await apiRequest<AuthUser>('/auth/change-password', {
        method: 'POST',
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      })
      logout()
      navigate('/login?passwordChanged=1', { replace: true })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to change the password. Please try again.')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <main className="forced-password-page">
      <section className="forced-password-card" aria-labelledby="forced-password-title">
        <span className="forced-password-icon"><LockKeyhole size={20} aria-hidden="true" /></span>
        <div className="eyebrow page-eyebrow">ACCOUNT SECURITY</div>
        <h1 id="forced-password-title">Change your temporary password</h1>
        <p>Your administrator set a temporary password. Choose a new password to continue. You will need to sign in again after it is updated.</p>
        <form className="case-form forced-password-form" onSubmit={submit}>
          <label>Current or temporary password <input name="current_password" type="password" autoComplete="current-password" maxLength={128} required /></label>
          <label>New password <input name="new_password" type="password" autoComplete="new-password" minLength={12} maxLength={128} required /></label>
          <label>Confirm new password <input name="confirm_password" type="password" autoComplete="new-password" minLength={12} maxLength={128} required /></label>
          {error && <p className="user-form-error" role="alert">{error}</p>}
          <button className="button button--primary forced-password-submit" type="submit" disabled={isSaving}>{isSaving ? 'Updating…' : 'Update password'} <ArrowRight size={16} /></button>
        </form>
      </section>
    </main>
  )
}
