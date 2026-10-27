import { useState } from 'react'
import { KeyRound, ShieldCheck, UserRoundPlus, UsersRound, UserX } from 'lucide-react'
import EmptyDataTable from '../components/EmptyDataTable'
import EmptyState from '../components/EmptyState'
import PageHeader from '../components/PageHeader'
import Panel from '../components/Panel'
import WorkspaceNotice from '../components/WorkspaceNotice'

export default function UsersPage() {
  const [roleFilter, setRoleFilter] = useState('all')
  return (
    <div className="feature-page users-page">
      <WorkspaceNotice />
      <PageHeader title="User Management" description="Review workspace access and role permissions." eyebrow="ADMINISTRATION" action={<button className="button button--primary button--small" type="button" disabled title="Account invitations require the backend."><UserRoundPlus size={16} /> Add new user</button>} />
      <div className="admin-preview-badge"><ShieldCheck size={15} /> Admin preview role · this page is hidden from regular-user preview</div>
      <Panel title="Search and filters" className="user-filters-panel">
        <div className="user-filter-row"><input type="search" placeholder="Search users by name, email, or role..." aria-label="Search users" disabled /><label>Role<select value={roleFilter} onChange={(event) => setRoleFilter(event.target.value)}><option value="all">All roles</option><option value="admin">Admin</option><option value="regular">Regular user</option></select></label><label>Status<select disabled defaultValue="all"><option value="all">All statuses</option></select></label><label>Sort by<select disabled defaultValue="newest"><option value="newest">Newest first</option></select></label></div>
      </Panel>
      <div className="user-management-layout">
        <Panel title="Users (0)" className="user-list-panel">
          <EmptyDataTable columns={['#', 'Name', 'Email', 'Role', 'Status', 'Last login', 'Actions']} icon={UsersRound} title="No user accounts connected" description="User accounts will appear here after administrator-managed authentication is implemented." />
          <div className="table-pagination"><span>Showing 0 users</span><div><button type="button" disabled aria-label="Previous page">‹</button><button className="pagination-current" type="button" disabled>1</button><button type="button" disabled aria-label="Next page">›</button></div></div>
        </Panel>
        <aside className="user-detail-stack">
          <Panel title="User details"><EmptyState icon={UsersRound} title="No user selected" description="Select a connected account to view its details." /></Panel>
          <Panel title="Role permissions" className="role-permissions-panel">
            <div className="role-permission-group"><span className="role-chip role-chip--admin">Admin</span><ul><li>Manage accounts and workspace settings</li><li>Manage patients and cases</li><li>Upload images and start configured analyses</li><li>View results and generate reports</li></ul></div>
            <div className="role-permission-group"><span className="role-chip role-chip--regular">Regular user</span><ul><li>Manage permitted patients and cases</li><li>Upload images and start configured analyses</li><li>View available results and reports</li></ul></div>
          </Panel>
          <Panel title="Account actions" className="account-actions-panel">
            <button className="button button--secondary" type="button" disabled><KeyRound size={15} /> Reset password</button>
            <button className="button button--secondary" type="button" disabled><UserX size={15} /> Deactivate account</button>
            <p>Account changes are unavailable until authentication is connected.</p>
          </Panel>
        </aside>
      </div>
    </div>
  )
}
