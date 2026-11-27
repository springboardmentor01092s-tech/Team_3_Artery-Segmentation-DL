import { useRef, useState, type FormEvent } from 'react'
import { Bell, ChartNoAxesColumn, Folder, Image as ImageIcon, Layers, Mail, Trash2, UserRound, UsersRound, X } from 'lucide-react'
import type { UserManagementRecord } from './user-management.mjs'

export type UserDialogMode = 'create' | 'role' | 'status' | 'reset' | 'delete'
export type CreateUserInput = { full_name: string; email: string; password: string; role: 'admin' | 'user' }

export default function UserManagementDialog({
  mode,
  user,
  nextRole,
  onClose,
  onCreate,
  onUpdateRole,
  onUpdateStatus,
  onResetPassword,
  onDeleteUser,
}: {
  mode: UserDialogMode
  user: UserManagementRecord | null
  nextRole: 'admin' | 'user'
  onClose: () => void
  onCreate: (payload: CreateUserInput) => Promise<void>
  onUpdateRole: () => Promise<void>
  onUpdateStatus: () => Promise<void>
  onResetPassword: (password: string) => Promise<void>
  onDeleteUser: () => Promise<void>
}) {
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState('')
  const [role, setRole] = useState<'admin' | 'user'>('user')
  const [temporaryPassword, setTemporaryPassword] = useState('')
  const [deleteConfirmed, setDeleteConfirmed] = useState(false)
  const submissionInProgress = useRef(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (submissionInProgress.current) return
    submissionInProgress.current = true
    setError('')
    setIsSaving(true)
    try {
      const form = new FormData(event.currentTarget)
      if (mode === 'create') {
        const fullName = String(form.get('full_name') ?? '').trim()
        if (!fullName) throw new Error('Enter the user’s full name.')
        await onCreate({
          full_name: fullName,
          email: String(form.get('email') ?? '').trim(),
          password: String(form.get('password') ?? ''),
          role,
        })
      } else if (mode === 'role') {
        await onUpdateRole()
      } else if (mode === 'status') {
        await onUpdateStatus()
      } else if (mode === 'delete') {
        if (!user || user.role !== 'user') throw new Error('Only a selected Regular User account can be deleted.')
        if (!deleteConfirmed) throw new Error('Confirm that you understand this deletion is permanent.')
        await onDeleteUser()
      } else {
        if (temporaryPassword.length < 12 || temporaryPassword.length > 128) {
          throw new Error('Temporary password must be between 12 and 128 characters.')
        }
        await onResetPassword(temporaryPassword)
      }
      onClose()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'The request could not be completed.')
    } finally {
      submissionInProgress.current = false
      setIsSaving(false)
    }
  }

  if (mode === 'delete') {
    const canDelete = user?.role === 'user' && deleteConfirmed && !isSaving
    return (
      <div className="case-dialog-backdrop user-delete-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget && !isSaving) onClose() }}>
        <section className="user-delete-dialog" role="dialog" aria-modal="true" aria-labelledby="user-delete-title" aria-describedby="user-delete-subtitle">
          <form onSubmit={submit}>
            <header className="user-delete-header">
              <span className="user-delete-icon" aria-hidden="true"><Trash2 size={25} strokeWidth={2.1} /></span>
              <div className="user-delete-heading-copy">
                <h2 id="user-delete-title">Delete User and All Associated Data?</h2>
                <p id="user-delete-subtitle">This action is permanent and cannot be undone.</p>
              </div>
              <button className="user-delete-close" type="button" onClick={onClose} disabled={isSaving} aria-label="Close dialog"><X size={21} /></button>
            </header>

            <section className="user-delete-account" aria-label="Selected user account">
              <strong className="user-delete-account__title">You are about to permanently delete:</strong>
              <div className="user-delete-account__details">
                <span className="user-delete-identity"><UserRound size={19} /><b>{user?.full_name?.trim() || 'Name not provided'}</b></span>
                <span className="user-delete-email"><Mail size={18} /><span>{user?.email || 'Email unavailable'}</span></span>
                <span className="user-delete-role">Regular User</span>
              </div>
            </section>

            <section className="user-delete-owned-data" aria-labelledby="user-delete-owned-title">
              <h3 id="user-delete-owned-title">The following data owned by this user will also be deleted:</h3>
              <div className="user-delete-data-grid">
                <div><UsersRound size={18} /><span>Patients</span></div>
                <div><Folder size={18} /><span>Cases</span></div>
                <div><ImageIcon size={18} /><span>Uploaded Images</span></div>
                <div><ChartNoAxesColumn size={18} /><span>Analysis Runs &amp; Results</span></div>
                <div><Layers size={18} /><span>Preprocessing Records</span></div>
                <div><Bell size={18} /><span>Notifications</span></div>
              </div>
            </section>

            <label className="user-delete-confirm">
              <input type="checkbox" checked={deleteConfirmed} onChange={(event) => setDeleteConfirmed(event.target.checked)} disabled={isSaving} />
              <span>I understand this will permanently delete the user account and all associated data.</span>
            </label>
            {error && <p className="user-delete-error" role="alert">{error}</p>}

            <footer className="user-delete-actions">
              <button className="user-delete-cancel" type="button" onClick={onClose} disabled={isSaving}>Cancel</button>
              <button className="user-delete-submit" type="submit" disabled={!canDelete}>
                <Trash2 size={16} />
                {isSaving ? 'Deleting…' : 'Delete User and All Associated Data'}
              </button>
            </footer>
          </form>
        </section>
      </div>
    )
  }

  const title = mode === 'create'
    ? 'Add new user'
    : mode === 'role'
      ? 'Confirm role change'
      : mode === 'status'
        ? `${user?.is_active ? 'Deactivate' : 'Activate'} account`
        : 'Set temporary password'

  return (
    <div className="case-dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget && !isSaving) onClose() }}>
      <section className="case-dialog user-management-dialog" role="dialog" aria-modal="true" aria-labelledby="user-dialog-title">
        <div className="case-dialog__heading">
          <div><span className="eyebrow page-eyebrow">USER MANAGEMENT</span><h2 id="user-dialog-title">{title}</h2></div>
          <button className="icon-button" type="button" onClick={onClose} disabled={isSaving} aria-label="Close dialog"><X size={18} /></button>
        </div>
        <form className="case-form" onSubmit={submit}>
          {mode === 'create' && <>
            <label>Full name <input name="full_name" autoComplete="name" maxLength={120} required /></label>
            <label>Email address <input name="email" type="email" autoComplete="email" maxLength={320} required /></label>
            <label>Initial password <input name="password" type="password" autoComplete="new-password" minLength={12} maxLength={128} required /></label>
            <label>Role <select value={role} onChange={(event) => setRole(event.target.value as 'admin' | 'user')}><option value="user">Regular user</option><option value="admin">Admin</option></select></label>
            <p className="user-dialog-note">Share the initial password securely. The API never returns the password or stored hash.</p>
          </>}
          {mode === 'role' && <p className="user-dialog-copy">Change {user?.full_name || user?.email} to <strong>{nextRole === 'admin' ? 'Admin' : 'Regular user'}</strong>? Backend safeguards will prevent removal of the last active administrator.</p>}
          {mode === 'status' && <p className="user-dialog-copy">{user?.is_active
            ? `Deactivate ${user.full_name || user.email}? They will no longer be able to log in. Their patients, cases and image records will remain.`
            : `Reactivate ${user?.full_name || user?.email}? They will be able to log in again.`}</p>}
          {mode === 'reset' && <>
            <p className="user-dialog-copy">Set a temporary password for <strong>{user?.full_name || user?.email}</strong>. Existing sessions will be invalidated and the user must change this password after signing in.</p>
            <label>Temporary password <input type="password" autoComplete="new-password" minLength={12} maxLength={128} value={temporaryPassword} onChange={(event) => setTemporaryPassword(event.target.value)} required /></label>
          </>}
          {error && <p className="user-form-error" role="alert">{error}</p>}
          <div className="user-dialog-actions">
            <button className="button button--secondary" type="button" onClick={onClose} disabled={isSaving}>Cancel</button>
            <button className="button button--primary" type="submit" disabled={isSaving}>{isSaving ? 'Working…' : mode === 'create' ? 'Create user' : mode === 'role' ? 'Confirm role' : mode === 'status' ? (user?.is_active ? 'Deactivate account' : 'Activate account') : 'Set temporary password'}</button>
          </div>
        </form>
      </section>
    </div>
  )
}
