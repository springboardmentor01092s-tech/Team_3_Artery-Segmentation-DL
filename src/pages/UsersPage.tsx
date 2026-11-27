import { useCallback, useEffect, useMemo, useState } from 'react'
import { KeyRound, RefreshCw, ShieldCheck, Trash2, UserCheck, UserRoundPlus, UserRoundX, UsersRound } from 'lucide-react'
import EmptyState from '../components/EmptyState'
import Panel from '../components/Panel'
import { useAuth } from '../auth/AuthProvider'
import { apiRequest } from '../auth/api'
import { useNotifications } from '../features/notifications/NotificationProvider'
import UserManagementDialog, { type CreateUserInput, type UserDialogMode } from '../features/users/UserManagementDialog'
import {
  filterAndSortUsers,
  getCleanupStatusErrorMessage,
  getUserActionAvailability,
  getUserPage,
  type UserManagementRecord,
} from '../features/users/user-management.mjs'

const PAGE_SIZE = 10

type PendingDeletionCleanup = {
  cleanup_id: string
  created_at: string | null
  storage_file_count: number
  analysis_run_count: number
  last_error: string | null
}

function formatDate(value: string | null | undefined) {
  if (!value) return 'Not available'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Not available' : date.toLocaleString()
}

export default function UsersPage() {
  const { user: currentUser } = useAuth()
  const { addUserManagementNotice } = useNotifications()
  const [users, setUsers] = useState<UserManagementRecord[]>([])
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [roleFilter, setRoleFilter] = useState<'all' | 'admin' | 'user'>('all')
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive'>('all')
  const [sort, setSort] = useState<'newest' | 'oldest' | 'name-asc' | 'name-desc'>('newest')
  const [page, setPage] = useState(1)
  const [isLoading, setIsLoading] = useState(true)
  const [isMutating, setIsMutating] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [dialog, setDialog] = useState<UserDialogMode | null>(null)
  const [nextRole, setNextRole] = useState<'admin' | 'user'>('user')
  const [keepSelectionEmpty, setKeepSelectionEmpty] = useState(false)
  const [pendingCleanups, setPendingCleanups] = useState<PendingDeletionCleanup[]>([])
  const [cleanupLoadError, setCleanupLoadError] = useState('')

  const reloadUsers = useCallback(async () => {
    setIsLoading(true)
    setError('')
    try {
      const records = await apiRequest<UserManagementRecord[]>('/users')
      setUsers(records)
      setSelectedUserId((current) => current && records.some((record) => record.id === current)
        ? current
        : null)
      return records
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to load user accounts.')
      return null
    } finally {
      setIsLoading(false)
    }
  }, [])

  const reloadPendingCleanups = useCallback(async () => {
    try {
      const records = await apiRequest<PendingDeletionCleanup[]>('/users/deletion-cleanups')
      setPendingCleanups(records)
      setCleanupLoadError('')
      return records
    } catch (cause) {
      setCleanupLoadError(getCleanupStatusErrorMessage(cause))
      return null
    }
  }, [])

  useEffect(() => {
    void reloadUsers()
    void reloadPendingCleanups()
  }, [reloadPendingCleanups, reloadUsers])

  const filteredUsers = useMemo(() => filterAndSortUsers(users, {
    query,
    role: roleFilter,
    status: statusFilter,
    sort,
  }), [users, query, roleFilter, statusFilter, sort])
  const pageData = useMemo(() => getUserPage(filteredUsers, page, PAGE_SIZE), [filteredUsers, page])
  const selectedUser = users.find((record) => record.id === selectedUserId) ?? null
  const isCurrentUserSelected = Boolean(selectedUser && selectedUser.id === currentUser?.id)
  const actionAvailability = useMemo(
    () => getUserActionAvailability(selectedUser, currentUser, users),
    [selectedUser, currentUser, users],
  )

  useEffect(() => {
    if (selectedUserId && !filteredUsers.some((record) => record.id === selectedUserId)) {
      setSelectedUserId(filteredUsers[0]?.id ?? null)
    } else if (!selectedUserId && filteredUsers.length && !keepSelectionEmpty) {
      setSelectedUserId(filteredUsers[0].id)
    }
  }, [filteredUsers, selectedUserId, keepSelectionEmpty])

  function resetPage() {
    setPage(1)
    setSuccess('')
  }

  async function createUser(payload: CreateUserInput) {
    setIsMutating(true)
    setError('')
    try {
      const created = await apiRequest<UserManagementRecord>('/users', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      setUsers((current) => [created, ...current.filter((record) => record.id !== created.id)])
      setSelectedUserId(created.id)
      setKeepSelectionEmpty(false)
      setQuery('')
      setRoleFilter('all')
      setStatusFilter('all')
      setSort('newest')
      setPage(1)
      addUserManagementNotice(`Account created for ${created.full_name || created.email}.`)
      await reloadUsers()
    } catch (cause) {
      throw cause
    } finally {
      setIsMutating(false)
    }
  }

  async function updateRole() {
    if (!selectedUser) return
    setIsMutating(true)
    setError('')
    try {
      const updated = await apiRequest<UserManagementRecord>(`/users/${selectedUser.id}/role`, {
        method: 'PATCH',
        body: JSON.stringify({ role: nextRole }),
      })
      setUsers((current) => current.map((record) => record.id === updated.id ? updated : record))
      setSuccess(`Role updated for ${updated.full_name || updated.email}.`)
    } catch (cause) {
      throw cause
    } finally {
      setIsMutating(false)
    }
  }

  async function updateStatus() {
    if (!selectedUser) return
    setIsMutating(true)
    setError('')
    try {
      const updated = await apiRequest<UserManagementRecord>(`/users/${selectedUser.id}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active: !selectedUser.is_active }),
      })
      setUsers((current) => current.map((record) => record.id === updated.id ? updated : record))
      setSuccess(`${updated.full_name || updated.email} is now ${updated.is_active ? 'active' : 'inactive'}.`)
    } catch (cause) {
      throw cause
    } finally {
      setIsMutating(false)
    }
  }

  async function resetPassword(temporaryPassword: string) {
    if (!selectedUser) return
    setIsMutating(true)
    setError('')
    try {
      const updated = await apiRequest<UserManagementRecord>(`/users/${selectedUser.id}/password-reset`, {
        method: 'POST',
        body: JSON.stringify({ temporary_password: temporaryPassword }),
      })
      setUsers((current) => current.map((record) => record.id === updated.id ? updated : record))
      setSuccess(`Temporary password set for ${updated.full_name || updated.email}. Their prior sessions are invalidated.`)
    } catch (cause) {
      throw cause
    } finally {
      setIsMutating(false)
    }
  }

  async function deleteUser() {
    if (!selectedUser || selectedUser.role !== 'user') return
    const deletedName = selectedUser.full_name || selectedUser.email
    setIsMutating(true)
    setError('')
    setSuccess('')
    try {
      const result = await apiRequest<{
        deleted_user_id: string
        cleanup_status: 'complete' | 'pending'
        cleanup_id: string | null
        detail: string
      }>(`/users/${selectedUser.id}`, { method: 'DELETE' })
      setUsers((current) => current.filter((record) => record.id !== result.deleted_user_id))
      setSelectedUserId(null)
      setKeepSelectionEmpty(true)
      setDialog(null)
      addUserManagementNotice(result.cleanup_status === 'complete'
        ? `User ${deletedName} has been deleted.`
        : `User ${deletedName} has been deleted; managed file cleanup is pending.`)
      await reloadUsers()
      await reloadPendingCleanups()
    } catch (cause) {
      throw cause
    } finally {
      setIsMutating(false)
    }
  }

  async function retryDeletionCleanup(cleanupId: string) {
    setIsMutating(true)
    setError('')
    try {
      const result = await apiRequest<{ status: 'complete' | 'pending' | 'not_deleted'; detail: string }>(
        `/users/deletion-cleanups/${cleanupId}/retry`,
        { method: 'POST' },
      )
      setSuccess(result.detail)
      if (result.status === 'not_deleted') {
        setKeepSelectionEmpty(false)
        await reloadUsers()
      }
      await reloadPendingCleanups()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'File cleanup retry failed.')
    } finally {
      setIsMutating(false)
    }
  }

  function openRoleDialog() {
    if (!selectedUser || !actionAvailability.canChangeRole) return
    setNextRole(selectedUser.role === 'admin' ? 'user' : 'admin')
    setError('')
    setSuccess('')
    setDialog('role')
  }

  function openStatusDialog() {
    if (!selectedUser) return
    if (selectedUser.is_active && !actionAvailability.canDeactivate) return
    setError('')
    setSuccess('')
    setDialog('status')
  }

  function openDialog(mode: UserDialogMode) {
    setError('')
    setSuccess('')
    setDialog(mode)
  }

  return (
    <div className="feature-page users-page">
      <div className="users-toolbar">
        <button className="button button--primary button--small" type="button" onClick={() => openDialog('create')} disabled={isLoading || isMutating}><UserRoundPlus size={16} /> Add new user</button>
      </div>
      <div className="users-notice-stack">
        {error && <div className="users-feedback users-feedback--error" role="alert"><span>{error}</span><button type="button" onClick={() => void reloadUsers()} disabled={isLoading}><RefreshCw size={14} /> Retry</button></div>}
        {success && <div className="users-feedback users-feedback--success" role="status"><span>{success}</span><button type="button" onClick={() => setSuccess('')} aria-label="Dismiss success message">×</button></div>}
        {cleanupLoadError && <div className="users-feedback users-feedback--error" role="alert">{cleanupLoadError}</div>}
        {pendingCleanups.length > 0 && <div className="users-feedback users-feedback--warning" role="status"><div><strong>File cleanup needs attention</strong><ul>{pendingCleanups.map((cleanup) => <li key={cleanup.cleanup_id}>Pending managed files: {cleanup.storage_file_count}; analysis artifact folders: {cleanup.analysis_run_count}. <button type="button" onClick={() => void retryDeletionCleanup(cleanup.cleanup_id)} disabled={isMutating}>Retry cleanup</button></li>)}</ul></div></div>}
      </div>

      <Panel title="Search and filters" className="user-filters-panel users-themed-panel users-themed-panel--blue">
        <div className="user-filter-row">
          <input type="search" placeholder="Search users by name or email..." aria-label="Search users by name or email" value={query} onChange={(event) => { setQuery(event.target.value); resetPage() }} />
          <label>Role<select aria-label="Filter users by role" value={roleFilter} onChange={(event) => { setRoleFilter(event.target.value as typeof roleFilter); resetPage() }}><option value="all">All roles</option><option value="admin">Admin</option><option value="user">Regular user</option></select></label>
          <label>Status<select aria-label="Filter users by status" value={statusFilter} onChange={(event) => { setStatusFilter(event.target.value as typeof statusFilter); resetPage() }}><option value="all">All statuses</option><option value="active">Active</option><option value="inactive">Inactive</option></select></label>
          <label>Sort by<select aria-label="Sort users" value={sort} onChange={(event) => { setSort(event.target.value as typeof sort); resetPage() }}><option value="newest">Newest first</option><option value="oldest">Oldest first</option><option value="name-asc">Name A–Z</option><option value="name-desc">Name Z–A</option></select></label>
        </div>
      </Panel>

      <Panel title={`Users (${users.length})`} className="user-list-panel users-themed-panel users-themed-panel--teal">
          <div className="data-table-wrap user-table-scroll">
            <table className="data-table user-table">
              <thead><tr>{['#', 'Name', 'Email', 'Role', 'Status', 'Created', 'Last login'].map((heading) => <th key={heading} scope="col">{heading}</th>)}</tr></thead>
              <tbody>
                {isLoading && <tr><td colSpan={7}><div className="user-table-message" role="status">Loading user accounts…</div></td></tr>}
                {!isLoading && users.length === 0 && !error && <tr><td colSpan={7}><EmptyState icon={UsersRound} title="No user accounts yet" description="Accounts created by an administrator will appear here." /></td></tr>}
                {!isLoading && users.length > 0 && filteredUsers.length === 0 && <tr><td colSpan={7}><EmptyState icon={UsersRound} title="No matching users" description="Adjust the search or filters to see other accounts." /></td></tr>}
                {!isLoading && pageData.items.map((record, index) => (
                  <tr key={record.id} className={record.id === selectedUserId ? 'user-row user-row--selected' : 'user-row'} onClick={() => { setKeepSelectionEmpty(false); setSelectedUserId(record.id) }}>
                    <td>{pageData.start + index}</td>
                    <td><button className="user-name-button" type="button" onClick={(event) => { event.stopPropagation(); setSelectedUserId(record.id) }}>{record.full_name || 'Name not provided'}</button></td>
                    <td>{record.email}</td>
                    <td><span className={`role-chip ${record.role === 'admin' ? 'role-chip--admin' : 'role-chip--regular'}`}>{record.role === 'admin' ? 'Admin' : 'Regular user'}</span></td>
                    <td><span className={record.is_active ? 'user-status user-status--active' : 'user-status user-status--inactive'}>{record.is_active ? 'Active' : 'Inactive'}</span></td>
                    <td>{formatDate(record.created_at)}</td>
                    <td>Not available</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="table-pagination">
            <span>Showing {pageData.start}–{pageData.end} of {pageData.total} matching users</span>
            <div>
              <button type="button" onClick={() => setPage((current) => Math.max(1, current - 1))} disabled={pageData.page <= 1} aria-label="Previous page">‹</button>
              <button className="pagination-current" type="button" aria-current="page" disabled>{pageData.page}</button>
              <button type="button" onClick={() => setPage((current) => Math.min(pageData.pageCount, current + 1))} disabled={pageData.page >= pageData.pageCount} aria-label="Next page">›</button>
            </div>
          </div>
      </Panel>

      <Panel title="Account Actions" className="account-actions-panel users-themed-panel users-themed-panel--violet">
            {isCurrentUserSelected && selectedUser?.role === 'admin' && (
              <p className="account-actions-note" role="note">
                {!actionAvailability.canChangeRole
                  ? 'Account actions are unavailable for your own administrator account.'
                  : 'Password reset and deactivation are unavailable for your own administrator account.'}
              </p>
            )}
            {!selectedUser && <p className="account-actions-note" role="status">Select a user from the list to view available account actions.</p>}
            <div className="account-actions-grid">
            <button className="button account-action-button account-action-button--reset" type="button" onClick={() => openDialog('reset')} disabled={!selectedUser || !actionAvailability.canResetPassword || isMutating} title={selectedUser?.id === currentUser?.id ? 'Ask another administrator to reset your password.' : undefined}><KeyRound size={16} /> Reset password</button>
            <button className="button account-action-button account-action-button--role" type="button" onClick={openRoleDialog} disabled={!selectedUser || !actionAvailability.canChangeRole || isMutating} title={!actionAvailability.canChangeRole ? 'The last active administrator cannot be demoted.' : undefined}><ShieldCheck size={16} /> Change role</button>
            <button className="button account-action-button account-action-button--status" type="button" onClick={openStatusDialog} disabled={!selectedUser || isMutating || (selectedUser.is_active && !actionAvailability.canDeactivate)} title={selectedUser && selectedUser.id === currentUser?.id ? 'You cannot deactivate your own account.' : selectedUser?.role === 'admin' && selectedUser.is_active && !actionAvailability.canDeactivate ? 'The last active administrator cannot be deactivated.' : undefined}>
              {selectedUser?.is_active ? <><UserRoundX size={15} /> Deactivate account</> : <><UserCheck size={15} /> Activate account</>}
            </button>
            {selectedUser?.role === 'user' && <button className="button button--danger account-action-button account-action-button--delete" type="button" onClick={() => openDialog('delete')} disabled={isMutating}><Trash2 size={16} /> Delete user</button>}
            </div>
      </Panel>

      {dialog && <UserManagementDialog
        mode={dialog}
        user={selectedUser}
        nextRole={nextRole}
        onClose={() => setDialog(null)}
        onCreate={createUser}
        onUpdateRole={updateRole}
        onUpdateStatus={updateStatus}
        onResetPassword={resetPassword}
        onDeleteUser={deleteUser}
      />}
    </div>
  )
}
