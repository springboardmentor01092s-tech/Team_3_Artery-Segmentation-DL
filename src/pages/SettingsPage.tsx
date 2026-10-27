import { Bell, Eye, KeyRound, Shield, SlidersHorizontal, UserRound } from 'lucide-react'
import PageHeader from '../components/PageHeader'
import Panel from '../components/Panel'
import WorkspaceNotice from '../components/WorkspaceNotice'
import { useAuth } from '../auth/AuthProvider'

export default function SettingsPage() {
  const { user } = useAuth()
  return (
    <div className="feature-page settings-page">
      <WorkspaceNotice />
      <PageHeader title="Settings" description="Review account access and workspace preferences." />
      <div className="settings-layout">
        <div className="settings-main-column">
          <Panel title="Account profile" className="settings-profile-panel">
            <div className="settings-profile-row"><span className="settings-avatar">{user?.email.slice(0, 1).toUpperCase() ?? 'U'}</span><div><strong>{user?.email}</strong><span>{user?.role === 'admin' ? 'Administrator' : 'Regular user'} · authenticated account</span></div><button className="button button--secondary button--small" type="button" disabled>Edit profile</button></div>
            <div className="settings-detail-grid"><div><span>Authentication</span><strong>Connected</strong></div><div><span>Account creation</span><strong>Administrator-managed</strong></div></div>
          </Panel>
          <Panel title="Sign-in and access" className="settings-access-panel">
            <div className="settings-option-row"><span className="settings-option-icon"><KeyRound size={17} /></span><div><strong>Authentication</strong><small>Account sign-in is connected; password recovery is not configured.</small></div><span className="state-pill state-pill--muted">Recovery unavailable</span></div>
            <div className="settings-option-row"><span className="settings-option-icon"><Shield size={17} /></span><div><strong>Account registration</strong><small>Public registration is disabled; accounts are created by an administrator.</small></div><span className="state-pill state-pill--muted">Admin managed</span></div>
            <div className="settings-option-row"><span className="settings-option-icon"><Eye size={17} /></span><div><strong>Role-based access</strong><small>Administrator and regular-user access is checked by the backend.</small></div><span className="state-pill state-pill--muted">Enforced</span></div>
          </Panel>
        </div>
        <div className="settings-side-column">
          <Panel title="Notifications" className="settings-notifications-panel">
            <p className="panel-description">Choose which workspace updates to receive.</p>
            <label className="settings-toggle-row"><span className="settings-option-icon"><Bell size={17} /></span><span><strong>Analysis status updates</strong><small>Completion and failure notices</small></span><input type="checkbox" disabled aria-label="Analysis status updates" /></label>
            <label className="settings-toggle-row"><span className="settings-option-icon"><UserRound size={17} /></span><span><strong>Account activity</strong><small>Invitations and access changes</small></span><input type="checkbox" disabled aria-label="Account activity" /></label>
          </Panel>
          <Panel title="Display preferences" className="settings-display-panel">
            <p className="panel-description">Visual preferences for this workspace.</p>
            <label className="settings-label">Density<select disabled defaultValue="comfortable"><option value="comfortable">Comfortable</option><option value="compact">Compact</option></select></label>
            <div className="settings-option-row"><span className="settings-option-icon"><SlidersHorizontal size={17} /></span><div><strong>Color theme</strong><small>Light theme</small></div><span className="state-pill state-pill--muted">Current</span></div>
          </Panel>
          <div className="settings-footnote">Preferences cannot be saved in this frontend preview.</div>
        </div>
      </div>
    </div>
  )
}
