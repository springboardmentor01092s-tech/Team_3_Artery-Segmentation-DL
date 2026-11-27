import { useEffect, useState, type FormEvent } from 'react'
import { Check, Eye, EyeOff, Laptop, Moon, Sun } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import Panel from '../components/Panel'
import { useAuth, type AuthUser } from '../auth/AuthProvider'
import { apiRequest } from '../auth/api'
import { useNotifications } from '../features/notifications/NotificationProvider'
import { useWorkspacePreferences } from '../preferences/WorkspacePreferencesProvider'
import { validatePasswordChange } from '../preferences/workspace-preferences.mjs'

type PasswordFields = { current: string; next: string; confirmation: string }

export default function SettingsPage() {
  const { user, updateUser, logout } = useAuth()
  const { preferences, updatePreferences } = useWorkspacePreferences()
  const { addMessageNotification } = useNotifications()
  const navigate = useNavigate()
  const [nameDraft, setNameDraft] = useState(user?.full_name ?? '')
  const [emailDraft, setEmailDraft] = useState(user?.email ?? '')
  const [profileEditing, setProfileEditing] = useState(false)
  const [profileLoading, setProfileLoading] = useState(false)
  const [profileError, setProfileError] = useState('')
  const [password, setPassword] = useState<PasswordFields>({ current: '', next: '', confirmation: '' })
  const [visiblePasswords, setVisiblePasswords] = useState({ current: false, next: false, confirmation: false })
  const [passwordLoading, setPasswordLoading] = useState(false)
  const [passwordError, setPasswordError] = useState('')

  useEffect(() => {
    setNameDraft(user?.full_name ?? '')
    setEmailDraft(user?.email ?? '')
  }, [user?.full_name, user?.email])

  const normalizedDraft = nameDraft.trim()
  const normalizedEmailDraft = emailDraft.trim().toLowerCase()
  const normalizedName = user?.full_name?.trim() ?? ''
  const normalizedEmail = user?.email.trim().toLowerCase() ?? ''
  const nameChanged = normalizedDraft !== normalizedName
  const emailChanged = normalizedEmailDraft !== normalizedEmail
  const profileDirty = nameChanged || emailChanged

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setProfileError('')
    if (!profileDirty) {
      setNameDraft(user?.full_name ?? '')
      setEmailDraft(user?.email ?? '')
      setProfileEditing(false)
      return
    }
    if (nameChanged && !normalizedDraft) {
      setProfileError('Enter your full name.')
      return
    }
    if (emailChanged && !normalizedEmailDraft) {
      setProfileError('Enter your email address.')
      return
    }
    const profilePayload = {
      ...(nameChanged ? { full_name: normalizedDraft } : {}),
      ...(emailChanged ? { email: normalizedEmailDraft } : {}),
    }
    setProfileLoading(true)
    try {
      const updated = await apiRequest<AuthUser & { email_verification_sent?: boolean }>('/auth/me/profile', {
        method: 'PATCH',
        body: JSON.stringify(profilePayload),
      })
      updateUser(updated)
      setNameDraft(updated.full_name ?? normalizedDraft)
      setEmailDraft(updated.email)
      setProfileEditing(false)
      addMessageNotification(updated.email_verification_sent
        ? 'Changes saved. Verify the new email address to finish updating it.'
        : 'Changes saved')
    } catch (cause) {
      setProfileError(cause instanceof Error ? cause.message : 'Profile could not be saved.')
    } finally {
      setProfileLoading(false)
    }
  }

  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setPasswordError('')
    const validation = validatePasswordChange(password.current, password.next, password.confirmation)
    if (validation) {
      setPasswordError(validation)
      return
    }
    setPasswordLoading(true)
    try {
      await apiRequest<AuthUser>('/auth/change-password', {
        method: 'POST',
        body: JSON.stringify({ current_password: password.current, new_password: password.next }),
      })
      setPassword({ current: '', next: '', confirmation: '' })
      logout()
      navigate('/login?passwordChanged=1', { replace: true })
    } catch (cause) {
      setPasswordError(cause instanceof Error ? cause.message : 'Password could not be changed.')
    } finally {
      setPasswordLoading(false)
    }
  }

  function toggleVisibility(field: keyof PasswordFields) {
    setVisiblePasswords((current) => ({ ...current, [field]: !current[field] }))
  }

  return (
    <div className="feature-page settings-page settings-page--redesigned">
      <div className="settings-layout settings-layout--redesigned">
        <div className="settings-main-column">
          <Panel title="Account" className="settings-profile-panel settings-themed-panel settings-themed-panel--blue">
            <form className="settings-profile-form" onSubmit={saveProfile}>
              <div className="settings-profile-identity">
                <span className="settings-avatar" aria-hidden="true">{(user?.full_name?.trim() || user?.email || 'U').slice(0, 1).toUpperCase()}</span>
                <div><strong>{user?.full_name?.trim() || 'Name not provided'}</strong><span>{user?.email}</span></div>
                <span className={`settings-role-badge ${user?.role === 'admin' ? 'settings-role-badge--admin' : ''}`}>{user?.role === 'admin' ? 'Administrator' : 'Regular User'}</span>
              </div>
              <div className="settings-profile-fields">
                {profileEditing ? <>
                  <label className="settings-field">Full name
                    <input value={nameDraft} onChange={(event) => setNameDraft(event.target.value)} maxLength={120} autoComplete="name" aria-label="Full name" />
                  </label>
                  <label className="settings-field">Email address
                    <input type="email" value={emailDraft} onChange={(event) => setEmailDraft(event.target.value)} maxLength={320} autoComplete="email" aria-label="Email address" required />
                  </label>
                </> : <>
                  <div className="settings-readonly"><span>Full name</span><strong>{user?.full_name?.trim() || 'Name not provided'}</strong></div>
                  <div className="settings-readonly"><span>Email address</span><strong>{user?.email ?? 'Not available'}</strong></div>
                </>}
                <div className="settings-readonly"><span>Role</span><strong>{user?.role === 'admin' ? 'Administrator' : 'Regular User'}</strong></div>
                <div className="settings-readonly"><span>Account status</span><strong>{user?.is_active ? 'Active' : 'Inactive'}</strong></div>
              </div>
              {profileError && <p className="settings-feedback settings-feedback--error" role="alert">{profileError}</p>}
              <div className="settings-form-actions">
                {profileEditing
                  ? <button className="button button--primary button--small" type="submit" disabled={profileLoading}>{profileLoading ? 'Saving…' : 'Save profile'}</button>
                  : <button className="button button--secondary button--small" type="button" onClick={() => { setNameDraft(user?.full_name ?? ''); setEmailDraft(user?.email ?? ''); setProfileError(''); setProfileEditing(true) }}>Edit profile</button>}
              </div>
            </form>
          </Panel>

          <Panel title="Workspace Preferences" className="settings-workspace-panel settings-themed-panel settings-themed-panel--violet">
            <p className="settings-section-description settings-workspace-description">Choose the first page to open after you sign in. This preference is stored only for your account in this browser.</p>
            <label className="settings-field">Default landing page
              <select value={preferences.defaultLandingPage} onChange={(event) => updatePreferences({ defaultLandingPage: event.target.value as '/dashboard' | '/patients' | '/cases' })} aria-label="Default landing page">
                <option value="/dashboard">Dashboard</option><option value="/patients">Patients</option><option value="/cases">Cases</option>
              </select>
            </label>
          </Panel>
        </div>

        <div className="settings-side-column">
          <Panel title="Change password" className="settings-security-panel settings-themed-panel settings-themed-panel--teal">
            <form className="settings-password-form" onSubmit={changePassword}>
              {([
                ['current', 'Current password', 'current-password'],
                ['next', 'New password', 'new-password'],
                ['confirmation', 'Confirm new password', 'new-password'],
              ] as const).map(([field, label, autocomplete]) => (
                <label className="settings-field" key={field}>{label}
                  <span className="settings-password-input">
                    <input type={visiblePasswords[field] ? 'text' : 'password'} value={password[field]} onChange={(event) => setPassword((current) => ({ ...current, [field]: event.target.value }))} autoComplete={autocomplete} minLength={field === 'current' ? 1 : 12} maxLength={128} required aria-label={label} />
                    <button type="button" className="settings-password-visibility" onClick={() => toggleVisibility(field)} aria-label={`${visiblePasswords[field] ? 'Hide' : 'Show'} ${label.toLowerCase()}`}>
                      {visiblePasswords[field] ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </span>
                </label>
              ))}
              <small className="settings-password-note">Use 12–128 characters. The current password must be correct; successful changes require signing in again.</small>
              {passwordError && <p className="settings-feedback settings-feedback--error" role="alert">{passwordError}</p>}
              <div className="settings-form-actions"><button className="button button--primary button--small" type="submit" disabled={passwordLoading}>{passwordLoading ? 'Updating…' : 'Change password'}</button></div>
            </form>
          </Panel>

          <Panel title="Appearance" className="settings-appearance-panel settings-themed-panel settings-themed-panel--blue">
            <div className="settings-choice-list" role="group" aria-label="Color theme">
              {([
                ['light', 'Light', <Sun size={17} key="light" />],
                ['dark', 'Dark', <Moon size={17} key="dark" />],
                ['system', 'System', <Laptop size={17} key="system" />],
              ] as const).map(([value, label, icon]) => (
                <button className={`settings-choice ${preferences.theme === value ? 'settings-choice--selected' : ''}`} key={value} type="button" aria-pressed={preferences.theme === value} onClick={() => updatePreferences({ theme: value })}>
                  {icon}<span>{label}</span>{preferences.theme === value && <Check size={15} className="settings-choice-check" />}
                </button>
              ))}
            </div>
            <p className="settings-appearance-description">Theme applies across the application and follows your operating-system preference when System is selected.</p>
          </Panel>
        </div>
      </div>
    </div>
  )
}
